"""Instalación y desinstalación de contenido de Bedrock.

Dos reglas gobiernan todo lo de aquí:

1. **El destino lo decide el tipo del módulo**, no la extensión ni el nombre. El
   pack declara qué es (`modules[].type`) y el juego mapea eso a una carpeta.
2. **La identidad es el uuid del manifiesto.** Antes de instalar se busca ese
   uuid entre lo que ya hay en disco; si aparece, se reemplaza esa carpeta
   conservando su nombre, aunque la haya creado el juego y se llame de otra
   forma. Así nunca queda el mismo pack dos veces.
"""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from .contenido import Analisis, Categoria, Componente, analizar
from .mod import EntradaHistorial, Forma, Instalado, nombre_de_carpeta
from .rutas import Instalacion
from .store import Store


class ErrorInstalacion(Exception):
    pass


class Installer:
    def __init__(self, store: Store, instalacion: Instalacion) -> None:
        self._store = store
        self._instalacion = instalacion

    def cambiar_instalacion(self, instalacion: Instalacion) -> None:
        self._instalacion = instalacion

    def instalar(self, analisis: Analisis, instalados: dict[str, Instalado]) -> list[Path]:
        """Instala todo lo que trae `analisis`. Devuelve las rutas creadas.

        `instalados` es el índice por uuid de lo que ya hay en disco — es lo que
        permite reconocer una actualización de un pack que instaló el juego.
        """
        if not analisis.componentes:
            raise ErrorInstalacion(f"{analisis.ruta.name} no contiene nada instalable")

        creadas = []
        for componente in analisis.componentes:
            creadas.append(self._instalar_componente(analisis, componente, instalados))
        return creadas

    def normalizar(self, pieza: Instalado, instalados: dict[str, Instalado]) -> Path:
        """Deja una pieza en la forma que produce el gestor: carpeta con el
        `manifest.json` en su raíz.

        Las otras dos formas que se encuentran en una instalación real —un
        `.mcpack` sin extraer y un pack con su carpeta contenedora dentro— son
        instalaciones válidas que el juego admite. Normalizarlas no las arregla:
        las uniforma, para que actualizarlas y desinstalarlas funcione igual que
        con el resto.
        """
        if not pieza.forma.normalizable:
            raise ErrorInstalacion(f"{pieza.nombre} ya está en forma de carpeta")

        if pieza.forma is Forma.EMPAQUETADO:
            analisis = analizar(pieza.ruta)
            if analisis is None:
                raise ErrorInstalacion(f"{pieza.ruta.name} no es contenido instalable")
            destinos = self.instalar(analisis, instalados)
            pieza.ruta.unlink()
            return destinos[0]

        return self._aplanar(pieza)

    def _aplanar(self, pieza: Instalado) -> Path:
        hijos = [h for h in pieza.ruta.iterdir() if h.is_dir()]
        if len(hijos) != 1 or not (hijos[0] / "manifest.json").is_file():
            raise ErrorInstalacion(f"No sé cómo normalizar {pieza.nombre}")

        interior = hijos[0]
        with tempfile.TemporaryDirectory(dir=pieza.ruta.parent) as tmp:
            # Se mueve fuera y se vuelve a entrar: subir los archivos uno a uno
            # dentro de la misma carpeta puede pisar el propio directorio origen.
            provisional = Path(tmp) / "contenido"
            shutil.move(str(interior), str(provisional))
            shutil.rmtree(pieza.ruta)
            shutil.move(str(provisional), str(pieza.ruta))

        self._store.registrar(EntradaHistorial(
            accion="normalizar",
            uuid=pieza.uuid,
            nombre=pieza.nombre,
            categoria=pieza.categoria.etiqueta,
            version=pieza.version,
            version_anterior=None,
        ))
        return pieza.ruta

    def desinstalar(self, pieza: Instalado) -> None:
        if pieza.ruta.is_dir():
            shutil.rmtree(pieza.ruta, ignore_errors=True)
        elif pieza.ruta.exists():
            pieza.ruta.unlink()

        if pieza.uuid:
            self._store.olvidar_origen(pieza.uuid)
        self._store.registrar(EntradaHistorial(
            accion="desinstalar",
            uuid=pieza.uuid,
            nombre=pieza.nombre,
            categoria=pieza.categoria.etiqueta,
            version=pieza.version,
            version_anterior=None,
        ))

    # ── Interno ───────────────────────────────────────────────────────────────

    def _instalar_componente(
        self, analisis: Analisis, componente: Componente, instalados: dict[str, Instalado]
    ) -> Path:
        anterior = instalados.get(componente.uuid) if componente.uuid else None
        destino = self._destino(componente, anterior)

        if destino.exists():
            shutil.rmtree(destino) if destino.is_dir() else destino.unlink()
        destino.parent.mkdir(parents=True, exist_ok=True)

        if componente.anidado_en is None:
            with zipfile.ZipFile(analisis.ruta) as zf:
                _extraer(zf, componente.prefijo, destino, analisis.ruta.name)
        else:
            with zipfile.ZipFile(analisis.ruta) as externo, \
                 tempfile.TemporaryDirectory() as tmp:
                interno = Path(tmp) / "anidado"
                interno.write_bytes(externo.read(componente.anidado_en))
                with zipfile.ZipFile(interno) as zf:
                    _extraer(zf, componente.prefijo, destino, componente.anidado_en)

        if componente.uuid:
            self._store.registrar_origen(componente.uuid, analisis.ruta.name)
        self._store.registrar(EntradaHistorial(
            accion="actualizar" if anterior else "instalar",
            uuid=componente.uuid,
            nombre=componente.nombre,
            categoria=componente.categoria.etiqueta,
            version=componente.version,
            version_anterior=anterior.version if anterior else None,
        ))
        return destino

    def _destino(self, componente: Componente, anterior: Instalado | None) -> Path:
        # Reinstalar sobre la carpeta que ya tenía el pack, tenga el nombre que
        # tenga: el juego lo localiza por uuid, y renombrarla solo dejaría dos.
        if anterior is not None and anterior.ruta.is_dir():
            return anterior.ruta

        carpeta = self._carpeta_de(componente.categoria)
        return _sin_colision(carpeta / nombre_de_carpeta(componente.nombre))

    def _carpeta_de(self, categoria: Categoria) -> Path:
        i = self._instalacion
        try:
            return {
                Categoria.RECURSO: i.resource_packs,
                Categoria.COMPORTAMIENTO: i.behavior_packs,
                Categoria.SKIN: i.skin_packs,
                Categoria.PLANTILLA: i.world_templates,
                Categoria.MUNDO: i.mundos,
            }[categoria]
        except KeyError:
            raise ErrorInstalacion(f"Sin destino para {categoria}") from None


def _extraer(zf: zipfile.ZipFile, prefijo: str, destino: Path, origen: str) -> None:
    """Extrae la parte del zip bajo `prefijo` a `destino`, sin el prefijo.

    Un pack empaquetado con su carpeta contenedora tiene que quedar aplanado: el
    juego busca `manifest.json` en la raíz de la carpeta del pack y no lo carga
    si está un nivel más abajo.
    """
    destino = destino.resolve()
    destino.mkdir(parents=True, exist_ok=True)

    for miembro in zf.infolist():
        if not miembro.filename.startswith(prefijo):
            continue
        relativa = miembro.filename[len(prefijo):]
        if not relativa:
            continue

        objetivo = (destino / relativa).resolve()
        if not objetivo.is_relative_to(destino):
            shutil.rmtree(destino, ignore_errors=True)
            raise ErrorInstalacion(
                f"{origen} intenta escribir fuera de su carpeta: {miembro.filename}"
            )

        if miembro.is_dir():
            objetivo.mkdir(parents=True, exist_ok=True)
            continue
        objetivo.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(miembro) as fuente, objetivo.open("wb") as salida:
            shutil.copyfileobj(fuente, salida)


def _sin_colision(destino: Path) -> Path:
    if not destino.exists():
        return destino
    for n in range(1, 1000):
        candidato = destino.with_name(f"{destino.name} ({n})")
        if not candidato.exists():
            return candidato
    return destino.with_name(f"{destino.name} {datetime.now():%Y%m%d%H%M%S}")
