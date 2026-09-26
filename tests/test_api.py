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


def test_renombrar_y_eliminar_sesion(tmp_path):
    c = cliente(tmp_path)
    sid = c.post("/api/sesiones", json={"nombre": "Entreno", "clase": "J/70"}).json()["id"]
    assert (tmp_path / "sesiones" / sid).exists()
    r = c.patch(f"/api/campeonatos/{sid}", json={"nombre": "Entreno de mayo"}).json()
    assert r["nombre"] == "Entreno de mayo" and r["nombre_original"] == "Entreno"
    fila = next(x for x in c.get("/api/campeonatos").json() if x["id"] == sid)
    assert fila["nombre"] == "Entreno de mayo"
    c.patch(f"/api/campeonatos/{sid}", json={"nombre": ""})   # vacío: vuelve al original
    assert next(x for x in c.get("/api/campeonatos").json() if x["id"] == sid)["nombre"] == "Entreno"
    assert c.delete(f"/api/campeonatos/{sid}").status_code == 200
    assert not any(x["id"] == sid for x in c.get("/api/campeonatos").json())
    assert not (tmp_path / "sesiones" / sid).exists()
    assert c.delete(f"/api/campeonatos/{sid}").status_code == 404


def test_debrief_en_segundo_plano(tmp_path, monkeypatch):
    """La generación no bloquea la petición: POST devuelve enseguida y GET informa hasta que termina."""
    import time
    from fasttack.ia import debrief
    monkeypatch.setattr(debrief, "comando_claude", lambda: "/usr/bin/true")
    monkeypatch.setattr(debrief, "datos_de", lambda alm, c, a, b: {"tipo": "debrief de una prueba", "x_kn": 4.5})
    monkeypatch.setattr(debrief, "generar_claude_code", lambda prompt, timeout_s=300: (time.sleep(0.3), "## Resumen\nVMG 4,5 kn.")[1])
    c = cliente(tmp_path)
    r = c.post("/api/campeonatos/xx~Open/debrief", json={"ambito": "k", "barco": "ESP1214"})
    assert r.status_code == 200 and r.json() == {"generando": True}
    for _ in range(40):
        g = c.get("/api/campeonatos/xx~Open/debrief?ambito=k&barco=ESP1214").json()
        if not g["generando"]:
            break
        time.sleep(0.1)
    assert g["debrief"]["texto"].startswith("## Resumen") and g["vigente"] and g["error"] is None
