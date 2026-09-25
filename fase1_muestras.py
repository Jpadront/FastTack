#!/usr/bin/env python3
"""Fase 1 — comprobar acceso, descargar muestras a data/sample/ y medir la telemetría.

Uso:
    python fase1_muestras.py                 # J/70 (regata 2) + ILCA 7 (Gold, regata 1)
    python fase1_muestras.py --solo-acceso   # solo comprueba conectividad
    python fase1_muestras.py --analizar      # re-analiza lo ya descargado, sin red

Genera data/sample/*.json y data/sample/informe_fase1.md con las respuestas a los ⚠️.
Solo usa la biblioteca estándar. Peticiones secuenciales con pausa y User-Agent identificable.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import math
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PLAYER = "https://player.vakaros.com"
TELE = "https://teleapi.regatta.app"
UA = "regatta-analysis/0.1 (uso interno del equipo; contacto: jpadrontorrent@gmail.com)"
PAUSA_S = 1.0
LIMIT = 100_000
OUT = Path("data/sample")

EVENTOS = [
    # (etiqueta, eventId, división, raceNumber de /api/regatta). La J/70 regata 1 se anuló en la
    # salida (50 OCS, sin llegadas), así que se muestrea la 2.
    ("j70", "oRkxbTpSZPbSkrmKrbj2", "Open", 2),
    ("ilca7", "5JsqWPmBU6P7G5rk15ic", "Gold", 1),
]
MARGEN_ANTES_MS = 10 * 60_000   # antes de la señal
MARGEN_DESPUES_MS = 5 * 60_000  # tras la última llegada


# ----------------------------------------------------------------------------- red
def get(url: str, params: dict | None = None) -> tuple[bytes, dict]:
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read()
        info = {"url": url, "status": r.status, "bytes_wire": len(raw),
                "encoding": r.headers.get("Content-Encoding"), "secs": round(time.time() - t0, 2)}
    if info["encoding"] == "gzip":
        raw = gzip.decompress(raw)
    info["bytes"] = len(raw)
    time.sleep(PAUSA_S)
    return raw, info


def get_json(url, params=None):
    raw, info = get(url, params)
    return json.loads(raw), info


def guardar(nombre: str, obj) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / nombre
    p.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
    return p


def comprobar_acceso() -> bool:
    ok = True
    for url in (f"{PLAYER}/api/regatta?event={EVENTOS[0][1]}", f"{TELE}/openapi.json"):
        try:
            _, info = get(url)
            print(f"OK   {info['status']} {info['bytes']:>9} B  {info['secs']}s  {url}")
        except Exception as e:  # noqa: BLE001
            ok = False
            print(f"FALLO {url}: {e}")
    return ok


# ----------------------------------------------------------------------- descarga
def señal_ms(start) -> int:
    """Hora de la señal: startTime (epoch ms) truncado al minuto (el registro va ~1 s tarde)."""
    return start["startTime"] // 60_000 * 60_000


def ms_rfc3339(t: str) -> int:
    from datetime import datetime
    return int(datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp() * 1000)


def ventana_regata(reg, division: str, race: int):
    """Ventana [señal − 10 min, última llegada + 5 min] a partir de /api/regatta.
    racing-summary no sirve: su numeración y sus 'begin'/'start' no coinciden con la señal."""
    doc = reg["revisions"][-1]["doc"]
    div = next(d for d in doc["divisions"] if d["name"] == division)
    r = next(x for x in div["races"] if x["raceNumber"] == race)
    senal = señal_ms(r["starts"][-1])
    fin = max([ms_rfc3339(f["finishingTime"]) for f in r["finishes"]] or [senal + 3600_000])
    return senal, fin, senal - MARGEN_ANTES_MS, min(fin + MARGEN_DESPUES_MS, senal + 3 * 3600_000)


def descargar_telemetria(event_id, division, begin, end, etiqueta, extra_meta=None):
    """Pagina /telemetry/event por 'after'. Deduplica por (ts, sn)."""
    filas, fields, vistos, after, pag, bytes_tot = [], None, set(), begin, 0, 0
    while True:
        data, info = get_json(f"{TELE}/telemetry/event/{event_id}",
                              {"division": division, "after": after, "before": end, "limit": LIMIT})
        pag += 1
        bytes_tot += info["bytes"]
        fields = fields or data["Fields"]
        rows = data.get("Rows") or []
        i_ts, i_sn = fields.index("ts"), fields.index("sn")
        nuevos = 0
        for r in rows:
            k = (r[i_ts], r[i_sn])
            if k not in vistos:
                vistos.add(k)
                filas.append(r)
                nuevos += 1
        print(f"  pág {pag}: {len(rows)} filas ({nuevos} nuevas), {info['bytes']/1e6:.1f} MB "
              f"({info['bytes_wire']/1e6:.1f} MB en red, {info['encoding']}), {info['secs']}s")
        if len(rows) < LIMIT or nuevos == 0:
            break
        after = max(r[i_ts] for r in rows)
    guardar(f"{etiqueta}_telemetry_race.json", {"Fields": fields, "Rows": filas,
                                                 "_meta": {"paginas": pag, "bytes": bytes_tot,
                                                           "after": begin, "before": end,
                                                           **(extra_meta or {})}})
    return fields, filas


def descargar(etiqueta, event_id, division, race):
    print(f"\n== {etiqueta} ({event_id}, {division}, regata {race})")
    reg, _ = get_json(f"{PLAYER}/api/regatta", {"event": event_id})
    guardar(f"{etiqueta}_regatta.json", reg)
    for nombre, ruta, params in [
        ("racing_summary", f"/telemetry/racing-summary/{event_id}", None),
        ("event_times", f"/telemetry/event-times/{event_id}", {"division": division}),
        ("courses", f"/courses/{event_id}", {"division": division}),
    ]:
        d, _ = get_json(TELE + ruta, params)
        guardar(f"{etiqueta}_{nombre}.json", d)
    try:
        d, _ = get_json(f"{TELE}/division/short-id/{event_id}/{urllib.parse.quote(division, safe='')}")
        guardar(f"{etiqueta}_short_id.json", d)
    except urllib.error.HTTPError as e:
        print(f"  short-id: HTTP {e.code}")

    senal, fin, begin, end = ventana_regata(reg, division, race)
    print(f"  ventana telemetría: {begin} → {end} ({(end-begin)/60000:.0f} min; "
          f"señal {senal}, última llegada {fin})")
    descargar_telemetria(event_id, division, begin, end, etiqueta,
                         {"race": race, "senal": senal, "ultima_llegada": fin})


# ------------------------------------------------------------------------ análisis
def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else None


def analizar(etiqueta) -> str:
    p = OUT / f"{etiqueta}_telemetry_race.json"
    if not p.exists():
        return f"## {etiqueta}\n\n(sin telemetría descargada)\n"
    d = json.loads(p.read_text())
    F, rows = d["Fields"], d["Rows"]
    ix = {f: i for i, f in enumerate(F)}
    col = lambda r, f: r[ix[f]]  # noqa: E731
    L = [f"## {etiqueta}\n", f"- Filas: {len(rows):,}; páginas: {d['_meta']['paginas']}; "
         f"tamaño JSON: {d['_meta']['bytes']/1e6:.1f} MB "
         f"(~{d['_meta']['bytes']/max(1,len(rows)):.0f} B/fila)"]

    por_sn = collections.defaultdict(list)
    for r in rows:
        por_sn[col(r, "sn")].append(r)
    roles = collections.Counter((col(v[0], "role")) for v in por_sn.values())
    L.append(f"- Dispositivos: {len(por_sn)} ({dict(roles)})")

    # Frecuencia de muestreo
    L.append("\n### Frecuencia de muestreo (Δt entre muestras consecutivas por dispositivo)\n")
    for rol in ("competitor", "mark"):
        dts, medianas = [], []
        for sn, rs in por_sn.items():
            if col(rs[0], "role") != rol:
                continue
            ts = sorted(col(r, "ts") for r in rs)
            dd = [b - a for a, b in zip(ts, ts[1:]) if b > a]
            if dd:
                dts += dd
                medianas.append(statistics.median(dd))
        if dts:
            c = collections.Counter(dts).most_common(6)
            L.append(f"- **{rol}**: mediana {statistics.median(dts):.0f} ms, p90 {pct(dts,.9)} ms, "
                     f"p99 {pct(dts,.99)} ms, máx {max(dts)} ms; Δt más frecuentes: {c}; "
                     f"mediana por dispositivo entre {min(medianas):.0f} y {max(medianas):.0f} ms; "
                     f"huecos >5 s: {sum(x > 5000 for x in dts)}")
    dup = len(rows) - len({(col(r, 'ts'), col(r, 'sn')) for r in rows})
    L.append(f"- (ts, sn) duplicados: {dup}; resolución: ts % 100 == 0 en "
             f"{100*sum(col(r,'ts') % 100 == 0 for r in rows)/max(1,len(rows)):.1f}% de filas")

    # Orden de filas (para paginar con 'after')
    tss = [col(r, "ts") for r in rows]
    L.append(f"- Filas ordenadas por ts: {all(a <= b for a, b in zip(tss, tss[1:]))}")

    # sail_number
    velas = {col(r, "sail_number") for r in rows if col(r, "role") == "competitor"}
    sin_esp = sorted(v for v in velas if v and " " not in v)
    L.append("\n### sail_number\n")
    L.append(f"- {len(velas)} velas distintas; sin espacio: {sin_esp[:15]}{'…' if len(sin_esp)>15 else ''}")
    sn_multi = {sn for sn, rs in por_sn.items() if len({col(r, 'sail_number') for r in rs}) > 1}
    L.append(f"- Dispositivos con >1 sail_number: {len(sn_multi)}")
    rpath = OUT / f"{etiqueta}_regatta.json"
    if rpath.exists():
        doc = json.loads(rpath.read_text())["revisions"][-1]["doc"]
        norm = lambda v: v.replace(" ", "").upper()  # noqa: E731
        inscritos = {norm(p["sailNumber"]) for dv in doc["divisions"] for p in dv.get("participants", [])}
        fuera = sorted(v for v in velas if norm(v) not in inscritos)
        L.append(f"- Velas de la telemetría que no están en participants (sin espacios): {fuera}")
    vmax = sorted(((max(col(r, "sog") for r in rs), col(rs[0], "sail_number")) for rs in por_sn.values()
                   if col(rs[0], "role") == "competitor"), reverse=True)[:3]
    L.append(f"- SOG máx. por dispositivo (top 3): {[(v, round(x, 1)) for x, v in vmax]}")
    marcas_vela = {col(r, "sail_number") for r in rows if col(r, "role") == "mark"}
    L.append(f"- sail_number en balizas: {marcas_vela}")

    # race_number / start_number / race_stage
    L.append("\n### race_number, start_number, race_stage\n")
    L.append(f"- (race_number, start_number): {collections.Counter((col(r,'race_number'), col(r,'start_number')) for r in rows).most_common(8)}")
    L.append(f"- race_stage: {collections.Counter(col(r,'race_stage') for r in rows).most_common()}")
    cambios = sum(1 for rs in por_sn.values()
                  if len({col(r, 'race_number') for r in rs}) > 1)
    L.append(f"- Dispositivos que cambian de race_number dentro de la ventana: {cambios}")

    # status
    L.append("\n### status\n")
    comp = [r for r in rows if col(r, "role") == "competitor"]  # las balizas siempre traen status 0
    st = collections.Counter(col(r, "status") for r in comp)
    L.append(f"- Valores: {st.most_common()}")
    L.append(f"- Coherencia posición/SOG por status: {calidad_status(por_sn, col)}")
    for s in st:
        sub = [col(r, "sog") for r in comp if col(r, "status") == s and col(r, "sog") is not None]
        stages = collections.Counter(col(r, "race_stage") for r in comp if col(r, "status") == s)
        L.append(f"  - status={s}: sog medio {statistics.fmean(sub) if sub else float('nan'):.2f} kn; "
                 f"race_stage {stages.most_common(3)}")

    # sog: cuantización
    sogs = [col(r, "sog") for r in rows if col(r, "sog")]
    ms = [s * 1852 / 3600 for s in sogs[:20000]]
    frac = sum(abs(m * 10 - round(m * 10)) < 1e-3 for m in ms) / max(1, len(ms))
    L.append(f"\n### sog\n\n- Múltiplos de 0,1 m/s: {100*frac:.1f}%; máx {max(sogs):.2f} kn")

    # roll: signo vs. amura (heading - COG no sirve; usamos giro del rumbo)
    L.append("\n### roll (signo)\n")
    L.append(f"- Rango roll: {min(col(r,'roll') for r in rows)}..{max(col(r,'roll') for r in rows)}; "
             f"pitch: {min(col(r,'pitch') for r in rows)}..{max(col(r,'pitch') for r in rows)}")
    meta = d["_meta"]
    senal, fin = meta.get("senal"), meta.get("ultima_llegada")
    if senal:
        L.append("- " + signo_roll(rows, col, senal))
        L.append("\n### heading frente a COG (en regata, SOG > 3 kn)\n")
        L.append("- " + heading_vs_cog(por_sn, col, senal, fin))

    # balizas
    L.append("\n### Balizas\n")
    L.append(analizar_balizas(etiqueta, por_sn, col, senal, fin))
    return "\n".join(L) + "\n"


def dist_m(la1, lo1, la2, lo2):
    k = math.pi / 180
    x = (lo2 - lo1) * k * math.cos((la1 + la2) / 2 * k)
    return 6371000 * math.hypot(x, (la2 - la1) * k)


def rumbo(la1, lo1, la2, lo2):
    k = math.pi / 180
    return math.degrees(math.atan2((lo2 - lo1) * k * math.cos((la1 + la2) / 2 * k), (la2 - la1) * k)) % 360


def dif_ang(a):
    return (a + 540) % 360 - 180


def twd_primera_ceñida(rows, col, senal):
    """Viento aprox. = bisectriz de los dos modos de rumbo de la flota entre señal+1 y señal+8 min
    (primera ceñida). Devuelve None si no hay dos modos claros."""
    hs = [col(r, "heading") for r in rows if col(r, "role") == "competitor"
          and senal + 60_000 <= col(r, "ts") <= senal + 8 * 60_000]
    if len(hs) < 500:
        return None
    hist = collections.Counter(int(h) // 5 * 5 for h in hs)
    suave = {b: sum(hist.get((b + k) % 360, 0) for k in (-5, 0, 5)) for b in range(0, 360, 5)}
    p1 = max(suave, key=suave.get)
    cand = {b: v for b, v in suave.items() if 50 <= abs(dif_ang(b - p1)) <= 120}
    if not cand:
        return None
    p2 = max(cand, key=cand.get)
    return (p1 + 2.5 + dif_ang(p2 - p1) / 2) % 360


def signo_roll(rows, col, senal):
    """En ceñida, amura estribor (viento por estribor) ⇒ el barco escora a babor, y al revés.
    Clasifica cada muestra de la primera ceñida por amura con el viento estimado y mira el signo."""
    twd = twd_primera_ceñida(rows, col, senal)
    if twd is None:
        return "No se pudo estimar el viento de la primera ceñida."
    est, bab = [], []
    for r in rows:
        if col(r, "role") != "competitor" or not senal + 60_000 <= col(r, "ts") <= senal + 8 * 60_000:
            continue
        x = dif_ang(col(r, "heading") - twd)
        (est if -70 < x < -15 else bab if 15 < x < 70 else []).append(col(r, "roll"))
    if not est or not bab:
        return f"Viento estimado {twd:.0f}°, pero faltan muestras de una de las amuras."
    return (f"Viento estimado (bisectriz de amuras, 1.ª ceñida) {twd:.0f}°. Amura estribor: n={len(est)}, "
            f"roll mediano {statistics.median(est):+.0f}°, {100*sum(x < 0 for x in est)/len(est):.0f}% < 0. "
            f"Amura babor: n={len(bab)}, roll mediano {statistics.median(bab):+.0f}°, "
            f"{100*sum(x > 0 for x in bab)/len(bab):.0f}% > 0. ⇒ roll>0 = escora a estribor si la "
            f"amura estribor da roll<0 y la babor roll>0.")


def heading_vs_cog(por_sn, col, t0, t1):
    """heading − COG (COG de posiciones consecutivas a ≤2 s, SOG > 3 kn)."""
    d = []
    for rs in por_sn.values():
        if col(rs[0], "role") != "competitor":
            continue
        rr = [r for r in rs if t0 <= col(r, "ts") <= t1]
        for a, b in zip(rr, rr[1:]):
            if 0 < col(b, "ts") - col(a, "ts") <= 2000 and col(a, "sog") > 3:
                p = (col(a, "latitude"), col(a, "longitude"), col(b, "latitude"), col(b, "longitude"))
                if dist_m(*p) >= 2:
                    d.append(dif_ang(col(a, "heading") - rumbo(*p)))
    if not d:
        return "sin datos"
    return (f"n={len(d)}; p5/p25/p50/p75/p95 = " + "/".join(f"{pct(d, q):+.1f}" for q in (.05, .25, .5, .75, .95))
            + f" °; |Δ|<5° en {100*sum(abs(x) < 5 for x in d)/len(d):.0f}%")


def calidad_status(por_sn, col):
    """|velocidad implícita por posiciones − SOG| por valor de status (muestras a ≤3 s, mismo status)."""
    err = collections.defaultdict(list)
    for rs in por_sn.values():
        if col(rs[0], "role") != "competitor":
            continue
        for a, b in zip(rs, rs[1:]):
            dt = (col(b, "ts") - col(a, "ts")) / 1000
            if 0 < dt <= 3 and col(a, "status") == col(b, "status"):
                v = dist_m(col(a, "latitude"), col(a, "longitude"), col(b, "latitude"), col(b, "longitude")) / dt
                err[col(a, "status")].append(abs(v * 3600 / 1852 - (col(a, "sog") + col(b, "sog")) / 2))
    return "; ".join(f"status={s} ({s:04b}): mediana {statistics.median(v):.2f} kn, p90 {pct(v, .9):.2f} kn (n={len(v)})"
                     for s, v in sorted(err.items()))


def funciones_balizas(etiqueta):
    """sn (telemetría) → funciones, combinando /courses y los courses de /api/regatta.
    En /api/regatta el sn va en hex de 10 dígitos ("0238004DAB"); en la telemetría es el
    entero de los 16 bits bajos (0x4DAB = 19883)."""
    funciones = collections.defaultdict(set)
    cpath = OUT / f"{etiqueta}_courses.json"
    if cpath.exists():
        for c in json.loads(cpath.read_text()).get("courses") or []:
            for m in c.get("marks", []):
                funciones[m["sn"]].add(f"{m['achievement_type']}[{m['mark_index']}]")
    rpath = OUT / f"{etiqueta}_regatta.json"
    if rpath.exists():
        doc = json.loads(rpath.read_text())["revisions"][-1]["doc"]
        for dv in doc.get("divisions", []):
            for c in dv.get("courses") or []:
                for ach in c.get("achievements", []):
                    for dr in ach.get("deviceRoles", []):
                        funciones[int(dr["sn"], 16) & 0xFFFF].add(f"{ach.get('title')}:{dr['role']}")
    return funciones


def analizar_balizas(etiqueta, por_sn, col, t0=None, t1=None):
    L = []
    funciones = funciones_balizas(etiqueta)
    for sn, rs in sorted(por_sn.items()):
        if col(rs[0], "role") != "mark":
            continue
        if t0:
            rs = [r for r in rs if t0 <= col(r, "ts") <= t1] or rs
        la = [col(r, "latitude") for r in rs]; lo = [col(r, "longitude") for r in rs]
        la0, lo0 = statistics.median(la), statistics.median(lo)
        desp = [dist_m(la0, lo0, a, b) for a, b in zip(la, lo)]
        otros = {f: sorted({col(r, f) for r in rs}) for f in ("sog", "heading", "roll", "pitch", "status")}
        otros = {f: v for f, v in otros.items() if v != [0]}
        L.append(f"- sn {sn} (0x{sn:04X}): {len(rs)} muestras en regata; funciones "
                 f"{sorted(funciones[sn]) if sn in funciones else '(no está en ningún recorrido)'}; "
                 f"desplazamiento respecto a la mediana p50/p95/máx = {pct(desp,.5):.0f}/{pct(desp,.95):.0f}/"
                 f"{max(desp):.0f} m; campos distintos de 0: {otros or 'ninguno'}")
    faltan = sorted(sn for sn in funciones if sn not in por_sn)
    if faltan:
        L.append(f"- En los recorridos pero sin telemetría en la ventana: {faltan}")
    return "\n".join(L) or "(sin balizas en la telemetría)"


def analizar_regatta(etiqueta) -> str:
    """Comprueba el orden de coordenadas y los formatos de fecha en /api/regatta."""
    p = OUT / f"{etiqueta}_regatta.json"
    if not p.exists():
        return ""
    reg = json.loads(p.read_text())
    doc = reg["revisions"][-1]["doc"]
    L = [f"### /api/regatta ({etiqueta})\n", f"- Revisiones: {len(reg['revisions'])}; "
         f"divisiones: {[d.get('name') for d in doc.get('divisions', [])]}"]
    ejemplos = collections.defaultdict(list)

    def walk(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, f"{path}.{k}")
        elif isinstance(o, list):
            if len(o) == 2 and all(isinstance(x, (int, float)) for x in o):
                ejemplos[path].append(o)
            else:
                for v in o:
                    walk(v, path + "[]")

    walk(doc)
    for path, xs in ejemplos.items():
        # Solo pares que parecen coordenadas; en Lisboa/Cascais lat≈38, lon≈-9 → |lat|>|lon|
        coords = [x for x in xs if all(abs(v) <= 180 for v in x) and any(abs(v) > 1 for v in x)]
        if not coords:
            continue
        lat_primero = sum(abs(x[0]) > abs(x[1]) for x in coords)
        L.append(f"- `{path}`: ej. {coords[0]}; primer valor = lat en {lat_primero}/{len(coords)} "
                 f"(supone |lat|>|lon| en la zona)")
    # Formatos de fecha
    fmts = collections.Counter()

    def fechas(o, k=""):
        if isinstance(o, dict):
            if set(o) >= {"seconds", "nanoseconds"}:
                fmts[(k, "{seconds,nanoseconds}")] += 1
                return
            for kk, v in o.items():
                fechas(v, kk)
        elif isinstance(o, list):
            for v in o:
                fechas(v, k)
        elif "time" in k.lower() or "date" in k.lower():
            if isinstance(o, (int, float)):
                fmts[(k, "epoch")] += 1
            elif isinstance(o, str):
                fmts[(k, "RFC3339 Z/offset" if o.endswith("Z") or "+" in o[10:] or o[19:].count("-")
                      else "ISO sin zona")] += 1
    fechas(doc)
    L.append("- Formatos de fecha: " + "; ".join(f"`{k}`→{f} ×{n}" for (k, f), n in sorted(fmts.items())))
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo-acceso", action="store_true")
    ap.add_argument("--analizar", action="store_true", help="no descarga; solo analiza data/sample/")
    a = ap.parse_args()
    if not a.analizar:
        if not comprobar_acceso():
            sys.exit("Sin acceso a las APIs: revisa la lista de dominios permitidos.")
        if a.solo_acceso:
            return
        for et, ev, div, race in EVENTOS:
            try:
                descargar(et, ev, div, race)
            except Exception as e:  # noqa: BLE001
                print(f"  ERROR en {et}: {e}")
    informe = ["# Informe Fase 1 — muestras de telemetría\n",
               f"Generado {time.strftime('%Y-%m-%d %H:%M')} por fase1_muestras.py\n"]
    for et, *_ in EVENTOS:
        informe.append(analizar(et))
        informe.append(analizar_regatta(et))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "informe_fase1.md").write_text("\n".join(informe))
    print("\n".join(informe))


if __name__ == "__main__":
    main()
