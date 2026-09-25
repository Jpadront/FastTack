"""Resumen del campeonato: general calculada y agregados de las pruebas analizadas.

Puro: recibe las pruebas del campeonato (con sus llegadas) y los análisis ya calculados; no descarga
ni calcula trazas. Todo lo que devuelve sale de números del motor; nada se inventa.

General calculada (puntuación baja, RRS apéndice A), sin penalizaciones ni decisiones del jurado:
- puesto en la prueba = orden de llegada entre los que terminan, quitando los OCS del comité cuando
  su lista es fiable (en las pruebas reconstruidas no lo es y no se aplican);
- OCS y sin llegada (DNF o DNC, no se distinguen) = inscritos + 1 (inscritos: barcos con alguna llegada);
- descartes: las peores puntuaciones de cada barco;
- empates: A8.1 (puntuaciones no descartadas de mejor a peor) y A8.2 (última prueba hacia atrás).
"""
from __future__ import annotations

import statistics

from . import escora as esc_mod

METRICAS_REND = ("vmg_ceñida", "vmg_popa", "sog_ceñida", "sog_popa", "twa_ceñida", "twa_popa",
                 "escora_ceñida", "escora_popa", "cabeceo_ceñida", "cabeceo_popa",
                 "perdida_virada_m", "perdida_trasluchada_m")
COBERTURA_RANGO = 0.5    # para ordenar la flota en una métrica, el barco necesita esta cobertura
PUERTA_MIN_M = 5.0       # por debajo de esta ventaja la puerta es indiferente y no cuenta
TRAMOS_VIENTO = (("< 10 kn", lambda w: w < 10), ("10–15 kn", lambda w: 10 <= w <= 15), ("> 15 kn", lambda w: w > 15))


def descartes_por_defecto(n_pruebas: int) -> int:
    """Un descarte a partir de 4 pruebas. Es solo el valor inicial: lo fijan las instrucciones de regata."""
    return 1 if n_pruebas >= 4 else 0


def puntuar_prueba(prueba: dict, inscritos: list[str]) -> dict[str, tuple[int, str | None]]:
    """{vela: (puntos, código)} de una prueba. Código: None, 'OCS' o 'DNF'."""
    penal = len(inscritos) + 1
    ocs = set(prueba.get("ocs") or []) if prueba.get("ocs_fiable") else set()
    orden = [v for v, _ in sorted(prueba["llegadas"].items(), key=lambda x: x[1]) if v not in ocs]
    puesto = {v: k + 1 for k, v in enumerate(orden)}
    res = {}
    for v in inscritos:
        if v in puesto:
            res[v] = (puesto[v], None)
        elif v in ocs:
            res[v] = (penal, "OCS")
        else:
            res[v] = (penal, "DNF")
    return res


def general(pruebas: list[dict], inscritos: list[str], descartes: int) -> list[dict]:
    """Clasificación general calculada. `pruebas` en orden de numeración, solo las que cuentan."""
    por_prueba = [puntuar_prueba(p, inscritos) for p in pruebas]
    filas = []
    for v in inscritos:
        pts = [pp[v] for pp in por_prueba]
        # descartes: las peores; con empate de puntos, la más antigua
        orden_peores = sorted(range(len(pts)), key=lambda k: (-pts[k][0], k))
        desc = set(orden_peores[:min(descartes, max(len(pts) - 1, 0))])
        total = sum(p for p, _ in pts)
        neto = sum(p for k, (p, _) in enumerate(pts) if k not in desc)
        filas.append({"vela": v, "total": total, "neto": neto,
                      "puntos": [{"pts": p, "cod": c, "desc": k in desc} for k, (p, c) in enumerate(pts)],
                      "_a81": sorted(p for k, (p, _) in enumerate(pts) if k not in desc),
                      "_a82": [p for p, _ in reversed(pts)]})
    filas.sort(key=lambda f: (f["neto"], f["_a81"], f["_a82"], f["vela"]))
    for k, f in enumerate(filas):
        f["puesto"] = k + 1
        del f["_a81"], f["_a82"]
    return filas


def _media(vals, pesos=None):
    """Media (ponderada si hay pesos) de los valores no nulos; None si no hay ninguno."""
    pesos = pesos if pesos is not None else [1.0] * len(vals)
    pares = [(v, w) for v, w in zip(vals, pesos) if v is not None and w]
    s = sum(w for _, w in pares)
    return round(sum(v * w for v, w in pares) / s, 3) if s else None


def _rangos(valores: dict[str, float], mayor_mejor: bool) -> dict[str, int]:
    orden = sorted(valores, key=lambda v: valores[v], reverse=mayor_mejor)
    return {v: k + 1 for k, v in enumerate(orden)}


def por_prueba(an: dict, puntos: dict[str, tuple[int, str | None]]) -> dict:
    """Métricas de cada barco en una prueba analizada, más medianas y rangos de la flota."""
    barcos = {}
    s = an.get("salida") or {"barcos": {}}
    puertas = [c for c in an["controles"] if c.get("puerta") and c["puerta"]["ventaja_m"] >= PUERTA_MIN_M]
    for v, (pts, cod) in puntos.items():
        r = an["rendimiento"].get(v)
        sb = s["barcos"].get(v) or {}
        lay = [t["barcos"][v]["layline"] for t in an["tramos"] if v in t["barcos"] and t["barcos"][v].get("layline")]
        ok = sum(1 for x in lay if x["estado"] == "OK")
        sob = [x["metros"] for x in lay if x["estado"] == "SOBREPASADA"]
        pz = [an["pasos"].get(v, {}).get(c["id"], {}).get("puerta") for c in puertas]
        pz_tot = [(p, c["puerta"]["favorecida"]) for p, c in zip(pz, puertas) if p]
        barcos[v] = {
            "pts": pts, "cod": cod,
            "rend": {m: r.get(m) for m in METRICAS_REND} if r else None,
            "cobertura": r.get("cobertura") if r else None,
            "salida": {k: sb.get(k) for k in ("margen_m", "pos_60", "posicion_linea_pct", "sobre_linea_gps", "en_salida")} if sb else None,
            "laylines": {"ok": ok, "sobrepasadas": len(sob), "metros": _media(sob)},
            "puertas": {"buenas": sum(1 for p, f in pz_tot if p == f), "total": len(pz_tot)},
        }
    # flota: mediana por métrica y rango de cada barco (solo barcos con cobertura suficiente)
    flota, rangos = {}, {}
    for m in METRICAS_REND:
        vals = {v: b["rend"][m] for v, b in barcos.items()
                if b["rend"] and b["rend"][m] is not None and (b["cobertura"] or 0) >= COBERTURA_RANGO}
        flota[m] = round(statistics.median(vals.values()), 3) if vals else None
        if m.startswith("vmg") or m.startswith("perdida"):
            rangos[m] = (_rangos(vals, m.startswith("vmg")), len(vals))
    for v, b in barcos.items():
        b["rango"] = {m: {"pos": r.get(v), "de": n} for m, (r, n) in rangos.items() if v in r}
    return {"barcos": barcos, "flota": flota}


def totales(filas: list[dict | None], vientos: list[float | None]) -> dict:
    """Agrega un barco sobre las pruebas analizadas (None = prueba sin analizar)."""
    hechas = [(f, w) for f, w in zip(filas, vientos) if f is not None]
    rend = {}
    for m in METRICAS_REND:
        rend[m] = _media([f["rend"][m] if f["rend"] else None for f, _ in hechas],
                         [f["cobertura"] or 0 for f, _ in hechas])
    sal = [f["salida"] for f, _ in hechas if f["salida"] and f["salida"].get("en_salida")]
    con60 = [x["pos_60"] for x in sal if x.get("pos_60") is not None]
    sob = [(f["laylines"]["sobrepasadas"], f["laylines"]["metros"]) for f, _ in hechas]
    n_sob = sum(n for n, _ in sob)
    viento = []
    for nombre, dentro in TRAMOS_VIENTO:
        grupo = [(f, w) for f, w in hechas if w is not None and dentro(w)]
        viento.append({"tramo": nombre, "pruebas": len(grupo),
                       "puesto_medio": _media([f["pts"] for f, _ in grupo]),
                       "vmg_ceñida": _media([f["rend"]["vmg_ceñida"] if f["rend"] else None for f, _ in grupo]),
                       "vmg_popa": _media([f["rend"]["vmg_popa"] if f["rend"] else None for f, _ in grupo])})
    return {
        "analizadas": len(hechas),
        "rend": rend,
        "salida": {"pruebas": len(sal), "margen_m": _media([x.get("margen_m") for x in sal]),
                   "posicion_linea_pct": _media([x.get("posicion_linea_pct") for x in sal]),
                   "top10_60": sum(1 for p in con60 if p <= 10), "con_60": len(con60),
                   "ocs": sum(1 for f, _ in hechas if f["cod"] == "OCS"),
                   "sobre_linea_gps": sum(1 for x in sal if x.get("sobre_linea_gps"))},
        "laylines": {"ok": sum(f["laylines"]["ok"] for f, _ in hechas), "sobrepasadas": n_sob,
                     "metros": round(sum(n * m for n, m in sob if m is not None) / n_sob, 1) if n_sob else None},
        "puertas": {"buenas": sum(f["puertas"]["buenas"] for f, _ in hechas),
                    "total": sum(f["puertas"]["total"] for f, _ in hechas)},
        "viento": viento,
    }


def escora_campeonato(pruebas: list[dict], validos: dict[str, dict], inscritos: list[str]) -> dict | None:
    """Escora óptima juntando todas las ceñidas del campeonato y, si hay viento de referencia, por
    intensidad. Por barco: en cuántas ceñidas su escora mediana cayó dentro del rango."""
    grupos, por_viento = [], {}
    for p in pruebas:
        an = validos.get(p["clave"])
        if not an:
            continue
        for t in an["tramos"]:
            o = t.get("escora_optima")
            if t.get("tipo") == "ceñida" and o and all("error_pct" in f for f in o["franjas"]):
                grupos.append(o["franjas"])
                w = p.get("viento_kn")
                if w is not None:
                    nombre = next(n for n, dentro in TRAMOS_VIENTO if dentro(w))
                    por_viento.setdefault(nombre, []).append(o["franjas"])
    todas = esc_mod.combinar(grupos) if len(grupos) >= 2 else None
    if not todas:
        return None
    lo, hi = todas["rango"]
    en_rango = {}
    for v in inscritos:
        esc = [t["barcos"][v]["escora"] for an in validos.values() for t in an["tramos"]
               if t.get("tipo") == "ceñida" and v in t["barcos"] and t["barcos"][v].get("escora") is not None]
        if esc:
            en_rango[v] = {"ceñidas": len(esc), "en_rango": sum(1 for e in esc if lo <= e < hi),
                           "escora_mediana": round(float(statistics.median(esc)), 1)}
    return {"todas": todas,
            "por_viento": [{"tramo": n, **r} for n, _ in TRAMOS_VIENTO
                           if n in por_viento and len(por_viento[n]) >= 2 and (r := esc_mod.combinar(por_viento[n]))],
            "barcos": en_rango}


def resumen(pruebas: list[dict], inscritos: list[str], analisis: dict[str, dict], descartes: int | None) -> dict:
    """pruebas: las que cuentan, en orden de numeración; analisis: {clave: análisis} de las ya calculadas."""
    d = descartes_por_defecto(len(pruebas)) if descartes is None else descartes
    gen = general(pruebas, inscritos, d)
    pts = [puntuar_prueba(p, inscritos) for p in pruebas]
    # Una prueba con el recorrido dudoso cuenta en la general, pero no en las métricas
    validos = {c: a for c, a in analisis.items() if not a.get("recorrido_dudoso")}
    pp = [por_prueba(validos[p["clave"]], pts[k]) if p["clave"] in validos else None for k, p in enumerate(pruebas)]
    vientos = [p.get("viento_kn") for p in pruebas]
    barcos = {}
    for v in inscritos:
        filas = [x["barcos"][v] if x else None for x in pp]
        barcos[v] = {"por_prueba": filas, "totales": totales(filas, vientos)}
    return {
        "descartes": d, "descartes_defecto": descartes_por_defecto(len(pruebas)), "inscritos": len(inscritos),
        "pruebas": [{"clave": p["clave"], "numero": p["numero"], "estado": p["estado"], "viento_kn": p.get("viento_kn"),
                     "ocs_aplicados": bool(p.get("ocs_fiable") and p.get("ocs")), "analizada": p["clave"] in analisis,
                     "recorrido_dudoso": bool(analisis.get(p["clave"], {}).get("recorrido_dudoso")),
                     "corriente": {k: (analisis[p["clave"]].get("corriente") or {}).get(k) for k in ("velocidad_kn", "hacia_grados", "confianza")}
                     if (analisis.get(p["clave"]) or {}).get("corriente") else None,
                     "flota": x["flota"] if x else None} for p, x in zip(pruebas, pp)],
        "general": gen,
        "barcos": barcos,
        "escora": escora_campeonato(pruebas, validos, inscritos),
        "pendientes": [p["clave"] for p in pruebas if p["clave"] not in analisis],
    }
