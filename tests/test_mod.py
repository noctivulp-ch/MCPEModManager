"""Pruebas del modelo de datos Mod.

`TipoArchivo.desde_ruta()` y `Mod.calcular_hash()` son primitivas que el
resto del sistema asume correctas. `desde_ruta()` determina qué ruta de
instalación toma un archivo; si devuelve el tipo equivocado, un `.mcpack` se
copiaría a `mods/` como si fuera `.so` y no funcionaría.

`calcular_hash()` alimenta el badge NEW — el test del archivo vacío existe
porque SHA-256 del vacío es un valor conocido y estable; si cambia, algo muy
raro pasó con la implementación.
"""

import hashlib
from pathlib import Path

from mcpemod.core.mod import TipoArchivo


def test_tipo_desde_ruta_so():
    assert TipoArchivo.desde_ruta(Path("mod.so")) == TipoArchivo.SO

def test_tipo_desde_ruta_mcpack():
    assert TipoArchivo.desde_ruta(Path("pack.mcpack")) == TipoArchivo.MCPACK

def test_tipo_desde_ruta_mcaddon():
    assert TipoArchivo.desde_ruta(Path("addon.mcaddon")) == TipoArchivo.MCADDON

def test_tipo_desde_ruta_zip():
    assert TipoArchivo.desde_ruta(Path("pack.zip")) == TipoArchivo.ZIP

def test_tipo_desde_ruta_desconocido():
    assert TipoArchivo.desde_ruta(Path("archivo.txt")) is None

def test_tipo_valor():
    assert TipoArchivo.SO.value == ".so"
    assert TipoArchivo.MCPACK.value == ".mcpack"


def test_calcular_hash(tmp_path):
    from mcpemod.core.mod import Mod
    archivo = tmp_path / "test.so"
    archivo.write_bytes(b"contenido de prueba")
    esperado = hashlib.sha256(b"contenido de prueba").hexdigest()
    assert Mod.calcular_hash(archivo) == esperado

def test_calcular_hash_vacio(tmp_path):
    from mcpemod.core.mod import Mod
    archivo = tmp_path / "vacio.so"
    archivo.write_bytes(b"")
    esperado = hashlib.sha256(b"").hexdigest()
    assert Mod.calcular_hash(archivo) == esperado
