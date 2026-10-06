"""Informe en PDF del campeonato o de un día: rendimiento frente al top 5 y el debrief de la IA.

Mismas cifras que el debrief del campeonato o del día (ia.debrief.datos_de con ámbito «campeonato»
o «dia:AAAA-MM-DD»).
"""
from __future__ import annotations

import datetime as dt

from .. import __version__
from ..ia import debrief as debrief_mod
from ..ingesta import campeonato as camp_mod
from ..ingesta.almacen import Almacen
from .graficos import logo
from .prueba import (AZUL, MARGEN, NARANJA, ROJO, TINTA, TINTA3, _PDF, _clave, _markdown, _por_que,
                     con_signo, num, tiempo)

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
DIFS = (("VMG en ceñida", "vmg_ceñida", "kn", 2, True), ("VMG en popa", "vmg_popa", "kn", 2, True),
        ("SOG en ceñida", "sog_ceñida", "kn", 2, True), ("SOG en popa", "sog_popa", "kn", 2, True),
        ("TWA en ceñida (+ = más abierto)", "twa_ceñida", "grados", 1, None),
        ("TWA en popa (+ = más bajo)", "twa_popa", "grados", 1, None),
        # la escora solo llega en el día (en el campeonato mezcla vientos muy distintos)
        ("Escora en ceñida", "escora_ceñida", "grados", 0, None), ("Escora en popa", "escora_popa", "grados", 0, None),
        ("Pérdida por virada", "perdida_virada", "m", 1, False), ("Pérdida por trasluchada", "perdida_trasluchada", "m", 1, False))
UNIDAD = {"kn": " kn.", "grados": "°", "m": " m."}


def _color(v, mas_mejor, d=1):
    if v is None or mas_mejor is None or abs(v) < 10 ** -d:
        return None
    return AZUL if (v > 0) == mas_mejor else ROJO


def _fecha(ms, tz):
    f = dt.datetime.fromtimestamp((ms + tz) / 1000, tz=dt.timezone.utc)
    return f"{f.day} de {MESES[f.month - 1]} de {f.year}"


def _cabecera(pdf: _PDF, titulo: str, sub: str, barco: str):
    pdf.set_fill_color(15, 42, 54)
    pdf.rect(0, 0, pdf.w, 30, style="F")
    logo(pdf, pdf.w - MARGEN - 31, 8, 8.5)
    pdf.set_xy(MARGEN, 7)
    pdf.set_font("Barlow", "B", 20)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 9, titulo, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Texto", "", 10)
    pdf.set_text_color(200, 210, 214)
    pdf.cell(0, 5, sub, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Barlow", "", 11)
    pdf.set_text_color(*NARANJA)
    pdf.cell(0, 6, barco)
    pdf.set_y(36)


def generar(alm: Almacen, camp_id: str, ambito: str, barco: str) -> bytes:
    camp = camp_mod.leer(alm, camp_id)
    if camp is None:
        raise KeyError(camp_id)
    if ambito != "campeonato" and not ambito.startswith("dia:"):
        raise ValueError("Ámbito no válido: «campeonato» o «dia:AAAA-MM-DD».")
    h = debrief_mod.datos_de(alm, camp_id, ambito, barco)
    dia = ambito.startswith("dia:")
    alias = alm.sql("select alias from campeonato where id=?", (camp_id,))
    nombre_camp = (alias[0]["alias"] if alias and alias[0]["alias"] else None) or camp.get("nombre") or camp_id
    info = next((b for b in camp["barcos"] if b["clave"] == barco), {})
    nombre_barco = h.get("barco", barco) + (f" · {info['nombre']}" if info.get("nombre") else "")
    tz = camp.get("tz_offset_ms") or 0
    if dia:
        f = dt.date.fromisoformat(ambito[4:])
        titulo = f"Informe del día · {h.get('dia', '')}".strip()
        sub = f"{nombre_camp} · {camp.get('clase') or ''} · {f.day} de {MESES[f.month - 1]} de {f.year}"
    else:
        titulo = "Informe del campeonato"
        fechas = ""
        if camp.get("inicio") and camp.get("fin"):
            fechas = f" · del {_fecha(camp['inicio'], tz)} al {_fecha(camp['fin'], tz)}"
        sub = f"{nombre_camp} · {camp.get('clase') or ''}{fechas}"
    pdf = _PDF(f"FastTack {__version__} · {nombre_camp} · {h.get('dia') or 'campeonato'} · {h.get('barco')} · "
               "cifras estimadas a partir del GPS de los barcos (sin anemómetro)")
    pdf.alias_nb_pages()
    pdf.add_page()
    _cabecera(pdf, titulo, sub.replace(" ·  ·", " ·"), nombre_barco)

    # Fichas
    medias = h.get("medias_del_dia" if dia else "medias_del_campeonato") or {}
    fichas = []
    if dia:
        r = h.get("resultado_del_dia") or {}
        g = h.get("general_tras_el_dia") or {}
        fichas.append(("Puesto del día", f"{r['puesto_del_dia']}.º" if r.get("puesto_del_dia") else "—",
                       f"de {r.get('barcos')} · {r.get('pruebas_del_dia')} pruebas" if r.get("barcos") else None, None))
        fichas.append(("General tras el día", f"{g['puesto']}.º" if g.get("puesto") else "—",
                       f"de {g.get('barcos')} · {g.get('pruebas_hasta_hoy')} pruebas" if g.get("barcos") else None, None))
    else:
        g = h.get("general_calculada") or {}
        e = h.get("estado") or {}
        fichas.append(("Puesto en la general", f"{g['puesto']}.º" if g.get("puesto") else "—",
                       f"de {g.get('barcos')} · {g.get('lectura', '')}" if g.get("barcos") else None, None))
        fichas.append(("Pruebas", str(e.get("pruebas_disputadas_hasta_ahora") or len(h.get("pruebas", []))),
                       "campeonato en curso" if e.get("campeonato_en_curso") else "general calculada", None))
    for m in ("ceñida", "popa"):
        v = medias.get(f"vmg_{m}_frente_al_top5_kn")
        fichas.append((f"VMG en {m} vs top 5", (con_signo(v, 2) + " kn.") if v is not None else "—",
                       _por_que(medias.get(f"vmg_{m}_frente_al_top5_por_que"), corto=True), _color(v, True, 2)))
    pdf.fichas(fichas)

    # Prueba a prueba
    pruebas = h.get("pruebas") or []
    if pruebas:
        pdf.seccion("Prueba a prueba", "Velocidad: semáforo de la VMG frente a toda la flota (bien: en el 20 % de arriba; normal: del 20 al 50 %; mal: en la mitad de abajo). VMG media de las ceñidas y de las popas frente a la mediana del top 5 "
                    "de la prueba, y por qué (velocidad o ángulo)."
                    + (" Tiempo frente al top 5: dónde se perdió cada prueba." if dia else ""))
        from .. import servicio
        from .paginas import SEMAFORO
        sems = servicio.semaforos_campeonato(alm, camp_id, barco)
        clave_de = {q["numero"]: q["clave"] for q in camp["pruebas"]}
        cab = ["Prueba", "Puesto", "Velocidad", "Ceñida", "Por qué", "Popa", "Por qué"]
        anchos = [15, 15, 19, 21, 43, 21, 44]
        if dia:
            cab += ["Total"]
            anchos = [14, 13, 18, 19, 37, 19, 37, 21]
        filas, col = [], []
        for p in pruebas:
            vc, vp = p.get("vmg_ceñida_frente_al_top5_kn"), p.get("vmg_popa_frente_al_top5_kn")
            sem = sems.get(clave_de.get(p["prueba"]))
            fila = [f"P{p['prueba']}", str(p.get("puesto") or "—"), sem["nivel"] if sem else "—",
                    (con_signo(vc, 2) + " kn.") if vc is not None else "—", _por_que(p.get("vmg_ceñida_frente_al_top5_por_que"), corto=True),
                    (con_signo(vp, 2) + " kn.") if vp is not None else "—", _por_que(p.get("vmg_popa_frente_al_top5_por_que"), corto=True)]
            c = [None, None, SEMAFORO[sem["nivel"]] if sem else None, _color(vc, True, 2), None, _color(vp, True, 2), None]
            if dia:
                tot = (p.get("donde_se_perdio_la_prueba") or {}).get("total_frente_al_top5_s")
                fila.append(tiempo(tot, True))
                c.append(ROJO if (tot or 0) > 0 else AZUL if (tot or 0) < 0 else None)
            if p.get("metricas", "sí") != "sí":
                fila[3:7] = ["—", "sin métricas", "—", ""]
            filas.append(fila)
            col.append(c)
        pdf.tabla(cab, filas, anchos, ["L", "R", "L", "R", "L", "R", "L"] + (["R"] if dia else []), col, tam=8)
        rec = h.get("vmg_frente_al_top5_prueba_a_prueba") or {}
        lineas = []
        for m in ("ceñida", "popa"):
            x = rec.get(m)
            if x:
                t = (f"**{m.capitalize()}:** peor que el top 5 en {x['peor_que_el_top5']} de {x['pruebas_con_dato']} pruebas"
                     if x["peor_que_el_top5"] else f"**{m.capitalize()}:** no fue peor que el top 5 en ninguna de las {x['pruebas_con_dato']} pruebas")
                if x["peor_que_el_top5"]:
                    t += f" (por velocidad en {x['en_las_peores_por_velocidad']}, por ángulo en {x['en_las_peores_por_angulo']})"
                lineas.append(t + (f"; mejor en {x['mejor_que_el_top5']}" if x.get("mejor_que_el_top5") else "") + ".")
        if lineas:
            pdf.ln(1.5)
            for t in lineas:
                pdf.texto(t, tam=9.5, alto=5)

    # Mejores y peores tramos (día)
    if dia and (h.get("mejores_tramos") or h.get("peores_tramos")):
        pdf.seccion("Mejores y peores tramos del día", "Por la VMG frente al top 5 de cada prueba.")
        for nombre, lista in (("Mejores", h.get("mejores_tramos")), ("Peores", h.get("peores_tramos"))):
            if lista:
                pdf.texto(f"**{nombre}:** " + " · ".join(f"{x['tramo']} de la P{x['prueba']} ({con_signo(x.get('vmg_frente_al_top5_kn'), 2)} kn.)"
                                                        for x in lista), tam=9.5, alto=5)

    # Medias frente al top 5
    if medias:
        pdf.seccion(f"Medias {'del día' if dia else 'del campeonato'} frente al top 5",
                    "Diferencia con la mediana del top 5 (" + ("del día" if dia else "de la general") + ", sin contarte). "
                    "Azul: mejor que el top 5; rojo: peor.")
        filas, col = [], []
        for et, base, u, d, mas_mejor in DIFS:
            v = medias.get(_clave(base, u, "_frente_al_top5"))
            if v is None:
                continue
            filas.append([et, con_signo(v, d) + UNIDAD[u]])
            col.append([None, _color(v, mas_mejor, d)])
        pdf.tabla(["", "Frente al top 5"], filas, [110, 40], ["L", "R"], col)
        for m in ("ceñida", "popa"):
            x = medias.get(f"vmg_{m}_frente_al_top5_por_que")
            if x:
                pdf.texto(f"**VMG en {m}:** {_por_que(x)}.", tam=9.5, alto=5)

    # Salidas, laylines y puertas
    s, s5 = h.get("salidas") or {}, h.get("salidas_top5") or {}
    lay, pu, pu5 = h.get("laylines") or {}, h.get("puertas") or {}, h.get("puertas_top5") or {}
    if s or lay or pu:
        pdf.seccion("Salidas, laylines y puertas", "Frente al top 5 (" + ("del día" if dia else "de la general") + ").")
        pct = lambda a, b: f" ({num(a / b * 100, 0)} %)" if b else ""
        filas = []
        if s.get("salidas_con_puesto_a_60_s"):
            filas.append(["En el top 10 a los 60 s. de la salida",
                          f"{s['veces_en_el_top_10_a_60_s']} de {s['salidas_con_puesto_a_60_s']}" + pct(s["veces_en_el_top_10_a_60_s"], s["salidas_con_puesto_a_60_s"]),
                          (f"{s5['veces_en_el_top_10_a_60_s']} de {s5['salidas_con_puesto_a_60_s']}" + pct(s5["veces_en_el_top_10_a_60_s"], s5["salidas_con_puesto_a_60_s"]))
                          if s5.get("salidas_con_puesto_a_60_s") else "—"])
        if s.get("margen_medio_m") is not None:
            filas.append(["Distancia media a la línea en la señal", num(s["margen_medio_m"], 1) + " m.",
                          num(s5.get("margen_medio_mediana_m"), 1) + " m." if s5.get("margen_medio_mediana_m") is not None else "—"])
        if s.get("ocs_segun_el_comite"):
            filas.append(["OCS (según el comité)", str(s["ocs_segun_el_comite"]), "—"])
        if lay.get("tramos_con_dato"):
            filas.append(["Laylines correctas", f"{lay['correctas']} de {lay['tramos_con_dato']}" + pct(lay["correctas"], lay["tramos_con_dato"]),
                          num(lay.get("correctas_top5_pct"), 0) + " %" if lay.get("correctas_top5_pct") is not None else "—"])
            if lay.get("sobrepasadas"):
                filas.append(["Sobrepasadas por cálculo / por tráfico",
                              f"{lay.get('sobrepasadas_por_calculo_o_sin_dato', 0)} / {lay.get('sobrepasadas_por_trafico', 0)}"
                              + (f" · {num(lay['exceso_medio_m'], 0)} m. de exceso" if lay.get("exceso_medio_m") else ""), "—"])
        if pu.get("puertas_con_ventaja_clara"):
            filas.append(["Puerta favorecida (ventaja ≥ 5 m.)", f"{pu['eligio_la_favorecida']} de {pu['puertas_con_ventaja_clara']}" + pct(pu["eligio_la_favorecida"], pu["puertas_con_ventaja_clara"]),
                          (f"{pu5['eligieron_la_favorecida']} de {pu5['puertas_con_ventaja_clara']}" + pct(pu5["eligieron_la_favorecida"], pu5["puertas_con_ventaja_clara"]))
                          if pu5.get("puertas_con_ventaja_clara") else "—"])
        pdf.tabla(["", "Tú", "Top 5"], filas, [86, 50, 42], ["L", "R", "R"])

    # Debrief
    d = debrief_mod.leer(alm, camp_id, ambito, barco)
    pdf.add_page()
    pdf.set_font("Barlow", "B", 16)
    pdf.set_text_color(*TINTA)
    pdf.cell(0, 8, f"Debrief {'del ' + h['dia'] if dia and h.get('dia') else 'del campeonato'}", new_x="LMARGIN", new_y="NEXT")
    if not d:
        pdf.texto("Aún no hay debrief: genéralo en la sección «Debrief IA» del resumen y vuelve a descargar el informe.",
                  tam=10, estilo="I", color=TINTA3)
    else:
        vigente = d["huella"] == debrief_mod.huella(h)
        cuando = dt.datetime.fromtimestamp(d["creado_en"] / 1000, tz=dt.timezone.utc) + dt.timedelta(milliseconds=tz)
        nota = f"Redactado por IA ({'Claude Code' if d['origen'] == 'claude-code' else 'texto pegado'}) el {cuando:%d/%m/%Y} con las cifras de FastTack."
        if not vigente:
            nota += " Las cifras han cambiado desde entonces (nuevas pruebas, nueva versión del cálculo o viento de referencia): conviene regenerarlo."
        avisos = debrief_mod.no_verificadas(d["texto"], h)
        if avisos:
            nota += f" Cifras sin comprobar en los datos: {', '.join(avisos[:6])}."
        pdf.texto(nota, tam=8.5, estilo="I", color=TINTA3, alto=4.2)
        pdf.ln(1)
        _markdown(pdf, d["texto"])
    return bytes(pdf.output())
