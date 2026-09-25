"""Cifras de las que sale el debrief: todo del motor, redondeado como en la web.

Convención: la unidad va en el nombre del campo (_kn, _m, _s, _grados, _pct); lo demás son puestos,
recuentos o textos. El validador se apoya en ella para comprobar cada cifra del texto con su unidad.
Las diferencias con la flota se calculan aquí para que la IA no tenga que hacer cuentas.
"""
from __future__ import annotations

import statistics

CALIDAD_BUENA = ("alta", "media")


def _r(v, d=0):
    if v is None:
        return None
    return round(float(v), d) if d else int(round(float(v)))


def _mediana(vals):
    vals = [v for v in vals if v is not None]
    return statistics.median(vals) if vals else None


def _lado(p):
    return {"IZQUIERDA": "izquierda", "DERECHA": "derecha", "flota": "toda la flota a la vez"}.get(p) if p else None


def _vela(v: str, nombres: dict) -> str:
    return nombres.get(v, {}).get("vela") or v


def _limpia(d):
    """Quita claves con None (menos ruido para la IA; «sin dato» se indica aparte)."""
    if isinstance(d, dict):
        return {k: _limpia(x) for k, x in d.items() if x is not None}
    if isinstance(d, list):
        return [_limpia(x) for x in d]
    return d


def de_prueba(an: dict, v: str, nombres: dict | None = None) -> dict:
    nombres = nombres or {}
    p = an["prueba"]
    clas = an["clasificacion"]
    mia = next((c for c in clas if c["vela"] == v), None)
    top5 = [c["vela"] for c in clas if c["vela"] != v][:5]   # referencia: los 5 primeros (sin este barco)
    h = {
        "tipo": "debrief de una prueba",
        "barco": _vela(v, nombres),
        "prueba": {
            "numero": p.get("numero"),
            "llegadas": "reconstruidas desde la telemetría (puesto provisional)" if p.get("estado") == "reconstruida" else "oficiales de RaceSense",
            "viento_referencia_kn": p.get("viento_kn"),
            "intensidad_viento": "calibrada con el viento de referencia" if p.get("viento_kn") else "sin calibrar (solo relativa)",
            "barcos_llegados": len(clas),
            "puesto": mia["posicion"] if mia else None,
            "tiempo_s": _r(mia["tiempo_s"]) if mia else None,
            "detras_del_ganador_s": _r(mia["tiempo_s"] - clas[0]["tiempo_s"]) if mia and clas else None,
            "recorrido_dudoso": bool(an.get("recorrido_dudoso")),
            "top5_de_la_prueba": [_vela(x, nombres) for x in top5],
        },
    }
    # Salida
    s = an.get("salida")
    if s:
        b = s["barcos"].get(v) or {}
        h["salida"] = {
            "telemetria_en_el_disparo": ("sí" if b.get("en_salida") else
                                         "no: hueco de datos de RaceSense, la salida no se puede medir (no es un fallo del barco)"),
            "margen_a_la_linea_m": _r(b.get("margen_m"), 1),
            "posicion_en_la_linea_pct": _r(b.get("posicion_linea_pct")),
            "posicion_en_la_linea_significa": "dónde salió en la línea: 0 % = extremo del comité, 100 % = pin (no es una nota)",
            "sog_en_el_disparo_kn": _r(b.get("sog_disparo"), 2),
            "cruce_gps_tras_la_senal_s": b.get("cruce_s"),
            "vmg_primeros_90_s_kn": _r(b.get("vmg_0_90"), 2),
            "puesto_a_60_s": b.get("pos_60"), "distancia_al_primero_a_60_s_m": _r(b.get("dist_60")),
            "puesto_a_180_s": b.get("pos_180"), "distancia_al_primero_a_180_s_m": _r(b.get("dist_180")),
            "primera_virada_tras_la_senal_s": b.get("primera_virada_s"),
            "puesto_en_baliza_1": b.get("pos_b1"), "detras_del_primero_en_baliza_1_s": b.get("gap_b1_s"),
            "ocs": b.get("ocs") not in (None, "NO"), "sobre_la_linea_gps": bool(b.get("sobre_linea_gps")),
            "extremo_favorecido": {"PIN": "pin", "COMITE": "comité"}.get(s["sesgo"]["extremo"], s["sesgo"]["extremo"].lower()),
            "sesgo_de_la_linea_grados": _r(s["sesgo"]["grados"], 1), "ventaja_del_extremo_m": _r(s["sesgo"]["metros"]),
            "twd_en_el_disparo_grados": _r(s.get("twd_disparo")),
        }
        s5 = [s["barcos"][x] for x in top5 if (s["barcos"].get(x) or {}).get("en_salida")]
        h["salida"]["top5"] = {"con_datos_en_el_disparo": len(s5),
                               "margen_a_la_linea_mediana_m": _r(_mediana([x.get("margen_m") for x in s5]), 1),
                               "posicion_en_la_linea_mediana_pct": _r(_mediana([x.get("posicion_linea_pct") for x in s5])),
                               "puesto_a_60_s_mediano": _r(_mediana([x.get("pos_60") for x in s5])),
                               "vmg_primeros_90_s_mediana_kn": _r(_mediana([x.get("vmg_0_90") for x in s5]), 2)}
    # Tramos
    pos_ant = None
    tramos = []
    for t in an["tramos"]:
        f = t["barcos"].get(v)
        buenos = [x for x in t["barcos"].values() if x.get("calidad") in CALIDAD_BUENA]
        med = {k: _mediana([x.get(k) for x in buenos]) for k in ("vmg", "sog", "twa", "perdida_m")}
        cinco = [t["barcos"][x] for x in top5 if (t["barcos"].get(x) or {}).get("calidad") in CALIDAD_BUENA]
        m5 = {k: _mediana([x.get(k) for x in cinco]) for k in ("vmg", "sog", "twa", "perdida_m", "maniobras", "distancia_m", "escora")}
        tr = {"nombre": t["nombre"], "tipo": t["tipo"], "largo_m": _r(t.get("largo_m")),
              "viento": {"twd_media_grados": _r(t["viento"]["twd_media"]),
                         "twa_de_la_flota_grados": _r(t["viento"].get("twa_flota")),
                         "roladas": [{"desde_pct": x["desde_pct"], "hasta_pct": x["hasta_pct"], "tipo": x["tipo"].lower(),
                                      "cambio_grados": _r(x["delta"], 1), "lado_que_la_recibio_primero": _lado(x.get("primero"))}
                                     for x in t.get("fases_rolada", [])],
                         "presion": [{"desde_pct": x["desde_pct"], "hasta_pct": x["hasta_pct"], "tipo": x["tipo"].lower(),
                                      "lado_que_la_recibio_primero": _lado(x.get("primero"))}
                                     for x in t.get("fases_presion", [])]}}
        if not f:
            tr["sin_datos_del_barco"] = True
            tramos.append(tr)
            continue
        lay = f.get("layline") or {}
        tr |= {
            "puesto_al_final": f.get("posicion"),
            "puestos_ganados": (pos_ant - f["posicion"]) if pos_ant and f.get("posicion") else None,
            "detras_del_primero_s": _r(f.get("gap_s")), "parcial_s": _r(f.get("parcial_s")),
            "calidad_de_datos": f.get("calidad"), "cobertura_pct": _r((f.get("cobertura") or 0) * 100),
            "vmg_kn": _r(f.get("vmg"), 2), "vmg_mediana_flota_kn": _r(med["vmg"], 2),
            "vmg_frente_a_la_mediana_kn": _r(f["vmg"] - med["vmg"], 2) if f.get("vmg") is not None and med["vmg"] is not None else None,
            "top5": {"barcos_con_datos": len(cinco),
                     "vmg_mediana_kn": _r(m5["vmg"], 2), "sog_mediana_kn": _r(m5["sog"], 2),
                     "twa_mediana_grados": _r(m5["twa"], 1), "maniobras_mediana": _r(m5["maniobras"]),
                     "perdida_en_maniobras_mediana_m": _r(m5["perdida_m"]),
                     "distancia_navegada_mediana_m": _r(m5["distancia_m"]), "escora_mediana_grados": _r(m5["escora"]),
                     "con_layline_sobrepasada": sum(1 for x in cinco if (x.get("layline") or {}).get("estado") == "SOBREPASADA")},
            "vmg_frente_al_top5_kn": _r(f["vmg"] - m5["vmg"], 2) if f.get("vmg") is not None and m5["vmg"] is not None else None,
            "sog_frente_al_top5_kn": _r(f["sog"] - m5["sog"], 2) if f.get("sog") is not None and m5["sog"] is not None else None,
            "distancia_frente_al_top5_m": _r(f["distancia_m"] - m5["distancia_m"]) if f.get("distancia_m") is not None and m5["distancia_m"] is not None else None,
            "sog_kn": _r(f.get("sog"), 2), "sog_mediana_flota_kn": _r(med["sog"], 2),
            "twa_grados": _r(f.get("twa"), 1), "twa_mediana_flota_grados": _r(med["twa"], 1),
            "distancia_navegada_m": _r(f.get("distancia_m")),
            "maniobras": f.get("maniobras"), "perdida_en_maniobras_m": _r(f.get("perdida_m")),
            "perdida_en_maniobras_mediana_flota_m": _r(med["perdida_m"]),
            "layline": ({"estado": "sobrepasada", "lado": (lay.get("lado") or "").lower()
                         + (" (mirando a sotavento)" if t["tipo"] == "popa" else " (mirando a barlovento)"), "exceso_m": _r(lay.get("metros")),
                         "tiempo_fuera_s": lay.get("segundos")} if lay.get("estado") == "SOBREPASADA"
                        else {"estado": "correcta"} if lay.get("estado") == "OK" else None),
            "modo": (f.get("modo") or "").lower() or None,
            "frente_al_barco_fantasma_m": _r(f.get("vs_fantasma_m")),
            "eficiencia_en_roladas_pct": _r(f.get("eficiencia_pct"), 1),
            "escora_grados": _r(f.get("escora")), "cabeceo_grados": _r(f.get("cabeceo")),
        }
        if f.get("puerta"):
            fin = next((c for c in an["controles"] if c["id"] == t["hasta"]), {})
            pz = fin.get("puerta")
            tr["puerta"] = {"elegida": f["puerta"].lower(), "nota": "izquierda/derecha mirando a sotavento",
                            **({"favorecida": pz["favorecida"].lower(), "ventaja_de_la_favorecida_m": _r(pz["ventaja_m"])} if pz else {})}
        pos_ant = f.get("posicion") or pos_ant
        tramos.append(tr)
    h["tramos"] = tramos
    # Medias de la prueba frente al top 5 y a la flota
    r = an["rendimiento"].get(v)
    if r:
        rend = {}
        for k, u, d in (("vmg_ceñida", "kn", 2), ("vmg_popa", "kn", 2), ("sog_ceñida", "kn", 2), ("sog_popa", "kn", 2),
                        ("twa_ceñida", "grados", 1), ("twa_popa", "grados", 1), ("escora_ceñida", "grados", 0),
                        ("escora_popa", "grados", 0), ("perdida_virada_m", None, 0), ("perdida_trasluchada_m", None, 0)):
            med = _mediana([x.get(k) for x in an["rendimiento"].values() if (x.get("cobertura") or 0) >= 0.5])
            nombre = k if u is None else f"{k}_{u}"
            mn = k.replace("_m", "_mediana_flota_m") if u is None else f"{k}_mediana_flota_{u}"
            rend[nombre] = _r(r.get(k), d)
            rend[mn] = _r(med, d)
            t5 = _mediana([an["rendimiento"][x].get(k) for x in top5
                           if x in an["rendimiento"] and (an["rendimiento"][x].get("cobertura") or 0) >= 0.5])
            rend[k.replace("_m", "_top5_m") if u is None else f"{k}_top5_{u}"] = _r(t5, d)
            if r.get(k) is not None and t5 is not None:
                rend[k.replace("_m", "_frente_al_top5_m") if u is None else f"{k}_frente_al_top5_{u}"] = _r(r[k] - t5, d)
        rend["viradas"] = r.get("n_viradas")
        rend["trasluchadas"] = r.get("n_trasluchadas")
        rend["cobertura_pct"] = _r((r.get("cobertura") or 0) * 100)
        h["medias_de_la_prueba"] = rend
    return _limpia(h)


def _dif(f, p, m):
    a = (f or {}).get("rend", {}) or {}
    b = p.get("flota") or {}
    return _r(a[m] - b[m], 2) if a.get(m) is not None and b.get(m) is not None else None


def de_campeonato(res: dict, v: str, nombre_camp: str, nombres: dict | None = None) -> dict:
    nombres = nombres or {}
    gen = res["general"]
    mia = next(f for f in gen if f["vela"] == v)
    b = res["barcos"][v]
    top5 = [f["vela"] for f in gen if f["vela"] != v][:5]
    t = b["totales"]

    def media_top5(fn, d):
        return _r(_mediana([fn(res["barcos"][x]["totales"]) for x in top5]), d)

    rend = {}
    for k, u, d in (("vmg_ceñida", "kn", 2), ("vmg_popa", "kn", 2), ("sog_ceñida", "kn", 2), ("sog_popa", "kn", 2),
                    ("twa_ceñida", "grados", 1), ("twa_popa", "grados", 1), ("escora_ceñida", "grados", 0),
                    ("escora_popa", "grados", 0), ("perdida_virada_m", None, 1), ("perdida_trasluchada_m", None, 1)):
        nombre = k if u is None else f"{k}_{u}"
        rend[nombre] = _r(t["rend"].get(k), d)
        t5 = media_top5(lambda x, k=k: x["rend"].get(k), d)
        rend[(k.replace("_m", "_top5_m") if u is None else f"{k}_top5_{u}")] = t5
        if t["rend"].get(k) is not None and t5 is not None:
            rend[(k.replace("_m", "_frente_al_top5_m") if u is None else f"{k}_frente_al_top5_{u}")] = _r(t["rend"][k] - t5, d)

    def top15(m):
        r = [f["rango"][m]["pos"] for f in b["por_prueba"] if f and m in f.get("rango", {}) and f["rango"][m]["pos"]]
        return {"pruebas_en_el_top_15": sum(1 for x in r if x <= 15), "pruebas_con_dato": len(r)} if r else None

    lay = t["laylines"]
    n_lay = lay["ok"] + lay["sobrepasadas"]
    pruebas = []
    for k, p in enumerate(res["pruebas"]):
        pt = mia["puntos"][k]
        f = b["por_prueba"][k]
        v5 = {m: _mediana([(res["barcos"][x]["por_prueba"][k] or {}).get("rend", {}).get(m) if res["barcos"][x]["por_prueba"][k]
                           and res["barcos"][x]["por_prueba"][k].get("rend") else None for x in top5])
              for m in ("vmg_ceñida", "vmg_popa")}
        mv = (f or {}).get("rend") or {}
        fila_top5 = {
            "vmg_ceñida_top5_kn": _r(v5["vmg_ceñida"], 2),
            "vmg_ceñida_frente_al_top5_kn": _r(mv["vmg_ceñida"] - v5["vmg_ceñida"], 2) if mv.get("vmg_ceñida") is not None and v5["vmg_ceñida"] is not None else None,
            "vmg_popa_top5_kn": _r(v5["vmg_popa"], 2),
            "vmg_popa_frente_al_top5_kn": _r(mv["vmg_popa"] - v5["vmg_popa"], 2) if mv.get("vmg_popa") is not None and v5["vmg_popa"] is not None else None,
        }
        pruebas.append({
            "prueba": p["numero"], "puntos": pt["pts"], "codigo": pt["cod"], "descartada": pt["desc"],
            "llegadas": "reconstruidas" if p["estado"] == "reconstruida" else "oficiales",
            "viento_referencia_kn": p.get("viento_kn"),
            "metricas": ("sí" if f is not None else "no: recorrido reconstruido dudoso (balizas estimadas mal situadas)"
                         if p.get("recorrido_dudoso") else "no: prueba sin analizar"),
            "vmg_ceñida_kn": _r(f["rend"].get("vmg_ceñida"), 2) if f and f.get("rend") else None,
            "vmg_ceñida_mediana_flota_kn": _r((p.get("flota") or {}).get("vmg_ceñida"), 2),
            "vmg_ceñida_frente_a_la_mediana_kn": _dif(f, p, "vmg_ceñida"),
            "vmg_popa_kn": _r(f["rend"].get("vmg_popa"), 2) if f and f.get("rend") else None,
            "vmg_popa_mediana_flota_kn": _r((p.get("flota") or {}).get("vmg_popa"), 2),
            "vmg_popa_frente_a_la_mediana_kn": _dif(f, p, "vmg_popa"),
        } | fila_top5)
    h = {
        "tipo": "debrief del campeonato",
        "campeonato": nombre_camp,
        "barco": _vela(v, nombres),
        "general_calculada": {"puesto": mia["puesto"], "barcos": res["inscritos"], "puntos_netos": mia["neto"],
                              "puntos_totales": mia["total"], "descartes": res["descartes"],
                              "nota": "sin penalizaciones ni decisiones del jurado"},
        "pruebas": pruebas,
        "medias_del_campeonato": rend | {"pruebas_con_metricas": t["analizadas"],
                                         "comparacion": "top5 = mediana de los 5 primeros de la general (sin contar este barco)"},
        "top_15_de_la_flota": {"vmg_ceñida": top15("vmg_ceñida"), "vmg_popa": top15("vmg_popa"),
                               "perdida_virada": top15("perdida_virada_m"), "perdida_trasluchada": top15("perdida_trasluchada_m")},
        "top5_de_la_general": [_vela(x, nombres) for x in top5],
        "salidas_top5": {"margen_medio_mediana_m": media_top5(lambda x: x["salida"]["margen_m"], 1),
                         "veces_en_el_top_10_a_60_s": sum(res["barcos"][x]["totales"]["salida"]["top10_60"] for x in top5),
                         "salidas_con_puesto_a_60_s": sum(res["barcos"][x]["totales"]["salida"]["con_60"] for x in top5)},
        "puertas_top5": {"puertas_con_ventaja_clara": sum(res["barcos"][x]["totales"]["puertas"]["total"] for x in top5),
                         "eligieron_la_favorecida": sum(res["barcos"][x]["totales"]["puertas"]["buenas"] for x in top5)},
        "salidas": {"salidas_con_datos": t["salida"]["pruebas"], "margen_medio_m": _r(t["salida"]["margen_m"], 1),
                    "posicion_media_en_la_linea_pct": _r(t["salida"]["posicion_linea_pct"]),
                    "posicion_en_la_linea_significa": "dónde sale en la línea: 0 % = extremo del comité, 100 % = pin (no es una nota)",
                    "veces_en_el_top_10_a_60_s": t["salida"]["top10_60"], "salidas_con_puesto_a_60_s": t["salida"]["con_60"],
                    "ocs": t["salida"]["ocs"], "sobre_la_linea_gps": t["salida"]["sobre_linea_gps"]},
        "laylines": {"tramos_con_dato": n_lay, "correctas": lay["ok"], "sobrepasadas": lay["sobrepasadas"],
                     "correctas_pct": _r(lay["ok"] / n_lay * 100) if n_lay else None,
                     "exceso_medio_m": _r(lay["metros"]),
                     "correctas_top5_pct": media_top5(lambda x: x["laylines"]["ok"] / (x["laylines"]["ok"] + x["laylines"]["sobrepasadas"]) * 100
                                                      if x["laylines"]["ok"] + x["laylines"]["sobrepasadas"] else None, 0)},
        "puertas": {"puertas_con_ventaja_clara": t["puertas"]["total"], "eligio_la_favorecida": t["puertas"]["buenas"]},
        "segun_el_viento": [{"tramo_de_viento": x["tramo"], "pruebas": x["pruebas"], "puesto_medio": _r(x["puesto_medio"], 1),
                             "vmg_ceñida_kn": _r(x["vmg_ceñida"], 2), "vmg_popa_kn": _r(x["vmg_popa"], 2)}
                            for x in t["viento"] if x["pruebas"]],
    }
    return _limpia(h)
