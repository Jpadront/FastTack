"""Viento reconstruido a partir de la flota (no hay anemómetro en RaceSense).

TWD: en cada uno de los 10 cortes de un tramo (por % del tiempo del líder), los COG de los barcos
que navegan ese tramo se separan en dos grupos (una amura y la otra, o una banda y la otra en
popa) y la TWD es su bisectriz. Si un corte no tiene datos suficientes, hereda la TWD del anterior
(«arrastre») con confianza baja.

Con menos de 3 barcos (sesiones propias con archivos .vkx) la bisectriz de un corte casi nunca
tiene las dos amuras. Entonces se usan los rumbos de todo el tramo: el ángulo entre amuras del
barco (o barcos) en el tramo se supone constante, y en cada corte la TWD es la bisectriz que
corresponde al rumbo que llevan (COG ± medio ángulo). Así una rolada se ve en la amura en la que
se esté navegando («amuras», confianza media).

Presión: mediana del SOG de la flota en cada corte. Sin viento de referencia es solo un índice
relativo; con él se convierte en nudos (ver `calibrar_tws`). Todo es estimado.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .geo import a_ejes, dif, mediana_circular
from .trazas import Traza

N_CORTES = 10
MARGEN_RODEO_MS = 20_000
MIN_BARCOS_BISECTRIZ = 3      # por debajo: método de «amuras» (rumbos del tramo)
AMURA_MAX_DEG = 25            # una muestra a más de esto del rumbo de su amura es una maniobra


@dataclass
class Corte:
    t: int                   # centro del corte (ms)
    twd: float
    twa_flota: float | None  # medio ángulo entre los dos grupos
    sog_mediana: float | None
    n: int
    confianza: float         # 0–1
    fuente: str              # 'bisectriz' | 'amuras' | 'arrastre'
    tws: float | None = None  # nudos, solo si hay viento de referencia
    # Por lado del campo (mirando a barlovento), para saber quién recibe antes una rolada o racha
    sog_izq: float | None = None
    sog_der: float | None = None
    twd_izq: float | None = None
    twd_der: float | None = None
    # Rumbos sobre el fondo de las dos amuras de la flota (centros de los grupos): incluyen la
    # corriente, así que las laylines sobre el fondo salen de ellos
    rumbos: tuple[float, float] | None = None


@dataclass
class VientoTramo:
    ceñida: bool
    t0: int
    t1: int
    cortes: list[Corte] = field(default_factory=list)
    # SOG mínima para usar una muestra: relativa a la flota (sirve para cualquier clase y viento)
    sog_min: float = 2.0

    def twd_en(self, t) -> np.ndarray:
        """TWD interpolada entre los centros de los cortes (constante fuera)."""
        tc = np.array([c.t for c in self.cortes], dtype=float)
        d = np.unwrap(np.radians([c.twd for c in self.cortes]))
        return np.degrees(np.interp(np.asarray(t, dtype=float), tc, d)) % 360.0

    def rumbos_en(self, t: float) -> tuple[float, float] | None:
        """Rumbos de las dos amuras en el corte válido más cercano a t."""
        validos = [c for c in self.cortes if c.rumbos is not None]
        if not validos:
            return None
        return min(validos, key=lambda c: abs(c.t - t)).rumbos

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


FRACCION_SOG_MIN, SOG_MIN_ABS = 0.4, 1.0


def sog_minima(trazas: dict[str, Traza], en_tramo: dict[str, tuple[int, int]]) -> float:
    """SOG por debajo de la cual una muestra no se usa (parado, rodeando, maniobrando): el 40 % de
    la SOG mediana de la flota en el tramo, y al menos 1 kn. En un J/70 da ~2,2 kn en ceñida y
    ~3 kn en popa, como los umbrales fijos de antes; en clases lentas o con poco viento no
    descarta la mitad de los datos."""
    s = [trazas[v].sog[trazas[v].tramo(e + MARGEN_RODEO_MS, sal - MARGEN_RODEO_MS)]
         for v, (e, sal) in en_tramo.items() if v in trazas]
    s = np.concatenate(s) if s else np.array([])
    s = s[~np.isnan(s)]
    return max(SOG_MIN_ABS, FRACCION_SOG_MIN * float(np.median(s))) if len(s) else 2.0


def viento_tramo(trazas: dict[str, Traza], en_tramo: dict[str, tuple[int, int]], t0: int, t1: int,
                 ceñida: bool, ref: float, limite_deg: float | None = None,
                 eje: float | None = None) -> VientoTramo:
    """`en_tramo`: barco → (entrada, salida) del tramo. `ref`: TWD de partida (la del tramo
    anterior o el rumbo del eje). Con `limite_deg`, un corte que se aparte más de eso de `ref`
    se descarta como dato insuficiente (en popa los grupos de COG son más frágiles)."""
    vt = VientoTramo(ceñida, t0, t1)
    vt.sog_min = sog_minima(trazas, en_tramo)
    d = (t1 - t0) / N_CORTES
    previo = ref
    amuras = _amuras_del_tramo(trazas, en_tramo, vt.sog_min, ref, ceñida, limite_deg) \
        if len(en_tramo) < MIN_BARCOS_BISECTRIZ else None
    for k in range(N_CORTES):
        a, b = t0 + k * d, t0 + (k + 1) * d
        cogs, sogs, lats, barcos = [], [], [], set()
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
            ok = ~np.isnan(c) & estable & (tr.sog[i] > vt.sog_min)
            if ok.any():
                cogs.append(c[ok]); sogs.append(tr.sog[i][ok]); barcos.add(v)
                if eje is not None:
                    _, lat = a_ejes(tr.x[i][ok], tr.y[i][ok], eje)
                    lats.append(lat if ceñida else -lat)  # derecha mirando a barlovento
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
        if amuras is not None:
            corte = _corte_por_amuras(tc, cog, sog_med, amuras, ceñida, limite_deg, ref)
            if corte is not None:
                vt.cortes.append(corte)
                previo = corte.twd
                continue
            valido = False
        lados = {}
        if lats:
            lat = np.concatenate(lats)
            corte_lat = np.median(lat)
            sog_all = np.concatenate(sogs)
            for nombre, m in (("izq", lat < corte_lat), ("der", lat >= corte_lat)):
                if m.sum() >= 10:
                    lados[f"sog_{nombre}"] = float(np.median(sog_all[m]))
                    a1, a2, m1, m2 = _dos_grupos(cog[m], previo, ceñida)
                    sp = abs(float(dif(a2 - a1)))
                    if min(m1, m2) >= 5 and (50 <= sp <= 130 if ceñida else 25 <= sp <= 150):
                        bb = (a1 + dif(a2 - a1) / 2) % 360
                        lados[f"twd_{nombre}"] = float(bb if ceñida else (bb + 180) % 360)
        if valido:
            twa = sep / 2 if ceñida else 180 - sep / 2
            equilibrio = min(n1, n2) / max(n1, n2)          # las dos amuras bien representadas
            cantidad = min(1.0, len(barcos) / 10)
            vt.cortes.append(Corte(tc, twd, twa, sog_med, len(cog), round(0.5 * equilibrio + 0.5 * cantidad, 2), "bisectriz",
                                   rumbos=(float(c1) % 360, float(c2) % 360), **lados))
            previo = twd
        else:
            vt.cortes.append(Corte(tc, previo, None, sog_med, len(cog), 0.2, "arrastre", **lados))
    # Cortes iniciales sin datos: toman la primera TWD válida
    primera = next((c.twd for c in vt.cortes if c.fuente != "arrastre"), None)
    if primera is not None:
        for c in vt.cortes:
            if c.fuente != "arrastre":
                break
            c.twd = primera
    return vt


def _amuras_del_tramo(trazas, en_tramo, sog_min, ref, ceñida, limite_deg):
    """Rumbos de las dos amuras en todo el tramo (pocos barcos): (c1, c2) o None."""
    cogs = []
    for v, (e, s) in en_tramo.items():
        tr = trazas.get(v)
        if tr is None:
            continue
        i = tr.tramo(e + MARGEN_RODEO_MS, s - MARGEN_RODEO_MS)
        if len(i) < 2:
            continue
        c = tr.cog[i]
        ok = ~np.isnan(c) & np.r_[False, np.abs(dif(np.diff(c))) < 8] & (tr.sog[i] > sog_min)
        cogs.append(c[ok])
    if not cogs:
        return None
    c1, c2, n1, n2 = _dos_grupos(np.concatenate(cogs), ref, ceñida)
    sep = abs(float(dif(c2 - c1)))
    if min(n1, n2) < 20 or not (50 <= sep <= 130 if ceñida else 25 <= sep <= 150):
        return None
    bis = (c1 + dif(c2 - c1) / 2) % 360
    twd = float(bis if ceñida else (bis + 180) % 360)
    if limite_deg is not None and abs(float(dif(twd - ref))) > limite_deg:
        return None
    return float(c1), float(c2), twd, min(n1, n2) / max(n1, n2)


def _corte_por_amuras(tc, cog, sog_med, amuras, ceñida, limite_deg, ref) -> Corte | None:
    c1, c2, twd_tramo, equilibrio = amuras
    medio = float(dif(c2 - c1)) / 2
    d1, d2 = np.abs(dif(cog - c1)), np.abs(dif(cog - c2))
    g1 = d1 < d2
    cerca = np.minimum(d1, d2) <= AMURA_MAX_DEG
    if cerca.sum() < 10:
        return None
    est = np.where(g1, cog + medio, cog - medio)[cerca] % 360   # bisectriz según el rumbo de cada muestra
    bis_tramo = twd_tramo if ceñida else (twd_tramo + 180) % 360
    bis = mediana_circular(est, bis_tramo)
    twd = float(bis if ceñida else (bis + 180) % 360)
    if limite_deg is not None and abs(float(dif(twd - ref))) > limite_deg:
        return None
    giro = float(dif(twd - twd_tramo))
    twa = abs(medio) if ceñida else 180 - abs(medio)
    return Corte(tc, twd, twa, sog_med, int(cerca.sum()), round(0.5 * equilibrio, 2), "amuras",
                 rumbos=((c1 + giro) % 360, (c2 + giro) % 360))


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


COINCIDE_MODELO_DEG = 25


def tws_modelo(tramos: list[VientoTramo], horario: list, tws_disparo: float | None, senal: int) -> str | None:
    """Intensidad del viento (TWS, kn) de cada corte con el viento horario del modelo meteorológico,
    interpolado en el tiempo, si su dirección cuadra con la TWD de la flota (≤ 25°). Con viento de
    referencia apuntado, el modelo se escala para que en el disparo valga ese viento (el modelo da la
    evolución; la referencia, el nivel). Así la intensidad no depende de la SOG, que no es
    proporcional al viento (planeo, saturación). Devuelve la fuente usada, o None si no vale."""
    if not horario or not tramos:
        return None
    ts = np.array([h[0] for h in horario], dtype=float)
    kn = np.array([h[1] for h in horario], dtype=float)
    dirs = [h[2] for h in horario]
    t0 = min(vt.t0 for vt in tramos)
    t1 = max(vt.t1 for vt in tramos)
    dentro = [d for (t, _, d) in horario if t0 - 1800_000 <= t <= t1 + 1800_000] or dirs
    twd = mediana_circular([c.twd for vt in tramos for c in vt.cortes], tramos[0].cortes[0].twd)
    if abs(float(dif(mediana_circular(dentro, dentro[0]) - twd))) > COINCIDE_MODELO_DEG:
        return None
    factor = 1.0
    if tws_disparo:
        en_senal = float(np.interp(senal, ts, kn))
        if en_senal > 0.5:
            factor = tws_disparo / en_senal
    for vt in tramos:
        for c in vt.cortes:
            c.tws = round(float(np.interp(c.t, ts, kn)) * factor, 2)
    return "modelo escalado a la referencia" if tws_disparo else "modelo"


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
    # El cambio ocurre entre los centros de los cortes (corte k = k·10 + 5 %): fases contiguas,
    # la primera desde el 0 % y la última hasta el 100 %.
    n = len(fundidas)
    return [{"desde_pct": 0 if k == 0 else f["desde"] * 10 + 5,
             "hasta_pct": 100 if k == n - 1 else f["hasta"] * 10 + 5, "tipo": f["tipo"],
             "delta": round(f["delta"], 2)} for k, f in enumerate(fundidas)]


def quien_primero(fases_: list[dict], cortes: list[Corte], campo: str, circular: bool) -> None:
    """Añade 'primero' a cada fase no estable: el lado del campo (mirando a barlovento) cuyo valor
    se había movido más en el sentido de la fase en el primer corte de la fase. Si los dos lados se
    mueven parecido (diferencia < 30 %) o faltan datos, 'flota'."""
    for f in fases_:
        f["primero"] = None
        k0 = max(0, (f["desde_pct"] - 5) // 10)  # primer corte de la fase
        if f["tipo"] in ("ESTABLE",):
            continue
        k1 = min(k0 + 1, len(cortes) - 1)
        signo = 1 if f["delta"] > 0 else -1
        mov = {}
        for lado in ("izq", "der"):
            a, b = getattr(cortes[k0], f"{campo}_{lado}"), getattr(cortes[k1], f"{campo}_{lado}")
            if a is not None and b is not None:
                d = float(dif(b - a)) if circular else b - a
                mov[lado] = d * signo
        if len(mov) < 2 or max(mov.values()) <= 0:
            f["primero"] = "flota"
            continue
        izq, der = mov["izq"], mov["der"]
        if abs(izq - der) < 0.3 * max(abs(izq), abs(der)):
            f["primero"] = "flota"
        else:
            f["primero"] = "IZQUIERDA" if izq > der else "DERECHA"
