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
- Usa SOLO las cifras de los DATOS. No calcules cifras nuevas (ni diferencias, ni medias, ni porcentajes): si necesitas una comparación, usa los campos que ya la traen (p. ej. «..._frente_al_top5_...», «..._top5_...»).
- La referencia es el TOP 5 (los 5 primeros de la prueba o de la general, sin contar este barco): las conclusiones salen de las diferencias con él. Nunca digas que el barco fue mejor que el top 5 si el campo «…_frente_al_top5_…» o «…_por_que» no lo dice.
- Sé realista: el tono tiene que cuadrar con el resultado. Si el barco quedó en el tercio central o en el último tercio, dilo claro y céntrate en lo que le separa del top 5; no presentes como fortaleza algo que solo es «igual que el top 5».
- «…_por_que» explica la diferencia de VMG con el top 5: si fue por velocidad (SOG) o por ángulo (TWA: más abierto o más cerrado en ceñida, más alto o más bajo en popa). Úsalo para decir qué falló, en palabras, sin repetir sus cifras.
- OCS: solo el que da el comité («ocs_segun_el_comite»). La distancia a la línea en la señal es orientativa (GPS en el palo, línea estimada): no digas que el barco estaba pasado si el comité no lo marcó.
- En las laylines sobrepasadas distingue el motivo que dan los datos: por tráfico (no podía virar, o la layline ya estaba ocupada) o por cálculo. Solo las de cálculo son un error de estimación; las de tráfico son una decisión táctica o forzada.
- Cuando hables de un tramo, nómbralo siempre con su nombre concreto y la prueba («Popa 2 de la prueba 3»). Si la cifra es una media de varios tramos («vmg_media_de_las_popas…»), dilo así («media de las dos popas»); no la atribuyas a un tramo.
- Cita las cifras tal cual o redondeadas, con coma decimal, un espacio antes de la unidad y un punto detrás de las unidades abreviadas, que ayuda a leer (4,06 kn.; 87 m.; 54 s.; 10,5°; 66 %). Los tiempos de hasta 60 s., en segundos (54 s.); los de más de 60 s., SIEMPRE en minutos y segundos: pásalos tú (339 s. → 5 min. 39 s.; 181 s. → 3 min. 1 s.); esta conversión no es una cifra nueva y es obligatoria. La unidad de cada campo va en su nombre: _kn, _m, _s, _grados (°), _pct (%).
- La corriente es ESTIMADA y tiene un nivel de confianza: si es baja, no la uses para explicar resultados. Úsala para explicar laylines o la ventaja de un lado solo si la confianza es alta o media.
- Todo lo relativo al viento, VMG, TWA, maniobras, laylines y barco fantasma es ESTIMADO por FastTack a partir del GPS de los barcos (no hay anemómetro): no lo presentes como medido ni lo atribuyas a RaceSense. Basta con decirlo una vez.
- Los huecos de telemetría y la calidad de datos son limitaciones de RaceSense, no errores de la tripulación: menciónalos solo como límite del análisis.
- Si un dato falta o la calidad de datos es baja, dilo en lugar de interpretarlo. No inventes causas que los datos no muestren; si propones una causa, preséntala como hipótesis.
- Izquierda/derecha son lados del campo, mirando a barlovento (en las puertas, mirando a sotavento, como indica el dato). No los traduzcas a babor/estribor ni a amuras.
- Si los DATOS traen «sesion_propia» con un solo barco, no hay flota ni top 5: no hables de puestos ni de la flota; compara entre pruebas y entre tramos del propio barco (evolución, regularidad, ceñida frente a popa) y recuerda que llegadas y balizas son estimadas.
- En la salida, usa «posicionamiento» para explicar cómo fue: si llegó pronto (y tuvo que frenar) o tarde (lejos de la línea), si tenía hueco a sotavento para arribar y acelerar, si un barco a sotavento en posición segura no le dejó desarrollar su navegación o si un barco de barlovento le planchó (aire sucio) y por qué, relacionándolo solo con cifras de los datos (distancia a la línea, SOG en el disparo frente a la primera fila, huecos, primera virada).
- Si hay «set_tras_barlovento» o «rodeo_final», úsalos solo cuando expliquen una ganancia o una pérdida clara del tramo (set directo o trasluchando al montar frente a lo que hizo el top 5; tiempo en la zona de la baliza y velocidad mínima frente al top 5).
- Si hay «reglaje_apuntado», es lo que la tripulación apuntó que llevaba: puedes relacionarlo con la velocidad o la escora como hipótesis, nunca como causa demostrada.
- El offset no es un tramo: menciónalo dentro de la popa («offset») solo si el tiempo de la baliza al offset es claramente peor o mejor que el del top 5.
- «donde_se_perdio_la_prueba» reparte el tiempo perdido frente al top 5 en salida, velocidad, maniobras y táctica y resto: úsalo para ordenar qué pesó más (y di que es estimado).
- «regularidad_vmg_pct»: cuanto menor, más regular. Menciónala si es claramente peor o mejor que la del top 5.
- El barco de los DATOS («barco») es el de quien lee: háblale de tú («saliste», «tu popa», «perdiste 20 m.»), sin su número de vela ni su nombre. Los demás barcos, por su vela.
- «frente_a_sus_vecinos»: ángulo, SOG y VMG frente a los barcos que tenía al lado (mismo viento). Úsalo para decir si navegaba más abierto o más cerrado (en popa, más bajo o más alto) y más rápido o más lento que los de al lado, comparándolo con el top 5. No hay ángulo óptimo medido: no lo inventes.
- Sin introducción ni despedida. Formato Markdown exactamente con estos encabezados:
"""

# Guía común de los debriefs de mejora (prueba, día y campeonato): qué entrenar, no una crónica
MEJORA = """
Eres el entrenador del equipo. El objetivo es mejorar: céntrate en lo que más tiempo costó y en lo que hay que entrenar, no en contarlo todo. Sé breve y concreto.
- Ordena por impacto con «donde_se_perdio_la_prueba» (segundos frente al top 5 por salida, velocidad, maniobras y táctica y resto) y, en el día, con «mejores_tramos» y «peores_tramos» (vienen ordenados por el motor).
- Cada punto nombra su tramo y prueba concretos y la causa que muestran los datos (salida y posicionamiento, velocidad y escora frente a la óptima, maniobras con giro, aceleración y ángulo de salida, táctica con roladas, amura favorecida, lado y laylines).
- Roles del viento (roladas): en «tactica», el viento de cada momento está sacado del rumbo de los barcos cercanos (roles locales, estimado). Di si navegaste en la amura favorecida, si viraste en el role y cuánto tardaste en virar tras entrar un role en contra (al menos 20 s. seguidos en la amura desfavorecida), siempre frente al top 5; di siempre «role en contra», nunca «rolón»; si el top 5 no lo hizo mejor, no lo presentes como la causa del resultado.
- Puestos a bordo: adapta los nombres a la tripulación de la clase (en un J/70: timonel, táctico, trimmer de mayor, trimmer de proa/spi y proa; en un Snipe: timonel y tripulante). Responsables habituales, como orientación (no como un hecho medido): táctico → salida, lado, roladas, laylines y puertas; timonel → modo y TWA, ángulo de salida y giro de las maniobras; trimmers → velocidad, escora y aceleración tras las maniobras; proa → maniobras y rodeos.
- En las maniobras, el ángulo de salida frente al top 5: en ceñida, salir más cerrado tarda en acelerar y más abierto pierde altura; en popa al revés: más bajo tarda en acelerar y más alto no baja lo suficiente.
- Vocabulario: en popa se dice «bajo» (modo bajo, navegar más bajo), nunca «profundo».- Si hay «reglaje_apuntado», relaciónalo solo como hipótesis.
- Escora óptima = la media de la escora de los 5 barcos con más VMG (estimada). Menciónala solo si el barco se aparta claramente (más de 2°) o pasa poco tiempo cerca de ella.
"""

PRUEBA = COMUN + MEJORA + """
## La prueba en dos frases
(resultado y qué lo explica)
## Lo que más costó
(lista de 2–3 puntos, del que más al que menos, cada uno con su tramo y su causa)
## Lo que funcionó
(lista de 1–2 puntos)
## Qué trabajar
(lista numerada de 3 prioridades concretas, cada una con el puesto a bordo responsable entre paréntesis)

Máximo 350 palabras.
"""

DIA = COMUN + MEJORA + """
## La jornada en dos frases
(resultado del día y qué lo explica)
## Lo que más costó
(lista de 2–4 puntos, del que más al que menos, cada uno con su tramo y prueba y su causa)
## Lo que funcionó
(lista de 2 puntos, con su tramo y prueba)
## Qué trabajar
(lista numerada de 3 prioridades concretas para el próximo día; cada una con el puesto a bordo responsable entre paréntesis)

Máximo 450 palabras.
"""

COACH = DIA   # compatibilidad: el antiguo «debrief de coach del día» es ahora el debrief del día

CRONICA = COMUN + """
Esto es la crónica de la prueba: qué pasó en el campo, para entenderla. No es un debrief del barco: cuenta la prueba (salida, cada tramo, llegada) con los barcos que la marcaron, qué lado o qué decisión pagó y por qué según los datos (roladas, presión, viento en la línea, puertas, sets), y en una línea por tramo dónde quedaste tú (el barco de los datos, siempre de tú). No des consejos ni «claves».

## La prueba en dos frases
## Salida
## Tramo a tramo
(una línea por tramo que empiece por su nombre en negrita)
## Llegada

Máximo 450 palabras.
"""

CAMPEONATO = COMUN + MEJORA + """
Si «estado.campeonato_en_curso» es verdadero, el campeonato no ha terminado: habla de lo disputado hasta ahora y orienta las prioridades a las pruebas que quedan.

Pocas cifras: la tripulación tiene que poder seguir las conclusiones de un vistazo. Como mucho UNA cifra por punto (la que más explica, normalmente la diferencia con el top 5) y ninguna en «Hipótesis para mejorar» ni en «Qué entrenar»; lo demás, en palabras («en 8 de 10 pruebas», «más abierto que el top 5», «más lento en popa»). No hables de puntos, ni de la suma de puntos, ni de qué prueba se descartó.
Para la velocidad usa «vmg_frente_al_top5_prueba_a_prueba» (en cuántas pruebas fue peor y por qué) y «medias_del_campeonato» (con su «…_por_que»): di en ceñida y en popa si falló la velocidad o el ángulo.

## El campeonato en dos frases
(dónde quedó en la general, en palabras sencillas, y la razón principal; sin puntos ni descartes)
## Lo que más costó
(lista de 2–4 puntos, del que más al que menos; en ceñida y popa di si falló el ángulo o la velocidad)
## Hipótesis para mejorar
(para cada uno de los 2–3 problemas principales, 2–3 posibilidades técnicas que podrían explicarlo, presentadas como hipótesis a comprobar en el agua: trimado de velas, reglaje del palo y la jarcia, técnica de timón (modo, ángulo, manejo de las olas), escora y peso de la tripulación, maniobras. Deben encajar con lo que muestran los datos: si falla el ángulo en ceñida, no propongas solo «más potencia»)
## Lo que funcionó
(lista de 1–2 puntos; solo lo que los datos muestran claramente mejor o igual que el top 5)
## Qué entrenar
(lista numerada de 3 a 4 ejercicios concretos, ordenados por impacto, cada uno con el puesto a bordo responsable entre paréntesis)

Máximo 500 palabras.
"""


class IANoDisponible(RuntimeError):
    pass


def instrucciones(datos: dict) -> str:
    base = {"debrief del campeonato": CAMPEONATO, "debrief del día": DIA,
            "debrief de coach del día": COACH, "crónica de la prueba": CRONICA}.get(datos.get("tipo"), PRUEBA)
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


_SEGUNDOS = re.compile(r"(?<!primeros )(?<![\d.,:])([-−+]?)(\d{2,5})\s*(?:s|seg|segundos)\b\.?")


def pulir(texto: str) -> str:
    """Tiempos de más de 60 s en minutos y segundos («339 s.» → «5 min. 39 s.»): la IA no siempre lo hace."""
    def a_min(m):
        n = int(m[2])
        if n <= 60:
            return m[0]
        mi, s = divmod(n, 60)
        return f"{m[1]}{mi} min." + (f" {s} s." if s else "")
    return _SEGUNDOS.sub(a_min, texto)


def guardar(alm: Almacen, camp_id: str, ambito: str, barco: str, datos: dict, texto: str, origen: str) -> dict:
    texto = pulir(texto)
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


def _valorar_tramos(h: dict):
    """Debrief de coach: los 2 mejores y los 2 peores tramos del día. Criterio: VMG frente al top 5 de
    la prueba; sin flota, frente a la media del propio barco en ese tipo de tramo ese día."""
    h["tipo"] = "debrief del día"
    tramos = [(f["prueba"], t) for f in h["pruebas"] for t in f.get("tramos", [])
              if t.get("vmg_kn") is not None and t.get("calidad_de_datos") in ("alta", "media", "baja")]
    for tipo in ("ceñida", "popa"):
        vs = [t["vmg_kn"] for _, t in tramos if t.get("tipo") == tipo]
        if vs:
            media = sum(vs) / len(vs)
            for _, t in tramos:
                if t.get("tipo") == tipo:
                    t["vmg_frente_a_tu_media_del_dia_kn"] = round(t["vmg_kn"] - media, 2)
    con_top5 = [x for x in tramos if x[1].get("vmg_frente_al_top5_kn") is not None]
    if len(con_top5) >= 3:
        clave, criterio = "vmg_frente_al_top5_kn", "VMG frente al top 5 de la prueba"
        lista = con_top5
    else:
        clave, criterio = "vmg_frente_a_tu_media_del_dia_kn", "VMG frente a la media del barco en ese tipo de tramo ese día"
        lista = tramos
    orden = sorted(lista, key=lambda x: x[1][clave], reverse=True)
    fila = lambda x: {"prueba": x[0], "tramo": x[1]["nombre"], clave: x[1][clave]}
    n = min(2, len(orden) // 2)
    h["mejores_tramos"] = [fila(x) for x in orden[:n]]
    h["peores_tramos"] = [fila(x) for x in orden[::-1][:n]]
    h["criterio_mejores_y_peores"] = criterio


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
    coach = ambito.startswith(("coach:", "dia:"))   # un solo debrief del día, con el detalle por tramo
    if ambito.startswith("coach:"):
        ambito = "dia:" + ambito[6:]
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
            dp = hechos_mod.de_prueba(an, barco, nombres, camp.get("clase"))
            fila["tramos"] = hechos_mod.tramos_compactos(dp, coach=coach)
            if dp.get("donde_se_perdio_la_prueba"):
                fila["donde_se_perdio_la_prueba"] = {k: x for k, x in dp["donde_se_perdio_la_prueba"].items() if k != "por_tramo"}
            if coach and dp.get("salida"):
                fila["salida"] = dp["salida"]
        # la escora óptima de un solo día tiene pocos datos: la del campeonato hasta ese día
        h["escora_optima_en_ceñida"] = hechos_mod._escora_camp(hasta, barco, [x["vela"] for x in hasta["general"] if x["vela"] != barco][:5])
        if h["escora_optima_en_ceñida"]:
            h["escora_optima_en_ceñida"]["nota"] = ("estimada: media de la escora de los 5 barcos con más VMG de cada ceñida, "
                                                    "en todas las ceñidas del campeonato hasta este día (un día solo tiene pocos datos)")
        if coach:
            _valorar_tramos(h)
        return h
    if ambito.startswith("cronica:"):
        an = servicio.analisis_prueba(alm, camp_id, ambito[8:])
        return hechos_mod.de_cronica(an, barco, nombres, camp.get("clase"))
    an = servicio.analisis_prueba(alm, camp_id, ambito)
    if not any(c["vela"] == barco for c in an["clasificacion"]) and barco not in an["rendimiento"]:
        raise ValueError("Este barco no tiene datos en esta prueba.")
    h = hechos_mod.de_prueba(an, barco, nombres, camp.get("clase"))
    try:   # viento y corriente del modelo meteorológico, si cuadra con la flota
        m = servicio.meteo_prueba(alm, camp_id, ambito, solo_cache=True)
        mm = {}
        if (m.get("viento") or {}).get("coincide"):
            mm["viento_modelo_kn"] = m["viento"]["kn"]
            mm["viento_modelo_rachas_kn"] = m["viento"].get("rachas_kn")
            mm["viento_modelo_desde_grados"] = m["viento"]["desde_grados"]
        if m.get("corriente"):
            mm["corriente_modelo_kn"] = m["corriente"]["kn"]
            mm["corriente_modelo_hacia_grados"] = m["corriente"]["hacia_grados"]
        if mm:
            h["meteo_modelo"] = mm | {"nota": "modelo meteorológico (Open-Meteo), viento a 10 m promediado a las horas de la prueba: referencia, no medido en el campo"}
    except Exception:  # noqa: BLE001 - sin red o sin datos: el debrief sigue sin ellos
        pass
    reg = next((p.get("reglaje") for p in camp["pruebas"] if p["clave"] == ambito), None)
    if reg:
        h["reglaje_apuntado"] = reg
    return h
