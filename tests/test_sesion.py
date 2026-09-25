"""Sesiones propias con archivos .vkx: un barco solo en un barlovento-sotavento sintético."""
import struct

import numpy as np
import pytest

from fasttack import servicio
from fasttack.ingesta import sesion, vkx
from fasttack.ingesta.almacen import Almacen
from fasttack.motor.pistas import Proyeccion
from fasttack.motor.viento import viento_tramo

T0 = 1_746_871_200_000          # 10/05/2025 10:00 UTC
SENAL = T0 + 300_000
PROY = Proyeccion(41.37, 2.21)
TWD = 100.0                      # viento del este
KN = 1852 / 3600


def _recorrido():
    """2 Hz: 5 min de espera junto a la línea, 2 vueltas de 900 m (ceñida a TWA 45°, popa a 150°),
    llegada a sotavento y 10 min parado. Devuelve (ts, x, y, sog_kn, rumbo) y la hora de llegada."""
    ts, x, y, sog, rum = [], [], [], [], []
    px, py, t = 0.0, 0.0, T0
    ux, uy = np.sin(np.radians(TWD)), np.cos(np.radians(TWD))   # hacia barlovento

    def paso(r, v):
        nonlocal px, py, t
        ts.append(t); x.append(px); y.append(py); sog.append(v); rum.append(r % 360)
        px += v * KN * 0.5 * np.sin(np.radians(r)); py += v * KN * 0.5 * np.cos(np.radians(r)); t += 500

    while t < SENAL:                                  # espera cerca de la línea
        paso(TWD + 90 if (t // 30_000) % 2 else TWD - 90, 1.0)
    px, py = 0.0, 0.0
    for _ in range(2):
        k = 0
        while px * ux + py * uy < 900:               # ceñida: bordos de 90 s
            paso(TWD + (45 if (k // 180) % 2 == 0 else -45), 5.0); k += 1
        k = 0
        while px * ux + py * uy > 0:                 # popa: trasluchadas cada 120 s
            paso(TWD + 180 + (30 if (k // 240) % 2 == 0 else -30), 6.0); k += 1
    llegada = t
    for _ in range(1200):                             # parado tras llegar
        paso(TWD, 0.3)
    return np.array(ts), np.array(x), np.array(y), np.array(sog), np.array(rum), llegada


def _vkx(ts, x, y, sog, rum):
    b = bytes([0xFF]) + bytes(7)
    b += bytes([0x05]) + struct.pack("<QBff", SENAL - 200_000, 0, *PROY.latlon(-60 * np.cos(np.radians(TWD)), 60 * np.sin(np.radians(TWD))))
    b += bytes([0x05]) + struct.pack("<QBff", SENAL - 190_000, 1, *PROY.latlon(60 * np.cos(np.radians(TWD)), -60 * np.sin(np.radians(TWD))))
    b += bytes([0x04]) + struct.pack("<QBi", SENAL, 3, 0)
    for t, xx, yy, s, r in zip(ts, x, y, sog, rum):
        lat, lon = PROY.latlon(xx, yy)
        h = np.radians(r) / 2
        b += bytes([0x02]) + struct.pack("<Qiifff4f", int(t), round(lat * 1e7), round(lon * 1e7), s * KN,
                                         np.radians(r), 0.0, np.cos(h), 0.0, 0.0, np.sin(h))
    return b


@pytest.fixture(scope="module")
def datos():
    return _recorrido()


def test_sesion_de_un_barco(tmp_path, datos):
    ts, x, y, sog, rum, llegada = datos
    alm = Almacen(tmp_path)
    sid = sesion.crear(alm, "Entreno", "J/70", "Europe/Madrid")["id"]
    camp = sesion.añadir_vkx(alm, sid, _vkx(ts, x, y, sog, rum), "ESP 1214", "Monjo II", "a.vkx")
    assert camp["fuente"] == "vkx" and camp["tz_offset_ms"] == 2 * 3600_000
    (p,) = camp["pruebas"]
    assert p["senal"] == SENAL and p["estado"] == "estimada" and p["numero"] == 1
    assert abs(p["llegadas"]["ESP1214"] - llegada) <= 10_000
    an = servicio.analisis_prueba(alm, sid, p["clave"])
    assert [t["nombre"] for t in an["tramos"]] == ["Ceñida 1", "Popa 1", "Ceñida 2", "Popa 2"]
    assert an["tramos"][0]["viento"]["twd_media"] == pytest.approx(TWD, abs=3)
    with pytest.raises(ValueError):   # el mismo archivo dos veces
        sesion.añadir_vkx(alm, sid, _vkx(ts, x, y, sog, rum), "ESP 1214")


def test_viento_por_amuras_con_un_barco(datos):
    from fasttack.motor.trazas import construir
    ts, x, y, sog, rum, _ = datos
    lat, lon = PROY.latlon(x, y)
    cols = vkx.a_columnas({"posiciones": np.column_stack([ts, lat * 1e7, lon * 1e7, sog * KN, np.radians(rum),
                                                           np.zeros(len(ts)), np.ones(len(ts)), np.zeros((len(ts), 3))])}, "X")
    tr = construir(cols, PROY)["X"]
    fin_c1 = int(ts[np.argmax((ts > SENAL) & (sog == 6.0))])
    vt = viento_tramo({"X": tr}, {"X": (SENAL, fin_c1)}, SENAL, fin_c1, True, TWD + 20)
    assert {c.fuente for c in vt.cortes} == {"amuras"}
    assert all(abs((c.twd - TWD + 180) % 360 - 180) < 3 for c in vt.cortes)
    assert vt.cortes[0].twa_flota == pytest.approx(45, abs=2)


def test_linea_con_pings():
    pings = [(1000, 0, 41.0, 2.0), (2000, 1, 41.001, 2.001), (5000, 0, 41.002, 2.0)]
    assert sesion._linea(pings, 4000) == {"leftEnd": [41.0, 2.0], "rightEnd": [41.001, 2.001], "fuente": "pings del Atlas"}
    assert sesion._linea(pings[:1], 4000) is None
    assert sesion._agrupar([10, 20, 200_000], 60_000) == [15, 200_000]
