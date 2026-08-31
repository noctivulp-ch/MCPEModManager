"""Modelos de datos del gestor."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from .contenido import Categoria

_ILEGALES = re.compile(r'[/\\:*?"<>|\x00-\x1f]')
_ESPACIOS = re.compile(r"\s+")
_LARGO_MAX_CARPETA = 64


class Forma(Enum):
    """Cómo está puesta una pieza en la carpeta del juego.

    No dice si el juego la carga o no: `EMPAQUETADO` y `ANIDADO` son formas que
    el juego admite, solo que no son las que produce este gestor. Se distinguen
    para poder normalizarlas, no para desaconsejarlas.
    """

    #: Carpeta con el `manifest.json` en su raíz. Lo que instala el gestor.
    CARPETA = "carpeta"
    #: Un `.mcpack` copiado a la carpeta sin extraer.
    EMPAQUETADO = "empaquetado"
    #: Extraído con su carpeta contenedora, con el manifiesto un nivel más abajo.
    ANIDADO = "anidado"

    @property
    def etiqueta(self) -> str:
        return {
            Forma.CARPETA: "",
            Forma.EMPAQUETADO: "sin extraer",
            Forma.ANIDADO: "carpeta anidada",
        }[self]

    @property
    def normalizable(self) -> bool:
        return self is not Forma.CARPETA


@dataclass(frozen=True)
class Instalado:
    """Una pieza de contenido presente en la carpeta del juego.

    La identidad es el `uuid` del manifiesto — es lo que usa el propio juego, y
    lo único estable entre dos versiones del mismo pack o entre lo que instaló
    el gestor y lo que importó el jugador por su cuenta.
    """

    uuid: str
    nombre: str
    version: str | None
    categoria: Categoria
    ruta: Path
    forma: Forma = Forma.CARPETA
    #: Nombre del archivo del que salió, si lo instaló este gestor.
    origen: str | None = None
    instalado_en: datetime | None = None


@dataclass
class EntradaHistorial:
    accion: str
    nombre: str
    categoria: str
    version: str | None
    version_anterior: str | None
    uuid: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    id: int | None = None


def nombre_de_carpeta(nombre: str, respaldo: str = "pack") -> str:
    """Un nombre de carpeta legible a partir del nombre del pack.

    El juego identifica los packs por uuid y nunca por su carpeta, así que el
    nombre es libre; se elige legible en vez de replicar el recorte a diez
    caracteres con el que quedan las carpetas importadas desde el juego.
    """
    limpio = _ESPACIOS.sub(" ", _ILEGALES.sub("", nombre)).strip(" .")
    return limpio[:_LARGO_MAX_CARPETA].strip() or respaldo


def hash_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()
