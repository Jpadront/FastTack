"""Táctica en un tramo (estimada: depende del viento reconstruido).

Amura favorecida: en cada instante, de las dos amuras (o bandas en popa) posibles con la TWD de ese
momento y el ángulo al viento del barco en el tramo, la que apunta más cerca de la baliza. Navegar en
la otra es navegar «en el rolón» (con la rolada en contra). Si la TWD está a menos de UMBRAL_GRADOS
de la dirección de la baliza, las dos amuras son iguales (neutro).

Viradas/trasluchadas: a favor si pasan de la amura desfavorecida a la favorecida (virar en el rolón),
en contra si pasan de la favorecida a la desfavorecida; neutras si no cambian nada (o sin datos).

Lado del campo: distancia lateral a la recta entre la baliza de salida del tramo y la de llegada,
mirando a barlovento (en popa también, para hablar del mismo lado del campo).
"""
from __future__ import annotations

import numpy as np

from . import roles
from .geo import a_ejes, dif
from .trazas import Traza

UMBRAL_GRADOS = 3.0
MARGEN_RODEO_MS = 20_000
MARGEN_MANIOBRA_MS = 10_000
VENTANA_MANIOBRA_MS = 40_000
CENTRO_M = 50.0
ROLON_MIN_MS = 20_000        # en la amura desfavorecida al menos 20 s seguidos = ha entrado un rolón
HUECO_ROLON_MS = 15_000      # huecos (maniobras, datos) que no cortan un rolón


def tramo(tr: Traza, e: int, s: int, vt, ceñida: bool, marca, p_ini, eje: float, maniobras: list,
          viento_local=None) -> dict | None:
    """viento_local: (ts, TWD) del viento en el sitio del barco (roles.viento_local); sin él, la TWD
    de los cortes, igual en todo el campo."""
    i = tr.tramo(e + MARGEN_RODEO_MS, s - MARGEN_RODEO_MS)
    if len(i) < 10:
        return None
    ok = ~np.isnan(tr.cog[i]) & (tr.sog[i] > vt.sog_min)
    for m in maniobras:
        ok &= np.abs(tr.ts[i] - m.t) > MARGEN_MANIOBRA_MS
    i = i[ok]
    if len(i) < 10:
        return None
    twd = roles.twd_en(viento_local, tr.ts[i], vt)
    ref = twd if ceñida else (twd + 180) % 360            # dirección a la que se avanza con viento cuadrado
    rel = dif(tr.cog[i] - ref)
    off = float(np.median(np.abs(rel)))                    # medio ángulo entre amuras del barco
    if marca is not None:
        rumbo_baliza = np.degrees(np.arctan2(marca[0] - tr.x[i], marca[1] - tr.y[i])) % 360
    else:
        rumbo_baliza = np.full(len(i), eje)
    d_mas = np.abs(dif(ref + off - rumbo_baliza))
    d_menos = np.abs(dif(ref - off - rumbo_baliza))
    signo_fav = np.where(d_mas < d_menos, 1.0, -1.0)
    neutro = np.abs(dif(ref - rumbo_baliza)) < UMBRAL_GRADOS
    en_fav = np.sign(rel) == signo_fav
    dt = np.diff(tr.ts[i], append=tr.ts[i][-1]) / 1000
    dt = np.minimum(dt, 5.0)                               # sin contar huecos
    util = ~neutro
    t_util = float(dt[util].sum())
    fav_pct = float(dt[util & en_fav].sum() / t_util * 100) if t_util > 0 else None

    def estado(a, b):
        m = (tr.ts[i] >= a) & (tr.ts[i] <= b) & util
        return None if m.sum() < 3 else bool(en_fav[m].mean() > 0.5)

    a_favor = en_contra = neutras = 0
    for m in maniobras:
        antes = estado(m.t - VENTANA_MANIOBRA_MS, m.t - MARGEN_MANIOBRA_MS)
        despues = estado(m.t + MARGEN_MANIOBRA_MS, m.t + VENTANA_MANIOBRA_MS)
        if antes is False and despues is True:
            a_favor += 1
        elif antes is True and despues is False:
            en_contra += 1
        else:
            neutras += 1
    # Reacción a los rolones: cuando el barco queda en la amura desfavorecida al menos ROLON_MIN_MS
    # seguidos, cuánto tarda en virar (o trasluchar). Sin maniobra antes del final del tramo: sin responder.
    t_ok = tr.ts[i][util]
    malo = ~en_fav[util]
    rolones, respuestas, sin_resp = 0, [], 0
    k = 0
    mts = sorted(m.t for m in maniobras)
    while k < len(t_ok):
        if not malo[k]:
            k += 1
            continue
        j = k
        while j + 1 < len(t_ok) and malo[j + 1] and t_ok[j + 1] - t_ok[j] <= HUECO_ROLON_MS:
            j += 1
        if t_ok[j] - t_ok[k] >= ROLON_MIN_MS:
            rolones += 1
            sig = next((m for m in mts if m >= t_ok[k]), None)
            if sig is not None and sig <= t_ok[j] + VENTANA_MANIOBRA_MS:
                respuestas.append((sig - t_ok[k]) / 1000)
            else:
                sin_resp += 1
        k = j + 1
    out = {"amura_favorecida_pct": None if fav_pct is None else round(fav_pct, 0),
           "rolones": rolones, "rolones_sin_responder": sin_resp,
           "respuesta_a_rolones_mediana_s": round(float(np.median(respuestas))) if respuestas else None,
           "viento": "local" if viento_local else "cortes",
           "tiempo_en_amura_desfavorecida_s": round(float(dt[util & ~en_fav].sum())),
           "tiempo_neutro_pct": round(float(dt[neutro].sum() / dt.sum() * 100), 0) if dt.sum() > 0 else None,
           "maniobras_a_favor_de_la_rolada": a_favor, "maniobras_en_contra_de_la_rolada": en_contra,
           "maniobras_neutras": neutras}
    if p_ini is not None:
        _, lat = a_ejes(tr.x[i] - p_ini[0], tr.y[i] - p_ini[1], eje)
        lat = lat if ceñida else -lat                      # + = derecha mirando a barlovento
        med = float(np.median(lat))
        out |= {"derecha_pct": round(float(dt[lat > 0].sum() / dt.sum() * 100), 0) if dt.sum() > 0 else None,
                "separacion_maxima_m": round(float(np.max(np.abs(lat)))),
                "lado": "derecha" if med > CENTRO_M else "izquierda" if med < -CENTRO_M else "centro"}
    return out
