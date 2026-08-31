"""Qué es realmente un archivo, mirando dentro y no su extensión.

La extensión no sirve para decidir nada: un `.zip` puede ser un resource pack y
un `.mcpack` puede ser cualquier cosa. Y tener un `manifest.json` en la raíz
tampoco basta — un modpack de CurseForge para Java también lo tiene. Lo que
identifica a Bedrock es el par `header.uuid` + `modules[].type`.

El destino de cada pieza sale de ahí: el juego mapea el tipo del módulo a una de
sus carpetas. El pack nunca declara una ruta; solo declara qué es.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .manifiesto import (
    TIPOS_COMPORTAMIENTO,
    TIPOS_PLANTILLA,
    TIPOS_RECURSO,
    TIPOS_SKIN,
    Manifiesto,
    ManifiestoInvalido,
    desde_zip,
)

_EXTENSIONES_ANIDADAS = (".mcpack", ".mcworld", ".mctemplate", ".mcaddon")
#: Un zip con más miembros que esto no se inspecciona a fondo: a partir de aquí
#: no es contenido de Bedrock sino un modpack de Java o un volcado cualquiera.
_MAX_MIEMBROS = 40_000


class Categoria(Enum):
    RECURSO = "recurso"
    COMPORTAMIENTO = "comportamiento"
    SKIN = "skin"
    PLANTILLA = "plantilla"
    MUNDO = "mundo"

    @property
    def etiqueta(self) -> str:
        return {
            Categoria.RECURSO: "Recursos",
            Categoria.COMPORTAMIENTO: "Comportamiento",
            Categoria.SKIN: "Skins",
            Categoria.PLANTILLA: "Plantilla de mundo",
            Categoria.MUNDO: "Mundo",
        }[self]


def categoria_de(tipos: frozenset[str]) -> Categoria | None:
    """La carpeta que le toca a un pack, según los tipos que declara.

    Un pack con módulos de recursos y de datos a la vez (los hay) se trata como
    de comportamiento: es donde el juego espera los `data` y los `script`, y el
    módulo de recursos viaja con ellos.
    """
    if tipos & TIPOS_PLANTILLA:
        return Categoria.PLANTILLA
    if tipos & TIPOS_SKIN:
        return Categoria.SKIN
    if tipos & TIPOS_COMPORTAMIENTO:
        return Categoria.COMPORTAMIENTO
    if tipos & TIPOS_RECURSO:
        return Categoria.RECURSO
    return None


@dataclass(frozen=True)
class Componente:
    """Una unidad instalable dentro de un archivo.

    Un `.mcaddon` trae varias — típicamente un pack de recursos y uno de
    comportamiento — y cada una va a una carpeta distinta con su propio uuid.
    """

    categoria: Categoria
    nombre: str
    uuid: str
    version: str | None
    #: Prefijo dentro del zip que hay que extraer, `""` si es la raíz.
    prefijo: str = ""
    #: Ruta del `.mcpack` interno del que sale, si viene anidado.
    anidado_en: str | None = None
    manifiesto: Manifiesto | None = None


@dataclass(frozen=True)
class Analisis:
    ruta: Path
    componentes: tuple[Componente, ...]

    @property
    def instalable(self) -> bool:
        return bool(self.componentes)

    @property
    def nombre(self) -> str:
        if len(self.componentes) == 1:
            return self.componentes[0].nombre
        return self.ruta.stem

    @property
    def version(self) -> str | None:
        versiones = {c.version for c in self.componentes if c.version}
        return versiones.pop() if len(versiones) == 1 else None

    @property
    def uuids(self) -> frozenset[str]:
        return frozenset(c.uuid for c in self.componentes if c.uuid)


def analizar(ruta: Path) -> Analisis | None:
    """Qué contiene `ruta`, o `None` si no es nada instalable."""
    try:
        if not ruta.is_file() or ruta.stat().st_size == 0:
            return None
    except OSError:
        return None

    # Todo el contenido de Bedrock es un zip, se llame como se llame. Lo que no
    # lo es, no es instalable — y esta es la única puerta de entrada.
    if not zipfile.is_zipfile(ruta):
        return None

    try:
        with zipfile.ZipFile(ruta) as zf:
            nombres = zf.namelist()
            if len(nombres) > _MAX_MIEMBROS:
                return None
            componentes = _componentes_de_zip(zf, nombres, ruta)
    except (zipfile.BadZipFile, OSError, RuntimeError):
        return None

    return Analisis(ruta, tuple(componentes)) if componentes else None


def _componentes_de_zip(zf: zipfile.ZipFile, nombres: list[str], ruta: Path) -> list[Componente]:
    mundo = _componente_mundo(nombres, ruta)
    if mundo is not None:
        return [mundo]

    componentes = [c for c in (_componente_pack(zf, m) for m in _manifiestos(nombres)) if c]
    componentes.extend(_componentes_anidados(zf, nombres))

    vistos: set[str] = set()
    unicos = []
    for c in componentes:
        clave = c.uuid or f"{c.anidado_en}|{c.prefijo}"
        if clave in vistos:
            continue
        vistos.add(clave)
        unicos.append(c)
    return unicos


def _manifiestos(nombres: list[str]) -> list[str]:
    """Los `manifest.json` que pueden ser la raíz de un pack.

    Se aceptan hasta dos niveles: un `.mcaddon` trae los packs en subcarpetas, y
    un pack empaquetado con su carpeta contenedora tiene el manifiesto un nivel
    por debajo de la raíz. Más abajo ya es contenido interno del pack.
    """
    return [
        n for n in nombres
        if n.rsplit("/", 1)[-1] == "manifest.json" and n.count("/") <= 2
    ]


def _componente_pack(zf: zipfile.ZipFile, ruta_manifest: str) -> Componente | None:
    try:
        manifiesto = desde_zip(zf, ruta_manifest)
    except (ManifiestoInvalido, KeyError, OSError):
        return None
    if not manifiesto.es_bedrock:
        return None

    categoria = categoria_de(manifiesto.tipos)
    if categoria is None:
        return None

    prefijo = ruta_manifest[: -len("manifest.json")]
    return Componente(
        categoria=categoria,
        nombre=manifiesto.nombre or Path(prefijo.rstrip("/")).name,
        uuid=manifiesto.uuid,
        version=manifiesto.version,
        prefijo=prefijo,
        manifiesto=manifiesto,
    )


def _componentes_anidados(zf: zipfile.ZipFile, nombres: list[str]) -> list[Componente]:
    """Packs empaquetados como archivo dentro del archivo (`.mcaddon` clásico)."""
    encontrados = []
    for interno in nombres:
        if not interno.lower().endswith(_EXTENSIONES_ANIDADAS):
            continue
        try:
            with zf.open(interno) as f, zipfile.ZipFile(f) as anidado:
                nombres_anidados = anidado.namelist()
                mundo = _componente_mundo(nombres_anidados, Path(interno))
                if mundo is not None:
                    encontrados.append(Componente(**{**mundo.__dict__, "anidado_en": interno}))
                    continue
                for m in _manifiestos(nombres_anidados):
                    c = _componente_pack(anidado, m)
                    if c is not None:
                        encontrados.append(Componente(**{**c.__dict__, "anidado_en": interno}))
        except (zipfile.BadZipFile, OSError, RuntimeError):
            continue
    return encontrados


def _componente_mundo(nombres: list[str], ruta: Path) -> Componente | None:
    """Un mundo se reconoce por su `level.dat`, no por la extensión `.mcworld`.

    No lleva `manifest.json` propio, así que tampoco tiene uuid: su identidad es
    el nombre que guarda en `levelname.txt`.
    """
    for n in nombres:
        if n.rsplit("/", 1)[-1] == "level.dat" and n.count("/") <= 1:
            prefijo = n[: -len("level.dat")]
            return Componente(
                categoria=Categoria.MUNDO,
                nombre=ruta.stem,
                uuid="",
                version=None,
                prefijo=prefijo,
            )
    return None
