"""Debrief con IA: instrucciones, generación (Claude Code o texto pegado a mano), validación y caché.

La IA solo redacta: recibe las cifras del motor (hechos.py) y el validador marca cualquier cifra del
texto que no esté en ellas. El texto se guarda con la huella de sus cifras: mientras no cambien
(nueva versión del motor, viento de referencia…), se reutiliza sin volver a llamar a la IA.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time

from ..ingesta.almacen import Almacen
from . import hechos as hechos_mod
from .validar import no_verificadas

COMUN = """Eres el analista de rendimiento de un equipo de {clase}. Escribe en español de España, para la tripulación, de forma directa y concreta.

Reglas estrictas:
- Usa SOLO las cifras de los DATOS. No calcules cifras nuevas (ni diferencias, ni medias, ni porcentajes): si necesitas una comparación, usa los campos que ya la traen (p. ej. «..._frente_a_la_mediana_kn», «..._mediana_flota_...», «..._top5_...»).
- La referencia principal es el TOP 5 (los 5 primeros de la prueba o de la general, sin contar este barco): compara primero con él (campos «top5…», «…_top5_…», «…_frente_al_top5_…») y usa la mediana de la flota solo como contexto. Las conclusiones y las claves deben salir de las diferencias con el top 5.
- Cita las cifras tal cual o redondeadas, con coma decimal y un espacio antes de la unidad (4,06 kn; 87 m; 54 s; 10,5°; 66 %). Los tiempos, en segundos o como mm:ss. La unidad de cada campo va en su nombre: _kn, _m, _s, _grados (°), _pct (%).
- La corriente es ESTIMADA y tiene un nivel de confianza: si es baja, no la uses para explicar resultados. Úsala para explicar laylines o la ventaja de un lado solo si la confianza es alta o media.
- Todo lo relativo al viento, VMG, TWA, maniobras, laylines y barco fantasma es ESTIMADO (no hay anemómetro): no lo presentes como medido.
- Los huecos de telemetría y la calidad de datos son limitaciones de RaceSense, no errores de la tripulación: menciónalos solo como límite del análisis.
- Si un dato falta o la calidad de datos es baja, dilo en lugar de interpretarlo. No inventes causas que los datos no muestren; si propones una causa, preséntala como hipótesis.
- Izquierda/derecha son lados del campo, mirando a barlovento (en las puertas, mirando a sotavento, como indica el dato). No los traduzcas a babor/estribor ni a amuras.
- Sin introducción ni despedida. Formato Markdown exactamente con estos encabezados:
"""

PRUEBA = COMUN + """
## Resumen
(2–3 frases: resultado y lo que más lo explica)
## Salida
## Ceñidas
## Popas
## Maniobras, laylines y puertas
## 3 claves para la próxima prueba
(lista numerada de 3 puntos accionables)

Máximo 350 palabras.
"""

CAMPEONATO = COMUN + """
## Balance
(2–3 frases)
## 3 puntos fuertes
(lista numerada)
## 3 áreas de mejora
(lista numerada)
## Prioridades de entrenamiento
(lista numerada de 3 a 5 ejercicios o hábitos concretos, ordenados por impacto)

Máximo 400 palabras.
"""


class IANoDisponible(RuntimeError):
    pass


def instrucciones(datos: dict) -> str:
    base = CAMPEONATO if datos.get("tipo") == "debrief del campeonato" else PRUEBA
    base = base.replace("{clase}", datos.get("clase") or "vela")
    return base + "\nDATOS:\n```json\n" + json.dumps(datos, ensure_ascii=False, indent=1) + "\n```\n"


def huella(datos: dict) -> str:
    return hashlib.sha1(json.dumps(datos, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


# ---------------------------------------------------------------- generación

def comando_claude() -> str | None:
    return shutil.which(os.environ.get("FASTTACK_CLAUDE", "claude"))


def generar_claude_code(prompt: str, timeout_s: int = 300) -> str:
    """Pide el texto a Claude Code instalado en este ordenador (usa la cuenta con la que se inició sesión)."""
    cmd = comando_claude()
    if not cmd:
        raise IANoDisponible("Claude Code no está instalado en este ordenador (comando «claude»).")
    with tempfile.TemporaryDirectory() as tmp:  # carpeta vacía: sin instrucciones de ningún proyecto
        try:
            r = subprocess.run([cmd, "-p", "--output-format", "text"], input=prompt, capture_output=True,
                               text=True, timeout=timeout_s, cwd=tmp)
        except subprocess.TimeoutExpired as e:
            raise IANoDisponible("Claude Code ha tardado demasiado en responder.") from e
    texto = (r.stdout or "").strip()
    if r.returncode != 0 or not texto:
        detalle = (r.stderr or r.stdout or "").strip().splitlines()[-1:] or ["sin respuesta"]
        raise IANoDisponible(f"Claude Code no ha podido generar el texto: {detalle[0][:300]}")
    return texto


# ---------------------------------------------------------------- caché

def leer(alm: Almacen, camp_id: str, ambito: str, barco: str) -> dict | None:
    r = alm.sql("select * from debrief where campeonato=? and ambito=? and barco=?", (camp_id, ambito, barco))
    if not r:
        return None
    d = dict(r[0])
    d["avisos"] = json.loads(d["avisos"] or "[]")
    return d


def guardar(alm: Almacen, camp_id: str, ambito: str, barco: str, datos: dict, texto: str, origen: str) -> dict:
    avisos = no_verificadas(texto, datos)
    alm.sql("insert into debrief (campeonato, ambito, barco, huella, texto, origen, avisos, creado_en) "
            "values (?, ?, ?, ?, ?, ?, ?, ?) on conflict(campeonato, ambito, barco) do update set "
            "huella=excluded.huella, texto=excluded.texto, origen=excluded.origen, avisos=excluded.avisos, "
            "creado_en=excluded.creado_en",
            (camp_id, ambito, barco, huella(datos), texto.strip(), origen, json.dumps(avisos, ensure_ascii=False),
             int(time.time() * 1000)))
    return leer(alm, camp_id, ambito, barco)


def datos_de(alm: Almacen, camp_id: str, ambito: str, barco: str) -> dict:
    """Cifras para el debrief de una prueba (ámbito = su clave) o del campeonato."""
    from .. import servicio
    from ..ingesta import campeonato as camp_mod
    camp = camp_mod.leer(alm, camp_id)
    if camp is None:
        raise KeyError(camp_id)
    nombres = {b["clave"]: b for b in camp["barcos"]}
    if ambito == "campeonato":
        res = servicio.resumen_campeonato(alm, camp_id)
        if res["pendientes"]:
            raise ValueError("Faltan pruebas por analizar: abre antes el resumen del campeonato.")
        if barco not in res["barcos"]:
            raise ValueError("Este barco no tiene llegadas en el campeonato.")
        return hechos_mod.de_campeonato(res, barco, camp.get("nombre") or "", nombres, camp.get("clase"))
    an = servicio.analisis_prueba(alm, camp_id, ambito)
    if not any(c["vela"] == barco for c in an["clasificacion"]) and barco not in an["rendimiento"]:
        raise ValueError("Este barco no tiene datos en esta prueba.")
    return hechos_mod.de_prueba(an, barco, nombres, camp.get("clase"))
