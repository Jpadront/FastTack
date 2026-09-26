"""Viento y corriente de referencia de un modelo meteorológico (Open-Meteo, gratis y sin clave).

- Viento a 10 m (velocidad, dirección de la que viene y rachas), hora a hora: API de previsiones
  históricas (modelos de 2–10 km archivados desde 2022). No se usa el reanálisis ERA5 (~25 km): en
  la costa mezcla tierra y mar (en el Mundial de Cascais daba 4 kn con 20–25 kn reales).
- Corriente superficial (velocidad y dirección hacia la que va), hora a hora: API marina.
Es un modelo: el viento a 10 m y promediado puede diferir del del campo de regatas. Se guarda en
datos/meteo/ y no se vuelve a pedir.
"""
from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path

import httpx

from .. import config

VIENTO_URLS = ("https://historical-forecast-api.open-meteo.com/v1/forecast",)
MARINA_URL = "https://marine-api.open-meteo.com/v1/marine"
KMH_A_KN = 1 / 1.852


class ErrorMeteo(RuntimeError):
    pass


def _dia(ms: int) -> str:
    return dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc).strftime("%Y-%m-%d")


def _pedir(url: str, params: dict) -> dict:
    try:
        r = httpx.get(url, params=params, timeout=30, headers={"User-Agent": config.USER_AGENT})
    except httpx.HTTPError as e:
        raise ErrorMeteo(f"Sin conexión con Open-Meteo: {e}") from e
    d = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code != 200 or d.get("error"):
        raise ErrorMeteo(f"Open-Meteo: {d.get('reason') or r.status_code}")
    return d


def horario(raiz: Path, lat: float, lon: float, dia: str, solo_cache: bool = False) -> dict:
    """Datos horarios de un día (UTC) en un punto, con caché en disco."""
    d = raiz / "meteo"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{lat:.2f}_{lon:.2f}_{dia}.json"
    if f.exists():
        return json.loads(f.read_text())
    if solo_cache:
        raise ErrorMeteo("Sin datos del modelo guardados.")
    base = {"latitude": round(lat, 3), "longitude": round(lon, 3), "start_date": dia, "end_date": dia, "timezone": "UTC"}
    out = {"viento": None, "corriente": None, "errores": []}
    for url in VIENTO_URLS:
        try:
            v = _pedir(url, base | {"hourly": "wind_speed_10m,wind_direction_10m,wind_gusts_10m", "wind_speed_unit": "kn"})
            if any(x is not None for x in v["hourly"]["wind_speed_10m"]):
                out["viento"] = {"fuente": "modelo de previsión (Open-Meteo)", **v["hourly"]}
                break
        except ErrorMeteo as e:
            out["errores"].append(str(e))
    try:
        m = _pedir(MARINA_URL, base | {"hourly": "ocean_current_velocity,ocean_current_direction"})
        if any(x is not None for x in m["hourly"]["ocean_current_velocity"]):
            out["corriente"] = m["hourly"]
    except ErrorMeteo as e:
        out["errores"].append(str(e))
    if out["viento"] is None and out["corriente"] is None:
        raise ErrorMeteo("; ".join(dict.fromkeys(out["errores"])) or "Open-Meteo no tiene datos para ese día y lugar.")
    if not out["errores"]:   # solo se guarda si no hubo fallos (un límite diario no debe quedar grabado)
        f.write_text(json.dumps(out))
    return out


def _media_circular(ang, pesos):
    s = sum(w * math.sin(math.radians(a)) for a, w in zip(ang, pesos))
    c = sum(w * math.cos(math.radians(a)) for a, w in zip(ang, pesos))
    return math.degrees(math.atan2(s, c)) % 360


def en_ventana(raiz: Path, lat: float, lon: float, desde_ms: int, hasta_ms: int, solo_cache: bool = False) -> dict:
    """Viento y corriente medios del modelo entre desde y hasta (horas que tocan la ventana)."""
    horas = []
    for dia in sorted({_dia(desde_ms), _dia(hasta_ms)}):
        h = horario(raiz, lat, lon, dia, solo_cache)
        for k, t in enumerate((h.get("viento") or h.get("corriente") or {}).get("time", [])):
            ms = int(dt.datetime.fromisoformat(t).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
            if desde_ms - 1800_000 <= ms <= hasta_ms + 1800_000:
                horas.append((ms, h, k))
    if not horas:
        raise ErrorMeteo("Open-Meteo no tiene datos a las horas de la prueba.")
    out = {"horas": [dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc).strftime("%H:%M") for ms, _, _ in horas]}
    errores = [e for _, h, _ in horas for e in h.get("errores", [])]
    if errores:
        out["aviso"] = "; ".join(dict.fromkeys(errores))
    vs = [(h["viento"]["wind_speed_10m"][k], h["viento"]["wind_direction_10m"][k], h["viento"]["wind_gusts_10m"][k])
          for _, h, k in horas if h.get("viento") and h["viento"]["wind_speed_10m"][k] is not None]
    out["serie"] = [[ms, h["viento"]["wind_speed_10m"][k], h["viento"]["wind_direction_10m"][k]]
                    for ms, h, k in horas if h.get("viento") and h["viento"]["wind_speed_10m"][k] is not None]
    if vs:
        out["viento"] = {"kn": round(sum(x[0] for x in vs) / len(vs), 1),
                         "desde_grados": round(_media_circular([x[1] for x in vs], [x[0] for x in vs])),
                         "rachas_kn": round(max(x[2] for x in vs if x[2] is not None), 1) if any(x[2] is not None for x in vs) else None,
                         "min_kn": round(min(x[0] for x in vs), 1), "max_kn": round(max(x[0] for x in vs), 1),
                         "fuente": horas[0][1]["viento"]["fuente"]}
    cs = [(h["corriente"]["ocean_current_velocity"][k] * KMH_A_KN, h["corriente"]["ocean_current_direction"][k])
          for _, h, k in horas if h.get("corriente") and h["corriente"]["ocean_current_velocity"][k] is not None]
    if cs:
        # media vectorial (la corriente cambia de sentido con la marea)
        e = sum(v * math.sin(math.radians(d)) for v, d in cs) / len(cs)
        n = sum(v * math.cos(math.radians(d)) for v, d in cs) / len(cs)
        out["corriente"] = {"kn": round(math.hypot(e, n), 2), "hacia_grados": round(math.degrees(math.atan2(e, n)) % 360),
                            "max_kn": round(max(v for v, _ in cs), 2)}
    return out
