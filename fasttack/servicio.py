"""Une ingesta y motor: el análisis de una prueba, calculado una vez y guardado."""
from __future__ import annotations

import json

import numpy as np

from .ingesta import campeonato as camp_mod
from .ingesta.almacen import Almacen
from .motor import analisis
from .motor.pistas import Proyeccion, pistas
from .motor.trazas import construir

MARGEN_ANTES_MS = 6 * 60_000    # telemetría desde 6 min antes de la señal
MARGEN_DESPUES_MS = 3 * 60_000  # hasta 3 min tras la última llegada


class PruebaNoAnalizable(ValueError):
    pass


def analisis_prueba(alm: Almacen, camp_id: str, clave: str, recalcular: bool = False) -> dict:
    camp, prueba = _cargar(alm, camp_id, clave)
    # La caché depende de la versión del motor y del viento de referencia.
    nombre = f"analisis_{clave}_v{analisis.VERSION}_{prueba.get('viento_kn') or 'sin'}.json"
    ruta = alm._dir(camp["event_id"], camp["division"]) / nombre
    if ruta.exists() and not recalcular:
        return json.loads(ruta.read_text())
    desde = prueba["senal"] - MARGEN_ANTES_MS
    hasta = max(prueba["llegadas"].values()) + MARGEN_DESPUES_MS
    cols = alm.telemetria(camp["event_id"], camp["division"], desde, hasta)
    if not len(cols["ts"]):
        raise PruebaNoAnalizable("RaceSense no tiene telemetría de esta prueba.")
    res = analisis.analizar(prueba, cols, {k: int(v) for k, v in camp["roles_recorrido"].items()})
    res["prueba"] = {"clave": clave, "numero": prueba["numero"], "estado": prueba["estado"],
                     "viento_kn": prueba.get("viento_kn"), "nota": prueba.get("nota")}
    ruta.write_text(json.dumps(res, ensure_ascii=False, default=float))
    return res


PASO_TRAZA_MS = 2_000   # para el mapa: como mucho una muestra cada 2 s (muestras reales, sin rellenar)
PASO_BALIZA_MS = 10_000


def _cargar(alm: Almacen, camp_id: str, clave: str):
    camp = camp_mod.leer(alm, camp_id)
    if camp is None:
        raise KeyError(camp_id)
    prueba = next((p for p in camp["pruebas"] if p["clave"] == clave), None)
    if prueba is None:
        raise KeyError(clave)
    if not prueba["llegadas"]:
        raise PruebaNoAnalizable("Esta prueba no tiene llegadas: no se puede analizar.")
    return camp, prueba


def _adelgazar(ts: np.ndarray, paso_ms: int) -> np.ndarray:
    """Índices con al menos `paso_ms` entre muestras (se conservan los bordes de los huecos)."""
    if not len(ts):
        return np.array([], dtype=int)
    idx, ultimo = [0], ts[0]
    for i in range(1, len(ts)):
        if ts[i] - ultimo >= paso_ms or (i + 1 < len(ts) and ts[i + 1] - ts[i] > 5_000):
            idx.append(i)
            ultimo = ts[i]
    return np.array(idx)


def pistas_prueba(alm: Almacen, camp_id: str, clave: str) -> dict:
    """Trazas para el mapa y el reproductor, en las mismas coordenadas locales que el análisis.
    Formato compacto por barco: listas paralelas t (décimas de s desde la señal), x, y (dm),
    sog (décimas de kn), cog, hdg, roll (grados enteros; cog ausente = -1)."""
    camp, prueba = _cargar(alm, camp_id, clave)
    ruta = alm._dir(camp["event_id"], camp["division"]) / f"pistas_{clave}_v{analisis.VERSION}.json"
    if ruta.exists():
        return json.loads(ruta.read_text())
    an = analisis_prueba(alm, camp_id, clave)
    senal = prueba["senal"]
    cols = alm.telemetria(camp["event_id"], camp["division"], senal - MARGEN_ANTES_MS,
                          max(prueba["llegadas"].values()) + MARGEN_DESPUES_MS)
    proy = Proyeccion(an["proyeccion"]["lat0"], an["proyeccion"]["lon0"])
    trazas = construir(cols, proy)
    barcos = {}
    for v, tr in trazas.items():
        i = _adelgazar(tr.ts, PASO_TRAZA_MS)
        if len(i) < 2:
            continue
        barcos[v] = {
            "t": ((tr.ts[i] - senal) // 100).astype(int).tolist(),
            "x": np.round(tr.x[i] * 10).astype(int).tolist(),
            "y": np.round(tr.y[i] * 10).astype(int).tolist(),
            "sog": np.round(tr.sog[i] * 10).astype(int).tolist(),
            "cog": np.where(np.isnan(tr.cog[i]), -1, np.round(tr.cog[i])).astype(int).tolist(),
            "hdg": np.round(tr.hdg[i]).astype(int).tolist(),
            "roll": np.round(tr.roll[i]).astype(int).tolist(),
        }
    _, balizas = pistas(cols, proy)
    usadas = {sn for c in an["controles"] for sn in c["sn"] if sn is not None}
    marcas = {}
    for sn, p in balizas.items():
        if sn not in usadas:
            continue
        i = _adelgazar(p.ts, PASO_BALIZA_MS)
        marcas[str(sn)] = {"t": ((p.ts[i] - senal) // 100).astype(int).tolist(),
                           "x": np.round(p.x[i] * 10).astype(int).tolist(),
                           "y": np.round(p.y[i] * 10).astype(int).tolist()}
    res = {"senal": senal, "proyeccion": an["proyeccion"], "barcos": barcos, "balizas": marcas}
    ruta.write_text(json.dumps(res, separators=(",", ":")))
    return res
