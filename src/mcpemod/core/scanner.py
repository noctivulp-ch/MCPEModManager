"""Estado del disco: qué hay instalado y qué hay en las carpetas vigiladas.

La fuente de verdad de lo instalado es el disco, no la base: el jugador importa
packs desde el propio juego sin pasar por el gestor, y una lista que no los
muestre miente. Se recorren las carpetas de la instalación activa leyendo cada
`manifest.json` para indexar por uuid.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QObject, Signal

from ..senales import conectar
from .contenido import Analisis, Categoria, analizar, categoria_de
from .manifiesto import ManifiestoInvalido, desde_carpeta, es_de_la_tienda
from .mod import Forma, Instalado, hash_archivo
from .rutas import Instalacion, carpeta_descargas
from .store import Store


class Scanner(QObject):
    instalados_cambiados = Signal()
    descargas_cambiadas = Signal()
    carpetas_cambiadas = Signal()

    def __init__(self, store: Store, instalacion: Instalacion, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._store = store
        self._instalacion = instalacion
        # Analizar un archivo abre su zip; con varias carpetas vigiladas eso se
        # repite en cada refresco. La clave incluye tamaño y mtime para que un
        # archivo reemplazado se vuelva a leer.
        self._cache: dict[tuple[str, int, int], Analisis | None] = {}
        self._watcher = QFileSystemWatcher(self)
        conectar(self._watcher.directoryChanged, self._al_cambiar_directorio)

        self._store.sembrar_carpetas(carpeta_descargas())
        self._reobservar()

    @property
    def instalacion(self) -> Instalacion:
        return self._instalacion

    def cambiar_instalacion(self, instalacion: Instalacion) -> None:
        self._instalacion = instalacion
        self._reobservar()
        self.notificar_cambio()

    # ── Carpetas vigiladas ────────────────────────────────────────────────────

    def carpetas(self) -> list[Path]:
        return self._store.carpetas()

    def agregar_carpeta(self, ruta: Path) -> None:
        self._store.agregar_carpeta(ruta.resolve())
        self._reobservar()
        self.carpetas_cambiadas.emit()
        self.descargas_cambiadas.emit()

    def quitar_carpeta(self, ruta: Path) -> bool:
        """Devuelve `False` si era la última: siempre queda una vigilada."""
        if not self._store.quitar_carpeta(ruta):
            return False
        self._reobservar()
        self.carpetas_cambiadas.emit()
        self.descargas_cambiadas.emit()
        return True

    # ── Observación ───────────────────────────────────────────────────────────

    def _reobservar(self) -> None:
        if self._watcher.directories():
            self._watcher.removePaths(self._watcher.directories())
        for ruta in (*self._instalacion.directorios_contenido, *self.carpetas()):
            if ruta.is_dir():
                self._watcher.addPath(str(ruta))

    def _al_cambiar_directorio(self, ruta: str) -> None:
        # Qt deja de observar un directorio si desaparece; al recrearse hay que
        # volver a engancharlo o el panel se queda congelado sin avisar.
        if Path(ruta).is_dir() and ruta not in self._watcher.directories():
            self._watcher.addPath(ruta)

        if Path(ruta) in self.carpetas():
            self.descargas_cambiadas.emit()
        else:
            self.instalados_cambiados.emit()

    def notificar_cambio(self) -> None:
        """Refresco tras una acción de la propia app, sin esperar al watcher."""
        self.instalados_cambiados.emit()
        self.descargas_cambiadas.emit()

    # ── Instalado ─────────────────────────────────────────────────────────────

    def leer_instalados(self) -> list[Instalado]:
        origenes = self._store.origenes()
        resultado: list[Instalado] = []

        for categoria, carpeta in self._carpetas_por_categoria().items():
            if not carpeta.is_dir():
                continue
            for entrada in sorted(carpeta.iterdir()):
                pieza = self._leer_entrada(entrada, categoria, origenes)
                if pieza is not None:
                    resultado.append(pieza)

        resultado.sort(key=lambda p: (p.categoria.value, p.nombre.lower()))
        return resultado

    def indice_por_uuid(self) -> dict[str, Instalado]:
        return {p.uuid: p for p in self.leer_instalados() if p.uuid}

    def _carpetas_por_categoria(self) -> dict[Categoria, Path]:
        i = self._instalacion
        return {
            Categoria.RECURSO: i.resource_packs,
            Categoria.COMPORTAMIENTO: i.behavior_packs,
            Categoria.SKIN: i.skin_packs,
            Categoria.PLANTILLA: i.world_templates,
            Categoria.MUNDO: i.mundos,
        }

    def _leer_entrada(
        self, entrada: Path, categoria: Categoria, origenes: dict
    ) -> Instalado | None:
        if entrada.is_file():
            return self._leer_empaquetado(entrada, categoria)
        if not entrada.is_dir():
            return None
        if categoria == Categoria.MUNDO:
            return self._leer_mundo(entrada)

        carpeta = _carpeta_del_pack(entrada)
        if carpeta is None:
            return None
        try:
            manifiesto = desde_carpeta(carpeta)
        except (ManifiestoInvalido, OSError):
            return None
        if not manifiesto.es_bedrock:
            return None

        archivo, instalado_en = origenes.get(manifiesto.uuid, (None, None))
        return Instalado(
            uuid=manifiesto.uuid,
            nombre=manifiesto.nombre or entrada.name,
            version=manifiesto.version,
            categoria=categoria_de(manifiesto.tipos) or categoria,
            ruta=entrada,
            forma=Forma.CARPETA if carpeta == entrada else Forma.ANIDADO,
            de_la_tienda=es_de_la_tienda(carpeta),
            origen=archivo,
            instalado_en=instalado_en,
        )

    def _leer_empaquetado(self, archivo: Path, categoria: Categoria) -> Instalado | None:
        """Un `.mcpack` copiado a la carpeta sin extraer.

        Es una forma de instalación válida que el juego admite; simplemente no es
        la que produce este gestor, así que se ofrece extraerlo para dejarlo como
        el resto.
        """
        if not zipfile.is_zipfile(archivo):
            return None
        analisis = self._analizar(archivo)
        if analisis is None or not analisis.componentes:
            return None
        c = analisis.componentes[0]
        return Instalado(
            uuid=c.uuid,
            nombre=c.nombre,
            version=c.version,
            categoria=c.categoria,
            ruta=archivo,
            forma=Forma.EMPAQUETADO,
        )

    def _leer_mundo(self, carpeta: Path) -> Instalado | None:
        if not (carpeta / "level.dat").is_file():
            return None
        nombre_txt = carpeta / "levelname.txt"
        nombre = carpeta.name
        if nombre_txt.is_file():
            nombre = nombre_txt.read_text(encoding="utf-8", errors="replace").strip() or nombre
        return Instalado(
            uuid="", nombre=nombre, version=None,
            categoria=Categoria.MUNDO, ruta=carpeta,
        )

    # ── Descargas ─────────────────────────────────────────────────────────────

    def leer_descargas(self) -> list[Analisis]:
        """Lo instalable que haya en cualquiera de las carpetas vigiladas.

        Un mismo archivo puede aparecer en dos carpetas vigiladas si una está
        dentro de la otra; se muestra una sola vez.
        """
        resultado: list[Analisis] = []
        vistos: set[Path] = set()

        for carpeta in self.carpetas():
            if not carpeta.is_dir():
                continue
            for archivo in sorted(carpeta.iterdir()):
                resuelta = archivo.resolve()
                if resuelta in vistos:
                    continue
                analisis = self._analizar(archivo)
                if analisis is not None:
                    vistos.add(resuelta)
                    resultado.append(analisis)
        return resultado

    def _analizar(self, archivo: Path) -> Analisis | None:
        try:
            info = archivo.stat()
        except OSError:
            return None
        clave = (str(archivo), info.st_size, int(info.st_mtime))
        if clave not in self._cache:
            self._cache[clave] = analizar(archivo)
        return self._cache[clave]

    def es_nuevo(self, ruta: Path) -> bool:
        try:
            return self._store.es_nuevo(hash_archivo(ruta))
        except OSError:
            return False

    def marcar_vistos(self, rutas: list[Path]) -> None:
        for ruta in rutas:
            try:
                self._store.marcar_visto(hash_archivo(ruta))
            except OSError:
                continue


def _carpeta_del_pack(entrada: Path) -> Path | None:
    """Dónde está el `manifest.json`: en la carpeta, o un nivel más abajo."""
    if (entrada / "manifest.json").is_file():
        return entrada
    try:
        hijos = [h for h in entrada.iterdir() if h.is_dir()]
    except OSError:
        return None
    if len(hijos) == 1 and (hijos[0] / "manifest.json").is_file():
        return hijos[0]
    return None
