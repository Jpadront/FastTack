"""API HTTP de FastTack y servidor de la web compilada."""
from __future__ import annotations

import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..ingesta import campeonato as camp_mod
from ..ingesta import propios as propios_mod
from ..ingesta import sesion as sesion_mod
from ..ingesta.vkx import ErrorVKX
from ..ingesta.almacen import Almacen
from ..ingesta.campeonato import DivisionAmbigua, elegir_division
from ..ingesta.racesense import ErrorRaceSense
from ..ingesta.url import UrlNoValida, leer_url
from .. import __version__, servicio, temporada as temporada_mod
from ..ia import debrief

WEB = Path(__file__).resolve().parent.parent / "web"
BARCO_POR_DEFECTO = "ESP1214"


class PeticionCarga(BaseModel):
    url: str
    division: str | None = None


class PeticionDebrief(BaseModel):
    ambito: str                 # 'campeonato' o la clave de la prueba
    barco: str                  # clave de la vela (ESP1214)
    texto: str | None = None    # si viene, es la respuesta pegada a mano (no se llama a la IA)


class AjustePrueba(BaseModel):
    reglaje: dict[str, str] | None = None   # lo que se llevaba: {«Obenques altos»: «14», …}
    numero: int | None = None
    excluida: bool | None = None
    viento_kn: float | None = None
    viento_dir: float | None = None


class PeticionSesion(BaseModel):
    nombre: str
    clase: str | None = None
    zona: str | None = None     # zona horaria del navegador (Europe/Madrid) para las horas locales


MAX_VKX = 200 * 1024 * 1024


class CambioCampeonato(BaseModel):
    nombre: str | None = None   # vacío = volver al nombre original


class Preferencias(BaseModel):
    barco: str


def crear_app(alm: Almacen | None = None) -> FastAPI:
    alm = alm or Almacen()
    app = FastAPI(title="FastTack", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.add_middleware(GZipMiddleware, minimum_size=2000)
    tareas: dict[str, dict] = {}  # carga en curso por campeonato
    generando: dict[tuple, dict] = {}  # debriefs que se están generando (campeonato, ámbito, barco)

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

    # ------------------------------------------------------------------ sesiones propias (.vkx)
    @app.post("/api/sesiones", status_code=201)
    def crear_sesion(p: PeticionSesion):
        return sesion_mod.crear(alm, p.nombre, p.clase, p.zona)

    @app.post("/api/sesiones/{sid}/vkx")
    async def subir_vkx(sid: str, request: Request, vela: str, nombre: str = "", archivo: str = ""):
        datos = await request.body()
        if not datos:
            raise HTTPException(422, "El archivo está vacío.")
        if len(datos) > MAX_VKX:
            raise HTTPException(413, "El archivo es demasiado grande.")
        try:
            return sesion_mod.añadir_vkx(alm, sid, datos, vela, nombre, archivo)
        except KeyError as e:
            raise HTTPException(404, "Sesión no encontrada") from e
        except (ErrorVKX, ValueError) as e:
            raise HTTPException(422, str(e)) from e

    @app.delete("/api/sesiones/{sid}/vkx/{n}")
    def quitar_vkx(sid: str, n: int):
        try:
            return sesion_mod.quitar_archivo(alm, sid, n)
        except KeyError as e:
            raise HTTPException(404, "Sesión no encontrada") from e

    @app.post("/api/sesiones/{sid}/reconstruir")
    def reconstruir_sesion(sid: str):
        try:
            return sesion_mod.reconstruir(alm, sid)
        except KeyError as e:
            raise HTTPException(404, "Sesión no encontrada") from e

    # ------------------------------------------------------------------ .vkx propios en un campeonato de RaceSense
    @app.post("/api/campeonatos/{camp_id:path}/vkx")
    async def subir_vkx_campeonato(camp_id: str, request: Request, vela: str, archivo: str = ""):
        camp = camp_mod.leer(alm, camp_id)
        if camp is None:
            raise HTTPException(404, "Campeonato no encontrado")
        datos = await request.body()
        if not datos or len(datos) > MAX_VKX:
            raise HTTPException(422, "Archivo vacío o demasiado grande.")
        try:
            return propios_mod.añadir(alm, camp, datos, vela, archivo)
        except (ErrorVKX, ValueError) as e:
            raise HTTPException(422, str(e)) from e

    @app.delete("/api/campeonatos/{camp_id:path}/vkx/{n}")
    def quitar_vkx_campeonato(camp_id: str, n: int):
        camp = camp_mod.leer(alm, camp_id)
        if camp is None:
            raise HTTPException(404, "Campeonato no encontrado")
        return propios_mod.quitar(alm, camp, n)

    @app.get("/api/campeonatos")
    def lista():
        return [dict(r) for r in alm.sql(
            "select id, coalesce(nullif(alias, ''), nombre) as nombre, nombre as nombre_original, clase, division, "
            "inicio, fin, estado, progreso, error, cargado_en from campeonato order by coalesce(inicio, 0) desc")]

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
        if "reglaje" in cambios:
            import json as _json
            r = {k.strip(): v.strip() for k, v in (cambios["reglaje"] or {}).items() if k.strip() and v.strip()}
            cambios["reglaje"] = _json.dumps(r, ensure_ascii=False) if r else None
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

    @app.get("/api/campeonatos/{camp_id:path}/pruebas/{clave}/meteo")
    def meteo_(camp_id: str, clave: str):
        from ..ingesta.meteo import ErrorMeteo
        try:
            return servicio.meteo_prueba(alm, camp_id, clave)
        except KeyError as e:
            raise HTTPException(404, "Prueba no encontrada") from e
        except servicio.PruebaNoAnalizable as e:
            raise HTTPException(422, str(e)) from e
        except ErrorMeteo as e:
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

    @app.get("/api/campeonatos/{camp_id:path}/resumen")
    def resumen_(camp_id: str, descartes: int | None = None):
        try:
            return servicio.resumen_campeonato(alm, camp_id, descartes)
        except KeyError as e:
            raise HTTPException(404, "Campeonato no encontrado") from e

    @app.get("/api/campeonatos/{camp_id:path}/debrief")
    def debrief_(camp_id: str, ambito: str, barco: str):
        datos = _datos_debrief(camp_id, ambito, barco)
        d = debrief.leer(alm, camp_id, ambito, barco)
        if d:  # se vuelve a comprobar con las cifras actuales (es inmediato)
            d["avisos"] = debrief.no_verificadas(d["texto"], datos)
        g = generando.get((camp_id, ambito, barco), {})
        return {"debrief": d, "vigente": bool(d and d["huella"] == debrief.huella(datos)),
                "instrucciones": debrief.instrucciones(datos), "claude_code": bool(debrief.comando_claude()),
                "generando": g.get("estado") == "generando", "error": g.get("error")}

    @app.post("/api/campeonatos/{camp_id:path}/debrief")
    def generar_debrief(camp_id: str, p: PeticionDebrief):
        datos = _datos_debrief(camp_id, p.ambito, p.barco)
        if p.texto is not None:
            if not p.texto.strip():
                raise HTTPException(422, "El texto está vacío")
            return debrief.guardar(alm, camp_id, p.ambito, p.barco, datos, p.texto, "manual")
        if not debrief.comando_claude():
            raise HTTPException(503, "Claude Code no está instalado en este ordenador (comando «claude»).")
        # En segundo plano: tarda 30–100 s y, publicado con Cloudflare, una petición no puede pasar de 100 s.
        # La web consulta el estado (GET) hasta que termina.
        clave_g = (camp_id, p.ambito, p.barco)
        if generando.get(clave_g, {}).get("estado") == "generando":
            return {"generando": True}
        generando[clave_g] = {"estado": "generando"}

        def trabajo():
            try:
                texto = debrief.generar_claude_code(debrief.instrucciones(datos))
                debrief.guardar(alm, camp_id, p.ambito, p.barco, datos, texto, "claude-code")
                generando[clave_g] = {"estado": "hecho"}
            except Exception as e:  # noqa: BLE001 - el error se enseña en la web
                generando[clave_g] = {"estado": "error", "error": str(e)}
        threading.Thread(target=trabajo, daemon=True).start()
        return {"generando": True}

    def _datos_debrief(camp_id: str, ambito: str, barco: str) -> dict:
        try:
            return debrief.datos_de(alm, camp_id, ambito, barco)
        except KeyError as e:
            raise HTTPException(404, "Campeonato o prueba no encontrados") from e
        except (ValueError, servicio.PruebaNoAnalizable) as e:
            raise HTTPException(422, str(e)) from e

    @app.get("/api/campeonatos/{camp_id:path}")
    def detalle(camp_id: str):
        c = camp_mod.leer(alm, camp_id)
        r = alm.sql("select estado, progreso, error, url, alias from campeonato where id=?", (camp_id,))
        if not c and not r:
            raise HTTPException(404, "Campeonato no encontrado")
        extra = dict(r[0]) if r else {}
        alias = extra.pop("alias", None)
        out = {**(c or {"id": camp_id}), **extra}
        if c and not sesion_mod.es_sesion(camp_id):
            out["propios"] = propios_mod.lista(alm, c)
        if alias:
            out["nombre_original"], out["nombre"] = out.get("nombre"), alias
        return out

    @app.patch("/api/campeonatos/{camp_id:path}")
    def renombrar(camp_id: str, p: CambioCampeonato):
        if not alm.sql("select 1 from campeonato where id=?", (camp_id,)):
            raise HTTPException(404, "Campeonato no encontrado")
        alm.sql("update campeonato set alias=? where id=?", ((p.nombre or "").strip() or None, camp_id))
        return detalle(camp_id)

    @app.delete("/api/campeonatos/{camp_id:path}")
    def eliminar(camp_id: str):
        """Lo quita de la lista con sus ajustes y debriefs. Los archivos .vkx de una sesión se borran;
        la telemetría ya descargada de RaceSense se conserva (si se vuelve a cargar, no se descarga otra vez)."""
        if camp_id in tareas:
            raise HTTPException(409, "Se está cargando: espera a que termine.")
        if not alm.sql("select 1 from campeonato where id=?", (camp_id,)):
            raise HTTPException(404, "Campeonato no encontrado")
        for tabla in ("ajuste_prueba", "debrief"):
            alm.sql(f"delete from {tabla} where campeonato=?", (camp_id,))
        alm.sql("delete from campeonato where id=?", (camp_id,))
        if sesion_mod.es_sesion(camp_id):
            import shutil
            shutil.rmtree(alm.ruta(camp_id), ignore_errors=True)
        return {"eliminado": camp_id}

    @app.get("/api/temporada")
    def temporada(barco: str | None = None):
        return temporada_mod.temporada(alm, barco or alm.preferencia("barco", BARCO_POR_DEFECTO))

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
