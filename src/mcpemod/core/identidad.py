"""Qué identifica a un pack, según la norma y según la práctica.

**La norma.** La documentación de Bedrock es explícita: el `header.uuid`
«identifica este pack de cualquier otro», y el `header.version` decide qué pasa
al reimportarlo — *"The new pack will replace the old one if the version is
higher, and ignored if it's the same or lower"*. Es decir: **uuid estable entre
versiones, número de versión que sube**. Esa es la identidad buena y la que se
mira primero.

**La práctica.** Hay autores que no la siguen y cambian el uuid en cada
publicación. Uno de los packs del equipo de prueba llega a codificar el número
de versión dentro del propio uuid:

    v1.3.1  header=a0909a90-90aa-9152-1310-157157157157
    v1.3.9  header=a0909a90-e0c2-9a52-1390-157157157157
                                      ▲▲▲▲

El `modules[].uuid` cambia igual. Para el juego, cada versión de ese pack es un
pack distinto y se le acumulan. Lo único idéntico en las cuatro versiones
publicadas es `header.name`, así que el gestor lo usa como respaldo: reconoce el
pack donde el juego no puede y reemplaza en vez de duplicar.

Ver `docs/decisiones/0020` para la historia completa y las fuentes.
"""

from __future__ import annotations

import re

_CODIGOS_COLOR = re.compile(r"§.")
_NO_SIGNIFICATIVO = re.compile(r"[^0-9a-z]+")
#: Marcas de versión dentro del nombre: «Hide Armor | V1.2», «… v2.2.11».
_VERSION_EN_NOMBRE = re.compile(r"\bv?\d+(?:\.\d+)+\b|\bv\d+\b", re.IGNORECASE)

#: A cuántos caracteres recorta el juego el nombre de la carpeta.
LARGO_CARPETA = 10


def limpiar(nombre: str) -> str:
    """El nombre sin los códigos `§x` con que los autores lo colorean."""
    return _CODIGOS_COLOR.sub("", nombre).strip()


def clave_de_pack(nombre: str) -> str:
    """La forma normalizada del nombre, para decidir si dos packs son el mismo.

    Se quitan tres cosas:

    - los códigos de color y las mayúsculas, espacios y puntuación, que cambian
      entre cómo escribe el autor el nombre en el manifiesto y en el catálogo;
    - **la versión metida dentro del nombre**, que la meten muchos: el mismo pack
      se llama «Hide Armor | V1.2» en una publicación y «Hide Armor | V1.3.1» en
      la siguiente, y sin quitarla no se reconocerían como el mismo.

    Lo que no se quita son los sufijos que distinguen packs hermanos —«NG», «FG»,
    «RP», «BP»—, porque ahí sí son packs distintos que conviven instalados.
    """
    sin_version = _VERSION_EN_NOMBRE.sub(" ", limpiar(nombre))
    return _NO_SIGNIFICATIVO.sub("", sin_version.lower())


def carpeta_del_juego(nombre: str) -> str:
    """El nombre de carpeta que el juego le daría a este pack al importarlo.

    Quita los códigos de color y las barras verticales, junta el resto sin
    espacios y recorta a diez caracteres. Comprobado contra las 43 carpetas de
    una instalación real: acierta en 42.

    La que falla es un pack cuyo `header.name` es la clave sin traducir
    `pack.name` y que colisionaba con otro igual; el juego la dejó en `pack(1)`
    en vez de `pack.name(1)`. Un caso borde de un nombre que ya era anómalo.

    Importa acertar porque **ese nombre es lo que hace que el juego reconozca una
    actualización**: misma carpeta destino, contenido reemplazado.
    """
    sin_adornos = re.sub(r"\s+", "", limpiar(nombre).replace("|", ""))
    return sin_adornos[:LARGO_CARPETA] or "pack"
