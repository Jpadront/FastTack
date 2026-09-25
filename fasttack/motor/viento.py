"""Viento reconstruido a partir de la flota (no hay anemómetro en RaceSense).

TWD: en cada uno de los 10 cortes de un tramo (por % del tiempo del líder), los COG de los barcos
que navegan ese tramo se separan en dos grupos (una amura y la otra, o una banda y la otra en
popa) y la TWD es su bisectriz. Si un corte no tiene datos suficientes, hereda la TWD del anterior
(«arrastre») con confianza baja.

Presión: mediana del SOG de la flota en cada corte. Sin viento de referencia es solo un índice
relativo; con él se convierte en nudos (ver `calibrar_tws`). Todo es estimado.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .geo import dif, mediana_circular
from .trazas import Traza

N_CORTES = 10
MARGEN_RODEO_MS = 20_000


@dataclass
class Corte:
    t: int                   # centro del corte (ms)
    twd: float
    twa_flota: float | None  # medio ángulo entre los dos grupos
    sog_mediana: float | None
    n: int
    confianza: float         # 0–1
    fuente: str              # 'bisectriz' | 'arrastre'
    tws: float | None = None  # nudos, solo si hay viento de referencia


@dataclass
class VientoTramo:
    ceñida: bool
    t0: int
    t1: int
    cortes: list[Corte] = field(default_factory=list)

    def twd_en(self, t) -> np.ndarray:
        """TWD interpolada entre los centros de los cortes (constante fuera)."""
        tc = np.array([c.t for c in self.cortes], dtype=float)
        d = np.unwrap(np.radians([c.twd for c in self.cortes]))
        return np.degrees(np.interp(np.asarray(t, dtype=float), tc, d)) % 360.0

    @property
    def twd_media(self) -> float:
        return mediana_circular([c.twd for c in self.cortes], self.cortes[0].twd)


def _dos_grupos(cog: np.ndarray, ref: float, ceñida: bool):
    """2-medias circular: devuelve (centro_izq, centro_der, n_izq, n_der)."""
    dirc = ref if ceñida else (ref + 180) % 360  # dirección hacia la que navega la flota
    c1, c2 = (dirc - 40) % 360, (dirc + 40) % 360
    g1 = np.zeros(len(cog), bool)
    for _ in range(6):
        g1 = np.abs(dif(cog - c1)) < np.abs(dif(cog - c2))
        if g1.sum() == 0 or (~g1).sum() == 0:
            break
        c1, c2 = mediana_circular(cog[g1], c1), mediana_circular(cog[~g1], c2)
    return c1, c2, int(g1.sum()), int((~g1).sum())


def viento_tramo(trazas: dict[str, Traza], en_tramo: dict[str, tuple[int, int]], t0: int, t1: int,
                 ceñida: bool, ref: float, limite_deg: float | None = None) -> VientoTramo:
    """`en_tramo`: barco → (entrada, salida) del tramo. `ref`: TWD de partida (la del tramo
    anterior o el rumbo del eje). Con `limite_deg`, un corte que se aparte más de eso de `ref`
    se descarta como dato insuficiente (en popa los grupos de COG son más frágiles)."""
    vt = VientoTramo(ceñida, t0, t1)
    d = (t1 - t0) / N_CORTES
    previo = ref
    for k in range(N_CORTES):
        a, b = t0 + k * d, t0 + (k + 1) * d
        cogs, sogs, barcos = [], [], set()
        for v, (e, s) in en_tramo.items():
            tr = trazas.get(v)
            if tr is None:
                continue
            lo, hi = max(a, e + MARGEN_RODEO_MS), min(b, s - MARGEN_RODEO_MS)
            if hi <= lo:
                continue
            i = tr.tramo(int(lo), int(hi))
            if len(i) < 2:
                continue
            c = tr.cog[i]
            estable = np.r_[False, np.abs(dif(np.diff(c))) < 8]
            ok = ~np.isnan(c) & estable & (tr.sog[i] > (2.0 if ceñida else 3.0))
            if ok.any():
                cogs.append(c[ok]); sogs.append(tr.sog[i][ok]); barcos.add(v)
        tc = int((a + b) / 2)
        if not cogs:
            vt.cortes.append(Corte(tc, previo, None, None, 0, 0.0, "arrastre"))
            continue
        cog = np.concatenate(cogs)
        sog_med = float(np.median(np.concatenate(sogs)))
        c1, c2, n1, n2 = _dos_grupos(cog, previo, ceñida)
        sep = abs(float(dif(c2 - c1)))
        valido = (min(n1, n2) >= 8 and len(barcos) >= 3
                  and (50 <= sep <= 130 if ceñida else 25 <= sep <= 150))
        if valido:
            bis = (c1 + dif(c2 - c1) / 2) % 360
            twd = float(bis if ceñida else (bis + 180) % 360)
            valido = limite_deg is None or abs(float(dif(twd - ref))) <= limite_deg
        if valido:
            twa = sep / 2 if ceñida else 180 - sep / 2
            equilibrio = min(n1, n2) / max(n1, n2)          # las dos amuras bien representadas
            cantidad = min(1.0, len(barcos) / 10)
            vt.cortes.append(Corte(tc, twd, twa, sog_med, len(cog), round(0.5 * equilibrio + 0.5 * cantidad, 2), "bisectriz"))
            previo = twd
        else:
            vt.cortes.append(Corte(tc, previo, None, sog_med, len(cog), 0.2, "arrastre"))
    # Cortes iniciales sin datos: toman la primera TWD válida
    primera = next((c.twd for c in vt.cortes if c.fuente == "bisectriz"), None)
    if primera is not None:
        for c in vt.cortes:
            if c.fuente == "bisectriz":
                break
            c.twd = primera
    return vt


def calibrar_tws(tramos: list[VientoTramo], tws_disparo: float | None):
    """Convierte el índice de presión (SOG mediano) en nudos a partir del viento de referencia.
    En cada ceñida: TWS ∝ SOG mediano, anclado al primer corte de la primera ceñida = TWS en el
    disparo. En popa el SOG no es proporcional al viento: cada popa se ancla al último corte de la
    ceñida anterior y varía con su propio SOG. Sin referencia, tws queda en None."""
    if not tws_disparo:
        return
    ancla_sog = ancla_tws = None
    for vt in tramos:
        base = next((c.sog_mediana for c in vt.cortes if c.sog_mediana), None)
        if base is None:
            continue
        if vt.ceñida and ancla_sog is None:
            ancla_sog, ancla_tws = base, tws_disparo
        elif ancla_tws is not None:
            ancla_sog = base  # el tramo empieza con el viento con el que acabó el anterior
        if ancla_sog is None:
            continue
        for c in vt.cortes:
            c.tws = round(ancla_tws * c.sog_mediana / ancla_sog, 2) if c.sog_mediana else None
        ultimo = next((c.tws for c in reversed(vt.cortes) if c.tws), None)
        ancla_tws = ultimo or ancla_tws


def fases(valores: list[float | None], umbral: float, etiquetas=("SUBIENDO", "BAJANDO", "ESTABLE"),
          circular: bool = False) -> list[dict]:
    """Agrupa los cortes en fases con la misma tendencia. Devuelve
    [{desde_pct, hasta_pct, tipo, delta}] con % del tramo (cada corte = 10 %)."""
    v = [x for x in valores]
    idx = [i for i, x in enumerate(v) if x is not None]
    if len(idx) < 2:
        return []
    difs = []
    for a, b in zip(idx, idx[1:]):
        dd = float(dif(v[b] - v[a])) if circular else v[b] - v[a]
        difs.append((a, b, dd))
    sube, baja, estable = etiquetas
    fases_, actual = [], None
    for a, b, dd in difs:
        tipo = sube if dd >= umbral / 2 else baja if dd <= -umbral / 2 else estable
        if actual and actual["tipo"] == tipo:
            actual["hasta"], actual["delta"] = b, actual["delta"] + dd
        else:
            actual = {"desde": a, "hasta": b, "tipo": tipo, "delta": dd}
            fases_.append(actual)
    # Las fases cuyo cambio total no llega al umbral se consideran estables y se funden
    for f in fases_:
        if abs(f["delta"]) < umbral:
            f["tipo"] = estable
    fundidas = []
    for f in fases_:
        if fundidas and fundidas[-1]["tipo"] == f["tipo"]:
            fundidas[-1]["hasta"] = f["hasta"]
            fundidas[-1]["delta"] += f["delta"]
        else:
            fundidas.append(dict(f))
    # Oscilación: tres o más fases alternas de derecha/izquierda seguidas
    return [{"desde_pct": f["desde"] * 10, "hasta_pct": (f["hasta"] + 1) * 10, "tipo": f["tipo"],
             "delta": round(f["delta"], 2)} for f in fundidas]
