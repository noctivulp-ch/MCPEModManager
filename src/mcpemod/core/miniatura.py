"""El `pack_icon.png` de un pack, esté como esté puesto.

Es la portada que el juego enseña en su lista, y la traen 48 de las 50 carpetas
de este equipo. Sirve para lo mismo aquí: en una lista de cuarenta packs con
nombres parecidos —tres se llaman «Better Foliage…»—, la portada distingue de un
vistazo lo que el texto obliga a leer.

Se busca en la raíz del pack y también un nivel más abajo, porque un pack
`ANIDADO` tiene su contenido dentro de una carpeta contenedora. En los que están
`EMPAQUETADO` se saca del `.mcpack` sin extraerlo: es un zip.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from .mod import Forma, Instalado

#: Un pack lleva `pack_icon.png`; un mundo, la captura que el juego guarda al
#: salir. Nombres distintos para lo mismo, así que se buscan los dos.
NOMBRES = ("pack_icon.png", "world_icon.jpeg")

#: Un icono de pack pesa unos pocos KB. Cualquier cosa mayor no es una portada
#: —o es una que no cabe en 40 px—, y leerla entera para encogerla sale caro.
MAXIMO = 4 * 1024 * 1024


def leer(pieza: Instalado) -> bytes | None:
    """Los bytes de la portada de un pack ya instalado, o `None`."""
    return de_ruta(pieza.ruta, empaquetado=pieza.forma is Forma.EMPAQUETADO)


def de_ruta(ruta: Path, prefijo: str = "", anidado_en: str | None = None,
            empaquetado: bool = False) -> bytes | None:
    """La portada de un pack que todavía no está instalado.

    Es la de un archivo de la carpeta de descargas, así que hay que decir **dónde
    mirar dentro**: un `.mcaddon` es un zip de `.mcpack`, y el pack que interesa
    puede estar a dos niveles de profundidad. `prefijo` es la carpeta dentro del
    zip y `anidado_en` el `.mcpack` interno, los mismos que trae cada
    `Componente` para poder extraerse.
    """
    try:
        if anidado_en:
            with zipfile.ZipFile(ruta) as fuera:
                with fuera.open(anidado_en) as crudo:
                    return _del_zip_abierto(
                        zipfile.ZipFile(io.BytesIO(crudo.read())), prefijo
                    )
        if empaquetado or (ruta.is_file() and zipfile.is_zipfile(ruta)):
            with zipfile.ZipFile(ruta) as zf:
                return _del_zip_abierto(zf, prefijo)
        return _de_carpeta(ruta)
    except (OSError, zipfile.BadZipFile, KeyError, ValueError):
        # Un pack sin portada legible se enseña sin ella. No es un fallo que
        # merezca interrumpir el listado entero.
        return None


def _de_carpeta(carpeta: Path) -> bytes | None:
    for nombre in NOMBRES:
        for ruta in (carpeta / nombre, *sorted(carpeta.glob(f"*/{nombre}"))):
            if ruta.is_file() and ruta.stat().st_size <= MAXIMO:
                return ruta.read_bytes()
    return None


def _del_zip_abierto(zf: zipfile.ZipFile, prefijo: str = "") -> bytes | None:
    """La portada dentro de un zip, buscando bajo `prefijo`.

    Con prefijo se busca **solo ahí**: un `.mcaddon` trae la portada de cada pack
    en su carpeta, y coger la primera que aparezca le pondría al pack de
    comportamiento la cara del de recursos.
    """
    dentro = [n for n in zf.namelist() if n.startswith(prefijo)]
    candidatos = [
        n for n in dentro
        for nombre in NOMBRES
        if n[len(prefijo):] == nombre
        or (n.endswith("/" + nombre) and n[len(prefijo):].count("/") == 1)
    ]
    # La menos profunda antes: un pack anidado puede traer las dos, y la de fuera
    # es la del pack entero.
    for nombre in sorted(candidatos, key=lambda n: n.count("/")):
        if zf.getinfo(nombre).file_size <= MAXIMO:
            return zf.read(nombre)
    return None


def manifiesto_de(pieza: Instalado):
    """El manifiesto completo de una pieza ya instalada, o `None`.

    El listado se queda con lo que cabe en una fila —nombre, versión, categoría—
    y descarta el resto. La descripción y las variantes solo hacen falta cuando
    alguien abre la ficha de un pack concreto, así que se releen entonces y no
    para los sesenta de la lista.
    """
    from .manifiesto import ManifiestoInvalido, desde_carpeta, desde_zip

    try:
        if pieza.forma is Forma.EMPAQUETADO:
            with zipfile.ZipFile(pieza.ruta) as zf:
                nombres = [n for n in zf.namelist() if n.endswith("manifest.json")]
                if not nombres:
                    return None
                return desde_zip(zf, min(nombres, key=lambda n: n.count("/")))
        if (pieza.ruta / "manifest.json").is_file():
            return desde_carpeta(pieza.ruta)
        # Un pack anidado tiene el manifiesto un nivel más abajo.
        for hijo in sorted(pieza.ruta.iterdir()):
            if (hijo / "manifest.json").is_file():
                return desde_carpeta(hijo)
    except (OSError, zipfile.BadZipFile, ManifiestoInvalido):
        return None
    return None
