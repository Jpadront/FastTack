"""Rendimiento del barco en un tramo, más allá de las medias (estimado; ver docs/metricas.md).

- Frente a los vecinos: ángulo, SOG y VMG de cada barco frente a los barcos de al lado (mismo viento).
- Regularidad: dispersión de la VMG de cada tramo de 30 s respecto a la de la flota en esos
  mismos 30 s (así las rachas y los roles, que tiene toda la flota, no cuentan).
- Set tras la baliza de barlovento: si traslucha nada más rodear o sigue en la misma banda.
- Rodeo: tiempo dentro de la zona (3 esloras) de la baliza y velocidad mínima.
"""
from __future__ import annotations

import math

import numpy as np

from .geo import dif
from .tramos import lado, vmg
from .trazas import Traza

MARGEN_RODEO_MS = 20_000
MARGEN_MANIOBRA_MS = 15_000
VENTANA_MS = 30_000
MIN_VENTANAS = 5
SET_VENTANA_MS = 45_000        # trasluchada dentro de los 45 s tras el rodeo = set trasluchando


def estables(tr: Traza, e: int, s: int, vt, maniobras_t: list[int]):
    """Índices del tramo navegando estable: sin los 20 s de cada rodeo, sin ±15 s alrededor de cada
    maniobra y sin momentos parados o sin rumbo. None si quedan menos de 10 muestras."""
    i = tr.tramo(e + MARGEN_RODEO_MS, s - MARGEN_RODEO_MS)
    if len(i) < 10:
        return None
    ok = ~np.isnan(tr.cog[i]) & (tr.sog[i] > vt.sog_min)
    for t in maniobras_t:
        ok &= np.abs(tr.ts[i] - t) > MARGEN_MANIOBRA_MS
    i = i[ok]
    return i if len(i) >= 10 else None


VECINOS_MS, VECINOS_M, MIN_VECINOS = 30_000, 300.0, 3
MIN_SEGMENTOS = 3


def frente_a_vecinos(segs: list[tuple]) -> dict[str, dict]:
    """Ángulo, SOG y VMG de cada barco frente a sus vecinos en el tramo.

    Cada segmento de 30 s navegando estable (sin rodeos, ni 30 s antes ni 25 s después de una
    maniobra) se compara con sus vecinos: otros barcos en la misma amura a < 300 m y ±30 s (al menos
    3), que tienen el mismo viento. Por barco, la mediana de sus segmentos:
    - ΔTWA (°): + = más abierto en ceñida / más bajo en popa que sus vecinos;
    - SOG y VMG en % de las de sus vecinos (100 = igual).
    No se da un «ángulo de máxima VMG»: comparando cada barco consigo mismo, cuando parece ir 4–8°
    más cerrado que sus vecinos su SOG apenas cambia (−0,3 %) y la VMG sube un 5–11 %; un barco que de
    verdad ciñe 8° más cerrado pierde mucha velocidad, así que esas diferencias son viento local
    (roles que los vecinos a 300 m no tienen), no timón. Sin anemómetro, el ángulo óptimo no se puede
    medir; la mediana de muchos segmentos sí dice si un barco navega más abierto o más cerrado que
    los que tiene al lado. Devuelve {vela: {twa_frente_vecinos, sog_frente_vecinos_pct,
    vmg_frente_vecinos_pct, segmentos}}."""
    if len(segs) < 10:
        return {}
    velas = np.array([s[0] for s in segs])
    t = np.array([s[1] for s in segs])
    v = np.array([s[3] for s in segs])
    x = np.array([s[4] for s in segs])
    y = np.array([s[5] for s in segs])
    amura = np.array([s[6] for s in segs])
    sog = np.array([s[7] for s in segs])
    twa = np.array([s[8] for s in segs])
    n = len(segs)
    r_twa, r_vmg, r_sog = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
    for k in range(n):
        m = ((np.abs(t - t[k]) <= VECINOS_MS) & (np.hypot(x - x[k], y - y[k]) <= VECINOS_M)
             & (velas != velas[k]) & (amura == amura[k]))
        if len(set(velas[m])) >= MIN_VECINOS:
            r_twa[k], r_vmg[k], r_sog[k] = np.median(twa[m]), np.median(v[m]), np.median(sog[m])
    ok = ~np.isnan(r_twa) & (np.nan_to_num(r_vmg) > 0.5) & (np.nan_to_num(r_sog) > 0.5)
    d = twa - np.where(ok, r_twa, 0)
    rel_v, rel_s = v / np.where(ok, r_vmg, 1), sog / np.where(ok, r_sog, 1)
    # fuera lo que no es navegar en rumbo (restos de maniobra, un rodeo, un barco parado)
    ok &= (np.abs(d) <= 15) & (rel_v > 0.6) & (rel_v < 1.4)
    out = {}
    for b in np.unique(velas[ok]):
        m = ok & (velas == b)
        if m.sum() >= MIN_SEGMENTOS:
            out[str(b)] = {"twa_frente_vecinos": round(float(np.median(d[m])), 1),
                           "sog_frente_vecinos_pct": round(float(np.median(rel_s[m]) - 1) * 100, 1),
                           "vmg_frente_vecinos_pct": round(float(np.median(rel_v[m]) - 1) * 100, 1),
                           "segmentos": int(m.sum())}
    return out


def vmg_por_ventanas(tr: Traza, e: int, s: int, vt, maniobras_t: list[int], t0: int) -> dict[int, float]:
    """VMG media de cada ventana de 30 s (alineadas desde t0) con ≥ 70 % de datos estables."""
    i = estables(tr, e, s, vt, maniobras_t)
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
    i = estables(tr, e, s, vt, maniobras_t)
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
    - velocidad = d / VMG estable propia − d / VMG estable del top 5, con d = largo del tramo en la
      dirección del viento (la VMG se mide a lo largo del viento);
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
        # la VMG se mide a lo largo del viento: la distancia que cubre es la del tramo en esa dirección
        dir_viento = t["viento"]["twd_media"] if t["tipo"] == "ceñida" else (t["viento"]["twd_media"] + 180) % 360
        dist = t["largo_m"] * abs(math.cos(math.radians(t["rumbo_eje"] - dir_viento)))
        d_vel = (dist / (vm * KN_MS) - dist / (v5 * KN_MS)) if vm and v5 and vm > 0.5 and v5 > 0.5 else 0.0
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
