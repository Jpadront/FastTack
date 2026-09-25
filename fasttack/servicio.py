"""Une ingesta y motor: el análisis de una prueba, calculado una vez y guardado."""
from __future__ import annotations

import json

import numpy as np

from .ingesta import campeonato as camp_mod
from .ingesta.almacen import Almacen
from .motor import analisis, resumen
from .motor.pistas import Proyeccion, pistas
from .motor.trazas import construir

MARGEN_ANTES_MS = 6 * 60_000    # telemetría desde 6 min antes de la señal
MARGEN_DESPUES_MS = 3 * 60_000  # hasta 3 min tras la última llegada


class PruebaNoAnalizable(ValueError):
    pass


def analisis_prueba(alm: Almacen, camp_id: str, clave: str, recalcular: bool = False) -> dict:
    camp, prueba = _cargar(alm, camp_id, clave)
    ruta = _ruta_analisis(alm, camp, prueba)
    if ruta.exists() and not recalcular:
        return json.loads(ruta.read_text())
    desde = prueba["senal"] - MARGEN_ANTES_MS
    hasta = max(prueba["llegadas"].values()) + MARGEN_DESPUES_MS
    cols = alm.telemetria(camp["event_id"], camp["division"], desde, hasta)
    if not len(cols["ts"]):
        raise PruebaNoAnalizable("RaceSense no tiene telemetría de esta prueba.")
    res = analisis.analizar(prueba, cols, {k: int(v) for k, v in camp["roles_recorrido"].items()}, camp.get("clase"))
    res["prueba"] = {"clave": clave, "numero": prueba["numero"], "estado": prueba["estado"],
                     "viento_kn": prueba.get("viento_kn"), "nota": prueba.get("nota")}
    ruta.write_text(json.dumps(res, ensure_ascii=False, default=float))
    return res


def _ruta_analisis(alm: Almacen, camp: dict, prueba: dict):
    # La caché depende de la versión del motor y del viento de referencia.
    nombre = f"analisis_{prueba['clave']}_v{analisis.VERSION}_{prueba.get('viento_kn') or 'sin'}.json"
    return alm._dir(camp["event_id"], camp["division"]) / nombre


def resumen_campeonato(alm: Almacen, camp_id: str, descartes: int | None = None) -> dict:
    """General calculada y agregados de las pruebas que cuentan. Solo usa los análisis ya guardados;
    las pruebas sin analizar salen en 'pendientes' (la web las pide una a una y vuelve a llamar)."""
    camp = camp_mod.leer(alm, camp_id)
    if camp is None:
        raise KeyError(camp_id)
    pruebas = sorted((p for p in camp["pruebas"] if p["numero"] is not None and p["llegadas"]), key=lambda p: p["numero"])
    hechos = {}
    for p in pruebas:
        ruta = _ruta_analisis(alm, camp, p)
        if ruta.exists():
            hechos[p["clave"]] = json.loads(ruta.read_text())
    # Inscritos: barcos con alguna llegada (RaceSense lista también dispositivos de prueba que no regatean)
    inscritos = [b["clave"] for b in camp["barcos"] if any(b["clave"] in p["llegadas"] for p in pruebas)]
    res = resumen.resumen(pruebas, inscritos, hechos, descartes)
    res["version"] = analisis.VERSION
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
    brj = an.get("brujulas") or {}
    desvios, decl = brj.get("desvios_grados", {}), brj.get("declinacion_grados", 0.0)
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
            # rumbo verdadero: HDG del dispositivo + desvío de su brújula (magnético/verdadero y montaje);
            # sin desvío estimado, solo la declinación (la mayoría de Atlas van en magnético)
            "hdg": np.round((tr.hdg[i] + desvios.get(v, decl)) % 360).astype(int).tolist(),
            "roll": np.round(tr.roll[i]).astype(int).tolist(),
            "pitch": np.round(tr.pitch[i]).astype(int).tolist(),
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
