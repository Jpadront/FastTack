"""Diagnóstico de la VMG frente al top 5 (velocidad o ángulo)."""
from fasttack.ia.hechos import causa_vmg


def test_ceñida_por_angulo():
    # misma SOG, 3° más abierto: la VMG baja por el ángulo
    c = causa_vmg(4.0, 5.6, 45.0, 4.2, 5.6, 42.0, popa=False)
    assert c["vmg"] == "peor que el top 5" and c["causa"] == "ángulo" and c["angulo"].startswith("más abierto")


def test_popa_por_velocidad():
    c = causa_vmg(7.4, 9.8, 142.0, 8.3, 10.7, 142.0, popa=True)
    assert c["causa"] == "velocidad" and c["velocidad"] == "más lento"


def test_igual():
    assert causa_vmg(4.2, 5.6, 42.0, 4.21, 5.6, 42.0, popa=False) == {"vmg": "igual que el top 5"}


def test_sin_datos():
    assert causa_vmg(None, 5.6, 42.0, 4.2, 5.6, 42.0, popa=False) is None
