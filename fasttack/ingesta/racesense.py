"""Cliente de las APIs públicas de RaceSense (no documentadas oficialmente; ver docs/fuente_datos.md).

Peticiones secuenciales, con pausa y un User-Agent identificable. Nada de caché aquí: de eso se
encarga `almacen`.
"""
from __future__ import annotations

import time
from urllib.parse import quote

import httpx
import numpy as np

from .. import config

# Columnas de /telemetry/event y el tipo con el que se guardan.
COLUMNAS = {
    "ts": np.int64, "sn": np.int32, "division": object, "sail_number": object,
    "race_number": np.int16, "start_number": np.int16, "race_stage": object, "role": object,
    "latitude": np.float64, "longitude": np.float64, "pitch": np.float32, "roll": np.float32,
    "heading": np.float32, "sog": np.float32, "status": np.int16,
}


class ErrorRaceSense(RuntimeError):
    pass


class Cliente:
    def __init__(self, pausa_s: float = config.PAUSA_S, http: httpx.Client | None = None):
        self.pausa_s = pausa_s
        self.http = http or httpx.Client(headers={"User-Agent": config.USER_AGENT}, timeout=120,
                                         follow_redirects=True)
        self._ultima = 0.0

    def _get(self, url: str, params: dict | None = None, reintentos: int = 3):
        espera = self.pausa_s - (time.monotonic() - self._ultima)
        if espera > 0:
            time.sleep(espera)
        for intento in range(reintentos):
            try:
                r = self.http.get(url, params={k: v for k, v in (params or {}).items() if v is not None})
                self._ultima = time.monotonic()
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                return r.json()
            except (httpx.TransportError, httpx.HTTPStatusError) as e:
                if intento == reintentos - 1:
                    raise ErrorRaceSense(f"RaceSense no responde ({url}): {e}") from e
                time.sleep(2 ** (intento + 1))

    # ------------------------------------------------------------------ player.vakaros.com
    def regatta(self, event_id: str) -> dict:
        d = self._get(f"{config.PLAYER}/api/regatta", {"event": event_id})
        if not d or not d.get("revisions"):
            raise ErrorRaceSense("RaceSense no tiene ese campeonato. Comprueba el enlace.")
        return d

    def correcciones(self, tipo: str, event_id: str, desde: int, hasta: int) -> dict:
        """race-hides, course-overlay o boat-mutes del organizador para un intervalo."""
        return self._get(f"{config.PLAYER}/api/{tipo}/{quote(event_id)}", {"from": desde, "to": hasta}) or {}

    # ------------------------------------------------------------------ teleapi.regatta.app
    def racing_summary(self, event_id: str) -> dict:
        return self._get(f"{config.TELE}/telemetry/racing-summary/{event_id}") or {}

    def event_times(self, event_id: str, division: str | None = None) -> dict:
        return self._get(f"{config.TELE}/telemetry/event-times/{event_id}", {"division": division}) or {}

    def courses(self, event_id: str, division: str | None = None) -> dict:
        return self._get(f"{config.TELE}/courses/{event_id}", {"division": division}) or {}

    def telemetria(self, event_id: str, division: str, desde: int, hasta: int,
                   progreso=None) -> dict[str, np.ndarray]:
        """Todas las filas de la división entre `desde` y `hasta` (ms), paginando por `after`.
        `after` es inclusivo: se deduplica por (ts, sn)."""
        filas, vistos, after, campos = [], set(), desde, None
        while True:
            d = self._get(f"{config.TELE}/telemetry/event/{event_id}",
                          {"division": division, "after": after, "before": hasta,
                           "limit": config.LIMITE_FILAS})
            campos = campos or (d or {}).get("Fields")
            rows = (d or {}).get("Rows") or []
            if not rows:
                break
            i_ts, i_sn = campos.index("ts"), campos.index("sn")
            nuevas = 0
            for r in rows:
                k = (r[i_ts], r[i_sn])
                if k not in vistos:
                    vistos.add(k)
                    filas.append(r)
                    nuevas += 1
            if progreso:
                progreso(len(filas))
            if len(rows) < config.LIMITE_FILAS or nuevas == 0:
                break
            after = max(r[i_ts] for r in rows)
        return a_columnas(campos, filas)


def a_columnas(campos: list[str] | None, filas: list[list]) -> dict[str, np.ndarray]:
    if campos is None:
        return {c: np.array([], dtype=t) for c, t in COLUMNAS.items()}
    ix = {c: i for i, c in enumerate(campos)}
    faltan = set(COLUMNAS) - set(ix)
    if faltan:
        raise ErrorRaceSense(f"La telemetría ha cambiado de formato: faltan {sorted(faltan)}")
    out = {}
    for c, t in COLUMNAS.items():
        vals = [r[ix[c]] for r in filas]
        if t is object:
            out[c] = np.array([v or "" for v in vals], dtype=object)
        else:
            out[c] = np.array([0 if v is None else v for v in vals], dtype=t)
    orden = np.argsort(out["ts"], kind="stable")
    return {c: v[orden] for c, v in out.items()}
