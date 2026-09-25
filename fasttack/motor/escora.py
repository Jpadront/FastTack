"""Escora óptima en ceñida (estimada), a partir de toda la flota.

1. Cada ceñida se corta en segmentos de 30 s por barco, fuera de los rodeos (20 s) y de las
   maniobras (30 s antes y 15 s después), con ≥ 70 % de datos y rumbo estable.
2. En cada segmento: escora = mediana de |roll − desviación del sensor| y VMG media.
3. VMG relativa = VMG del segmento / mediana de la VMG de sus vecinos: los segmentos de otros barcos
   a menos de 300 m y ±30 s (al menos 3). Los vecinos tienen el mismo viento, así que se quitan la
   presión y las roladas, también las locales: comparar con toda la flota daría ventaja a quien
   pilla una racha, que escora más y va más rápido aunque la escora no sea la causa.
4. Se agrupa en franjas de escora de 2° (≥ 30 segmentos y ≥ 8 barcos por franja) y se busca la
   franja con mejor VMG relativa (por su media menos un error típico). El rango óptimo son las franjas contiguas a la mejor que pierden
   < 1 %. Una franja es claramente peor si pierde ≥ 1 % y más de 2 errores típicos de la diferencia. Con
   estos datos la curva es una meseta, no un pico: un valor único sería falsa precisión.
5. Es concluyente si alguna franja queda claramente peor; se da la pérdida de la franja peor más
   cercana por debajo y por encima del rango. Si no, la escora no marca diferencias en ese tramo.
Es una asociación en la flota, no un experimento: la escora también depende del peso y del estilo
de cada tripulación.
"""
from __future__ import annotations

import numpy as np

from .trazas import Traza
from .viento import VientoTramo

SEGMENTO_MS = 30_000
MARGEN_RODEO_MS = 20_000
ANTES_MANIOBRA_MS, TRAS_MANIOBRA_MS = 30_000, 15_000
VECINOS_MS, VECINOS_M, MIN_VECINOS = 30_000, 300.0, 3
FRANJA = 2
MIN_SEGMENTOS, MIN_BARCOS = 30, 8


def segmentos(trazas: dict[str, Traza], barcos: dict[str, tuple[int, int]], viento: VientoTramo,
              maniobras: dict[str, list[int]], offsets: dict[str, float]) -> list[tuple]:
    """(vela, t centro, escora °, VMG kn, x, y) de cada segmento válido."""
    out = []
    for v, (e, s) in barcos.items():
        x = trazas.get(v)
        if x is None:
            continue
        mans = maniobras.get(v, [])
        off = offsets.get(v, 0.0)
        a = e + MARGEN_RODEO_MS
        while a + SEGMENTO_MS <= s - MARGEN_RODEO_MS:
            b = a + SEGMENTO_MS
            if not any(a - TRAS_MANIOBRA_MS < m < b + ANTES_MANIOBRA_MS for m in mans) and x.cobertura(a, b) >= 0.7:
                i = x.tramo(a, b)
                i = i[~np.isnan(x.cog[i]) & (x.sog[i] > 2)]
                if len(i) >= 8:
                    twd = viento.twd_en(x.ts[i])
                    vmg = float(np.mean(x.sog[i] * np.cos(np.radians(x.cog[i] - twd))))
                    out.append((v, (a + b) / 2, float(np.median(np.abs(x.roll[i] - off))), vmg,
                                float(np.mean(x.x[i])), float(np.mean(x.y[i]))))
            a = b
    return out


def optima(segs: list[tuple]) -> dict | None:
    if len(segs) < 3 * MIN_SEGMENTOS:
        return None
    v = np.array([s[3] for s in segs])
    t = np.array([s[1] for s in segs])
    h = np.array([s[2] for s in segs])
    velas = np.array([s[0] for s in segs])
    x = np.array([s[4] for s in segs])
    y = np.array([s[5] for s in segs])
    ref = np.full(len(v), np.nan)
    for k in range(len(v)):
        m = (np.abs(t - t[k]) <= VECINOS_MS) & (np.hypot(x - x[k], y - y[k]) <= VECINOS_M) & (velas != velas[k])
        if len(set(velas[m])) >= MIN_VECINOS:
            ref[k] = np.median(v[m])
    ok = np.nan_to_num(ref) > 0.5
    rel = np.where(ok, v / np.where(ok, ref, 1) * 100, np.nan)
    if ok.sum() < 3 * MIN_SEGMENTOS:
        return None
    franjas = []
    for lo in range(int(np.nanmin(h)) // FRANJA * FRANJA, int(np.nanmax(h)) + FRANJA, FRANJA):
        m = (h >= lo) & (h < lo + FRANJA) & ok
        if m.sum() >= MIN_SEGMENTOS and len(set(velas[m])) >= MIN_BARCOS:
            franjas.append({"desde": lo, "hasta": lo + FRANJA, "segmentos": int(m.sum()), "barcos": len(set(velas[m])),
                            "vmg_rel_pct": round(float(np.mean(rel[m])), 1),
                            "_se": float(np.std(rel[m]) / np.sqrt(m.sum()))})
    if len(franjas) < 2:
        return None
    # la mejor por su cota inferior (media − error típico): una franja con pocos datos no gana por ruido
    k = max(range(len(franjas)), key=lambda j: franjas[j]["vmg_rel_pct"] - franjas[j]["_se"])
    mejor = franjas[k]

    def peor(f):
        """Claramente peor que la mejor franja: ≥ 1 % y más de 2 errores típicos de la diferencia."""
        d = mejor["vmg_rel_pct"] - f["vmg_rel_pct"]
        return d > max(1.0, 2 * float(np.hypot(mejor["_se"], f["_se"])))

    def cerca(f):
        """Pierde menos de un 1 % frente a la mejor (dentro del ruido práctico)."""
        return mejor["vmg_rel_pct"] - f["vmg_rel_pct"] < 1.0

    # rango: franjas contiguas a la mejor que pierden < 1 %; las franjas con pocos datos y mucha
    # incertidumbre cortan el rango pero no cuentan como peores si no lo son claramente
    a, b = k, k
    while a > 0 and cerca(franjas[a - 1]) and franjas[a - 1]["hasta"] == franjas[a]["desde"]:
        a -= 1
    while b < len(franjas) - 1 and cerca(franjas[b + 1]) and franjas[b + 1]["desde"] == franjas[b]["hasta"]:
        b += 1
    lo, hi = franjas[a]["desde"], franjas[b]["hasta"]
    debajo = [f for f in franjas if f["hasta"] <= lo and peor(f)]
    encima = [f for f in franjas if f["desde"] >= hi and peor(f)]
    for f in franjas:
        f.pop("_se")
    perdida = lambda f: round(mejor["vmg_rel_pct"] - f["vmg_rel_pct"], 1)
    return {
        "franjas": franjas,
        "mejor": [mejor["desde"], mejor["hasta"]],
        "rango": [lo, hi],
        "concluyente": bool(debajo or encima),
        # la franja peor más cercana al rango, por cada lado: «por debajo de 12°, −1,5 %»
        "debajo": {"hasta_grados": debajo[-1]["hasta"], "perdida_pct": perdida(debajo[-1])} if debajo else None,
        "encima": {"desde_grados": encima[0]["desde"], "perdida_pct": perdida(encima[0])} if encima else None,
        "navegado": [int(np.percentile(h, 10)), int(np.percentile(h, 90))],
        "segmentos": int(ok.sum()),
        "_por_barco": {b: [float(e) for e in h[velas == b]] for b in set(velas)},
    }


def en_rango_por_barco(opt: dict) -> dict[str, float]:
    """% de los segmentos de cada barco dentro del rango óptimo (solo si el resultado es concluyente)."""
    if not opt["concluyente"]:
        return {}
    lo, hi = opt["rango"]
    return {b: round(100 * sum(lo <= x < hi for x in hs) / len(hs)) for b, hs in opt["_por_barco"].items() if hs}
