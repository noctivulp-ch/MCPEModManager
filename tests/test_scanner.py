"""Pruebas del Scanner — lo que la app cree que hay puesto y descargado.

Necesita un `QCoreApplication` porque `QFileSystemWatcher` es un objeto de Qt,
pero no toca la UI ni necesita display: el escaneo en sí es lógica pura sobre
directorios de `tmp_path`.
"""

import io
import json
import zipfile

import pytest
from PySide6.QtCore import QCoreApplication

from mcpemod.core import scanner as modulo_scanner
from mcpemod.core.mod import Mod, TipoArchivo
from mcpemod.core.scanner import Scanner
from mcpemod.core.store import Store


@pytest.fixture(scope="session")
def qt_app():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


@pytest.fixture
def entorno(tmp_path, monkeypatch, qt_app):
    mods = tmp_path / "mods"
    descargas = tmp_path / "Downloads"
    mods.mkdir()
    descargas.mkdir()

    monkeypatch.setattr(modulo_scanner, "MODS_DIR", mods)
    monkeypatch.setattr(modulo_scanner, "DESCARGAS_DIR", descargas)
    monkeypatch.setattr(modulo_scanner, "DIRECTORIOS_INSTALACION", (mods,))

    store = Store(tmp_path / "test.db")
    return {"store": store, "scanner": Scanner(store), "mods": mods, "descargas": descargas}


def _pack(destino, version=(1, 0, 0)):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"header": {"version": list(version)}}))
    destino.write_bytes(buf.getvalue())
    return destino


# --- instalados ---

def test_detecta_so_puesto_a_mano(entorno):
    """Un `.so` copiado a `mods/` sin pasar por el gestor sigue siendo un mod puesto."""
    (entorno["mods"] / "Suelto-v1.0.0.so").write_bytes(b"ELF")
    instalados = entorno["scanner"].leer_instalados()
    assert [m.nombre for m in instalados] == ["Suelto-v1.0.0"]
    assert instalados[0].version == "1.0.0"

def test_ignora_archivos_no_so_en_mods(entorno):
    (entorno["mods"] / "leeme.txt").write_text("hola")
    assert entorno["scanner"].leer_instalados() == []

def test_incluye_packs_registrados(entorno, tmp_path):
    """Un pack extraído no vive en `mods/`: sin la base no aparecería en la lista."""
    carpeta = tmp_path / "resource_packs" / "Bonito"
    carpeta.mkdir(parents=True)
    entorno["store"].guardar_mod(Mod(
        nombre="Bonito", canonico="Bonito", archivo="Bonito.mcpack",
        rutas=[carpeta], tipo=TipoArchivo.MCPACK, version="1.0.0",
        hash_sha256="h", instalado=True,
    ))
    assert [m.nombre for m in entorno["scanner"].leer_instalados()] == ["Bonito"]

def test_purga_lo_borrado_por_fuera(entorno, tmp_path):
    entorno["store"].guardar_mod(Mod(
        nombre="Fantasma", canonico="Fantasma", archivo="Fantasma.mcpack",
        rutas=[tmp_path / "no_existe"], tipo=TipoArchivo.MCPACK, version="1.0.0",
        hash_sha256="h", instalado=True,
    ))
    assert entorno["scanner"].leer_instalados() == []
    assert entorno["store"].mods_instalados() == []

def test_no_duplica_lo_ya_registrado(entorno):
    ruta = entorno["mods"] / "MyMod-v1.0.0.so"
    ruta.write_bytes(b"ELF")
    entorno["store"].guardar_mod(Mod(
        nombre="MyMod-v1.0.0", canonico="MyMod", archivo="MyMod-v1.0.0.so",
        rutas=[ruta], tipo=TipoArchivo.SO, version="1.0.0",
        hash_sha256="h", instalado=True,
    ))
    assert len(entorno["scanner"].leer_instalados()) == 1


# --- descargas ---

def test_lee_descargas_soportadas(entorno):
    (entorno["descargas"] / "MyMod-v1.0.0.so").write_bytes(b"ELF")
    _pack(entorno["descargas"] / "Bonito.mcpack")
    (entorno["descargas"] / "documento.pdf").write_bytes(b"%PDF")

    nombres = [m.archivo for m in entorno["scanner"].leer_descargas()]
    assert nombres == ["Bonito.mcpack", "MyMod-v1.0.0.so"]

def test_ignora_descarga_incompleta(entorno):
    """Un zip a medias existe pero no se puede abrir: mostrarlo solo produce un
    error al pulsar Instalar."""
    (entorno["descargas"] / "medio.mcpack").write_bytes(b"PK\x03\x04 truncado")
    (entorno["descargas"] / "vacio.so").write_bytes(b"")
    assert entorno["scanner"].leer_descargas() == []

def test_badge_new_la_primera_vez(entorno):
    (entorno["descargas"] / "MyMod-v1.0.0.so").write_bytes(b"ELF")
    scanner = entorno["scanner"]

    mods = scanner.leer_descargas()
    assert mods[0].primera_vez is True

    # Leer de nuevo no apaga el aviso: solo lo apaga mirarlo.
    assert scanner.leer_descargas()[0].primera_vez is True

    scanner.marcar_vistas(mods)
    assert scanner.leer_descargas()[0].primera_vez is False

def test_badge_new_reaparece_si_cambia_el_contenido(entorno):
    """El aviso va por hash, no por nombre: la misma descarga con contenido
    nuevo es un archivo nuevo aunque se llame igual."""
    ruta = entorno["descargas"] / "MyMod.so"
    ruta.write_bytes(b"ELF v1")
    scanner = entorno["scanner"]
    scanner.marcar_vistas(scanner.leer_descargas())

    ruta.write_bytes(b"ELF v2")
    assert scanner.leer_descargas()[0].primera_vez is True

def test_canonico_enlaza_descarga_con_instalado(entorno):
    (entorno["mods"] / "MyMod-v1.0.0.so").write_bytes(b"ELF")
    (entorno["descargas"] / "MyMod-v2.0.0.so").write_bytes(b"ELF2")
    scanner = entorno["scanner"]

    instalado = scanner.leer_instalados()[0]
    descarga = scanner.leer_descargas()[0]
    assert instalado.canonico == descarga.canonico == "MyMod"


# --- señales ---

def test_notificar_cambio_emite_ambas(entorno):
    recibidas = []
    entorno["scanner"].mods_cambiados.connect(lambda: recibidas.append("mods"))
    entorno["scanner"].descargas_cambiadas.connect(lambda: recibidas.append("descargas"))
    entorno["scanner"].notificar_cambio()
    assert recibidas == ["mods", "descargas"]
