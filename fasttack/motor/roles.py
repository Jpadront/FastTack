"""Roles locales: el viento en cada punto y momento a partir del rumbo de los propios barcos (estimado).

Sin anemómetro, la TWD reconstruida por cortes (viento.py) es la misma en todo el campo. Pero un
barco navegando estable mantiene casi constante su ángulo real al viento: comparando cada barco
consigo mismo, cuando parece ir 4–8° más cerrado que sus vecinos su SOG apenas cambia (−0,3 %), así
que lo que cambia es el viento, no el timón. Por eso el rumbo de cada barco es un anemómetro de roles:

1. Ángulo habitual de cada barco en el tramo (mitad del ángulo entre amuras): mediana de |COG − TWD|
   navegando estable, con la TWD de los cortes.
2. Cada 5 s, muestra de viento de cada barco = su COG (media de ±15 s) ∓ su ángulo habitual, según
   la amura (en popa, con la dirección de avance y la TWD + 180).
3. Viento local de un barco en un momento = media circular de las muestras de los barcos a menos de
   300 m y ±30 s (él incluido; al menos 3 barcos). Con menos, la de los cortes.
4. Se repite una vez con el viento local en lugar del de los cortes (el ángulo habitual de cada
   barco queda medido frente a su viento local) y se vuelve a calcular el viento local.
Es una estimación: un barco que cambia de modo (orza o arriba a propósito) aparece como un role
para él, pero la mediana de los vecinos lo diluye.
"""
from __future__ import annotations

import numpy as np

from .geo import dif

PASO_MS = 5_000
MEDIA_MS = 15_000
VECINOS_MS, VECINOS_M, MIN_BARCOS = 30_000, 300.0, 3
MARGEN_RODEO_MS, MARGEN_MANIOBRA_MS = 20_000, 15_000
ITERACIONES = 2


def _media_circ(a: np.ndarray) -> float:
    r = np.radians(a)
    return float(np.degrees(np.arctan2(np.sin(r).mean(), np.cos(r).mean())) % 360)


def _muestras(tr, e: int, s: int, maniobras: list[int], sog_min: float):
    """(ts, cog medio ±15 s, x, y) cada 5 s navegando estable."""
    out = []
    for t in range(e + MARGEN_RODEO_MS, s - MARGEN_RODEO_MS + 1, PASO_MS):
        if any(abs(t - m) <= MARGEN_MANIOBRA_MS for m in maniobras):
            continue
        i = tr.tramo(t - MEDIA_MS, t + MEDIA_MS)
        i = i[~np.isnan(tr.cog[i]) & (tr.sog[i] > sog_min)]
        if len(i) < 10:
            continue
        # sin trozos con giros dentro (restos de una maniobra no detectada)
        c = _media_circ(tr.cog[i])
        if np.max(np.abs(dif(tr.cog[i] - c))) > 25:
            continue
        out.append((t, c, float(np.mean(tr.x[i])), float(np.mean(tr.y[i]))))
    return out


def viento_local(trazas: dict, en_tramo: dict[str, tuple[int, int]], vt, maniobras: dict[str, list[int]],
                 ceñida: bool) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """{vela: (ts, TWD local °)} cada 5 s navegando estable."""
    mu = {v: _muestras(trazas[v], e, s, maniobras.get(v, []), vt.sog_min) for v, (e, s) in en_tramo.items() if v in trazas}
    mu = {v: m for v, m in mu.items() if len(m) >= 5}
    if len(mu) < MIN_BARCOS:
        return {}
    velas = np.array([v for v, m in mu.items() for _ in m])
    ts = np.array([x[0] for m in mu.values() for x in m], dtype=float)
    cog = np.array([x[1] for m in mu.values() for x in m])
    xs = np.array([x[2] for m in mu.values() for x in m])
    ys = np.array([x[3] for m in mu.values() for x in m])
    twd = vt.twd_en(ts)                                   # primera vuelta: TWD de los cortes
    for _ in range(ITERACIONES):
        ref = twd if ceñida else (twd + 180) % 360        # dirección a la que se avanza con viento cuadrado
        rel = dif(cog - ref)
        lado = np.sign(rel)
        # ángulo habitual de cada barco (su mitad del ángulo entre amuras)
        off = np.zeros(len(ts))
        for v in mu:
            m = velas == v
            off[m] = np.median(np.abs(rel[m]))
        muestra = (cog - lado * off) % 360                # dirección de avance con viento cuadrado
        muestra = muestra if ceñida else (muestra + 180) % 360
        nuevo = twd.copy()
        orden = np.argsort(ts)
        tso = ts[orden]
        for k in range(len(ts)):
            a, b = np.searchsorted(tso, [ts[k] - VECINOS_MS, ts[k] + VECINOS_MS + 1])
            j = orden[a:b]
            j = j[np.hypot(xs[j] - xs[k], ys[j] - ys[k]) <= VECINOS_M]
            if len(set(velas[j])) >= MIN_BARCOS:
                nuevo[k] = _media_circ(muestra[j])
        twd = nuevo
    return {v: (ts[velas == v], twd[velas == v]) for v in mu}


def twd_en(serie: tuple[np.ndarray, np.ndarray] | None, t: np.ndarray, vt) -> np.ndarray:
    """TWD local interpolada en t (la de los cortes fuera de la serie o sin serie)."""
    base = vt.twd_en(t)
    if serie is None or len(serie[0]) < 2:
        return base
    st, sw = serie
    d = np.degrees(np.interp(t, st, np.unwrap(np.radians(sw)))) % 360
    fuera = (t < st[0] - PASO_MS) | (t > st[-1] + PASO_MS)
    return np.where(fuera, base, d)
