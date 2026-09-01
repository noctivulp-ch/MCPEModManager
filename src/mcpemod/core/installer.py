"""Instalación y desinstalación de contenido de Bedrock.

Dos reglas gobiernan todo lo de aquí:

1. **Qué carpeta le toca lo decide el tipo del módulo**, no la extensión ni el
   nombre. El pack declara qué es (`modules[].type`) y el juego mapea eso a una
   de sus carpetas.
2. **Qué pack es lo dice su `header.uuid`**, que es la identidad oficial, **y en
   segundo lugar su nombre**, para los packs cuyo autor cambia el uuid en cada
   publicación — que los hay, y al juego se le acumulan. Si se encuentra un pack
   que ya está, se reemplaza su carpeta en vez de crear otra. Ver
   `mcpemod.core.identidad`.
"""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from .contenido import Analisis, Categoria, Componente, analizar
from .identidad import clave_de_pack
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

    def instalar(
        self,
        analisis: Analisis,
        instalados: dict[str, Instalado],
        solo: set[str] | None = None,
    ) -> list[Path]:
        """Instala lo que trae `analisis`. Devuelve las rutas creadas.

        `instalados` es el índice de lo que ya hay en disco (`Scanner.indice()`),
        que responde por uuid y por clave de nombre — es lo que permite reconocer
        que esto es una versión nueva de algo que ya está.

        `solo` limita qué piezas se instalan. Acepta **uuid o clave de nombre**,
        las dos señales con las que se reconoce un pack, porque el emparejamiento
        pudo hacerse por cualquiera de ellas: al actualizar un pack cuyo autor le
        cambió el nombre, la clave no coincide y el uuid sí.

        Hace falta porque un pack puede estar publicado **dentro de un addon** con
        más cosas, y actualizarlo no debe instalar de propina lo que nadie pidió.
        """
        if not analisis.componentes:
            raise ErrorInstalacion(f"{analisis.ruta.name} no contiene nada instalable")

        if solo is None:
            elegidos = list(analisis.componentes)
        else:
            # El uuid antes que el nombre: dos packs hermanos suelen compartir
            # `header.name`, y quedarse con el del nombre instalaría el otro.
            elegidos = [c for c in analisis.componentes if c.uuid and c.uuid in solo]
            if not elegidos:
                elegidos = [
                    c for c in analisis.componentes if clave_de_pack(c.nombre) in solo
                ]
        if not elegidos:
            raise ErrorInstalacion(
                f"{analisis.ruta.name} no contiene el pack que se iba a actualizar"
            )

        return [self._instalar_componente(analisis, c, instalados) for c in elegidos]

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
        # El uuid primero, que es la identidad oficial; el nombre como respaldo
        # para los packs cuyo autor lo cambia en cada versión.
        anterior = (
            (instalados.get(componente.uuid) if componente.uuid else None)
            or instalados.get(clave_de_pack(componente.nombre))
        )
        destino = self._destino(componente, anterior)
        self._retirar_forma_anterior(anterior, destino, analisis.ruta)

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
        # Sobre la carpeta que ya tenía este pack, se llame como se llame: es lo
        # que hace del reemplazo una actualización y no un duplicado.
        if anterior is not None and anterior.ruta.is_dir():
            return anterior.ruta

        carpeta = self._carpeta_de(componente.categoria)
        return _sin_colision(carpeta / nombre_de_carpeta(componente.nombre))

    def _retirar_forma_anterior(
        self, anterior: Instalado | None, destino: Path, origen: Path
    ) -> None:
        """Quita la versión anterior cuando no está en la carpeta que se reusa.

        Pasa al actualizar un pack que estaba **sin extraer**: lo viejo es un
        archivo `.mcpack` y lo nuevo una carpeta, así que no se sobrescribe solo.
        Sin esto quedan los dos, con el mismo uuid, y el juego ve el pack dos
        veces — que es justo lo que este gestor existe para evitar.
        """
        if anterior is None or anterior.ruta == destino:
            return
        # El archivo que se está instalando no se toca, aunque sea el anterior.
        if anterior.ruta.resolve() == origen.resolve():
            return

        if anterior.ruta.is_file():
            anterior.ruta.unlink(missing_ok=True)
        elif anterior.ruta.is_dir():
            shutil.rmtree(anterior.ruta, ignore_errors=True)

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
