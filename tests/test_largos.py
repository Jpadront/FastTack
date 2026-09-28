"""Recorrido con largos: detección de la baliza de ala (motor/recorrido._alas)."""
import numpy as np

from fasttack.motor.pistas import Pista
from fasttack.motor.recorrido import Control, Paso, _alas
from fasttack.motor.trazas import Traza, cog

T0 = 1_700_000_000_000


def _barco(nombre, puntos, sog_kn=8.0, dt=1.0, ruido=0.0, rng=None):
    """Traza que recorre los puntos en línea recta a velocidad constante."""
    xs, ys = [puntos[0][0]], [puntos[0][1]]
    v = sog_kn * 1852 / 3600 * dt
    for (x0, y0), (x1, y1) in zip(puntos, puntos[1:]):
        n = max(1, int(np.hypot(x1 - x0, y1 - y0) / v))
        for k in range(1, n + 1):
            xs.append(x0 + (x1 - x0) * k / n + (rng.normal(0, ruido) if rng is not None else 0))
            ys.append(y0 + (y1 - y0) * k / n + (rng.normal(0, ruido) if rng is not None else 0))
    x, y = np.array(xs), np.array(ys)
    ts = T0 + (np.arange(len(x)) * dt * 1000).astype(np.int64)
    n = len(ts)
    return Traza(nombre, ts, x, y, np.full(n, sog_kn), np.full(n, np.nan), np.zeros(n), np.zeros(n), cog(ts, x, y))


def _recorrido(trazas):
    a, b = (0.0, 1000.0), (0.0, 0.0)
    barl = Control("b1", "Baliza 1", "barlovento", "atlas", [(None, Pista.constante(*a))], T0)
    sota = Control("s1", "Sotavento", "sotavento", "estimada", [(None, Pista.constante(*b))], T0 + 600_000)
    pasos = {v: {"b1": Paso(int(tr.ts[0]), *a), "s1": Paso(int(tr.ts[-1]), *b)} for v, tr in trazas.items()}
    return [barl, sota], pasos


def test_triangulo_con_largos():
    rng = np.random.default_rng(1)
    # dos largos por una baliza de ala a 700 m del eje (rumbos 234° y 126°, a 54° de la popa)
    trazas = {f"B{k}": _barco(f"B{k}", [(0, 1000), (-700 + rng.normal(0, 15), 500 + rng.normal(0, 15)), (0, 0)], rng=rng)
              for k in range(10)}
    controles, pasos = _recorrido(trazas)
    avisos = []
    out = _alas(trazas, controles, pasos, 0.0, {}, 20.0, avisos)
    assert [c.tipo for c in out] == ["barlovento", "ala", "sotavento"]
    x, y = out[1].puntos[0][1].en(np.array([T0]))
    assert abs(x[0] + 700) < 60 and abs(y[0] - 500) < 60
    assert all("a1" in p for p in pasos.values()) and avisos


def test_popa_trasluchando_en_la_layline_no_es_un_largo():
    rng = np.random.default_rng(2)
    # toda la flota baja por la izquierda y traslucha en la layline (rumbos a unos 27° de la popa)
    trazas = {f"B{k}": _barco(f"B{k}", [(0, 1000), (-250 + rng.normal(0, 15), 500 + rng.normal(0, 15)), (0, 0)], rng=rng)
              for k in range(10)}
    controles, pasos = _recorrido(trazas)
    out = _alas(trazas, controles, pasos, 0.0, {}, 20.0, [])
    assert [c.tipo for c in out] == ["barlovento", "sotavento"]
