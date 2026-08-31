"""Pruebas del Scanner — lo que la app cree que hay instalado y descargado.

La fuente de verdad es el disco y no la base, porque el jugador importa packs
desde el propio juego sin pasar por el gestor. Una lista construida solo desde
la base no los mostraría.

Necesita un `QCoreApplication` porque `QFileSystemWatcher` es un objeto de Qt,
pero no toca la UI ni necesita pantalla.
"""

import json

import pytest
from conftest import escribir_zip, manifiesto, mundo, pack
from PySide6.QtCore import QCoreApplication

from mcpemod.core.contenido import Categoria
from mcpemod.core.scanner import Scanner


@pytest.fixture(scope="session")
def qt_app():
    return QCoreApplication.instance() or QCoreApplication([])


@pytest.fixture
def scanner(store, instalacion, descargas, qt_app):
    return Scanner(store, instalacion)


def _pack_instalado(carpeta, en_carpeta, **kwargs):
    destino = carpeta / en_carpeta
    destino.mkdir(parents=True)
    (destino / "manifest.json").write_text(json.dumps(manifiesto(**kwargs)))
    return destino


# --- instalados ---

def test_lee_lo_que_instalo_el_juego(scanner, instalacion):
    """Un pack importado desde el juego está en disco y no en la base."""
    _pack_instalado(instalacion.resource_packs, "HideArmorV",
                    nombre="Hide Armor", uuid="u-1", version=(1, 2, 0))
    piezas = scanner.leer_instalados()
    assert [p.nombre for p in piezas] == ["Hide Armor"]
    assert piezas[0].version == "1.2.0"
    assert piezas[0].ruta.name == "HideArmorV"

def test_indice_por_uuid(scanner, instalacion):
    _pack_instalado(instalacion.resource_packs, "Cualquiera", nombre="X", uuid="el-uuid")
    assert set(scanner.indice_por_uuid()) == {"el-uuid"}

def test_separa_por_categoria(scanner, instalacion):
    _pack_instalado(instalacion.resource_packs, "RP", nombre="RP", uuid="u-1")
    _pack_instalado(instalacion.behavior_packs, "BP", nombre="BP", uuid="u-2", tipo="data")
    categorias = {p.nombre: p.categoria for p in scanner.leer_instalados()}
    assert categorias == {"RP": Categoria.RECURSO, "BP": Categoria.COMPORTAMIENTO}

def test_ignora_carpetas_sin_manifiesto(scanner, instalacion):
    (instalacion.resource_packs / "basura").mkdir()
    assert scanner.leer_instalados() == []

def test_mundo_usa_su_levelname(scanner, instalacion):
    carpeta = instalacion.mundos / "bE2ZIuTv+eY="
    carpeta.mkdir()
    (carpeta / "level.dat").write_bytes(b"nivel")
    (carpeta / "levelname.txt").write_text("DurDream")
    piezas = scanner.leer_instalados()
    assert [(p.nombre, p.categoria) for p in piezas] == [("DurDream", Categoria.MUNDO)]


# --- lo que el juego no carga ---

def test_mcpack_sin_extraer_sale_inactivo(scanner, instalacion, tmp_path):
    """Está en la carpeta correcta, pero el juego solo abre carpetas."""
    origen = pack(tmp_path / "tmp.mcpack", nombre="Bonito", uuid="u")
    (instalacion.resource_packs / "Bonito.mcpack").write_bytes(origen.read_bytes())

    piezas = scanner.leer_instalados()
    assert [(p.nombre, p.activo) for p in piezas] == [("Bonito", False)]

def test_pack_anidado_sale_inactivo(scanner, instalacion):
    """El manifiesto está un nivel por debajo de donde lo busca el juego."""
    interior = instalacion.resource_packs / "JavaCombat" / "JavaCombat Bn"
    interior.mkdir(parents=True)
    (interior / "manifest.json").write_text(json.dumps(manifiesto(nombre="Java", uuid="u")))

    piezas = scanner.leer_instalados()
    assert [(p.nombre, p.activo) for p in piezas] == [("Java", False)]

def test_pack_normal_sale_activo(scanner, instalacion):
    _pack_instalado(instalacion.resource_packs, "Bonito", nombre="Bonito", uuid="u")
    assert scanner.leer_instalados()[0].activo is True


# --- descargas ---

def test_lee_solo_lo_instalable(scanner, descargas, tmp_path):
    pack(descargas / "Bonito.mcpack", nombre="Bonito", uuid="u")
    mundo(descargas / "MiMundo.mcworld")
    (descargas / "documento.pdf").write_bytes(b"%PDF-1.4")
    escribir_zip(descargas / "fotos.zip", {"a.png": b"\x89PNG"})

    nombres = [a.ruta.name for a in scanner.leer_descargas()]
    assert nombres == ["Bonito.mcpack", "MiMundo.mcworld"]

def test_carpeta_de_descargas_sin_contenido(scanner, descargas):
    assert scanner.leer_descargas() == []


# --- badge NEW ---

def test_es_nuevo_la_primera_vez(scanner, descargas):
    ruta = pack(descargas / "Bonito.mcpack", uuid="u")
    assert scanner.es_nuevo(ruta) is True
    assert scanner.es_nuevo(ruta) is True  # leerlo no lo apaga

def test_marcar_visto_apaga_el_aviso(scanner, descargas):
    ruta = pack(descargas / "Bonito.mcpack", uuid="u")
    scanner.marcar_vistos([ruta])
    assert scanner.es_nuevo(ruta) is False

def test_el_aviso_va_por_contenido_no_por_nombre(scanner, descargas):
    """La misma descarga con contenido nuevo es un archivo nuevo."""
    ruta = pack(descargas / "Bonito.mcpack", uuid="u", version=(1, 0, 0))
    scanner.marcar_vistos([ruta])
    pack(descargas / "Bonito.mcpack", uuid="u", version=(2, 0, 0))
    assert scanner.es_nuevo(ruta) is True


# --- señales e instalación activa ---

def test_notificar_cambio_emite_ambas(scanner):
    recibidas = []
    scanner.instalados_cambiados.connect(lambda: recibidas.append("instalados"))
    scanner.descargas_cambiadas.connect(lambda: recibidas.append("descargas"))
    scanner.notificar_cambio()
    assert recibidas == ["instalados", "descargas"]

def test_cambiar_instalacion(scanner, tmp_path, qt_app):
    from mcpemod.core.rutas import Instalacion

    otra_raiz = tmp_path / "otro_launcher"
    otra = Instalacion("otra", otra_raiz, otra_raiz / "games/com.mojang")
    for c in otra.directorios_contenido:
        c.mkdir(parents=True)
    _pack_instalado(otra.resource_packs, "Solo aquí", nombre="Solo aquí", uuid="u")

    assert scanner.leer_instalados() == []
    scanner.cambiar_instalacion(otra)
    assert [p.nombre for p in scanner.leer_instalados()] == ["Solo aquí"]
