"""Escora óptima en ceñida y en popa (estimada), a partir de toda la flota.

En popa la escora lleva signo: + = a sotavento, − = a barlovento (en popa se escora a barlovento a
propósito con poco viento, para equilibrar el timón y abrir el spi). En ceñida, siempre a sotavento.

1. Cada ceñida se corta en segmentos de 30 s por barco, fuera de los rodeos (20 s) y de las
   maniobras (30 s antes y 15 s después), con ≥ 70 % de datos y rumbo estable.
2. En cada segmento: escora = mediana de |roll − desviación del sensor| y VMG media.
3. VMG relativa = VMG del segmento / mediana de la VMG de sus vecinos: los segmentos de otros barcos
   en la misma amura a menos de 300 m y ±30 s (al menos 3). Igual con la SOG: si con más escora la
   SOG sigue subiendo pero la VMG baja, el barco va más rápido pero pierde altura (abatimiento o
   rumbo más abierto); si bajan las dos, le falta potencia. Los vecinos tienen el mismo viento, así que se quitan la
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
    ceñida = viento.ceñida
    """(vela, t centro, escora °, VMG kn, x, y, amura ±1, SOG kn) de cada segmento válido."""
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
                i = i[~np.isnan(x.cog[i]) & (x.sog[i] > viento.sog_min)]
                if len(i) >= 8:
                    twd = viento.twd_en(x.ts[i])
                    al_viento = (x.cog[i] - twd + 540) % 360 - 180             # + = viento por babor
                    rel = al_viento if ceñida else (al_viento + 360) % 360 - 180
                    vmg = float(np.mean(x.sog[i] * np.cos(np.radians(rel))))
                    if ceñida:
                        esc = float(np.median(np.abs(x.roll[i] - off)))
                    else:   # a sotavento (+) o a barlovento (−): viento por babor → sotavento = estribor (roll +)
                        esc = float(np.median((x.roll[i] - off) * np.sign(al_viento)))
                    out.append((v, (a + b) / 2, esc, vmg,
                                float(np.mean(x.x[i])), float(np.mean(x.y[i])), float(np.sign(np.median(rel))),
                                float(np.mean(x.sog[i]))))
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
    amura = np.array([s[6] for s in segs])
    sog = np.array([s[7] for s in segs])
    ref = np.full(len(v), np.nan)
    ref_sog = np.full(len(v), np.nan)
    for k in range(len(v)):
        m = ((np.abs(t - t[k]) <= VECINOS_MS) & (np.hypot(x - x[k], y - y[k]) <= VECINOS_M)
             & (velas != velas[k]) & (amura == amura[k]))
        if len(set(velas[m])) >= MIN_VECINOS:
            ref[k] = np.median(v[m])
            ref_sog[k] = np.median(sog[m])
    ok = np.nan_to_num(ref) > 0.5
    rel = np.where(ok, v / np.where(ok, ref, 1) * 100, np.nan)
    rel_sog = np.where(ok, sog / np.where(ok, ref_sog, 1) * 100, np.nan)
    if ok.sum() < 3 * MIN_SEGMENTOS:
        return None
    franjas = []
    for lo in range(int(np.nanmin(h)) // FRANJA * FRANJA, int(np.nanmax(h)) + FRANJA, FRANJA):
        m = (h >= lo) & (h < lo + FRANJA) & ok
        if m.sum() >= MIN_SEGMENTOS and len(set(velas[m])) >= MIN_BARCOS:
            franjas.append({"desde": lo, "hasta": lo + FRANJA, "segmentos": int(m.sum()), "barcos": len(set(velas[m])),
                            "vmg_rel_pct": round(float(np.mean(rel[m])), 1),
                            "sog_rel_pct": round(float(np.mean(rel_sog[m])), 1),
                            "error_pct": round(float(np.std(rel[m]) / np.sqrt(m.sum())), 2)})
    r = _evaluar(franjas)
    if r is None:
        return None
    return r | {"navegado": [int(np.percentile(h, 10)), int(np.percentile(h, 90))],
                "segmentos": int(ok.sum()),
                "_por_barco": {b: [float(e) for e in h[velas == b]] for b in set(velas)}}


def _evaluar(franjas: list[dict]) -> dict | None:
    """Mejor franja, rango óptimo y pérdidas a partir de las franjas (con su error típico)."""
    if len(franjas) < 2:
        return None
    se = lambda f: f["error_pct"]
    # la mejor por su cota inferior (media − error típico): una franja con pocos datos no gana por ruido
    k = max(range(len(franjas)), key=lambda j: franjas[j]["vmg_rel_pct"] - se(franjas[j]))
    mejor = franjas[k]

    def peor(f):
        """Claramente peor que la mejor franja: ≥ 1 % y más de 2 errores típicos de la diferencia."""
        d = mejor["vmg_rel_pct"] - f["vmg_rel_pct"]
        return d > max(1.0, 2 * float(np.hypot(se(mejor), se(f))))

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
    perdida = lambda f: round(mejor["vmg_rel_pct"] - f["vmg_rel_pct"], 1)
    return {
        "franjas": franjas,
        "mejor": [mejor["desde"], mejor["hasta"]],
        "rango": [lo, hi],
        "concluyente": bool(debajo or encima),
        # la franja peor más cercana al rango, por cada lado: «por debajo de 12°, −1,5 %»
        "debajo": {"hasta_grados": debajo[-1]["hasta"], "perdida_pct": perdida(debajo[-1])} if debajo else None,
        "encima": {"desde_grados": encima[0]["desde"], "perdida_pct": perdida(encima[0])} if encima else None,
        # con más escora que el rango: ¿más rápido pero más abierto? (SOG ≥ 1,5 puntos por encima de la VMG)
        "sobreescora": next(({"desde_grados": f["desde"], "sog_rel_pct": f["sog_rel_pct"], "vmg_rel_pct": f["vmg_rel_pct"]}
                             for f in franjas if f["desde"] >= hi and f["sog_rel_pct"] - f["vmg_rel_pct"] >= 1.5), None),
    }


def combinar(grupos: list[list[dict]]) -> dict | None:
    """Junta las franjas de varias ceñidas (cada una ya relativa a sus vecinos): media ponderada por
    segmentos y error típico combinado. Sirve para el campeonato o para una intensidad de viento."""
    por = {}
    for franjas in grupos:
        for f in franjas:
            por.setdefault(f["desde"], []).append(f)
    out = []
    for lo in sorted(por):
        fs = por[lo]
        n = sum(f["segmentos"] for f in fs)
        if n < 2 * MIN_SEGMENTOS:
            continue
        w = lambda k: sum(f[k] * f["segmentos"] for f in fs) / n
        out.append({"desde": lo, "hasta": lo + FRANJA, "segmentos": n, "ceñidas": len(fs),
                    "barcos": max(f["barcos"] for f in fs),
                    "vmg_rel_pct": round(w("vmg_rel_pct"), 1), "sog_rel_pct": round(w("sog_rel_pct"), 1),
                    "error_pct": round(float(np.sqrt(sum((f["segmentos"] * f["error_pct"]) ** 2 for f in fs)) / n), 2)})
    r = _evaluar(out)
    if r is None:
        return None
    return r | {"segmentos": sum(f["segmentos"] for f in out), "ceñidas": len(grupos)}


def en_rango_por_barco(opt: dict) -> dict[str, float]:
    """% de los segmentos de cada barco dentro del rango óptimo (solo si el resultado es concluyente)."""
    if not opt["concluyente"]:
        return {}
    lo, hi = opt["rango"]
    return {b: round(100 * sum(lo <= x < hi for x in hs) / len(hs)) for b, hs in opt["_por_barco"].items() if hs}
