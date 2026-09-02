"""Qué packs están aplicados, y en qué orden.

Instalar y activar son cosas distintas: un pack se activa **listándolo** en un
JSON, con `pack_id` y `version` que tienen que cuadrar con su manifiesto. Un
desajuste hace que no cargue, y el juego no dice por qué —de ahí que aquí se
valide antes de escribir en vez de confiar—.

Hay dos ámbitos y no son simétricos:

- **Global**, en `minecraftpe/global_resource_packs.json`. Solo packs de
  recursos: los de comportamiento cambian el contenido del mundo, así que no
  tienen activación global. No es un archivo que falte.
- **Por mundo**, en sus `world_resource_packs.json` y `world_behavior_packs.json`.
  Aquí activar es además **copiar el pack dentro del mundo**, porque un mundo usa
  su copia y no la instalación.

El orden de la lista importa: los packs se aplican en ese orden y el último gana.

Ver `docs/funciones/activacion-de-packs.md`.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from .contenido import Categoria
from .manifiesto import ManifiestoInvalido, desde_carpeta
from .mod import Instalado, nombre_de_carpeta
from .rutas import Instalacion

#: Los packs de comportamiento no se activan globalmente.
CATEGORIAS_GLOBALES = (Categoria.RECURSO,)
CATEGORIAS_DE_MUNDO = (Categoria.RECURSO, Categoria.COMPORTAMIENTO)


class ErrorActivacion(Exception):
    pass


@dataclass(frozen=True)
class Referencia:
    """Una entrada de un archivo de activación."""

    uuid: str
    version: tuple[int, ...]
    subpack: str | None = None

    def a_json(self) -> dict:
        datos: dict = {"pack_id": self.uuid, "version": list(self.version)}
        if self.subpack:
            datos["subpack"] = self.subpack
        return datos

    @property
    def version_texto(self) -> str:
        return ".".join(str(x) for x in self.version)


def _version_de(texto: str | None) -> tuple[int, ...]:
    """El `header.version` como lo espera el archivo de activación.

    Tiene que cuadrar **exactamente** con el manifiesto; si no, el pack no carga.
    """
    partes = []
    for trozo in (texto or "").split("."):
        try:
            partes.append(int(trozo))
        except ValueError:
            break
    return tuple(partes) if partes else (0, 0, 0)


def leer(archivo: Path) -> list[Referencia]:
    """Las referencias de un archivo de activación, en su orden."""
    if not archivo.is_file():
        return []
    try:
        datos = json.loads(archivo.read_text(encoding="utf-8-sig") or "[]")
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(datos, list):
        return []

    referencias = []
    for entrada in datos:
        if not isinstance(entrada, dict) or not entrada.get("pack_id"):
            continue
        version = entrada.get("version") or []
        referencias.append(Referencia(
            uuid=str(entrada["pack_id"]),
            version=tuple(int(x) for x in version if isinstance(x, int)),
            subpack=entrada.get("subpack") or None,
        ))
    return referencias


def escribir(archivo: Path, referencias: list[Referencia]) -> None:
    """Reescribe el archivo de activación, sin dejarlo a medias.

    Se escribe en un temporal al lado y se sustituye de golpe: si el proceso
    muere a mitad, lo que había sigue entero. Un archivo truncado aquí deja al
    mundo sin sus packs.
    """
    archivo.parent.mkdir(parents=True, exist_ok=True)
    contenido = json.dumps([r.a_json() for r in referencias], indent=2)

    descriptor, provisional = tempfile.mkstemp(dir=archivo.parent, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as f:
            f.write(contenido)
            f.flush()
            os.fsync(f.fileno())
        os.replace(provisional, archivo)
    except OSError:
        Path(provisional).unlink(missing_ok=True)
        raise


class Ambito:
    """Dónde se activan packs: el juego entero, o un mundo."""

    def __init__(self, nombre: str, instalacion: Instalacion) -> None:
        self.nombre = nombre
        self._instalacion = instalacion

    @property
    def categorias(self) -> tuple[Categoria, ...]:
        raise NotImplementedError

    def archivo_de(self, categoria: Categoria) -> Path:
        raise NotImplementedError

    # ── Lectura ───────────────────────────────────────────────────────────────

    def activos(self, categoria: Categoria) -> list[Referencia]:
        return leer(self.archivo_de(categoria))

    def uuids_activos(self) -> set[str]:
        return {r.uuid for c in self.categorias for r in self.activos(c)}

    # ── Escritura ─────────────────────────────────────────────────────────────

    def activar(self, pieza: Instalado, subpack: str | None = None) -> None:
        """Añade el pack al final: el último de la lista es el que manda."""
        self._comprobar(pieza)
        categoria = self._categoria_de(pieza)
        archivo = self.archivo_de(categoria)

        referencias = [r for r in leer(archivo) if r.uuid != pieza.uuid]
        referencias.append(Referencia(pieza.uuid, _version_de(pieza.version), subpack))
        self._preparar(pieza)
        escribir(archivo, referencias)

    def desactivar(self, pieza: Instalado) -> None:
        archivo = self.archivo_de(self._categoria_de(pieza))
        escribir(archivo, [r for r in leer(archivo) if r.uuid != pieza.uuid])

    def elegir_subpack(self, pieza: Instalado, subpack: str | None) -> None:
        """Cambia qué variante del pack se aplica, sin moverlo de sitio.

        No es activar de nuevo con otra variante: eso lo mandaría al final de la
        lista y el orden es lo que decide cuál gana cuando dos packs tocan lo
        mismo. Aquí solo cambia el campo.

        Con `None` se quita la elección, que **no es dejarlo sin variante**: la
        documentación dice que sin ella el juego coge sola *«the highest
        memory_performance_tier value that doesn't exceed the tier of the
        player's device»*. Es devolverle la decisión al juego.
        """
        categoria = self._categoria_de(pieza)
        archivo = self.archivo_de(categoria)
        referencias = leer(archivo)
        if not any(r.uuid == pieza.uuid for r in referencias):
            raise ErrorActivacion(
                f"«{pieza.nombre}» no está activo en {self.nombre.lower()}: "
                "no hay ninguna variante que cambiar"
            )
        escribir(archivo, [
            replace(r, subpack=subpack) if r.uuid == pieza.uuid else r
            for r in referencias
        ])

    def subpack_de(self, pieza: Instalado) -> str | None:
        """Qué variante tiene elegida, si tiene alguna."""
        for categoria in self.categorias:
            for r in self.activos(categoria):
                if r.uuid == pieza.uuid:
                    return r.subpack
        return None

    def reordenar(self, categoria: Categoria, uuids: list[str]) -> None:
        """Deja los activos en el orden dado. El último gana."""
        por_uuid = {r.uuid: r for r in self.activos(categoria)}
        ordenadas = [por_uuid[u] for u in uuids if u in por_uuid]
        # Lo que no venga en la lista se conserva al final, para no perderlo.
        ordenadas += [r for u, r in por_uuid.items() if u not in set(uuids)]
        escribir(self.archivo_de(categoria), ordenadas)

    # ── Interno ───────────────────────────────────────────────────────────────

    def _categoria_de(self, pieza: Instalado) -> Categoria:
        if pieza.categoria not in self.categorias:
            raise ErrorActivacion(
                f"«{pieza.nombre}» es de {pieza.categoria.etiqueta.lower()} y eso "
                f"no se activa en {self.nombre.lower()}"
            )
        return pieza.categoria

    def _comprobar(self, pieza: Instalado) -> None:
        """Que se pueda activar, antes de escribir nada.

        El juego no avisa de un `pack_id` o una `version` que no cuadren: el pack
        simplemente no aparece, y averiguar por qué lleva un rato.
        """
        if not pieza.uuid:
            raise ErrorActivacion(f"«{pieza.nombre}» no declara uuid")
        if not pieza.version:
            raise ErrorActivacion(f"«{pieza.nombre}» no declara versión")
        if pieza.de_la_tienda:
            raise ErrorActivacion(
                f"«{pieza.nombre}» es contenido de la tienda: lo gestiona el juego"
            )
        if pieza.forma.normalizable:
            raise ErrorActivacion(
                f"«{pieza.nombre}» está {pieza.forma.etiqueta}; extráelo antes de activarlo"
            )

    def _preparar(self, pieza: Instalado) -> None:
        """Lo que haga falta antes de anotarlo. En global, nada."""


class Global(Ambito):
    """El juego entero. Solo packs de recursos."""

    def __init__(self, instalacion: Instalacion) -> None:
        super().__init__("Global", instalacion)

    @property
    def categorias(self) -> tuple[Categoria, ...]:
        return CATEGORIAS_GLOBALES

    def archivo_de(self, categoria: Categoria) -> Path:
        if categoria != Categoria.RECURSO:
            raise ErrorActivacion(
                "los packs de comportamiento no tienen activación global: "
                "cambian el contenido del mundo, así que van por mundo"
            )
        return self._instalacion.com_mojang / "minecraftpe" / "global_resource_packs.json"


class Mundo(Ambito):
    """Un mundo concreto. Recursos y comportamiento, con copia propia."""

    def __init__(self, instalacion: Instalacion, carpeta: Path) -> None:
        super().__init__(_nombre_de_mundo(carpeta), instalacion)
        self.carpeta = carpeta

    @property
    def categorias(self) -> tuple[Categoria, ...]:
        return CATEGORIAS_DE_MUNDO

    def archivo_de(self, categoria: Categoria) -> Path:
        cual = "resource" if categoria == Categoria.RECURSO else "behavior"
        return self.carpeta / f"world_{cual}_packs.json"

    def carpeta_de(self, categoria: Categoria) -> Path:
        cual = "resource_packs" if categoria == Categoria.RECURSO else "behavior_packs"
        return self.carpeta / cual

    def _preparar(self, pieza: Instalado) -> None:
        """Copia el pack dentro del mundo. Sin esto, la entrada no sirve de nada."""
        self.copiar_dentro(pieza)

    def copiar_dentro(self, pieza: Instalado) -> Path:
        """Deja una copia del pack en el mundo, sustituyendo la que hubiera.

        El nombre de carpeta va recortado a diez caracteres porque es un
        requisito para los packs dentro de un mundo: por encima de eso, en Xbox
        las rutas se pasan de largo y el pack no carga.
        """
        destino_padre = self.carpeta_de(pieza.categoria)
        destino_padre.mkdir(parents=True, exist_ok=True)

        anterior = self._copia_existente(pieza.uuid)
        destino = anterior or _sin_colision(destino_padre / nombre_de_carpeta(pieza.nombre))

        if destino.exists():
            shutil.rmtree(destino)
        shutil.copytree(pieza.ruta, destino)
        return destino

    def quitar_copia(self, pieza: Instalado) -> None:
        copia = self._copia_existente(pieza.uuid)
        if copia is not None:
            shutil.rmtree(copia, ignore_errors=True)

    def _copia_existente(self, uuid: str) -> Path | None:
        for categoria in self.categorias:
            carpeta = self.carpeta_de(categoria)
            if not carpeta.is_dir():
                continue
            for candidata in carpeta.iterdir():
                if not (candidata / "manifest.json").is_file():
                    continue
                try:
                    if desde_carpeta(candidata).uuid == uuid:
                        return candidata
                except (ManifiestoInvalido, OSError):
                    continue
        return None

    def copias(self) -> dict[str, str]:
        """Qué versión tiene el mundo de cada pack, por uuid.

        Es lo que permite ver el desfase: un mundo usa su copia, así que
        actualizar el pack instalado no le llega.
        """
        versiones = {}
        for categoria in self.categorias:
            carpeta = self.carpeta_de(categoria)
            if not carpeta.is_dir():
                continue
            for candidata in carpeta.iterdir():
                if not (candidata / "manifest.json").is_file():
                    continue
                try:
                    manifiesto = desde_carpeta(candidata)
                except (ManifiestoInvalido, OSError):
                    continue
                if manifiesto.uuid:
                    versiones[manifiesto.uuid] = manifiesto.version or ""
        return versiones


def mundos_de(instalacion: Instalacion) -> list[Mundo]:
    if not instalacion.mundos.is_dir():
        return []
    encontrados = [
        Mundo(instalacion, c)
        for c in sorted(instalacion.mundos.iterdir())
        if c.is_dir() and (c / "level.dat").is_file()
    ]
    encontrados.sort(key=lambda m: m.nombre.lower())
    return encontrados


def _nombre_de_mundo(carpeta: Path) -> str:
    etiqueta = carpeta / "levelname.txt"
    if etiqueta.is_file():
        leido = etiqueta.read_text(encoding="utf-8", errors="replace").strip()
        if leido:
            return leido
    return carpeta.name


def _sin_colision(destino: Path) -> Path:
    if not destino.exists():
        return destino
    for n in range(1, 100):
        candidato = destino.with_name(f"{destino.name[:8]}({n})")
        if not candidato.exists():
            return candidato
    return destino
