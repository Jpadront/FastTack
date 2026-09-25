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
