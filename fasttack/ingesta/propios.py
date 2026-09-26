"""Archivos .vkx propios dentro de un campeonato de RaceSense.

RaceSense pierde muchas muestras (huecos de segundos a minutos). El registro interno del Atlas de un
barco no tiene huecos: si se añade, sustituye la telemetría de RaceSense de ese barco en el tiempo que
cubre el archivo; el resto de la flota sigue viniendo de RaceSense. Los archivos se guardan en la
carpeta del campeonato (propios.json + tel_propio_N.parquet + propio_N.vkx) y no salen del ordenador.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from . import normalizar as nz
from . import vkx
from .racesense import COLUMNAS

SN_BASE = 60_000     # sn de las filas de los archivos propios (no chocan con los de RaceSense)


def _ruta(alm, camp: dict):
    return alm._dir(camp["event_id"], camp["division"])


def lista(alm, camp: dict) -> list[dict]:
    p = _ruta(alm, camp) / "propios.json"
    return json.loads(p.read_text()) if p.exists() else []


def _guardar_lista(alm, camp: dict, items: list[dict]):
    (_ruta(alm, camp) / "propios.json").write_text(json.dumps(items, ensure_ascii=False))


def _limpiar_cache(alm, camp: dict):
    d = _ruta(alm, camp)
    for f in [*d.glob("analisis_*.json"), *d.glob("pistas_*.json")]:
        f.unlink()


def añadir(alm, camp: dict, datos: bytes, vela: str, archivo: str = "") -> list[dict]:
    clave = nz.vela(vela)
    barcos = {b["clave"]: b for b in camp.get("barcos", [])}
    if clave not in barcos:
        raise ValueError(f"La vela «{vela}» no está en la flota de este campeonato.")
    reg = vkx.leer(datos)
    huella = hashlib.sha1(datos).hexdigest()[:12]
    items = lista(alm, camp)
    if any(x["huella"] == huella for x in items):
        raise ValueError("Este archivo ya está añadido.")
    n = max((x["n"] for x in items), default=0) + 1
    cols = vkx.a_columnas(reg, barcos[clave]["vela"], sn=SN_BASE + n, division=camp["division"])
    desde, hasta = int(cols["ts"][0]), int(cols["ts"][-1])
    senales = [p["senal"] for p in camp.get("pruebas", [])]
    if senales and not any(desde - 3 * 3600_000 <= s <= hasta for s in senales):
        raise ValueError("El archivo no coincide con ninguna prueba del campeonato (fechas distintas).")
    d = _ruta(alm, camp)
    (d / f"propio_{n}.vkx").write_bytes(datos)
    pq.write_table(pa.table({c: cols[c] for c in COLUMNAS}), d / f"tel_propio_{n}.parquet", compression="zstd")
    items.append({"n": n, "huella": huella, "vela": barcos[clave]["vela"], "clave": clave, "archivo": archivo,
                  "desde": desde, "hasta": hasta, "muestras": len(cols["ts"]),
                  "pruebas": sum(1 for s in senales if desde <= s <= hasta)})
    _guardar_lista(alm, camp, items)
    _limpiar_cache(alm, camp)
    return items


def quitar(alm, camp: dict, n: int) -> list[dict]:
    items = [x for x in lista(alm, camp) if x["n"] != n]
    d = _ruta(alm, camp)
    for f in (f"propio_{n}.vkx", f"tel_propio_{n}.parquet"):
        (d / f).unlink(missing_ok=True)
    _guardar_lista(alm, camp, items)
    _limpiar_cache(alm, camp)
    return items


def mezclar(d, cols: dict, desde: int, hasta: int) -> dict:
    """Sustituye en `cols` (telemetría de RaceSense) las filas de cada barco con archivo propio, en
    el tiempo que cubre su archivo, por las del archivo."""
    p = d / "propios.json"
    if not p.exists():
        return cols
    items = [x for x in json.loads(p.read_text()) if x["hasta"] >= desde and x["desde"] <= hasta]
    if not items:
        return cols
    claves = np.array([nz.vela(v) for v in cols["sail_number"]], dtype=object) if len(cols["ts"]) else np.array([], dtype=object)
    quitar_ = np.zeros(len(cols["ts"]), bool)
    partes = []
    for x in items:
        quitar_ |= (claves == x["clave"]) & (cols["role"] != "mark") & (cols["ts"] >= x["desde"]) & (cols["ts"] <= x["hasta"])
        f = d / f"tel_propio_{x['n']}.parquet"
        if f.exists():
            t = pq.read_table(f, filters=[("ts", ">=", desde), ("ts", "<=", hasta)])
            partes.append({c: t.column(c).to_numpy(zero_copy_only=False) for c in COLUMNAS})
    out = {c: np.concatenate([cols[c][~quitar_]] + [q[c] for q in partes]) for c in COLUMNAS}
    orden = np.argsort(out["ts"], kind="stable")
    return {c: v[orden] for c, v in out.items()}
