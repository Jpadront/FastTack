"""De la URL de RaceSense al identificador del campeonato.

Formas aceptadas (ver docs/fuente_datos.md):
    https://player.vakaros.com/watch/{eventId}/{división}?ts=...#race=2&boat=...
    https://player.vakaros.com/?event={eventId}&division={división}
    https://player.vakaros.com/#event={eventId}&division={división}
    {eventId}   (el identificador suelto)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse

_ID = re.compile(r"^[A-Za-z0-9_-]{8,40}$")


@dataclass(frozen=True)
class RefCampeonato:
    event_id: str
    division: str | None  # etiqueta de la URL: suele ser la clase ("J/70"), no el nombre interno


class UrlNoValida(ValueError):
    pass


def leer_url(texto: str) -> RefCampeonato:
    texto = texto.strip()
    if _ID.match(texto):
        return RefCampeonato(texto, None)
    u = urlparse(texto)
    if not u.scheme or not u.netloc:
        raise UrlNoValida("No parece una URL. Copia el enlace completo del visor de RaceSense.")
    partes = [unquote(p) for p in u.path.split("/") if p]
    if len(partes) >= 2 and partes[0] == "watch" and _ID.match(partes[1]):
        return RefCampeonato(partes[1], partes[2] if len(partes) > 2 else None)
    for fuente in (u.query, u.fragment):
        q = parse_qs(fuente)
        ev = (q.get("event") or [None])[0]
        if ev and _ID.match(ev):
            return RefCampeonato(ev, (q.get("division") or [None])[0])
    raise UrlNoValida("La URL no incluye el identificador del campeonato "
                      "(formato esperado: https://player.vakaros.com/watch/<id>/<clase>).")
