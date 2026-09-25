"""Comprueba que cada cifra de un texto de IA sale de los datos que se le dieron.

Cada número del texto se compara, con su unidad (kn, m, s, °, %), con las cifras de los datos
(unidad por el sufijo del campo: _kn, _m, _s, _grados, _pct). Vale si el número del texto es un
redondeo de alguna cifra de los datos (±media unidad de su último decimal). Los tiempos mm:ss se
pasan a segundos. Se ignoran los números de etiquetas (P3, Ceñida 2, top 10, ESP 1214…), los
marcadores de lista y los enteros pequeños sin unidad (recuentos como «3 claves»).
"""
from __future__ import annotations

import re

UNIDADES = {"kn": "kn", "nudo": "kn", "nudos": "kn", "m": "m", "metro": "m", "metros": "m",
            "s": "s", "seg": "s", "segundo": "s", "segundos": "s", "min": "min", "minuto": "min", "minutos": "min",
            "°": "grados", "grado": "grados", "grados": "grados", "%": "pct"}
SUFIJOS = (("_kn", "kn"), ("_m", "m"), ("_s", "s"), ("_grados", "grados"), ("_pct", "pct"))

NUMERO = re.compile(
    r"(?<![\w/.,])[-−+]?(\d+(?:[.,]\d+)?)(?::(\d{2}))?(?::(\d{2}))?"
    r"(?:\s*(kn|nudos?|metros?|m|segundos?|seg|s|minutos?|min|°|grados?|%)(?![\wáéíóúñ]))?")
ETIQUETA = re.compile(r"(?:\bP|[Cc]eñidas?|[Pp]opas?|[Oo]ffsets?|[Bb]alizas?|[Pp]ruebas?|[Rr]egatas?|[Tt]op|"
                      r"[Tt]ramos?|J/|\b(?!VMG|SOG|TWA|TWD|TWS|COG|HDG)[A-Z]{3}|[Pp]uertas?|RRS|[Aa]pp?)\s*$")
LISTA = re.compile(r"^\s*(?:[-*]\s*)?$")


def cifras(datos) -> list[tuple[float, str | None]]:
    """(valor absoluto, unidad) de cada número de los datos."""
    out = []

    def rec(x, clave=""):
        if isinstance(x, dict):
            for k, v in x.items():
                # números que forman parte del nombre del campo («puesto_a_60_s», «top_15»)
                for n, u in re.findall(r"(?:^|_)(\d+)(?:_(s|m)(?=_|$))?", k):
                    out.append((float(n), {"s": "s", "m": "m"}.get(u)))
                rec(v, k)
        elif isinstance(x, list):
            for v in x:
                rec(v, clave)
        elif isinstance(x, (int, float)) and not isinstance(x, bool):
            unidad = next((u for suf, u in SUFIJOS if clave.endswith(suf)), None)
            out.append((abs(float(x)), unidad))
    rec(datos)
    return out


def no_verificadas(texto: str, datos) -> list[str]:
    """Cifras del texto que no aparecen en los datos (vacía = todo cuadra)."""
    base = cifras(datos)
    malas = []
    for linea in texto.splitlines():
        for m in NUMERO.finditer(linea):
            antes = linea[:m.start()]
            if ETIQUETA.search(antes):
                continue
            ent, mm, ss, uni = m.group(1), m.group(2), m.group(3), m.group(4)
            # «1.» / «2)» al empezar una línea: marcador de lista
            if LISTA.match(antes) and linea[m.end():m.end() + 1] in (".", ")") and not uni:
                continue
            unidad = UNIDADES.get(uni) if uni else None
            if mm is not None:  # mm:ss o h:mm:ss
                partes = [int(ent.replace(",", ".").split(".")[0]), int(mm)] + ([int(ss)] if ss else [])
                valor = partes[0] * 3600 + partes[1] * 60 + partes[2] if ss else partes[0] * 60 + partes[1]
                tol, unidad = 0.5, "s"
            else:
                txt = ent.replace(",", ".")
                valor = float(txt)
                dec = len(txt.split(".")[1]) if "." in txt else 0
                tol = 0.5 * 10 ** -dec + 1e-9
                if unidad == "min":
                    valor, tol, unidad = valor * 60, 30 + 1e-9, "s"
            if unidad is None and mm is None and valor <= 3 and "." not in ent and "," not in ent:
                continue  # recuentos pequeños
            candidatos = [v for v, u in base if unidad is None or u == unidad]
            if not any(abs(valor - v) <= tol for v in candidatos):
                malas.append(m.group(0).strip())
    return malas
