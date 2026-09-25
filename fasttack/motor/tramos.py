"""Métricas de cada barco en cada tramo (fórmulas en docs/metricas.md)."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .geo import KN, a_ejes, dif, rumbo
from .trazas import HUECO_MS, Traza
from .viento import VientoTramo

MANIOBRA_MIN_MS = 15_000      # tiempo en la nueva amura para contar una maniobra
MARGEN_RODEO_MS = 20_000      # maniobras pegadas a un rodeo son parte del rodeo
VENTANA_ANTES_S, VENTANA_DESPUES_S = 30, 30   # pérdida en maniobra
HUECO_MANIOBRA_MS = 4_000


@dataclass
class Maniobra:
    t: int
    tipo: str                 # 'virada' | 'trasluchada'
    perdida_m: float | None   # None si hay huecos en la ventana
    x: float
    y: float


def lado(tr: Traza, i: np.ndarray, twd: np.ndarray, ceñida: bool) -> np.ndarray:
    """+1 amura babor (viento por babor), -1 amura estribor, NaN sin COG. En popa, con la TWD+180."""
    ref = twd if ceñida else (twd + 180) % 360
    d = dif(tr.cog[i] - ref)
    s = np.sign(d)  # COG a la derecha del viento (ceñida) = amura babor
    s[np.isnan(d)] = np.nan
    return s if ceñida else -s


def vmg(tr: Traza, i: np.ndarray, twd: np.ndarray, ceñida: bool) -> np.ndarray:
    """Velocidad útil (kn) hacia barlovento en ceñida y hacia sotavento en popa."""
    ref = twd if ceñida else (twd + 180) % 360
    return tr.sog[i] * np.cos(np.radians(dif(tr.cog[i] - ref)))


def maniobras(tr: Traza, t0: int, t1: int, viento: VientoTramo, margen_ini_ms: int = MARGEN_RODEO_MS) -> list[Maniobra]:
    """Viradas (ceñida) o trasluchadas (popa): cambios del lado del viento que se mantienen al
    menos MANIOBRA_MIN_MS. Las pegadas a un rodeo no cuentan (salvo al inicio desde la salida)."""
    i = tr.tramo(t0, t1)
    if len(i) < 3:
        return []
    twd = viento.twd_en(tr.ts[i])
    s = lado(tr, i, twd, viento.ceñida)
    ok = ~np.isnan(s) & (tr.sog[i] > 1.5)
    idx, sg = i[ok], s[ok]
    out = []
    j = 0
    while j < len(idx) - 1:
        if sg[j + 1] != sg[j]:
            # ¿se mantiene la nueva amura al menos MANIOBRA_MIN_MS?
            k = j + 1
            while k < len(idx) and sg[k] == sg[j + 1]:
                k += 1
            if tr.ts[idx[k - 1]] - tr.ts[idx[j + 1]] >= MANIOBRA_MIN_MS or k == len(idx):
                tm = int((tr.ts[idx[j]] + tr.ts[idx[j + 1]]) / 2)
                if tm - t0 > margen_ini_ms and t1 - tm > MARGEN_RODEO_MS:
                    out.append(Maniobra(tm, "virada" if viento.ceñida else "trasluchada",
                                        perdida(tr, tm, viento), float(tr.x[idx[j]]), float(tr.y[idx[j]])))
            j = k - 1 if k - 1 > j else j + 1
        else:
            j += 1
    return out


def perdida(tr: Traza, tm: int, viento: VientoTramo) -> float | None:
    """Metros perdidos en una maniobra. Referencia = VMG media de antes (−30…−10 s) y de después
    (+20…+30 s); pérdida = lo que se habría avanzado a esa VMG entre −10 y +20 s menos lo que se
    avanzó de verdad. Usar también el «después» evita culpar a la maniobra de un cambio de
    presión. Solo si no hay huecos de más de 4 s en −30…+30 s."""
    a, b = tm - VENTANA_ANTES_S * 1000, tm + VENTANA_DESPUES_S * 1000
    i = tr.tramo(a, b)
    if len(i) < 10 or np.any(np.diff(tr.ts[i]) > HUECO_MANIOBRA_MS) or tr.ts[i[0]] - a > 3000 or b - tr.ts[i[-1]] > 3000:
        return None
    twd = viento.twd_en(tr.ts[i])
    v = vmg(tr, i, twd, viento.ceñida)
    t = (tr.ts[i] - tm) / 1000
    antes, despues = t < -10, t > 20
    if antes.sum() < 3 or despues.sum() < 3 or np.isnan(v[antes]).all() or np.isnan(v[despues]).all():
        return None
    base = (float(np.nanmean(v[antes])) + float(np.nanmean(v[despues]))) / 2
    ventana = (t >= -10) & (t <= 20)
    tv, vv = t[ventana], np.nan_to_num(v[ventana], nan=base)
    if len(tv) < 2:
        return None
    avance = float(np.sum((vv[1:] + vv[:-1]) / 2 * np.diff(tv))) * KN
    esperado = base * KN * (tv[-1] - tv[0])
    return round(max(0.0, esperado - avance), 1)


def media_temporal(v: np.ndarray, ts: np.ndarray) -> float | None:
    """Media ponderada por tiempo (cada muestra pesa su intervalo, como máximo 5 s)."""
    if len(v) < 2:
        return None
    w = np.minimum(np.diff(ts, append=ts[-1]), HUECO_MS).astype(float)
    ok = ~np.isnan(v)
    if not ok.any() or w[ok].sum() == 0:
        return None
    return float(np.sum(v[ok] * w[ok]) / w[ok].sum())


def offset_escora(tr: Traza, periodos: list[tuple[int, int, VientoTramo]]) -> float:
    """Desviación fija del sensor: media de la escora mediana en cada amura en ceñida (una
    instalación perfecta escora lo mismo a las dos bandas). 0 si no hay datos de las dos amuras."""
    babor, estribor = [], []
    for t0, t1, vt in periodos:
        if not vt.ceñida:
            continue
        i = tr.tramo(t0, t1)
        if len(i) < 5:
            continue
        s = lado(tr, i, vt.twd_en(tr.ts[i]), True)
        babor.append(tr.roll[i][s > 0]); estribor.append(tr.roll[i][s < 0])
    b, e = np.concatenate(babor) if babor else [], np.concatenate(estribor) if estribor else []
    if len(b) < 60 or len(e) < 60:
        return 0.0
    return float((np.median(b) + np.median(e)) / 2)


def layline(tr: Traza, t0: int, t1: int, marca_xy, viento: VientoTramo, twa_flota: float,
            ultima_maniobra: Maniobra | None) -> dict:
    """Sobrepaso de la layline en la aproximación final a la baliza.
    Las laylines sobre el fondo son las rectas que llegan a la baliza con los rumbos que la flota
    navega en cada amura en ese momento (incluyen la corriente, que las hace asimétricas); si no
    hay rumbos por amura, TWD ± TWA de la flota. Desde la última maniobra antes de la baliza (o el
    inicio del tramo), el barco está fuera si la demora a la baliza queda fuera del cono entre las
    dos amuras: para llegar tendría que abrir (ceñida) o subir (popa) respecto a su amura. El exceso
    es la distancia en perpendicular a la layline de esa amura."""
    if marca_xy is None or twa_flota is None:
        return {"estado": None, "lado": None, "metros": None, "segundos": None}
    mx, my = marca_xy
    rumbos = viento.rumbos_en(t1 - 60_000)
    if rumbos is None:
        twd = float(viento.twd_en(t1 - 60_000))
        eje = twd if viento.ceñida else (twd + 180) % 360
        a = twa_flota if viento.ceñida else 180 - twa_flota
        rumbos = ((eje - a) % 360, (eje + a) % 360)
    k1, k2 = rumbos
    centro = (k1 + ((k2 - k1 + 540) % 360 - 180) / 2) % 360        # dirección del avance (bisectriz)
    semi = abs((k2 - k1 + 540) % 360 - 180) / 2
    if ultima_maniobra is not None:
        px, py, tp = ultima_maniobra.x, ultima_maniobra.y, ultima_maniobra.t
    else:
        xy = tr.en(t0, hueco_ms=60_000)
        if xy is None:
            return {"estado": None, "lado": None, "metros": None, "segundos": None}
        (px, py), tp = xy, t0

    def fuera(dx, dy):
        """Grados fuera del cono (+ = por la derecha de la amura derecha, − = por la izquierda) y distancia."""
        dem = np.degrees(np.arctan2(dx, dy)) % 360
        rel = (dem - centro + 540) % 360 - 180
        return np.where(rel > semi, rel - semi, np.where(rel < -semi, rel + semi, 0.0)), np.hypot(dx, dy)

    exceso, dist = fuera(np.array([mx - px]), np.array([my - py]))
    exceso, dist = float(exceso[0]), float(dist[0])
    if exceso == 0.0 or dist == 0.0:
        return {"estado": "OK", "lado": None, "metros": 0.0, "segundos": 0}
    # Lado del campo mirando hacia donde se navega: si la baliza queda a la derecha de la amura
    # derecha, el barco está a la izquierda (como Track to Tactics y como se nombran las puertas).
    lado_campo = "IZQUIERDA" if exceso > 0 else "DERECHA"
    metros = dist * math.sin(math.radians(abs(exceso)))
    # segundos navegados fuera del cono entre la maniobra y la baliza
    i = tr.tramo(tp, t1)
    seg = 0
    if len(i) > 1:
        e, _ = fuera(mx - tr.x[i], my - tr.y[i])
        seg = int(np.sum(np.minimum(np.diff(tr.ts[i]), HUECO_MS)[(e != 0)[:-1]]) / 1000)
    return {"estado": "SOBREPASADA", "lado": lado_campo, "metros": round(metros, 1), "segundos": seg,
            "_cono": (centro, semi), "_tp": tp}


def modo(twa: float | None, sog: float | None, med_twa: float, med_sog: float, ceñida: bool) -> str | None:
    """Modo frente a la mediana de la flota en el tramo."""
    if twa is None or sog is None:
        return None
    if ceñida:
        if twa < med_twa - 1.5 and sog < med_sog:
            return "ALTURA"
        if twa > med_twa + 1.5 and sog > med_sog:
            return "VELOCIDAD"
        return "VMG"
    if twa > med_twa + 3 and sog < med_sog:
        return "PROFUNDO"
    if twa < med_twa - 3 and sog > med_sog:
        return "VELOCIDAD"
    return "VMG"


def fantasma(largo_m: float, viento: VientoTramo, eje_tramo: float, twa_flota: float | None) -> float | None:
    """Distancia del barco fantasma: recorre el tramo con el ángulo de la flota y siempre en la
    amura favorecida por la rolada de cada corte. En el corte k avanza largo/10 a lo largo del eje
    y navega (largo/10) / cos(α − |δk|), con δk = TWD del corte − rumbo del eje (en popa, con la
    dirección del viento + 180)."""
    if not twa_flota or not largo_m:
        return None
    alpha = twa_flota if viento.ceñida else 180 - twa_flota
    total = 0.0
    for c in viento.cortes:
        ref = c.twd if viento.ceñida else (c.twd + 180) % 360
        delta = min(abs(float(dif(ref - eje_tramo))), alpha - 1)
        total += (largo_m / len(viento.cortes)) / math.cos(math.radians(alpha - delta))
    return round(total, 1)


def rumbo_tramo(ini_xy, fin_xy) -> float:
    return float(rumbo(fin_xy[0] - ini_xy[0], fin_xy[1] - ini_xy[1]))
