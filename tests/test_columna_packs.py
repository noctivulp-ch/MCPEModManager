"""Pruebas de la columna de activación: mover packs de las tres formas.

Lo que se comprueba es **dónde acaba** un pack al soltarlo o pegarlo, que es lo
que decide qué gana cuando dos tocan lo mismo. Los eventos de ratón de Qt no se
prueban aquí; sí la decisión de en qué hueco cae.
"""

from pathlib import Path

import pytest
from PySide6.QtCore import QMimeData, QPoint, Qt
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QApplication

from mcpemod.core.contenido import Categoria
from mcpemod.core.mod import Instalado
from mcpemod.ui.widgets.columna_packs import MIME_PACK, ColumnaPacks, FilaPack


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication([])


def _pieza(nombre, uuid):
    return Instalado(uuid=uuid, nombre=nombre, version="1.0.0",
                     categoria=Categoria.RECURSO, ruta=Path("/tmp/x"))


@pytest.fixture
def columna(qt_app):
    c = ColumnaPacks("Aplicados", "vacío")
    c.resize(300, 400)
    c.poner([_pieza(f"Pack {i}", f"u-{i}") for i in range(4)],
            activo=True, agrupado=False)
    c.show()
    qt_app.processEvents()
    return c


def test_cada_fila_lleva_su_asa(columna):
    """Se arrastra por el asa y no por la fila entera: si no, desplazar la lista
    con el ratón sería imposible."""
    from mcpemod.ui.widgets.columna_packs import Asa

    filas = columna.findChildren(FilaPack)
    assert filas
    assert all(f.findChildren(Asa) for f in filas)


def test_soltar_arriba_del_todo_cae_en_la_primera_posicion(columna, qt_app):
    recibido = []
    columna.soltado.connect(lambda u, i: recibido.append((u, i)))

    datos = QMimeData()
    datos.setData(MIME_PACK, b"u-nuevo")
    columna.dropEvent(QDropEvent(QPoint(10, 0), Qt.DropAction.MoveAction, datos,
                                 Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
    assert recibido == [("u-nuevo", 0)]


def test_soltar_al_final_cae_despues_de_todo(columna, qt_app):
    recibido = []
    columna.soltado.connect(lambda u, i: recibido.append((u, i)))

    datos = QMimeData()
    datos.setData(MIME_PACK, b"u-nuevo")
    columna.dropEvent(QDropEvent(QPoint(10, 5000), Qt.DropAction.MoveAction, datos,
                                 Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
    assert recibido[0][1] == len(columna._filas)


def test_lo_que_no_es_un_pack_no_se_acepta(columna):
    recibido = []
    columna.soltado.connect(lambda u, i: recibido.append((u, i)))

    datos = QMimeData()
    datos.setText("un texto cualquiera")
    columna.dropEvent(QDropEvent(QPoint(10, 10), Qt.DropAction.MoveAction, datos,
                                 Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
    assert recibido == []


def test_el_hueco_se_decide_por_el_centro_de_cada_fila(columna, qt_app):
    """Soltar en la mitad de arriba de una fila pone antes; en la de abajo,
    después. Es lo que uno espera al colocar algo entre dos cosas."""
    fila = columna._filas[1]
    centro = fila.mapTo(columna, fila.rect().center()).y()
    assert columna._posicion_en(centro - 5) == 1
    assert columna._posicion_en(centro + 5) == 2
