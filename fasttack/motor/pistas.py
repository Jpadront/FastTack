"""Trazas por dispositivo a partir de la tabla de telemetría, en coordenadas locales (metros)."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ..ingesta.normalizar import vela

M_POR_GRADO = 111_320.0


@dataclass
class Proyeccion:
    """Equirrectangular local: suficiente para un campo de regatas de pocos km."""
    lat0: float
    lon0: float

    @property
    def k(self) -> float:
        return math.cos(math.radians(self.lat0))

    def xy(self, lat, lon):
        return ((np.asarray(lon) - self.lon0) * self.k * M_POR_GRADO,
                (np.asarray(lat) - self.lat0) * M_POR_GRADO)


@dataclass
class Pista:
    ts: np.ndarray  # ms, ordenado
    x: np.ndarray
    y: np.ndarray
    fija: bool = False  # posición constante (p. ej. extremo de línea del documento): no caduca

    def en(self, t: np.ndarray, edad_max_ms: int = 15 * 60_000):
        """Posición (última muestra ≤ t, de hace ≤ edad_max) para cada t; NaN si no hay."""
        t = np.asarray(t)
        i = np.searchsorted(self.ts, t, side="right") - 1
        ok = (i >= 0) & ((t - self.ts[np.clip(i, 0, None)] <= edad_max_ms) | self.fija)
        i = np.clip(i, 0, None)
        return np.where(ok, self.x[i], np.nan), np.where(ok, self.y[i], np.nan)

    @classmethod
    def constante(cls, x: float, y: float) -> "Pista":
        return cls(np.array([-(2**62)]), np.array([x]), np.array([y]), fija=True)


def pistas(cols: dict, proy: Proyeccion) -> tuple[dict[str, Pista], dict[int, Pista]]:
    """(barcos por vela normalizada, balizas por sn). Una vela con dos Atlas se une en una traza."""
    x, y = proy.xy(cols["latitude"], cols["longitude"])
    barcos, balizas = {}, {}
    es_marca = cols["role"] == "mark"
    for sn in np.unique(cols["sn"][es_marca]):
        m = es_marca & (cols["sn"] == sn)
        balizas[int(sn)] = Pista(cols["ts"][m], x[m], y[m])
    comp = ~es_marca
    claves = np.array([vela(v) for v in cols["sail_number"][comp]], dtype=object)
    idx = np.nonzero(comp)[0]
    for v in np.unique(claves):
        if not v:
            continue
        sel = idx[claves == v]
        o = np.argsort(cols["ts"][sel], kind="stable")
        sel = sel[o]
        barcos[v] = Pista(cols["ts"][sel], x[sel], y[sel])
    return barcos, balizas
