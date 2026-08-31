"""Pruebas de arrastrar y soltar sobre la ventana.

El gesto decide por lo que es cada cosa: un archivo que es contenido se instala,
una carpeta se empieza a vigilar, y lo demás se dice sin hacer nada. Se prueba la
lógica (`ui.soltar`), no los eventos de Qt: lo que puede equivocarse es la
decisión, no que Qt entregue el evento.
"""

import pytest
from conftest import escribir_zip, mundo, pack
from PySide6.QtCore import QCoreApplication, QMimeData, QUrl

from mcpemod.core import Installer, Scanner
from mcpemod.ui import soltar


@pytest.fixture(scope="session")
def qt_app():
    return QCoreApplication.instance() or QCoreApplication([])


@pytest.fixture
def entorno(store, instalacion, descargas, qt_app):
    scanner = Scanner(store, instalacion)
    return scanner, Installer(store, instalacion), instalacion, descargas


def _procesar(entorno, *rutas):
    scanner, installer, _, _ = entorno
    return soltar.procesar(list(rutas), scanner, installer)


# --- lectura del arrastre ---

def test_rutas_de_un_arrastre_de_archivos(tmp_path):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(tmp_path / "a.mcpack"))])
    assert soltar.rutas_de(mime) == [tmp_path / "a.mcpack"]

def test_arrastre_de_texto_no_trae_rutas():
    mime = QMimeData()
    mime.setText("solo texto")
    assert soltar.rutas_de(mime) == []

def test_arrastre_remoto_se_ignora():
    """Un arrastre desde el navegador puede traer una URL http, no un archivo."""
    mime = QMimeData()
    mime.setUrls([QUrl("https://ejemplo.com/pack.mcpack")])
    assert soltar.rutas_de(mime) == []

def test_admite_solo_lo_que_existe(tmp_path):
    existe = tmp_path / "hay.txt"
    existe.touch()
    assert soltar.admite([existe]) is True
    assert soltar.admite([tmp_path / "fantasma"]) is False


# --- soltar archivos ---

def test_soltar_un_pack_lo_instala(entorno, tmp_path):
    _, _, instalacion, _ = entorno
    ruta = pack(tmp_path / "fuera" / "Bonito.mcpack", nombre="Bonito", uuid="u")

    resultado = _procesar(entorno, ruta)
    assert resultado.instalados == ["Bonito"]
    assert (instalacion.resource_packs / "Bonito").is_dir()

def test_soltar_un_mundo_lo_instala(entorno, tmp_path):
    _, _, instalacion, _ = entorno
    resultado = _procesar(entorno, mundo(tmp_path / "fuera" / "MiMundo.mcworld"))
    assert (instalacion.mundos / "MiMundo").is_dir()
    assert resultado.instalados

def test_soltar_algo_que_no_es_contenido(entorno, tmp_path):
    ruta = escribir_zip(tmp_path / "fotos.zip", {"a.png": b"\x89PNG"})
    resultado = _procesar(entorno, ruta)
    assert resultado.ignorados == ["fotos.zip"]
    assert not resultado.instalados

def test_soltar_varios_a_la_vez(entorno, tmp_path):
    uno = pack(tmp_path / "fuera" / "Uno.mcpack", nombre="Uno", uuid="u-1")
    dos = pack(tmp_path / "fuera" / "Dos.mcpack", nombre="Dos", uuid="u-2", tipo="data")
    basura = tmp_path / "fuera" / "notas.txt"
    basura.write_text("hola")

    resultado = _procesar(entorno, uno, dos, basura)
    assert sorted(resultado.instalados) == ["Dos", "Uno"]
    assert resultado.ignorados == ["notas.txt"]

def test_soltar_el_mismo_pack_dos_veces_no_duplica(entorno, tmp_path):
    _, _, instalacion, _ = entorno
    ruta = pack(tmp_path / "fuera" / "Bonito.mcpack", nombre="Bonito", uuid="u")
    _procesar(entorno, ruta)
    _procesar(entorno, ruta)
    assert len(list(instalacion.resource_packs.iterdir())) == 1


# --- soltar carpetas ---

def test_soltar_una_carpeta_la_vigila(entorno, tmp_path):
    scanner = entorno[0]
    carpeta = tmp_path / "Mods bajados"
    carpeta.mkdir()

    resultado = _procesar(entorno, carpeta)
    assert resultado.carpetas == ["Mods bajados"]
    assert carpeta in scanner.carpetas()

def test_soltar_una_carpeta_ya_vigilada(entorno, descargas):
    resultado = _procesar(entorno, descargas)
    assert resultado.carpetas == []
    assert "ya vigilada" in resultado.ignorados[0]

def test_una_carpeta_no_se_intenta_instalar(entorno, tmp_path):
    """Una carpeta con un manifiesto dentro es ambigua: puede ser un pack
    extraído o el sitio donde se guardan las descargas. Vigilarla no destruye
    nada; instalarla por error, sí."""
    scanner, _, instalacion, _ = entorno
    carpeta = tmp_path / "un pack extraido"
    carpeta.mkdir()
    (carpeta / "manifest.json").write_text("{}")

    _procesar(entorno, carpeta)
    assert carpeta in scanner.carpetas()
    assert list(instalacion.resource_packs.iterdir()) == []


# --- mensajes ---

def test_el_mensaje_resume_lo_que_paso(entorno, tmp_path):
    uno = pack(tmp_path / "fuera" / "Uno.mcpack", nombre="Uno", uuid="u-1")
    carpeta = tmp_path / "Mods"
    carpeta.mkdir()
    basura = tmp_path / "fuera" / "notas.txt"
    basura.write_text("hola")

    mensaje = _procesar(entorno, uno, carpeta, basura).mensaje()
    assert "Instalado: Uno" in mensaje
    assert "Mods" in mensaje
    assert "notas.txt" in mensaje

def test_varios_ignorados_se_resumen(entorno, tmp_path):
    basuras = []
    for n in range(3):
        ruta = tmp_path / f"n{n}.txt"
        ruta.write_text("x")
        basuras.append(ruta)
    mensaje = _procesar(entorno, *basuras).mensaje()
    assert "3 archivos no son contenido de Bedrock" in mensaje

def test_ruta_inexistente_se_salta(entorno, tmp_path):
    resultado = _procesar(entorno, tmp_path / "fantasma.mcpack")
    assert not resultado.hubo_algo
