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


def vmg_estable(tr: Traza, e: int, s: int, vt, maniobras_t: list[int]) -> float | None:
    """VMG media navegando estable (sin rodeos ni maniobras): la velocidad «pura» del barco."""
    i = _estables(tr, e, s, vt, maniobras_t)
    if i is None:
        return None
    v = vmg(tr, i, vt.twd_en(tr.ts[i]), vt.ceñida)
    w = np.minimum(np.diff(tr.ts[i], append=tr.ts[i][-1]), 5_000).astype(float)
    return float(np.sum(v * w) / w.sum()) if w.sum() > 0 else None


def segundos_en_maniobras(mans) -> float | None:
    """Segundos perdidos en las maniobras del tramo: las medidas, y las no medidas (huecos de datos)
    a la mediana de las medidas. None si no se midió ninguna."""
    med = [m.detalle["perdida_s"] for m in mans if m.detalle]
    if not mans:
        return 0.0
    if not med:
        return None
    return float(sum(med) + (len(mans) - len(med)) * np.median(med))


KN_MS = 1852 / 3600


def desglose(salida_tramos: list[dict], salida: dict | None, llegadas: dict, v: str) -> dict | None:
    """Dónde perdió (o ganó) tiempo el barco frente al top 5 de la prueba (los 5 primeros sin él).

    Por tramo, frente a la mediana del top 5:
    - velocidad = largo / VMG estable propia − largo / VMG estable del top 5;
    - maniobras = segundos perdidos en maniobras propios − los del top 5;
    - salida (solo la primera ceñida) = (metros por detrás del primero a los 60 s − los del top 5) / VMG propia;
    - táctica = diferencia de parcial − lo anterior (roladas, lado, laylines, rodeos y lo no medido).
    En el total, la táctica es la diferencia real en la llegada menos salida, velocidad y maniobras.
    + = segundos perdidos, − = ganados."""
    top5 = [x for x in sorted(llegadas, key=llegadas.get) if x != v][:5]
    if v not in llegadas or len(top5) < 3:
        return None
    sal_medida = False
    tramos, tot = [], {"salida_s": 0.0, "velocidad_s": 0.0, "maniobras_s": 0.0, "tactica_s": 0.0, "total_s": 0.0}
    for k, t in enumerate(salida_tramos):
        f = t["barcos"].get(v)
        cinco = [t["barcos"][x] for x in top5 if x in t["barcos"]]
        if not f or len(cinco) < 3 or f.get("calidad") not in ("alta", "media") or not t.get("largo_m"):
            tramos.append({"tramo": t["nombre"], "sin_datos": True})
            continue
        med = lambda key: (float(np.median([c[key] for c in cinco if c.get(key) is not None]))
                           if sum(c.get(key) is not None for c in cinco) >= 3 else None)
        d_total = f["parcial_s"] - med("parcial_s")
        vm, v5 = f.get("vmg_estable"), med("vmg_estable")
        d_vel = (t["largo_m"] / (vm * KN_MS) - t["largo_m"] / (v5 * KN_MS)) if vm and v5 and vm > 0.5 and v5 > 0.5 else 0.0
        m5 = med("perdida_man_s")
        d_man = (f["perdida_man_s"] - m5) if f.get("perdida_man_s") is not None and m5 is not None else 0.0
        d_sal = 0.0
        if k == 0 and salida:
            b = salida["barcos"].get(v) or {}
            d5 = [salida["barcos"][x].get("dist_60") for x in top5 if (salida["barcos"].get(x) or {}).get("dist_60") is not None]
            if b.get("dist_60") is not None and len(d5) >= 3 and vm:
                d_sal = (b["dist_60"] - float(np.median(d5))) / (vm * KN_MS)
                sal_medida = True
        d_tac = d_total - d_vel - d_man - d_sal
        fila = {"tramo": t["nombre"], "total_s": round(d_total), "salida_s": round(d_sal), "velocidad_s": round(d_vel),
                "maniobras_s": round(d_man), "tactica_s": round(d_tac)}
        tramos.append(fila)
        for key in tot:
            tot[key] += fila[key]
    if not any("total_s" in x for x in tramos):
        return None
    # Total: la diferencia real en la llegada frente al tiempo mediano del top 5. «Táctica y resto» es
    # lo que no explican salida, velocidad y maniobras (incluye los tramos sin datos).
    total = (llegadas[v] - float(np.median([llegadas[x] for x in top5]))) / 1000
    medidos = tot["salida_s"] + tot["velocidad_s"] + tot["maniobras_s"]
    return {"frente_a": top5, "total_s": round(total), "salida_s": round(tot["salida_s"]) if sal_medida else None,
            "velocidad_s": round(tot["velocidad_s"]), "maniobras_s": round(tot["maniobras_s"]),
            "tactica_s": round(total - medidos), "por_tramo": tramos,
            "tramos_sin_datos": sum(1 for x in tramos if x.get("sin_datos"))}
