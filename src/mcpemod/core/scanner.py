"""Estado del disco: qué hay instalado y qué hay descargado.

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
from .manifiesto import ManifiestoInvalido, desde_carpeta
from .mod import Instalado, hash_archivo
from .rutas import Instalacion, carpeta_descargas
from .store import Store


class Scanner(QObject):
    instalados_cambiados = Signal()
    descargas_cambiadas = Signal()

    def __init__(self, store: Store, instalacion: Instalacion, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._store = store
        self._instalacion = instalacion
        self._watcher = QFileSystemWatcher(self)
        conectar(self._watcher.directoryChanged, self._al_cambiar_directorio)
        self._reobservar()

    @property
    def instalacion(self) -> Instalacion:
        return self._instalacion

    def cambiar_instalacion(self, instalacion: Instalacion) -> None:
        self._instalacion = instalacion
        self._reobservar()
        self.notificar_cambio()

    def _reobservar(self) -> None:
        if self._watcher.directories():
            self._watcher.removePaths(self._watcher.directories())
        for ruta in (*self._instalacion.directorios_contenido, carpeta_descargas()):
            if ruta.is_dir():
                self._watcher.addPath(str(ruta))

    def _al_cambiar_directorio(self, ruta: str) -> None:
        # Qt deja de observar un directorio si desaparece; al recrearse hay que
        # volver a engancharlo o el panel se queda congelado sin avisar.
        if Path(ruta).is_dir() and ruta not in self._watcher.directories():
            self._watcher.addPath(ruta)

        if ruta == str(carpeta_descargas()):
            self.descargas_cambiadas.emit()
        else:
            self.instalados_cambiados.emit()

    def notificar_cambio(self) -> None:
        """Refresco tras una acción de la propia app, sin esperar al watcher."""
        self.instalados_cambiados.emit()
        self.descargas_cambiadas.emit()

    # ── Lecturas ──────────────────────────────────────────────────────────────

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
            return self._leer_archivo_suelto(entrada, categoria)
        if not entrada.is_dir():
            return None

        if categoria == Categoria.MUNDO:
            return self._leer_mundo(entrada, origenes)

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
            # El juego busca el manifiesto en la raíz de la carpeta del pack: si
            # está un nivel más abajo, el pack está ahí pero no se carga.
            activo=carpeta == entrada,
            origen=archivo,
            instalado_en=instalado_en,
        )

    def _leer_archivo_suelto(self, archivo: Path, categoria: Categoria) -> Instalado | None:
        """Un `.mcpack` copiado a la carpeta sin extraer.

        Está donde debe pero el juego no lo lee: solo abre carpetas. Se muestra
        como inactivo para que se vea que hace falta instalarlo de verdad.
        """
        if not zipfile.is_zipfile(archivo):
            return None
        analisis = analizar(archivo)
        if analisis is None or not analisis.componentes:
            return None
        c = analisis.componentes[0]
        return Instalado(
            uuid=c.uuid,
            nombre=c.nombre,
            version=c.version,
            categoria=c.categoria,
            ruta=archivo,
            activo=False,
        )

    def _leer_mundo(self, carpeta: Path, origenes: dict) -> Instalado | None:
        if not (carpeta / "level.dat").is_file():
            return None
        nombre_txt = carpeta / "levelname.txt"
        nombre = carpeta.name
        if nombre_txt.is_file():
            leido = nombre_txt.read_text(encoding="utf-8", errors="replace").strip()
            nombre = leido or nombre
        return Instalado(
            uuid="",
            nombre=nombre,
            version=None,
            categoria=Categoria.MUNDO,
            ruta=carpeta,
        )

    def leer_descargas(self) -> list[Analisis]:
        descargas = carpeta_descargas()
        if not descargas.is_dir():
            return []

        resultado = []
        for archivo in sorted(descargas.iterdir()):
            analisis = analizar(archivo)
            if analisis is not None:
                resultado.append(analisis)
        return resultado

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
    """Dónde está el `manifest.json`: en la carpeta, o un nivel más abajo.

    Un pack empaquetado con su propia carpeta contenedora se extrae anidado. El
    juego no lo carga así, pero está instalado y hay que verlo en la lista.
    """
    if (entrada / "manifest.json").is_file():
        return entrada
    try:
        hijos = [h for h in entrada.iterdir() if h.is_dir()]
    except OSError:
        return None
    if len(hijos) == 1 and (hijos[0] / "manifest.json").is_file():
        return hijos[0]
    return None
