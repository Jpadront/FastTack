"""Piezas gráficas del informe PDF (fpdf2): mapa pequeño de trazas y gráfico de líneas.

Sin dependencias nuevas: todo se dibuja con líneas de fpdf2 en milímetros de la página.
"""
from __future__ import annotations

import math

import numpy as np

TINTA, TINTA2, TINTA3 = (16, 34, 43), (74, 90, 98), (130, 142, 148)
LINEA, REJILLA, AGUA = (205, 212, 216), (230, 234, 236), (232, 240, 243)
NARANJA = (224, 98, 46)
# colores de los barcos comparados (el propio, siempre naranja)
PALETA = [(42, 120, 214), (26, 127, 75), (106, 90, 205), (0, 140, 150), (168, 100, 0), (120, 120, 120)]


class Traza:
    """Traza compacta de servicio.pistas_prueba en unidades normales: s desde la señal, m, kn, grados."""

    def __init__(self, d: dict):
        self.t = np.asarray(d["t"], dtype=float) / 10
        self.x = np.asarray(d["x"], dtype=float) / 10
        self.y = np.asarray(d["y"], dtype=float) / 10
        self.sog = np.asarray(d["sog"], dtype=float) / 10
        cog = np.asarray(d["cog"], dtype=float)
        self.cog = np.where(cog < 0, np.nan, cog)

    def tramo(self, t0: float, t1: float):
        m = (self.t >= t0) & (self.t <= t1)
        return self.x[m], self.y[m]

    def en(self, T: np.ndarray, canal: str, hueco_s: float = 15.0):
        """Valor interpolado en los instantes T; NaN fuera de la traza o en huecos de más de hueco_s."""
        T = np.asarray(T, dtype=float)
        v = getattr(self, canal)
        if len(self.t) < 2:
            return np.full(T.shape, np.nan)
        out = np.interp(T, self.t, v)
        i = np.clip(np.searchsorted(self.t, T), 1, len(self.t) - 1)
        malo = (T < self.t[0]) | (T > self.t[-1]) | ((self.t[i] - self.t[i - 1]) > hueco_s)
        out[malo] = np.nan
        return out


def mapa(pdf, x0: float, y0: float, w: float, h: float, trazas: list, puntos: list = (), lineas: list = (),
         twd: float | None = None, titulo: str | None = None, marcas: list = ()):
    """Mapa con el norte arriba y la misma escala en los dos ejes.
    trazas: [(xs, ys, color, grosor)]; puntos: [(x, y, rótulo)]; lineas: [((x0, y0), (x1, y1), color, discontinua)]."""
    xs = np.concatenate([t[0] for t in trazas if len(t[0])] + [np.array([p[0] for p in puntos])] +
                        [np.array([a[0] for a, *_ in lineas] + [b[0] for _, b, *_ in lineas])])
    ys = np.concatenate([t[1] for t in trazas if len(t[1])] + [np.array([p[1] for p in puntos])] +
                        [np.array([a[1] for a, *_ in lineas] + [b[1] for _, b, *_ in lineas])])
    xs, ys = xs[np.isfinite(xs)], ys[np.isfinite(ys)]
    pdf.set_fill_color(*AGUA)
    pdf.set_draw_color(*LINEA)
    pdf.set_line_width(0.2)
    pdf.rect(x0, y0, w, h, style="DF")
    if titulo:
        pdf.set_font("Barlow", "", 7)
        pdf.set_text_color(*TINTA2)
        pdf.set_xy(x0 + 2, y0 + 1)
        pdf.cell(w - 4, 3.5, titulo.upper())
    if not len(xs):
        return
    pad = 4
    ax0, ax1, ay0, ay1 = x0 + pad, x0 + w - pad, y0 + pad + (3 if titulo else 0), y0 + h - pad
    mx0, mx1, my0, my1 = float(xs.min()), float(xs.max()), float(ys.min()), float(ys.max())
    esc = min((ax1 - ax0) / max(mx1 - mx0, 1), (ay1 - ay0) / max(my1 - my0, 1))
    cx, cy = (mx0 + mx1) / 2, (my0 + my1) / 2
    X = lambda x: (ax0 + ax1) / 2 + (x - cx) * esc
    Y = lambda y: (ay0 + ay1) / 2 - (y - cy) * esc
    for (a, b, col, disc) in lineas:
        pdf.set_draw_color(*col)
        pdf.set_line_width(0.35)
        if disc:
            pdf.set_dash_pattern(dash=1.2, gap=0.9)
        pdf.line(X(a[0]), Y(a[1]), X(b[0]), Y(b[1]))
        pdf.set_dash_pattern()
    for xs_, ys_, col, grosor in trazas:
        if len(xs_) < 2:
            continue
        pdf.set_draw_color(*col)
        pdf.set_line_width(grosor)
        pts = [(X(a), Y(b)) for a, b in zip(xs_, ys_) if np.isfinite(a) and np.isfinite(b)]
        if len(pts) >= 2:
            pdf.polyline(pts, style="D")
    for x, y, col in marcas:   # posiciones de los barcos en un instante
        pdf.set_fill_color(*col)
        pdf.set_draw_color(255, 255, 255)
        pdf.set_line_width(0.25)
        pdf.circle(X(x), Y(y), 0.9, style="DF")
    pdf.set_font("Barlow", "", 6.5)
    for x, y, et in puntos:
        pdf.set_draw_color(74, 58, 167)
        pdf.set_fill_color(255, 255, 255)
        pdf.set_line_width(0.4)
        pdf.circle(X(x), Y(y), 1.1, style="DF")
        if et:
            pdf.set_text_color(*TINTA)
            pdf.set_xy(X(x) + 1.4, Y(y) - 3.2)
            pdf.cell(20, 3, et)
    # escala y viento
    m = next((v for v in (20, 50, 100, 200, 250, 500, 1000, 2000) if v * esc >= 10), 2000)
    pdf.set_draw_color(*TINTA2)
    pdf.set_line_width(0.4)
    pdf.line(x0 + w - 3 - m * esc, y0 + h - 3, x0 + w - 3, y0 + h - 3)
    pdf.set_font("Mono", "", 5.5)
    pdf.set_text_color(*TINTA2)
    pdf.set_xy(x0 + w - 23, y0 + h - 6.2)
    pdf.cell(20, 3, f"{m} m.", align="R")
    if twd is not None:
        ux, uy = math.sin(math.radians(twd)), math.cos(math.radians(twd))
        ox, oy = x0 + w - 6, y0 + 7 + (3 if titulo else 0)
        # flecha hacia donde va el viento (viene de twd)
        pdf.set_draw_color(*TINTA)
        pdf.set_line_width(0.45)
        pdf.line(ox + ux * 3.5, oy - uy * 3.5, ox - ux * 3.5, oy + uy * 3.5)
        hx, hy = ox - ux * 3.5, oy + uy * 3.5
        for s in (-1, 1):
            a = math.radians(twd + 180 + s * 150)
            pdf.line(hx, hy, hx + math.sin(a) * 1.6, hy - math.cos(a) * 1.6)
        pdf.set_xy(ox - 8, oy + 4.2)
        pdf.cell(16, 3, f"{round(twd)}°", align="C")


def grafico(pdf, x0: float, y0: float, w: float, h: float, series: list, xlim, ylim=None, xticks=(), xfmt=str,
            yfmt=None, titulo: str | None = None, unidad: str = "", referencia: float | None = None,
            marcas_x: list = ()):
    """Gráfico de líneas. series: [(xs, ys, color, grosor, discontinua)]. referencia: línea horizontal."""
    if titulo:
        pdf.set_font("Barlow", "", 8)
        pdf.set_text_color(*TINTA2)
        pdf.set_xy(x0, y0)
        pdf.cell(w, 4, titulo.upper())
        y0 += 5
        h -= 5
    ml, mb = 11, 5
    ax0, ax1, ay0, ay1 = x0 + ml, x0 + w - 1, y0 + 1, y0 + h - mb
    vals = np.concatenate([np.asarray(s[1], dtype=float) for s in series] + [np.array([referencia] if referencia is not None else [])])
    vals = vals[np.isfinite(vals)]
    if ylim is None:
        if not len(vals):
            return
        lo, hi = float(vals.min()), float(vals.max())
        pad = (hi - lo) * 0.08 or 0.5
        ylim = (lo - pad, hi + pad)
    X = lambda x: ax0 + (x - xlim[0]) / ((xlim[1] - xlim[0]) or 1) * (ax1 - ax0)
    Y = lambda v: ay1 - (v - ylim[0]) / ((ylim[1] - ylim[0]) or 1) * (ay1 - ay0)
    yfmt = yfmt or (lambda v: f"{v:.1f}".replace(".", ","))
    pdf.set_line_width(0.15)
    pdf.set_font("Mono", "", 5.5)
    pdf.set_text_color(*TINTA3)
    for k in range(5):
        v = ylim[0] + (ylim[1] - ylim[0]) * k / 4
        pdf.set_draw_color(*REJILLA)
        pdf.line(ax0, Y(v), ax1, Y(v))
        pdf.set_xy(x0, Y(v) - 1.6)
        pdf.cell(ml - 1.5, 3.2, yfmt(v), align="R")
    for t in xticks:
        pdf.set_draw_color(*REJILLA)
        pdf.line(X(t), ay0, X(t), ay1)
        pdf.set_xy(X(t) - 8, ay1 + 0.6)
        pdf.cell(16, 3, xfmt(t), align="C")
    if unidad:
        pdf.set_xy(x0, ay0 - 3.2)
        pdf.cell(ml - 1.5, 3, unidad, align="R")
    if referencia is not None:
        pdf.set_draw_color(*TINTA3)
        pdf.set_line_width(0.25)
        pdf.line(ax0, Y(referencia), ax1, Y(referencia))
    for xm in marcas_x:
        pdf.set_draw_color(*TINTA2)
        pdf.set_line_width(0.3)
        pdf.set_dash_pattern(dash=1, gap=0.8)
        pdf.line(X(xm), ay0, X(xm), ay1)
        pdf.set_dash_pattern()
    for xs, ys, col, grosor, disc in series:
        pdf.set_draw_color(*col)
        pdf.set_line_width(grosor)
        if disc:
            pdf.set_dash_pattern(dash=1.2, gap=0.9)
        tramo = []
        for a, b in zip(xs, ys):
            if b is None or not np.isfinite(b):
                if len(tramo) >= 2:
                    pdf.polyline(tramo, style="D")
                tramo = []
                continue
            tramo.append((X(a), Y(min(max(b, ylim[0]), ylim[1]))))
        if len(tramo) >= 2:
            pdf.polyline(tramo, style="D")
        pdf.set_dash_pattern()
    pdf.set_line_width(0.2)


def leyenda(pdf, x: float, y: float, elementos: list, tam: float = 7):
    """[(color, texto, discontinua)] en una línea."""
    pdf.set_font("Texto", "", tam)
    for col, et, disc in elementos:
        pdf.set_draw_color(*col)
        pdf.set_line_width(0.7)
        if disc:
            pdf.set_dash_pattern(dash=1, gap=0.7)
        pdf.line(x, y + 1.6, x + 4.5, y + 1.6)
        pdf.set_dash_pattern()
        pdf.set_text_color(*TINTA2)
        pdf.set_xy(x + 5.5, y)
        ww = pdf.get_string_width(et) + 1.5
        pdf.cell(ww, 3.2, et)
        x += 5.5 + ww + 3.5
    pdf.set_line_width(0.2)
