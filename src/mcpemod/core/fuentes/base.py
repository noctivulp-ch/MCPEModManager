"""Lo que toda fuente de contenido tiene que saber contestar.

Una fuente es un catálogo del que se pueden bajar packs: MCPEDL, CurseForge, o
lo que venga. El resto de la app no sabe de cuál viene nada — solo maneja
`Publicacion` y `Descarga`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class Descarga:
    """Un archivo concreto que publica una fuente."""

    nombre: str
    url: str
    tamano: int = 0
    fecha: datetime | None = None
    #: La versión que anuncia el catálogo, si la anuncia. No es de fiar: sale del
    #: nombre del archivo, no del manifiesto. Solo sirve para ordenar candidatas.
    version_anunciada: str | None = None


@dataclass(frozen=True)
class Publicacion:
    """Una entrada del catálogo: un pack con todas sus versiones."""

    fuente: str
    id: str
    titulo: str
    autor: str
    url: str
    descargas: tuple[Descarga, ...] = ()
    resumen: str = ""
    imagen: str | None = None
    descargas_totales: int = 0
    actualizado: datetime | None = None
    categorias: tuple[str, ...] = field(default=())
    #: El catálogo publica archivos pero no da con qué bajarlos, porque el autor
    #: desactivó la distribución por aplicaciones de terceros. Se puede mirar,
    #: no instalar.
    distribucion_bloqueada: bool = False

    @property
    def ultima(self) -> Descarga | None:
        """El archivo más reciente. Los catálogos los listan del nuevo al viejo."""
        return self.descargas[0] if self.descargas else None


class Fuente(Protocol):
    """Un catálogo consultable.

    `disponible` existe porque una fuente puede estar apagada por configuración
    —CurseForge sin clave— y la app tiene que poder saberlo sin intentar una
    petición que va a fallar.
    """

    nombre: str
    etiqueta: str

    @property
    def disponible(self) -> bool: ...

    def buscar(self, texto: str, pagina: int = 1, por_pagina: int = 20) -> list[Publicacion]: ...

    def recientes(self, pagina: int = 1, por_pagina: int = 20) -> list[Publicacion]: ...
