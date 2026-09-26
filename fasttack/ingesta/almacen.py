"""Caché local: respuestas de RaceSense (JSON), telemetría (Parquet) y estado de la app (SQLite).

Estructura en disco:
    datos/fasttack.sqlite                      campeonatos, ajustes por prueba y preferencias
    datos/racesense/{eventId}/*.json           respuestas de /api/regatta, racing-summary, courses…
    datos/racesense/{eventId}/{división}/tel_{t0}_{t1}.parquet   trozos de telemetría
    datos/racesense/{eventId}/{división}/tramos.json             qué intervalos están ya descargados
Una prueba terminada se descarga una sola vez.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from .. import config
from .normalizar import division_tele
from .racesense import COLUMNAS, Cliente

_ESQUEMA = """
create table if not exists campeonato (
    id text primary key,            -- eventId~división
    event_id text not null,
    division text not null,         -- nombre interno de la división ('Open', 'Gold')
    url text,
    nombre text, clase text, inicio integer, fin integer,
    estado text, progreso text, error text,
    cargado_en integer
);
create table if not exists ajuste_prueba (   -- lo que el usuario corrige a mano
    campeonato text not null,
    clave text not null,            -- hora de la señal (ms) como texto: estable entre recargas
    numero integer,                 -- numeración propia (null = automática)
    excluida integer,               -- 1 = no cuenta (entrenamiento, anulada…)
    viento_kn real,                 -- viento de referencia: TWS en el disparo
    viento_dir real,                -- y dirección (opcional)
    primary key (campeonato, clave)
);
create table if not exists preferencia (clave text primary key, valor text);
create table if not exists debrief (       -- textos de IA ya generados (se reutilizan mientras no cambien las cifras)
    campeonato text not null,
    ambito text not null,           -- 'campeonato' o la clave de la prueba
    barco text not null,
    huella text not null,           -- huella de las cifras de las que sale el texto
    texto text not null,
    origen text not null,           -- 'claude-code' o 'manual'
    avisos text,                    -- JSON: cifras del texto que no están en los datos
    creado_en integer not null,
    primary key (campeonato, ambito, barco)
);
"""


class Almacen:
    def __init__(self, raiz: Path = config.DATOS, cliente: Cliente | None = None):
        self.raiz = Path(raiz)
        self.raiz.mkdir(parents=True, exist_ok=True)
        self.cliente = cliente or Cliente()
        self._lock = threading.Lock()
        self.db = sqlite3.connect(self.raiz / "fasttack.sqlite", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(_ESQUEMA)
        cols = {r[1] for r in self.db.execute("pragma table_info(campeonato)")}
        if "alias" not in cols:   # nombre puesto por el usuario (v0.16)
            self.db.execute("alter table campeonato add column alias text")
            self.db.commit()

    # ------------------------------------------------------------------ SQLite
    def sql(self, q: str, args=()):
        with self._lock:
            cur = self.db.execute(q, args)
            self.db.commit()
            return cur.fetchall()

    def preferencia(self, clave: str, defecto: str | None = None) -> str | None:
        r = self.sql("select valor from preferencia where clave=?", (clave,))
        return r[0]["valor"] if r else defecto

    def fijar_preferencia(self, clave: str, valor: str):
        self.sql("insert into preferencia values (?, ?) on conflict(clave) do update set valor=excluded.valor",
                 (clave, valor))

    # ------------------------------------------------------------------ JSON de RaceSense
    def ruta(self, event_id: str, division: str | None = None) -> Path:
        """Carpeta de un evento de RaceSense, o de una sesión propia de archivos .vkx («vkx-…»)."""
        d = self.raiz / ("sesiones" if es_local(event_id) else "racesense") / event_id
        return d / division.replace("/", "_") if division else d

    def _dir(self, event_id: str, division: str | None = None) -> Path:
        d = self.ruta(event_id, division)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def json(self, event_id: str, nombre: str, obtener, refrescar: bool = False):
        """Respuesta cacheada. `refrescar` vuelve a pedirla (p. ej. el documento de un evento en curso)."""
        p = self._dir(event_id) / f"{nombre}.json"
        if p.exists() and not refrescar:
            return json.loads(p.read_text())
        d = obtener()
        p.write_text(json.dumps(d, ensure_ascii=False))
        return d

    # ------------------------------------------------------------------ telemetría
    def telemetria(self, event_id: str, division: str, desde: int, hasta: int,
                   progreso=None) -> dict[str, np.ndarray]:
        """Telemetría de [desde, hasta]. Descarga solo los trozos que falten."""
        d = self._dir(event_id, division)
        if es_local(event_id):   # sesión propia: solo los archivos .vkx importados
            return _leer_parquets(sorted(d.glob("tel_vkx_*.parquet")), desde, hasta)
        idx_p = d / "tramos.json"
        tramos = json.loads(idx_p.read_text()) if idx_p.exists() else []
        for a, b in _huecos(desde, hasta, [(t["desde"], t["hasta"]) for t in tramos if t["definitivo"]]):
            cols = self.cliente.telemetria(event_id, division_tele(division), a, b, progreso)
            nombre = f"tel_{a}_{b}.parquet"
            pq.write_table(pa.table({c: cols[c] for c in COLUMNAS}), d / nombre, compression="zstd")
            tramos = [t for t in tramos if not (t["desde"] == a and t["hasta"] == b)]
            tramos.append({"desde": a, "hasta": b, "archivo": nombre,
                           # un trozo vacío no se da por definitivo: se vuelve a pedir la próxima vez
                           "definitivo": bool(len(cols["ts"])) and b < time.time() * 1000 - config.MARGEN_DIRECTO_MS})
            idx_p.write_text(json.dumps(tramos))
        archivos = [d / t["archivo"] for t in tramos if t["hasta"] >= desde and t["desde"] <= hasta]
        from .propios import mezclar   # archivos .vkx propios: sustituyen a RaceSense para ese barco
        return mezclar(d, quitar_congeladas(_leer_parquets(archivos, desde, hasta)), desde, hasta)


def es_local(event_id: str) -> bool:
    return event_id.startswith("vkx-")


def _leer_parquets(archivos, desde: int, hasta: int) -> dict[str, np.ndarray]:
    partes = [pq.read_table(f, filters=[("ts", ">=", desde), ("ts", "<=", hasta)]) for f in archivos]
    if not partes:
        return {c: np.array([], dtype=tp) for c, tp in COLUMNAS.items()}
    tab = pa.concat_tables(partes)
    cols = {c: tab.column(c).to_numpy(zero_copy_only=False) for c in COLUMNAS}
    # Trozos contiguos comparten bordes: quitar duplicados (ts, sn) y ordenar.
    clave = cols["ts"].astype(np.int64) * 65536 + cols["sn"].astype(np.int64)
    _, unicos = np.unique(clave, return_index=True)
    orden = unicos[np.argsort(cols["ts"][unicos], kind="stable")]
    return {c: v[orden] for c, v in cols.items()}


CONGELADA_MS = 5_000


def quitar_congeladas(cols: dict) -> dict:
    """Quita las muestras «congeladas»: RaceSense repite a veces la misma muestra de un barco (misma
    posición, SOG y rumbo) durante minutos, mezclada con las reales. Un barco que navega no vuelve
    exactamente al mismo punto con la misma velocidad y rumbo: se conserva la primera vez y se quitan
    las repeticiones > 5 s después. Las balizas (fondeadas) no se tocan."""
    n = len(cols["ts"])
    if not n:
        return cols
    lat = np.round(cols["latitude"].astype(float) * 1e6).astype(np.int64)
    lon = np.round(cols["longitude"].astype(float) * 1e6).astype(np.int64)
    sog = np.round(np.nan_to_num(cols["sog"].astype(float), nan=-1) * 100).astype(np.int64)
    hdg = np.round(np.nan_to_num(cols["heading"].astype(float), nan=-1) * 10).astype(np.int64)
    sn = cols["sn"].astype(np.int64)
    ts = cols["ts"].astype(np.int64)
    orden = np.lexsort((ts, hdg, sog, lon, lat, sn))
    k = np.stack([sn, lat, lon, sog, hdg])[:, orden]
    nuevo = np.r_[True, np.any(k[:, 1:] != k[:, :-1], axis=0)]
    inicio = np.maximum.accumulate(np.where(nuevo, np.arange(n), 0))
    t_ord = ts[orden]
    congelada = (t_ord - t_ord[inicio] > CONGELADA_MS) & (sog[orden] > 50)   # moviéndose (> 0,5 kn)
    if "role" in cols:
        congelada &= cols["role"][orden] != "mark"
    quitar = np.zeros(n, bool)
    quitar[orden[congelada]] = True
    return {c: v[~quitar] for c, v in cols.items()}


def _huecos(desde: int, hasta: int, cubiertos: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Partes de [desde, hasta] que no están en `cubiertos`."""
    huecos, cursor = [], desde
    for a, b in sorted(cubiertos):
        if b < cursor or a > hasta:
            continue
        if a > cursor:
            huecos.append((cursor, a))
        cursor = max(cursor, b)
        if cursor >= hasta:
            break
    if cursor < hasta:
        huecos.append((cursor, hasta))
    return huecos
