"""Une ingesta y motor: el análisis de una prueba, calculado una vez y guardado."""
from __future__ import annotations

import json

from .ingesta import campeonato as camp_mod
from .ingesta.almacen import Almacen
from .motor import analisis

MARGEN_ANTES_MS = 6 * 60_000    # telemetría desde 6 min antes de la señal
MARGEN_DESPUES_MS = 3 * 60_000  # hasta 3 min tras la última llegada


class PruebaNoAnalizable(ValueError):
    pass


def analisis_prueba(alm: Almacen, camp_id: str, clave: str, recalcular: bool = False) -> dict:
    camp = camp_mod.leer(alm, camp_id)
    if camp is None:
        raise KeyError(camp_id)
    prueba = next((p for p in camp["pruebas"] if p["clave"] == clave), None)
    if prueba is None:
        raise KeyError(clave)
    if not prueba["llegadas"]:
        raise PruebaNoAnalizable("Esta prueba no tiene llegadas: no se puede analizar.")
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
