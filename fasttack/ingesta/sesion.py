"""Sesiones propias: regatas o entrenamientos sin RaceSense, a partir de archivos .vkx del Atlas 2.

Una sesión se guarda como un campeonato más (id «vkx-…», división «Sesión»), así el motor, el
resumen y el debrief funcionan igual. Lo que en RaceSense viene del comité aquí sale de los archivos:
- Pruebas: las salidas marcadas con el cronómetro del Atlas (evento «salida») de cualquier barco.
- Línea de salida: los últimos pings de pin y comité antes de la señal (de cualquier barco).
- Llegadas: sin línea de llegada, final del último tramo de cada barco (estimada, ver
  motor/deteccion.llegada_sin_linea); la línea de llegada es la mediana de esos puntos.
- Balizas: estimadas con los rodeos de los barcos que haya (como las balizas sin Atlas).

Los archivos se guardan tal cual en la carpeta de datos (nunca salen del ordenador).
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from ..motor import deteccion as det
from ..motor import recorrido as rec
from ..motor.pistas import Pista, Proyeccion
from ..motor.trazas import construir
from . import normalizar as nz
from . import vkx
from .almacen import Almacen
from .campeonato import VERSION_INGESTA, Prueba, con_ajustes
from .racesense import COLUMNAS

PREFIJO = "vkx-"
DIVISION = "Sesión"
AGRUPAR_SALIDAS_MS = 60_000        # salidas de varios barcos a menos de esto son la misma
PING_ANTES_MS = 4 * 3600_000       # pings de línea válidos: de las 4 h anteriores a la señal…
PING_DESPUES_MS = 30 * 60_000      # …o, si no hay, de la media hora siguiente
MARGEN_SIGUIENTE_MS = 6 * 60_000   # una prueba acaba, como tarde, 6 min antes de la señal siguiente
DURACION_MAX_MS = 3 * 3600_000


def es_sesion(camp_id: str) -> bool:
    return camp_id.startswith(PREFIJO)


def _dir(alm: Almacen, sid: str):
    return alm._dir(sid, DIVISION)


def _meta(alm: Almacen, sid: str) -> dict:
    p = _dir(alm, sid) / "sesion.json"
    if not p.exists():
        raise KeyError(sid)
    return json.loads(p.read_text())


def _guardar_meta(alm: Almacen, meta: dict):
    (_dir(alm, meta["id"]) / "sesion.json").write_text(json.dumps(meta, ensure_ascii=False))


def crear(alm: Almacen, nombre: str, clase: str | None, zona: str | None) -> dict:
    sid = PREFIJO + uuid.uuid4().hex[:10]
    meta = {"id": sid, "nombre": nombre.strip() or "Sesión propia", "clase": (clase or "").strip() or None,
            "zona": zona or None, "archivos": []}
    _guardar_meta(alm, meta)
    alm.sql("insert into campeonato (id, event_id, division, nombre, clase, estado) values (?, ?, ?, ?, ?, 'listo')",
            (sid, sid, DIVISION, meta["nombre"], meta["clase"]))
    return reconstruir(alm, sid)


def añadir_vkx(alm: Almacen, sid: str, datos: bytes, vela: str, nombre_barco: str = "", nombre_archivo: str = "") -> dict:
    """Guarda un .vkx de un barco y vuelve a calcular las pruebas de la sesión."""
    meta = _meta(alm, sid)
    vela = vela.strip()
    if not nz.vela(vela):
        raise ValueError("Falta el número de vela del barco de este archivo.")
    reg = vkx.leer(datos)
    huella = hashlib.sha1(datos).hexdigest()[:12]
    if any(a["huella"] == huella for a in meta["archivos"]):
        raise ValueError("Este archivo ya está en la sesión.")
    n = max((a["n"] for a in meta["archivos"]), default=0) + 1
    d = _dir(alm, sid)
    (d / f"vkx_{n}.vkx").write_bytes(datos)
    cols = vkx.a_columnas(reg, vela, sn=n, division=DIVISION)
    pq.write_table(pa.table({c: cols[c] for c in COLUMNAS}), d / f"tel_vkx_{n}.parquet", compression="zstd")
    (d / f"vkx_{n}.json").write_text(json.dumps({"eventos": reg["eventos"], "linea": reg["linea"],
                                                   "declinacion_grados": reg["declinacion_grados"]}))
    meta["archivos"].append({"n": n, "huella": huella, "vela": vela, "clave": nz.vela(vela),
                             "nombre": nombre_barco.strip(), "archivo": nombre_archivo,
                             "desde": int(cols["ts"][0]), "hasta": int(cols["ts"][-1]), "muestras": len(cols["ts"]),
                             "salidas": len(vkx.salidas(reg)), "pings": len(reg["linea"])})
    _guardar_meta(alm, meta)
    return reconstruir(alm, sid)


def quitar_archivo(alm: Almacen, sid: str, n: int) -> dict:
    meta = _meta(alm, sid)
    meta["archivos"] = [a for a in meta["archivos"] if a["n"] != n]
    d = _dir(alm, sid)
    for f in (f"vkx_{n}.vkx", f"tel_vkx_{n}.parquet", f"vkx_{n}.json"):
        (d / f).unlink(missing_ok=True)
    _guardar_meta(alm, meta)
    return reconstruir(alm, sid)


def _desfase_ms(zona: str | None, ms: int) -> int:
    """Desfase horario (ms) de la zona en ese instante (con su horario de verano)."""
    if not zona:
        return 0
    try:
        import datetime as dt
        from zoneinfo import ZoneInfo
        off = dt.datetime.fromtimestamp(ms / 1000, tz=ZoneInfo(zona)).utcoffset()
        return int(off.total_seconds() * 1000) if off else 0
    except Exception:  # noqa: BLE001 - zona desconocida en este sistema: hora UTC
        return 0


def _agrupar(tiempos: list[int], dist_ms: int) -> list[int]:
    grupos: list[list[int]] = []
    for t in sorted(tiempos):
        if grupos and t - grupos[-1][-1] <= dist_ms:
            grupos[-1].append(t)
        else:
            grupos.append([t])
    return [int(np.median(g)) for g in grupos]


def reconstruir(alm: Almacen, sid: str) -> dict:
    """Pruebas, líneas y llegadas de la sesión a partir de todos sus archivos."""
    meta = _meta(alm, sid)
    d = _dir(alm, sid)
    for f in [*d.glob("analisis_*.json"), *d.glob("pistas_*.json")]:   # con otros barcos cambian
        f.unlink()
    eventos, pings = [], []
    for a in meta["archivos"]:
        j = json.loads((d / f"vkx_{a['n']}.json").read_text())
        eventos += [(int(t), tipo) for t, tipo, _ in j["eventos"]]
        pings += [(int(t), extremo, lat, lon) for t, extremo, lat, lon in j["linea"]]
    senales = _agrupar([t for t, tipo in eventos if tipo == 3], AGRUPAR_SALIDAS_MS)
    fin_datos = max((a["hasta"] for a in meta["archivos"]), default=0)

    pruebas = []
    for k, s in enumerate(senales):
        fin = min(senales[k + 1] - MARGEN_SIGUIENTE_MS if k + 1 < len(senales) else fin_datos, s + DURACION_MAX_MS)
        p = Prueba(clave=str(s), senal=s, origen="Atlas", raceNumber=None, estado="sin llegadas", ocs_fiable=False)
        p.linea_salida = _linea(pings, s)
        if p.linea_salida is None:
            p.nota = "Sin pings de la línea de salida (pin y comité) en los archivos: no se puede analizar."
        pruebas.append((p, fin))

    _llegadas(alm, sid, [x for x in pruebas if x[0].linea_salida], meta.get("zona"))
    pruebas = [p for p, _ in pruebas]

    barcos = {}
    for a in meta["archivos"]:
        barcos.setdefault(a["clave"], {"vela": a["vela"], "clave": a["clave"], "nombre": a["nombre"]})
    t0 = min((a["desde"] for a in meta["archivos"]), default=None)
    tz = _desfase_ms(meta.get("zona"), senales[0] if senales else (t0 or 0))
    camp = {
        "id": sid, "event_id": sid, "division": DIVISION, "fuente": "vkx",
        "clase": meta.get("clase"), "nombre": meta["nombre"],
        "inicio": t0, "fin": fin_datos or None, "revision": len(meta["archivos"]), "tz_offset_ms": tz,
        "roles_recorrido": {}, "barcos": sorted(barcos.values(), key=lambda b: b["clave"]),
        "archivos": meta["archivos"],
        "pruebas": [asdict(p) | {"n_llegadas": p.n_llegadas} for p in pruebas],
        "cargado_en": int(time.time() * 1000), "version_ingesta": VERSION_INGESTA,
    }
    (d / "campeonato.json").write_text(json.dumps(camp, ensure_ascii=False))
    alm.sql("update campeonato set nombre=?, clase=?, inicio=?, fin=?, estado='listo', cargado_en=? where id=?",
            (camp["nombre"], camp["clase"], camp["inicio"], camp["fin"], camp["cargado_en"], sid))
    return con_ajustes(alm, camp)


def _linea(pings: list, s: int) -> dict | None:
    """Últimos pings de pin (0) y comité (1) antes de la señal; si faltan, los primeros de después."""
    ext = {}
    for extremo in (0, 1):
        antes = [p for p in pings if p[1] == extremo and s - PING_ANTES_MS <= p[0] <= s]
        despues = [p for p in pings if p[1] == extremo and s < p[0] <= s + PING_DESPUES_MS]
        p = max(antes) if antes else (min(despues) if despues else None)
        if p is None:
            return None
        ext[extremo] = [float(p[2]), float(p[3])]
    return {"leftEnd": ext[0], "rightEnd": ext[1], "fuente": "pings del Atlas"}


def _llegadas(alm: Almacen, sid: str, pruebas: list[tuple[Prueba, int]], zona: str | None):
    """Llegada estimada de cada barco en cada prueba; la línea de llegada, su mediana."""
    if not pruebas:
        return
    desde = min(p.senal for p, _ in pruebas) - 60_000
    hasta = max(f for _, f in pruebas)
    cols = alm.telemetria(sid, DIVISION, desde, hasta)
    if not len(cols["ts"]):
        return
    proy = Proyeccion(float(np.mean(cols["latitude"])), float(np.mean(cols["longitude"])))
    trazas = construir(cols, proy)
    brutas = {}   # (prueba, vela) → LlegadaPropia
    for p, fin in pruebas:
        (la1, lo1), (la2, lo2) = p.linea_salida["leftEnd"], p.linea_salida["rightEnd"]
        pin = Pista.constante(*map(float, proy.xy(la1, lo1)))
        com = Pista.constante(*map(float, proy.xy(la2, lo2)))
        en_agua = {v: tr for v, tr in trazas.items() if tr.cobertura(p.senal, p.senal + 10 * 60_000) > 0.5}
        if not en_agua:
            continue
        eje = rec.eje_inicial(en_agua, pin, com, p.senal)
        ox, oy = (pin.x[0] + com.x[0]) / 2, (pin.y[0] + com.y[0]) / 2
        for v, tr in en_agua.items():
            ll = det.llegada_sin_linea(tr, eje, ox, oy, p.senal, fin)
            if ll is not None:
                brutas[(p.clave, v)] = ll
    # Referencia por día: punto mediano de las llegadas limpias (el barco se paró al llegar)
    por_dia: dict[str, list] = {}
    dia = {p.clave: _dia(p.senal, zona) for p, _ in pruebas}
    for (c, v), ll in brutas.items():
        if ll.limpia:
            por_dia.setdefault(dia[c], []).append((ll.x, ll.y))
    for p, _ in pruebas:
        llegadas, puntos, dudosas = {}, [], 0
        for (c, v), ll in brutas.items():
            if c != p.clave:
                continue
            if not ll.limpia:
                ref = por_dia.get(dia[c])
                aj = det.ajustar_a_referencia(trazas[v], ll, *np.median(ref, axis=0)) if ref else None
                if aj is not None:
                    ll = aj
                else:
                    dudosas += 1
            llegadas[v] = ll.t
            puntos.append((ll.x, ll.y))
        if not llegadas:
            p.nota = "No se detecta la llegada (¿prueba anulada o sin recorrido completo?)."
            continue
        p.llegadas = llegadas
        p.estado = "estimada"
        mx, my = np.median(puntos, axis=0)
        lat, lon = proy.latlon(float(mx), float(my))
        p.linea_llegada = {"leftEnd": [lat, lon], "rightEnd": [lat, lon], "fuente": "estimada"}
        p.nota = ("Llegada estimada: final del último tramo de cada barco (no hay línea de llegada en los archivos)."
                  + (f" {dudosas} llegada(s) poco fiables: el barco siguió navegando." if dudosas else ""))


def _dia(ms: int, zona: str | None) -> str:
    import datetime as dt
    return dt.datetime.fromtimestamp((ms + _desfase_ms(zona, ms)) / 1000, tz=dt.timezone.utc).strftime("%Y-%m-%d")
