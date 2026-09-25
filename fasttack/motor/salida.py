"""Análisis de la salida (fórmulas en docs/metricas.md)."""
from __future__ import annotations

import math

import numpy as np

from .geo import a_ejes, dif, rumbo
from .pistas import Pista
from .tramos import Maniobra, media_temporal, vmg
from .trazas import Traza
from .viento import VientoTramo


def _linea(pin: Pista, comite: Pista, t: int):
    px, py = pin.en(np.array([t]))
    cx, cy = comite.en(np.array([t]))
    return (float(px[0]), float(py[0])), (float(cx[0]), float(cy[0]))


def sesgo(pin_xy, com_xy, twd: float) -> dict:
    """Extremo favorecido: el que está más a barlovento. Grados = desviación entre la
    perpendicular a la línea y la TWD; metros = ventaja a barlovento del extremo favorecido."""
    ventaja_pin = float(a_ejes(pin_xy[0] - com_xy[0], pin_xy[1] - com_xy[1], twd)[0])
    largo = math.hypot(pin_xy[0] - com_xy[0], pin_xy[1] - com_xy[1])
    grados = math.degrees(math.asin(min(1.0, abs(ventaja_pin) / largo))) if largo else 0.0
    return {"extremo": "PIN" if ventaja_pin > 0 else "COMITÉ", "grados": round(grados, 1),
            "metros": round(abs(ventaja_pin), 1), "largo_linea_m": round(largo, 1)}


def analizar(trazas: dict[str, Traza], pin: Pista, comite: Pista, senal: int, eje: float,
             viento1: VientoTramo, b1_xy, pasos_b1: dict[str, int], maniobras: dict[str, list[Maniobra]],
             ocs: list[str], ocs_fiable: bool) -> dict:
    pin_xy, com_xy = _linea(pin, comite, senal)
    cp = np.array([pin_xy[0] - com_xy[0], pin_xy[1] - com_xy[1]])
    largo2 = float(cp @ cp) or 1.0
    # normal unitaria hacia el lado del recorrido
    n = np.array([cp[1], -cp[0]]) / math.sqrt(largo2)
    ux, uy = math.sin(math.radians(eje)), math.cos(math.radians(eje))
    if n @ np.array([ux, uy]) < 0:
        n = -n
    twd = float(viento1.twd_en(senal))

    def firmada(x, y):  # distancia a la línea, + en el lado del recorrido
        return (np.asarray(x) - com_xy[0]) * n[0] + (np.asarray(y) - com_xy[1]) * n[1]

    barcos = {}
    for v, tr in trazas.items():
        xy = tr.en(senal)
        fila = {"posicion_linea_pct": None, "margen_m": None, "sog_disparo": None, "cruce_s": None,
                "vmg_0_90": None, "pos_60": None, "dist_60": None, "pos_180": None, "dist_180": None,
                "primera_virada_s": None, "pos_b1": None, "gap_b1_s": None,
                "ocs": "COMITÉ" if v in ocs else "NO"}
        if xy is not None:
            b = np.array(xy) - np.array(com_xy)
            fila["posicion_linea_pct"] = round(float(b @ cp) / largo2 * 100, 1)
            fila["margen_m"] = round(float(firmada(*xy)), 1)
            fila["sog_disparo"] = round(tr.en(senal, "sog"), 2)
            fila["sobre_linea_gps"] = fila["margen_m"] > 0  # en el lado del recorrido en el disparo
        # Cruce de la línea: primer paso del lado de salida al del recorrido desde 30 s antes
        i = tr.tramo(senal - 30_000, senal + 180_000)
        if len(i) > 1:
            d = firmada(tr.x[i], tr.y[i])
            k = np.nonzero((d[:-1] <= 0) & (d[1:] > 0) & (np.diff(tr.ts[i]) <= 5000))[0]
            k = [j for j in k if tr.ts[i[j + 1]] >= senal] or list(k)
            if k:
                j = k[0]
                f = -d[j] / (d[j + 1] - d[j])
                fila["cruce_s"] = round((tr.ts[i[j]] + f * (tr.ts[i[j + 1]] - tr.ts[i[j]]) - senal) / 1000, 1)
        i = tr.tramo(senal, senal + 90_000)
        if len(i) > 5 and tr.cobertura(senal, senal + 90_000) > 0.6:
            m = media_temporal(vmg(tr, i, viento1.twd_en(tr.ts[i]), True), tr.ts[i])
            fila["vmg_0_90"] = round(m, 2) if m is not None else None
        man = maniobras.get(v) or []
        if man:
            fila["primera_virada_s"] = round((man[0].t - senal) / 1000)
        barcos[v] = fila

    # Barcos que salen: en la señal a menos de 300 m de la línea, o que la cruzan en 3 min.
    # (En Cascais Vela R9 había barcos a 1 km, sin correr, que salían «primeros» a +60 s.)
    salen = {v for v, f in barcos.items()
             if (f["margen_m"] is not None and abs(f["margen_m"]) < 300) or f["cruce_s"] is not None}
    for v, f in barcos.items():
        f["en_salida"] = v in salen

    # Posición y distancia al primero a +60 y +180 s: avance hacia la baliza 1 a lo largo del eje
    for seg in (60, 180):
        dist = {}
        for v, tr in trazas.items():
            if v not in salen:
                continue
            xy = tr.en(senal + seg * 1000)
            if xy is not None and b1_xy is not None:
                dist[v] = float(a_ejes(b1_xy[0] - xy[0], b1_xy[1] - xy[1], eje)[0])
        orden = sorted(dist, key=dist.get)
        for k, v in enumerate(orden, 1):
            barcos[v][f"pos_{seg}"] = k
            barcos[v][f"dist_{seg}"] = round(dist[v] - dist[orden[0]], 1)
    orden = sorted(pasos_b1, key=pasos_b1.get)
    for k, v in enumerate(orden, 1):
        if v in barcos:
            barcos[v]["pos_b1"] = k
            barcos[v]["gap_b1_s"] = round((pasos_b1[v] - pasos_b1[orden[0]]) / 1000)
    return {
        "comite": {"xy": com_xy}, "pin": {"xy": pin_xy},
        "sesgo": sesgo(pin_xy, com_xy, twd),
        "twd_disparo": round(twd, 1),
        "rumbo_linea": round(float(rumbo(cp[0], cp[1])), 1),
        "barcos": barcos,
    }
