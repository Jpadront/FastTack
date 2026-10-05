"""Informe en PDF de una prueba: rendimiento frente al top 5 y el debrief de la IA.

Usa las mismas cifras que recibe el debrief (ia.debrief.datos_de), así el PDF y el texto de la IA
cuadran siempre. Fuentes de la web (Barlow Semi Condensed, Source Sans 3, IBM Plex Mono; licencias
en fuentes/).
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from fpdf import FPDF

from .. import __version__
from ..ia import debrief as debrief_mod
from ..ingesta import campeonato as camp_mod
from ..ingesta.almacen import Almacen

FUENTES = Path(__file__).parent / "fuentes"
TINTA, TINTA2, TINTA3 = (16, 34, 43), (74, 90, 98), (130, 142, 148)
LINEA, REJILLA, FONDO = (205, 212, 216), (230, 234, 236), (244, 246, 247)
AZUL, AZUL_OSC, ROJO, NARANJA = (42, 120, 214), (28, 92, 171), (192, 57, 43), (224, 98, 46)
MARGEN = 16


# ---------------------------------------------------------------- formatos (como en la web)

def num(v, d=1) -> str:
    if v is None:
        return "—"
    r = round(float(v), d)
    s = f"{abs(r):,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("−" if r < 0 else "") + s


def con_signo(v, d=1) -> str:
    if v is None:
        return "—"
    return ("+" if v > 0 else "") + num(v, d)


def tiempo(s, signo=False) -> str:
    if s is None:
        return "—"
    pre = ("+" if s > 0 else "−" if s < 0 else "") if signo else ("−" if s < 0 else "")
    a = abs(round(s))
    if a <= 60:
        return f"{pre}{a} s."
    m, x = divmod(a, 60)
    return f"{pre}{m} min." + (f" {x} s." if x else "")


# ---------------------------------------------------------------- documento

class _PDF(FPDF):
    def __init__(self, pie: str, orientacion: str = "P"):
        super().__init__(orientation=orientacion, format="A4", unit="mm")
        self.pie = pie
        self.set_margins(MARGEN, MARGEN, MARGEN)
        self.set_auto_page_break(True, 16)
        self.add_font("Barlow", "", str(FUENTES / "BarlowSemiCondensed-SemiBold.ttf"))
        self.add_font("Barlow", "B", str(FUENTES / "BarlowSemiCondensed-Bold.ttf"))
        self.add_font("Texto", "", str(FUENTES / "SourceSans3-Regular.ttf"))
        self.add_font("Texto", "B", str(FUENTES / "SourceSans3-Semibold.ttf"))
        self.add_font("Texto", "I", str(FUENTES / "SourceSans3-It.ttf"))
        self.add_font("Mono", "", str(FUENTES / "IBMPlexMono-Regular.ttf"))
        self.add_font("Mono", "B", str(FUENTES / "IBMPlexMono-SemiBold.ttf"))
        self.set_title("Informe FastTack")
        self.set_creator(f"FastTack {__version__}")

    def footer(self):
        self.set_y(-12)
        self.set_font("Texto", "", 8)
        self.set_text_color(*TINTA3)
        pie = self.pie
        while self.get_string_width(pie) > self.w - 2 * MARGEN - 22 and len(pie) > 20:
            pie = pie[:-2]
        self.cell(0, 4, pie if pie == self.pie else pie.rstrip(" ·,") + "…", align="L")
        self.set_x(-MARGEN - 30)
        self.cell(30, 4, f"pág. {self.page_no()}/{{nb}}", align="R")

    # -- piezas
    def seccion(self, titulo: str, sub: str | None = None):
        if self.get_y() > self.h - 45:
            self.add_page()
        self.ln(3)
        self.set_font("Barlow", "B", 11)
        self.set_text_color(*TINTA2)
        self.cell(0, 6, titulo.upper(), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*LINEA)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(1.5)
        if sub:
            self.set_font("Texto", "I", 8.5)
            self.set_text_color(*TINTA3)
            self.multi_cell(0, 4, sub, new_x="LMARGIN", new_y="NEXT")
            self.ln(0.5)

    def texto(self, t: str, tam=10, estilo="", color=TINTA, alto=5):
        self.set_font("Texto", estilo, tam)
        self.set_text_color(*color)
        self.multi_cell(0, alto, t, new_x="LMARGIN", new_y="NEXT", markdown=True)

    def fichas(self, fichas: list[tuple[str, str, str | None, tuple | None]]):
        """[(etiqueta, valor, detalle, color del valor)] en una fila de recuadros."""
        n = len(fichas)
        hueco = 3
        ancho = (self.w - self.l_margin - self.r_margin - hueco * (n - 1)) / n
        y = self.get_y()
        for k, (et, val, det, col) in enumerate(fichas):
            x = self.l_margin + k * (ancho + hueco)
            self.set_fill_color(*FONDO)
            self.set_draw_color(*REJILLA)
            self.rect(x, y, ancho, 19, style="DF")
            self.set_xy(x + 3, y + 2)
            self.set_font("Barlow", "", 7.5)
            self.set_text_color(*TINTA3)
            self.cell(ancho - 6, 4, et.upper())
            self.set_xy(x + 3, y + 6.5)
            tam = 13
            self.set_font("Mono", "B", tam)
            while self.get_string_width(val) > ancho - 6 and tam > 8:   # que quepa en la ficha
                tam -= 0.5
                self.set_font("Mono", "B", tam)
            self.set_text_color(*(col or TINTA))
            self.cell(ancho - 6, 6.5, val)
            if det:
                self.set_xy(x + 3, y + 13.5)
                tam = 7.5
                self.set_font("Texto", "", tam)
                while self.get_string_width(det) > ancho - 6 and tam > 5.5:
                    tam -= 0.25
                    self.set_font("Texto", "", tam)
                self.set_text_color(*TINTA2)
                self.cell(ancho - 6, 4, det)
        self.set_y(y + 22)

    def escora(self, nombre: str, o: dict, f: dict, quien: str):
        """Escora óptima de una ceñida, como en la web (prueba/EscoraOptima.svelte): cifras y gráfico de
        VMG (y SOG) relativa a los vecinos por franja de escora, con la óptima y la del barco marcadas."""
        c = o.get("curva") or {}
        fr = c.get("franjas") or []
        alto = 62 if fr else 14
        if self.get_y() + alto > self.h - 22:
            self.add_page()
        g = lambda x: "—" if x is None else num(x, 1).removesuffix(",0") + "°"
        mia, frente, en = f.get("escora"), f.get("escora_frente_optima"), f.get("escora_en_rango_pct")
        self.set_font("Barlow", "B", 10)
        self.set_text_color(*TINTA)
        self.cell(0, 5.5, nombre, new_x="LMARGIN", new_y="NEXT")
        partes = [f"**Los 5 con más VMG:** {g(o.get('escora'))}" + (f" (entre {g(o['rango'][0])} y {g(o['rango'][1])})" if o.get("rango") else "")]
        if mia is not None:
            lect = "" if frente is None else (" · en la óptima" if abs(frente) <= 2 else " · más escorado" if frente > 0 else " · más plano")
            partes.append(f"**{quien}:** {g(mia)}" + (f" ({con_signo(frente, 1)}°{lect})" if frente is not None else ""))
        if en is not None:
            partes.append(f"**cerca de la óptima (±2°):** {num(en, 0)} % del tiempo")
        self.texto(" · ".join(partes), tam=9, alto=4.6)
        if not fr:
            return
        # gráfico
        x0, x1 = self.l_margin + 14, self.w - self.r_margin - 2
        y0 = self.get_y() + 2
        y1 = y0 + 40
        xlo, xhi = fr[0]["desde"], fr[-1]["hasta"]
        vals = [q["vmg_rel_pct"] for q in fr] + [q["sog_rel_pct"] for q in fr if q.get("sog_rel_pct") is not None]
        ylo, yhi = min(vals + [99]) - 1, max(vals + [100]) + 1
        X = lambda e: x0 + (e - xlo) / ((xhi - xlo) or 1) * (x1 - x0)
        Y = lambda v: y1 - (v - ylo) / ((yhi - ylo) or 1) * (y1 - y0)
        cl = lambda e: max(xlo, min(xhi, e))
        rg = c.get("rango")
        if rg:
            self.set_fill_color(222, 234, 248)
            self.rect(X(rg[0]), y0, max(0, X(rg[1]) - X(rg[0])), y1 - y0, style="F")
        self.set_font("Mono", "", 6.5)
        self.set_text_color(*TINTA3)
        for v in (ylo + 1, 100, yhi - 1):
            self.set_draw_color(*(LINEA if v == 100 else REJILLA))
            self.set_line_width(0.2)
            self.line(x0, Y(v), x1, Y(v))
            self.set_xy(self.l_margin, Y(v) - 2)
            self.cell(12.5, 4, f"{num(v, 0)} %", align="R")
        for e in [q["desde"] for q in fr] + [xhi]:
            self.set_xy(X(e) - 6, y1 + 0.8)
            self.cell(12, 3.5, f"{e}°", align="C")
        cx = [X((q["desde"] + q["hasta"]) / 2) for q in fr]
        if fr[0].get("sog_rel_pct") is not None:
            self.set_draw_color(138, 150, 156)
            self.set_line_width(0.3)
            self.set_dash_pattern(dash=1.4, gap=1.1)
            pts = [(x, Y(q["sog_rel_pct"])) for x, q in zip(cx, fr) if q.get("sog_rel_pct") is not None]
            for a, b in zip(pts, pts[1:]):
                self.line(*a, *b)
            self.set_dash_pattern()
        self.set_draw_color(*AZUL)
        self.set_line_width(0.55)
        pts = [(x, Y(q["vmg_rel_pct"])) for x, q in zip(cx, fr)]
        for a, b in zip(pts, pts[1:]):
            self.line(*a, *b)
        self.set_draw_color(255, 255, 255)
        self.set_line_width(0.4)
        for (x, y), q in zip(pts, fr):
            dentro = rg and q["desde"] >= rg[0] and q["hasta"] <= rg[1]
            self.set_fill_color(*(AZUL if dentro else (138, 150, 156)))
            self.circle(x, y, 1.3, style="DF")
        self.set_font("Mono", "", 6.5)
        if o.get("escora") is not None:
            self.set_draw_color(*TINTA2)
            self.set_line_width(0.35)
            self.set_dash_pattern(dash=1.1, gap=0.8)
            self.line(X(cl(o["escora"])), y0, X(cl(o["escora"])), y1)
            self.set_dash_pattern()
            self.set_text_color(*TINTA2)
            self.set_xy(X(cl(o["escora"])) + 1, y0 + 0.3)
            self.cell(30, 3, "5 con más VMG")
        if mia is not None:
            self.set_draw_color(*NARANJA)
            self.set_line_width(0.55)
            self.line(X(cl(mia)), y0, X(cl(mia)), y1)
            self.set_text_color(*NARANJA)
            self.set_xy(X(cl(mia)) + 1, y0 + 3.6)
            self.cell(30, 3, quien)
        self.set_line_width(0.2)
        # leyenda
        self.set_xy(x0, y1 + 5.5)
        self.set_font("Texto", "", 7.5)
        ly = y1 + 7.3
        x = x0
        for col, et, raya in ((AZUL, "VMG", None), ((138, 150, 156), "SOG", 1), ((222, 234, 248), "franjas sin pérdida", "caja"),
                              (NARANJA, quien, None), (TINTA2, "óptima (5 con más VMG)", 1)):
            if raya == "caja":
                self.set_fill_color(*col)
                self.rect(x, ly - 1.3, 5, 2.6, style="F")
            else:
                self.set_draw_color(*col)
                self.set_line_width(0.5)
                if raya:
                    self.set_dash_pattern(dash=1.1, gap=0.8)
                self.line(x, ly, x + 5, ly)
                self.set_dash_pattern()
            self.set_text_color(*TINTA2)
            self.set_xy(x + 6, ly - 2)
            w = self.get_string_width(et) + 2
            self.cell(w, 4, et)
            x += 6 + w + 4
        self.set_line_width(0.2)
        self.set_y(y1 + 11)

    def tabla(self, cabecera: list[str], filas: list[list], anchos: list[float], alinear: list[str],
              colores: list[list] | None = None, resaltar: set[int] | None = None, tam=8.5):
        """Tabla simple; colores[i][j] = color del texto de la celda; resaltar = filas en negrita."""
        alto = 5.6
        self.set_font("Barlow", "", 7.5)
        self.set_text_color(*TINTA2)
        self.set_draw_color(*LINEA)
        x0 = self.get_x()
        for c, w, a in zip(cabecera, anchos, alinear):
            self.cell(w, alto, c.upper(), border="B", align=a)
        self.ln(alto)
        for i, fila in enumerate(filas):
            if self.get_y() > self.h - 24:
                self.add_page()
            if resaltar and i in resaltar:
                self.set_fill_color(252, 236, 228)
                self.rect(x0, self.get_y(), sum(anchos), alto, style="F")
            for j, (v, w, a) in enumerate(zip(fila, anchos, alinear)):
                mono = a == "R"
                self.set_font("Mono" if mono else "Texto", "B" if resaltar and i in resaltar else "", tam - (0.6 if mono else 0))
                col = (colores[i][j] if colores and colores[i][j] else TINTA)
                self.set_text_color(*col)
                self.cell(w, alto, str(v), align=a)
            self.ln(alto)
            self.set_draw_color(*REJILLA)
            self.line(x0, self.get_y(), x0 + sum(anchos), self.get_y())

    def barras(self, filas: list[tuple[str, float | None]], escala: float):
        """Barras divergentes: + (perdido) en rojo a la derecha, − (ganado) en azul a la izquierda."""
        ancho_et, ancho_val = 32, 32
        x0 = self.l_margin
        ancho = self.w - self.l_margin - self.r_margin - ancho_et - ancho_val
        medio = x0 + ancho_et + ancho / 2
        for et, s in filas:
            y = self.get_y()
            self.set_font("Texto", "", 9.5)
            self.set_text_color(*TINTA2)
            self.cell(ancho_et, 6, et)
            self.set_draw_color(*LINEA)
            self.line(medio, y + 0.5, medio, y + 5.5)
            if s:
                w = min(abs(s) / escala, 1) * (ancho / 2 - 2)
                self.set_fill_color(*(ROJO if s > 0 else AZUL))
                self.rect(medio if s > 0 else medio - w, y + 1.4, w, 3.2, style="F")
            self.set_x(x0 + ancho_et + ancho)
            self.set_font("Mono", "B", 9)
            self.set_text_color(*(TINTA3 if s is None else ROJO if s > 0 else AZUL if s < 0 else TINTA))
            self.cell(ancho_val, 6, "sin datos" if s is None else tiempo(s, signo=True), align="R")
            self.ln(6)


# ---------------------------------------------------------------- contenido

MEDIAS = (("VMG en ceñida", "vmg_ceñida", "kn", 2, True), ("VMG en popa", "vmg_popa", "kn", 2, True),
          ("SOG en ceñida", "sog_ceñida", "kn", 2, True), ("SOG en popa", "sog_popa", "kn", 2, True),
          ("TWA en ceñida", "twa_ceñida", "grados", 1, None), ("TWA en popa", "twa_popa", "grados", 1, None),
          ("Escora en ceñida", "escora_ceñida", "grados", 0, None), ("Escora en popa", "escora_popa", "grados", 0, None))
UNIDAD = {"kn": " kn.", "grados": "°", "m": " m."}


def _clave(base, u, sufijo=""):
    return f"{base}{sufijo}_m" if u == "m" else f"{base}{sufijo}_{u}"


def _por_que(p: dict | None, corto: bool = False) -> str:
    """«peor que el top 5 por velocidad y ángulo: más lento y más abierto» (corto: «más lento, más abierto»)."""
    if not p:
        return "—"
    if p["vmg"].startswith("igual"):
        return "igual" if corto else "igual que el top 5"
    rasgos = [x.split(" (")[0] for x in (p.get("velocidad"), p.get("angulo")) if x]
    if corto:
        return ", ".join(rasgos) or ("sin causa clara" if p["vmg"].startswith("peor") else "mejor")
    t = p["vmg"] + (f", por {p['causa']}" if p.get("causa") and not p["causa"].startswith("sin") else "")
    return t + (": " + " y ".join(rasgos) if rasgos else "")


def _markdown(pdf: _PDF, texto: str):
    """Encabezados, listas y **negrita** del debrief."""
    for linea in texto.splitlines():
        t = linea.strip()
        if not t:
            pdf.ln(1.5)
            continue
        if m := re.match(r"^#{1,4}\s+(.*)", t):
            if pdf.get_y() > pdf.h - 40:
                pdf.add_page()
            pdf.ln(1.5)
            pdf.set_font("Barlow", "B", 12)
            pdf.set_text_color(*AZUL_OSC)
            pdf.multi_cell(0, 6, m[1].replace("**", ""), new_x="LMARGIN", new_y="NEXT")
            continue
        marca, cuerpo = None, t
        if m := re.match(r"^(\d+)[.)]\s+(.*)", t):
            marca, cuerpo = f"{m[1]}.", m[2]
        elif m := re.match(r"^[-*•]\s+(.*)", t):
            marca, cuerpo = "•", m[1]
        pdf.set_font("Texto", "", 10)
        pdf.set_text_color(*TINTA)
        if marca:
            pdf.set_x(pdf.l_margin + 2)
            pdf.cell(5, 5.2, marca)
            pdf.multi_cell(0, 5.2, cuerpo, new_x="LMARGIN", new_y="NEXT", markdown=True)
        else:
            pdf.multi_cell(0, 5.2, cuerpo, new_x="LMARGIN", new_y="NEXT", markdown=True)
        pdf.ln(0.6)


from .paginas import generar  # noqa: E402,F401  (el informe se compone en paginas.py)
