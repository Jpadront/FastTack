"""Motor de análisis con datos sintéticos: viento, maniobras, layline, fases y barco fantasma."""
import math

import numpy as np
import pytest

from fasttack.motor import tramos as tm
from fasttack.motor.geo import dif
from fasttack.motor.trazas import Traza, cog
from fasttack.motor.viento import Corte, VientoTramo, calibrar_tws, fases, viento_tramo

T0 = 1_700_000_000_000
TWD = 320.0


def barco_ciñendo(nombre, tws_sog=6.0, twa=40.0, bordos_s=120, dur_s=900, dt=1.0, x0=0.0,
                  virada_lenta=None):
    """Ciñe en zigzag con TWA fijo respecto a TWD; vira cada `bordos_s` segundos."""
    ts = T0 + (np.arange(0, dur_s, dt) * 1000).astype(np.int64)
    x, y, sog = [x0], [0.0], []
    for k, t in enumerate(ts):
        s = (t - T0) / 1000
        amura = 1 if int(s // bordos_s) % 2 == 0 else -1
        rumbo_ = (TWD + amura * twa) % 360
        v = tws_sog
        if virada_lenta is not None and abs(s - virada_lenta) < 8:  # pierde velocidad en la virada
            v = tws_sog * 0.4
        sog.append(v)
        if k:
            d = v * 1852 / 3600 * dt
            x.append(x[-1] + d * math.sin(math.radians(rumbo_)))
            y.append(y[-1] + d * math.cos(math.radians(rumbo_)))
    x, y = np.array(x), np.array(y)
    n = len(ts)
    return Traza(nombre, ts, x, y, np.array(sog), np.zeros(n), np.zeros(n), np.zeros(n), cog(ts, x, y))


def viento_fijo(ceñida=True, twd=TWD):
    return VientoTramo(ceñida, T0, T0 + 900_000,
                       [Corte(T0 + k * 90_000, twd, 40.0, 6.0, 100, 1.0, "bisectriz") for k in range(10)])


def test_bisectriz_recupera_la_twd():
    trazas = {f"B{i}": barco_ciñendo(f"B{i}", bordos_s=100 + 13 * i, x0=i * 30.0) for i in range(8)}
    en = {v: (T0, T0 + 900_000) for v in trazas}
    vt = viento_tramo(trazas, en, T0, T0 + 900_000, True, ref=300.0)
    buenos = [c for c in vt.cortes if c.fuente == "bisectriz"]
    assert len(buenos) >= 8
    for c in buenos:
        assert abs(float(dif(c.twd - TWD))) < 1.0
        assert abs(c.twa_flota - 40.0) < 1.0


def test_maniobras_y_perdida():
    tr = barco_ciñendo("A", bordos_s=120, virada_lenta=240)
    mans = tm.maniobras(tr, T0, T0 + 900_000, viento_fijo())
    tiempos = [(m.t - T0) / 1000 for m in mans]
    assert len(tiempos) == 7
    assert all(abs(t - e) <= 2.5 for t, e in zip(tiempos, [120, 240, 360, 480, 600, 720, 840]))  # COG centrado: ±2 s
    perdidas = [m.perdida_m for m in mans]
    assert perdidas[0] == pytest.approx(0, abs=1.0)          # virada sin pérdida de velocidad
    assert perdidas[1] > 10                                  # virada lenta: pierde metros


def test_perdida_nula_con_huecos():
    tr = barco_ciñendo("A", bordos_s=120)
    quita = (tr.ts > T0 + 235_000) & (tr.ts < T0 + 245_000)
    for campo in ("ts", "x", "y", "sog", "hdg", "roll", "pitch", "cog"):
        setattr(tr, campo, getattr(tr, campo)[~quita])
    m = [m for m in tm.maniobras(tr, T0, T0 + 900_000, viento_fijo()) if abs(m.t - (T0 + 240_000)) < 10_000]
    assert m and m[0].perdida_m is None  # se cuenta, pero sin pérdida


def test_layline_sobrepasada_y_ok():
    # Baliza en (0, 1000). Barco en la última virada a 400 m a la derecha y 200 m por debajo:
    # con TWA 40° la layline está a 800·tan40 ≈ 671 m... a 200 m de distancia la layline cae a 168 m.
    tr = barco_ciñendo("A")
    vt = viento_fijo(twd=0.0)
    ok = tm.layline(tr, T0, T0 + 900_000, (0.0, 1000.0), vt, 40.0,
                    tm.Maniobra(T0, "virada", None, 100.0, 0.0))
    assert ok["estado"] == "OK"
    fuera = tm.layline(tr, T0, T0 + 900_000, (0.0, 1000.0), vt, 40.0,
                       tm.Maniobra(T0, "virada", None, 400.0, 800.0))
    assert fuera["estado"] == "SOBREPASADA" and fuera["lado"] == "DERECHA"
    assert fuera["metros"] == pytest.approx((400 - 200 * math.tan(math.radians(40))) * math.cos(math.radians(40)), abs=0.5)


def test_fantasma_sin_rolada_es_el_zigzag_teorico():
    vt = viento_fijo(twd=0.0)
    assert tm.fantasma(1000.0, vt, 0.0, 40.0) == pytest.approx(1000 / math.cos(math.radians(40)), abs=0.5)
    # con rolada de 10° en todos los cortes, el fantasma aprovecha la amura favorecida
    vt2 = viento_fijo(twd=10.0)
    assert tm.fantasma(1000.0, vt2, 0.0, 40.0) < 1000 / math.cos(math.radians(40))


def test_fases_de_rolada():
    f = fases([320, 320.5, 321, 324, 327, 330, 330, 330.5, 330, 329.8], 3.0,
              ("PROGRESIVA DERECHA", "PROGRESIVA IZQUIERDA", "ESTABLE"), circular=True)
    tipos = [x["tipo"] for x in f]
    assert "PROGRESIVA DERECHA" in tipos and tipos[-1] == "ESTABLE"
    # fases contiguas que cubren el tramo entero
    assert f[0]["desde_pct"] == 0 and f[-1]["hasta_pct"] == 100
    assert all(a["hasta_pct"] == b["desde_pct"] for a, b in zip(f, f[1:]))


def test_calibrar_tws_con_referencia():
    c1 = viento_fijo()
    for k, c in enumerate(c1.cortes):
        c.sog_mediana = 6.0 if k < 5 else 6.6
    calibrar_tws([c1], 12.0)
    assert c1.cortes[0].tws == 12.0 and c1.cortes[-1].tws == pytest.approx(13.2)
    c2 = viento_fijo()
    calibrar_tws([c2], None)
    assert c2.cortes[0].tws is None
