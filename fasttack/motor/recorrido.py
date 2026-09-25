"""Recorrido real de una prueba: rodeos, balizas, secuencia de tramos y pasos por baliza.

RaceSense da la función de cada baliza pero no el orden del recorrido ni las vueltas, y en algunos
campeonatos las balizas de barlovento no llevan Atlas. El recorrido se reconstruye con la flota:
1. Eje inicial: perpendicular a la línea de salida, hacia el lado del recorrido.
2. Por barco, extremos alternos de su avance a lo largo del eje (con histéresis): máximos =
   rodeos de barlovento, mínimos = rodeos de sotavento.
3. Nº de vueltas = moda del nº de rodeos de barlovento de los que llegan.
4. Posición de cada baliza por vuelta: el Atlas de la baliza si está cerca del rodeo de la flota;
   si no, la mediana de los puntos de rodeo (estimada).
5. Paso por baliza de cada barco = máxima aproximación a esa baliza cerca de su rodeo.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .geo import a_ejes, distancia, rumbo
from .pistas import Pista
from .trazas import Traza

HISTERESIS_MIN_M = 150.0
# Eslora (m) por clase, para la zona de baliza (3 esloras). Sin clase conocida, la del J/70.
ESLORAS = {"j/70": 6.93, "j/80": 8.0, "j/24": 7.32, "snipe": 4.72, "ilca": 4.23, "laser": 4.23, "470": 4.7,
           "420": 4.2, "49er": 4.99, "49erfx": 4.99, "nacra 17": 5.25, "finn": 4.5, "star": 6.92, "etchells": 9.3,
           "melges 24": 7.32, "melges 20": 6.1, "sb20": 6.15, "dragon": 8.9, "optimist": 2.31, "29er": 4.45,
           "flying fifteen": 6.1, "rs21": 6.4, "j/111": 11.1, "fireball": 4.93}
ZONA_M = 3 * 6.93


def zona_de(clase: str | None) -> float:
    """Zona de baliza: 3 esloras de la clase del campeonato."""
    return 3 * ESLORAS.get((clase or "").strip().lower(), 6.93)
RADIO_ATLAS_M = 250.0      # un Atlas a menos de esto del rodeo de la flota es esa baliza
OFFSET_VENTANA_MS = 150_000  # el offset se rodea en los 2,5 min siguientes a la baliza
OFFSET_BAJADA_M = 40.0       # empieza la popa cuando se baja más de esto respecto a la baliza
OFFSET_MIN_M = 40.0          # separación lateral mínima para considerar que hay offset


@dataclass
class Control:
    """Un punto de paso: salida, baliza de barlovento, puerta/baliza de sotavento o llegada."""
    id: str                    # 'salida', 'b1', 's1', 'b2', …, 'llegada'
    nombre: str                # 'Baliza 1', 'Puerta', 'Llegada'…
    tipo: str                  # 'salida' | 'barlovento' | 'offset' | 'sotavento' | 'llegada'
    fuente: str                # 'atlas' | 'estimada' | 'documento'
    puntos: list = field(default_factory=list)  # [(sn o None, pista)] — 2 si es puerta o línea
    rodeo_mediano: int | None = None             # ms

    @property
    def es_puerta(self) -> bool:
        return self.tipo == "sotavento" and len(self.puntos) == 2


@dataclass
class Paso:
    t: int                     # ms
    x: float
    y: float
    entrada: int | None = None
    salida: int | None = None
    puerta: str | None = None  # 'IZQUIERDA' | 'DERECHA' (mirando a sotavento, como RaceSense)


def eje_inicial(trazas: dict[str, Traza], pin: Pista, comite: Pista, senal: int) -> float:
    """Rumbo perpendicular a la línea hacia donde va la flota a los 3 min."""
    px, py = pin.en(np.array([senal]))
    cx, cy = comite.en(np.array([senal]))
    linea = float(rumbo(px[0] - cx[0], py[0] - cy[0]))
    mx, my = (px[0] + cx[0]) / 2, (py[0] + cy[0]) / 2
    pos = [t.en(senal + 180_000) for t in trazas.values()]
    pos = np.array([p for p in pos if p is not None])
    candidatos = [(linea + 90) % 360, (linea - 90) % 360]
    if not len(pos):
        return candidatos[0]
    avance = [np.median(a_ejes(pos[:, 0] - mx, pos[:, 1] - my, c)[0]) for c in candidatos]
    return candidatos[int(np.argmax(avance))]


def extremos(tr: Traza, eje: float, t0: int, t1: int, histeresis: float) -> list[tuple[str, int, float, float]]:
    """Máximos y mínimos alternos del avance a lo largo del eje: [('max'|'min', t, x, y)]."""
    i = tr.tramo(t0, t1)
    if len(i) < 3:
        return []
    a, _ = a_ejes(tr.x[i], tr.y[i], eje)
    out, subiendo, j_ext = [], True, 0
    for j in range(1, len(i)):
        if subiendo:
            if a[j] > a[j_ext]:
                j_ext = j
            elif a[j] < a[j_ext] - histeresis:
                out.append(("max", int(tr.ts[i[j_ext]]), float(tr.x[i[j_ext]]), float(tr.y[i[j_ext]])))
                subiendo, j_ext = False, j
        else:
            if a[j] < a[j_ext]:
                j_ext = j
            elif a[j] > a[j_ext] + histeresis:
                out.append(("min", int(tr.ts[i[j_ext]]), float(tr.x[i[j_ext]]), float(tr.y[i[j_ext]])))
                subiendo, j_ext = True, j
    return out


def reconstruir(trazas: dict[str, Traza], balizas: dict[int, Pista], roles: dict[str, int],
                senal: int, llegadas: dict[str, int], pin: Pista, comite: Pista,
                llegada_a: Pista | None, llegada_b: Pista | None, zona_m: float = ZONA_M):
    """Devuelve (controles, pasos por barco, eje inicial, nº de vueltas, avisos)."""
    avisos = []
    eje = eje_inicial(trazas, pin, comite, senal)
    fin_flota = max(llegadas.values()) if llegadas else senal + 3 * 3600_000

    # Longitud aproximada del primer tramo (mediana del máximo avance de la flota en 40 min)
    px, py = pin.en(np.array([senal]))
    cx, cy = comite.en(np.array([senal]))
    ox, oy = float((px[0] + cx[0]) / 2), float((py[0] + cy[0]) / 2)
    maxs = []
    for tr in trazas.values():
        i = tr.tramo(senal, senal + 40 * 60_000)
        if len(i):
            maxs.append(np.max(a_ejes(tr.x[i] - ox, tr.y[i] - oy, eje)[0]))
    largo = float(np.median(maxs)) if maxs else 1500.0
    hist = max(HISTERESIS_MIN_M, 0.2 * largo)

    ext = {}
    for v, tr in trazas.items():
        fin = llegadas.get(v, fin_flota) + 60_000
        ext[v] = extremos(tr, eje, senal, fin, hist)
    # nº de rodeos de barlovento de los que llegan (antes de su llegada)
    n_max = [sum(1 for e in ext[v] if e[0] == "max" and e[1] < llegadas[v]) for v in llegadas if v in ext]
    vueltas = int(np.bincount(n_max).argmax()) if n_max else 0
    if vueltas == 0:
        avisos.append("No se ha podido reconstruir el recorrido (sin rodeos detectados).")

    # ¿La llegada es a sotavento (tras una popa) o a barlovento (tras una ceñida)?
    llegada_barlovento = False
    if llegada_a is not None and llegada_b is not None:
        lx, ly = llegada_a.en(np.array([fin_flota]))
        llegada_barlovento = bool(a_ejes(lx[0] - ox, ly[0] - oy, eje)[0] > 0.6 * largo)

    # Secuencia de rodeos esperada por barco
    secuencia = []
    for k in range(1, vueltas + 1):
        secuencia.append(("barlovento", k))
        if k < vueltas or llegada_barlovento:
            secuencia.append(("sotavento", k))
    if llegada_barlovento:  # la última «sotavento» sobra: tras la última baliza se ciñe a la llegada
        secuencia = secuencia[:-1]

    rodeos: dict[tuple, list] = {s: [] for s in secuencia}
    for v, lst in ext.items():
        maxs_v = [e for e in lst if e[0] == "max" and e[1] < llegadas.get(v, fin_flota + 1)]
        mins_v = [e for e in lst if e[0] == "min" and e[1] < llegadas.get(v, fin_flota + 1)]
        for (tipo, k) in secuencia:
            fuente = maxs_v if tipo == "barlovento" else mins_v
            if len(fuente) >= k:
                rodeos[(tipo, k)].append((v, *fuente[k - 1][1:]))

    # Balizas por rodeo
    controles = [Control("salida", "Salida", "salida", "atlas" if not comite.fija else "documento",
                         [(roles.get("startLeft"), pin), (roles.get("startRight"), comite)], senal)]
    n_barl = n_sota = 0
    for (tipo, k) in secuencia:
        pts = rodeos[(tipo, k)]
        if not pts:
            continue
        t_med = int(np.median([p[1] for p in pts]))
        mx, my = float(np.median([p[2] for p in pts])), float(np.median([p[3] for p in pts]))
        if tipo == "barlovento":
            n_barl += 1
            c = _baliza(f"b{k}", f"Baliza {n_barl}", tipo, balizas, [roles.get("markPort"), roles.get("markStarboard")],
                        mx, my, t_med)
        else:
            n_sota += 1
            puerta = [roles.get("gateLeft"), roles.get("gateRight")]
            c = _puerta(f"s{k}", balizas, puerta, mx, my, t_med) or _baliza(
                f"s{k}", "Sotavento" if vueltas < 3 else f"Sotavento {n_sota}", tipo, balizas,
                [roles.get("markPort"), roles.get("markStarboard")], mx, my, t_med)
        controles.append(c)
    controles.append(Control("llegada", "Llegada", "llegada", "atlas" if llegada_a is not None else "documento",
                             [(roles.get("finishLeft"), llegada_a), (roles.get("finishRight"), llegada_b)],
                             int(np.median(list(llegadas.values()))) if llegadas else None))

    # Pasos por baliza de cada barco
    pasos: dict[str, dict[str, Paso]] = {}
    for v, tr in trazas.items():
        pv = {}
        for c in controles:
            if c.tipo in ("barlovento", "sotavento"):
                k = int(c.id[1:])
                cand = [p for p in rodeos.get((c.tipo, k), []) if p[0] == v]
                if cand:
                    pv[c.id] = _paso(tr, c, cand[0][1], eje, zona_m)
        if v in llegadas:
            xy = tr.en(llegadas[v], hueco_ms=30_000)
            pv["llegada"] = Paso(llegadas[v], *(xy if xy else (np.nan, np.nan)))
        pasos[v] = pv
    controles = _offsets(trazas, controles, pasos, eje, zona_m)
    return controles, pasos, eje, vueltas, avisos


def _offsets(trazas, controles, pasos, eje, zona_m: float = ZONA_M) -> list[Control]:
    """Offset tras cada baliza de barlovento, estimado con la flota: tras la baliza se navega de
    través hasta el offset y allí empieza la popa. Por barco, el punto de rodeo es la última
    muestra antes de bajar OFFSET_BAJADA_M respecto a la baliza; su mediana es el offset si está a
    más de OFFSET_MIN_M de la baliza en lateral. Paso = máxima aproximación a ese punto."""
    nuevos = []
    for c in controles:
        nuevos.append(c)
        if c.tipo != "barlovento":
            continue
        k = c.id[1:]
        puntos = []
        for v, tr in trazas.items():
            p = pasos[v].get(c.id)
            if p is None or np.isnan(p.x):
                continue
            i = tr.tramo(p.t, p.t + OFFSET_VENTANA_MS)
            if len(i) < 3:
                continue
            al, _ = a_ejes(tr.x[i] - p.x, tr.y[i] - p.y, eje)
            baja = np.nonzero(al < -OFFSET_BAJADA_M)[0]
            if len(baja) and baja[0] > 0:
                j = baja[0] - 1
                puntos.append((v, float(tr.x[i[j]]), float(tr.y[i[j]])))
        if len(puntos) < 5:
            continue
        ox, oy = float(np.median([q[1] for q in puntos])), float(np.median([q[2] for q in puntos]))
        mx, my = c.puntos[0][1].en(np.array([c.rodeo_mediano]))
        _, lat = a_ejes(ox - mx[0], oy - my[0], eje)
        if abs(float(lat)) < OFFSET_MIN_M:
            continue
        off = Control(f"o{k}", f"Offset {k}", "offset", "estimada", [(None, Pista.constante(ox, oy))])
        tiempos = []
        for v, tr in trazas.items():
            p = pasos[v].get(c.id)
            if p is None:
                continue
            q = _paso(tr, off, p.t + 60_000, eje, zona_m)
            if not np.isnan(q.x) and q.t >= p.t:
                pasos[v][off.id] = q
                tiempos.append(q.t)
        off.rodeo_mediano = int(np.median(tiempos)) if tiempos else None
        nuevos.append(off)
    return nuevos


def _baliza(cid, nombre, tipo, balizas, sns, mx, my, t_med) -> Control:
    for sn in sns:
        p = balizas.get(sn) if sn is not None else None
        if p is None:
            continue
        bx, by = p.en(np.array([t_med]))
        if not np.isnan(bx[0]) and distancia(mx, my, bx[0], by[0]) < RADIO_ATLAS_M:
            return Control(cid, nombre, tipo, "atlas", [(sn, p)], t_med)
    return Control(cid, nombre, tipo, "estimada", [(None, Pista.constante(mx, my))], t_med)


def _puerta(cid, balizas, sns, mx, my, t_med) -> Control | None:
    if None in sns or any(sn not in balizas for sn in sns):
        return None
    pts = []
    for sn in sns:
        bx, by = balizas[sn].en(np.array([t_med]))
        if np.isnan(bx[0]) or distancia(mx, my, bx[0], by[0]) > RADIO_ATLAS_M:
            return None
        pts.append((sn, balizas[sn]))
    return Control(cid, "Puerta", "sotavento", "atlas", pts, t_med)


def _paso(tr: Traza, c: Control, t_rodeo: int, eje: float, zona_m: float = ZONA_M) -> Paso:
    """Máxima aproximación a la baliza (o a la de la puerta elegida) en ±4 min del rodeo."""
    i = tr.tramo(t_rodeo - 240_000, t_rodeo + 240_000)
    if not len(i):
        return Paso(t_rodeo, np.nan, np.nan)
    mejor = None
    for nombre_lado, (sn, p) in zip(("IZQUIERDA", "DERECHA"), c.puntos):
        bx, by = p.en(tr.ts[i])
        d = distancia(tr.x[i], tr.y[i], bx, by)
        if np.all(np.isnan(d)):
            continue
        j = int(np.nanargmin(d))
        if mejor is None or d[j] < mejor[0]:
            mejor = (d[j], j, nombre_lado, d)
    if mejor is None:
        return Paso(t_rodeo, np.nan, np.nan)
    dmin, j, lado, d = mejor
    dentro = np.nonzero(d <= max(zona_m, dmin + 5))[0]
    ent = int(tr.ts[i[dentro[0]]]) if len(dentro) else None
    sal = int(tr.ts[i[dentro[-1]]]) if len(dentro) else None
    puerta = None
    if c.es_puerta:
        (s1, p1), (s2, p2) = c.puntos
        x1, y1 = p1.en(np.array([tr.ts[i[j]]]))
        x2, y2 = p2.en(np.array([tr.ts[i[j]]]))
        _, lat1 = a_ejes(x1[0], y1[0], eje)
        _, lat2 = a_ejes(x2[0], y2[0], eje)
        elegido_1 = lado == "IZQUIERDA"
        lat_elegida, lat_otra = (lat1, lat2) if elegido_1 else (lat2, lat1)
        # Convención de RaceSense (gateLeft/gateRight): mirando a sotavento, como la ve el barco
        # que llega por la popa. El eje apunta a barlovento, así que la derecha se invierte.
        puerta = "IZQUIERDA" if lat_elegida > lat_otra else "DERECHA"
    return Paso(int(tr.ts[i[j]]), float(tr.x[i[j]]), float(tr.y[i[j]]), ent, sal, puerta)
