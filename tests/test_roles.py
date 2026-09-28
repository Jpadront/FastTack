"""Roles locales: el viento en el sitio de cada barco a partir del rumbo de la flota."""
import numpy as np

import tests.test_motor as base
from fasttack.motor import roles
from fasttack.motor.geo import dif


def _flota(twd, x0, n=4):
    viejo = base.TWD
    base.TWD = twd
    try:
        return {f"B{twd:.0f}_{i}": base.barco_ciñendo(f"B{twd:.0f}_{i}", bordos_s=100 + 13 * i, x0=x0 + i * 40.0)
                for i in range(n)}
    finally:
        base.TWD = viejo


def test_sin_roles_el_viento_local_es_el_de_los_cortes():
    trazas = _flota(base.TWD, 0.0)
    en = {v: (base.T0, base.T0 + 900_000) for v in trazas}
    vl = roles.viento_local(trazas, en, base.viento_fijo(), {}, True)
    assert len(vl) == len(trazas)
    for ts, tw in vl.values():
        assert np.all(np.abs(dif(tw - base.TWD)) < 1.5)


def test_ve_un_role_local():
    # dos grupos lejos (5 km): uno con el viento 10° rolado a la derecha; los cortes dan el del primero
    trazas = _flota(base.TWD, 0.0) | _flota(base.TWD + 10, 5000.0)
    en = {v: (base.T0, base.T0 + 900_000) for v in trazas}
    vl = roles.viento_local(trazas, en, base.viento_fijo(), {}, True)
    for v, (ts, tw) in vl.items():
        esperado = base.TWD + 10 if v.startswith(f"B{base.TWD + 10:.0f}") else base.TWD
        assert abs(float(np.median(dif(tw - esperado)))) < 2.0, v
