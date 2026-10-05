"""Semáforo de datos de una prueba: ¿fue el barco rápido? (bien, normal o mal).

Sale de la VMG navegando (rendimiento del motor) frente a toda la flota de la prueba: el percentil
de la flota que el barco superó en ceñida y en popa, y su media. Frente a la flota y no frente al
top 5, para que un barco de media flota no salga siempre en rojo. Tercio de arriba = bien, tercio
del medio = normal, tercio de abajo = mal. Con menos de MIN_BARCOS barcos con datos no se da.
"""
from __future__ import annotations

MIN_BARCOS = 5
CORTES = (100 / 3, 200 / 3)   # percentil: < 33,3 mal · < 66,7 normal · resto bien


def percentil(valor: float, otros: list[float]) -> float:
    """% de los otros barcos con menos VMG (los empates cuentan la mitad)."""
    if not otros:
        return 50.0
    menos = sum(1 for x in otros if x < valor) + 0.5 * sum(1 for x in otros if x == valor)
    return 100 * menos / len(otros)


def semaforo(an: dict, v: str) -> dict | None:
    rd = an.get("rendimiento") or {}
    mio = rd.get(v)
    if not mio:
        return None
    pcts = {}
    for modo in ("ceñida", "popa"):
        k = f"vmg_{modo}"
        otros = [r[k] for x, r in rd.items() if x != v and r.get(k) is not None]
        if mio.get(k) is not None and len(otros) + 1 >= MIN_BARCOS:
            pcts[modo] = round(percentil(mio[k], otros))
    if not pcts:
        return None
    p = sum(pcts.values()) / len(pcts)
    nivel = "mal" if p < CORTES[0] else "normal" if p < CORTES[1] else "bien"
    return {"nivel": nivel, "percentil": round(p), **{f"percentil_{m}": x for m, x in pcts.items()}}
