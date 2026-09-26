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
HUECO_MANIOBRA_MS = 6000


@dataclass
class Maniobra:
    t: int
    tipo: str                 # 'virada' | 'trasluchada'
    perdida_m: float | None   # None si hay huecos en la ventana
    x: float
    y: float
    detalle: dict | None = None   # fases de la maniobra (analizar_maniobra)


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
                                        None, float(tr.x[idx[j]]), float(tr.y[idx[j]])))
            j = k - 1 if k - 1 > j else j + 1
        else:
            j += 1
    objetivo = twa_objetivo(tr, t0, t1, viento, [m.t for m in out])
    for k, m in enumerate(out):   # con la siguiente maniobra ya conocida (encadenadas)
        m.detalle = analizar_maniobra(tr, m.t, viento, out[k + 1].t if k + 1 < len(out) else t1, objetivo)
        m.perdida_m = m.detalle["perdida_m"] if m.detalle else None
    return out


# Fases de una maniobra (ver docs/metricas.md, «Maniobras»)
GIRO_UMBRAL_DEG = 6.0          # el giro empieza/acaba al separarse/llegar a menos de esto del rumbo estable
ENTRADA_S = (-25, -8)          # rumbo, SOG y VMG de entrada (antes de que empiece a girar)
ESTABLE_S = (25, 45)           # rumbo, SOG y VMG estables en la nueva amura (tras el giro)
RECUPERADO_FRAC = 0.95         # acelerado: SOG ≥ 95 % de la estable de salida…
RECUPERADO_S = 4               # …durante 4 s
MAX_RECUPERACION_S = 60
GIRO_MAX_DEG = 115             # más giro: viró y cambió de rumbo (p. ej. arribó a un través)
CAMBIO_MODO = 0.6              # VMG de una amura < 60 % de la de la otra: no es una maniobra limpia


SALIDA_S = 10                  # ángulo de salida: TWA media de los 10 s siguientes al giro
SALIDA_TOLERANCIA_DEG = 3.0    # a menos de esto del objetivo, la salida es correcta
FRANJA_TWA_DEG = 2.0
FRANJA_MIN_S = 30


def twa_objetivo(tr: Traza, t0: int, t1: int, viento: VientoTramo, maniobras_t: list[int]) -> float | None:
    """TWA con la que el barco saca más VMG en el tramo: franjas de 2° de TWA (navegando estable, lejos
    de maniobras y rodeos), la de mayor VMG media con al menos 30 s de datos."""
    i = tr.tramo(t0 + MARGEN_RODEO_MS, t1 - MARGEN_RODEO_MS)
    if len(i) < 20:
        return None
    ok = ~np.isnan(tr.cog[i]) & (tr.sog[i] > viento.sog_min)
    for tm in maniobras_t:
        ok &= np.abs(tr.ts[i] - tm) > 45_000
    i = i[ok]
    if len(i) < 20:
        return None
    twd = viento.twd_en(tr.ts[i])
    twa = np.abs(dif(tr.cog[i] - twd))
    v = vmg(tr, i, twd, viento.ceñida)
    w = np.minimum(np.diff(tr.ts[i], append=tr.ts[i][-1]), HUECO_MS) / 1000
    franja = np.floor(twa / FRANJA_TWA_DEG)
    mejor, mejor_v = None, -np.inf
    for f in np.unique(franja):
        m = franja == f
        if w[m].sum() < FRANJA_MIN_S:
            continue
        vm = float(np.sum(v[m] * w[m]) / w[m].sum())
        if vm > mejor_v:
            mejor, mejor_v = (f + 0.5) * FRANJA_TWA_DEG, vm
    return mejor


def _rumbo_medio(v):
    r = np.radians(v[~np.isnan(v)])
    return float(np.degrees(np.arctan2(np.sin(r).mean(), np.cos(r).mean())) % 360) if len(r) else None


def analizar_maniobra(tr: Traza, tm: int, viento: VientoTramo, siguiente: int | None = None,
                      objetivo_twa: float | None = None) -> dict | None:
    """Fases de una virada o trasluchada y metros perdidos.

    - Entrada (−25…−8 s): rumbo, SOG y VMG estables en la amura de partida.
    - Giro: desde que el rumbo (proa; COG si no hay) se separa más de 6° del de entrada hasta que
      llega a menos de 6° del rumbo estable de la nueva amura (+25…+45 s tras el centro del giro).
    - Aceleración: desde el final del giro hasta que la SOG vuelve al 95 % de la estable de salida
      durante 4 s (como mucho 60 s).
    - Pérdida = lo que se habría avanzado sin maniobrar desde el inicio del giro hasta estar
      acelerado, menos lo que se avanzó. Sin maniobrar = hasta la mitad del giro, a la VMG de
      entrada; desde ahí, a la VMG estable de la nueva amura. Así una rolada o un cambio de presión
      (una amura mejor que la otra) no se carga a la maniobra, sino a la amura.
    - Ángulo de salida: TWA media en los 10 s siguientes al giro frente a la TWA con la que el barco
      saca más VMG en el tramo (twa_objetivo). Recién salido de la maniobra todos abaten y arriban
      para acelerar, así que la referencia es cómo sale el top 5 (ver `valorar_salidas`).
    Si la maniobra siguiente llega antes de estabilizar, la referencia es solo la de entrada
    («encadenada»). None si hay huecos de más de 4 s o faltan datos."""
    fin_max = tm + (ESTABLE_S[1] + 5) * 1000
    if siguiente is not None:
        fin_max = min(fin_max, siguiente - 5_000)
    a = tm + ENTRADA_S[0] * 1000 - 2_000
    i = tr.tramo(a, max(fin_max, tm + 15_000))
    if len(i) < 10:
        return None
    ts = tr.ts[i]
    if np.any(np.diff(ts) > HUECO_MANIOBRA_MS) or ts[0] - a > 3000:
        return None
    t = (ts - tm) / 1000
    rumbo = np.where(np.isnan(tr.hdg[i]), tr.cog[i], tr.hdg[i])
    twd = viento.twd_en(ts)
    v = vmg(tr, i, twd, viento.ceñida)
    sog = tr.sog[i]
    ent = (t >= ENTRADA_S[0]) & (t <= ENTRADA_S[1])
    est = (t >= ESTABLE_S[0]) & (t <= ESTABLE_S[1]) & (ts <= fin_max)
    encadenada = est.sum() < 5
    if ent.sum() < 5:
        return None
    r_ent = _rumbo_medio(rumbo[ent])
    if encadenada:   # rumbo de la nueva amura: los últimos segundos disponibles
        cola = (t > 10) & (ts <= fin_max)
        if cola.sum() < 3:
            return None
        r_sal = _rumbo_medio(rumbo[cola])
    else:
        r_sal = _rumbo_medio(rumbo[est])
    if r_ent is None or r_sal is None or abs(dif(r_sal - r_ent)) < 30:
        return None
    # inicio y fin del giro
    fuera = np.abs(dif(rumbo - r_ent)) > GIRO_UMBRAL_DEG
    cand = np.nonzero(fuera & (t > ENTRADA_S[1]) & (t < 10))[0]
    if not len(cand):
        return None
    k0 = cand[0]
    # fin del giro: llega a menos de 6° del rumbo de la nueva amura o lo pasa (sale más arribado/orzado)
    total = float(dif(r_sal - r_ent))
    avance = dif(rumbo - r_ent) * np.sign(total)
    llegado = np.nonzero((avance >= abs(total) - GIRO_UMBRAL_DEG) & (np.arange(len(t)) > k0))[0]
    if not len(llegado):
        return None
    k1 = llegado[0]
    vmg_ent, sog_ent = float(np.nanmedian(v[ent])), float(np.median(sog[ent]))
    if encadenada:
        vmg_est, sog_est = vmg_ent, sog_ent
    else:
        vmg_est, sog_est = float(np.nanmedian(v[est])), float(np.median(sog[est]))
    ref = (vmg_ent + vmg_est) / 2
    if not np.isfinite(ref) or min(vmg_ent, vmg_est) <= 0.3:
        return None
    # No es una maniobra limpia (virar y arribar a un través, rodeo, maniobra de salida…): no se mide
    if abs(total) > GIRO_MAX_DEG or min(vmg_ent, vmg_est) < CAMBIO_MODO * max(vmg_ent, vmg_est):
        return None
    # acelerado: SOG ≥ 95 % de la estable durante 4 s
    objetivo = RECUPERADO_FRAC * sog_est
    k2 = None
    for k in range(k1, len(t)):
        if t[k] - t[k1] > MAX_RECUPERACION_S:
            break
        m = (t >= t[k]) & (t <= t[k] + RECUPERADO_S)
        if m.sum() >= 2 and t[m][-1] - t[k] >= RECUPERADO_S - 1 and np.all(sog[m] >= objetivo):
            k2 = k
            break
    completa = k2 is not None
    if k2 is None:
        k2 = len(t) - 1
    tramo_ = slice(k0, k2 + 1)
    tv, vv = t[tramo_], np.nan_to_num(v[tramo_], nan=ref)
    if len(tv) < 2:
        return None
    avance = float(np.sum((vv[1:] + vv[:-1]) / 2 * np.diff(tv))) * KN
    medio = (t[k0] + t[k1]) / 2
    esperado = (vmg_ent * (medio - tv[0]) + vmg_est * (tv[-1] - medio)) * KN
    perdida_m = max(0.0, esperado - avance)
    sal = (t >= t[k1]) & (t <= t[k1] + SALIDA_S)
    twa_sal = float(np.nanmedian(np.abs(dif(tr.cog[i][sal] - twd[sal])))) if sal.sum() >= 3 else None
    frente = round(twa_sal - objetivo_twa, 1) if twa_sal is not None and objetivo_twa is not None else None
    sog_min = float(np.min(sog[k0:k2 + 1]))
    return {
        "perdida_m": round(float(perdida_m), 1),
        "perdida_s": round(float(perdida_m / (ref * KN)), 1),                     # segundos a la VMG de referencia
        "duracion_giro_s": round(float(t[k1] - t[k0]), 1),
        "tiempo_aceleracion_s": round(float(t[k2] - t[k1]), 1) if completa else None,
        "sog_entrada_kn": round(sog_ent, 2), "sog_minima_kn": round(sog_min, 2),
        "sog_salida_estable_kn": round(sog_est, 2),
        "caida_sog_pct": round((1 - sog_min / sog_ent) * 100) if sog_ent > 0 else None,
        "vmg_entrada_kn": round(vmg_ent, 2), "vmg_salida_estable_kn": round(vmg_est, 2),
        "angulo_girado_grados": round(abs(float(dif(r_sal - r_ent)))),
        "twa_salida_grados": None if twa_sal is None else round(twa_sal, 1),
        "twa_objetivo_grados": None if objetivo_twa is None else round(objetivo_twa, 1),
        "salida_frente_al_objetivo_grados": frente,   # + = más abierta en ceñida / más profunda en popa
        "encadenada": bool(encadenada), "acelerado": bool(completa),
    }


def valorar_salidas(maniobras: dict[str, list[Maniobra]], referencia: list[str]) -> dict:
    """Ángulo de salida frente al del top 5 (mediana de sus salidas respecto a su propia TWA objetivo).
    En ceñida, más cerrada que el top 5 tarda más en acelerar y más abierta pierde altura; en popa al
    revés: más profunda tarda en acelerar y más alta pierde profundidad. Devuelve la referencia."""
    ref_d = [m.detalle["salida_frente_al_objetivo_grados"] for v in referencia for m in maniobras.get(v, [])
             if m.detalle and m.detalle.get("salida_frente_al_objetivo_grados") is not None]
    con_datos = {v for v in referencia for m in maniobras.get(v, []) if m.detalle}
    quien = "el top 5"
    if len(ref_d) < 4 or len(con_datos) < 3:
        # Sin flota (sesiones .vkx): frente a la salida habitual del barco en esta prueba
        ref_d = [m.detalle["salida_frente_al_objetivo_grados"] for ms in maniobras.values() for m in ms
                 if m.detalle and m.detalle.get("salida_frente_al_objetivo_grados") is not None]
        if len(ref_d) < 4 or len(maniobras) >= 3:
            return {}
        quien, referencia = "su salida habitual", list(maniobras)
    ref = float(np.median(ref_d))
    ref5 = {k: [m.detalle[k] for v in referencia for m in maniobras.get(v, []) if m.detalle and m.detalle.get(k) is not None]
            for k in ("perdida_s", "duracion_giro_s", "tiempo_aceleracion_s", "caida_sog_pct")}
    for ms in maniobras.values():
        for m in ms:
            d = (m.detalle or {}).get("salida_frente_al_objetivo_grados")
            if d is None:
                continue
            x = round(d - ref, 1)
            m.detalle["salida_frente_al_top5_grados"] = x
            ceñida = m.tipo == "virada"
            if abs(x) <= SALIDA_TOLERANCIA_DEG:
                m.detalle["salida"] = f"como {quien}"
            elif ceñida:
                m.detalle["salida"] = (f"más cerrada (alta) que {quien}: tarda más en acelerar" if x < 0
                                       else f"más abierta (baja) que {quien}: pierde altura")
            else:
                m.detalle["salida"] = (f"más profunda que {quien}: tarda más en acelerar" if x > 0
                                       else f"más alta que {quien}: pierde profundidad")
    return {"referencia": quien, "salida_top5_frente_al_objetivo_grados": round(ref, 1), "maniobras_top5": len(ref_d),
            **{f"{k}_top5": round(float(np.median(v)), 1) for k, v in ref5.items() if v}}


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
    """Distancia del barco fantasma: recorre el tramo siempre en la amura favorecida por la rolada
    de cada corte. En el corte k avanza largo/10 a lo largo del eje y navega (largo/10) / cos(a),
    con a = ángulo con el eje del rumbo sobre el fondo de la amura favorecida (el de la flota en ese
    corte, que incluye la corriente). Sin rumbos por amura: a = α − |δk|, con α el ángulo de la flota
    y δk = TWD del corte − rumbo del eje (en popa, con la dirección del viento + 180)."""
    if not twa_flota or not largo_m:
        return None
    alpha = twa_flota if viento.ceñida else 180 - twa_flota
    total = 0.0
    for c in viento.cortes:
        if c.rumbos is not None:
            # rumbos sobre el fondo de las dos amuras (con la corriente, como las laylines): el fantasma
            # navega en la que forma menos ángulo con el eje del tramo
            a = min(abs(float(dif(c.rumbos[0] - eje_tramo))), abs(float(dif(c.rumbos[1] - eje_tramo))))
            a = min(a, 89.0)
        else:
            ref = c.twd if viento.ceñida else (c.twd + 180) % 360
            a = alpha - min(abs(float(dif(ref - eje_tramo))), alpha - 1)
        total += (largo_m / len(viento.cortes)) / math.cos(math.radians(a))
    return round(total, 1)


def rumbo_tramo(ini_xy, fin_xy) -> float:
    return float(rumbo(fin_xy[0] - ini_xy[0], fin_xy[1] - ini_xy[1]))
