"""Modelos de datos del gestor."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .contenido import Categoria

_ILEGALES = re.compile(r'[/\\:*?"<>|\x00-\x1f]')
_ESPACIOS = re.compile(r"\s+")
_LARGO_MAX_CARPETA = 64


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
    #: `False` cuando el pack está en la carpeta pero el juego no lo puede leer
    #: (por ejemplo un `.mcpack` copiado sin extraer).
    activo: bool = True
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
