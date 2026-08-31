"""Persistencia SQLite: mods instalados e historial de cambios."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .mod import EntradaHistorial, Mod, TipoArchivo

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS mods (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre       TEXT NOT NULL,
    canonico     TEXT NOT NULL,
    archivo      TEXT NOT NULL UNIQUE,
    tipo         TEXT NOT NULL,
    version      TEXT,
    hash         TEXT NOT NULL,
    rutas        TEXT NOT NULL,
    instalado_en TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mods_canonico ON mods (canonico);

CREATE TABLE IF NOT EXISTS historial (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    accion           TEXT NOT NULL,
    archivo          TEXT NOT NULL,
    version          TEXT,
    version_anterior TEXT,
    timestamp        TEXT NOT NULL
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
            _migrar(cx)
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

    # ── Mods instalados ───────────────────────────────────────────────────────

    def guardar_mod(self, mod: Mod) -> None:
        with self._cx() as cx:
            cx.execute(
                """INSERT INTO mods (nombre, canonico, archivo, tipo, version, hash, rutas, instalado_en)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(archivo) DO UPDATE SET
                       nombre=excluded.nombre,
                       canonico=excluded.canonico,
                       version=excluded.version,
                       hash=excluded.hash,
                       rutas=excluded.rutas,
                       instalado_en=excluded.instalado_en""",
                (
                    mod.nombre,
                    mod.canonico,
                    mod.archivo,
                    mod.tipo.value,
                    mod.version,
                    mod.hash_sha256,
                    json.dumps([str(r) for r in mod.rutas]),
                    (mod.instalado_en or datetime.now()).isoformat(),
                ),
            )

    def eliminar_mod(self, archivo: str) -> None:
        with self._cx() as cx:
            cx.execute("DELETE FROM mods WHERE archivo = ?", (archivo,))

    def mods_instalados(self) -> list[Mod]:
        with self._cx() as cx:
            filas = cx.execute("SELECT * FROM mods ORDER BY nombre COLLATE NOCASE").fetchall()
        return [_fila_a_mod(f) for f in filas]

    def buscar_por_canonico(self, canonico: str) -> Mod | None:
        """El mod instalado que es "el mismo" que uno nuevo, ignorando versión."""
        with self._cx() as cx:
            fila = cx.execute(
                "SELECT * FROM mods WHERE canonico = ? ORDER BY instalado_en DESC LIMIT 1",
                (canonico,),
            ).fetchone()
        return _fila_a_mod(fila) if fila else None

    def buscar_por_archivo(self, archivo: str) -> Mod | None:
        with self._cx() as cx:
            fila = cx.execute("SELECT * FROM mods WHERE archivo = ?", (archivo,)).fetchone()
        return _fila_a_mod(fila) if fila else None

    # ── Historial ─────────────────────────────────────────────────────────────

    def registrar(self, entrada: EntradaHistorial) -> None:
        with self._cx() as cx:
            cx.execute(
                """INSERT INTO historial (accion, archivo, version, version_anterior, timestamp)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    entrada.accion,
                    entrada.archivo,
                    entrada.version,
                    entrada.version_anterior,
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
                id=f["id"],
                accion=f["accion"],
                archivo=f["archivo"],
                version=f["version"],
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


def _fila_a_mod(fila: sqlite3.Row) -> Mod:
    return Mod(
        id=fila["id"],
        nombre=fila["nombre"],
        canonico=fila["canonico"],
        archivo=fila["archivo"],
        tipo=TipoArchivo(fila["tipo"]),
        version=fila["version"],
        hash_sha256=fila["hash"],
        rutas=[Path(r) for r in json.loads(fila["rutas"])],
        instalado=True,
        instalado_en=datetime.fromisoformat(fila["instalado_en"]),
    )


def _migrar(cx: sqlite3.Connection) -> None:
    """Lleva una base del esquema inicial (`ruta` única, sin `canonico`) al actual.

    La base vive en `~/.local/share/` y sobrevive a las reinstalaciones, así que
    no se puede asumir que empiece vacía.
    """
    tabla = cx.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='mods'"
    ).fetchone()
    if tabla is None:
        return

    columnas = {f["name"] for f in cx.execute("PRAGMA table_info(mods)").fetchall()}
    if "canonico" in columnas and "rutas" in columnas:
        return

    from .version import nombre_canonico

    filas = cx.execute("SELECT * FROM mods").fetchall()
    cx.execute("ALTER TABLE mods RENAME TO mods_v1")
    cx.executescript(_ESQUEMA)
    for f in filas:
        cx.execute(
            """INSERT OR IGNORE INTO mods
               (nombre, canonico, archivo, tipo, version, hash, rutas, instalado_en)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                f["nombre"],
                nombre_canonico(f["nombre"]),
                f["archivo"],
                f["tipo"],
                f["version"],
                f["hash"],
                json.dumps([f["ruta"]]),
                f["instalado_en"],
            ),
        )
    cx.execute("DROP TABLE mods_v1")
