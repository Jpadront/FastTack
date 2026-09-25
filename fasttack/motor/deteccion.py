"""Detección de salidas y llegadas a partir de la telemetría (para pruebas que faltan en RaceSense).

Validado con la prueba 1 del Mundial de J/70 2026 (API 2), que tiene llegadas oficiales: señal
exacta y llegadas con error mediano de 0,34 s por barco (docs/fuente_datos.md).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np

from .pistas import Pista


@dataclass
class Cruce:
    t: int          # ms
    barco: str
    sentido: bool   # True = de izquierda a derecha de la línea A→B


def cruces(barcos: dict[str, Pista], a: Pista, b: Pista, desde: int, hasta: int,
           dt_max_ms: int = 10_000) -> list[Cruce]:
    """Cruces de cada traza con el segmento A–B (posición de A y B en el instante de cada muestra)."""
    out = []
    for v, p in barcos.items():
        m = (p.ts >= desde) & (p.ts <= hasta)
        ts, x, y = p.ts[m], p.x[m], p.y[m]
        if len(ts) < 2:
            continue
        ax, ay = a.en(ts[:-1])
        bx, by = b.en(ts[:-1])
        px, py, qx, qy = x[:-1], y[:-1], x[1:], y[1:]
        s1 = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
        s2 = (bx - ax) * (qy - ay) - (by - ay) * (qx - ax)
        s3 = (qx - px) * (ay - py) - (qy - py) * (ax - px)
        s4 = (qx - px) * (by - py) - (qy - py) * (bx - px)
        ok = (np.diff(ts) <= dt_max_ms) & (s1 * s2 < 0) & (s3 * s4 < 0)
        for i in np.nonzero(ok)[0]:
            out.append(Cruce(int(ts[i]), v, bool(s1[i] > 0)))
    out.sort(key=lambda c: c.t)
    return out


def detectar_senal(barcos, pin: Pista, comite: Pista, desde: int, hasta: int,
                   minimo_barcos: int) -> tuple[int, int] | None:
    """La ventana de 60 s con más barcos distintos cruzando la línea empieza ~20 s antes de la
    señal: señal = minuto siguiente al primer cruce de esa ráfaga. Devuelve (señal, nº de barcos)."""
    c = cruces(barcos, pin, comite, desde, hasta)
    mejor, j, cuenta = (0, None), 0, Counter()
    for i, ci in enumerate(c):  # ventana deslizante [c[i].t, c[i].t + 60 s]
        while j < len(c) and c[j].t <= ci.t + 60_000:
            cuenta[c[j].barco] += 1
            j += 1
        if len(cuenta) > mejor[0]:
            mejor = (len(cuenta), ci.t)
        cuenta[ci.barco] -= 1
        if not cuenta[ci.barco]:
            del cuenta[ci.barco]
    n, t = mejor
    if t is None or n < minimo_barcos:
        return None
    return (t // 60_000 + 1) * 60_000, n


@dataclass
class Llegadas:
    tiempos: dict[str, int]     # barco → ms del cruce de llegada
    cruces_por_barco: float     # en la última ola
    duracion_ms: int            # de la última ola

    def parece_llegada(self, minimo_barcos: int) -> bool:
        """Una llegada real: cada barco cruza pocas veces (2–3) en una ola corta (~10 min). Si
        no, suele ser la flota rondando la línea mientras se recogen las balizas (entrenamiento
        del Mundial: 42 cruces por barco en 35 min)."""
        return (len(self.tiempos) >= minimo_barcos and self.cruces_por_barco <= 6
                and self.duracion_ms <= 25 * 60_000)


def detectar_llegadas(barcos, a: Pista, b: Pista, desde: int, hasta: int,
                      hueco_ms: int = 8 * 60_000) -> Llegadas:
    """Los cruces de la línea de llegada se agrupan en olas (separadas > 8 min). La última ola es
    la llegada; por barco cuenta su primer cruce en el sentido mayoritario de esa ola."""
    c = cruces(barcos, a, b, desde, hasta)
    if not c:
        return Llegadas({}, 0.0, 0)
    olas = [[c[0]]]
    for x in c[1:]:
        (olas[-1].append(x) if x.t - olas[-1][-1].t <= hueco_ms else olas.append([x]))
    ultima = olas[-1]
    sentido = Counter(x.sentido for x in ultima[:30]).most_common(1)[0][0]
    tiempos: dict[str, int] = {}
    for x in ultima:
        if x.sentido == sentido and x.barco not in tiempos:
            tiempos[x.barco] = x.t
    n_barcos = len({x.barco for x in ultima})
    return Llegadas(tiempos, len(ultima) / n_barcos, ultima[-1].t - ultima[0].t)
