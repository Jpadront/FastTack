import numpy as np

from fasttack.motor.escora import optima

RNG = np.random.default_rng(5)


def segs(perdida_por_grado, optimo=17.0, n=900):
    """Segmentos de 30 s de 20 barcos: VMG = 4,5 kn × (1 − pérdida por grado × |escora − óptimo|) + ruido."""
    out = []
    for k in range(n):
        h = RNG.uniform(8, 24)
        vmg = 4.5 * (1 - perdida_por_grado * abs(h - optimo)) + RNG.normal(0, 0.05)
        out.append((f"B{k % 20}", 1000 * k, h, vmg, RNG.uniform(0, 200), RNG.uniform(0, 200), 1.0, vmg / 0.77))
    return out


def test_encuentra_el_optimo():
    o = optima(segs(0.01))
    assert o["concluyente"]
    assert o["rango"][0] <= 17 <= o["rango"][1] and o["rango"][1] - o["rango"][0] <= 10
    assert o["debajo"]["perdida_pct"] >= 1 and o["encima"]["perdida_pct"] >= 1
    assert o["mejor"][0] <= 17 <= o["mejor"][1] + 2


def test_sin_efecto_no_es_concluyente():
    o = optima(segs(0.0))
    assert not o["concluyente"]


def test_pocos_datos():
    assert optima(segs(0.01, n=30)) is None


def test_combinar_ceñidas():
    from fasttack.motor.escora import combinar
    a, b = optima(segs(0.01)), optima(segs(0.01))
    c = combinar([a["franjas"], b["franjas"]])
    assert c["ceñidas"] == 2 and c["segmentos"] == a["segmentos"] + b["segmentos"]
    assert c["rango"][0] <= 17 <= c["rango"][1]


def test_optima_propia_un_solo_barco():
    """Sin flota: la VMG de cada segmento frente a la del mismo barco en su amura a ±2,5 min."""
    from fasttack.motor import escora as esc
    segs = []
    for k in range(30):
        t = k * 30_000
        h = 12 + (k % 3) * 2            # 12, 14, 16°
        vmg = 4.0 * (1.03 if h == 14 else 1.0)   # 14° es la mejor
        segs.append(("ESP1", t, h + 0.5, vmg, 0.0, 0.0, 1.0 if (k // 6) % 2 else -1.0, 5.5, 40.0))
    c = esc.optima_propia(segs)
    assert c is not None and c["propia"]
    assert c["mejor"] == [14, 16]
    assert all(f["barcos"] == 1 for f in c["franjas"])


def test_orientativa_con_muy_pocos_datos():
    """Con 6 segmentos de un barco sigue saliendo una curva (orientativa) para dar una idea."""
    from fasttack.motor import escora as esc
    h = [15.8, 16.0, 16.6, 16.9, 16.9, 18.3]
    segs = [("ESP1", k * 30_000, e, 4.0 + 0.05 * k, 0.0, 0.0, 1.0, 5.5, 40.0) for k, e in enumerate(h)]
    assert esc.optima_propia(segs) is None
    c = esc.orientativa(segs)
    assert c is not None and c["orientativa"] and c["propia"]
    assert len(c["franjas"]) >= 2


def test_semaforo_de_datos():
    """Percentil de VMG frente a la flota: 20 % de arriba bien, del 20 al 50 % normal, mitad de abajo mal."""
    from fasttack.motor.semaforo import semaforo
    rd = {f"B{k}": {"vmg_ceñida": 4.0 + k * 0.1, "vmg_popa": 6.0 + k * 0.1} for k in range(10)}
    assert semaforo({"rendimiento": rd}, "B9")["nivel"] == "bien"
    assert semaforo({"rendimiento": rd}, "B5")["nivel"] == "normal"
    assert semaforo({"rendimiento": rd}, "B0")["nivel"] == "mal"
    assert semaforo({"rendimiento": rd}, "B8")["nivel"] == "bien"      # más VMG que el 89 %
    assert semaforo({"rendimiento": rd}, "B7")["nivel"] == "normal"    # 78 %
    assert semaforo({"rendimiento": rd}, "B4")["nivel"] == "mal"       # 44 %
    assert semaforo({"rendimiento": {"B0": rd["B0"]}}, "B0") is None


def test_reglajes_con_semaforo():
    """La comparación de reglajes cuenta cuántas pruebas fueron bien, normal y mal con cada valor."""
    from fasttack.temporada import comparar_reglajes
    base = {"franja": "8–12 kn", "vmg_ceñida_frente_top5": 0.1, "vmg_popa_frente_top5": None, "puesto_relativo": 0.3}
    filas = [{**base, "reglaje": {"Backstay": "3"}, "semaforo": {"nivel": "bien"}},
             {**base, "reglaje": {"Backstay": "3"}, "semaforo": {"nivel": "normal"}},
             {**base, "reglaje": {"Backstay": "5"}, "semaforo": {"nivel": "mal"}},
             {**base, "reglaje": {"Backstay": "5"}, "semaforo": None}]
    r = {x["valor"]: x["semaforo"] for x in comparar_reglajes(filas)}
    assert r["3"] == {"bien": 1, "normal": 1, "mal": 0}
    assert r["5"] == {"bien": 0, "normal": 0, "mal": 1}


def test_forma_giro_registro_denso_y_disperso():
    """Giro sintético de 90° en 6 s: lento al principio (25 % en la 1.ª mitad), con 8° de pasada."""
    import numpy as np
    from fasttack.motor.tramos import forma_giro
    t = np.arange(-10, 20, 0.5)
    f = np.clip(t / 6, 0, 1)
    ang = 90 * f ** 2                                   # lento al principio, rápido al final
    ang = np.where((t > 6) & (t <= 10), 90 + 8 * np.sin((t - 6) / 4 * np.pi), ang)
    rumbo = (100 + ang) % 360
    sog = 5 - 2 * np.exp(-((t - 7) ** 2) / 4)
    k0, k1 = int(np.searchsorted(t, 0.5)), int(np.searchsorted(t, 6))
    d = forma_giro(t, rumbo, 100.0, 90.0, k0, k1, sog, len(t) - 1)
    assert 15 <= d["giro_primera_mitad_pct"] <= 35
    assert 6 <= d["pasada_grados"] <= 9
    assert 0 < d["sog_minima_tras_giro_s"] <= 2
    # telemetría dispersa (1,3 s): no se da forma
    t2 = np.arange(-10, 20, 1.3)
    r2 = (100 + 90 * np.clip(t2 / 6, 0, 1)) % 360
    assert forma_giro(t2, r2, 100.0, 90.0, int(np.searchsorted(t2, 0.5)), int(np.searchsorted(t2, 6)), np.full(len(t2), 5.0), len(t2) - 1) == {}
