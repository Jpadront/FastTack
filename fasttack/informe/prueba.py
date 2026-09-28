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
    def __init__(self, pie: str):
        super().__init__(format="A4", unit="mm")
        self.pie = pie
        self.set_margins(MARGEN, MARGEN, MARGEN)
        self.set_auto_page_break(True, 18)
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
        self.cell(0, 4, self.pie, align="L")
        self.set_x(-MARGEN - 30)
        self.cell(30, 4, f"pág. {self.page_no()}/{{nb}}", align="R")

    # -- piezas
    def seccion(self, titulo: str, sub: str | None = None):
        if self.get_y() > 250:
            self.add_page()
        self.ln(3)
        self.set_font("Barlow", "B", 11)
        self.set_text_color(*TINTA2)
        self.cell(0, 6, titulo.upper(), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*LINEA)
        self.line(MARGEN, self.get_y(), self.w - MARGEN, self.get_y())
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
        ancho = (self.w - 2 * MARGEN - hueco * (n - 1)) / n
        y = self.get_y()
        for k, (et, val, det, col) in enumerate(fichas):
            x = MARGEN + k * (ancho + hueco)
            self.set_fill_color(*FONDO)
            self.set_draw_color(*REJILLA)
            self.rect(x, y, ancho, 19, style="DF")
            self.set_xy(x + 3, y + 2)
            self.set_font("Barlow", "", 7.5)
            self.set_text_color(*TINTA3)
            self.cell(ancho - 6, 4, et.upper())
            self.set_xy(x + 3, y + 6.5)
            self.set_font("Mono", "B", 13)
            self.set_text_color(*(col or TINTA))
            self.cell(ancho - 6, 6.5, val)
            if det:
                self.set_xy(x + 3, y + 13.5)
                self.set_font("Texto", "", 7.5)
                self.set_text_color(*TINTA2)
                self.cell(ancho - 6, 4, det)
        self.set_y(y + 22)

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
        ancho = self.w - 2 * MARGEN - ancho_et - ancho_val
        medio = MARGEN + ancho_et + ancho / 2
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
            self.set_x(MARGEN + ancho_et + ancho)
            self.set_font("Mono", "B", 9)
            self.set_text_color(*(TINTA3 if s is None else ROJO if s > 0 else AZUL if s < 0 else TINTA))
            self.cell(ancho_val, 6, "sin datos" if s is None else tiempo(s, signo=True), align="R")
            self.ln(6)


# ---------------------------------------------------------------- contenido

MEDIAS = (("VMG en ceñida", "vmg_ceñida", "kn", 2, True), ("VMG en popa", "vmg_popa", "kn", 2, True),
          ("SOG en ceñida", "sog_ceñida", "kn", 2, True), ("SOG en popa", "sog_popa", "kn", 2, True),
          ("TWA en ceñida", "twa_ceñida", "grados", 1, None), ("TWA en popa", "twa_popa", "grados", 1, None),
          ("Escora en ceñida", "escora_ceñida", "grados", 0, None), ("Escora en popa", "escora_popa", "grados", 0, None),
          ("Pérdida por virada", "perdida_virada", "m", 0, False), ("Pérdida por trasluchada", "perdida_trasluchada", "m", 0, False))
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
            pdf.set_x(MARGEN + 2)
            pdf.cell(5, 5.2, marca)
            pdf.multi_cell(0, 5.2, cuerpo, new_x="LMARGIN", new_y="NEXT", markdown=True)
        else:
            pdf.multi_cell(0, 5.2, cuerpo, new_x="LMARGIN", new_y="NEXT", markdown=True)
        pdf.ln(0.6)


def generar(alm: Almacen, camp_id: str, clave: str, barco: str) -> bytes:
    camp = camp_mod.leer(alm, camp_id)
    if camp is None:
        raise KeyError(camp_id)
    prueba = next((p for p in camp["pruebas"] if p["clave"] == clave), None)
    if prueba is None:
        raise KeyError(clave)
    h = debrief_mod.datos_de(alm, camp_id, clave, barco)
    alias = alm.sql("select alias from campeonato where id=?", (camp_id,))
    nombre_camp = (alias[0]["alias"] if alias and alias[0]["alias"] else None) or camp.get("nombre") or camp_id
    info_barco = next((b for b in camp["barcos"] if b["clave"] == barco), {})
    nombre_barco = h.get("barco") + (f" · {info_barco['nombre']}" if info_barco.get("nombre") else "")
    tz = camp.get("tz_offset_ms") or 0
    fecha = dt.datetime.fromtimestamp((prueba["senal"] + tz) / 1000, tz=dt.timezone.utc)
    p = h.get("prueba", {})
    num_prueba = p.get("numero") or prueba.get("numero")

    pdf = _PDF(f"FastTack {__version__} · {nombre_camp} · prueba {num_prueba} · {h.get('barco')} · "
               "cifras estimadas a partir del GPS de los barcos (sin anemómetro)")
    pdf.alias_nb_pages()
    pdf.add_page()

    # Cabecera
    pdf.set_fill_color(*TINTA)
    pdf.rect(0, 0, pdf.w, 30, style="F")
    pdf.set_xy(MARGEN, 7)
    pdf.set_font("Barlow", "B", 20)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 9, f"Prueba {num_prueba} · Informe de rendimiento", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Texto", "", 10)
    pdf.set_text_color(200, 210, 214)
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    pdf.cell(0, 5, f"{nombre_camp} · {camp.get('clase') or ''} · {fecha.day} de {meses[fecha.month - 1]} de {fecha.year}, "
                   f"{fecha:%H:%M}".replace(" ·  ·", " ·"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Barlow", "", 11)
    pdf.set_text_color(*NARANJA)
    pdf.cell(0, 6, nombre_barco)
    pdf.set_y(36)

    # Fichas
    dsp = h.get("donde_se_perdio_la_prueba") or {}
    tot = dsp.get("total_frente_al_top5_s")
    fichas = [("Puesto", f"{p['puesto']}.º" if p.get("puesto") else "—", f"de {p.get('barcos_llegados')} llegados" if p.get("barcos_llegados") else None, None),
              ("Detrás del ganador", tiempo(p.get("detras_del_ganador_s")), None, None)]
    if tot is not None:
        fichas.append(("Frente al top 5", tiempo(tot, signo=True), "tiempo perdido (+) o ganado (−)", ROJO if tot > 0 else AZUL))
    vref = p.get("viento_referencia_kn")
    fichas.append(("Viento", f"{num(vref, 0)} kn." if vref else "—", None if vref else "sin viento de referencia", None))
    pdf.fichas(fichas)
    if p.get("llegadas") and "oficial" not in str(p.get("llegadas")):
        pdf.texto(f"Llegadas {p['llegadas']}.", tam=8.5, estilo="I", color=TINTA3, alto=4)

    # Dónde se perdió
    if dsp:
        pdf.seccion("Dónde se perdió la prueba", "En el orden de la prueba. Tiempo perdido (+) o ganado (−) frente al tiempo mediano de los 5 primeros. "
                    "Velocidad: con tu VMG navegando estable; maniobras: viradas y trasluchadas; táctica y resto: lo que falta "
                    "hasta la diferencia real (roladas, lado, laylines, rodeos).")
        # En el orden de la prueba: la salida y cada tramo (el primero, sin la salida)
        sal = dsp.get("salida_s") if not isinstance(dsp.get("salida_s"), str) else None
        pt = dsp.get("por_tramo", [])
        partes = [("Salida", sal)] + [(x["tramo"], None if x.get("sin_datos") else
                                       x["total_s"] - ((x.get("salida_s") or 0) if k == 0 else 0)) for k, x in enumerate(pt)]
        escala = max([30] + [abs(v) for _, v in partes if v])
        pdf.barras(partes, escala)
        pdf.ln(1)
        tipos = [("velocidad", dsp.get("velocidad_s")), ("maniobras", dsp.get("maniobras_s")), ("táctica y resto", dsp.get("tactica_y_resto_s"))]
        pdf.texto("Por tipo: " + " · ".join(f"{k} **{tiempo(v, True)}**" for k, v in tipos if v is not None), tam=9.5, color=TINTA2)
        con = [x for x in pt if not x.get("sin_datos")]
        if con:
            pdf.ln(1)
            filas = [[x["tramo"], tiempo(x["total_s"] - ((x.get("salida_s") or 0) if x is pt[0] else 0), True), tiempo(x.get("velocidad_s"), True),
                      tiempo(x.get("maniobras_s"), True), tiempo(x.get("tactica_y_resto_s"), True)] for x in con]
            col = [[None] + [ROJO if (v or 0) > 0 else AZUL if (v or 0) < 0 else None
                             for v in (x["total_s"] - ((x.get("salida_s") or 0) if x is pt[0] else 0), x.get("velocidad_s"),
                                       x.get("maniobras_s"), x.get("tactica_y_resto_s"))] for x in con]
            pdf.tabla(["Tramo", "Total", "Velocidad", "Maniobras", "Táctica y resto"], filas,
                      [42, 34, 34, 34, 34], ["L", "R", "R", "R", "R"], col)
        pdf.texto("Cada tramo se compara con la mediana del top 5 en ese tramo: la suma no coincide exactamente con la diferencia en la llegada.",
                  tam=8, estilo="I", color=TINTA3, alto=4)

    # Medias frente al top 5
    md = h.get("medias_de_la_prueba") or {}
    if md:
        pdf.seccion("Medias de la prueba frente al top 5", "Top 5 = mediana de los 5 primeros de la prueba (sin contarte). "
                    "VMG, TWA y pérdidas son estimadas con el viento reconstruido.")
        filas, col = [], []
        for et, base, u, d, mas_mejor in MEDIAS:
            yo, t5, dif = md.get(_clave(base, u)), md.get(_clave(base, u, "_top5")), md.get(_clave(base, u, "_frente_al_top5"))
            if yo is None and t5 is None:
                continue
            ud = UNIDAD[u]
            filas.append([et, num(yo, d) + ud if yo is not None else "—", num(t5, d) + ud if t5 is not None else "—",
                          con_signo(dif, d) + ud if dif is not None else "—"])
            bien = None if dif is None or mas_mejor is None or abs(dif) < 10 ** -d else (dif > 0) == mas_mejor
            col.append([None, None, None, None if bien is None else AZUL if bien else ROJO])
        pdf.tabla(["", "Tú", "Top 5", "Diferencia"], filas, [62, 38, 38, 40], ["L", "R", "R", "R"], col)
        pq = [(m, md.get(f"vmg_{m}_frente_al_top5_por_que")) for m in ("ceñida", "popa")]
        pq = [(m, x) for m, x in pq if x]
        if pq:
            pdf.ln(1.5)
            for m, x in pq:
                pdf.texto(f"**VMG en {m}:** {_por_que(x)}.", tam=9.5, alto=5)

    # Tramo a tramo
    tramos = [t for t in h.get("tramos", []) if not t.get("sin_datos_del_barco")]
    if tramos:
        pdf.seccion("Tramo a tramo", "Puesto al final del tramo; VMG frente a la mediana del top 5 y por qué; "
                    "escora frente a la óptima (media de los 5 con más VMG del tramo); tiempo en la amura favorecida "
                    "con el viento en tu sitio (roles locales).")
        filas, col = [], []
        for t in tramos:
            lay = t.get("layline") or {}
            esc = (t.get("escora_optima") or {}).get("escora_del_barco_frente_a_ella_grados")
            tac = t.get("tactica") or {}
            gan = t.get("puestos_ganados")
            filas.append([t["nombre"],
                          f"{t.get('puesto_al_final') or '—'}" + (f" ({con_signo(gan, 0)})" if gan else ""),
                          con_signo(t.get("vmg_frente_al_top5_kn"), 2) + " kn." if t.get("vmg_frente_al_top5_kn") is not None else "—",
                          _por_que(t.get("vmg_frente_al_top5_por_que"), corto=True),
                          f"{t.get('maniobras', '—')}" + (f" · {num(t.get('perdida_en_maniobras_m'), 0)} m." if t.get("perdida_en_maniobras_m") else ""),
                          ("+" + num(lay.get("exceso_m"), 0) + " m." if lay.get("estado") == "sobrepasada" else "ok" if lay.get("estado") == "correcta" else "—"),
                          (con_signo(esc, 1) + "°") if esc is not None else "—",
                          (num(tac.get("amura_favorecida_pct"), 0) + " %") if tac.get("amura_favorecida_pct") is not None else "—"])
            v = t.get("vmg_frente_al_top5_kn")
            col.append([None, (AZUL if (gan or 0) > 0 else ROJO if (gan or 0) < 0 else None),
                        (None if v is None or abs(v) < 0.03 else AZUL if v > 0 else ROJO), None, None,
                        ROJO if lay.get("estado") == "sobrepasada" else None, (ROJO if esc is not None and abs(esc) > 2 else None), None])
        pdf.tabla(["Tramo", "Puesto", "VMG vs top 5", "Por qué", "Maniobras", "Layline", "Escora", "Amura fav."],
                  filas, [19, 17, 21, 50, 20, 17, 17, 17], ["L", "R", "R", "L", "R", "R", "R", "R"], col, tam=8)

    # Debrief
    d = debrief_mod.leer(alm, camp_id, clave, barco)
    pdf.add_page()
    pdf.set_font("Barlow", "B", 16)
    pdf.set_text_color(*TINTA)
    pdf.cell(0, 8, f"Debrief de la prueba {num_prueba}", new_x="LMARGIN", new_y="NEXT")
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
