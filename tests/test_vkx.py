import struct

import numpy as np
import pytest

from fasttack.ingesta import vkx


def _cuaternion(escora, rumbo):
    """Cuaternión (w, x, y, z) de una rotación rumbo (z) · escora (x)."""
    r, y = np.radians(escora) / 2, np.radians(rumbo) / 2
    return (np.cos(y) * np.cos(r), np.cos(y) * np.sin(r), np.sin(y) * np.sin(r), np.sin(y) * np.cos(r))


def _archivo():
    b = bytes([0xFF]) + bytes(7)
    b += bytes([0x04]) + struct.pack("<QBi", 1_000_000, 3, 0)
    b += bytes([0x05]) + struct.pack("<QBff", 999_000, 0, 41.37, 2.21)
    for k in range(3):
        b += bytes([0x02]) + struct.pack("<Qiifff4f", 1_000_000 + 500 * k, 413_700_000, 22_100_000 + k,
                                         2.0, 1.0, 0.0, *_cuaternion(-12.0, 55.0))
    b += bytes([0x07]) + bytes(12) + bytes([0xFE]) + bytes(2)
    return b


def test_lee_posiciones_y_eventos():
    reg = vkx.leer(_archivo())
    assert vkx.salidas(reg) == [1_000_000]
    assert reg["linea"][0][1] == 0
    c = vkx.a_columnas(reg, "ESP 1214")
    assert len(c["ts"]) == 3 and c["sail_number"][0] == "ESP 1214"
    assert c["latitude"][0] == pytest.approx(41.37)
    assert c["sog"][0] == pytest.approx(2.0 * 3600 / 1852, rel=1e-5)
    assert c["roll"][0] == pytest.approx(-12.0, abs=0.01)    # escora a babor
    assert c["heading"][0] == pytest.approx(55.0, abs=0.01)


def test_clave_desconocida():
    with pytest.raises(vkx.ErrorVKX):
        vkx.leer(_archivo() + bytes([0x99]) + bytes(20))


def test_fila_final_cortada():
    assert len(vkx.leer(_archivo() + bytes([0x02]) + bytes(10))["posiciones"]) == 3


def test_mezclar_archivo_propio_en_campeonato(tmp_path):
    """El archivo propio sustituye a RaceSense para ese barco solo en el tiempo que cubre."""
    import json
    import pyarrow as pa
    import pyarrow.parquet as pq
    from fasttack.ingesta.propios import mezclar
    from fasttack.ingesta.racesense import COLUMNAS

    def filas(vela, ts, sn, rol="competitor"):
        n = len(ts)
        base = {c: np.zeros(n, t) if t is not object else np.full(n, "", dtype=object) for c, t in COLUMNAS.items()}
        base.update({"ts": np.array(ts, np.int64), "sn": np.full(n, sn, np.int32), "sail_number": np.full(n, vela, dtype=object),
                     "role": np.full(n, rol, dtype=object), "latitude": np.full(n, 41.0), "longitude": np.full(n, 2.0)})
        return base
    rs = {c: np.concatenate([a[c], b[c]]) for c in COLUMNAS
          for a, b in [(filas("ESP 1214", [0, 10_000, 20_000, 30_000], 1), filas("ITA 1", [0, 10_000, 20_000, 30_000], 2))]}
    propio = filas("ESP 1214", [8_000, 9_000, 10_000, 11_000, 12_000], 60_001)
    pq.write_table(pa.table({c: propio[c] for c in COLUMNAS}), tmp_path / "tel_propio_1.parquet")
    (tmp_path / "propios.json").write_text(json.dumps([{"n": 1, "clave": "ESP1214", "desde": 8_000, "hasta": 12_000}]))
    out = mezclar(tmp_path, rs, 0, 30_000)
    esp = out["ts"][out["sail_number"] == "ESP 1214"].tolist()
    assert esp == [0, 8_000, 9_000, 10_000, 11_000, 12_000, 20_000, 30_000]   # la muestra de RaceSense a 10 s se sustituye
    assert (out["sail_number"] == "ITA 1").sum() == 4                          # el resto de la flota no cambia
    assert list(out["ts"]) == sorted(out["ts"])
