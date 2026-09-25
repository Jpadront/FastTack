#!/usr/bin/env python3
"""Prototipo: página de reproducción de una prueba del Mundial de J/70 con clasificación oficial.

Descarga (si falta) la telemetría de la prueba, toma señal, llegadas y OCS de /api/regatta y
escribe una página HTML autocontenida con los datos incrustados. Las balizas de barlovento no
transmitieron en ninguna prueba: se estiman con los rodeos de la flota.
La página lleva datos de Vakaros: es para uso privado del equipo.

    python prototipo/construir_visor.py SALIDA.html [raceNumber de /api/regatta, por defecto 6]
"""
from __future__ import annotations

import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fase1_muestras as f  # noqa: E402
import fase1_reconstruir as r  # noqa: E402

REGATA_API = 8  # 12-09, 1.ª prueba del día = prueba 9 oficial (mejor cobertura de ESP 1214)
PRUEBA_OFICIAL = {2: 1, 3: 2, 4: 3, 5: 5, 6: 6, 7: 7, 8: 9, 9: 10}  # ver docs/fuente_datos.md
PROPIO = "ESP1214"
PASO_FLOTA_MS = 4000
HORA_LOCAL = 1  # Cascais en septiembre: UTC+1
PLANTILLA = Path(__file__).with_name("visor.html")


def remuestrear(tr, t0, t1, paso):
    out, j = [], 0
    for t in range(t0, t1 + 1, paso):
        while j + 1 < len(tr) and tr[j + 1][0] <= t:
            j += 1
        if tr[j][0] <= t and t - tr[j][0] <= 15_000:
            out.append((t, tr[j]))
    return out


def balizas_barlovento(barcos, senal, fin, twd):
    """Rodeos de barlovento: máximos locales de avance contra el viento de cada barco,
    agrupados a < 120 m y < 15 min. Grupos con ≥ 15 barcos = baliza estimada."""
    k = math.cos(math.radians(38.66))
    ux, uy = math.sin(math.radians(twd)), math.cos(math.radians(twd))
    proj = lambda la, lo: ((lo + 9.38) * k * ux + (la - 38.66) * uy) * 111_320  # noqa: E731
    pts = []
    for v, tr in barcos.items():
        tr = [p for p in tr if senal <= p[0] <= fin]
        P = [proj(p[1], p[2]) for p in tr]
        for i, (t, la, lo) in enumerate(tr):
            vec = [P[j] for j in range(max(0, i - 150), min(len(tr), i + 150)) if abs(tr[j][0] - t) <= 240_000]
            if P[i] == max(vec) and P[i] - min(vec) > 300:
                pts.append((t, la, lo, v))
    grupos = []
    for p in sorted(pts):
        for g in grupos:
            if f.dist_m(g["la"], g["lo"], p[1], p[2]) < 120 and p[0] - g["t1"] < 15 * 60_000:
                g["p"].append(p); g["t1"] = p[0]
                g["la"] = statistics.median(x[1] for x in g["p"]); g["lo"] = statistics.median(x[2] for x in g["p"])
                break
        else:
            grupos.append({"p": [p], "t0": p[0], "t1": p[0], "la": p[1], "lo": p[2]})
    # Une grupos casi en el mismo sitio (< 60 m) que se solapan en el tiempo.
    unidos = []
    for g in sorted(grupos, key=lambda g: -len(g["p"])):
        for u in unidos:
            if f.dist_m(u["la"], u["lo"], g["la"], g["lo"]) < 60 and g["t0"] <= u["t1"] + 600_000 and u["t0"] <= g["t1"] + 600_000:
                u["p"] += g["p"]; u["t0"] = min(u["t0"], g["t0"]); u["t1"] = max(u["t1"], g["t1"])
                break
        else:
            unidos.append(dict(g))
    res = [{"lat": g["la"], "lon": g["lo"], "t0": g["t0"], "t1": g["t1"], "barcos": len({x[3] for x in g["p"]})}
           for g in unidos if len({x[3] for x in g["p"]}) >= 15]
    res.sort(key=lambda e: e["t0"])
    # Vuelta: rodeos que se solapan en el tiempo son de la misma vuelta (baliza y desmarque).
    vuelta, fin_vuelta, n = 0, -1, 0
    for e in res:
        if e["t0"] > fin_vuelta:
            vuelta, n = vuelta + 1, 0
        n += 1
        fin_vuelta = max(fin_vuelta, e["t1"])
        e["nombre"] = f"Barlovento v{vuelta}" + ("" if n == 1 else " (2.º punto)")
    return res


def main(salida, regata=REGATA_API):
    doc = json.loads((f.OUT / "j70_regatta.json").read_text())["revisions"][-1]["doc"]
    race = next(x for x in doc["divisions"][0]["races"] if x["raceNumber"] == regata)
    start = race["starts"][-1]
    senal = f.señal_ms(start)
    norm = lambda v: v.replace(" ", "").upper()  # noqa: E731
    oficiales = {norm(x["sailNumber"]): f.ms_rfc3339(x["finishingTime"]) for x in race["finishes"]}
    fin = max(oficiales.values()) + 3 * 60_000
    t0 = senal - 6 * 60_000
    path = f.OUT / (f"j70_r{regata}_telemetry_race.json" if regata != 2 else "j70_telemetry_race.json")
    if not path.exists():
        f.descargar_telemetria(r.EVENTO, r.DIVISION, t0, fin, f"j70_r{regata}")
    crudo = json.loads(path.read_text())
    ix = {k: i for i, k in enumerate(crudo["Fields"])}
    _, barcos, balizas = r.cargar(path)
    filas = [x for x in crudo["Rows"] if t0 <= x[0] <= fin]
    col = lambda x, k: x[ix[k]]  # noqa: E731
    twd = f.twd_primera_ceñida(filas, col, senal)
    ocs = ({norm(v) for v in start["ocsParticipants"]} - {norm(v) for v in start["exoneratedParticipants"]}
           - {norm(v) for v in start.get("clearedOcs") or []})
    llegadas = {v: t for v, t in oficiales.items() if v not in ocs}

    flota = {}
    for v, tr in barcos.items():
        m = remuestrear(tr, t0, fin, PASO_FLOTA_MS)
        if len(m) > 50:
            flota[v] = [[(t - t0) // 1000, round(p[1] * 1e5), round(p[2] * 1e5)] for t, p in m]
    propio = [[(x[0] - t0) / 1000, round(col(x, "latitude") * 1e5), round(col(x, "longitude") * 1e5),
               round(col(x, "sog"), 2), col(x, "heading"), col(x, "roll")]
              for x in filas if col(x, "role") == "competitor"
              and col(x, "sail_number").replace(" ", "").upper() == PROPIO]
    nombres = {}
    for p in doc["divisions"][0]["participants"]:
        nombres[p["sailNumber"].replace(" ", "").upper()] = [p["sailNumber"], p.get("boatName") or ""]
    marcas = []
    for sn, nombre, tipo in ((r.PIN, "Pin", "salida"), (r.COMITE, "Comité · salida y llegada", "comite"),
                             (r.LLEGADA[1], "Llegada", "llegada")):
        m = remuestrear(balizas[sn], t0, fin, 20_000)
        marcas.append({"nombre": nombre, "tipo": tipo,
                       "pos": [[(t - t0) // 1000, round(p[1] * 1e5), round(p[2] * 1e5)] for t, p in m]})
    estimadas = balizas_barlovento(barcos, senal, fin, twd)
    for e in estimadas:
        marcas.append({"nombre": e["nombre"], "tipo": "estimada", "barcos": e["barcos"],
                       "desde": (e["t0"] - t0) // 1000 - 600, "hasta": (e["t1"] - t0) // 1000 + 60,
                       "pos": [[0, round(e["lat"] * 1e5), round(e["lon"] * 1e5)]]})
    orden = sorted(llegadas, key=llegadas.get)
    datos = {
        "t0": t0, "senal": (senal - t0) // 1000, "fin": (fin - t0) // 1000, "horaLocal": HORA_LOCAL,
        "twd": round(twd), "propio": PROPIO, "flota": flota, "yo": propio, "marcas": marcas,
        "llegadas": [[v, (llegadas[v] - senal) / 1000] for v in orden],
        "ocs": sorted(ocs), "prueba": PRUEBA_OFICIAL.get(regata, regata),
        "fecha": datetime.fromtimestamp(senal / 1000, timezone.utc).strftime("%Y-%m-%d"),
        "nombres": {v: nombres.get(v, [v, ""]) for v in set(flota) | set(oficiales)},
    }
    html = PLANTILLA.read_text().replace("/*DATOS*/null", json.dumps(datos, separators=(",", ":")))
    Path(salida).write_text(html)
    print(f"{salida}: {len(html)/1e6:.1f} MB; {len(flota)} barcos; {len(orden)} llegadas; "
          f"{PROPIO} {orden.index(PROPIO)+1 if PROPIO in orden else '-'}; TWD {twd:.0f}; "
          f"barlovento estimadas {[(round(e['lat'],5), round(e['lon'],5), e['barcos']) for e in estimadas]}")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else REGATA_API)
