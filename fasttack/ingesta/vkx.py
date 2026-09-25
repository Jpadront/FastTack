"""Lector de archivos .vkx (registro interno del Vakaros Atlas 2).

Formato binario little-endian: una sucesión de filas «clave (1 byte) + carga de longitud fija».
Las filas se agrupan en páginas (0xFF cabecera … 0xFE terminador). Solo se aceptan las claves
comprobadas con archivos reales; una clave desconocida detiene la lectura con un error claro en
lugar de desalinear el resto del archivo.

    0x02 posición, velocidad y orientación: ts u64 (ms UTC), lat i32 (1e-7 °), lon i32 (1e-7 °),
         SOG f32 (m/s), COG f32 (rad), altitud f32 (m), cuaternión w, x, y, z f32
    0x03 declinación: ts, declinación f32 (rad), lat i32, lon i32
    0x04 evento del cronómetro de salida: ts, tipo u8 (0 reinicio, 1 arranque, 2 sincronización,
         3 salida, 4 fin), valor i32 (s)
    0x05 ping de la línea de salida: ts, extremo u8 (0 pin, 1 comité), lat f32, lon f32
    0x07, 0x08, 0x0E: estado interno del dispositivo (se ignoran)
"""
from __future__ import annotations

import struct

import numpy as np

from .racesense import COLUMNAS

LONGITUD = {0xFF: 7, 0xFE: 2, 0x02: 44, 0x03: 20, 0x04: 13, 0x05: 17, 0x07: 12, 0x08: 13, 0x0E: 16}
MS_A_KN = 3600 / 1852
EVENTOS = {0: "reinicio", 1: "arranque", 2: "sincronizacion", 3: "salida", 4: "fin"}


class ErrorVKX(ValueError):
    pass


def leer(datos: bytes) -> dict:
    """{'posiciones': array (n, 13), 'eventos': [(ts, tipo, valor)], 'linea': [(ts, extremo, lat, lon)],
    'declinacion_grados': float | None}"""
    pos, eventos, linea, decl = [], [], [], None
    i, n = 0, len(datos)
    while i < n:
        k = datos[i]
        largo = LONGITUD.get(k)
        if largo is None:
            raise ErrorVKX(f"Registro de tipo 0x{k:02X} no reconocido (byte {i}); el archivo no se puede leer entero.")
        if i + 1 + largo > n:
            break   # última fila cortada (el Atlas se apagó escribiendo)
        p = datos[i + 1:i + 1 + largo]
        if k == 0x02:
            pos.append(struct.unpack("<Qiifff4f", p))
        elif k == 0x04:
            eventos.append(struct.unpack("<QBi", p))
        elif k == 0x05:
            linea.append(struct.unpack("<QBff", p))
        elif k == 0x03 and decl is None:
            decl = float(np.degrees(struct.unpack("<Qfii", p)[1]))
        i += 1 + largo
    if not pos:
        raise ErrorVKX("El archivo no tiene posiciones.")
    return {"posiciones": np.array(pos, dtype=np.float64), "eventos": eventos, "linea": linea,
            "declinacion_grados": decl}


def orientacion(q: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(rumbo, escora, cabeceo) en grados desde el cuaternión (w, x, y, z).
    Escora + = a estribor, como en RaceSense; rumbo 0–360."""
    w, x, y, z = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
    roll = np.degrees(np.arctan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y)))
    pitch = np.degrees(np.arcsin(np.clip(2 * (w * y - z * x), -1, 1)))
    yaw = np.degrees(np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))) % 360
    return yaw, roll, pitch


def a_columnas(reg: dict, vela: str, sn: int = 0, division: str = "") -> dict[str, np.ndarray]:
    """Las posiciones del archivo en el formato de columnas de la telemetría de RaceSense."""
    p = reg["posiciones"]
    p = p[np.argsort(p[:, 0], kind="stable")]
    _, u = np.unique(p[:, 0], return_index=True)
    p = p[u]
    p = p[(p[:, 1] != 0) | (p[:, 2] != 0)]          # sin posición GPS
    hdg, roll, pitch = orientacion(p[:, 6:10])
    m = len(p)
    cols = {
        "ts": p[:, 0].astype(np.int64), "sn": np.full(m, sn, np.int32),
        "division": np.full(m, division, dtype=object), "sail_number": np.full(m, vela, dtype=object),
        "race_number": np.zeros(m, np.int16), "start_number": np.zeros(m, np.int16),
        "race_stage": np.full(m, "", dtype=object), "role": np.full(m, "competitor", dtype=object),
        "latitude": p[:, 1] / 1e7, "longitude": p[:, 2] / 1e7,
        "pitch": pitch.astype(np.float32), "roll": roll.astype(np.float32),
        "heading": hdg.astype(np.float32), "sog": (p[:, 3] * MS_A_KN).astype(np.float32),
        "status": np.zeros(m, np.int16),
    }
    return {c: cols[c].astype(t) if t is not object else cols[c] for c, t in COLUMNAS.items()}


def salidas(reg: dict) -> list[int]:
    """Horas (ms) de las salidas marcadas por el cronómetro del Atlas (evento «salida»)."""
    return sorted(int(t) for t, tipo, _ in reg["eventos"] if tipo == 3)
