"""Debrief con IA: instrucciones, generación (Claude Code o texto pegado a mano), validación y caché.

La IA solo redacta: recibe las cifras del motor (hechos.py) y el validador marca cualquier cifra del
texto que no esté en ellas. El texto se guarda con la huella de sus cifras: mientras no cambien
(nueva versión del motor, viento de referencia…), se reutiliza sin volver a llamar a la IA.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
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
- En las laylines sobrepasadas distingue el motivo que dan los datos: por tráfico (no podía virar, o la layline ya estaba ocupada) o por cálculo. Solo las de cálculo son un error de estimación; las de tráfico son una decisión táctica o forzada.
- Cuando hables de un tramo, nómbralo siempre con su nombre concreto y la prueba («Popa 2 de la prueba 3»). Si la cifra es una media de varios tramos («vmg_media_de_las_popas…»), dilo así («media de las dos popas»); no la atribuyas a un tramo.
- Cita las cifras tal cual o redondeadas, con coma decimal y un espacio antes de la unidad (4,06 kn; 87 m; 54 s; 10,5°; 66 %). Los tiempos, en segundos o como mm:ss. La unidad de cada campo va en su nombre: _kn, _m, _s, _grados (°), _pct (%).
- La corriente es ESTIMADA y tiene un nivel de confianza: si es baja, no la uses para explicar resultados. Úsala para explicar laylines o la ventaja de un lado solo si la confianza es alta o media.
- Todo lo relativo al viento, VMG, TWA, maniobras, laylines y barco fantasma es ESTIMADO (no hay anemómetro): no lo presentes como medido.
- Los huecos de telemetría y la calidad de datos son limitaciones de RaceSense, no errores de la tripulación: menciónalos solo como límite del análisis.
- Si un dato falta o la calidad de datos es baja, dilo en lugar de interpretarlo. No inventes causas que los datos no muestren; si propones una causa, preséntala como hipótesis.
- Izquierda/derecha son lados del campo, mirando a barlovento (en las puertas, mirando a sotavento, como indica el dato). No los traduzcas a babor/estribor ni a amuras.
- Si los DATOS traen «sesion_propia» con un solo barco, no hay flota ni top 5: no hables de puestos ni de la flota; compara entre pruebas y entre tramos del propio barco (evolución, regularidad, ceñida frente a popa) y recuerda que llegadas y balizas son estimadas.
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

DIA = COMUN + """
## Balance del día
(2–3 frases: resultado del día y cómo queda en la general)
## Lo que funcionó
(lista de 2–3 puntos)
## Lo que hay que corregir
(lista de 2–3 puntos)
## Claves para mañana
(lista numerada de 3 puntos accionables)

Máximo 350 palabras.
"""

CAMPEONATO = COMUN + """
Si «estado.campeonato_en_curso» es verdadero, el campeonato no ha terminado: habla de lo disputado hasta ahora y orienta las prioridades a las pruebas que quedan.

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
    base = {"debrief del campeonato": CAMPEONATO, "debrief del día": DIA}.get(datos.get("tipo"), PRUEBA)
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


# Con un solo barco (sesión con archivos .vkx) las comparaciones con la flota son consigo mismo
_DE_FLOTA = re.compile(r"mediana_flota|frente_a_la_mediana|top5|top_1[05]|puesto|detras_del|distancia_al_primero|"
                       r"general|puntos|descart|barcos_llegados|barcos_ya_en_la_layline|de_la_flota|eligieron|"
                       r"resultado_del_dia|veces_en_el_top|salidas_con_puesto|comparacion|recibio_primero")


def _sin_flota(o):
    if isinstance(o, dict):
        return {k: _sin_flota(v) for k, v in o.items() if not _DE_FLOTA.search(k)}
    if isinstance(o, list):
        return [_sin_flota(v) for v in o]
    return o


def datos_de(alm: Almacen, camp_id: str, ambito: str, barco: str) -> dict:
    """Cifras para el debrief de una prueba (ámbito = su clave), de un día o del campeonato."""
    from ..ingesta import campeonato as camp_mod
    h = _datos_de(alm, camp_id, ambito, barco)
    camp = camp_mod.leer(alm, camp_id)
    if camp.get("fuente") == "vkx":
        n = len(camp["barcos"])
        if n <= 1:
            h = _sin_flota(h)
        h["sesion_propia"] = {"fuente": "archivos .vkx del Atlas 2 (sin RaceSense)", "barcos_con_archivo": n,
                              "llegadas_y_balizas": "estimadas con las trazas de los barcos",
                              "comparacion_con_la_flota": "no hay (un solo barco)" if n <= 1 else f"solo entre {n} barcos"}
    return h


def _datos_de(alm: Almacen, camp_id: str, ambito: str, barco: str) -> dict:
    from .. import servicio
    from ..ingesta import campeonato as camp_mod
    camp = camp_mod.leer(alm, camp_id)
    if camp is None:
        raise KeyError(camp_id)
    nombres = {b["clave"]: b for b in camp["barcos"]}
    en_curso = bool(camp.get("fin")) and camp["fin"] + 86_400_000 > time.time() * 1000
    if ambito == "campeonato":
        # Con las pruebas disputadas y analizadas hasta ahora: no hace falta que el campeonato termine
        res = servicio.resumen_campeonato(alm, camp_id)
        if barco not in res["barcos"]:
            raise ValueError("Este barco no tiene llegadas en el campeonato.")
        h = hechos_mod.de_campeonato(res, barco, camp.get("nombre") or "", nombres, camp.get("clase"))
        h["estado"] = {"campeonato_en_curso": en_curso, "pruebas_disputadas_hasta_ahora": len(res["pruebas"]),
                       "pruebas_aun_sin_analizar": len(res["pendientes"])}
        return h
    if ambito.startswith("dia:"):
        dia = ambito[4:]
        res = servicio.resumen_campeonato(alm, camp_id, descartes=0, solo_dia=dia)
        if res["pendientes"]:   # un día tiene pocas pruebas: se analizan aquí las que falten
            for clave in res["pendientes"]:
                try:
                    servicio.analisis_prueba(alm, camp_id, clave)
                except Exception:  # noqa: BLE001 - una prueba sin datos no impide el resto
                    pass
            res = servicio.resumen_campeonato(alm, camp_id, descartes=0, solo_dia=dia)
        if not res["pruebas"]:
            raise ValueError("No hay pruebas ese día.")
        if barco not in res["barcos"]:
            raise ValueError("Este barco no tiene llegadas ese día.")
        hasta = servicio.resumen_campeonato(alm, camp_id, hasta_dia=dia)
        h = hechos_mod.de_dia(res, hasta, barco, dia, camp.get("nombre") or "", nombres, camp.get("clase"))
        # desglose por tramo de cada prueba del día (con el top 5 de esa prueba)
        por_numero = {p["numero"]: p for p in res["pruebas"]}
        for fila in h["pruebas"]:
            p = por_numero.get(fila["prueba"])
            try:
                an = servicio.analisis_prueba(alm, camp_id, p["clave"])
            except Exception:  # noqa: BLE001
                continue
            if an.get("recorrido_dudoso"):
                continue
            fila["tramos"] = hechos_mod.tramos_compactos(hechos_mod.de_prueba(an, barco, nombres, camp.get("clase")))
        # la escora óptima de un solo día tiene pocos datos: la del campeonato hasta ese día
        h["escora_optima_en_ceñida"] = hechos_mod._escora_camp(hasta, barco, [x["vela"] for x in hasta["general"] if x["vela"] != barco][:5])
        if h["escora_optima_en_ceñida"]:
            h["escora_optima_en_ceñida"]["nota"] = "todas las ceñidas del campeonato hasta este día juntas (un día solo tiene pocos datos)"
        return h
    an = servicio.analisis_prueba(alm, camp_id, ambito)
    if not any(c["vela"] == barco for c in an["clasificacion"]) and barco not in an["rendimiento"]:
        raise ValueError("Este barco no tiene datos en esta prueba.")
    return hechos_mod.de_prueba(an, barco, nombres, camp.get("clase"))
