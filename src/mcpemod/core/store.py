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

CREATE TABLE IF NOT EXISTS emparejamientos (
    uuid            TEXT PRIMARY KEY,
    encontrado      INTEGER NOT NULL,
    fuente          TEXT,
    id_publicacion  TEXT,
    titulo          TEXT,
    autor           TEXT,
    url_publicacion TEXT,
    confianza       TEXT,
    version_remota  TEXT,
    url_descarga    TEXT,
    nombre_archivo  TEXT,
    comprobado_en   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ajustes (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS carpetas (
    ruta       TEXT PRIMARY KEY,
    agregada_en TEXT NOT NULL
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

    # ── Carpetas vigiladas ────────────────────────────────────────────────────

    def carpetas(self) -> list[Path]:
        """Las carpetas donde se buscan descargas, en el orden en que se añadieron."""
        with self._cx() as cx:
            filas = cx.execute(
                "SELECT ruta FROM carpetas ORDER BY agregada_en, ruta"
            ).fetchall()
        return [Path(f["ruta"]) for f in filas]

    def agregar_carpeta(self, ruta: Path) -> None:
        with self._cx() as cx:
            cx.execute(
                "INSERT OR IGNORE INTO carpetas (ruta, agregada_en) VALUES (?, ?)",
                (str(ruta), datetime.now().isoformat()),
            )

    def quitar_carpeta(self, ruta: Path) -> bool:
        """Quita una carpeta salvo que sea la última.

        Quedarse sin ninguna dejaría la pestaña de descargas vacía para siempre y
        sin nada que pulsar para recuperarla.
        """
        with self._cx() as cx:
            total = cx.execute("SELECT COUNT(*) AS n FROM carpetas").fetchone()["n"]
            if total <= 1:
                return False
            cx.execute("DELETE FROM carpetas WHERE ruta = ?", (str(ruta),))
        return True

    def sembrar_carpetas(self, predeterminada: Path) -> None:
        """Deja al menos una carpeta vigilada.

        Se llama al arrancar: en la primera ejecución no hay ninguna, y si el
        usuario quitó todas menos una y esa desapareció del disco, vuelve la
        predeterminada en vez de dejar la lista muerta.
        """
        if not self.carpetas():
            self.agregar_carpeta(predeterminada)

    # ── Emparejamientos con los catálogos ─────────────────────────────────────

    def emparejamientos(self) -> dict[str, dict]:
        """Lo que ya se sabe de cada uuid, por uuid.

        Confirmar un emparejamiento cuesta media docena de peticiones, así que se
        guarda también el resultado negativo: un pack que no está en ningún
        catálogo no debe volver a buscarse en cada arranque.
        """
        with self._cx() as cx:
            filas = cx.execute("SELECT * FROM emparejamientos").fetchall()
        return {
            f["uuid"]: {
                **{k: f[k] for k in f.keys() if k != "comprobado_en"},
                "encontrado": bool(f["encontrado"]),
                "comprobado_en": datetime.fromisoformat(f["comprobado_en"]),
            }
            for f in filas
        }

    def guardar_emparejamiento(self, uuid: str, *, encontrado: bool, **datos) -> None:
        columnas = ("fuente", "id_publicacion", "titulo", "autor", "url_publicacion",
                    "confianza", "version_remota", "url_descarga", "nombre_archivo")
        with self._cx() as cx:
            cx.execute(
                f"""INSERT INTO emparejamientos
                    (uuid, encontrado, {", ".join(columnas)}, comprobado_en)
                    VALUES (?, ?, {", ".join("?" * len(columnas))}, ?)
                    ON CONFLICT(uuid) DO UPDATE SET
                        encontrado=excluded.encontrado,
                        {", ".join(f"{c}=excluded.{c}" for c in columnas)},
                        comprobado_en=excluded.comprobado_en""",
                (uuid, int(encontrado), *(datos.get(c) for c in columnas),
                 datetime.now().isoformat()),
            )

    def olvidar_emparejamientos(self) -> None:
        with self._cx() as cx:
            cx.execute("DELETE FROM emparejamientos")

    # ── Ajustes ───────────────────────────────────────────────────────────────

    def ajuste(self, clave: str, por_defecto: str = "") -> str:
        with self._cx() as cx:
            fila = cx.execute("SELECT valor FROM ajustes WHERE clave = ?", (clave,)).fetchone()
        return fila["valor"] if fila else por_defecto

    def guardar_ajuste(self, clave: str, valor: str) -> None:
        with self._cx() as cx:
            cx.execute(
                """INSERT INTO ajustes (clave, valor) VALUES (?, ?)
                   ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor""",
                (clave, valor),
            )

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
