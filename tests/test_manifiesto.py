"""Pruebas de lectura del `manifest.json`.

El manifiesto es la única fuente fiable de identidad: el `header.uuid` es lo que
usa el propio juego para reconocer un pack, y lo que permite saber que dos
archivos con nombres distintos son el mismo contenido.

Los casos raros de aquí no son hipotéticos: salen de los 43 manifiestos
instalados en un equipo real — comentarios `//` en el JSON, nombres con códigos
de color `§`, y nombres que en realidad son claves de localización.
"""

import json

import pytest

from mcpemod.core.manifiesto import (
    ManifiestoInvalido, cargar_json, desde_datos, limpiar_formato,
)


def _bytes(datos: dict) -> bytes:
    return json.dumps(datos).encode()


# --- JSON tolerante ---

def test_json_normal():
    assert cargar_json(b'{"a": 1}') == {"a": 1}

def test_json_con_bom():
    assert cargar_json('﻿{"a": 1}'.encode()) == {"a": 1}

def test_json_con_comentarios():
    # Un pack real del equipo de prueba trae los `subpacks` comentados con `//`.
    crudo = b'{\n "a": 1,\n // "subpacks": [],\n "b": 2\n}'
    assert cargar_json(crudo) == {"a": 1, "b": 2}

def test_json_con_comentarios_de_bloque():
    assert cargar_json(b'{"a": 1 /* nota */, "b": 2}') == {"a": 1, "b": 2}

def test_json_con_coma_colgante():
    assert cargar_json(b'{"a": 1, "b": [1, 2,],}') == {"a": 1, "b": [1, 2]}

def test_json_no_destroza_las_urls():
    # Quitar `//` a lo bruto rompería la url del campo `metadata`.
    datos = cargar_json(b'{"url": "https://ejemplo.com/x", "a": 1, /* c */ "b": 2}')
    assert datos["url"] == "https://ejemplo.com/x"

def test_json_irrecuperable():
    with pytest.raises(ManifiestoInvalido):
        cargar_json(b"{esto no es json")


# --- nombre ---

def test_limpiar_codigos_de_color():
    assert limpiar_formato("§fHide §bArmor§6 | §aV1.2§r") == "Hide Armor | V1.2"

def test_nombre_se_limpia_al_leer():
    m = desde_datos(_bytes({"header": {"name": "§2Mutant §3Creatures§r", "uuid": "u",
                                       "version": [1, 0, 0]},
                            "modules": [{"type": "resources"}]}))
    assert m.nombre == "Mutant Creatures"

def test_nombre_localizado_se_resuelve():
    """`header.name` puede ser una clave, no un nombre.

    Cuatro packs del equipo de prueba se llaman literalmente `pack.name`; su
    nombre real está en `texts/en_US.lang`.
    """
    def leer_lang(archivo):
        return b"pack.name=Farmer's Delight[RP]\n" if archivo == "en_US.lang" else None

    m = desde_datos(
        _bytes({"header": {"name": "pack.name", "uuid": "u", "version": [1, 0, 0]},
                "modules": [{"type": "resources"}]}),
        leer_lang=leer_lang,
    )
    assert m.nombre == "Farmer's Delight[RP]"

def test_nombre_localizado_sin_traduccion_se_queda_igual():
    m = desde_datos(
        _bytes({"header": {"name": "pack.name", "uuid": "u", "version": [1, 0, 0]},
                "modules": [{"type": "resources"}]}),
        leer_lang=lambda _: None,
    )
    assert m.nombre == "pack.name"


# --- versión ---

def test_version_como_lista():
    m = desde_datos(_bytes({"header": {"name": "x", "uuid": "u", "version": [1, 5, 0]},
                            "modules": [{"type": "resources"}]}))
    assert m.version == "1.5.0"

def test_version_como_texto():
    m = desde_datos(_bytes({"header": {"name": "x", "uuid": "u", "version": "3.0.0"},
                            "modules": [{"type": "resources"}]}))
    assert m.version == "3.0.0"

def test_sin_version():
    m = desde_datos(_bytes({"header": {"name": "x", "uuid": "u"},
                            "modules": [{"type": "resources"}]}))
    assert m.version is None


# --- es_bedrock ---

def test_pack_de_bedrock_es_valido():
    m = desde_datos(_bytes({"header": {"name": "x", "uuid": "u", "version": [1, 0, 0]},
                            "modules": [{"type": "resources"}]}))
    assert m.es_bedrock

def test_modpack_de_curseforge_no_es_bedrock():
    """Un modpack de Java trae `manifest.json` en la raíz del zip igual que un pack.

    Sin este filtro el gestor ofrecería instalar los modpacks de Forge que hay
    en cualquier carpeta de descargas.
    """
    m = desde_datos(_bytes({
        "manifestType": "minecraftModpack", "manifestVersion": 1,
        "name": "DeceasedCraft", "version": "5.10.16",
        "minecraft": {"version": "1.20.1"}, "files": [],
    }))
    assert not m.es_bedrock

def test_sin_uuid_no_es_bedrock():
    m = desde_datos(_bytes({"header": {"name": "x", "version": [1, 0, 0]},
                            "modules": [{"type": "resources"}]}))
    assert not m.es_bedrock

def test_tipo_de_modulo_desconocido_no_es_bedrock():
    m = desde_datos(_bytes({"header": {"name": "x", "uuid": "u", "version": [1, 0, 0]},
                            "modules": [{"type": "lo_que_sea"}]}))
    assert not m.es_bedrock

def test_dependencias():
    m = desde_datos(_bytes({
        "header": {"name": "x", "uuid": "u", "version": [1, 0, 0]},
        "modules": [{"type": "data"}],
        "dependencies": [{"uuid": "OTRO-UUID", "version": [1, 0, 0]}],
    }))
    assert m.dependencias == ("otro-uuid",)
