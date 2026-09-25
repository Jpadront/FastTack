"""Cargar un campeonato: documento del comité + telemetría → lista de pruebas y flota.

La lista de pruebas NO es la de /api/regatta tal cual (ver docs/fuente_datos.md):
- Hay pruebas del comité sin llegadas (entrenamiento, anuladas o llegadas perdidas).
- Hay pruebas navegadas que no están en el documento (Mundial J/70: 2.ª prueba del 9 y del 11).
Se detectan en la telemetría (ráfaga de cruces de la línea de salida y ola de llegadas) y se
añaden como «reconstruidas». La numeración es cronológica y editable.
"""
from __future__ import annotations

import json
import statistics
import time
from dataclasses import asdict, dataclass, field

from ..motor.deteccion import detectar_llegadas, detectar_senal
from ..motor.pistas import Pista, Proyeccion, pistas
from . import normalizar as nz
from .almacen import Almacen
from .url import RefCampeonato, leer_url

VENTANA_BUSQUEDA_MS = 4 * 3600_000     # tras el inicio de una ventana de racing-summary
DURACION_MAX_MS = 3 * 3600_000          # de una prueba, para buscar llegadas
FRACCION_FLOTA_SALIDA = 0.4             # barcos distintos cruzando en 60 s para aceptar una salida
FRACCION_DURACION_MIN = 0.6             # 1.ª llegada frente a la mediana de las oficiales
FRACCION_FLOTA_LLEGADA = 0.5            # llegadas detectadas mínimas (el entrenamiento del Mundial
                                        # daba 40 de ~100 barcos volviendo a puerto)


class DivisionAmbigua(ValueError):
    def __init__(self, opciones: list[str]):
        super().__init__("El campeonato tiene varias divisiones: elige una.")
        self.opciones = opciones


@dataclass
class Prueba:
    clave: str                 # hora de la señal (ms) como texto
    senal: int                 # ms UTC
    origen: str                # «comité» o «telemetría»
    raceNumber: int | None     # el del documento del comité, si lo hay
    estado: str                # «oficial», «reconstruida» o «sin llegadas»
    llegadas: dict[str, int] = field(default_factory=dict)   # vela normalizada → ms
    ocs: list[str] = field(default_factory=list)
    ocs_fiable: bool = True
    linea_salida: dict | None = None
    numero: int | None = None
    excluida: bool = False
    viento_kn: float | None = None
    viento_dir: float | None = None
    nota: str = ""

    @property
    def n_llegadas(self) -> int:
        return len(self.llegadas)


def elegir_division(doc: dict, etiqueta: str | None) -> dict:
    divs = doc.get("divisions") or []
    if not divs:
        raise ValueError("El campeonato no tiene divisiones en RaceSense.")
    if etiqueta:
        for d in divs:
            nombres = {d.get("name"), d.get("boatClass"), f"{d.get('boatClass')} {d.get('name')}"}
            if etiqueta in nombres:
                return d
    if len(divs) == 1:
        return divs[0]
    raise DivisionAmbigua([d["name"] for d in divs])


def roles_recorrido(division: dict) -> dict[str, int]:
    """Rol → sn de telemetría (startLeft = pin, startRight = comité, finishLeft/Right…)."""
    roles = {}
    for c in division.get("courses") or []:
        for ach in c.get("achievements", []):
            for dr in ach.get("deviceRoles", []):
                roles.setdefault(dr["role"], nz.sn_de_hex(dr["sn"]))
    return roles


# Sube cuando cambia cómo se obtienen las pruebas o las llegadas: la web propone volver a cargar
# los campeonatos guardados con una versión anterior (la telemetría ya descargada se reutiliza).
VERSION_INGESTA = 3


def cargar(alm: Almacen, url: str | RefCampeonato, division_elegida: str | None = None,
           progreso=lambda texto: None) -> dict:
    ref = leer_url(url) if isinstance(url, str) else url
    ev = ref.event_id
    progreso("Descargando el documento del campeonato")
    reg = alm.json(ev, "regatta", lambda: alm.cliente.regatta(ev), refrescar=True)
    doc = reg["revisions"][-1]["doc"]
    div = elegir_division(doc, division_elegida or ref.division)
    nombre_div = div["name"]
    tz = next((r.get("timezoneOffset") for r in div.get("races", []) if r.get("timezoneOffset")), 0) or 0

    progreso("Descargando el resumen de la telemetría")
    resumen = alm.json(ev, "racing_summary", lambda: alm.cliente.racing_summary(ev), refrescar=True)
    ventanas = [r for d in resumen.get("divisions") or [] if nz.misma_division(d.get("division"), nombre_div)
                for r in d.get("races") or []]
    roles = roles_recorrido(div)

    # 1) Pruebas del documento del comité
    pruebas: list[Prueba] = []
    for r in div.get("races") or []:
        if not r.get("starts"):
            continue
        st = r["starts"][-1]  # varias salidas = llamadas generales; vale la última
        llegadas = {nz.vela(f["sailNumber"]): nz.ms(f["finishingTime"], tz) for f in r.get("finishes") or []}
        ocs = ({nz.vela(v) for v in st.get("ocsParticipants") or []}
               - {nz.vela(v) for v in st.get("exoneratedParticipants") or []}
               - {nz.vela(v) for v in st.get("clearedOcs") or []})
        s = nz.senal(st)
        pruebas.append(Prueba(clave=str(s), senal=s, origen="comité", raceNumber=r.get("raceNumber"),
                              estado="oficial" if llegadas else "sin llegadas",
                              llegadas={v: t for v, t in llegadas.items() if v not in ocs},
                              ocs=sorted(ocs), linea_salida=st.get("startLine")))
    senales = sorted(p.senal for p in pruebas)
    oficiales = [p for p in pruebas if p.estado == "oficial"]
    flota = statistics.median([len(p.llegadas) + len(p.ocs) for p in oficiales]) if oficiales else 20
    dur_ganador = statistics.median([min(p.llegadas.values()) - p.senal for p in oficiales]) if oficiales else None

    def siguiente_senal(t: int) -> int:
        return next((s for s in senales if s > t + 60_000), t + VENTANA_BUSQUEDA_MS)

    # 2) Ventanas de la telemetría sin ninguna señal del comité: posibles pruebas que faltan
    candidatas = []
    for w in ventanas:
        a = w["begin"]
        b = min(w["end"], a + VENTANA_BUSQUEDA_MS)
        if not any(a - 15 * 60_000 <= s <= b for s in senales):
            candidatas.append((a, min(b, siguiente_senal(a) - 10 * 60_000)))

    # 3) Primero las salidas que faltan (así cada búsqueda de llegadas termina en la señal siguiente)
    for j, (a, b) in enumerate(candidatas, 1):
        progreso(f"Buscando pruebas que faltan en RaceSense ({j}/{len(candidatas)})")
        p = _buscar_salida(alm, ev, nombre_div, roles, div, a, b, int(flota * FRACCION_FLOTA_SALIDA))
        if p:
            pruebas.append(p)
            senales = sorted(senales + [p.senal])

    # 4) Llegadas de las pruebas que no las tienen
    necesitan = [p for p in pruebas if p.estado == "sin llegadas"]
    for i, p in enumerate(necesitan, 1):
        progreso(f"Buscando llegadas en la telemetría ({i}/{len(necesitan)})")
        fin = min(p.senal + DURACION_MAX_MS, siguiente_senal(p.senal) - 10 * 60_000)
        _reconstruir_llegadas(alm, ev, nombre_div, roles, p, p.senal - 10 * 60_000, fin,
                              dur_ganador, int(flota * FRACCION_FLOTA_LLEGADA))
        if p.estado == "reconstruida" and p.origen == "comité":
            p.ocs_fiable = False
            p.nota = "Llegadas reconstruidas desde la telemetría; los OCS del comité son dudosos."

    pruebas.sort(key=lambda p: p.senal)

    participantes = {nz.vela(p["sailNumber"]): p for p in div.get("participants") or []}
    en_salida = {nz.vela(v) for r in div.get("races") or [] for st in r.get("starts") or []
                 for v in st.get("checkedInParticipants") or []}
    barcos = sorted(({"vela": participantes.get(v, {}).get("sailNumber", v), "clave": v,
                      "nombre": participantes.get(v, {}).get("boatName") or ""}
                     for v in (en_salida or participantes)), key=lambda b: b["clave"])
    camp = {
        "id": f"{ev}~{nombre_div}", "event_id": ev, "division": nombre_div,
        "clase": div.get("boatClass"), "nombre": doc.get("name"),
        "inicio": nz.ms(doc.get("startDate")), "fin": nz.ms(doc.get("endDate")),
        "revision": len(reg["revisions"]), "tz_offset_ms": tz // 1000,
        "roles_recorrido": roles, "barcos": barcos,
        "pruebas": [asdict(p) | {"n_llegadas": p.n_llegadas} for p in pruebas],
        "cargado_en": int(time.time() * 1000), "version_ingesta": VERSION_INGESTA,
    }
    (alm._dir(ev, nombre_div) / "campeonato.json").write_text(json.dumps(camp, ensure_ascii=False))
    return con_ajustes(alm, camp)


def leer(alm: Almacen, camp_id: str) -> dict | None:
    ev, _, division = camp_id.partition("~")
    p = alm.raiz / "racesense" / ev / division.replace("/", "_") / "campeonato.json"
    if not p.exists():
        return None
    camp = json.loads(p.read_text())
    camp["desactualizado"] = camp.get("version_ingesta", 1) < VERSION_INGESTA
    return con_ajustes(alm, camp)


def con_ajustes(alm: Almacen, camp: dict) -> dict:
    """Aplica lo que el usuario ha corregido (numeración, exclusión, viento de referencia).
    Numeración automática: cronológica, solo pruebas con llegadas y no excluidas."""
    ajustes = {r["clave"]: r for r in alm.sql("select * from ajuste_prueba where campeonato=?", (camp["id"],))}
    n = 0
    for p in camp["pruebas"]:
        a = ajustes.get(p["clave"])
        p["viento_kn"] = a["viento_kn"] if a else None
        p["viento_dir"] = a["viento_dir"] if a else None
        p["excluida"] = bool(a["excluida"]) if a and a["excluida"] is not None else not p["llegadas"]
        p["numero"] = None
        if not p["excluida"]:
            n += 1
            p["numero"] = a["numero"] if a and a["numero"] is not None else n
    return camp


def _telemetria_pistas(alm, ev, division, desde, hasta):
    cols = alm.telemetria(ev, division, desde, hasta)
    if not len(cols["ts"]):
        return None, None, None
    comp = cols["role"] != "mark"
    proy = Proyeccion(float(cols["latitude"][comp].mean() if comp.any() else cols["latitude"].mean()),
                      float(cols["longitude"][comp].mean() if comp.any() else cols["longitude"].mean()))
    barcos, balizas = pistas(cols, proy)
    return proy, barcos, balizas


def _linea(balizas, roles, izq, der, proy, linea_doc=None):
    a, b = balizas.get(roles.get(izq)), balizas.get(roles.get(der))
    if a and b:
        return a, b
    if linea_doc:  # extremos del documento: [lat, lon]
        (la1, lo1), (la2, lo2) = linea_doc["leftEnd"], linea_doc["rightEnd"]
        x1, y1 = proy.xy(la1, lo1)
        x2, y2 = proy.xy(la2, lo2)
        return Pista.constante(float(x1), float(y1)), Pista.constante(float(x2), float(y2))
    return None


FRACCION_OCS_ENTRENAMIENTO = 0.25      # con tantos OCS no es una prueba real (habría llamada general)


def _reconstruir_llegadas(alm, ev, division, roles, p: Prueba, desde, hasta, dur_ganador, minimo):
    # Muchos OCS del comité = entrenamiento o prueba anulada (el entrenamiento del Mundial tuvo 36)
    if len(p.ocs) > FRACCION_OCS_ENTRENAMIENTO * (minimo / FRACCION_FLOTA_LLEGADA):
        p.nota = (f"{len(p.ocs)} OCS del comité: parece un entrenamiento o una prueba anulada. "
                  "No cuenta (márcala en «Cuenta» si fue válida).")
        return
    proy, barcos, balizas = _telemetria_pistas(alm, ev, division, desde, hasta)
    if not barcos:
        return
    linea = _linea(balizas, roles, "finishLeft", "finishRight", proy)
    if not linea:
        p.nota = "Sin balizas de llegada en la telemetría: no se pueden reconstruir las llegadas."
        return
    det = detectar_llegadas(barcos, *linea, p.senal + 20 * 60_000, hasta)
    primera = min(det.tiempos.values()) if det.tiempos else None
    if (primera and det.parece_llegada(minimo)
            and (dur_ganador is None or primera - p.senal >= FRACCION_DURACION_MIN * dur_ganador)):
        p.llegadas = {v: t for v, t in det.tiempos.items() if v not in set(p.ocs)}
        p.estado = "reconstruida"
    else:
        p.nota = "No se detecta una llegada de la flota: prueba de entrenamiento, anulada o sin datos."


def _buscar_salida(alm, ev, division, roles, div, a, b, minimo) -> Prueba | None:
    proy, barcos, balizas = _telemetria_pistas(alm, ev, division, a, b)
    if not barcos:
        return None
    linea_doc = next((r["starts"][-1].get("startLine") for r in reversed(div.get("races") or [])
                      if r.get("starts")), None)
    linea = _linea(balizas, roles, "startLeft", "startRight", proy, linea_doc)
    if not linea:
        return None
    det = detectar_senal(barcos, *linea, a, b, max(minimo, 5))
    if not det:
        return None
    s, _n = det
    return Prueba(clave=str(s), senal=s, origen="telemetría", raceNumber=None, estado="sin llegadas",
                  ocs_fiable=False, nota="Prueba que no está en el documento del comité: reconstruida.")
