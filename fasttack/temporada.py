"""Temporada: la evolución de un barco a lo largo de todos sus campeonatos y sesiones, y la
comparación de reglajes por franja de viento. Solo usa los análisis ya guardados (las pruebas sin
analizar salen en «pendientes» y la web las pide una a una)."""
from __future__ import annotations

import json
import statistics

from .ingesta import campeonato as camp_mod
from .ingesta.almacen import Almacen
from . import servicio

FRANJAS_KN = ((0, 8, "< 8 kn"), (8, 12, "8–12 kn"), (12, 16, "12–16 kn"), (16, 99, "> 16 kn"))


def _med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def _franja(kn):
    if kn is None:
        return "sin viento de referencia"
    return next(n for a, b, n in FRANJAS_KN if a <= kn < b)


def fila_de(an: dict, v: str) -> dict | None:
    """Indicadores del barco v en una prueba analizada (None si no la navegó)."""
    clas = an["clasificacion"]
    mia = next((c for c in clas if c["vela"] == v), None)
    r = an["rendimiento"].get(v)
    if mia is None or r is None:
        return None
    top5 = [c["vela"] for c in clas if c["vela"] != v][:5]
    rt = [an["rendimiento"][x] for x in top5 if x in an["rendimiento"]]
    frente = lambda k: (round(r[k] - _med([x.get(k) for x in rt]), 2)
                        if r.get(k) is not None and len([x for x in rt if x.get(k) is not None]) >= 3 else None)
    viradas = [m["detalle"]["perdida_s"] for t in an["tramos"] if t["tipo"] == "ceñida"
               for m in t["maniobras"].get(v, []) if m.get("detalle")]
    lay = [(t["barcos"].get(v) or {}).get("layline") or {} for t in an["tramos"]]
    lay = [x.get("estado") for x in lay if x.get("estado")]
    reg = [(t["barcos"].get(v) or {}).get("regularidad_pct") for t in an["tramos"]]
    presion = _med([f.get("sog") for t in an["tramos"] if t["tipo"] == "ceñida" for f in t["barcos"].values()
                    if f.get("calidad") in ("alta", "media")])
    d = r.get("desglose") or {}
    return {
        "puesto": mia["posicion"], "barcos": len(clas), "puesto_relativo": round(mia["posicion"] / len(clas), 3),
        "vmg_ceñida_frente_top5": frente("vmg_ceñida"), "vmg_popa_frente_top5": frente("vmg_popa"),
        "perdida_virada_s": round(_med(viradas), 1) if viradas else None,
        "laylines_sobrepasadas": sum(1 for x in lay if x == "SOBREPASADA"), "laylines": len(lay),
        "regularidad_pct": round(_med(reg), 1) if _med(reg) is not None else None,
        "sog_flota_ceñida": round(presion, 2) if presion else None,
        "desglose": {k: d.get(k) for k in ("total_s", "salida_s", "velocidad_s", "maniobras_s", "tactica_s")} if d else None,
    }


def temporada(alm: Almacen, barco: str) -> dict:
    from .ingesta.normalizar import vela
    v = vela(barco)
    filas, pendientes = [], []
    for c in alm.sql("select id, coalesce(nullif(alias, ''), nombre) as nombre from campeonato where estado='listo'"):
        camp = camp_mod.leer(alm, c["id"])
        if camp is None or v not in {b["clave"] for b in camp["barcos"]}:
            continue
        tz = camp.get("tz_offset_ms") or 0
        for p in camp["pruebas"]:
            if p["numero"] is None or not p["llegadas"]:
                continue
            ruta = servicio._ruta_analisis(alm, camp, p)
            if not ruta.exists():
                if v in p["llegadas"]:
                    pendientes.append({"campeonato": c["id"], "clave": p["clave"]})
                continue
            an = json.loads(ruta.read_text())
            if an.get("recorrido_dudoso") or "error" in an:
                continue
            f = fila_de(an, v)
            if f is None:
                continue
            filas.append({"campeonato": c["id"], "nombre": c["nombre"], "clase": camp.get("clase"),
                          "clave": p["clave"], "numero": p["numero"], "senal": p["senal"],
                          "dia": servicio.dia_de(p["senal"], tz), "viento_kn": p.get("viento_kn"),
                          "franja": _franja(p.get("viento_kn")), "reglaje": p.get("reglaje") or {}, **f})
    filas.sort(key=lambda x: x["senal"])
    return {"barco": v, "filas": filas, "pendientes": pendientes, "reglajes": comparar_reglajes(filas)}


def comparar_reglajes(filas: list[dict]) -> list[dict]:
    """Para cada ajuste que ha tenido al menos dos valores: VMG frente al top 5 con cada valor, por
    franja de viento (media de las pruebas; con pocas pruebas es orientativo)."""
    claves = sorted({k for f in filas for k in f["reglaje"]})
    out = []
    for k in claves:
        con = [f for f in filas if k in f["reglaje"]]
        if len({f["reglaje"][k] for f in con}) < 2:
            continue
        grupos = {}
        for f in con:
            grupos.setdefault((f["franja"], f["reglaje"][k]), []).append(f)
        for (franja, valor), fs in sorted(grupos.items()):
            media = lambda key: (round(statistics.mean([x[key] for x in fs if x[key] is not None]), 2)
                                 if any(x[key] is not None for x in fs) else None)
            out.append({"ajuste": k, "valor": valor, "franja": franja, "pruebas": len(fs),
                        "vmg_ceñida_frente_top5": media("vmg_ceñida_frente_top5"),
                        "vmg_popa_frente_top5": media("vmg_popa_frente_top5"),
                        "puesto_relativo": media("puesto_relativo")})
    return out
