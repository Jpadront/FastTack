"""La corriente se recupera de una flota sintética con desvíos de brújula y abatimiento conocidos."""
import numpy as np

from fasttack.motor.corriente import estimar
from fasttack.motor.trazas import Traza

RNG = np.random.default_rng(3)


def flota(c_este, c_norte, n=14, twd=0.0, abat=4.0, desvios=None, stw=(5.5, 8.0)):
    """Cada barco: ceñida (dos amuras) y popa (dos trasluchadas), 1 muestra/s, sin huecos."""
    trazas, t_ceñ, t_pop = {}, {}, {}
    c = np.array([c_este, c_norte])
    for b in range(n):
        delta = desvios[b] if desvios is not None else RNG.normal(0, 2)
        ts, cog, sog, hdg = [], [], [], []
        t = 0
        for fase, (twa, v) in enumerate(((42, stw[0]), (145, stw[1]))):
            for lado in (1, -1):
                for _ in range(200):
                    rumbo_agua = twd + lado * twa + (lado * abat if fase == 0 else 0)   # el abatimiento aleja del viento
                    agua = v * np.array([np.sin(np.radians(rumbo_agua)), np.cos(np.radians(rumbo_agua))])
                    g = agua + c + RNG.normal(0, 0.05, 2)
                    rumbo_proa = twd + lado * twa
                    ts.append(t); t += 1000
                    cog.append(np.degrees(np.arctan2(g[0], g[1])) % 360)
                    sog.append(float(np.hypot(*g)))
                    hdg.append((rumbo_proa - delta + RNG.normal(0, 1)) % 360)
            if fase == 0:
                t_ceñ[f"B{b}"] = (0, t - 1000)
                inicio_popa = t
            else:
                t_pop[f"B{b}"] = (inicio_popa, t - 1000)
        z = np.zeros(len(ts))
        trazas[f"B{b}"] = Traza(f"B{b}", np.array(ts), z, z, np.array(sog), np.array(hdg), z, z, np.array(cog))
    tramos = [{"ceñida": True, "avance": twd, "barcos": {k: (a - 30_000, b + 30_000) for k, (a, b) in t_ceñ.items()}},
              {"ceñida": False, "avance": (twd + 180) % 360, "barcos": {k: (a - 30_000, b + 30_000) for k, (a, b) in t_pop.items()}}]
    return trazas, tramos


def test_recupera_la_corriente():
    trazas, tramos = flota(0.4, -0.3)
    c = estimar(trazas, tramos)
    assert abs(c.este_kn - 0.4) < 0.12 and abs(c.norte_kn + 0.3) < 0.12
    assert abs(c.abatimiento_grados - 4) < 1.5
    assert c.confianza in ("alta", "media")


def test_sin_corriente_da_casi_cero():
    trazas, tramos = flota(0.0, 0.0)
    c = estimar(trazas, tramos)
    assert c.velocidad_kn < 0.12


def test_descarta_brujulas_estropeadas():
    desvios = [0, 1, -1, 2, -2, 0.5, -0.5, 1.5, -1.5, 0, 1, -1, 60, 0]
    trazas, tramos = flota(0.3, 0.0, desvios=desvios)
    c = estimar(trazas, tramos)
    assert "B12" in c.brujulas_descartadas
    assert abs(c.este_kn - 0.3) < 0.12


def test_sin_popa_no_estima():
    trazas, tramos = flota(0.3, 0.0)
    assert estimar(trazas, tramos[:1]) is None
