"""Normalización de los datos de RaceSense (reglas en docs/fuente_datos.md)."""
from __future__ import annotations

from datetime import datetime, timezone


def vela(v: str | None) -> str:
    """Clave de vela: sin espacios y en mayúsculas ('GER1898' y 'GER 1898' son el mismo barco)."""
    return (v or "").replace(" ", "").upper()


def sn_de_hex(sn_hex: str) -> int:
    """El sn de /api/regatta va en hex ('0238004DAB'); la telemetría usa sus 16 bits bajos."""
    return int(sn_hex, 16) & 0xFFFF


def ms(valor, tz_offset_us: int = 0) -> int | None:
    """Marca de tiempo a epoch ms (UTC). Acepta los 4 formatos de RaceSense:
    epoch ms, RFC 3339 con zona, ISO sin zona (hora local de la regata) y {seconds, nanoseconds}."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return int(valor)
    if isinstance(valor, dict) and "seconds" in valor:
        return int(valor["seconds"]) * 1000 + int(valor.get("nanoseconds", 0)) // 1_000_000
    if isinstance(valor, str):
        d = datetime.fromisoformat(valor.replace("Z", "+00:00"))
        if d.tzinfo is None:  # hora local de la regata
            return int(d.replace(tzinfo=timezone.utc).timestamp() * 1000) - tz_offset_us // 1000
        return int(d.timestamp() * 1000)
    raise ValueError(f"Formato de fecha desconocido: {valor!r}")


def senal(start: dict) -> int:
    """Hora de la señal: startTime truncado al minuto (el dispositivo lo registra ~1 s tarde)."""
    return ms(start["startTime"]) // 60_000 * 60_000


def latlon_de_geojson(obj) -> tuple[float, float] | None:
    """{coordinates: [lon, lat]} → (lat, lon)."""
    c = (obj or {}).get("coordinates")
    return (c[1], c[0]) if c else None
