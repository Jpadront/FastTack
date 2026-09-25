"""Detección de salida y llegada con una flota sintética."""
import numpy as np

from fasttack.motor.deteccion import detectar_llegadas, detectar_senal
from fasttack.motor.pistas import Pista

SENAL = 1_000_000_000_000 // 60_000 * 60_000
PIN, COMITE = Pista.constante(0, 0), Pista.constante(300, 0)        # línea de salida en y = 0
L1, L2 = Pista.constante(0, -500), Pista.constante(300, -500)        # llegada en y = -500


def flota(n=30, llegada=True):
    """Barcos bajo la línea hasta la señal; cruzan (y = 0) entre 5 y 40 s después; suben a
    barlovento y vuelven para cruzar la llegada (y = -500) empezando a los 50 min, 10 s entre barcos."""
    barcos = {}
    for i in range(n):
        t = np.arange(SENAL - 300_000, SENAL + 3_600_000, 1000)
        cruce_s = SENAL + 5_000 + i * 1_200
        y = np.where(t < cruce_s, -20 + (t - SENAL) / 100_000, 1 + (t - cruce_s) / 1000 * 2.5)
        y = np.minimum(y, 1500)
        if llegada:
            vuelta = SENAL + 3_000_000 + i * 10_000
            y = np.where(t > vuelta - 600_000, 1499.5 - (t - (vuelta - 600_000)) / 1000 * (2000 / 600), y)
        barcos[f"B{i}"] = Pista(t, np.full(len(t), 10.0 + i * 9), y)
    return barcos


def test_senal_detectada_al_minuto():
    s, n = detectar_senal(flota(), PIN, COMITE, SENAL - 600_000, SENAL + 1_800_000, minimo_barcos=10)
    assert s == SENAL + 60_000 or s == SENAL  # la ráfaga empieza justo tras la señal
    assert n >= 25


def test_sin_rafaga_no_hay_salida():
    assert detectar_senal(flota(n=3), PIN, COMITE, SENAL - 600_000, SENAL + 1_800_000, 10) is None


def test_llegadas_en_orden():
    det = detectar_llegadas(flota(), L1, L2, SENAL + 1_200_000, SENAL + 3_600_000)
    orden = sorted(det.tiempos, key=det.tiempos.get)
    assert orden[:3] == ["B0", "B1", "B2"]
    assert len(det.tiempos) == 30
    assert det.parece_llegada(minimo_barcos=15)


def test_pista_con_muestras_caduca_y_la_constante_no():
    p = Pista(np.array([0, 1000]), np.array([0.0, 1.0]), np.array([0.0, 1.0]))
    x, _ = p.en(np.array([500, 1000 + 16 * 60_000]))
    assert x[0] == 0.0 and np.isnan(x[1])
    x, _ = PIN.en(np.array([SENAL + 10**9]))
    assert x[0] == 0.0
