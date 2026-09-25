"""¿Por qué se sobrepasó la layline? Tráfico o cálculo (estimado, con las posiciones de toda la flota).

Para un barco que sobrepasó la layline, la decisión está entre el momento en que cruzó la layline
(sobre la amura anterior) y su última maniobra hacia la baliza. En ese intervalo:

- **No podía virar**: había otro barco a menos de 3 esloras en el lado hacia el que tenía que virar
  (entre su rumbo y el de la nueva amura). Si eso pasa en ≥ 50 % del intervalo, el sobrepaso fue
  forzado por el tráfico.
- **Layline con tráfico**: al cruzar la layline, ya había ≥ 3 barcos navegando por ella delante (en
  la nueva amura, a menos de 3 esloras de la recta y más cerca de la baliza). Virar debajo de ellos
  es navegar en aire sucio: pasarse un poco para tener aire limpio es una decisión táctica.
- **Cálculo**: ninguna de las dos: nadie impedía virar ni ocupaba la layline.

Las posiciones de la flota se toman en una rejilla de 5 s (sin rellenar huecos de más de 10 s).
"""
from __future__ import annotations

import numpy as np

from .trazas import Traza

PASO_MS = 5_000
HUECO_MS = 10_000
MIN_EN_LAYLINE = 3
BLOQUEO_PCT = 50


class Rejilla:
    """Posición y rumbo de cada barco cada 5 s en [t0, t1] (NaN en los huecos)."""

    def __init__(self, trazas: dict[str, Traza], t0: int, t1: int):
        self.t = np.arange(t0, t1 + PASO_MS, PASO_MS, dtype=np.int64)
        self.velas = [v for v, x in trazas.items() if len(x.ts) >= 2]
        n, m = len(self.velas), len(self.t)
        self.x = np.full((n, m), np.nan)
        self.y = np.full((n, m), np.nan)
        self.cog = np.full((n, m), np.nan)
        for k, v in enumerate(self.velas):
            tr = trazas[v]
            j = np.searchsorted(tr.ts, self.t)
            ok = (j > 0) & (j < len(tr.ts))
            jj = np.clip(j, 1, len(tr.ts) - 1)
            a, b = tr.ts[jj - 1], tr.ts[jj]
            ok &= (b - a) <= HUECO_MS
            f = np.where(b > a, (self.t - a) / np.maximum(b - a, 1), 0.0)
            self.x[k] = np.where(ok, tr.x[jj - 1] + (tr.x[jj] - tr.x[jj - 1]) * f, np.nan)
            self.y[k] = np.where(ok, tr.y[jj - 1] + (tr.y[jj] - tr.y[jj - 1]) * f, np.nan)
            self.cog[k] = np.where(ok, tr.cog[jj - 1], np.nan)
        self.idx = {v: k for k, v in enumerate(self.velas)}

    def columna(self, t: int) -> int:
        return int(np.clip(round((t - self.t[0]) / PASO_MS), 0, len(self.t) - 1))


def _dif(a):
    return (a + 180) % 360 - 180


def analizar(rej: Rejilla, v: str, marca: tuple[float, float], centro: float, semi: float,
             t_desde: int, tp: int, zona_m: float) -> dict | None:
    """Motivo del sobrepaso del barco v (su última maniobra en tp; la anterior, o el inicio del tramo,
    en t_desde). None si no hay datos suficientes."""
    k = rej.idx.get(v)
    if k is None or tp - t_desde < PASO_MS:
        return None
    c0, c1 = rej.columna(t_desde), rej.columna(tp)
    xs, ys = rej.x[k, c0:c1 + 1], rej.y[k, c0:c1 + 1]
    mx, my = marca
    dem = np.degrees(np.arctan2(mx - xs, my - ys)) % 360
    rel = _dif(dem - centro)
    exceso = np.where(rel > semi, rel - semi, np.where(rel < -semi, rel + semi, 0.0))
    fuera = (exceso != 0) & ~np.isnan(xs)
    if not fuera.any():
        return None
    # cruce de la layline: primer instante a partir del cual el barco ya queda fuera (≥ 80 %)
    n = len(fuera)
    ini = next((i for i in range(n) if fuera[i] and fuera[i:].mean() >= 0.8), None)
    if ini is None:
        return None
    c_cruce = c0 + ini
    # amura final: la del borde del cono por el que se sobrepasó
    signo = 1 if np.nanmedian(exceso[ini:][exceso[ini:] != 0]) > 0 else -1
    k_final = (centro + signo * semi) % 360
    # 1) ¿podía virar? barcos a < 3 esloras en el sector hacia el que tenía que girar
    bloqueado, validos = 0, 0
    for c in range(c_cruce, c1 + 1):
        x0, y0, cg = rej.x[k, c], rej.y[k, c], rej.cog[k, c]
        if np.isnan(x0) or np.isnan(cg):
            continue
        validos += 1
        dx, dy = rej.x[:, c] - x0, rej.y[:, c] - y0
        d = np.hypot(dx, dy)
        cerca = (d > 0) & (d <= zona_m)
        if not cerca.any():
            continue
        dem_o = np.degrees(np.arctan2(dx, dy)) % 360
        giro = _dif(k_final - cg)                       # hacia dónde tendría que girar
        rel_o = _dif(dem_o - cg)
        en_sector = np.where(giro >= 0, (rel_o >= 0) & (rel_o <= giro + 30), (rel_o <= 0) & (rel_o >= giro - 30))
        if np.any(cerca & en_sector):
            bloqueado += 1
    bloq_pct = round(100 * bloqueado / validos) if validos else None
    # 2) ¿había barcos ya en la layline, delante, al cruzarla?
    x0, y0 = rej.x[k, c_cruce], rej.y[k, c_cruce]
    ux, uy = np.sin(np.radians(k_final)), np.cos(np.radians(k_final))
    ox, oy = rej.x[:, c_cruce] - mx, rej.y[:, c_cruce] - my
    a_lo_largo = -(ox * ux + oy * uy)                   # distancia a la baliza a lo largo de la layline
    perp = np.abs(ox * uy - oy * ux)                     # distancia a la layline
    mio = -((x0 - mx) * ux + (y0 - my) * uy)
    rumbo_ok = np.abs(_dif(rej.cog[:, c_cruce] - k_final)) <= 25
    en_layline = (perp <= zona_m) & (a_lo_largo > 0) & (a_lo_largo < mio) & rumbo_ok
    en_layline[k] = False
    n_lay = int(np.nansum(en_layline))
    if bloq_pct is not None and bloq_pct >= BLOQUEO_PCT:
        motivo = "no_podia_virar"
    elif n_lay >= MIN_EN_LAYLINE:
        motivo = "layline_con_trafico"
    else:
        motivo = "calculo"
    return {"motivo": motivo, "barcos_en_layline": n_lay, "bloqueado_pct": bloq_pct,
            "segundos_hasta_virar": max(0, int((tp - int(rej.t[c_cruce])) / 1000))}
