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


LLEGADA_DT_MAX_MS = 90_000


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
            # instante del cruce: interpolado en el segmento entre las dos muestras
            t = ts[i] + (ts[i + 1] - ts[i]) * s1[i] / (s1[i] - s2[i])
            out.append(Cruce(int(t), v, bool(s1[i] > 0)))
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
                      hueco_ms: int = 8 * 60_000, dt_max_ms: int = LLEGADA_DT_MAX_MS) -> Llegadas:
    """Los cruces de la línea de llegada se agrupan en olas (separadas > 8 min). La última ola es
    la llegada; por barco cuenta su primer cruce en el sentido mayoritario de esa ola.
    Se admite un hueco de datos de hasta `dt_max_ms` sobre la línea (la hora se interpola): con la
    cobertura de RaceSense, exigir muestras seguidas deja sin llegada a barcos que sí terminaron."""
    c = cruces(barcos, a, b, desde, hasta, dt_max_ms)
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


# ---------------------------------------------------------------- sesiones propias (.vkx, sin línea de llegada)

VENTANA_REF_MS = 10 * 60_000     # velocidad de referencia: los 10 primeros minutos de la prueba
FRACCION_PARADA = 0.55           # tras la llegada, la SOG (mediana móvil de 90 s) baja de esto
PARADA_LIMPIA_MS = 5 * 60_000    # llegada «limpia»: el barco para en los 5 min siguientes
PASADO_M = 250.0                 # la llegada no está más allá de esto de la última baliza


@dataclass
class LlegadaPropia:
    t: int
    x: float
    y: float
    limpia: bool                 # el barco se paró enseguida (llegada fiable)
    tramo_final: str             # 'popa' (llegada a sotavento) o 'ceñida'
    ventana: tuple[int, int]     # desde el último rodeo hasta el final de la búsqueda
    rodeos: int


def llegada_sin_linea(tr, eje: float, ox: float, oy: float, senal: int, fin: int) -> LlegadaPropia | None:
    """Llegada de un barco sin línea de llegada conocida: final del último tramo del recorrido.

    1. Fin de la regata del barco: la SOG (mediana móvil de 90 s) cae por debajo del 55 % de la de
       los 10 primeros minutos, o el final de la ventana (señal siguiente).
    2. Rodeos: extremos alternos del avance a lo largo del eje (como en recorrido.extremos).
    3. Llegada: punto más avanzado del último tramo (más a sotavento si es una popa), sin pasar
       más de 250 m de la baliza anterior en ese sentido."""
    from .geo import a_ejes
    from .recorrido import HISTERESIS_MIN_M, extremos
    tg = np.arange(senal, fin, 5_000)
    if len(tg) < 30:
        return None
    sg = np.interp(tg, tr.ts, tr.sog)
    ref = float(np.median(sg[tg < senal + VENTANA_REF_MS]))
    med = np.array([np.median(sg[max(0, j - 17):j + 1]) for j in range(len(sg))])
    baja = np.nonzero((tg > senal + VENTANA_REF_MS) & (med < FRACCION_PARADA * ref))[0]
    parada = int(tg[baja[0]]) if len(baja) else fin
    i = tr.tramo(senal, parada)
    if len(i) < 10:
        return None
    a, _ = a_ejes(tr.x[i] - ox, tr.y[i] - oy, eje)
    ext = extremos(tr, eje, senal, parada, max(HISTERESIS_MIN_M, 0.2 * float(np.max(a))))
    if not ext:
        return None
    tipo, t_ext = ext[-1][0], ext[-1][1]
    previos = [e for e in ext if e[0] != tipo]
    a_prev = float(a_ejes(previos[-1][2] - ox, previos[-1][3] - oy, eje)[0]) if previos else 0.0
    j = tr.tramo(t_ext, parada)
    if len(j) < 2:
        return None
    aj, _ = a_ejes(tr.x[j] - ox, tr.y[j] - oy, eje)
    sentido = 1 if tipo == "max" else -1          # tras barlovento se baja
    pasado = np.nonzero(sentido * (a_prev - aj) > PASADO_M)[0]
    if len(pasado) > 1:
        j, aj = j[:pasado[0]], aj[:pasado[0]]
    k = j[int(np.argmin(sentido * aj))]
    return LlegadaPropia(int(tr.ts[k]), float(tr.x[k]), float(tr.y[k]), parada - int(tr.ts[k]) <= PARADA_LIMPIA_MS,
                         "popa" if tipo == "max" else "ceñida", (t_ext, int(tr.ts[j[-1]])), len(ext))


def ajustar_a_referencia(tr, ll: LlegadaPropia, rx: float, ry: float, radio_m: float = 300.0) -> LlegadaPropia | None:
    """Llegada no limpia (el barco siguió navegando): máxima aproximación, en el último tramo, al
    punto de llegada de las pruebas limpias del mismo día. None si no pasa a menos de radio_m."""
    i = tr.tramo(*ll.ventana)
    if not len(i):
        return None
    d = np.hypot(tr.x[i] - rx, tr.y[i] - ry)
    k = int(np.argmin(d))
    if d[k] > radio_m:
        return None
    j = i[k]
    return LlegadaPropia(int(tr.ts[j]), float(tr.x[j]), float(tr.y[j]), False, ll.tramo_final, ll.ventana, ll.rodeos)
