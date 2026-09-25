"""Motivo del sobrepaso de la layline con una flota sintética (viento del norte, baliza en (0, 1000))."""
import numpy as np

from fasttack.motor.trafico import Rejilla, analizar
from fasttack.motor.trazas import Traza, cog

MARCA = (0.0, 1000.0)
CENTRO, SEMI = 0.0, 40.0          # amuras a 320° y 040°


def traza(v, puntos):
    """puntos: lista de (t_s, x, y) cada 1 s."""
    ts = np.array([p[0] * 1000 for p in puntos], dtype=np.int64)
    x = np.array([p[1] for p in puntos], float)
    y = np.array([p[2] for p in puntos], float)
    z = np.zeros(len(ts))
    return Traza(v, ts, x, y, np.full(len(ts), 6.0), z, z, z, cog(ts, x, y))


def recta(t0, t1, x0, y0, rumbo, v=3.0):
    r = np.radians(rumbo)
    return [(t, x0 + np.sin(r) * v * (t - t0), y0 + np.cos(r) * v * (t - t0)) for t in range(t0, t1 + 1)]


def barco_que_se_pasa():
    # navega a 040° desde la izquierda, cruza la layline de la amura 320° y vira tarde (t = 120 s)
    return traza("A", recta(0, 120, -100, 300, 40, v=5.0))


def test_calculo_sin_nadie_cerca():
    trazas = {"A": barco_que_se_pasa()}
    r = analizar(Rejilla(trazas, 0, 120_000), "A", MARCA, CENTRO, SEMI, 0, 120_000, 21.0)
    assert r["motivo"] == "calculo" and r["segundos_hasta_virar"] > 0


def test_no_podia_virar_con_un_barco_a_barlovento():
    a = barco_que_se_pasa()
    # B navega en paralelo, 12 m a su izquierda-proa (hacia donde tendría que virar A)
    b = traza("B", [(t, x - 8, y + 9) for t, x, y in zip(a.ts // 1000, a.x, a.y)])
    r = analizar(Rejilla({"A": a, "B": b}, 0, 120_000), "A", MARCA, CENTRO, SEMI, 0, 120_000, 21.0)
    assert r["motivo"] == "no_podia_virar"


def test_layline_ocupada():
    a = barco_que_se_pasa()
    otros = {}
    for n in range(4):   # 4 barcos ya en la layline de 320°, entre A y la baliza
        d = 150 + 60 * n
        x0, y0 = MARCA[0] + np.sin(np.radians(140)) * d, MARCA[1] + np.cos(np.radians(140)) * d
        otros[f"L{n}"] = traza(f"L{n}", recta(0, 120, x0 - np.sin(np.radians(320)) * 220, y0 - np.cos(np.radians(320)) * 220, 320, v=2.0))
    r = analizar(Rejilla({"A": a, **otros}, 0, 120_000), "A", MARCA, CENTRO, SEMI, 0, 120_000, 21.0)
    assert r["motivo"] == "layline_con_trafico" and r["barcos_en_layline"] >= 3
