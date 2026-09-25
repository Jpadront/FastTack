"""Análisis completo de una prueba: de la telemetría al resultado que muestra la app.

Todo es determinista y reproducible: mismas entradas → mismo resultado. Cada cifra lleva su
naturaleza (directa, calculada o estimada) en docs/metricas.md, y las métricas de un tramo se
anulan (None) si la cobertura de la telemetría del barco en ese tramo no llega a COBERTURA_MIN.
"""
from __future__ import annotations

import math

import numpy as np

from .geo import a_ejes, dif, distancia, rumbo
from .pistas import Pista, Proyeccion, pistas
from . import recorrido as rec
from . import salida as sal
from . import corriente as corr
from . import escora as esc_mod
from . import tramos as tm
from .trazas import Traza, construir
from .viento import calibrar_tws, fases, quien_primero, viento_tramo

VERSION = "0.6.7"
COBERTURA_MIN = 0.25         # fracción mínima del tramo con datos para dar medias (si no: «datos insuficientes»)
COBERTURA_DISTANCIA = 0.5    # la distancia navegada cruza los huecos en línea recta: exige más datos


def calidad(cob: float) -> str:
    return "alta" if cob >= 0.7 else "media" if cob >= 0.45 else "baja" if cob >= COBERTURA_MIN else "insuficiente"
HUECO_MEDIAS_MS = 15_000     # para medias de un tramo, un hueco de hasta 15 s no invalida el tramo


def _punto(c: rec.Control, t: int):
    """Posición representativa de un control en t (punto medio si son dos)."""
    pts = []
    for _, p in c.puntos:
        if p is None:
            continue
        x, y = p.en(np.array([t]))
        if not np.isnan(x[0]):
            pts.append((float(x[0]), float(y[0])))
    if not pts:
        return None
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def _linea_de(balizas, roles, izq, der, proy, linea_doc=None):
    a, b = balizas.get(roles.get(izq)), balizas.get(roles.get(der))
    if a is not None and b is not None:
        return a, b
    if linea_doc:
        (la1, lo1), (la2, lo2) = linea_doc["leftEnd"], linea_doc["rightEnd"]
        x1, y1 = proy.xy(la1, lo1)
        x2, y2 = proy.xy(la2, lo2)
        return Pista.constante(float(x1), float(y1)), Pista.constante(float(x2), float(y2))
    return None, None


def _r(v, n=2):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else round(float(v), n)


def recorrido_dudoso(tramos: list[dict], llegadas: dict, senal: int) -> bool:
    """El recorrido reconstruido no cuadra si el parcial mediano de algún tramo se aleja mucho del
    reparto de la duración de la prueba entre sus tramos (fuera de 0,4–2,5 veces)."""
    if not tramos or not llegadas:
        return False
    esperado = (float(np.median(list(llegadas.values()))) - senal) / 1000 / len(tramos)
    for t in tramos:
        parciales = [f["parcial_s"] for f in t["barcos"].values() if f.get("parcial_s")]
        if not parciales:
            return True
        r = float(np.median(parciales)) / esperado
        if not 0.4 <= r <= 2.5:
            return True
    return False


def analizar(prueba: dict, cols: dict, roles: dict[str, int]) -> dict:
    senal = prueba["senal"]
    llegadas = {v: t for v, t in prueba["llegadas"].items()}
    comp = cols["role"] != "mark"
    proy = Proyeccion(float(np.mean(cols["latitude"][comp])), float(np.mean(cols["longitude"][comp])))
    trazas = construir(cols, proy)
    _, balizas = pistas(cols, proy)
    avisos = []

    pin, comite = _linea_de(balizas, roles, "startLeft", "startRight", proy, prueba.get("linea_salida"))
    if pin is None:
        return {"version": VERSION, "error": "No hay línea de salida: ni balizas con Atlas ni extremos en el documento."}
    lleg_a, lleg_b = _linea_de(balizas, roles, "finishLeft", "finishRight", proy)
    if comite.fija:
        avisos.append("La línea de salida se toma del documento del comité (sus balizas no transmiten).")

    controles, pasos, eje, vueltas, av = rec.reconstruir(trazas, balizas, roles, senal, llegadas,
                                                          pin, comite, lleg_a, lleg_b)
    avisos += av
    for c in controles:
        if c.fuente == "estimada":
            avisos.append(f"{c.nombre}: sin Atlas; posición estimada con los rodeos de la flota.")

    # ---------------------------------------------------------------- tramos y viento
    tramos = []
    n_ceñ = n_popa = 0
    for ini, fin in zip(controles, controles[1:]):
        if fin.tipo == "offset":  # baliza → offset forma parte del rodeo, no es un tramo
            continue
        ceñida = fin.tipo == "barlovento" or (fin.tipo == "llegada" and ini.tipo == "sotavento")
        if ceñida:
            n_ceñ += 1
        else:
            n_popa += 1
        nombre = f"Ceñida {n_ceñ}" if ceñida else f"Popa {n_popa}"
        en_tramo = {}
        for v in trazas:
            e = senal if ini.id == "salida" else (pasos[v].get(ini.id).t if ini.id in pasos[v] else None)
            s = pasos[v].get(fin.id).t if fin.id in pasos[v] else None
            if e is not None and s is not None and s > e:
                en_tramo[v] = (e, s)
        if not en_tramo:
            avisos.append(f"{nombre}: ningún barco tiene paso por las dos balizas del tramo.")
            continue
        # Pasos imposibles (rodeo mal detectado por un hueco): fuera del tramo
        med = float(np.median([s_ - e for e, s_ in en_tramo.values()]))
        raros = [v for v, (e, s_) in en_tramo.items() if not 0.5 * med <= s_ - e <= 2.5 * med]
        for v in raros:
            del en_tramo[v]
        if raros:
            avisos.append(f"{nombre}: {len(raros)} barco(s) sin paso fiable por las balizas del tramo (huecos de datos).")
        lider = min(en_tramo, key=lambda v: en_tramo[v][1])
        t0, t1 = en_tramo[lider]
        p_ini = _punto(ini, ini.rodeo_mediano or senal)
        p_fin = _punto(fin, fin.rodeo_mediano or t1)
        eje_tramo = tm.rumbo_tramo(p_ini, p_fin) if p_ini and p_fin else eje
        # TWD de partida: la del final del tramo anterior; en el primero, el rumbo del eje
        previo = tramos[-1]["viento"].cortes[-1].twd if tramos else None
        ref = previo if previo is not None else (eje_tramo if ceñida else (eje_tramo + 180) % 360)
        vt = viento_tramo(trazas, en_tramo, t0, t1, ceñida, ref, limite_deg=30 if previo is not None else None,
                          eje=eje_tramo)
        largo = float(distancia(*p_ini, *p_fin)) if p_ini and p_fin else None
        tramos.append({"id": f"{'c' if ceñida else 'p'}{n_ceñ if ceñida else n_popa}", "nombre": nombre,
                       "ceñida": ceñida, "desde": ini.id, "hasta": fin.id, "en_tramo": en_tramo, "viento": vt,
                       "eje": eje_tramo, "largo_m": largo, "lider": lider})
    calibrar_tws([t["viento"] for t in tramos], prueba.get("viento_kn"))

    # ---------------------------------------------------------------- maniobras y offset de escora
    man_por_tramo = {t["id"]: {} for t in tramos}
    for t in tramos:
        for v, (e, s) in t["en_tramo"].items():
            man_por_tramo[t["id"]][v] = tm.maniobras(trazas[v], e, s, t["viento"],
                                                     0 if t["desde"] == "salida" else tm.MARGEN_RODEO_MS)
    offsets = {v: tm.offset_escora(tr, [(e, s, t["viento"]) for t in tramos for vv, (e, s) in t["en_tramo"].items() if vv == v])
               for v, tr in trazas.items()}

    # ---------------------------------------------------------------- métricas por tramo
    salida_tramos = []
    for t in tramos:
        vt, ceñida = t["viento"], t["ceñida"]
        twas = [c.twa_flota for c in vt.cortes if c.twa_flota]
        twa_flota = float(np.median(twas)) if twas else None
        filas = {}
        for v, (e, s) in t["en_tramo"].items():
            tr = trazas[v]
            i = tr.tramo(e, s)
            cob = tr.cobertura(e, s, HUECO_MEDIAS_MS)
            f = {"t_entrada": e, "t_salida": s, "parcial_s": round((s - e) / 1000, 1), "cobertura": round(cob, 2),
                 "calidad": calidad(cob)}
            mans = man_por_tramo[t["id"]][v]
            perdidas = [m.perdida_m for m in mans if m.perdida_m is not None]
            f["maniobras"] = len(mans)
            f["perdida_m"] = round(sum(perdidas), 1) if perdidas else (0.0 if not mans else None)
            f["perdidas_medidas"] = len(perdidas)
            if cob >= COBERTURA_MIN and len(i) > 5:
                twd = vt.twd_en(tr.ts[i])
                ref = twd if ceñida else (twd + 180) % 360
                f["sog"] = _r(tm.media_temporal(tr.sog[i], tr.ts[i]))
                f["vmg"] = _r(tm.media_temporal(tm.vmg(tr, i, twd, ceñida), tr.ts[i]))
                f["twa"] = _r(tm.media_temporal(np.abs(dif(tr.cog[i] - twd)), tr.ts[i]), 1)
                f["distancia_m"] = (round(float(np.sum(np.hypot(np.diff(tr.x[i]), np.diff(tr.y[i])))), 0)
                                    if cob >= COBERTURA_DISTANCIA else None)
                esc = np.abs(tr.roll[i] - offsets[v])
                f["escora"] = _r(np.median(esc), 1)
                f["escora_iqr"] = _r(np.subtract(*np.percentile(esc, [75, 25])), 1)
                f["cabeceo"] = _r(np.median(tr.pitch[i]), 1)
                f["cabeceo_iqr"] = _r(np.subtract(*np.percentile(tr.pitch[i], [75, 25])), 1)
            else:
                f.update({k: None for k in ("sog", "vmg", "twa", "distancia_m", "escora", "escora_iqr", "cabeceo", "cabeceo_iqr")})
            fin_ctrl = next(c for c in controles if c.id == t["hasta"])
            paso_fin = pasos[v].get(t["hasta"])
            marca = None
            if fin_ctrl.tipo in ("barlovento", "sotavento") and paso_fin is not None:
                if fin_ctrl.es_puerta:  # la baliza de la puerta por la que pasó
                    marca = min((p.en(np.array([s])) for _, p in fin_ctrl.puntos),
                                key=lambda xy: math.hypot(xy[0][0] - paso_fin.x, xy[1][0] - paso_fin.y))
                    marca = (float(marca[0][0]), float(marca[1][0]))
                else:
                    marca = _punto(fin_ctrl, s)
            f["layline"] = tm.layline(tr, e, s, marca, vt, twa_flota, mans[-1] if mans else None)
            f["puerta"] = paso_fin.puerta if paso_fin else None
            filas[v] = f
        # posiciones y gaps al final del tramo
        orden = sorted(filas, key=lambda v: filas[v]["t_salida"])
        for k, v in enumerate(orden, 1):
            filas[v]["posicion"] = k
            filas[v]["gap_s"] = round((filas[v]["t_salida"] - filas[orden[0]]["t_salida"]) / 1000, 1)
        # modo frente a la flota y barco fantasma
        buenas = [f for f in filas.values() if f["twa"] is not None]
        med_twa = float(np.median([f["twa"] for f in buenas])) if buenas else None
        med_sog = float(np.median([f["sog"] for f in buenas])) if buenas else None
        fant = tm.fantasma(t["largo_m"], vt, t["eje"], twa_flota)
        for f in filas.values():
            f["modo"] = tm.modo(f["twa"], f["sog"], med_twa, med_sog, ceñida) if buenas else None
            if fant and f["distancia_m"]:
                f["vs_fantasma_m"] = round(f["distancia_m"] - fant, 0)
                f["eficiencia_pct"] = round((fant - f["distancia_m"]) / fant * 100, 1)
            else:
                f["vs_fantasma_m"] = f["eficiencia_pct"] = None
        presion = [c.tws for c in vt.cortes] if prueba.get("viento_kn") else [c.sog_mediana for c in vt.cortes]
        fr = fases([c.twd for c in vt.cortes], 3.0, ("PROGRESIVA DERECHA", "PROGRESIVA IZQUIERDA", "ESTABLE"), circular=True)
        quien_primero(fr, vt.cortes, "twd", True)
        fp = fases(presion, 0.5 if prueba.get("viento_kn") else 0.2, ("SUBIENDO", "BAJANDO", "ESTABLE"))
        quien_primero(fp, vt.cortes, "sog", False)
        cortes = [{"pct": 5 + 10 * k, "t": c.t, "twd": round(c.twd, 1), "twa_flota": _r(c.twa_flota, 1),
                   "sog_mediana": _r(c.sog_mediana), "tws": c.tws, "confianza": c.confianza, "fuente": c.fuente,
                   "sog_izq": _r(c.sog_izq), "sog_der": _r(c.sog_der),
                   "rumbos": [round(c.rumbos[0], 1), round(c.rumbos[1], 1)] if c.rumbos else None}
                  for k, c in enumerate(vt.cortes)]
        # Escora óptima (solo ceñida): franjas de escora frente a la VMG relativa a la flota
        opt = None
        if ceñida:
            opt = esc_mod.optima(esc_mod.segmentos(trazas, dict(t["en_tramo"]), vt,
                                                   {v: [m.t for m in ms] for v, ms in man_por_tramo[t["id"]].items()}, offsets))
            if opt:
                for v, pct in esc_mod.en_rango_por_barco(opt).items():
                    if v in filas:
                        filas[v]["escora_en_rango_pct"] = pct
                opt.pop("_por_barco")
        salida_tramos.append({
            "escora_optima": opt,
            "id": t["id"], "nombre": t["nombre"], "tipo": "ceñida" if ceñida else "popa",
            "desde": t["desde"], "hasta": t["hasta"], "t0": vt.t0, "t1": vt.t1,
            "rumbo_eje": round(t["eje"], 1), "largo_m": _r(t["largo_m"], 0),
            "viento": {"twd_media": round(vt.twd_media, 1), "twa_flota": _r(twa_flota, 1), "cortes": cortes,
                       "tws_calibrada": bool(prueba.get("viento_kn"))},
            "fases_rolada": fr,
            "fases_presion": fp,
            "fantasma_m": fant,
            "barcos": filas,
            "maniobras": {v: [{"t": m.t, "tipo": m.tipo, "perdida_m": m.perdida_m} for m in ms]
                          for v, ms in man_por_tramo[t["id"]].items()},
        })

    # ---------------------------------------------------------------- salida
    c1 = next((t for t in tramos if t["ceñida"]), None)
    b1 = next((c for c in controles if c.tipo == "barlovento"), None)
    salida = None
    if c1 is not None:
        pasos_b1 = {v: p[b1.id].t for v, p in pasos.items() if b1 and b1.id in p}
        man_c1 = man_por_tramo[c1["id"]]
        salida = sal.analizar(trazas, pin, comite, senal, eje, c1["viento"],
                              _punto(b1, b1.rodeo_mediano) if b1 else None, pasos_b1, man_c1,
                              prueba.get("ocs", []), prueba.get("ocs_fiable", True))
        salida["tws_disparo"] = prueba.get("viento_kn")

    # ---------------------------------------------------------------- rendimiento (toda la prueba)
    rendimiento = {}
    for v in trazas:
        r = {}
        for tipo in ("ceñida", "popa"):
            fl = [(tr_["barcos"][v]) for tr_ in salida_tramos if tr_["tipo"] == tipo and v in tr_["barcos"]]
            fl = [f for f in fl if f["sog"] is not None]
            w = [f["parcial_s"] for f in fl]
            for k in ("vmg", "sog", "twa", "escora", "cabeceo"):
                vals = [f[k] for f in fl if f[k] is not None]
                ww = [f["parcial_s"] for f in fl if f[k] is not None]
                r[f"{k}_{tipo}"] = _r(np.average(vals, weights=ww), 2) if vals else None
            tipo_m = "virada" if tipo == "ceñida" else "trasluchada"
            per = [m["perdida_m"] for tr_ in salida_tramos if tr_["tipo"] == tipo
                   for m in tr_["maniobras"].get(v, []) if m["perdida_m"] is not None]
            r[f"perdida_{tipo_m}_m"] = _r(np.mean(per), 1) if per else None
            r[f"n_{tipo_m}s"] = sum(len(tr_["maniobras"].get(v, [])) for tr_ in salida_tramos if tr_["tipo"] == tipo)
        r["cobertura"] = _r(trazas[v].cobertura(senal, llegadas[v], HUECO_MEDIAS_MS), 2) if v in llegadas else None
        rendimiento[v] = r

    # Puerta favorecida: la baliza más a barlovento según la TWD al acabar la popa (se navega
    # menos hacia abajo y menos hacia arriba). Nombres mirando a sotavento, como RaceSense.
    puertas = {}
    for c in controles:
        if not c.es_puerta or c.rodeo_mediano is None:
            continue
        popa = next((t for t in tramos if t["hasta"] == c.id), None)
        if popa is None:
            continue
        twd = float(popa["viento"].cortes[-1].twd)
        (s1, p1), (s2, p2) = c.puntos
        x1, y1 = p1.en(np.array([c.rodeo_mediano]))
        x2, y2 = p2.en(np.array([c.rodeo_mediano]))
        if np.isnan(x1[0]) or np.isnan(x2[0]):
            continue
        barl_1, lat_1 = a_ejes(x1[0], y1[0], twd)
        barl_2, lat_2 = a_ejes(x2[0], y2[0], twd)
        mejor_1 = barl_1 > barl_2
        # mirando a sotavento, la izquierda es la derecha mirando a barlovento (lat mayor)
        lado_1 = "IZQUIERDA" if lat_1 > lat_2 else "DERECHA"
        lado_2 = "DERECHA" if lado_1 == "IZQUIERDA" else "IZQUIERDA"
        puertas[c.id] = {"favorecida": lado_1 if mejor_1 else lado_2, "ventaja_m": _r(abs(float(barl_1 - barl_2)), 1),
                         "twd": round(twd, 1)}

    # Corriente de la prueba (constante): brújula + comprobación con las velocidades de las amuras
    entrada_corr = [{"ceñida": t["tipo"] == "ceñida", "t0": t["t0"], "t1": t["t1"],
                     "avance": t["viento"]["twd_media"] if t["tipo"] == "ceñida" else (t["viento"]["twd_media"] + 180) % 360,
                     "barcos": {v: (f["t_entrada"], f["t_salida"]) for v, f in t["barcos"].items()}}
                    for t in salida_tramos]
    decl = corr.declinacion(proy.lat0, proy.lon0, senal)
    c = corr.estimar(trazas, entrada_corr, decl)
    # por vuelta (ceñida + popa siguiente): la marea cambia durante la prueba
    vueltas_corr = []
    for k in range(0, len(entrada_corr) - 1):
        a, b = entrada_corr[k], entrada_corr[k + 1]
        if a["ceñida"] and not b["ceñida"]:
            cv = corr.estimar(trazas, [a, b], decl)
            vueltas_corr.append({"vuelta": len(vueltas_corr) + 1, "desde_s": round((a["t0"] - senal) / 1000),
                                 "hasta_s": round((b["t1"] - senal) / 1000), **(cv.a_dict() if cv else {"confianza": None})})
    orden = sorted(llegadas, key=llegadas.get)
    dudoso = recorrido_dudoso(salida_tramos, llegadas, senal)
    if dudoso:
        avisos.insert(0, "Recorrido dudoso: los parciales de los tramos no cuadran con la duración de la prueba "
                         "(balizas estimadas mal situadas). Las llegadas valen; las métricas por tramo, no.")
    return {
        "recorrido_dudoso": dudoso,
        "corriente": (c.a_dict() | {"por_vuelta": vueltas_corr}) if c else None,
        "brujulas": c.a_dict_brujulas() if c else {"declinacion_grados": round(decl, 1), "desvios_grados": {}},
        "version": VERSION,
        "senal": senal,
        "proyeccion": {"lat0": proy.lat0, "lon0": proy.lon0},
        "vueltas": vueltas,
        "eje": round(eje, 1),
        "controles": [{"id": c.id, "nombre": c.nombre, "tipo": c.tipo, "fuente": c.fuente,
                       "sn": [sn for sn, _ in c.puntos], "t_mediano": c.rodeo_mediano,
                       "xy": _punto(c, c.rodeo_mediano or senal), **({"puerta": puertas[c.id]} if c.id in puertas else {})}
                      for c in controles],
        "pasos": {v: {cid: {"t": p.t, "entrada": p.entrada, "salida": p.salida, "puerta": p.puerta}
                      for cid, p in pv.items()} for v, pv in pasos.items()},
        "tramos": salida_tramos,
        "salida": salida,
        "rendimiento": rendimiento,
        "clasificacion": [{"vela": v, "posicion": k, "t": llegadas[v],
                           "tiempo_s": round((llegadas[v] - senal) / 1000, 1)} for k, v in enumerate(orden, 1)],
        "ocs": prueba.get("ocs", []),
        "offsets_escora": {v: round(o, 1) for v, o in offsets.items()},
        "avisos": avisos,
    }
