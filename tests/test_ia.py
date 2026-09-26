import os
import stat

from fasttack.ia import debrief
from fasttack.ia.validar import no_verificadas

DATOS = {"prueba": {"puesto": 14, "tiempo_s": 5200, "detras_del_ganador_s": 181},
         "tramos": [{"nombre": "Ceñida 1", "vmg_kn": 4.06, "vmg_frente_a_la_mediana_kn": -0.34, "layline": {"exceso_m": 87},
                     "twa_grados": 41.5, "cobertura_pct": 66, "parcial_s": 1552}]}


def test_validar_acepta_cifras_de_los_datos_y_redondeos():
    texto = ("## Ceñidas\nEn la Ceñida 1, VMG 4,06 kn (4,1 kn redondeado), 0,34 kn por debajo de la mediana; "
             "TWA 41,5°, 87 m de exceso de layline, cobertura 66 %. Parcial 25:52. Puesto 14 de la P9, a 181 s.\n"
             "1. Tres claves para ESP 1214 en el top 10.")
    assert no_verificadas(texto, DATOS) == []


def test_validar_marca_cifras_inventadas_o_con_otra_unidad():
    texto = "VMG 4,5 kn y 87 s fuera de la layline; perdió 120 m en la salida."
    assert no_verificadas(texto, DATOS) == ["4,5 kn", "87 s", "120 m"]


def test_huella_estable_y_sensible_a_los_datos():
    assert debrief.huella(DATOS) == debrief.huella(dict(DATOS))
    assert debrief.huella(DATOS) != debrief.huella({**DATOS, "prueba": {"puesto": 15}})


def test_instrucciones_segun_el_ambito():
    assert "Qué trabajar" in debrief.instrucciones({"tipo": "debrief de una prueba"})
    assert "Qué entrenar" in debrief.instrucciones({"tipo": "debrief del campeonato"})


def test_generar_con_claude_code_usa_el_comando(tmp_path, monkeypatch):
    falso = tmp_path / "claude"
    falso.write_text("#!/bin/sh\ncat > /dev/null\necho '## Resumen'\necho 'Puesto 14.'\n")
    falso.chmod(falso.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("FASTTACK_CLAUDE", str(falso))
    assert debrief.generar_claude_code("hola") == "## Resumen\nPuesto 14."


def test_sin_claude_code_error_claro(monkeypatch):
    monkeypatch.setenv("FASTTACK_CLAUDE", "no-existe-este-comando")
    try:
        debrief.generar_claude_code("hola")
    except debrief.IANoDisponible as e:
        assert "no está instalado" in str(e)
    else:
        raise AssertionError("debía fallar")


def test_cifras_del_nombre_del_campo():
    datos = {"salidas": {"veces_en_el_top_10_a_60_s": 1}}
    assert no_verificadas("Solo 1 de 3 salidas en el top 10 a 60 s; a 90 s no hay dato.", datos) == ["90 s"]


def test_instrucciones_del_dia():
    t = debrief.instrucciones({"tipo": "debrief del día", "clase": "Snipe"})
    assert "Lo que más costó" in t and "equipo de Snipe" in t


def test_validador_punto_de_miles():
    from fasttack.ia.validar import no_verificadas
    datos = {"parcial_s": 1533, "vmg_kn": 5.44}
    assert no_verificadas("Parcial de 1.533 s a 5,44 kn.", datos) == []
    assert no_verificadas("Parcial de 1.534 s.", datos) == ["1.534 s"]
