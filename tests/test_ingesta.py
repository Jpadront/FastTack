import pytest

from fasttack.ingesta import normalizar as nz
from fasttack.ingesta.almacen import _huecos
from fasttack.ingesta.url import UrlNoValida, leer_url


@pytest.mark.parametrize("url, ev, div", [
    ("https://player.vakaros.com/watch/oRkxbTpSZPbSkrmKrbj2/J%2F70?ts=1788872452066.0466#race=2&boat=ESP+1214&tab=custom",
     "oRkxbTpSZPbSkrmKrbj2", "J/70"),
    ("https://player.vakaros.com/watch/NxFrzPhBiHHrg9C0XHHz", "NxFrzPhBiHHrg9C0XHHz", None),
    ("https://player.vakaros.com/?event=5JsqWPmBU6P7G5rk15ic&division=ILCA%20Gold", "5JsqWPmBU6P7G5rk15ic", "ILCA Gold"),
    ("https://player.vakaros.com/#event=5JsqWPmBU6P7G5rk15ic&division=Gold", "5JsqWPmBU6P7G5rk15ic", "Gold"),
    ("  oRkxbTpSZPbSkrmKrbj2 ", "oRkxbTpSZPbSkrmKrbj2", None),
])
def test_leer_url(url, ev, div):
    r = leer_url(url)
    assert (r.event_id, r.division) == (ev, div)


@pytest.mark.parametrize("url", ["hola", "https://player.vakaros.com/", "https://example.com/watch/x"])
def test_url_no_valida(url):
    with pytest.raises(UrlNoValida):
        leer_url(url)


def test_vela_y_sn():
    assert nz.vela("GER 1898") == nz.vela("ger1898") == "GER1898"
    assert nz.sn_de_hex("0238004DAB") == 19883


def test_fechas_en_los_cuatro_formatos():
    t = 1788869101000  # 2026-09-08 12:05:01 UTC
    assert nz.ms(t) == t
    assert nz.ms("2026-09-08T12:05:01Z") == t
    assert nz.ms("2026-09-08T13:05:01", tz_offset_us=3_600_000_000) == t  # hora local UTC+1
    assert nz.ms({"seconds": t // 1000, "nanoseconds": 0}) == t
    assert nz.senal({"startTime": t}) == 1788869100000  # truncado al minuto


def test_huecos_de_cache():
    assert _huecos(0, 100, []) == [(0, 100)]
    assert _huecos(0, 100, [(0, 100)]) == []
    assert _huecos(0, 100, [(20, 40), (60, 80)]) == [(0, 20), (40, 60), (80, 100)]
    assert _huecos(50, 70, [(0, 60)]) == [(60, 70)]


def test_division_de_la_telemetria():
    from fasttack.ingesta.normalizar import division_tele, misma_division
    assert division_tele("Snipe Worlds 2026") == "Snipe_Worlds_2026"
    assert division_tele("Open") == "Open"
    assert misma_division("Snipe_Worlds_2026", "Snipe Worlds 2026") and not misma_division("Open", "Gold")


def test_quitar_muestras_congeladas():
    import numpy as np
    from fasttack.ingesta.almacen import quitar_congeladas
    # barco 1 navegando; en t=20 s y t=30 s RaceSense repite la muestra de t=1 s (congelada)
    ts = np.array([0, 1000, 2000, 20000, 21000, 30000])
    lat = np.array([38.0, 38.0001, 38.0002, 38.0001, 38.0020, 38.0001])
    cols = {"ts": ts, "sn": np.ones(6, int), "latitude": lat, "longitude": np.full(6, -9.4),
            "sog": np.array([6.0, 6.1, 6.2, 6.1, 6.3, 6.1]), "heading": np.array([10.0, 11, 12, 11, 13, 11]),
            "role": np.array(["boat"] * 6, dtype=object)}
    out = quitar_congeladas(cols)
    assert list(out["ts"]) == [0, 1000, 2000, 21000]
    # una baliza fondeada repite posición y no se toca
    cols["role"] = np.array(["mark"] * 6, dtype=object)
    assert len(quitar_congeladas(cols)["ts"]) == 6


def test_meteo_media_de_la_prueba(tmp_path, monkeypatch):
    """Viento y corriente del modelo promediados a las horas de la prueba (sin red: respuestas fijas)."""
    from fasttack.ingesta import meteo
    horas = [f"2026-09-12T{h:02d}:00" for h in range(24)]

    def falso(url, params):
        if "marine" in url:
            return {"hourly": {"time": horas, "ocean_current_velocity": [1.852] * 24, "ocean_current_direction": [90] * 24}}
        return {"hourly": {"time": horas, "wind_speed_10m": [10.0 + h for h in range(24)],
                           "wind_direction_10m": [350] * 12 + [10] * 12, "wind_gusts_10m": [20.0] * 24}}
    monkeypatch.setattr(meteo, "_pedir", falso)
    import datetime as dt
    t = lambda h: int(dt.datetime(2026, 9, 12, h, tzinfo=dt.timezone.utc).timestamp() * 1000)
    m = meteo.en_ventana(tmp_path, 38.7, -9.4, t(11), t(13))
    assert m["horas"] == ["11:00", "12:00", "13:00"]
    assert m["viento"]["kn"] == 22.0 and m["viento"]["rachas_kn"] == 20.0
    assert m["viento"]["desde_grados"] in (0, 360) or abs(m["viento"]["desde_grados"] - 3) < 5   # media circular 350°/10°
    assert m["corriente"] == {"kn": 1.0, "hacia_grados": 90, "max_kn": 1.0}
    assert (tmp_path / "meteo").exists()
