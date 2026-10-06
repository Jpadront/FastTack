"""Informe PDF de una prueba, en apaisado, por fases: portada (evolución, dónde se perdió, medias),
salida, una página por tramo, viradas y trasluchadas, escora óptima y el debrief de la IA.

Todo sale del análisis del motor (servicio.analisis_prueba) y de las trazas del mapa
(servicio.pistas_prueba): no hay cálculo nuevo, solo se ordena y se dibuja. El barco se compara con
los 5 primeros de la prueba (los del desglose «Dónde se perdió»).
"""
from __future__ import annotations

import datetime as dt
import math

import numpy as np

from .. import __version__
from ..ia import debrief as debrief_mod
from ..ingesta import campeonato as camp_mod
from ..ingesta.almacen import Almacen
from . import graficos as g
from ..motor.semaforo import semaforo
from .prueba import AZUL, LINEA, MARGEN, NARANJA, ROJO, TINTA, TINTA2, TINTA3, _PDF, _markdown, con_signo, num, tiempo

VERDE = (26, 127, 75)
SEMAFORO = {"bien": (26, 127, 75), "normal": (211, 155, 0), "mal": (192, 57, 43)}   # los de la web
MAR = (15, 42, 54)
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
# medias de la prueba (rendimiento del motor): etiqueta, clave, decimales, unidad, ¿más es mejor?
MEDIAS_R = [("VMG en ceñida", "vmg_ceñida", 2, " kn.", True), ("VMG en popa", "vmg_popa", 2, " kn.", True),
            ("SOG en ceñida", "sog_ceñida", 2, " kn.", True), ("SOG en popa", "sog_popa", 2, " kn.", True),
            ("TWA en ceñida", "twa_ceñida", 1, "°", None), ("TWA en popa", "twa_popa", 1, "°", None),
            ("Escora en ceñida", "escora_ceñida", 0, "°", None), ("Escora en popa", "escora_popa", 0, "°", None),
            ("Pérdida por virada", "perdida_virada_m", 1, " m.", False), ("Pérdida por trasluchada", "perdida_trasluchada_m", 1, " m.", False)]
CAUSAS = {"salida_s": "la salida", "velocidad_s": "velocidad", "maniobras_s": "maniobras", "tactica_s": "táctica y recorrido"}


def _med(xs):
    xs = [x for x in xs if x is not None]
    return float(np.median(xs)) if xs else None


def _dif(a):
    return (a + 180) % 360 - 180


class _Ctx:
    def __init__(self, an, pis, ref, camp):
        self.an, self.ref, self.senal = an, ref, an["senal"]
        self.trazas = {v: g.Traza(d) for v, d in pis["barcos"].items()}
        self.balizas = pis.get("balizas", {})
        des = (an.get("rendimiento", {}).get(ref) or {}).get("desglose") or {}
        self.desglose = des
        clas = [c["vela"] for c in an["clasificacion"]]
        self.comp = des.get("frente_a") or [v for v in clas if v != ref][:5]
        self.velas = [ref] + [v for v in self.comp if v != ref]
        self.color = {ref: NARANJA, **{v: g.PALETA[k % len(g.PALETA)] for k, v in enumerate(self.comp)}}
        info = {b["clave"]: b for b in camp.get("barcos", [])}
        self.vela = lambda v: (info.get(v) or {}).get("vela") or v

    def seg(self, ms):
        return (ms - self.senal) / 1000

    def punto_control(self, c, T):
        """Posiciones (x, y) del control en T (s desde la señal): Atlas si lo hay, si no su punto fijo."""
        out = []
        for k, sn in enumerate(c.get("sn") or []):
            b = self.balizas.get(str(sn)) if sn is not None else None
            if b and b["t"]:
                i = int(np.clip(np.searchsorted(np.asarray(b["t"]) / 10, T), 0, len(b["t"]) - 1))
                out.append((b["x"][i] / 10, b["y"][i] / 10))
            elif c.get("puntos_xy") and k < len(c["puntos_xy"]) and c["puntos_xy"][k]:
                out.append(tuple(c["puntos_xy"][k]))
        if not out and c.get("xy"):
            out.append(tuple(c["xy"]))
        return out


def _cabecera(pdf, banda: str, titulo: str, sub: str | None = None):
    pdf.add_page()
    pdf.set_fill_color(*MAR)
    pdf.rect(0, 0, pdf.w, 13, style="F")
    g.logo(pdf, MARGEN, 2.8, 7.4)
    pdf.set_font("Texto", "", 8.5)
    pdf.set_text_color(184, 206, 214)
    pdf.set_xy(pdf.w - MARGEN - 200, 4)
    pdf.cell(200, 5, banda, align="R")
    pdf.set_xy(MARGEN, 17)
    pdf.set_font("Barlow", "B", 20)
    pdf.set_text_color(*TINTA)
    pdf.cell(0, 9, titulo, new_x="LMARGIN", new_y="NEXT")
    if sub:
        pdf.set_font("Texto", "", 9)
        pdf.set_text_color(*TINTA2)
        pdf.cell(0, 5, sub, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)


def _etiqueta(pdf, x, y, texto, fondo=MAR):
    """Etiqueta de sección en píldora, como las del informe de la web."""
    pdf.set_font("Barlow", "B", 8)
    w = pdf.get_string_width(texto.upper()) + 8
    pdf.set_fill_color(*fondo)
    pdf.rect(x, y, w, 5.5, style="F", round_corners=True, corner_radius=1.5)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(x, y + 0.3)
    pdf.cell(w, 5, texto.upper(), align="C")
    return y + 7


def _en_columna(pdf, x, w, fn):
    """Ejecuta fn con los márgenes de una columna (las tablas y textos vuelven a su x)."""
    l, r = pdf.l_margin, pdf.r_margin
    pdf.set_left_margin(x)
    pdf.set_right_margin(pdf.w - x - w)
    pdf.set_x(x)
    try:
        fn()
    finally:
        pdf.set_left_margin(l)
        pdf.set_right_margin(r)


# ---------------------------------------------------------------- portada

def _evolucion(ctx: _Ctx):
    """Puesto, distancia al primero y lo ganado (+) o perdido (−) frente al control anterior."""
    an = ctx.an
    ctrl = [c for c in an["controles"] if c["tipo"] not in ("salida", "offset")]
    cab = ["Barco"] + [c["nombre"] for c in ctrl]
    filas, colores = [], []
    orden = {c["id"]: sorted((p[c["id"]]["t"], v) for v, p in an["pasos"].items() if p.get(c["id"])) for c in ctrl}
    for v in ctx.velas:
        fila, col, prev = [ctx.vela(v)], [None], None
        for c in ctrl:
            o = orden[c["id"]]
            k = next((i for i, (_, x) in enumerate(o) if x == v), None)
            if k is None:
                fila.append("—")
                col.append(None)
                prev = None
                continue
            gap = (o[k][0] - o[0][0]) / 1000
            txt = f"{k + 1}/{len(o)} · {'+' + tiempo(gap) if gap else '0 s.'}"
            dc = None
            if prev is not None:
                ganado = prev - gap
                if abs(ganado) >= 1:
                    txt += f" · {'+' if ganado > 0 else '−'}{tiempo(abs(ganado))}"
                    dc = VERDE if ganado > 0 else ROJO
            fila.append(txt)
            col.append(dc)
            prev = gap
        filas.append(fila)
        colores.append(col)
    return cab, filas, colores


def _portada(pdf, ctx: _Ctx, h: dict, banda: str, titulo: str, sub: str):
    an, ref = ctx.an, ctx.ref
    _cabecera(pdf, banda, titulo, sub)
    clas = [c["vela"] for c in an["clasificacion"]]
    k = clas.index(ref) if ref in clas else None
    d = ctx.desglose
    tot = d.get("total_s")
    causa = None
    if tot:
        cands = [(x, d[x]) for x in CAUSAS if d.get(x) is not None]
        cands.sort(key=lambda c: -c[1] * math.copysign(1, tot))
        causa = cands[0] if cands and cands[0][1] * tot > 0 else None
    sal = an.get("salida") or {}
    corr = an.get("corriente")
    gap = (an["clasificacion"][k]["t"] - an["clasificacion"][0]["t"]) / 1000 if k else 0
    sem = semaforo(an, ref)
    pdf.fichas([
        ("Puesto", f"{k + 1}/{len(clas)}" if k is not None else "—", ("ganador" if k == 0 else f"a {tiempo(gap)} del ganador") if k is not None else None, NARANJA),
        ("Frente al top 5", tiempo(tot, signo=True) if tot is not None else "—", "perdido (+) o ganado (−) en la llegada", ROJO if (tot or 0) > 0 else AZUL if tot else None),
        ("Causa principal", CAUSAS[causa[0]] if causa else "—", tiempo(causa[1], signo=True) if causa else None, None),
        ("Viento en el disparo", f"{num(sal.get('twd_disparo'), 0)}°" if sal.get("twd_disparo") is not None else "—",
         f"{num(sal['tws_disparo'], 1)} kn. (estimado)" if sal.get("tws_disparo") else "intensidad sin calibrar", None),
        ("Corriente", f"{num(corr['velocidad_kn'], 1)} kn." if corr else "—", f"hacia {num(corr['hacia_grados'], 0)}° (estimada)" if corr else None, None),
        ("Velocidad frente a la flota", sem["nivel"].capitalize() if sem else "—",
         f"VMG mejor que el {sem['percentil']} % de la flota" if sem else "faltan barcos con datos (mín. 5)",
         SEMAFORO[sem["nivel"]] if sem else None),
    ])
    pdf.set_font("Texto", "", 8.5)
    pdf.set_text_color(*TINTA2)
    pdf.cell(0, 4.5, "Comparado con los 5 primeros: " + ", ".join(ctx.vela(v) for v in ctx.comp) + ".", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1.5)
    # Evolución de la prueba
    y = _etiqueta(pdf, MARGEN, pdf.get_y(), "Evolución de la prueba")
    pdf.set_y(y)
    cab, filas, col = _evolucion(ctx)
    ancho = pdf.w - 2 * MARGEN
    anchos = [28] + [(ancho - 28) / (len(cab) - 1)] * (len(cab) - 1)
    pdf.tabla(cab, filas, anchos, ["L"] + ["C"] * (len(cab) - 1), col, resaltar={0}, tam=8)
    pdf.set_font("Texto", "I", 7.5)
    pdf.set_text_color(*TINTA3)
    pdf.cell(0, 4, "En cada baliza: puesto, distancia al primero y, desde la segunda, lo ganado (verde) o perdido (rojo) frente a la anterior.",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    # Dónde se perdió (izquierda) y medias frente al top 5 (derecha)
    y0 = pdf.get_y()
    wi = 150
    dsp = h.get("donde_se_perdio_la_prueba") or {}

    def izquierda():
        _etiqueta(pdf, pdf.l_margin, y0, "Dónde se perdió la prueba")
        pdf.set_y(y0 + 7)
        if not dsp:
            pdf.texto("Sin desglose: hacen falta datos del barco y del top 5.", tam=9, color=TINTA3)
            return
        salida = dsp.get("salida_s") if not isinstance(dsp.get("salida_s"), str) else None
        pt = dsp.get("por_tramo", [])
        partes = [("Salida", salida)] + [(x["tramo"], None if x.get("sin_datos") else
                                          x["total_s"] - ((x.get("salida_s") or 0) if j == 0 else 0)) for j, x in enumerate(pt)]
        pdf.barras(partes, max([30] + [abs(v) for _, v in partes if v]))
        tipos = [("velocidad", dsp.get("velocidad_s")), ("maniobras", dsp.get("maniobras_s")), ("táctica y resto", dsp.get("tactica_y_resto_s"))]
        pdf.texto("Por tipo: " + " · ".join(f"{t} **{tiempo(v, True)}**" for t, v in tipos if v is not None), tam=8.5, color=TINTA2, alto=4.5)

    def derecha():
        _etiqueta(pdf, pdf.l_margin, y0, "Medias de la prueba frente al top 5")
        pdf.set_y(y0 + 7)
        rd = an.get("rendimiento") or {}
        yo_r = rd.get(ref) or {}
        filas, cols = [], []
        for et, k, d, u, mas_mejor in MEDIAS_R:
            yo = yo_r.get(k)
            t5 = _med([(rd.get(v) or {}).get(k) for v in ctx.comp])
            if yo is None and t5 is None:
                continue
            dif = yo - t5 if yo is not None and t5 is not None else None
            filas.append([et, num(yo, d) + u if yo is not None else "—", num(t5, d) + u if t5 is not None else "—",
                          con_signo(dif, d) + u if dif is not None else "—"])
            bien = None if dif is None or mas_mejor is None or abs(dif) < 10 ** -d else (dif > 0) == mas_mejor
            cols.append([None, None, None, None if bien is None else VERDE if bien else ROJO])
        if filas:
            pdf.tabla(["", "Tú", "Top 5", "Diferencia"], filas, [40, 25, 25, 25], ["L", "R", "R", "R"], cols, tam=7.8)

    _en_columna(pdf, MARGEN, wi, izquierda)
    y_izq = pdf.get_y()
    pdf.set_y(y0)
    _en_columna(pdf, MARGEN + wi + 8, pdf.w - 2 * MARGEN - wi - 8, derecha)
    pdf.set_y(max(y_izq, pdf.get_y()) + 2)


# ---------------------------------------------------------------- salida

def _pagina_salida(pdf, ctx: _Ctx, banda: str):
    an, ref = ctx.an, ctx.ref
    sal = an.get("salida")
    if not sal:
        return
    sb = sal["barcos"]
    sg = sal.get("sesgo") or {}
    _cabecera(pdf, banda, "Salida", "Aproximación, posición en la línea, aceleración y primer minuto")
    # los datos de la línea, como en la web
    sn = list(reversed((an.get("controles") or [{}])[0].get("sn") or []))
    corr = an.get("corriente")
    pdf.fichas([
        ("Comité · pin", " · ".join(str(x) if x is not None else "—" for x in sn) or "—", "números de serie de las balizas", None),
        ("Sesgo de la línea (est.)", f"{num(sg.get('grados'), 1)}° {'pin' if sg.get('extremo') == 'PIN' else 'comité'}" if sg.get("grados") is not None else "—",
         f"{num(sg.get('metros'), 0)} m. de ventaja en ese extremo" if sg.get("metros") is not None else None, None),
        ("Viento en el disparo (est.)", f"{num(sal.get('twd_disparo'), 0)}°" if sal.get("twd_disparo") is not None else "—",
         f"{num(sal['tws_disparo'], 1)} kn." if sal.get("tws_disparo") else "intensidad sin calibrar", None),
        ("Línea", f"{num(sg.get('largo_linea_m'), 0)} m." if sg.get("largo_linea_m") is not None else "—", "de comité a pin", None),
        ("Corriente (est.)", f"{num(corr['velocidad_kn'], 2)} kn." if corr else "sin estimar",
         f"hacia {num(corr['hacia_grados'], 0)}° · confianza {corr.get('confianza', '—')}" if corr else None, None),
    ])
    pdf.ln(3)
    y0 = pdf.get_y()
    # mapa: de −60 a +90 s.
    trazas = []
    for v in reversed(ctx.velas):
        tr = ctx.trazas.get(v)
        if tr:
            xs, ys = tr.tramo(-60, 90)
            trazas.append((xs, ys, ctx.color[v], 0.7 if v == ref else 0.4))
    com, pin = sal["comite"]["xy"], sal["pin"]["xy"]
    en_disparo = [(float(ctx.trazas[v].en(np.array([0.0]), "x")[0]), float(ctx.trazas[v].en(np.array([0.0]), "y")[0]), ctx.color[v])
                  for v in ctx.velas if v in ctx.trazas]
    g.mapa(pdf, MARGEN, y0, 105, 70, trazas, [(pin[0], pin[1], "pin"), (com[0], com[1], "comité")],
           marcas=[m for m in en_disparo if np.isfinite(m[0])],
           lineas=[((pin[0], pin[1]), (com[0], com[1]), TINTA2, True)], twd=sal.get("twd_disparo"), titulo="De −60 a +90 s. del disparo · puntos: en el disparo")
    # qué decidió la salida
    x1 = MARGEN + 112
    w1 = pdf.w - MARGEN - x1

    def decidio():
        _etiqueta(pdf, pdf.l_margin, y0, "Qué decidió la salida")
        pdf.set_y(y0 + 7)
        b = sb.get(ref) or {}
        cinco = [sb.get(v) or {} for v in ctx.comp]
        m5 = lambda k: _med([c.get(k) for c in cinco])
        lineas = []
        if b.get("dist_60") is not None:
            lineas.append(f"A los 60 s. estabas a **{num(b['dist_60'], 0)} m.** del primero (top 5: {num(m5('dist_60'), 0)} m.), "
                          f"{b.get('pos_60', '—')}.º; a los 180 s., a **{num(b.get('dist_180'), 0)} m.** ({b.get('pos_180', '—')}.º).")
        if b.get("margen_m") is not None:
            lineas.append(f"En el disparo, a **{num(abs(b['margen_m']), 1)} m.** {'por detrás de' if b['margen_m'] <= 0 else 'pasado de'} la línea, "
                          f"al {num(b.get('posicion_linea_pct'), 0)} % de comité a pin, con **{num(b.get('sog_disparo'), 2)} kn.** (top 5: {num(m5('sog_disparo'), 2)} kn.).")
        if b.get("vmg_0_90") is not None:
            lineas.append(f"VMG en los primeros 90 s.: **{num(b['vmg_0_90'], 2)} kn.** (top 5: {num(m5('vmg_0_90'), 2)} kn.).")
        if b.get("primera_virada_s") is not None:
            lineas.append(f"Primera virada a los **{tiempo(b['primera_virada_s'])}** (top 5: {tiempo(m5('primera_virada_s'))}).")
        diag = b.get("diagnostico") or {}
        for k, txt in diag.items():
            if isinstance(txt, str) and txt:
                lineas.append(f"{k.replace('_', ' ').capitalize()}: {txt}.")
        d0 = next((x for x in (ctx.desglose.get("por_tramo") or []) if not x.get("sin_datos")), None)
        if d0 and d0.get("salida_s") is not None:
            lineas.append(f"En el desglose, la salida pesa **{tiempo(d0['salida_s'], True)}** frente al top 5.")
        for t in lineas[:8]:
            pdf.texto("• " + t, tam=8.5, alto=4.4)
            pdf.ln(0.6)

    _en_columna(pdf, x1, w1, decidio)
    yd = pdf.get_y() + 3
    # aceleración: a la derecha, bajo «qué decidió», si cabe; si no, al final de la página
    T = np.arange(-60, 60.5, 1.0)
    series_ac = [(T, ctx.trazas[v].en(T, "sog"), ctx.color[v], 0.7 if v == ref else 0.35, False)
                 for v in reversed(ctx.velas) if v in ctx.trazas]
    acel_arriba = bool(series_ac) and y0 + 70 - yd >= 32

    def aceleracion(x, y, w, h, x_ley):
        g.grafico(pdf, x, y, w, h, series_ac, (-60, 60), xticks=(-60, -30, 0, 30, 60),
                  xfmt=lambda t: "disparo" if t == 0 else f"{t:+d} s.", titulo="Aceleración: SOG de −60 a +60 s. (kn.)", marcas_x=[0])
        for k, v in enumerate(ctx.velas):
            g.leyenda(pdf, x_ley, y + 6 + 4 * k, [(ctx.color[v], ctx.vela(v), False)])

    if acel_arriba:
        aceleracion(x1, yd, w1 - 30, y0 + 70 - yd, x1 + w1 - 27)
    # comparativa
    pdf.set_y(max(y0 + 73, pdf.get_y() + 2))
    y = _etiqueta(pdf, MARGEN, pdf.get_y(), "Comparativa de salida")
    pdf.set_y(y)
    filas, cols = [], []
    for v in ctx.velas:
        b = sb.get(v) or {}
        m = b.get("margen_m")
        filas.append([ctx.vela(v), f"{num(b.get('posicion_linea_pct'), 0)} %" if b.get("posicion_linea_pct") is not None else "—",
                      (con_signo(m, 1) + " m.") if m is not None else "—", num(b.get("sog_disparo"), 2),
                      (con_signo(b.get("cruce_s"), 0) + " s.") if b.get("cruce_s") is not None else "—", num(b.get("vmg_0_90"), 2),
                      str(b.get("pos_60") or "—"), f"{num(b.get('dist_60'), 0)} m." if b.get("dist_60") is not None else "—",
                      str(b.get("pos_180") or "—"), f"{num(b.get('dist_180'), 0)} m." if b.get("dist_180") is not None else "—",
                      tiempo(b.get("primera_virada_s")), (f"{b['pos_b1']}.º" + (f" +{tiempo(b['gap_b1_s'])}" if b.get("gap_b1_s") else "")) if b.get("pos_b1") else "—"])
        cols.append([None, None, (ROJO if m > 0 else VERDE) if m is not None else None] + [None] * 9)
    pdf.tabla(["Barco", "Línea C-P", "Margen", "SOG disparo", "Cruce GPS", "VMG 0–90 s.", "+60", "Δ60", "+180", "Δ180", "1.ª virada", "Baliza 1"],
              filas, [26, 20, 20, 20, 19, 21, 13, 18, 13, 18, 22, 32], ["L"] + ["R"] * 11, cols, resaltar={0}, tam=7.8)
    # aceleración
    ya = pdf.get_y() + 2
    if not acel_arriba and series_ac and ya < pdf.h - 45:
        aceleracion(MARGEN, ya, 180, pdf.h - ya - 18, MARGEN + 186)


# ---------------------------------------------------------------- tramos

def _twd_en(tramo, ms):
    c = tramo["viento"]["cortes"]
    t = np.array([x["t"] for x in c], dtype=float)
    d = np.unwrap(np.radians([x["twd"] for x in c]))
    return np.degrees(np.interp(ms, t, d)) % 360


def _vmg_por_progreso(ctx: _Ctx, tramo, v, n=10):
    """VMG (VMC en un largo) media de cada décima del tramo del barco (por su propio tiempo)."""
    f = tramo["barcos"].get(v)
    tr = ctx.trazas.get(v)
    if not f or not tr:
        return None
    e, s = ctx.seg(f["t_entrada"]), ctx.seg(f["t_salida"])
    out = []
    for k in range(n):
        T = np.linspace(e + (s - e) * k / n, e + (s - e) * (k + 1) / n, 25)
        sog = tr.en(T, "sog")
        c = np.radians(tr.en(T, "cog"))
        if tramo["tipo"] == "largo":
            ref = np.full(T.shape, tramo["rumbo_eje"])
        else:
            w = _twd_en(tramo, T * 1000 + ctx.senal)
            ref = w if tramo["tipo"] == "ceñida" else (w + 180) % 360
        vm = sog * np.cos(c - np.radians(ref))
        out.append(float(np.nanmean(vm)) if np.isfinite(vm).sum() >= 5 else None)
    return out


def _causa(ctx: _Ctx, tramo):
    """Como «Qué decidió el tramo» en la web: desglose del tramo, causa principal y qué mirar."""
    fila = next((x for x in (ctx.desglose.get("por_tramo") or []) if x["tramo"] == tramo["nombre"]), None)
    if not fila or fila.get("sin_datos"):
        return None, None, []
    partes = [(k, fila[k]) for k in CAUSAS if fila.get(k) is not None and (k != "salida_s" or fila[k] != 0)]
    tot = fila.get("total_s") or 0
    principal = None
    if tot and partes:
        c = sorted(partes, key=lambda p: -p[1] * math.copysign(1, tot))[0]
        principal = c if c[1] * tot > 0 else None
    f = tramo["barcos"].get(ctx.ref) or {}
    cinco = [tramo["barcos"][v] for v in ctx.comp if v in tramo["barcos"]]
    m5 = lambda k: _med([c.get(k) for c in cinco])
    ceñida = tramo["tipo"] == "ceñida"
    pistas = []
    if principal:
        k = principal[0]
        if k == "velocidad_s":
            ds = f["sog"] - m5("sog") if f.get("sog") is not None and m5("sog") is not None else None
            dt_ = f["twa"] - m5("twa") if f.get("twa") is not None and m5("twa") is not None else None
            if ds is not None:
                pistas.append(f"SOG {con_signo(ds, 2)} kn. frente al top 5")
            if dt_ is not None:
                pistas.append(f"TWA {con_signo(dt_, 1)}° ({('más abierto' if dt_ > 0 else 'más cerrado') if ceñida else ('más bajo' if dt_ > 0 else 'más alto')})")
            if ds is not None and dt_ is not None:
                pistas.append("a igual ángulo te faltó velocidad: trimado, peso o escora" if ds < -0.1 and abs(dt_) < 1.5
                              else "más abierto sin la velocidad que lo compense: busca altura" if ceñida and dt_ > 1.5
                              else "más alto sin la velocidad que lo compense: baja más" if not ceñida and dt_ < -1.5
                              else "más cerrado y más lento: abre un poco para ganar velocidad" if ceñida and dt_ < -1.5 and ds < -0.1
                              else "más bajo y más lento: sube un poco para ganar velocidad" if not ceñida and dt_ > 1.5 and ds < -0.1
                              else "mira el modo y la escora frente al top 5")
        elif k == "maniobras_s":
            pistas.append(f"{f.get('maniobras', '—')} maniobras (top 5: {num(m5('maniobras'), 0)}) y {num(f.get('perdida_m'), 0)} m. perdidos en ellas (top 5: {num(m5('perdida_m'), 0)} m.)")
        elif k == "salida_s":
            pistas.append("mira la página de la salida")
        else:
            lay = f.get("layline") or {}
            if lay.get("estado") == "SOBREPASADA":
                pistas.append(f"layline sobrepasada {num(lay.get('metros'), 0)} m.")
            fav = (f.get("tactica") or {}).get("amura_favorecida_pct")
            if fav is not None:
                pistas.append(f"{num(fav, 0)} % en la amura favorecida (top 5: {num(_med([(c.get('tactica') or {}).get('amura_favorecida_pct') for c in cinco]), 0)} %)")
            sr = (f.get("tactica") or {}).get("roles_en_contra_sin_responder")
            if sr:
                pistas.append(f"{sr} role{'s' if sr > 1 else ''} en contra sin responder")
            if f.get("vs_fantasma_m") is not None:
                pistas.append(f"{num(abs(f['vs_fantasma_m']), 0)} m. {'más' if f['vs_fantasma_m'] > 0 else 'menos'} que el fantasma")
    return fila, principal, pistas


def _pagina_tramo(pdf, ctx: _Ctx, tramo, banda: str):
    an, ref = ctx.an, ctx.ref
    vi = tramo["viento"]
    es_l = tramo["tipo"] == "largo"
    sub = (f"{num(tramo.get('largo_m'), 0)} m. · TWD media {num(vi.get('twd_media'), 0)}°"
           + (f" · TWA de la flota {num(vi.get('twa_flota'), 0)}°" if vi.get("twa_flota") and not es_l else "")
           + (f" · fantasma {num(tramo.get('fantasma_m'), 0)} m." if tramo.get("fantasma_m") else "")
           + (" · largo: se compara la VMC (velocidad hacia la baliza)" if es_l else ""))
    _cabecera(pdf, banda, tramo["nombre"], sub)
    y0 = pdf.get_y()
    # mapa del tramo
    trazas = []
    for v in reversed(ctx.velas):
        f, tr = tramo["barcos"].get(v), ctx.trazas.get(v)
        if f and tr:
            xs, ys = tr.tramo(ctx.seg(f["t_entrada"]), ctx.seg(f["t_salida"]))
            trazas.append((xs, ys, ctx.color[v], 0.7 if v == ref else 0.4))
    cam = tramo.get("fantasma_camino") or []
    if len(cam) >= 2:
        trazas.insert(0, (np.array([p[0] for p in cam]), np.array([p[1] for p in cam]), (150, 150, 160), 0.35))
    puntos = []
    for cid in (tramo["desde"], tramo["hasta"]):
        c = next((x for x in an["controles"] if x["id"] == cid), None)
        if c:
            for k, p in enumerate(ctx.punto_control(c, ctx.seg(tramo["t0"]))):
                puntos.append((p[0], p[1], c["nombre"] if k == 0 else ""))
    g.mapa(pdf, MARGEN, y0, 92, 80, trazas, puntos, twd=vi.get("twd_media"),
           titulo="Trazas del tramo" + (" · gris: fantasma" if len(cam) >= 2 else ""))
    # qué decidió
    xm, wm = MARGEN + 97, 88
    fila, principal, pistas = _causa(ctx, tramo)

    def decidio():
        _etiqueta(pdf, pdf.l_margin, y0, "Qué decidió el tramo")
        pdf.set_y(y0 + 7)
        if not fila:
            pdf.texto("Sin desglose: faltan datos del barco o del top 5 en este tramo.", tam=8.5, color=TINTA3)
            return
        tot = fila["total_s"]
        pdf.texto(f"Frente al top 5: **{tiempo(abs(tot))} {'perdidos' if tot > 0 else 'ganados' if tot < 0 else ''}**"
                  + (f" · causa principal: **{CAUSAS[principal[0]]}**" if principal else "") + ".", tam=9, alto=4.6)
        pdf.ln(1)
        partes = [(CAUSAS[k], v) for k in CAUSAS for kk, v in [(k, fila.get(k))] if v is not None and (k != "salida_s" or v != 0)]
        esc = max([10] + [abs(v) for _, v in partes])
        for et, v in partes:
            yy = pdf.get_y()
            pdf.set_font("Texto", "B" if principal and CAUSAS[principal[0]] == et else "", 8)
            pdf.set_text_color(*TINTA2)
            pdf.cell(30, 4.6, et)
            medio = pdf.l_margin + 30 + 17
            pdf.set_draw_color(*LINEA)
            pdf.line(medio, yy + 0.4, medio, yy + 4.2)
            if v:
                w = min(abs(v) / esc, 1) * 16
                pdf.set_fill_color(*(ROJO if v > 0 else AZUL))
                pdf.rect(medio if v > 0 else medio - w, yy + 1.1, w, 2.6, style="F")
            pdf.set_xy(pdf.l_margin + 30 + 35, yy)
            pdf.set_font("Mono", "B", 7.5)
            pdf.set_text_color(*(ROJO if v > 0 else AZUL if v < 0 else TINTA))
            pdf.cell(wm - 65, 4.6, tiempo(v, True), align="R")
            pdf.ln(4.6)
        if pistas:
            pdf.ln(1)
            pdf.texto("**Qué mirar:** " + " · ".join(pistas) + ".", tam=8, color=TINTA2, alto=4.2)

    _en_columna(pdf, xm, wm, decidio)
    # viento del tramo (cortes del motor)
    xw = xm + wm + 6
    ww = pdf.w - MARGEN - xw
    cortes = vi.get("cortes") or []
    pct = [c["pct"] for c in cortes]
    rol = [_dif(c["twd"] - vi["twd_media"]) for c in cortes]
    pres = [c.get("sog_mediana") for c in cortes]   # presión medida en el campo (sin anemómetro)
    if cortes:
        g.rosa(pdf, xw, y0, ww, 40, cortes, vi["twd_media"], titulo="TWD · rosa del tramo")
        d = _dif(cortes[-1]["twd"] - cortes[0]["twd"])
        pdf.set_xy(xw, y0 + 42.2)
        pdf.set_font("Texto", "", 7)
        pdf.set_text_color(*TINTA2)
        izq, der = min(rol), max(rol)
        sg = lambda x: ("+" if round(x) > 0 else "−" if round(x) < 0 else "±") + num(abs(x), 0)
        pdf.cell(ww, 3.4, f"Máx. izquierda {round((vi['twd_media'] + izq) % 360)}° ({sg(izq)}°) · "
                 f"media {round(vi['twd_media'] % 360)}° · máx. derecha {round((vi['twd_media'] + der) % 360)}° ({sg(der)}°)", align="C")
        pdf.set_xy(xw, y0 + 45.8)
        pdf.cell(ww, 3.4, f"De {round(cortes[0]['twd'] % 360)}° a {round(cortes[-1]['twd'] % 360)}°: "
                 + ("sin rolada neta" if abs(d) < 0.5 else f"{num(abs(d), 0)}° a la {'derecha' if d > 0 else 'izquierda'}")
                 + f" · horquilla {num(max(rol) - min(rol), 0)}°", align="C")
    ok = [p for p in pres if p is not None]
    if cortes and ok:
        dec = 2
        g.tira(pdf, xw, y0 + 50, ww, 26, cortes, pres, vi["twd_media"], dec,
               titulo="Presión: SOG mediana de la flota · tira del tramo (kn.)")
        kmx, kmn = pres.index(max(ok)), pres.index(min(ok))
        pdf.set_xy(xw, y0 + 76)
        pdf.set_font("Texto", "", 7)
        pdf.set_text_color(*TINTA2)
        pdf.cell(ww, 3.4, f"Media {num(sum(ok) / len(ok), dec)} kn. · más presión al {cortes[kmx]['pct']} %, menos al {cortes[kmn]['pct']} %"
                 " · color relativo al tramo", align="C")
    # tabla comparativa
    pdf.set_y(y0 + 84)
    bs = tramo["barcos"]
    buenas = [f for f in bs.values() if f.get("calidad") in ("alta", "media")]
    mvmg, mdist = _med([f.get("vmg") for f in buenas]), _med([f.get("distancia_m") for f in buenas])
    ent = [] if tramo["desde"] == "salida" else [v for v, _ in sorted(((v, f["t_entrada"]) for v, f in bs.items()), key=lambda x: x[1])]
    filas, cols = [], []
    for v in ctx.velas:
        f = bs.get(v)
        if not f:
            continue
        pe = ent.index(v) + 1 if v in ent else None
        gan = pe - f["posicion"] if pe and f.get("posicion") else None
        dv = f["vmg"] - mvmg if f.get("vmg") is not None and mvmg is not None else None
        dd = f["distancia_m"] - mdist if f.get("distancia_m") is not None and mdist is not None else None
        lay = f.get("layline") or {}
        filas.append([ctx.vela(v), str(pe or "—"), str(f.get("posicion") or "—"), con_signo(gan, 0) if gan else ("0" if gan == 0 else "—"),
                      tiempo(f.get("parcial_s")), num(f.get("vmg"), 2), (con_signo(dv, 2)) if dv is not None else "—",
                      num(f.get("sog"), 2), f"{num(f.get('twa'), 1)}°" if f.get("twa") is not None and not es_l else "—",
                      f"{num(f.get('distancia_m'), 0)} m." if f.get("distancia_m") is not None else "—",
                      (con_signo(dd, 0) + " m.") if dd is not None else "—",
                      "—" if es_l else str(f.get("maniobras") if f.get("maniobras") is not None else "—"),
                      "—" if es_l else (f"{num(f.get('perdida_m'), 0)} m." if f.get("perdida_m") is not None else "—"),
                      ("Dcha" if lay.get("lado") == "DERECHA" else "Izda") + f" +{num(lay.get('metros'), 0)} m." if lay.get("estado") == "SOBREPASADA" else "OK" if lay.get("estado") == "OK" else "—",
                      f"{num(f.get('escora'), 0)}°" if f.get("escora") is not None else "—",
                      f"{num((f.get('tactica') or {}).get('amura_favorecida_pct'), 0)} %" if (f.get("tactica") or {}).get("amura_favorecida_pct") is not None else "—"])
        cols.append([None, None, None, (VERDE if (gan or 0) > 0 else ROJO if (gan or 0) < 0 else None), None, None,
                     (None if dv is None or abs(dv) < 0.05 else VERDE if dv > 0 else ROJO), None, None, None,
                     (None if dd is None or abs(dd) < 20 else VERDE if dd < 0 else ROJO), None, None,
                     ROJO if lay.get("estado") == "SOBREPASADA" else None, None, None])
    pdf.tabla(["Barco", "Entrada", "Puesto", "Ganados", "Parcial", "VMC" if es_l else "VMG", "Δ flota", "SOG", "TWA", "Distancia", "Δ dist.",
               "Man.", "Pérdida", "Layline", "Escora", "Amura fav."],
              filas, [23, 13, 13, 15, 25, 14, 16, 14, 15, 21, 18, 11, 17, 23, 15, 20], ["L"] + ["R"] * 15, cols, resaltar={0}, tam=7.6)
    pdf.set_font("Texto", "I", 7)
    pdf.set_text_color(*TINTA3)
    pdf.cell(0, 3.6, "Δ flota y Δ dist.: frente a la mediana de la flota en el tramo (barcos con datos fiables). Puesto: al final del tramo.",
             new_x="LMARGIN", new_y="NEXT")
    # VMG a lo largo del tramo
    yv = pdf.get_y() + 1.5
    if yv < pdf.h - 36:
        xs = [5 + 10 * k for k in range(10)]
        series = []
        for v in reversed(ctx.velas):
            vm = _vmg_por_progreso(ctx, tramo, v)
            if vm:
                series.append((xs, [np.nan if x is None else x for x in vm], ctx.color[v], 0.7 if v == ref else 0.35, False))
        # escora frente a VMG (como en la web): a la derecha, con el gráfico de VMG más estrecho
        eo = tramo.get("escora_optima") or {}
        curva = None if es_l else eo.get("curva")
        hv = pdf.h - yv - 16
        if series:
            wv = 138 if curva else 200
            g.grafico(pdf, MARGEN, yv, wv, hv, series, (0, 100), xticks=(0, 25, 50, 75, 100), xfmt=lambda t: f"{t} %",
                      titulo=("VMC" if es_l else "VMG") + (" a lo largo del tramo, en kn." if curva else
                                                         " a lo largo del tramo, en kn. (cada décima del tramo de cada barco)"))
            if curva:
                for k, v in enumerate(ctx.velas):
                    g.leyenda(pdf, MARGEN + wv + 3, yv + 6 + 4 * k, [(ctx.color[v], ctx.vela(v), False)])
            else:
                g.leyenda(pdf, MARGEN + 206, yv + 6, [(ctx.color[v], ctx.vela(v), False) for v in ctx.velas[:3]])
                g.leyenda(pdf, MARGEN + 206, yv + 11, [(ctx.color[v], ctx.vela(v), False) for v in ctx.velas[3:]])
        if curva:
            popa = tramo["tipo"] != "ceñida"
            mia = (tramo["barcos"].get(ref) or {}).get("escora_sotavento" if popa else "escora")
            gr = lambda x: f"{num(x, 1).removesuffix(',0')}°"
            tit = ("Escora en popa (+ sotavento)" if popa else "Escora frente a VMG") + (
                f" · 5 con más VMG {gr(eo['escora'])}" if eo.get("escora") is not None else "") + (
                f" · tú {gr(mia)}" if mia is not None else "") + (" · orientativa" if curva.get("orientativa") else "")
            xe = MARGEN + 168
            g.escora(pdf, xe, yv, pdf.w - MARGEN - xe, hv, curva, eo.get("escora"), mia, ctx.vela(ref), titulo=tit)


# ---------------------------------------------------------------- maniobras

METRICAS_MAN = [("SOG de entrada", "sog_entrada_kn", 2, " kn.", 1), ("SOG mínima", "sog_minima_kn", 2, " kn.", 1),
                ("Caída de SOG", "caida_sog_pct", 0, " %", -1), ("SOG estable de salida", "sog_salida_estable_kn", 2, " kn.", 1),
                ("Duración del giro", "duracion_giro_s", 1, " s.", -1), ("Tiempo en acelerar (95 %)", "tiempo_aceleracion_s", 1, " s.", -1),
                ("VMG antes", "vmg_entrada_kn", 2, " kn.", 1), ("VMG después", "vmg_salida_estable_kn", 2, " kn.", 1),
                ("Pérdida", "perdida_m", 1, " m.", -1), ("Pérdida en tiempo", "perdida_s", 1, " s.", -1)]


def _pagina_maniobras(pdf, ctx: _Ctx, tipo: str, banda: str):
    an, ref = ctx.an, ctx.ref
    tt = "ceñida" if tipo == "virada" else "popa"

    def lista(velas):
        return [(m, v, t) for t in an["tramos"] if t["tipo"] == tt for v in velas for m in (t.get("maniobras") or {}).get(v, []) if m.get("detalle")]

    mias, otras = lista([ref]), lista(ctx.comp)
    if not mias and not otras:
        return
    _cabecera(pdf, banda, "Viradas" if tipo == "virada" else "Trasluchadas",
              f"Sincronizadas en el instante en que la proa cruza el viento · de −5 a +15 s. · tú ({len(mias)}) frente al top 5 ({len(otras)})")
    y0 = pdf.get_y()
    OFF = np.arange(-5, 15.01, 0.5)
    perfiles = []   # (es_mia, sog, x, y)
    for m, v, t in mias + otras:
        tr = ctx.trazas.get(v)
        if not tr:
            continue
        T0 = ctx.seg(m["t"])
        T = T0 + OFF
        x, y = tr.en(T, "x"), tr.en(T, "y")
        x0_, y0_ = tr.en(np.array([T0]), "x")[0], tr.en(np.array([T0]), "y")[0]
        if not np.isfinite(x0_):
            continue
        w = math.radians(_twd_en(t, m["t"]))
        dx, dy = x - x0_, y - y0_
        perfiles.append((v == ref, tr.en(T, "sog"), dx * math.cos(w) - dy * math.sin(w), dx * math.sin(w) + dy * math.cos(w)))
    # trayectorias con el viento arriba
    lado = 84
    trazas = [(p[2], p[3], NARANJA if p[0] else AZUL, 0.5 if p[0] else 0.3) for p in sorted(perfiles, key=lambda p: p[0])]
    if trazas:
        g.mapa(pdf, MARGEN, y0, lado, lado, trazas, [(0, 0, "")], titulo="Trayectorias con el viento arriba")
    # métricas
    xm = MARGEN + lado + 8
    wmx = pdf.w - MARGEN - xm

    def metricas():
        _etiqueta(pdf, pdf.l_margin, y0, "Medias (mediana de las maniobras)")
        pdf.set_y(y0 + 7)
        filas, cols = [], []
        for et, k, d, u, mejor in METRICAS_MAN:
            a = _med([m["detalle"].get(k) for m, _, _ in mias])
            b = _med([m["detalle"].get(k) for m, _, _ in otras])
            dif = a - b if a is not None and b is not None else None
            filas.append([et, num(a, d) + u if a is not None else "—", num(b, d) + u if b is not None else "—",
                          (con_signo(dif, d) + u) if dif is not None else "—"])
            cols.append([None, None, None, None if dif is None or abs(dif) < 10 ** -d else VERDE if dif * mejor > 0 else ROJO])
        na = sum(1 for m, _, _ in mias if not m["detalle"].get("acelerado"))
        nb = sum(1 for m, _, _ in otras if not m["detalle"].get("acelerado"))
        filas.append(["Sin acelerar al 95 % en 60 s.", f"{na} de {len(mias)}", f"{nb} de {len(otras)}", ""])
        cols.append([None] * 4)
        pdf.tabla(["", "Tú", "Top 5", "Diferencia"], filas, [60, 34, 34, 34], ["L", "R", "R", "R"], cols, tam=8)
        pdf.ln(1)
        pdf.texto("Entrada: SOG estable de −25 a −8 s.; estable: la de la nueva amura (+25 a +45 s.); acelerar: desde el final del giro "
                  "hasta el 95 % de la estable. Pérdida: lo que se habría avanzado hacia el viento sin maniobrar menos lo avanzado "
                  "(las roladas se cargan a la amura). Verde: mejor que el top 5.", tam=7.5, color=TINTA3, alto=3.8)

    _en_columna(pdf, xm, wmx, metricas)
    # perfil de SOG
    yp = y0 + lado + 3
    series = [(OFF, p[1], (247, 196, 172) if p[0] else (180, 205, 235), 0.25, False) for p in perfiles]

    def media(es_mia):
        ps = [p[1] for p in perfiles if p[0] == es_mia]
        if not ps:
            return None
        with np.errstate(all="ignore"):
            return np.nanmean(np.vstack(ps), axis=0)
    for es_mia, col in ((False, AZUL), (True, NARANJA)):
        mm = media(es_mia)
        if mm is not None:
            series.append((OFF, mm, col, 0.9, False))
    g.grafico(pdf, MARGEN, yp, 200, pdf.h - yp - 16, series, (-5, 15), xticks=(-5, 0, 5, 10, 15),
              xfmt=lambda t: "cruce" if t == 0 else f"{t:+d} s.", titulo="SOG durante la maniobra, en kn. (finas: cada una · gruesas: la media)",
              marcas_x=[0])
    g.leyenda(pdf, MARGEN + 206, yp + 6, [(NARANJA, ctx.vela(ref), False), (AZUL, "top 5", False)])


# ---------------------------------------------------------------- documento

def generar(alm: Almacen, camp_id: str, clave: str, barco: str) -> bytes:
    from .. import servicio
    camp = camp_mod.leer(alm, camp_id)
    if camp is None:
        raise KeyError(camp_id)
    prueba = next((p for p in camp["pruebas"] if p["clave"] == clave), None)
    if prueba is None:
        raise KeyError(clave)
    h = debrief_mod.datos_de(alm, camp_id, clave, barco)
    an = servicio.analisis_prueba(alm, camp_id, clave)
    pis = servicio.pistas_prueba(alm, camp_id, clave)
    alias = alm.sql("select alias from campeonato where id=?", (camp_id,))
    nombre_camp = (alias[0]["alias"] if alias and alias[0]["alias"] else None) or camp.get("nombre") or camp_id
    info_barco = next((b for b in camp["barcos"] if b["clave"] == barco), {})
    tz = camp.get("tz_offset_ms") or 0
    fecha = dt.datetime.fromtimestamp((prueba["senal"] + tz) / 1000, tz=dt.timezone.utc)
    num_prueba = (h.get("prueba") or {}).get("numero") or prueba.get("numero")
    ctx = _Ctx(an, pis, barco, camp)
    nombre_barco = ctx.vela(barco) + (f" · {info_barco['nombre']}" if info_barco.get("nombre") else "")

    pdf = _PDF(f"FastTack {__version__} · {nombre_camp} · prueba {num_prueba} · {ctx.vela(barco)} · "
               "cifras estimadas a partir del GPS de los barcos (sin anemómetro)", orientacion="L")
    pdf.set_margins(MARGEN, MARGEN, MARGEN)
    pdf.alias_nb_pages()
    banda = f"{nombre_camp} · prueba {num_prueba} · {nombre_barco}"
    _portada(pdf, ctx, h, banda, f"Prueba {num_prueba} · {nombre_barco}",
             f"{camp.get('clase') or ''} · {fecha.day} de {MESES[fecha.month - 1]} de {fecha.year}, {fecha:%H:%M} · {nombre_camp}")
    _pagina_salida(pdf, ctx, banda)
    for t in an["tramos"]:
        _pagina_tramo(pdf, ctx, t, banda)
    _pagina_maniobras(pdf, ctx, "virada", banda)
    _pagina_maniobras(pdf, ctx, "trasluchada", banda)
    # escora óptima en las ceñidas
    cen = [t for t in an.get("tramos", []) if t.get("tipo") == "ceñida" and (t.get("escora_optima") or {}).get("curva") and barco in t.get("barcos", {})]
    if cen:
        _cabecera(pdf, banda, "Escora óptima en ceñida", "Óptima = media de la escora de los 5 barcos con más VMG del tramo, navegando estable; "
                  "cada punto: VMG (y SOG) en esa franja de escora frente a los vecinos. Estimada.")
        for t in cen:
            pdf.escora(t["nombre"], t["escora_optima"], t["barcos"][barco], "Tú")
            pdf.ln(1)
    # debrief
    d = debrief_mod.leer(alm, camp_id, clave, barco)
    _cabecera(pdf, banda, f"Debrief de la prueba {num_prueba}")
    if not d:
        pdf.texto("Aún no hay debrief de esta prueba: genéralo en la pestaña «Debrief» de la web y vuelve a descargar el informe.",
                  tam=10, estilo="I", color=TINTA2)
    else:
        vigente = d["huella"] == debrief_mod.huella(h)
        cuando = dt.datetime.fromtimestamp(d["creado_en"] / 1000, tz=dt.timezone.utc) + dt.timedelta(milliseconds=tz)
        nota = f"Redactado por IA ({'Claude Code' if d['origen'] == 'claude-code' else 'texto pegado'}) el {cuando:%d/%m/%Y} con las cifras de FastTack."
        if not vigente:
            nota += " Las cifras han cambiado desde entonces (nueva versión del cálculo o viento de referencia): conviene regenerarlo."
        avisos = debrief_mod.no_verificadas(d["texto"], h)
        if avisos:
            nota += f" Cifras sin comprobar en los datos: {', '.join(avisos[:6])}."
        pdf.texto(nota, tam=8.5, estilo="I", color=TINTA3, alto=4.2)
        pdf.ln(1)
        _markdown(pdf, d["texto"])
    return bytes(pdf.output())
