"""Arranque en un solo comando: `uv run fasttack`.

Sirve la app en el puerto 8000 para este ordenador y para los dispositivos de la misma Wi-Fi,
e imprime la dirección y un QR para abrirla desde el móvil.
"""
from __future__ import annotations

import argparse
import socket


def ip_local() -> str | None:
    """IP de este ordenador en la red local (sin enviar nada: UDP no conecta de verdad)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 80))
            return s.getsockname()[0]
    except OSError:
        return None


def main():
    ap = argparse.ArgumentParser(prog="fasttack", description="Análisis de regatas con datos de RaceSense")
    ap.add_argument("--puerto", type=int, default=8000)
    ap.add_argument("--solo-este-ordenador", action="store_true", help="no aceptar conexiones de la Wi-Fi")
    ap.add_argument("--tunel", metavar="NOMBRE", nargs="?", const="fasttack",
                    help="publicar en internet con un túnel de Cloudflare ya creado (ver docs/publicar.md)")
    ap.add_argument("--direccion", metavar="URL", help="dirección pública del túnel, para mostrarla al arrancar")
    a = ap.parse_args()
    if a.tunel:
        a.solo_este_ordenador = True   # con túnel, solo se entra por Cloudflare (con su control de acceso)

    import uvicorn

    from . import __version__
    from .api.app import crear_app

    host = "127.0.0.1" if a.solo_este_ordenador else "0.0.0.0"
    print(f"\n  FastTack {__version__}")
    print(f"  En este ordenador:  http://localhost:{a.puerto}")
    ip = None if a.solo_este_ordenador else ip_local()
    if ip:
        url = f"http://{ip}:{a.puerto}"
        print(f"  Desde el móvil (misma Wi-Fi): {url}\n")
        try:
            import qrcode
            q = qrcode.QRCode(border=1)
            q.add_data(url)
            q.print_ascii(invert=True)
        except Exception:  # noqa: BLE001 - el QR es una comodidad
            pass
    tunel = None
    if a.tunel:
        tunel = _arrancar_tunel(a.tunel, a.puerto)
        if tunel and a.direccion:
            print(f"  En internet (con acceso restringido): {a.direccion}")
    print("  Para parar: Ctrl+C\n")
    try:
        uvicorn.run(crear_app(), host=host, port=a.puerto, log_level="warning")
    finally:
        if tunel:
            tunel.terminate()


def _arrancar_tunel(nombre: str, puerto: int):
    """Lanza `cloudflared tunnel run` hacia FastTack. None si cloudflared no está instalado."""
    import shutil
    import subprocess
    exe = shutil.which("cloudflared")
    if not exe:
        print("  ⚠ No encuentro «cloudflared»: instálalo (docs/publicar.md). Sigo sin túnel.")
        return None
    print(f"  Túnel de Cloudflare «{nombre}» en marcha (registro en ~/.cloudflared/fasttack.log)")
    import pathlib
    log = pathlib.Path.home() / ".cloudflared" / "fasttack.log"
    log.parent.mkdir(exist_ok=True)
    return subprocess.Popen([exe, "tunnel", "--no-autoupdate", "run", "--url", f"http://localhost:{puerto}", nombre],
                            stdout=open(log, "a"), stderr=subprocess.STDOUT)


if __name__ == "__main__":
    main()
