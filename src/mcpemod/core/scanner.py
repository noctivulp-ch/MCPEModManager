"""Observador de directorios: mods instalados y carpeta de descargas."""

from __future__ import annotations

import zipfile
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QObject, Signal

from .mod import Mod, TipoArchivo
from .rutas import DESCARGAS_DIR, DIRECTORIOS_INSTALACION, EXTENSIONES_SOPORTADAS, MODS_DIR
from .store import Store
from .version import detectar_version, nombre_canonico


class Scanner(QObject):
    mods_cambiados = Signal()
    descargas_cambiadas = Signal()

    def __init__(self, store: Store, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._store = store
        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._al_cambiar_directorio)
        for ruta in (*DIRECTORIOS_INSTALACION, DESCARGAS_DIR):
            self._observar(ruta)

    def _observar(self, ruta: Path) -> None:
        if not ruta.is_dir():
            return
        if str(ruta) not in self._watcher.directories():
            self._watcher.addPath(str(ruta))

    def _al_cambiar_directorio(self, ruta: str) -> None:
        # Qt deja de observar un directorio si desaparece; al recrearse (lo que
        # pasa al vaciar y rehacer `mods/`) hay que volver a engancharlo o el
        # panel se queda congelado sin avisar.
        self._observar(Path(ruta))

        if ruta == str(DESCARGAS_DIR):
            self.descargas_cambiadas.emit()
        else:
            self.mods_cambiados.emit()

    def notificar_cambio(self) -> None:
        """Fuerza el refresco de los paneles tras una acción de la propia app.

        El watcher tarda en reaccionar y no cubre lo que se escribe fuera de los
        directorios observados; sin esto, instalar deja la vista desactualizada.
        """
        self.mods_cambiados.emit()
        self.descargas_cambiadas.emit()

    # ── Lecturas ──────────────────────────────────────────────────────────────

    def leer_instalados(self) -> list[Mod]:
        """Lo que hay puesto: lo que registró el gestor más los `.so` sueltos.

        Un `.so` copiado a mano a `mods/` es un mod instalado aunque el gestor no
        lo haya puesto — ignorarlo haría que la lista mintiera.
        """
        resultado: list[Mod] = []
        conocidos: set[str] = set()

        for mod in self._store.mods_instalados():
            if not any(r.exists() for r in mod.rutas):
                # Borrado por fuera de la app: la base deja de reflejar el disco.
                self._store.eliminar_mod(mod.archivo)
                continue
            resultado.append(mod)
            conocidos.update(r.name for r in mod.rutas)

        if MODS_DIR.is_dir():
            for archivo in sorted(MODS_DIR.iterdir()):
                if archivo.suffix.lower() != ".so" or archivo.name in conocidos:
                    continue
                resultado.append(Mod(
                    nombre=archivo.stem,
                    canonico=nombre_canonico(archivo.stem),
                    archivo=archivo.name,
                    rutas=[archivo],
                    tipo=TipoArchivo.SO,
                    version=detectar_version(archivo),
                    hash_sha256=Mod.calcular_hash(archivo),
                    instalado=True,
                ))

        resultado.sort(key=lambda m: m.nombre.lower())
        return resultado

    def leer_descargas(self) -> list[Mod]:
        resultado: list[Mod] = []
        if not DESCARGAS_DIR.is_dir():
            return resultado

        for archivo in sorted(DESCARGAS_DIR.iterdir()):
            if not archivo.is_file() or archivo.suffix.lower() not in EXTENSIONES_SOPORTADAS:
                continue
            if _descarga_incompleta(archivo):
                continue
            try:
                hash_sha256 = Mod.calcular_hash(archivo)
            except OSError:
                continue

            resultado.append(Mod(
                nombre=archivo.stem,
                canonico=nombre_canonico(archivo.stem),
                archivo=archivo.name,
                rutas=[archivo],
                tipo=TipoArchivo.desde_ruta(archivo),
                version=detectar_version(archivo),
                hash_sha256=hash_sha256,
                instalado=False,
                primera_vez=self._store.es_nuevo(hash_sha256),
            ))

        return resultado

    def marcar_vistas(self, mods: list[Mod]) -> None:
        for mod in mods:
            if mod.primera_vez:
                self._store.marcar_visto(mod.hash_sha256)


def _descarga_incompleta(archivo: Path) -> bool:
    """Un zip que aún se está descargando existe pero no se puede abrir.

    Sin este filtro la lista muestra archivos a medias y instalarlos falla con un
    error de zip corrupto que no dice nada sobre la causa real.
    """
    if archivo.suffix.lower() == ".so":
        return archivo.stat().st_size == 0
    return not zipfile.is_zipfile(archivo)
