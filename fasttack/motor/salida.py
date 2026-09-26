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


# Posicionamiento en la salida (estimado; distancias en esloras de la clase)
SUCIO_ESLORAS = 6            # la sombra de viento de un barco llega hasta ~6 esloras
SUCIO_GRADOS = 15            # y abarca ±15° alrededor del viento aparente
AWA_GIRO = 15                # el viento aparente en ceñida viene ~15° más a proa que el real
HUECO_LIBRE_ESLORAS = 6
PRIMERA_FILA_ESLORAS = 2
PASO_S = 2
SEGURO_LADO_ESLORAS, SEGURO_DELANTE_ESLORAS = 1.5, 2.0


def _estado(tr: Traza, t: int):
    """(x, y, cog, sog) en t; None si hay hueco."""
    xy = tr.en(t)
    if xy is None:
        return None
    j = int(np.clip(np.searchsorted(tr.ts, t), 0, len(tr.ts) - 1))
    c = tr.cog[j]
    return (xy[0], xy[1], None if np.isnan(c) else float(c), tr.en(t, "sog"))


def posicionamiento(trazas: dict[str, Traza], salen: set, senal: int, twd: float, firmada, eslora: float) -> dict:
    """Para cada barco que sale: cómo llegó a la línea, qué barcos tenía al lado en la señal y si
    navegó en aire sucio (o con un barco a sotavento en posición segura) los primeros 90 s.

    - Lados: a sotavento/barlovento según la amura del barco en cada momento. «Delante» = a lo largo
      de su rumbo.
    - Aire sucio: otro barco a ≤ 6 esloras en la dirección de la que le llega el viento aparente
      (TWD girada 15° hacia su proa, ±15°).
    - Sotavento en posición segura: un barco a sotavento a ≤ 1,5 esloras de lado y de 0 a 2 esloras delante,
      que le quita el viento limpio al arribar (no le deja navegar más abierto para acelerar)."""
    velas = [v for v in trazas if v in salen]
    tiempos = list(range(senal - 30_000, senal + 90_001, PASO_S * 1000))
    est = {v: [_estado(trazas[v], t) for t in tiempos] for v in velas}
    k0 = tiempos.index(senal)
    out = {}
    for v in velas:
        sucio, seguro, total, culpables = 0, 0, 0, {}
        vecinos = {"sotavento": None, "barlovento": None}
        for k in range(k0, len(tiempos)):
            a = est[v][k]
            if a is None or a[2] is None:
                continue
            ax, ay, ac, _ = a
            lado = 1.0 if dif(ac - twd) > 0 else -1.0          # + = viento por babor
            awd = (twd + lado * AWA_GIRO) % 360               # de dónde le llega el viento aparente
            total += 1
            en_sucio = en_seguro = False
            for w in velas:
                if w == v or est[w][k] is None:
                    continue
                bx, by = est[w][k][0], est[w][k][1]
                dx, dy = bx - ax, by - ay
                d = math.hypot(dx, dy)
                if d > HUECO_LIBRE_ESLORAS * eslora or d < 1e-6:
                    continue
                marc = math.degrees(math.atan2(dx, dy)) % 360
                delante, costado = a_ejes(dx, dy, ac)          # costado + = a estribor
                a_sotavento = costado * lado > 0                # viento por babor → sotavento = estribor
                if d <= SUCIO_ESLORAS * eslora and abs(dif(marc - awd)) <= SUCIO_GRADOS:
                    en_sucio = True
                    culpables[w] = culpables.get(w, 0) + 1
                if a_sotavento and abs(costado) <= SEGURO_LADO_ESLORAS * eslora and 0 <= delante <= SEGURO_DELANTE_ESLORAS * eslora:
                    en_seguro = True
                if k == k0 and abs(delante) <= 1.5 * eslora:  # vecinos en la señal, a la par
                    lado_v = "sotavento" if a_sotavento else "barlovento"
                    if vecinos[lado_v] is None or abs(costado) < vecinos[lado_v][1]:
                        vecinos[lado_v] = (w, abs(costado))
            sucio += en_sucio
            seguro += en_seguro and k <= k0 + 60 // PASO_S
        # aproximación: distancia a la línea a −30 y −10 s, tiempo casi parado cerca de ella
        def margen(dt):
            e = est[v][tiempos.index(senal + dt * 1000)]
            return None if e is None else float(firmada(e[0], e[1]))
        cerca_lento = sum(1 for k in range(0, k0) if est[v][k] is not None and est[v][k][3] is not None
                          and abs(float(firmada(est[v][k][0], est[v][k][1]))) <= 2 * eslora)
        culpable = max(culpables, key=culpables.get) if culpables else None
        cul = None
        if culpable:
            a, b = est[v][k0], est[culpable][k0]
            if a is not None and b is not None and a[2] is not None:
                _, cst = a_ejes(b[0] - a[0], b[1] - a[1], a[2])
                lado = 1.0 if dif(a[2] - twd) > 0 else -1.0
                cul = "barlovento" if cst * lado < 0 else "sotavento"
        out[v] = {
            "margen_menos_30_m": None if margen(-30) is None else round(margen(-30), 1),
            "margen_menos_10_m": None if margen(-10) is None else round(margen(-10), 1),
            "s_cerca_de_la_linea_antes": cerca_lento * PASO_S,
            "hueco_sotavento_esloras": (None if vecinos["sotavento"] is None else round(vecinos["sotavento"][1] / eslora, 1)),
            "vecino_sotavento": vecinos["sotavento"][0] if vecinos["sotavento"] else None,
            "hueco_barlovento_esloras": (None if vecinos["barlovento"] is None else round(vecinos["barlovento"][1] / eslora, 1)),
            "vecino_barlovento": vecinos["barlovento"][0] if vecinos["barlovento"] else None,
            "aire_sucio_pct": round(sucio / total * 100) if total else None,
            "aire_sucio_de": culpable, "aire_sucio_lado": cul,
            "sotavento_seguro_pct": round(seguro / min(total, 60 // PASO_S + 1) * 100) if total else None,
        }
    return out


LINEA_DESDE_S, LINEA_HASTA_S = 10, 60   # viento en la línea: rumbos de los barcos de +10 a +60 s
MIN_BARCOS_ZONA = 3


def viento_en_la_linea(trazas: dict[str, Traza], barcos: dict, senal: int, twd: float, twa: float | None) -> list[dict] | None:
    """TWD y presión en cada tercio de la línea (comité, centro, pin) justo después de la salida.

    Casi todos salen en la misma amura, así que la bisectriz no sirve: con el ángulo al viento de la
    flota en la ceñida (TWA), cada muestra da su TWD = COG ± TWA según la amura (se descartan las que
    se apartan > 20° de ese ángulo: maniobrando o arribando). Cada barco va a la zona de la línea por
    la que salió; TWD de la zona = mediana de sus barcos; presión = SOG mediana."""
    if not twa:
        return None
    zonas = {"comité": [], "centro": [], "pin": []}
    for v, f in barcos.items():
        p = f.get("posicion_linea_pct")
        if not f.get("en_salida") or p is None or not 0 <= p <= 100:
            continue
        tr = trazas[v]
        i = tr.tramo(senal + LINEA_DESDE_S * 1000, senal + LINEA_HASTA_S * 1000)
        i = i[~np.isnan(tr.cog[i])]
        if len(i) < 5:
            continue
        rel = dif(tr.cog[i] - twd)
        ok = np.abs(np.abs(rel) - twa) <= 20
        if ok.sum() < 5:
            continue
        est = (tr.cog[i][ok] - np.sign(rel[ok]) * twa) % 360     # babor (rel +): TWD = COG − TWA
        r = np.radians(est)
        t_barco = float(np.degrees(np.arctan2(np.sin(r).mean(), np.cos(r).mean())) % 360)
        zona = "comité" if p < 100 / 3 else "centro" if p < 200 / 3 else "pin"
        zonas[zona].append((t_barco, float(np.median(tr.sog[i]))))
    if sum(len(z) for z in zonas.values()) < 2 * MIN_BARCOS_ZONA:
        return None
    out = []
    for nombre, xs in zonas.items():
        if len(xs) < MIN_BARCOS_ZONA:
            out.append({"zona": nombre, "barcos": len(xs), "twd": None, "sog": None})
            continue
        r = np.radians([x[0] for x in xs])
        t_z = float(np.degrees(np.arctan2(np.sin(r).mean(), np.cos(r).mean())) % 360)
        out.append({"zona": nombre, "barcos": len(xs), "twd": round(t_z, 1), "rolada": round(float(dif(t_z - twd)), 1),
                    "sog": round(float(np.median([x[1] for x in xs])), 2)})
    return out


def valorar(f: dict, ref_sog: float | None, eslora: float) -> dict:
    """Diagnóstico de la salida a partir de las cifras (sin interpretar más allá de ellas)."""
    diag = {}
    m, sog = f.get("margen_m"), f.get("sog_disparo")
    m10 = f.get("margen_menos_10_m")
    if f.get("sobre_linea_gps") or f.get("ocs") not in (None, "NO"):
        diag["llegada"] = "pasado: sobre la línea en la señal"
    elif m10 is not None and m10 > -eslora and sog is not None and ref_sog and sog < 0.7 * ref_sog:
        diag["llegada"] = "pronto: a menos de una eslora de la línea 10 s antes y lento en la señal (tuvo que frenar)"
    elif m is not None and m < -PRIMERA_FILA_ESLORAS * eslora and (f.get("cruce_s") or 0) > 5:
        diag["llegada"] = "tarde: lejos de la línea en la señal"
    elif m is not None:
        diag["llegada"] = "a tiempo"
    h = f.get("hueco_sotavento_esloras")
    diag["hueco_a_sotavento"] = ("libre (nadie a menos de 6 esloras a la par)" if h is None and f.get("en_salida")
                                 else "sin hueco" if h is not None and h < 1.5 else "justo" if h is not None and h < 3 else "suficiente" if h is not None else None)
    if (f.get("aire_sucio_pct") or 0) >= 30:
        diag["primeros_90_s"] = ("planchado por un barco a barlovento" if f.get("aire_sucio_lado") == "barlovento"
                                 else "en aire sucio de un barco a sotavento/delante")
    elif (f.get("sotavento_seguro_pct") or 0) >= 50:
        diag["primeros_90_s"] = "con un barco a sotavento en posición segura: no pudo arribar para acelerar"
    else:
        diag["primeros_90_s"] = "aire limpio"
    return diag


def analizar(trazas: dict[str, Traza], pin: Pista, comite: Pista, senal: int, eje: float,
             viento1: VientoTramo, b1_xy, pasos_b1: dict[str, int], maniobras: dict[str, list[Maniobra]],
             ocs: list[str], ocs_fiable: bool, eslora: float = 6.93) -> dict:
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

    # Posicionamiento: aproximación, vecinos en la señal y aire sucio los primeros 90 s
    pos = posicionamiento(trazas, salen, senal, twd, firmada, eslora)
    fila1 = [f["sog_disparo"] for f in barcos.values() if f.get("en_salida") and f["sog_disparo"] is not None
             and f["margen_m"] is not None and -PRIMERA_FILA_ESLORAS * eslora <= f["margen_m"] <= 0]
    ref_sog = float(np.median(fila1)) if len(fila1) >= 3 else None
    for v, p in pos.items():
        barcos[v].update(p)
        barcos[v]["diagnostico"] = valorar(barcos[v], ref_sog, eslora)
    twas = [c.twa_flota for c in viento1.cortes[:3] if c.twa_flota]
    en_linea = viento_en_la_linea(trazas, barcos, senal, twd, float(np.median(twas)) if twas else None)

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
        "sog_primera_fila": None if ref_sog is None else round(ref_sog, 2),
        "viento_en_la_linea": en_linea,
        "eslora_m": eslora,
        "barcos": barcos,
    }
