"""Trazas de los barcos con todos sus canales (posición, SOG, rumbo, escora, cabeceo) y COG.

La telemetría llega con huecos (cobertura ~50 %): nada aquí rellena lo que no hay. El COG solo se
calcula entre muestras separadas ≤ 5 s y los cálculos por tramo miden su cobertura.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..ingesta.normalizar import vela
from .geo import rumbo
from .pistas import Proyeccion

HUECO_MS = 5_000  # separación máxima entre muestras para considerarlas continuas


@dataclass
class Traza:
    vela: str
    ts: np.ndarray      # ms
    x: np.ndarray       # m
    y: np.ndarray
    sog: np.ndarray     # kn
    hdg: np.ndarray     # grados (tal cual el dispositivo)
    roll: np.ndarray    # grados, + = escora a estribor
    pitch: np.ndarray
    cog: np.ndarray     # grados, NaN donde no hay muestras vecinas

    def tramo(self, t0: int, t1: int) -> np.ndarray:
        """Índices de las muestras en [t0, t1]."""
        return np.arange(np.searchsorted(self.ts, t0), np.searchsorted(self.ts, t1, side="right"))

    def en(self, t: float, canal: str = "xy", hueco_ms: int = HUECO_MS):
        """Valor interpolado en t; None si t cae en un hueco (> hueco_ms entre muestras)."""
        i = np.searchsorted(self.ts, t)
        if i == 0 or i >= len(self.ts):
            if i < len(self.ts) and self.ts[i] == t:
                i += 1
            else:
                return None
        a, b = i - 1, i
        dt = self.ts[b] - self.ts[a]
        if dt > hueco_ms:
            return None
        f = (t - self.ts[a]) / dt if dt else 0.0
        if canal == "xy":
            return (self.x[a] + (self.x[b] - self.x[a]) * f, self.y[a] + (self.y[b] - self.y[a]) * f)
        v = getattr(self, canal)
        return float(v[a] + (v[b] - v[a]) * f)

    def cobertura(self, t0: int, t1: int, hueco_ms: int = HUECO_MS) -> float:
        """Fracción de [t0, t1] cubierta por muestras separadas ≤ hueco_ms."""
        if t1 <= t0:
            return 0.0
        ts = self.ts[(self.ts >= t0 - hueco_ms) & (self.ts <= t1 + hueco_ms)]
        if len(ts) < 2:
            return 0.0
        a, b = np.clip(ts[:-1], t0, t1), np.clip(ts[1:], t0, t1)
        ok = np.diff(ts) <= hueco_ms
        return float(((b - a) * ok).sum() / (t1 - t0))


def construir(cols: dict, proy: Proyeccion) -> dict[str, Traza]:
    """Una traza por vela (una vela con dos Atlas se une en una)."""
    comp = cols["role"] != "mark"
    claves = np.array([vela(v) for v in cols["sail_number"][comp]], dtype=object)
    idx = np.nonzero(comp)[0]
    x, y = proy.xy(cols["latitude"], cols["longitude"])
    out = {}
    for v in np.unique(claves):
        if not v:
            continue
        sel = idx[claves == v]
        sel = sel[np.argsort(cols["ts"][sel], kind="stable")]
        ts = cols["ts"][sel].astype(np.int64)
        _, u = np.unique(ts, return_index=True)  # dos dispositivos en la misma décima
        sel, ts = sel[u], ts[u]
        tx, ty = x[sel], y[sel]
        out[v] = Traza(v, ts, tx, ty, cols["sog"][sel].astype(float), cols["heading"][sel].astype(float),
                       cols["roll"][sel].astype(float), cols["pitch"][sel].astype(float), cog(ts, tx, ty))
    return out


def cog(ts, x, y, hueco_ms: int = HUECO_MS) -> np.ndarray:
    """COG por diferencia centrada (o lateral en los bordes de un hueco)."""
    n = len(ts)
    out = np.full(n, np.nan)
    if n < 2:
        return out
    dt = np.diff(ts)
    ok = dt <= hueco_ms
    seg = rumbo(np.diff(x), np.diff(y))
    mov = np.hypot(np.diff(x), np.diff(y)) > 0.3  # sin desplazamiento el rumbo no vale
    seg = np.where(ok & mov, seg, np.nan)
    # centrado: media circular del segmento anterior y el siguiente
    prev, nxt = np.r_[np.nan, seg], np.r_[seg, np.nan]
    s = np.nan_to_num(np.sin(np.radians(prev))) + np.nan_to_num(np.sin(np.radians(nxt)))
    c = np.nan_to_num(np.cos(np.radians(prev))) + np.nan_to_num(np.cos(np.radians(nxt)))
    alguno = ~(np.isnan(prev) & np.isnan(nxt))
    out[alguno] = np.degrees(np.arctan2(s[alguno], c[alguno])) % 360.0
    return out
