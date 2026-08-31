"""Persistencia SQLite: historial de cambios y archivos ya vistos.

El estado de lo instalado **no** se guarda aquí: la fuente de verdad es el disco,
porque el jugador instala packs desde el propio juego sin pasar por el gestor.
La base guarda lo que el disco no sabe — qué pasó y cuándo, y de qué archivo
salió cada pack.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .mod import EntradaHistorial

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS historial (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    accion           TEXT NOT NULL,
    uuid             TEXT NOT NULL DEFAULT '',
    nombre           TEXT NOT NULL,
    categoria        TEXT NOT NULL DEFAULT '',
    version          TEXT,
    version_anterior TEXT,
    timestamp        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS origenes (
    uuid         TEXT PRIMARY KEY,
    archivo      TEXT NOT NULL,
    instalado_en TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vistos (
    hash TEXT PRIMARY KEY
);
"""


class Store:
    def __init__(self, ruta_db: Path) -> None:
        ruta_db.parent.mkdir(parents=True, exist_ok=True)
        self._db = ruta_db
        with self._cx() as cx:
            _descartar_esquema_v1(cx)
            cx.executescript(_ESQUEMA)

    @contextmanager
    def _cx(self):
        con = sqlite3.connect(self._db)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()

    # ── Origen de cada pack ───────────────────────────────────────────────────

    def registrar_origen(self, uuid: str, archivo: str) -> None:
        with self._cx() as cx:
            cx.execute(
                """INSERT INTO origenes (uuid, archivo, instalado_en) VALUES (?, ?, ?)
                   ON CONFLICT(uuid) DO UPDATE SET
                       archivo=excluded.archivo, instalado_en=excluded.instalado_en""",
                (uuid, archivo, datetime.now().isoformat()),
            )

    def olvidar_origen(self, uuid: str) -> None:
        with self._cx() as cx:
            cx.execute("DELETE FROM origenes WHERE uuid = ?", (uuid,))

    def origenes(self) -> dict[str, tuple[str, datetime]]:
        with self._cx() as cx:
            filas = cx.execute("SELECT * FROM origenes").fetchall()
        return {
            f["uuid"]: (f["archivo"], datetime.fromisoformat(f["instalado_en"]))
            for f in filas
        }

    # ── Historial ─────────────────────────────────────────────────────────────

    def registrar(self, entrada: EntradaHistorial) -> None:
        with self._cx() as cx:
            cx.execute(
                """INSERT INTO historial (accion, uuid, nombre, categoria, version,
                                          version_anterior, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    entrada.accion, entrada.uuid, entrada.nombre, entrada.categoria,
                    entrada.version, entrada.version_anterior,
                    entrada.timestamp.isoformat(),
                ),
            )

    def historial(self, limite: int = 200) -> list[EntradaHistorial]:
        with self._cx() as cx:
            filas = cx.execute(
                "SELECT * FROM historial ORDER BY timestamp DESC, id DESC LIMIT ?", (limite,)
            ).fetchall()
        return [
            EntradaHistorial(
                id=f["id"], accion=f["accion"], uuid=f["uuid"], nombre=f["nombre"],
                categoria=f["categoria"], version=f["version"],
                version_anterior=f["version_anterior"],
                timestamp=datetime.fromisoformat(f["timestamp"]),
            )
            for f in filas
        ]

    # ── Archivos vistos (badge NEW) ───────────────────────────────────────────

    def marcar_visto(self, hash_sha256: str) -> None:
        with self._cx() as cx:
            cx.execute("INSERT OR IGNORE INTO vistos (hash) VALUES (?)", (hash_sha256,))

    def es_nuevo(self, hash_sha256: str) -> bool:
        with self._cx() as cx:
            fila = cx.execute("SELECT 1 FROM vistos WHERE hash = ?", (hash_sha256,)).fetchone()
        return fila is None


def _descartar_esquema_v1(cx: sqlite3.Connection) -> None:
    """La tabla `mods` de la primera versión indexaba por nombre de archivo.

    No se migra: registraba packs por el nombre del `.so` o del archivo
    descargado, y la identidad correcta —el uuid del manifiesto— no está ahí ni
    se puede deducir. El historial de aquella versión tampoco lo tiene, así que
    se conserva tal cual y las columnas nuevas quedan vacías para esas filas.
    """
    tabla = cx.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='mods'"
    ).fetchone()
    if tabla is not None:
        cx.execute("DROP TABLE mods")

    columnas = {
        f["name"]
        for f in cx.execute("PRAGMA table_info(historial)").fetchall()
    }
    if columnas and "nombre" not in columnas:
        cx.execute("ALTER TABLE historial RENAME COLUMN archivo TO nombre")
        cx.execute("ALTER TABLE historial ADD COLUMN uuid TEXT NOT NULL DEFAULT ''")
        cx.execute("ALTER TABLE historial ADD COLUMN categoria TEXT NOT NULL DEFAULT ''")
