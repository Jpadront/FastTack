#!/usr/bin/env python3
"""Fase 1 — reconstruir desde la telemetría las regatas que /api/regatta pierde.

En el Mundial de J/70 2026, los días 9 y 11 de septiembre se navegaron 2 pruebas cada día, pero
/api/regatta solo guarda la salida de la primera (regatas 4 y 7, sin llegadas) y ni siquiera
contiene la segunda. La telemetría sí tiene las cuatro.

Método (validado con la regata 2, que sí tiene llegadas oficiales):
- Salida: cruces de la línea pin→comité (posición de las balizas en cada instante). La ventana
  de 60 s con más barcos distintos cruzando empieza ~20 s antes de la señal: señal = minuto
  siguiente al primer cruce de esa ráfaga.
- Llegada: cruces de la línea de llegada agrupados en «olas» (separadas > 8 min); la última ola
  es la llegada y, por barco, cuenta el primer cruce en la dirección mayoritaria de esa ola.

Uso:
    python fase1_reconstruir.py             # descarga (si falta) y analiza 9 y 11-09
    python fase1_reconstruir.py --analizar  # sin red
Escribe data/sample/reconstruccion_j70.md.
"""
from __future__ import annotations

import argparse
import bisect
import collections
import json
import math
from datetime import datetime, timezone

import fase1_muestras as f

EVENTO, DIVISION = "oRkxbTpSZPbSkrmKrbj2", "Open"
PIN, COMITE = 19883, 25687             # start_line[0], start_line[1]
LLEGADA = (25687, 25639)               # finish_line[0], finish_line[1]
# día: [(ventana de búsqueda de la salida, ventana de búsqueda de la llegada), ...] en UTC
DIAS = {
    "2026-09-09": [(("12:40", "13:10"), ("13:30", "14:45")), (("15:50", "16:40"), ("17:20", "18:30"))],
    "2026-09-11": [(("11:50", "12:20"), ("12:55", "13:40")), (("13:40", "14:10"), ("14:50", "16:10"))],
}
VALIDACION = 2  # raceNumber de /api/regatta con llegadas oficiales, ya descargado por fase1_muestras


def ms(dia, hm):
    return int(datetime.fromisoformat(f"{dia}T{hm}:00+00:00").timestamp() * 1000)


def hora(t):
    return datetime.fromtimestamp(t / 1000, timezone.utc).strftime("%H:%M:%S")


def cargar(path):
    d = json.loads(path.read_text())
    ix = {k: i for i, k in enumerate(d["Fields"])}
    barcos, balizas = collections.defaultdict(list), collections.defaultdict(list)
    for r in d["Rows"]:
        p = (r[ix["ts"]], r[ix["latitude"]], r[ix["longitude"]])
        if r[ix["role"]] == "mark":
            balizas[r[ix["sn"]]].append(p)
        else:
            barcos[r[ix["sail_number"]].replace(" ", "").upper()].append(p)
    return d["_meta"], barcos, balizas


class Pista:
    """Posición de un dispositivo en un instante (última muestra de hace ≤ 15 min)."""

    def __init__(self, pts):
        self.pts, self.ts = pts, [p[0] for p in pts]

    def en(self, t, max_edad=15 * 60_000):
        i = bisect.bisect_right(self.ts, t) - 1
        return self.pts[i][1:] if i >= 0 and t - self.ts[i] <= max_edad else None


def lado(a, b, p):
    k = math.cos(math.radians(a[0]))
    return (b[1] - a[1]) * k * (p[0] - a[0]) - (b[0] - a[0]) * (p[1] - a[1]) * k


def cruces(barcos, A: Pista, B: Pista, t0, t1):
    """(ts, vela, dirección) de cada cruce del segmento A–B (posiciones de A y B en ese instante)."""
    out = []
    for vela, tr in barcos.items():
        tr = [x for x in tr if t0 <= x[0] <= t1]
        for (ta, *p), (tb, *q) in zip(tr, tr[1:]):
            a, b = A.en(ta), B.en(ta)
            if tb - ta > 10_000 or not a or not b:
                continue
            s1, s2 = lado(a, b, p), lado(a, b, q)
            if s1 * s2 < 0 and lado(p, q, a) * lado(p, q, b) < 0:
                out.append((ta, vela, s1 < 0 < s2))
    return sorted(out)


def salida(barcos, balizas, t0, t1):
    c = cruces(barcos, Pista(balizas[PIN]), Pista(balizas[COMITE]), t0, t1)
    n, t = max(((len({v for tt, v, _ in c[i:] if tt <= t + 60_000}), t) for i, (t, _, _) in enumerate(c)),
               default=(0, None))
    return n, (t // 60_000 + 1) * 60_000 if t else None


def llegadas(barcos, balizas, t0, t1, hueco=8 * 60_000):
    c = cruces(barcos, Pista(balizas[LLEGADA[0]]), Pista(balizas[LLEGADA[1]]), t0, t1)
    if not c:
        return {}
    olas = [[c[0]]]
    for x in c[1:]:
        (olas[-1].append(x) if x[0] - olas[-1][-1][0] <= hueco else olas.append([x]))
    ultima = olas[-1]
    direccion = collections.Counter(d for _, _, d in ultima[:30]).most_common(1)[0][0]
    fin = {}
    for t, v, d in ultima:
        if d == direccion and v not in fin:
            fin[v] = t
    return fin


def validar():
    meta, barcos, balizas = cargar(f.OUT / "j70_telemetry_race.json")
    doc = json.loads((f.OUT / "j70_regatta.json").read_text())["revisions"][-1]["doc"]
    race = next(r for r in doc["divisions"][0]["races"] if r["raceNumber"] == VALIDACION)
    oficial = {x["sailNumber"].replace(" ", "").upper(): f.ms_rfc3339(x["finishingTime"]) for x in race["finishes"]}
    _, senal = salida(barcos, balizas, meta["after"], meta["senal"] + 15 * 60_000)
    fin = llegadas(barcos, balizas, meta["senal"] + 30 * 60_000, meta["before"])
    err = sorted(abs(fin[v] - oficial[v]) / 1000 for v in fin if v in oficial)
    orden_of = sorted(oficial, key=oficial.get)
    orden_det = sorted(fin, key=fin.get)
    comunes = [v for v in orden_of if v in fin]
    iguales = sum(a == b for a, b in zip(comunes, [v for v in orden_det if v in oficial]))
    return [f"## Validación con la regata {VALIDACION} de /api/regatta\n",
            f"- Señal oficial {hora(meta['senal'])} UTC; detectada {hora(senal)} UTC.",
            f"- Llegadas oficiales {len(oficial)} ({hora(min(oficial.values()))}–{hora(max(oficial.values()))}); "
            f"detectadas {len(fin)} ({hora(min(fin.values()))}–{hora(max(fin.values()))}).",
            f"- Error por barco: mediana {err[len(err)//2]:.2f} s, p90 {f.pct(err, .9):.2f} s, máx {err[-1]:.2f} s.",
            f"- Puesto idéntico al oficial en {iguales}/{len(comunes)} barcos.\n"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--analizar", action="store_true")
    a = ap.parse_args()
    L = ["# Reconstrucción de regatas J/70 desde la telemetría\n"]
    L += validar()
    L.append("## Días 9 y 11 de septiembre\n")
    L.append("| Día | Prueba del día | En /api/regatta | Señal (UTC) | Ráfaga de salida | Llegadas detectadas | 1.ª llegada (UTC) | Última (UTC) |")
    L.append("|---|---|---|---|---|---|---|---|")
    api = {("2026-09-09", 0): "regata 4 (sin llegadas)", ("2026-09-11", 0): "regata 7 (sin llegadas)"}
    for dia, pruebas in DIAS.items():
        p = f.OUT / f"j70_dia_{dia}_telemetry_race.json"
        if not p.exists() and not a.analizar:
            f.descargar_telemetria(EVENTO, DIVISION, ms(dia, "10:00"), ms(dia, "18:30"), f"j70_dia_{dia}")
        _, barcos, balizas = cargar(p)
        for i, ((s0, s1), (l0, l1)) in enumerate(pruebas):
            n, senal = salida(barcos, balizas, ms(dia, s0), ms(dia, s1))
            fin = llegadas(barcos, balizas, ms(dia, l0), ms(dia, l1))
            ts = sorted(fin.values())
            L.append(f"| {dia} | {i+1} | {api.get((dia, i), '**no está**')} | {hora(senal)} | {n} barcos | "
                     f"{len(fin)} | {hora(ts[0]) if ts else '-'} | {hora(ts[-1]) if ts else '-'} |")
    out = f.OUT / "reconstruccion_j70.md"
    out.write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
