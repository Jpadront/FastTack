"""Configuración: carpeta de datos, identificación ante RaceSense y ritmo de peticiones."""
from __future__ import annotations

import os
from pathlib import Path

# Carpeta de datos (caché de RaceSense y estado de la app). Se puede cambiar con FASTTACK_DATOS.
DATOS = Path(os.environ.get("FASTTACK_DATOS", Path(__file__).resolve().parent.parent / "datos"))

PLAYER = "https://player.vakaros.com"
TELE = "https://teleapi.regatta.app"
USER_AGENT = "FastTack/0.1 (analisis interno de un equipo de J/70)"  # solo ASCII en cabeceras HTTP
PAUSA_S = float(os.environ.get("FASTTACK_PAUSA_S", "1.0"))  # entre peticiones a RaceSense
LIMITE_FILAS = 100_000  # máximo que admite /telemetry/event por petición

# Una ventana de telemetría que termina hace menos de esto puede estar incompleta (evento en
# directo): se descarga, pero no se marca como definitiva en la caché.
MARGEN_DIRECTO_MS = 2 * 3600_000
