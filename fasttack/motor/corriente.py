"""Corriente estimada de una prueba (sin corredera: todo sale del GPS y de la brújula del Atlas).

Método principal (brújula): para cada barco, tramo y amura, la diferencia COG − HDG mezcla tres cosas:
    COG − HDG = δ_barco + abatimiento (solo en ceñida, de signo opuesto en cada amura) + (c · n(rumbo)) / SOG
donde δ_barco es el desvío fijo de la brújula de ese barco (montaje, magnético/verdadero), c la
corriente y n(rumbo) el vector unitario 90° a la derecha del rumbo. Con toda la flota navegando en
cuatro rumbos (dos amuras en ceñida y dos en popa) se resuelve por mínimos cuadrados c (2), el
abatimiento y un δ por barco (con suma cero). Se descartan las brújulas con desvíos > 15° y las
observaciones anómalas, y se vuelve a resolver.

Comprobación independiente (velocidades iguales): en ceñida, un barco va igual de rápido por el agua
en las dos amuras; si sobre el fondo una va más rápida, la diferencia es la corriente transversal al
eje. Si las dos estimaciones de la componente transversal coinciden, la confianza es alta.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .trazas import Traza

DESVIO_MAX = np.radians(15)   # brújulas con más desvío: fuera
MIN_BARCOS = 8
MIN_MUESTRAS = 10
MARGEN_RODEO_MS = 20_000


_GEOMAG = None


def declinacion(lat: float, lon: float, ms: int) -> float:
    """Declinación magnética (° E +) con el modelo magnético mundial WMM 2025 (válido 2025–2030)."""
    global _GEOMAG
    import datetime as dt
    from pygeomag import GeoMag
    if _GEOMAG is None:
        _GEOMAG = GeoMag(coefficients_file="wmm/WMM_2025.COF")
    d = dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc)
    inicio = dt.datetime(d.year, 1, 1, tzinfo=dt.timezone.utc)
    año = d.year + (d - inicio).total_seconds() / (365.25 * 86400)
    try:
        return float(_GEOMAG.calculate(glat=lat, glon=lon, alt=0, time=año).d)
    except Exception:  # noqa: BLE001 - fuera del periodo del modelo: sin corrección
        return 0.0


def _wrap(a):
    return (a + 180) % 360 - 180


def _u(grados):
    r = np.radians(grados)
    return np.array([np.sin(r), np.cos(r)])


@dataclass
class Corriente:
    este_kn: float
    norte_kn: float
    eje_grados: float                 # rumbo de la primera ceñida (hacia barlovento)
    a_favor_kn: float                 # componente hacia barlovento (+) / sotavento (−) a lo largo del eje
    derecha_kn: float                 # componente hacia la derecha del eje, mirando a barlovento
    abatimiento_grados: float
    barcos: int
    residuo_grados: float
    transversal_velocidades_kn: float | None   # comprobación independiente
    confianza: str                    # 'alta', 'media' o 'baja'
    brujulas_descartadas: list = field(default_factory=list)
    desvios: dict = field(default_factory=dict)   # vela → grados que hay que sumar a su HDG para el rumbo verdadero
    declinacion_grados: float = 0.0

    @property
    def velocidad_kn(self) -> float:
        return float(np.hypot(self.este_kn, self.norte_kn))

    @property
    def hacia_grados(self) -> float:
        return float(np.degrees(np.arctan2(self.este_kn, self.norte_kn)) % 360)

    def a_dict(self) -> dict:
        r = lambda x, d=2: None if x is None else round(float(x), d)
        return {"velocidad_kn": r(self.velocidad_kn), "hacia_grados": r(self.hacia_grados, 0),
                "este_kn": r(self.este_kn), "norte_kn": r(self.norte_kn),
                "a_favor_kn": r(self.a_favor_kn), "derecha_kn": r(self.derecha_kn),
                "abatimiento_grados": r(self.abatimiento_grados, 1), "barcos": self.barcos,
                "residuo_grados": r(self.residuo_grados, 1),
                "transversal_velocidades_kn": r(self.transversal_velocidades_kn),
                "confianza": self.confianza, "brujulas_descartadas": self.brujulas_descartadas}

    def a_dict_brujulas(self) -> dict:
        return {"declinacion_grados": round(self.declinacion_grados, 1),
                "desvios_grados": {v: round(d, 1) for v, d in sorted(self.desvios.items())}}


def _observaciones(trazas: dict[str, Traza], tramos: list[dict]):
    """(vela, ceñida, lado, COG−HDG en rad, rumbo medio, SOG mediana) por barco, tramo y amura."""
    obs = []
    for t in tramos:
        ce = t["ceñida"]
        for v, (e, s) in t["barcos"].items():
            x = trazas.get(v)
            if x is None:
                continue
            i = x.tramo(e + MARGEN_RODEO_MS, s - MARGEN_RODEO_MS)
            i = i[(x.sog[i] > (2.5 if ce else 3.0)) & ~np.isnan(x.cog[i]) & ~np.isnan(x.hdg[i])]
            rel = _wrap(x.cog[i] - t["avance"])
            for lado in (1, -1):
                j = i[rel * lado > 0]
                if len(j) < MIN_MUESTRAS:
                    continue
                d = np.radians(np.median(_wrap(x.cog[j] - x.hdg[j])))
                r = np.radians(x.cog[j])
                h = float(np.degrees(np.arctan2(np.sin(r).mean(), np.cos(r).mean())))
                obs.append((v, ce, lado, float(d), h, float(np.median(x.sog[j]))))
    return obs


def _resolver(obs, desvio_medio: float = 0.0):
    velas = sorted({o[0] for o in obs})
    iv = {v: k for k, v in enumerate(velas)}
    X, y = [], []
    for v, ce, lado, d, h, s in obs:
        f = np.zeros(3 + len(velas))
        f[0:2] = np.array([np.cos(np.radians(h)), -np.sin(np.radians(h))]) / s   # 90° a la derecha del rumbo
        f[2] = lado if ce else 0.0
        f[3 + iv[v]] = 1.0
        X.append(f)
        y.append(d)
    f = np.zeros(3 + len(velas))
    f[3:] = 10.0 / len(velas)   # desvío medio de la flota = declinación (la mayoría de Atlas van en magnético)
    X.append(f)
    y.append(10.0 * np.radians(desvio_medio))
    X, y = np.array(X), np.array(y)
    sol, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = (y - X @ sol)[:-1]
    return sol, res, velas


def transversal_por_velocidades(trazas: dict[str, Traza], tramo: dict) -> float | None:
    """Corriente hacia la derecha del avance (kn) en una ceñida, suponiendo la misma velocidad por
    el agua en las dos amuras: la dirección del avance es perpendicular a la diferencia de las
    velocidades medias de cada amura; la media de ambas, fuera del eje, es la corriente."""
    g, lados = [], []
    for v, (e, s) in tramo["barcos"].items():
        x = trazas.get(v)
        if x is None:
            continue
        i = x.tramo(e + MARGEN_RODEO_MS, s - MARGEN_RODEO_MS)
        i = i[(x.sog[i] > 2.0) & ~np.isnan(x.cog[i])]
        g.append(x.sog[i][:, None] * np.stack([np.sin(np.radians(x.cog[i])), np.cos(np.radians(x.cog[i]))], 1))
        lados.append(_wrap(x.cog[i] - tramo["avance"]))
    if not g:
        return None
    g, rel = np.concatenate(g), np.concatenate(lados)
    a, b = rel > 0, rel < 0
    if a.sum() < 50 or b.sum() < 50:
        return None
    ga, gb = g[a].mean(0), g[b].mean(0)
    d, m = (ga - gb) / 2, (ga + gb) / 2
    avance = (np.degrees(np.arctan2(d[0], d[1])) - 90) % 360
    if abs(_wrap(avance - tramo["avance"])) > 90:
        avance = (avance + 180) % 360
    return float(m @ _u(avance + 90))


def estimar(trazas: dict[str, Traza], tramos: list[dict], declinacion: float = 0.0) -> Corriente | None:
    """tramos: [{'ceñida': bool, 'avance': rumbo del avance (°), 'barcos': {vela: (t_entrada, t_salida)}}].
    Una corriente constante para toda la prueba. None si no hay datos suficientes.
    declinacion (° E +): el desvío medio de la flota se fija en ella (un Atlas en magnético lee
    rumbo verdadero − declinación, así que COG − HDG = declinación)."""
    if not any(t["ceñida"] for t in tramos) or not any(not t["ceñida"] for t in tramos):
        return None
    obs = _observaciones(trazas, tramos)
    todas = list(obs)
    descartadas = []
    for _ in range(3):
        velas_ok = {o[0] for o in obs}
        con_ambos = {v for v in velas_ok if any(o[0] == v and o[1] for o in obs) and any(o[0] == v and not o[1] for o in obs)}
        obs = [o for o in obs if o[0] in con_ambos]
        if len(con_ambos) < MIN_BARCOS:
            return None
        sol, res, velas = _resolver(obs, declinacion)
        malos = {v for v, dlt in zip(velas, sol[3:]) if abs(dlt) > DESVIO_MAX}
        sigma = 1.4826 * np.median(np.abs(res - np.median(res)))
        atipicos = {k for k, r in enumerate(res) if abs(r) > 3 * max(sigma, np.radians(2))}
        if not malos and not atipicos:
            break
        descartadas += sorted(malos)
        obs = [o for k, o in enumerate(obs) if o[0] not in malos and k not in atipicos]
    cx, cy, lam = sol[:3]
    eje = next(t["avance"] for t in tramos if t["ceñida"])
    c = np.array([cx, cy])
    derecha = float(c @ _u(eje + 90))
    cruces = [x for x in (transversal_por_velocidades(trazas, t) for t in tramos if t["ceñida"]) if x is not None]
    otra = float(np.mean(cruces)) if cruces else None
    if otra is None:
        confianza = "media"
    else:
        dif = abs(otra - derecha)
        confianza = "alta" if dif <= 0.15 else "media" if dif <= 0.3 and np.sign(otra) == np.sign(derecha) else "baja"
    # Desvío de cada brújula (también de las descartadas), con la corriente y el abatimiento ya fijos
    desvios = {}
    for v in {o[0] for o in todas}:
        r = [o[3] - (lam * o[2] if o[1] else 0.0)
             - (np.array([np.cos(np.radians(o[4])), -np.sin(np.radians(o[4]))]) @ c) / o[5]
             for o in todas if o[0] == v]
        desvios[v] = float(np.degrees(np.median(r)))
    return Corriente(este_kn=float(cx), norte_kn=float(cy), eje_grados=float(eje),
                     a_favor_kn=float(c @ _u(eje)), derecha_kn=derecha,
                     abatimiento_grados=float(np.degrees(lam)), barcos=len(velas),
                     residuo_grados=float(np.degrees(np.std(res))), transversal_velocidades_kn=otra,
                     confianza=confianza, brujulas_descartadas=descartadas, desvios=desvios,
                     declinacion_grados=float(declinacion))
