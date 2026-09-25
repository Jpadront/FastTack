from fastapi.testclient import TestClient

from fasttack.api.app import crear_app
from fasttack.ingesta.almacen import Almacen


def cliente(tmp_path):
    return TestClient(crear_app(Almacen(tmp_path)))


def test_preferencia_barco_por_defecto_y_cambio(tmp_path):
    c = cliente(tmp_path)
    assert c.get("/api/preferencias").json() == {"barco": "ESP1214"}
    c.put("/api/preferencias", json={"barco": "ESP1170"})
    assert c.get("/api/preferencias").json() == {"barco": "ESP1170"}


def test_url_no_valida(tmp_path):
    r = cliente(tmp_path).post("/api/campeonatos", json={"url": "hola"})
    assert r.status_code == 422


def test_campeonato_desconocido(tmp_path):
    assert cliente(tmp_path).get("/api/campeonatos/xx~Open").status_code == 404
    assert cliente(tmp_path).get("/api/no-existe").status_code == 404
