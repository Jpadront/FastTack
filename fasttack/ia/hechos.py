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


MOTIVOS = {"no_podia_virar": "tráfico: no podía virar (barco a menos de 3 esloras hacia donde tenía que virar)",
           "layline_con_trafico": "tráfico: la layline ya estaba ocupada por barcos delante (virar debajo era aire sucio)",
           "calculo": "cálculo: nadie le impedía virar ni ocupaba la layline"}


def _motivo(tr):
    if not tr:
        return {"motivo": "sin datos suficientes para saberlo"}
    return {"motivo": MOTIVOS.get(tr["motivo"], tr["motivo"]), "barcos_ya_en_la_layline": tr["barcos_en_layline"],
            "segundos_desde_la_layline_hasta_virar_s": tr["segundos_hasta_virar"]}


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


def _offset(an, t, v, top5):
    """Popa que empieza en un offset: tiempo desde la baliza de barlovento hasta el offset, frente al top 5."""
    if t["tipo"] != "popa" or not t["desde"].startswith("o"):
        return None
    b = "b" + t["desde"][1:]
    dur = lambda x: ((an["pasos"].get(x, {}).get(t["desde"], {}).get("t") or 0) - (an["pasos"].get(x, {}).get(b, {}).get("t") or 0)) / 1000
    mio = dur(v)
    if not 0 < mio < 300:
        return None
    t5 = [d for d in (dur(x) for x in top5) if 0 < d < 300]
    return {"de_la_baliza_al_offset_s": _r(mio), "top5_mediana_s": _r(_mediana(t5)) if len(t5) >= 2 else None}


def _twa_max(pol):
    """TWA de la franja de la polar con más VMG (con ≥ 30 s)."""
    pol = [x for x in (pol or []) if x["s"] >= 30]
    return max(pol, key=lambda x: x["vmg"])["twa"] if pol else None


def _rodeo(r, top5):
    if not r:
        return None
    t5 = [x for x in top5 if x]
    return {"tiempo_en_la_zona_s": r["tiempo_zona_s"], "sog_entrada_kn": r["sog_entrada"], "sog_minima_kn": r["sog_minima"],
            "sog_salida_kn": r["sog_salida"],
            "top5_tiempo_en_la_zona_mediano_s": _r(_mediana([x["tiempo_zona_s"] for x in t5]), 1) if len(t5) >= 2 else None,
            "top5_sog_minima_mediana_kn": _r(_mediana([x["sog_minima"] for x in t5]), 2) if len(t5) >= 2 else None,
            "nota": "zona = 3 esloras alrededor de la baliza"}


def _set(st, top5):
    if not st:
        return None
    t5 = [x["set"] for x in top5 if x]
    return {"set": {"directo": "directo (sin trasluchar al montar)", "trasluchando": "trasluchando al montar"}[st["set"]],
            "trasluchada_tras_el_rodeo_s": st.get("trasluchada_s"),
            "top5": {k: t5.count(k) for k in ("directo", "trasluchando") if t5.count(k)} or None}


def _tactica(tac, top5):
    """Cómo se jugaron las roladas y el lado del campo (motor/tactica.py), con el top 5."""
    if not tac:
        return None
    t5 = [x for x in top5 if x]
    out = {
        "amura_favorecida_pct": tac.get("amura_favorecida_pct"),
        "amura_favorecida_significa": "tiempo navegando en la amura que apuntaba más a la baliza con la rolada de cada momento",
        "tiempo_en_la_amura_desfavorecida_s": tac.get("tiempo_en_amura_desfavorecida_s"),
        "maniobras_a_favor_de_la_rolada": tac.get("maniobras_a_favor_de_la_rolada"),
        "maniobras_en_contra_de_la_rolada": tac.get("maniobras_en_contra_de_la_rolada"),
        "lado_del_campo": tac.get("lado"), "tiempo_a_la_derecha_pct": tac.get("derecha_pct"),
        "separacion_maxima_del_eje_m": tac.get("separacion_maxima_m"),
    }
    if len(t5) >= 2:
        out["top5_amura_favorecida_mediana_pct"] = _r(_mediana([x.get("amura_favorecida_pct") for x in t5]))
        out["top5_tiempo_a_la_derecha_mediano_pct"] = _r(_mediana([x.get("derecha_pct") for x in t5]))
        lados = [x.get("lado") for x in t5 if x.get("lado")]
        out["top5_lados"] = {l: lados.count(l) for l in ("izquierda", "centro", "derecha") if lados.count(l)}
    return out


def _maniobras(f, t, an, v):
    """Fases de las maniobras del tramo (medianas) frente al top 5 de la prueba."""
    d = f.get("maniobras_detalle")
    if not d:
        return None
    tipo = "virada" if t["tipo"] == "ceñida" else "trasluchada"
    ref = (an.get("maniobras_top5") or {}).get(tipo) or {}
    salidas = [m["detalle"].get("salida") for m in t["maniobras"].get(v, []) if m.get("detalle") and m["detalle"].get("salida")]
    out = {"tipo": tipo, "medidas": len([m for m in t["maniobras"].get(v, []) if m.get("detalle")]),
           "perdida_mediana_s": d.get("perdida_s"), "duracion_del_giro_mediana_s": d.get("duracion_giro_s"),
           "tiempo_en_acelerar_mediano_s": d.get("tiempo_aceleracion_s"), "caida_de_velocidad_mediana_pct": _r(d.get("caida_sog_pct")),
           "sog_entrada_mediana_kn": d.get("sog_entrada_kn"), "sog_minima_mediana_kn": d.get("sog_minima_kn"),
           "angulo_de_salida_frente_al_top5_grados": d.get("salida_frente_al_top5_grados"),
           "angulo_de_salida_significa": ("+ = sale más abierto (baja, pierde altura), − = más cerrado (alta, tarda en acelerar)"
                                          if tipo == "virada" else "+ = sale más profundo (tarda en acelerar), − = más alto (pierde profundidad)"),
           "salidas": {x: salidas.count(x) for x in sorted(set(salidas))} or None,
           "top5_perdida_mediana_s": ref.get("perdida_s_top5"), "top5_duracion_del_giro_mediana_s": ref.get("duracion_giro_s_top5"),
           "top5_tiempo_en_acelerar_mediano_s": ref.get("tiempo_aceleracion_s_top5"),
           "top5_caida_de_velocidad_mediana_pct": _r(ref.get("caida_sog_pct_top5"))}
    return out


def de_prueba(an: dict, v: str, nombres: dict | None = None, clase: str | None = None) -> dict:
    nombres = nombres or {}
    p = an["prueba"]
    clas = an["clasificacion"]
    mia = next((c for c in clas if c["vela"] == v), None)
    top5 = [c["vela"] for c in clas if c["vela"] != v][:5]   # referencia: los 5 primeros (sin este barco)
    h = {
        "tipo": "debrief de una prueba",
        "clase": clase,
        "barco": _vela(v, nombres),
        "prueba": {
            "numero": p.get("numero"),
            "llegadas": {"reconstruida": "reconstruidas desde la telemetría (puesto provisional)",
                         "estimada": "estimadas: final del último tramo (sesión con archivos .vkx)"}.get(p.get("estado"), "oficiales de RaceSense"),
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
    c = an.get("corriente")
    if c:
        h["corriente_estimada"] = {
            "velocidad_kn": c["velocidad_kn"], "hacia_grados": c["hacia_grados"],
            "a_lo_largo_del_recorrido_kn": c["a_favor_kn"], "a_lo_largo_significa": "positivo = hacia barlovento, negativo = hacia sotavento",
            "transversal_kn": c["derecha_kn"], "transversal_significa": "positivo = hacia la derecha mirando a barlovento",
            "confianza": c["confianza"],
            "por_vuelta": [{"vuelta": v["vuelta"], "velocidad_kn": v["velocidad_kn"], "hacia_grados": v["hacia_grados"],
                            "confianza": v["confianza"]} for v in c.get("por_vuelta", []) if v.get("confianza")],
            "nota": "estimada desde GPS y brújulas de la flota; las laylines ya la incluyen; TWD y TWA son sobre el fondo",
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
        vl = [z for z in (s.get("viento_en_la_linea") or []) if z.get("twd") is not None]
        if len(vl) >= 2:
            p_l = b.get("posicion_linea_pct")
            h["salida"]["viento_en_la_linea"] = {
                "zonas": [{"zona": z["zona"], "barcos": z["barcos"], "rolada_frente_a_la_media_grados": z["rolada"],
                           "sog_mediana_kn": z["sog"]} for z in vl],
                "zona_del_barco": (None if p_l is None else "comité" if p_l < 100 / 3 else "centro" if p_l < 200 / 3 else "pin"),
                "significa": ("TWD estimada en cada tercio de la línea de +10 a +60 s con los rumbos de los barcos que salieron por él; "
                              "rolada + = a la derecha (el viento viene más de la derecha), − = a la izquierda"),
            }
        d = b.get("diagnostico")
        if d:
            h["salida"]["posicionamiento"] = {
                "llegada_a_la_linea": d.get("llegada"),
                "distancia_a_la_linea_10_s_antes_m": _r(b.get("margen_menos_10_m"), 1),
                "distancia_a_la_linea_30_s_antes_m": _r(b.get("margen_menos_30_m"), 1),
                "sog_en_el_disparo_primera_fila_mediana_kn": s.get("sog_primera_fila"),
                "hueco_a_sotavento": d.get("hueco_a_sotavento"),
                "hueco_a_sotavento_esloras": b.get("hueco_sotavento_esloras"),
                "barco_a_sotavento": _vela(b["vecino_sotavento"], nombres) if b.get("vecino_sotavento") else None,
                "hueco_a_barlovento_esloras": b.get("hueco_barlovento_esloras"),
                "barco_a_barlovento": _vela(b["vecino_barlovento"], nombres) if b.get("vecino_barlovento") else None,
                "primeros_90_s": d.get("primeros_90_s"),
                "aire_sucio_primeros_90_s_pct": b.get("aire_sucio_pct"),
                "aire_sucio_de": _vela(b["aire_sucio_de"], nombres) if b.get("aire_sucio_de") and (b.get("aire_sucio_pct") or 0) > 0 else None,
                "aire_sucio_llegaba_desde": b.get("aire_sucio_lado") if (b.get("aire_sucio_pct") or 0) > 0 else None,
                "barco_a_sotavento_en_posicion_segura_primeros_60_s_pct": b.get("sotavento_seguro_pct"),
                "nota": ("estimado con las posiciones GPS de la flota: aire sucio = otro barco a ≤ 6 esloras de donde le llega el "
                         "viento aparente; posición segura = barco a sotavento a ≤ 1,5 esloras de lado y hasta 2 delante"),
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
        # top 5 con datos (también calidad baja: son pocos barcos); con menos de 2, sin referencia
        cinco = [t["barcos"][x] for x in top5 if (t["barcos"].get(x) or {}).get("calidad") in CALIDAD_BUENA + ("baja",)]
        m5 = {k: (_mediana([x.get(k) for x in cinco]) if len(cinco) >= 2 else None)
              for k in ("vmg", "sog", "twa", "perdida_m", "maniobras", "distancia_m", "escora")}
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
                         "tiempo_fuera_s": lay.get("segundos"), **_motivo(lay.get("trafico"))} if lay.get("estado") == "SOBREPASADA"
                        else {"estado": "correcta"} if lay.get("estado") == "OK" else None),
            "modo": (f.get("modo") or "").lower() or None,
            "frente_al_barco_fantasma_m": _r(f.get("vs_fantasma_m")),
            "eficiencia_en_roladas_pct": _r(f.get("eficiencia_pct"), 1),
            "escora_grados": _r(f.get("escora")), "cabeceo_grados": _r(f.get("cabeceo")),
            "escora_con_signo_grados": _r(f.get("escora_sotavento"), 1),
            "tactica": _tactica(f.get("tactica"), [t["barcos"][x].get("tactica") for x in top5 if t["barcos"].get(x)]),
            "regularidad_vmg_pct": f.get("regularidad_pct"),
            "regularidad_vmg_top5_mediana_pct": _r(_mediana([(t["barcos"].get(x) or {}).get("regularidad_pct") for x in top5]), 1),
            "regularidad_significa": "variación de la VMG de cada 30 s frente a la de la flota en esos 30 s: cuanto menor, más regular",
            "twa_de_maxima_vmg_grados": _twa_max(f.get("polar")),
            "twa_de_maxima_vmg_top5_grados": _r(_mediana([_twa_max((t["barcos"].get(x) or {}).get("polar")) for x in top5]), 1),
            "rodeo_final": _rodeo(f.get("rodeo"), [(t["barcos"].get(x) or {}).get("rodeo") for x in top5]),
            "set_tras_barlovento": _set(f.get("set"), [(t["barcos"].get(x) or {}).get("set") for x in top5]),
            "offset": _offset(an, t, v, top5),
            "maniobras_detalle": _maniobras(f, t, an, v),
        }
        o = t.get("escora_optima")
        if o:
            tr["escora_optima"] = {
                "concluyente": o["concluyente"],
                "rango_desde_grados": o["rango"][0], "rango_hasta_grados": o["rango"][1],
                "mejor_franja_desde_grados": o["mejor"][0], "mejor_franja_hasta_grados": o["mejor"][1],
                "por_debajo_de_grados": (o.get("debajo") or {}).get("hasta_grados"),
                "perdida_por_debajo_pct": (o.get("debajo") or {}).get("perdida_pct"),
                "por_encima_de_grados": (o.get("encima") or {}).get("desde_grados"),
                "perdida_por_encima_pct": (o.get("encima") or {}).get("perdida_pct"),
                "tiempo_del_barco_en_rango_pct": f.get("escora_en_rango_pct"),
                "con_mas_escora_va_mas_rapido_pero_mas_abierto_desde_grados": (o.get("sobreescora") or {}).get("desde_grados"),
                "nota": ("estimada: VMG relativa a la flota por franjas de 2° de escora; si no es concluyente, la escora no marcó diferencias"
                         + ("; en popa la escora lleva signo: + a sotavento, − a barlovento (compárala con escora_con_signo_grados)"
                            if t["tipo"] == "popa" else "")),
            }
        if f.get("puerta"):
            fin = next((c for c in an["controles"] if c["id"] == t["hasta"]), {})
            pz = fin.get("puerta")
            tr["puerta"] = {"elegida": f["puerta"].lower(), "nota": "izquierda/derecha mirando a sotavento",
                            **({"favorecida": pz["favorecida"].lower(), "ventaja_de_la_favorecida_m": _r(pz["ventaja_m"])} if pz else {})}
        pos_ant = f.get("posicion") or pos_ant
        tramos.append(tr)
    h["tramos"] = tramos
    dg = (an["rendimiento"].get(v) or {}).get("desglose")
    if dg:
        h["donde_se_perdio_la_prueba"] = {
            "total_frente_al_top5_s": dg["total_s"], "salida_s": dg["salida_s"] if dg["salida_s"] is not None else "sin datos en la señal",
            "velocidad_s": dg["velocidad_s"],
            "maniobras_s": dg["maniobras_s"], "tactica_y_resto_s": dg["tactica_s"],
            "por_tramo": [{k.replace("tactica_s", "tactica_y_resto_s"): x for k, x in f.items()} for f in dg["por_tramo"]],
            "significa": ("segundos perdidos (+) o ganados (−) frente al tiempo mediano del top 5; velocidad = VMG navegando "
                          "estable (incluye aire sucio); táctica y resto = lo que falta hasta la diferencia real (roladas, lado, "
                          "laylines, rodeos)"),
        }
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


def _escora_camp(res, v, top5):
    e = res.get("escora")
    if not e:
        return None
    t, b = e["todas"], e["barcos"]
    mio = b.get(v) or {}
    return {"ceñidas_juntas": t["ceñidas"], "concluyente": t["concluyente"],
            "rango_desde_grados": t["rango"][0], "rango_hasta_grados": t["rango"][1],
            "mejor_franja_desde_grados": t["mejor"][0], "mejor_franja_hasta_grados": t["mejor"][1],
            "por_debajo_de_grados": (t.get("debajo") or {}).get("hasta_grados"),
            "perdida_por_debajo_pct": (t.get("debajo") or {}).get("perdida_pct"),
            "escora_mediana_del_barco_grados": mio.get("escora_mediana"),
            "ceñidas_del_barco_con_escora_en_rango": mio.get("en_rango"), "ceñidas_del_barco": mio.get("ceñidas"),
            "escora_mediana_top5_grados": _r(_mediana([(b.get(x) or {}).get("escora_mediana") for x in top5]), 1),
            "nota": "todas las ceñidas del campeonato juntas; VMG relativa a los barcos vecinos por franja de 2° de escora"}


def de_campeonato(res: dict, v: str, nombre_camp: str, nombres: dict | None = None, clase: str | None = None) -> dict:
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
            "vmg_media_de_las_ceñidas_top5_kn": _r(v5["vmg_ceñida"], 2),
            "vmg_media_de_las_ceñidas_frente_al_top5_kn": _r(mv["vmg_ceñida"] - v5["vmg_ceñida"], 2) if mv.get("vmg_ceñida") is not None and v5["vmg_ceñida"] is not None else None,
            "vmg_media_de_las_popas_top5_kn": _r(v5["vmg_popa"], 2),
            "vmg_media_de_las_popas_frente_al_top5_kn": _r(mv["vmg_popa"] - v5["vmg_popa"], 2) if mv.get("vmg_popa") is not None and v5["vmg_popa"] is not None else None,
        }
        pruebas.append({
            "prueba": p["numero"], "puntos": pt["pts"], "codigo": pt["cod"], "descartada": pt["desc"],
            "llegadas": {"reconstruida": "reconstruidas", "estimada": "estimadas"}.get(p["estado"], "oficiales"),
            "corriente_kn": (p.get("corriente") or {}).get("velocidad_kn"),
            "corriente_confianza": (p.get("corriente") or {}).get("confianza"),
            "viento_referencia_kn": p.get("viento_kn"),
            "metricas": ("sí" if f is not None else "no: recorrido reconstruido dudoso (balizas estimadas mal situadas)"
                         if p.get("recorrido_dudoso") else "no: prueba sin analizar"),
            "vmg_media_de_las_ceñidas_kn": _r(f["rend"].get("vmg_ceñida"), 2) if f and f.get("rend") else None,
            "vmg_media_de_las_ceñidas_mediana_flota_kn": _r((p.get("flota") or {}).get("vmg_ceñida"), 2),
            "vmg_media_de_las_ceñidas_frente_a_la_mediana_kn": _dif(f, p, "vmg_ceñida"),
            "vmg_media_de_las_popas_kn": _r(f["rend"].get("vmg_popa"), 2) if f and f.get("rend") else None,
            "vmg_media_de_las_popas_mediana_flota_kn": _r((p.get("flota") or {}).get("vmg_popa"), 2),
            "vmg_media_de_las_popas_frente_a_la_mediana_kn": _dif(f, p, "vmg_popa"),
        } | fila_top5)
    h = {
        "tipo": "debrief del campeonato",
        "clase": clase,
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
                     "sobrepasadas_por_trafico": lay.get("por_trafico"),
                     "sobrepasadas_por_calculo_o_sin_dato": lay["sobrepasadas"] - (lay.get("por_trafico") or 0),
                     "correctas_pct": _r(lay["ok"] / n_lay * 100) if n_lay else None,
                     "exceso_medio_m": _r(lay["metros"]),
                     "correctas_top5_pct": media_top5(lambda x: x["laylines"]["ok"] / (x["laylines"]["ok"] + x["laylines"]["sobrepasadas"]) * 100
                                                      if x["laylines"]["ok"] + x["laylines"]["sobrepasadas"] else None, 0)},
        "puertas": {"puertas_con_ventaja_clara": t["puertas"]["total"], "eligio_la_favorecida": t["puertas"]["buenas"]},
        "escora_optima_en_ceñida": _escora_camp(res, v, top5),
        "segun_el_viento": [{"tramo_de_viento": x["tramo"], "pruebas": x["pruebas"], "puesto_medio": _r(x["puesto_medio"], 1),
                             "vmg_ceñida_kn": _r(x["vmg_ceñida"], 2), "vmg_popa_kn": _r(x["vmg_popa"], 2)}
                            for x in t["viento"] if x["pruebas"]],
    }
    return _limpia(h)


def de_dia(res: dict, hasta: dict, v: str, dia: str, nombre_camp: str, nombres: dict | None = None,
           clase: str | None = None) -> dict:
    """Debrief de un día: las pruebas de ese día (con el top 5 del día como referencia) y cómo queda
    el barco en la general calculada al terminar el día."""
    import datetime as dt
    h = de_campeonato(res, v, nombre_camp, nombres, clase)
    h["tipo"] = "debrief del día"
    d = dt.date.fromisoformat(dia)
    h["dia"] = f"{['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'][d.weekday()]} {d.day}"
    dia_gen = h.pop("general_calculada")
    h["resultado_del_dia"] = {"puntos_del_dia": dia_gen["puntos_totales"], "puesto_del_dia": dia_gen["puesto"],
                              "barcos": dia_gen["barcos"], "pruebas_del_dia": len(res["pruebas"]),
                              "nota": "puesto por la suma de puntos de las pruebas del día, sin descartes"}
    h["top5_del_dia"] = h.pop("top5_de_la_general")
    g = next((f for f in hasta["general"] if f["vela"] == v), None)
    if g:
        h["general_tras_el_dia"] = {"puesto": g["puesto"], "puntos_netos": g["neto"], "barcos": hasta["inscritos"],
                                    "pruebas_hasta_hoy": len(hasta["pruebas"]), "descartes": hasta["descartes"]}
    h.pop("segun_el_viento", None)
    # nombres «del día» para que el texto no hable del campeonato
    if "medias_del_campeonato" in h:
        h["medias_del_dia"] = h.pop("medias_del_campeonato")
        h["medias_del_dia"]["comparacion"] = "top5 = mediana de los 5 primeros del día (sin contar este barco)"
    if h.get("escora_optima_en_ceñida"):
        h["escora_optima_en_ceñida"]["nota"] = "todas las ceñidas del campeonato hasta hoy juntas (más datos que un solo día)"
    h["nota"] = "salidas, laylines, puertas y medias se refieren solo a las pruebas de este día"
    return h


def tramos_compactos(dp: dict, coach: bool = False) -> list[dict]:
    """Desglose por tramo de una prueba (de «de_prueba») con lo esencial, para el debrief del día."""
    claves = ("nombre", "tipo", "puesto_al_final", "puestos_ganados", "detras_del_primero_s", "calidad_de_datos",
              "vmg_kn", "vmg_frente_al_top5_kn", "vmg_frente_a_la_mediana_kn", "sog_frente_al_top5_kn",
              "twa_grados", "maniobras", "perdida_en_maniobras_m", "layline", "puerta", "modo")
    claves_coach = ("sog_kn", "sog_frente_al_top5_kn", "sog_mediana_flota_kn", "twa_mediana_flota_grados", "escora_grados",
                    "escora_con_signo_grados", "escora_optima", "tactica", "maniobras_detalle", "viento", "parcial_s",
                    "frente_al_barco_fantasma_m", "top5", "regularidad_vmg_pct", "regularidad_vmg_top5_mediana_pct",
                    "twa_de_maxima_vmg_grados", "twa_de_maxima_vmg_top5_grados", "rodeo_final", "set_tras_barlovento", "offset")
    out = []
    for t in dp.get("tramos", []):
        if t.get("sin_datos_del_barco"):
            out.append({"nombre": t["nombre"], "sin_datos_del_barco": True})
            continue
        f = {k: t[k] for k in claves + (claves_coach if coach else ()) if k in t}
        if "top5" in t and not coach:
            f["vmg_top5_kn"] = t["top5"].get("vmg_mediana_kn")
        out.append(f)
    return out


def de_cronica(an: dict, v: str, nombres: dict | None = None, clase: str | None = None) -> dict:
    """Crónica de la prueba: qué pasó en el campo (salida, cada tramo, llegada) con los barcos que
    marcaron la prueba, y dónde queda el barco de referencia en cada momento."""
    nombres = nombres or {}
    vn = lambda x: _vela(x, nombres)
    clas = an["clasificacion"]
    p = an["prueba"]
    h = {"tipo": "crónica de la prueba", "clase": clase, "barco_de_referencia": vn(v),
         "prueba": {"numero": p.get("numero"), "barcos_llegados": len(clas),
                    "llegadas": {"reconstruida": "reconstruidas", "estimada": "estimadas"}.get(p.get("estado"), "oficiales"),
                    "podio": [vn(c["vela"]) for c in clas[:3]],
                    "puesto_del_barco_de_referencia": next((c["posicion"] for c in clas if c["vela"] == v), None)}}
    s = an.get("salida")
    if s:
        orden60 = sorted((f["pos_60"], x) for x, f in s["barcos"].items() if f.get("pos_60"))
        zona = lambda pl: None if pl is None else "comité" if pl < 100 / 3 else "centro" if pl < 200 / 3 else "pin"
        h["salida"] = {
            "extremo_favorecido": {"PIN": "pin", "COMITÉ": "comité"}.get(s["sesgo"]["extremo"], s["sesgo"]["extremo"]),
            "sesgo_grados": _r(s["sesgo"]["grados"], 1), "ventaja_del_extremo_m": _r(s["sesgo"]["metros"]),
            "viento_en_la_linea": [{"zona": z["zona"], "barcos": z["barcos"], "rolada_frente_a_la_media_grados": z.get("rolada"),
                                    "sog_mediana_kn": z.get("sog")} for z in (s.get("viento_en_la_linea") or []) if z.get("twd") is not None] or None,
            "mejores_a_60_s": [{"barco": vn(x), "zona_de_la_linea": zona(s["barcos"][x].get("posicion_linea_pct"))} for _, x in orden60[:5]],
            "barco_de_referencia": ({"puesto_a_60_s": s["barcos"][v].get("pos_60"), "zona_de_la_linea": zona(s["barcos"][v].get("posicion_linea_pct")),
                                     "diagnostico": s["barcos"][v].get("diagnostico")} if v in s["barcos"] else None),
        }
    tramos = []
    for t in an["tramos"]:
        fs = t["barcos"]
        por_pos = sorted((f["posicion"], x) for x, f in fs.items() if f.get("posicion"))
        top10 = [x for _, x in por_pos[:10]]
        rapidos = sorted((f["parcial_s"], x) for x, f in fs.items() if f.get("parcial_s") and f.get("calidad") in ("alta", "media"))[:3]
        lados = [(fs[x].get("tactica") or {}).get("lado") for x in top10]
        tr = {"nombre": t["nombre"], "tipo": t["tipo"],
              "lider_al_final": vn(por_pos[0][1]) if por_pos else None,
              "mas_rapidos_del_tramo": [{"barco": vn(x), "parcial_s": _r(ps)} for ps, x in rapidos],
              "lado_de_los_10_primeros_al_final": {l: lados.count(l) for l in ("izquierda", "centro", "derecha") if lados.count(l)} or None,
              "roladas": [{"desde_pct": x["desde_pct"], "hasta_pct": x["hasta_pct"], "tipo": x["tipo"].lower(), "cambio_grados": _r(x["delta"], 1),
                           "lado_que_la_recibio_primero": _lado(x.get("primero"))} for x in t.get("fases_rolada", []) if x["tipo"] != "ESTABLE"],
              "presion": [{"desde_pct": x["desde_pct"], "hasta_pct": x["hasta_pct"], "tipo": x["tipo"].lower(),
                           "lado_que_la_recibio_primero": _lado(x.get("primero"))} for x in t.get("fases_presion", []) if x["tipo"] != "ESTABLE"],
              "laylines_sobrepasadas_entre_los_10_primeros": sum(1 for x in top10 if (fs[x].get("layline") or {}).get("estado") == "SOBREPASADA")}
        sets = [(fs[x].get("set") or {}).get("set") for x in top10]
        if any(sets):
            tr["set_de_los_10_primeros"] = {k: sets.count(k) for k in ("directo", "trasluchando") if sets.count(k)}
        puertas = [fs[x].get("puerta") for x in top10 if fs[x].get("puerta")]
        if puertas:
            fin = next((c for c in an["controles"] if c["id"] == t["hasta"]), {})
            tr["puerta"] = {"eleccion_de_los_10_primeros": {k.lower(): puertas.count(k) for k in ("IZQUIERDA", "DERECHA") if puertas.count(k)},
                            "favorecida": (fin.get("puerta") or {}).get("favorecida", "").lower() or None,
                            "nota": "izquierda/derecha mirando a sotavento"}
        f = fs.get(v)
        if f:
            tr["barco_de_referencia"] = {"puesto_al_final": f.get("posicion"), "lado": (f.get("tactica") or {}).get("lado"),
                                         "parcial_s": _r(f.get("parcial_s"))}
        tramos.append(tr)
    h["tramos"] = tramos
    return _limpia(h)
