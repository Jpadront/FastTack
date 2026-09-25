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
    ap = argparse.ArgumentParser(prog="fasttack", description="Análisis de regatas J/70 con datos de RaceSense")
    ap.add_argument("--puerto", type=int, default=8000)
    ap.add_argument("--solo-este-ordenador", action="store_true", help="no aceptar conexiones de la Wi-Fi")
    a = ap.parse_args()

    import uvicorn

    from .api.app import crear_app

    host = "127.0.0.1" if a.solo_este_ordenador else "0.0.0.0"
    print(f"\n  FastTack en este ordenador:  http://localhost:{a.puerto}")
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
    print("  Para parar: Ctrl+C\n")
    uvicorn.run(crear_app(), host=host, port=a.puerto, log_level="warning")


if __name__ == "__main__":
    main()
