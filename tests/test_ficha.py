"""La ficha de un pack, venga de donde venga.

Un pack instalado y un archivo de la carpeta de descargas tienen las mismas cosas
que contar, pero no son lo mismo: el segundo no está puesto en ninguna parte, así
que no puede elegirse su variante — la elección se guarda dentro de la entrada de
activación, y no tiene ninguna.

Si eso falla en silencio, la ficha ofrece elegir una variante y al aplicarla no
pasa nada, o peor, se escribe en la entrada de otro pack.
"""

import json

import pytest
from PySide6.QtWidgets import QApplication, QRadioButton

from mcpemod.core.activacion import Global
from mcpemod.core.contenido import Categoria, analizar
from mcpemod.core.manifiesto import desde_datos
from mcpemod.core.mod import Instalado
from mcpemod.ui.dialogo_pack import FichaPack, de_componente, de_instalado

from conftest import escribir_zip, manifiesto


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication([])


CON_VARIANTES = dict(subpacks=[
    {"folder_name": "sp1", "name": "Una"},
    {"folder_name": "sp2", "name": "Otra"},
])


def _instalado(instalacion, uuid="aaaaaaaa-1111-1111-1111-111111111111"):
    carpeta = instalacion.com_mojang / "resource_packs" / "P"
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "manifest.json").write_text(
        json.dumps(manifiesto(nombre="P", uuid=uuid, **CON_VARIANTES))
    )
    return Instalado(uuid=uuid, nombre="P", version="1.0.0",
                     categoria=Categoria.RECURSO, ruta=carpeta)


def test_un_pack_de_descargas_no_ofrece_elegir_variante(qt_app, tmp_path, instalacion):
    """Enseñarlas sí: son parte de lo que trae. Pero no hay entrada de activación
    donde guardar la elección, así que ofrecerla sería un botón que no hace nada.
    """
    archivo = escribir_zip(tmp_path / "x.mcpack", {
        "manifest.json": json.dumps(manifiesto(**CON_VARIANTES)),
    })
    analisis = analizar(archivo)
    ficha = FichaPack(
        de_componente(analisis.ruta, analisis.componentes[0]),
        # Aunque le pasen un ámbito: lo que decide es que no está instalado.
        ambito=Global(instalacion), activo=True,
    )
    assert not ficha.hay_variantes_que_guardar
    assert not ficha.findChildren(QRadioButton)


def test_un_pack_instalado_y_activo_si_la_ofrece(qt_app, instalacion):
    general = Global(instalacion)
    pieza = _instalado(instalacion)
    general.activar(pieza)

    ficha = FichaPack(
        de_instalado(pieza, desde_datos(
            (pieza.ruta / "manifest.json").read_bytes())),
        ambito=general, activo=True,
    )
    assert ficha.hay_variantes_que_guardar
    # Las dos variantes más «lo elige el juego», que no es lo mismo que ninguna.
    assert len(ficha.findChildren(QRadioButton)) == 3


def test_un_pack_instalado_pero_no_activo_no_la_ofrece(qt_app, instalacion):
    pieza = _instalado(instalacion)
    ficha = FichaPack(
        de_instalado(pieza, desde_datos(
            (pieza.ruta / "manifest.json").read_bytes())),
        ambito=Global(instalacion), activo=False,
    )
    assert not ficha.hay_variantes_que_guardar


def test_guardar_escribe_la_carpeta_y_no_el_nombre(qt_app, instalacion):
    """Es el fallo que el juego no perdona: escribir «Una» donde va `sp1` lo deja
    buscando una variante que no existe, y el pack se aplica sin ella."""
    general = Global(instalacion)
    pieza = _instalado(instalacion)
    general.activar(pieza)

    ficha = FichaPack(
        de_instalado(pieza, desde_datos(
            (pieza.ruta / "manifest.json").read_bytes())),
        ambito=general, activo=True,
    )
    radios = ficha.findChildren(QRadioButton)
    radios[1].setChecked(True)          # la primera variante de verdad
    assert ficha.guardar_variante() is None
    assert general.subpack_de(pieza) == "sp1"


def test_un_pack_sin_manifiesto_legible_abre_la_ficha_igual(qt_app, instalacion):
    """Con lo que ya se sabe del pack. Es más útil que un error."""
    pieza = _instalado(instalacion)
    ficha = FichaPack(de_instalado(pieza, None))
    assert not ficha.hay_variantes_que_guardar
