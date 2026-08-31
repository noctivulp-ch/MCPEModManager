"""Modelo de datos central: un Mod y su estado."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


class EstadoVersion(Enum):
    IGUAL = "igual"
    NUEVA = "nueva"
    ANTERIOR = "anterior"
    DESCONOCIDA = "desconocida"


class TipoArchivo(Enum):
    SO = ".so"
    MCPACK = ".mcpack"
    MCADDON = ".mcaddon"
    ZIP = ".zip"

    @classmethod
    def desde_ruta(cls, ruta: Path) -> TipoArchivo | None:
        sufijo = ruta.suffix.lower()
        for t in cls:
            if t.value == sufijo:
                return t
        return None


@dataclass
class Mod:
    nombre: str
    #: El nombre sin la versión — la clave con la que se detecta una actualización.
    canonico: str
    archivo: str
    #: Todo lo que la instalación puso en disco. Un `.mcaddon` deja varias
    #: carpetas; desinstalar tiene que poder borrarlas todas, no solo la primera.
    rutas: list[Path]
    tipo: TipoArchivo
    version: str | None
    hash_sha256: str
    instalado: bool = False
    primera_vez: bool = False
    instalado_en: datetime | None = None
    id: int | None = None

    @property
    def origen(self) -> Path:
        """La primera ruta — el archivo o carpeta principal del mod."""
        return self.rutas[0]

    @staticmethod
    def calcular_hash(ruta: Path) -> str:
        h = hashlib.sha256()
        with ruta.open("rb") as f:
            for bloque in iter(lambda: f.read(65536), b""):
                h.update(bloque)
        return h.hexdigest()


@dataclass
class EntradaHistorial:
    accion: str
    archivo: str
    version: str | None
    version_anterior: str | None
    timestamp: datetime = field(default_factory=datetime.now)
    id: int | None = None
