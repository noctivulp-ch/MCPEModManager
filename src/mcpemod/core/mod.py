"""Modelos de datos del gestor."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from .contenido import Categoria
from .identidad import carpeta_del_juego, clave_de_pack

_ILEGALES = re.compile(r'[/\\:*?"<>\x00-\x1f]')


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

    **Qué pack es lo dice `nombre`; qué versión, `uuid`.** No al revés: hay
    autores que cambian el uuid en cada publicación, y el juego actualiza igual
    porque se guía por el nombre. Ver `mcpemod.core.identidad`.
    """

    #: Identidad de la **versión**. Dos piezas con el mismo uuid son la misma
    #: versión del mismo pack; con distinto uuid pueden ser dos versiones del
    #: mismo pack.
    uuid: str
    nombre: str
    version: str | None
    categoria: Categoria
    ruta: Path
    forma: Forma = Forma.CARPETA
    #: Contenido comprado en el Marketplace: lo gestiona el juego, no el gestor.
    de_la_tienda: bool = False
    #: Nombre del archivo del que salió, si lo instaló este gestor.
    autores: tuple[str, ...] = ()
    origen: str | None = None
    instalado_en: datetime | None = None

    @property
    def clave(self) -> str:
        """Identidad del pack: su nombre normalizado."""
        return clave_de_pack(self.nombre)

    @property
    def gestionable(self) -> bool:
        """Si tiene sentido que el gestor lo toque.

        Lo de la tienda viene cifrado y firmado, y el juego lo descarga y
        actualiza él solo: ni se le buscan versiones nuevas en un catálogo
        público ni se desinstala a mano.
        """
        return not self.de_la_tienda


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
    """El nombre de carpeta que el juego le daría a este pack.

    **No es cosmético.** El juego deriva la carpeta destino del nombre del pack
    al importar un `.mcpack`, y si esa carpeta ya existe reemplaza su contenido:
    es así como reconoce una actualización. Poner otro nombre haría que el mismo
    pack acabase dos veces, una por cada vía de instalación.
    """
    limpio = _ILEGALES.sub("", carpeta_del_juego(nombre))
    return limpio or respaldo


def hash_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()
