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
_PRIVADOS = re.compile(r"[\ue000-\uf8ff]")
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
class Subpack:
    """Una variante del pack entre las que el jugador elige.

    La documentación oficial las describe como lo que son: *«sub-packs let
    players choose between different variations of a resource pack and switch
    between them at any time»*. No son packs aparte — son las **opciones** de
    este: hojas redondas o normales, con efectos o sin ellos, qué tan raras
    aparecen unas estructuras.

    `carpeta` es lo que se escribe en el archivo de activación y `nombre` lo que
    se le enseña a quien elige —*«the name players see when choosing your
    sub-pack»*—. No son lo mismo y confundirlos activa un subpack que no existe:
    en un pack de este equipo la carpeta es `with_vfx` y el nombre «With VFX
    effect».
    """

    carpeta: str
    nombre: str
    #: RAM mínima que pide, en tramos de 250 MB. El juego elige solo el más alto
    #: que quepa en el aparato, así que **no elegir no es no tener ninguno**.
    memoria: int | None = None


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
    #: Lo que el juego enseña bajo el nombre del pack.
    descripcion: str = ""
    subpacks: tuple[Subpack, ...] = field(default=())
    #: Los párrafos sueltos de `settings`, que la documentación describe como
    #: *«a description of what the pack and sub-packs include»*. Es donde algunos
    #: autores explican qué hace cada variante y qué hay que hacer para cambiarla.
    notas: tuple[str, ...] = field(default=())

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
    """Quita lo que solo tiene sentido dentro del juego.

    Los códigos `§x` con que los autores colorean el nombre, y los caracteres del
    **Área de Uso Privado** (U+E000–U+F8FF): son los glifos de la fuente de
    Minecraft —iconos de corazón, de comida, de escudo— y ahí dibujan algo, pero
    en cualquier otra fuente son cajas vacías. Un pack de este equipo llama a sus
    variantes `\uf14d Monochrome Icons`, y esa caja no aporta nada a quien elige.
    """
    return _PRIVADOS.sub("", _CODIGOS_COLOR.sub("", texto)).strip()


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
        descripcion=_texto_localizado(header.get("description"), leer_lang),
        subpacks=_subpacks(datos_json.get("subpacks"), leer_lang),
        notas=tuple(
            limpio
            for s in datos_json.get("settings") or []
            if isinstance(s, dict) and s.get("type") == "label"
            and (limpio := limpiar_formato(str(s.get("text", ""))).strip())
        ),
    )


def _texto_localizado(valor, leer_lang) -> str:
    """Un texto del manifiesto, resolviendo la clave si es una.

    La descripción admite lo mismo que el nombre: en vez del texto, la clave de
    un `.lang`. Sin resolverla se le enseña al usuario `pack.description`.
    """
    texto = limpiar_formato(str(valor or "")).strip()
    if _CLAVE_LOCALIZADA.match(texto) and leer_lang is not None:
        texto = limpiar_formato(_resolver_lang(texto, leer_lang) or texto).strip()
    return texto


def _subpacks(valor, leer_lang) -> tuple[Subpack, ...]:
    """Las variantes declaradas, con lo justo para elegir una.

    Hay autores que meten la explicación entera dentro del `name`, con saltos de
    línea: uno de este equipo escribe cuatro párrafos ahí. Para elegir hace falta
    una línea, así que se corta por el primer salto y lo demás se descarta —lo
    que explica el pack va en `notas`, que es su sitio—.
    """
    subpacks = []
    for s in valor or []:
        if not isinstance(s, dict) or not s.get("folder_name"):
            continue
        nombre = _texto_localizado(s.get("name"), leer_lang).splitlines()
        subpacks.append(Subpack(
            carpeta=str(s["folder_name"]),
            nombre=(nombre[0].strip() if nombre else "") or str(s["folder_name"]),
            memoria=s.get("memory_tier") if isinstance(s.get("memory_tier"), int) else None,
        ))
    return tuple(subpacks)


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
