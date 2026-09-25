from fasttack.motor.resumen import general, puntuar_prueba, resumen, descartes_por_defecto


def prueba(clave, orden, ocs=(), fiable=True, numero=1, viento=None):
    return {"clave": clave, "numero": numero, "estado": "oficial", "viento_kn": viento,
            "llegadas": {v: 1000 + k for k, v in enumerate(orden)}, "ocs": list(ocs), "ocs_fiable": fiable}


INSCRITOS = ["A", "B", "C", "D"]


def test_puntuar_ocs_y_sin_llegada():
    p = puntuar_prueba(prueba("1", ["A", "B", "C"], ocs=["A"]), INSCRITOS)
    # A es OCS: sale de la llegada y los demás suben; D no llega. Penalización = inscritos + 1
    assert p == {"A": (5, "OCS"), "B": (1, None), "C": (2, None), "D": (5, "DNF")}


def test_ocs_no_fiable_no_se_aplica():
    p = puntuar_prueba(prueba("1", ["A", "B"], ocs=["A"], fiable=False), INSCRITOS)
    assert p["A"] == (1, None)


def test_general_con_descarte_y_desempate():
    ps = [prueba("1", ["A", "B", "C", "D"]), prueba("2", ["B", "A", "D", "C"]), prueba("3", ["D", "C", "B", "A"])]
    g = general(ps, INSCRITOS, 1)
    por = {f["vela"]: f for f in g}
    # A: 1+2+4 -> descarta 4 -> 3; B: 2+1+3 -> descarta 3 -> 3. Empate: A8.1 (1,2) == (1,2);
    # A8.2: última prueba A=4, B=3 -> gana B
    assert por["A"]["neto"] == por["B"]["neto"] == 3
    assert [f["vela"] for f in g][:2] == ["B", "A"]
    assert por["A"]["puntos"][2]["desc"] and not por["A"]["puntos"][0]["desc"]


def test_descartes_por_defecto():
    assert descartes_por_defecto(3) == 0 and descartes_por_defecto(4) == 1


def analisis_min(velas):
    return {
        "controles": [{"id": "s1", "puerta": {"favorecida": "DERECHA", "ventaja_m": 8.0}}],
        "pasos": {v: {"s1": {"puerta": "DERECHA" if k % 2 == 0 else "IZQUIERDA"}} for k, v in enumerate(velas)},
        "salida": {"barcos": {v: {"margen_m": -5.0 - k, "pos_60": k + 1, "en_salida": True} for k, v in enumerate(velas)}},
        "tramos": [{"barcos": {v: {"layline": {"estado": "OK" if k else "SOBREPASADA", "metros": 40.0}} for k, v in enumerate(velas)}}],
        "rendimiento": {v: {"vmg_ceñida": 4.0 + k / 10, "vmg_popa": 5.0, "cobertura": 0.9} for k, v in enumerate(velas)},
    }


def test_resumen_agrega_pruebas_analizadas():
    ps = [prueba("1", ["A", "B", "C", "D"], numero=1, viento=8.0), prueba("2", ["B", "A", "C", "D"], numero=2, viento=12.0)]
    r = resumen(ps, INSCRITOS, {"1": analisis_min(INSCRITOS)}, None)
    assert r["pendientes"] == ["2"] and r["descartes"] == 0
    a = r["barcos"]["A"]
    assert a["por_prueba"][1] is None and a["totales"]["analizadas"] == 1
    assert a["totales"]["laylines"] == {"ok": 0, "sobrepasadas": 1, "metros": 40.0, "por_trafico": 0}
    assert a["totales"]["puertas"] == {"buenas": 1, "total": 1}
    assert a["totales"]["salida"]["top10_60"] == 1
    # D tiene el mejor VMG en ceñida de la prueba 1
    assert r["barcos"]["D"]["por_prueba"][0]["rango"]["vmg_ceñida"] == {"pos": 1, "de": 4}
    assert r["pruebas"][0]["flota"]["vmg_ceñida"] == 4.15
    v = {x["tramo"]: x for x in a["totales"]["viento"]}
    assert v["< 10 kn"]["pruebas"] == 1 and v["10–15 kn"]["pruebas"] == 0


def test_recorrido_dudoso_no_entra_en_las_metricas():
    ps = [prueba("1", ["A", "B", "C", "D"])]
    an = analisis_min(INSCRITOS) | {"recorrido_dudoso": True}
    r = resumen(ps, INSCRITOS, {"1": an}, None)
    assert r["pendientes"] == [] and r["pruebas"][0]["recorrido_dudoso"]
    assert r["barcos"]["A"]["por_prueba"] == [None] and r["general"][0]["vela"] == "A"
