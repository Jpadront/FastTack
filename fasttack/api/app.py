"""API HTTP de FastTack y servidor de la web compilada."""
from __future__ import annotations

import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..ingesta import campeonato as camp_mod
from ..ingesta.almacen import Almacen
from ..ingesta.campeonato import DivisionAmbigua, elegir_division
from ..ingesta.racesense import ErrorRaceSense
from ..ingesta.url import UrlNoValida, leer_url
from .. import __version__, servicio

WEB = Path(__file__).resolve().parent.parent / "web"
BARCO_POR_DEFECTO = "ESP1214"


class PeticionCarga(BaseModel):
    url: str
    division: str | None = None


class AjustePrueba(BaseModel):
    numero: int | None = None
    excluida: bool | None = None
    viento_kn: float | None = None
    viento_dir: float | None = None


class Preferencias(BaseModel):
    barco: str


def crear_app(alm: Almacen | None = None) -> FastAPI:
    alm = alm or Almacen()
    app = FastAPI(title="FastTack", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.add_middleware(GZipMiddleware, minimum_size=2000)
    tareas: dict[str, dict] = {}  # carga en curso por campeonato

    def _cargar(camp_id: str, url: str, division: str):
        def progreso(texto):
            tareas[camp_id]["progreso"] = texto
            alm.sql("update campeonato set progreso=? where id=?", (texto, camp_id))
        try:
            c = camp_mod.cargar(alm, url, division, progreso)
            alm.sql("update campeonato set estado='listo', progreso=null, error=null, nombre=?, clase=?, "
                    "inicio=?, fin=?, cargado_en=? where id=?",
                    (c["nombre"], c["clase"], c["inicio"], c["fin"], c["cargado_en"], camp_id))
        except Exception as e:  # noqa: BLE001 - el error se enseña en la interfaz
            alm.sql("update campeonato set estado='error', error=? where id=?", (str(e), camp_id))
        finally:
            tareas.pop(camp_id, None)

    @app.post("/api/campeonatos", status_code=202)
    def cargar(p: PeticionCarga):
        try:
            ref = leer_url(p.url)
            reg = alm.json(ref.event_id, "regatta", lambda: alm.cliente.regatta(ref.event_id), refrescar=True)
            div = elegir_division(reg["revisions"][-1]["doc"], p.division or ref.division)
        except UrlNoValida as e:
            raise HTTPException(422, str(e)) from e
        except DivisionAmbigua as e:
            raise HTTPException(409, {"mensaje": str(e), "divisiones": e.opciones}) from e
        except ErrorRaceSense as e:
            raise HTTPException(502, str(e)) from e
        camp_id = f"{ref.event_id}~{div['name']}"
        if camp_id in tareas:
            return {"id": camp_id, "estado": "cargando"}
        doc = reg["revisions"][-1]["doc"]
        alm.sql("insert into campeonato (id, event_id, division, url, nombre, clase, estado) "
                "values (?, ?, ?, ?, ?, ?, 'cargando') on conflict(id) do update set "
                "estado='cargando', error=null, url=excluded.url",
                (camp_id, ref.event_id, div["name"], p.url, doc.get("name"), div.get("boatClass")))
        tareas[camp_id] = {"progreso": "Empezando", "desde": time.time()}
        threading.Thread(target=_cargar, args=(camp_id, p.url, div["name"]), daemon=True).start()
        return {"id": camp_id, "estado": "cargando"}

    @app.get("/api/campeonatos")
    def lista():
        return [dict(r) for r in alm.sql(
            "select id, nombre, clase, division, inicio, fin, estado, progreso, error, cargado_en "
            "from campeonato order by coalesce(inicio, 0) desc")]

    @app.get("/api/campeonatos/{camp_id:path}/estado")
    def estado(camp_id: str):
        r = alm.sql("select estado, progreso, error from campeonato where id=?", (camp_id,))
        if not r:
            raise HTTPException(404, "Campeonato no encontrado")
        return dict(r[0])

    @app.patch("/api/campeonatos/{camp_id:path}/pruebas/{clave}")
    def ajustar(camp_id: str, clave: str, a: AjustePrueba):
        cambios = a.model_dump(exclude_unset=True)
        if not cambios:
            raise HTTPException(422, "Nada que cambiar")
        cols = ", ".join(cambios)
        alm.sql(f"insert into ajuste_prueba (campeonato, clave, {cols}) values (?, ?, {', '.join('?' * len(cambios))}) "
                f"on conflict(campeonato, clave) do update set " + ", ".join(f"{c}=excluded.{c}" for c in cambios),
                (camp_id, clave, *[int(v) if isinstance(v, bool) else v for v in cambios.values()]))
        return detalle(camp_id)

    @app.get("/api/campeonatos/{camp_id:path}/pruebas/{clave}/pistas")
    def pistas_(camp_id: str, clave: str):
        try:
            return servicio.pistas_prueba(alm, camp_id, clave)
        except KeyError as e:
            raise HTTPException(404, "Prueba no encontrada") from e
        except servicio.PruebaNoAnalizable as e:
            raise HTTPException(422, str(e)) from e
        except ErrorRaceSense as e:
            raise HTTPException(502, str(e)) from e

    @app.get("/api/campeonatos/{camp_id:path}/pruebas/{clave}/analisis")
    def analisis(camp_id: str, clave: str, recalcular: bool = False):
        try:
            return servicio.analisis_prueba(alm, camp_id, clave, recalcular)
        except KeyError as e:
            raise HTTPException(404, "Prueba no encontrada") from e
        except servicio.PruebaNoAnalizable as e:
            raise HTTPException(422, str(e)) from e
        except ErrorRaceSense as e:
            raise HTTPException(502, str(e)) from e

    @app.get("/api/campeonatos/{camp_id:path}")
    def detalle(camp_id: str):
        c = camp_mod.leer(alm, camp_id)
        r = alm.sql("select estado, progreso, error, url from campeonato where id=?", (camp_id,))
        if not c and not r:
            raise HTTPException(404, "Campeonato no encontrado")
        return {**(c or {"id": camp_id}), **(dict(r[0]) if r else {})}

    @app.get("/api/version")
    def version():
        return {"version": __version__}

    @app.get("/api/preferencias")
    def preferencias():
        return {"barco": alm.preferencia("barco", BARCO_POR_DEFECTO)}

    @app.put("/api/preferencias")
    def fijar(p: Preferencias):
        alm.fijar_preferencia("barco", p.barco)
        return {"barco": p.barco}

    # Web compilada (frontend/ → fasttack/web). Cualquier otra ruta devuelve la aplicación.
    if (WEB / "assets").exists():
        app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")

    @app.get("/{resto:path}", include_in_schema=False)
    def web(resto: str):
        if resto.startswith("api/"):
            raise HTTPException(404, "Ruta de la API desconocida")
        f = (WEB / resto).resolve()
        if resto and f.is_file() and WEB in f.parents:
            # assets/ lleva el hash en el nombre: se puede guardar para siempre
            cache = "public, max-age=31536000, immutable" if "assets" in f.parts else "no-cache"
            return FileResponse(f, headers={"Cache-Control": cache})
        if (WEB / "index.html").exists():
            # la página se revalida siempre: así una versión nueva se ve al recargar
            return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-cache"})
        raise HTTPException(404, "La web no está compilada: ejecuta `npm run build` en frontend/.")

    return app
