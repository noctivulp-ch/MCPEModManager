"""Rutas de importación y constructores de contenido de Bedrock sintético.

Los packs de prueba se construyen aquí en vez de guardarse como archivos porque
lo que se prueba es la lectura del manifiesto: tener el JSON a la vista en el
test es lo que hace evidente qué caso cubre cada uno.
"""

import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parents[1]
for _ruta in (_RAIZ / "src", _RAIZ.parent / "#Libs/wulfenite_ui/PyQT/src"):
    if str(_ruta) not in sys.path:
        sys.path.insert(0, str(_ruta))


def manifiesto(nombre="Pack", uuid="11111111-1111-1111-1111-111111111111",
               version=(1, 0, 0), tipo="resources", **extra):
    datos = {
        "format_version": 2,
        "header": {"name": nombre, "uuid": uuid, "version": list(version)},
        "modules": [{"type": tipo, "uuid": uuid, "version": list(version)}],
    }
    datos.update(extra)
    return datos


def escribir_zip(destino: Path, miembros: dict[str, bytes | str]) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w") as zf:
        for nombre, datos in miembros.items():
            zf.writestr(nombre, datos if isinstance(datos, bytes) else str(datos))
    return destino


def pack(destino: Path, prefijo="", **kwargs) -> Path:
    """Un pack de Bedrock con su manifiesto y un archivo de contenido."""
    return escribir_zip(destino, {
        f"{prefijo}manifest.json": json.dumps(manifiesto(**kwargs)),
        f"{prefijo}pack_icon.png": b"\x89PNG",
    })


def addon(destino: Path, packs: dict[str, dict]) -> Path:
    """Un `.mcaddon`: un zip que contiene varios `.mcpack`."""
    miembros = {}
    for nombre_interno, kwargs in packs.items():
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as interno:
            interno.writestr("manifest.json", json.dumps(manifiesto(**kwargs)))
            interno.writestr("contenido.txt", nombre_interno)
        miembros[nombre_interno] = buf.getvalue()
    return escribir_zip(destino, miembros)


def mundo(destino: Path, nombre="Mi mundo", prefijo="") -> Path:
    return escribir_zip(destino, {
        f"{prefijo}level.dat": b"\x00\x00\x00\x08nivel",
        f"{prefijo}levelname.txt": nombre,
        f"{prefijo}db/000001.log": b"datos",
    })


@pytest.fixture
def instalacion(tmp_path):
    """Una instalación del juego vacía, con la estructura que crea Bedrock."""
    from mcpemod.core.rutas import Instalacion

    raiz = tmp_path / "launcher"
    inst = Instalacion("prueba", raiz, raiz / "games/com.mojang")
    for carpeta in inst.directorios_contenido:
        carpeta.mkdir(parents=True)
    return inst


@pytest.fixture
def store(tmp_path):
    from mcpemod.core.store import Store
    return Store(tmp_path / "prueba.db")


@pytest.fixture
def descargas(tmp_path, monkeypatch):
    """Carpeta de descargas aislada, sustituyendo la detección por XDG."""
    from mcpemod.core import rutas, scanner

    carpeta = tmp_path / "Descargas"
    carpeta.mkdir()
    monkeypatch.setattr(rutas, "carpeta_descargas", lambda: carpeta)
    monkeypatch.setattr(scanner, "carpeta_descargas", lambda: carpeta)
    return carpeta
