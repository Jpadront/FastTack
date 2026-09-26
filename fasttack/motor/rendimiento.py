"""Rendimiento del barco en un tramo, más allá de las medias (estimado; ver docs/metricas.md).

- Polar del tramo: SOG mediana por franja de ángulo al viento (TWA), navegando estable.
- Regularidad: dispersión de la VMG de cada tramo de 30 s respecto a la de la flota en esos
  mismos 30 s (así las rachas y los roles, que tiene toda la flota, no cuentan).
- Set tras la baliza de barlovento: si traslucha nada más rodear o sigue en la misma banda.
- Rodeo: tiempo dentro de la zona (3 esloras) de la baliza y velocidad mínima.
"""
from __future__ import annotations

import numpy as np

from .geo import dif
from .tramos import lado, vmg
from .trazas import Traza

MARGEN_RODEO_MS = 20_000
MARGEN_MANIOBRA_MS = 15_000
FRANJA_CEÑIDA, FRANJA_POPA = 2, 5
FRANJA_MIN_S = 15
VENTANA_MS = 30_000
MIN_VENTANAS = 5
SET_VENTANA_MS = 45_000        # trasluchada dentro de los 45 s tras el rodeo = set trasluchando


def _estables(tr: Traza, e: int, s: int, vt, maniobras_t: list[int]):
    i = tr.tramo(e + MARGEN_RODEO_MS, s - MARGEN_RODEO_MS)
    if len(i) < 10:
        return None
    ok = ~np.isnan(tr.cog[i]) & (tr.sog[i] > vt.sog_min)
    for t in maniobras_t:
        ok &= np.abs(tr.ts[i] - t) > MARGEN_MANIOBRA_MS
    i = i[ok]
    return i if len(i) >= 10 else None


def polar(tr: Traza, e: int, s: int, vt, maniobras_t: list[int]) -> list[dict] | None:
    """[{twa, sog, vmg, s}] por franja de TWA (2° en ceñida, 5° en popa) con ≥ 15 s de datos."""
    i = _estables(tr, e, s, vt, maniobras_t)
    if i is None:
        return None
    twd = vt.twd_en(tr.ts[i])
    twa = np.abs(dif(tr.cog[i] - twd))
    v = vmg(tr, i, twd, vt.ceñida)
    w = np.minimum(np.diff(tr.ts[i], append=tr.ts[i][-1]), 5_000) / 1000
    paso = FRANJA_CEÑIDA if vt.ceñida else FRANJA_POPA
    franja = np.floor(twa / paso)
    out = []
    for f in np.unique(franja):
        m = franja == f
        if w[m].sum() < FRANJA_MIN_S:
            continue
        out.append({"twa": round(float((f + 0.5) * paso), 1), "sog": round(float(np.median(tr.sog[i][m])), 2),
                    "vmg": round(float(np.median(v[m])), 2), "s": round(float(w[m].sum()))})
    return out or None


def vmg_por_ventanas(tr: Traza, e: int, s: int, vt, maniobras_t: list[int], t0: int) -> dict[int, float]:
    """VMG media de cada ventana de 30 s (alineadas desde t0) con ≥ 70 % de datos estables."""
    i = _estables(tr, e, s, vt, maniobras_t)
    if i is None:
        return {}
    v = vmg(tr, i, vt.twd_en(tr.ts[i]), vt.ceñida)
    k = (tr.ts[i] - t0) // VENTANA_MS
    out = {}
    for kk in np.unique(k):
        m = k == kk
        span = (tr.ts[i][m][-1] - tr.ts[i][m][0]) if m.sum() > 1 else 0
        if span >= 0.6 * VENTANA_MS:
            out[int(kk)] = float(np.mean(v[m]))
    return out


def regularidad(ventanas: dict[str, dict[int, float]]) -> dict[str, float]:
    """Desviación típica (%) de la VMG de cada ventana respecto a la mediana de la flota en esa
    ventana. Sin flota (menos de 3 barcos por ventana), respecto a la mediana del propio barco."""
    por_k: dict[int, list[float]] = {}
    for vs in ventanas.values():
        for k, x in vs.items():
            por_k.setdefault(k, []).append(x)
    ref = {k: float(np.median(x)) for k, x in por_k.items() if len(x) >= 3}
    out = {}
    for v, vs in ventanas.items():
        if ref:
            rel = [x / ref[k] for k, x in vs.items() if k in ref and ref[k] > 0.3]
        else:
            med = float(np.median(list(vs.values()))) if vs else 0
            rel = [x / med for x in vs.values()] if med > 0.3 else []
        if len(rel) >= MIN_VENTANAS:
            out[v] = round(float(np.std(rel) * 100), 1)
    return out


def tipo_set(tr: Traza, e: int, vt) -> dict | None:
    """Tras rodear la baliza de barlovento (o el offset): ¿traslucha nada más montar o sigue en la
    misma banda? Compara la banda de 5–15 s tras el rodeo con la de 20–45 s."""
    i = tr.tramo(e, e + SET_VENTANA_MS + 15_000)
    if len(i) < 10:
        return None
    i = i[~np.isnan(tr.cog[i]) & (tr.sog[i] > vt.sog_min)]
    if len(i) < 10:
        return None
    t = (tr.ts[i] - e) / 1000
    b = lado(tr, i, vt.twd_en(tr.ts[i]), False)
    a, d = b[(t >= 5) & (t <= 15)], b[(t >= 20) & (t <= SET_VENTANA_MS / 1000)]
    if len(a) < 3 or len(d) < 3:
        return None
    antes, despues = np.nanmedian(a), np.nanmedian(d)
    if antes == despues:
        return {"set": "directo"}
    cambio = np.nonzero((t > 5) & (b != antes))[0]
    return {"set": "trasluchando", "trasluchada_s": round(float(t[cambio[0]])) if len(cambio) else None}


def rodeo(tr: Traza, paso) -> dict | None:
    """Tiempo dentro de la zona de la baliza y velocidad mínima en ella."""
    if paso is None or paso.entrada is None or paso.salida is None or paso.salida <= paso.entrada:
        return None
    i = tr.tramo(paso.entrada, paso.salida)
    if len(i) < 2:
        return None
    return {"tiempo_zona_s": round((paso.salida - paso.entrada) / 1000, 1),
            "sog_entrada": round(float(tr.sog[i[0]]), 2), "sog_minima": round(float(np.min(tr.sog[i])), 2),
            "sog_salida": round(float(tr.sog[i[-1]]), 2)}
