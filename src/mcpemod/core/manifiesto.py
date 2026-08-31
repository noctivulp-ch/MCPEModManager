"""Lectura del `manifest.json` de Bedrock — la identidad real de un pack.

El juego no identifica los packs por su carpeta ni por el nombre del archivo:
usa el `header.uuid`. Se comprueba en `global_resource_pack_settings.json`, que
guarda los ajustes de cada pack bajo su `pack_id`, nunca bajo una ruta.

De ahí que todo en esta app gire alrededor del uuid: es lo único estable entre
dos versiones del mismo pack, entre un archivo renombrado y el original, y entre
lo que instala el gestor y lo que importó el juego por su cuenta.
"""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

#: Cabecera del `contents.json` cifrado con que la tienda empaqueta su contenido.
#: Va en los bytes 4-8, tras cuatro de versión.
MAGIA_CONTENTS = b"\xfc\xb9\xcf\x9b"

_COMENTARIOS = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/', re.DOTALL)
_COMAS_COLGANTES = re.compile(r",(\s*[}\]])")
_CODIGOS_COLOR = re.compile(r"§.")
_CLAVE_LOCALIZADA = re.compile(r"^[\w.]+\.name$")

#: `modules[].type` → clase de contenido. Es lo único que el pack declara sobre
#: su destino; la carpeta concreta la decide el juego a partir de esto.
TIPOS_RECURSO = {"resources"}
TIPOS_COMPORTAMIENTO = {"data", "script", "client_data"}
TIPOS_SKIN = {"skin_pack"}
TIPOS_PLANTILLA = {"world_template"}
TIPOS_CONOCIDOS = TIPOS_RECURSO | TIPOS_COMPORTAMIENTO | TIPOS_SKIN | TIPOS_PLANTILLA


class ManifiestoInvalido(Exception):
    pass


@dataclass(frozen=True)
class Manifiesto:
    uuid: str
    nombre: str
    version: str | None
    tipos: frozenset[str]
    min_engine: str | None = None
    dependencias: tuple[str, ...] = field(default=())
    #: `metadata.authors`. Es la señal más barata para distinguir el pack
    #: original de las reediciones con el mismo nombre al buscar en un catálogo.
    autores: tuple[str, ...] = field(default=())
    #: `metadata.url`, la página del pack. Lo declaran pocos, pero cuando está
    #: apunta directo a la publicación y ahorra tener que adivinar cuál es.
    url: str = ""
    licencia: str = ""

    @property
    def es_bedrock(self) -> bool:
        """Un manifiesto de Bedrock tiene uuid y al menos un módulo reconocible.

        Hace falta comprobarlo: un modpack de CurseForge para Java también trae
        un `manifest.json` en la raíz del zip, y sin este filtro el gestor
        ofrecería instalarlo.
        """
        return bool(self.uuid) and bool(self.tipos & TIPOS_CONOCIDOS)


def cargar_json(datos: bytes) -> dict:
    """`json.loads` tolerante con lo que traen los packs reales.

    Los manifiestos se editan a mano: llevan BOM, comentarios `//` y comas
    colgantes. Uno de los packs instalados en este equipo tiene los `subpacks`
    comentados con `//`, y `json.loads` a secas lo rechaza entero.
    """
    texto = datos.decode("utf-8-sig", errors="replace")
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass

    # Se preservan las cadenas para no destrozar un `//` dentro de una URL.
    limpio = _COMENTARIOS.sub(lambda m: m.group(0) if m.group(0).startswith('"') else "", texto)
    limpio = _COMAS_COLGANTES.sub(r"\1", limpio)
    try:
        return json.loads(limpio)
    except json.JSONDecodeError as e:
        raise ManifiestoInvalido(f"manifest.json ilegible: {e}") from e


def limpiar_formato(texto: str) -> str:
    """Quita los códigos `§x` con que los autores colorean el nombre del pack."""
    return _CODIGOS_COLOR.sub("", texto).strip()


def _version_a_texto(valor) -> str | None:
    if isinstance(valor, list):
        return ".".join(str(x) for x in valor)
    if isinstance(valor, str) and valor.strip():
        return valor.strip()
    return None


def desde_datos(datos: bytes, leer_lang=None) -> Manifiesto:
    """Interpreta un `manifest.json`.

    `leer_lang(nombre)` devuelve el contenido de `texts/<nombre>` si existe. Se
    necesita porque `header.name` puede ser una clave de localización en vez de
    un nombre: cuatro packs de este equipo se llaman literalmente `pack.name`, y
    su nombre de verdad está en `texts/en_US.lang`.
    """
    datos_json = cargar_json(datos)
    header = datos_json.get("header") or {}

    nombre = limpiar_formato(str(header.get("name", "")))
    if _CLAVE_LOCALIZADA.match(nombre) and leer_lang is not None:
        nombre = limpiar_formato(_resolver_lang(nombre, leer_lang) or nombre)

    tipos = {
        str(m.get("type", "")).lower()
        for m in datos_json.get("modules") or []
        if isinstance(m, dict)
    }

    return Manifiesto(
        uuid=str(header.get("uuid", "")).lower(),
        nombre=nombre,
        version=_version_a_texto(header.get("version")),
        tipos=frozenset(tipos - {""}),
        min_engine=_version_a_texto(header.get("min_engine_version")),
        dependencias=tuple(
            str(d.get("uuid", "")).lower()
            for d in datos_json.get("dependencies") or []
            if isinstance(d, dict) and d.get("uuid")
        ),
        autores=tuple(
            str(a).strip()
            for a in (datos_json.get("metadata") or {}).get("authors") or []
            if str(a).strip()
        ),
        url=str((datos_json.get("metadata") or {}).get("url") or "").strip(),
        licencia=str((datos_json.get("metadata") or {}).get("license") or "").strip(),
    )


def _resolver_lang(clave: str, leer_lang) -> str | None:
    for idioma in ("en_US.lang", "es_ES.lang"):
        contenido = leer_lang(idioma)
        if not contenido:
            continue
        for linea in contenido.decode("utf-8-sig", errors="replace").splitlines():
            nombre, sep, valor = linea.partition("=")
            if sep and nombre.strip() == clave:
                return valor.strip()
    return None


def desde_zip(zf: zipfile.ZipFile, ruta_manifest: str) -> Manifiesto:
    base = ruta_manifest.rsplit("/", 1)[0] + "/" if "/" in ruta_manifest else ""

    def leer_lang(nombre: str) -> bytes | None:
        try:
            return zf.read(f"{base}texts/{nombre}")
        except KeyError:
            return None

    return desde_datos(zf.read(ruta_manifest), leer_lang)


def desde_carpeta(carpeta: Path) -> Manifiesto:
    def leer_lang(nombre: str) -> bytes | None:
        ruta = carpeta / "texts" / nombre
        return ruta.read_bytes() if ruta.is_file() else None

    return desde_datos((carpeta / "manifest.json").read_bytes(), leer_lang)


def es_de_la_tienda(carpeta: Path) -> bool:
    """Si el pack lo instaló la tienda del juego, y no el usuario por su cuenta.

    El contenido comprado en el Marketplace viene cifrado y firmado: trae un
    `contents.json` con su cabecera binaria y un `signatures.json`. Ningún pack
    de los que se descargan por fuera los tiene — en el equipo de prueba, los 43
    de `com.mojang` no traen ninguno de los dos y los 4 de `premium_cache` traen
    ambos.

    Importa porque el juego gestiona ese contenido él solo: buscarle
    actualizaciones en un catálogo público es trabajo tirado, y desinstalarlo a
    mano es pelearse con el juego.
    """
    contents = carpeta / "contents.json"
    if contents.is_file():
        try:
            with contents.open("rb") as f:
                if f.read(8)[4:8] == MAGIA_CONTENTS:
                    return True
        except OSError:
            pass
    return (carpeta / "signatures.json").is_file()
