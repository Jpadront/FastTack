import numpy as np

from fasttack.motor.escora import optima

RNG = np.random.default_rng(5)


def segs(perdida_por_grado, optimo=17.0, n=900):
    """Segmentos de 30 s de 20 barcos: VMG = 4,5 kn × (1 − pérdida por grado × |escora − óptimo|) + ruido."""
    out = []
    for k in range(n):
        h = RNG.uniform(8, 24)
        vmg = 4.5 * (1 - perdida_por_grado * abs(h - optimo)) + RNG.normal(0, 0.05)
        out.append((f"B{k % 20}", 1000 * k, h, vmg, RNG.uniform(0, 200), RNG.uniform(0, 200)))
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
