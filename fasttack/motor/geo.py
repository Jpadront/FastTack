"""Ángulos y geometría plana (coordenadas locales en metros, x = este, y = norte)."""
from __future__ import annotations

import math

import numpy as np

KN = 1852 / 3600  # m/s por nudo


def dif(a):
    """Diferencia angular normalizada a (-180, 180]."""
    return (np.asarray(a) + 180.0) % 360.0 - 180.0


def rumbo(dx, dy):
    """Rumbo (0 = norte, 90 = este) del vector (dx, dy)."""
    return np.degrees(np.arctan2(dx, dy)) % 360.0


def unitario(rumbo_deg):
    r = math.radians(rumbo_deg)
    return math.sin(r), math.cos(r)


def media_circular(angulos, pesos=None) -> float:
    a = np.radians(np.asarray(angulos, dtype=float))
    w = np.ones_like(a) if pesos is None else np.asarray(pesos, dtype=float)
    return float(np.degrees(np.arctan2((w * np.sin(a)).sum(), (w * np.cos(a)).sum())) % 360.0)


def mediana_circular(angulos, referencia: float) -> float:
    """Mediana de ángulos cercanos entre sí, medida alrededor de `referencia`."""
    return float((referencia + np.median(dif(np.asarray(angulos) - referencia))) % 360.0)


def a_ejes(x, y, rumbo_eje: float):
    """(a lo largo del eje, a la derecha del eje) para un eje con ese rumbo."""
    ux, uy = unitario(rumbo_eje)
    x, y = np.asarray(x), np.asarray(y)
    return x * ux + y * uy, x * uy - y * ux


def distancia(x1, y1, x2, y2):
    return np.hypot(np.asarray(x2) - x1, np.asarray(y2) - y1)
