"""Pruebas de la columna de activación: dónde acaba un pack al moverlo.

Lo que se comprueba es **dónde cae**, que es lo que decide cuál gana cuando dos
packs tocan lo mismo — el juego aplica el último—. Los eventos de ratón no se
simulan: el gesto se prueba llamando al coordinador, que es donde está la
decisión, y no en el camino que la dispara.

Si esto falla en silencio, arrastrar un pack lo deja un sitio más allá del hueco
que se enseñó al soltarlo, y eso no se ve hasta entrar al juego.
"""

from pathlib import Path

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QWidget

from mcpemod.core.contenido import Categoria
from mcpemod.core.mod import Instalado
from mcpemod.ui.widgets.arrastre import Arrastre, Capsula, Hueco
from mcpemod.ui.widgets.columna_packs import ColumnaPacks, FilaPack


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


@pytest.fixture
def escena(qt_app, columna):
    """Las dos columnas viven bajo un padre común, como en el panel."""
    padre = QWidget()
    padre.resize(700, 400)
    columna.setParent(padre)
    columna.move(0, 0)

    arrastre = Arrastre(padre)
    arrastre.registrar(columna)
    columna.arrastre = arrastre
    padre.show()
    qt_app.processEvents()
    return padre, columna, arrastre


def test_cada_fila_lleva_su_asa(columna):
    """Se arrastra por el asa y no por la fila entera: si no, desplazar la lista
    con el ratón sería imposible."""
    from mcpemod.ui.widgets.columna_packs import Asa

    filas = columna.findChildren(FilaPack)
    assert filas
    assert all(f.findChildren(Asa) for f in filas)


def test_el_hueco_se_decide_por_el_centro_de_cada_fila(columna):
    """Soltar en la mitad de arriba de una fila pone antes; en la de abajo,
    después. Es lo que uno espera al colocar algo entre dos cosas."""
    fila = columna._filas[1]
    centro = fila.mapTo(columna, fila.rect().center()).y()
    assert columna._posicion_en(centro - 5) == 1
    assert columna._posicion_en(centro + 5) == 2


def test_soltar_al_final_cae_despues_de_todo(columna):
    assert columna._posicion_en(5000) == len(columna._filas)


def test_la_fila_escondida_no_cuenta_para_la_posicion(columna, qt_app):
    """La que se arrastra está oculta, y quien recibe la posición reinserta sobre
    una lista de la que ya la ha quitado.

    Contándola, todo lo que cayera por debajo del pack movido se colocaba un
    sitio más allá del hueco que se enseñó — y el orden es justo lo que decide
    qué textura se ve.
    """
    columna._filas[0].hide()
    qt_app.processEvents()
    assert columna._posicion_en(5000) == len(columna._filas) - 1


def test_al_levantar_un_pack_desaparece_de_la_lista(escena, qt_app):
    _, columna, arrastre = escena
    fila = columna._filas[1]

    arrastre.empezar(fila, columna, columna.mapToGlobal(QPoint(10, 10)))
    qt_app.processEvents()

    assert not fila.isVisible()
    assert arrastre.activo


def test_lo_que_se_sostiene_no_lleva_botones(escena, qt_app):
    """En el agarre no se pulsa nada: la cápsula es el nombre y la versión."""
    padre, columna, arrastre = escena
    arrastre.empezar(columna._filas[0], columna, columna.mapToGlobal(QPoint(10, 10)))
    qt_app.processEvents()

    capsulas = padre.findChildren(Capsula)
    assert len(capsulas) == 1
    from PySide6.QtWidgets import QPushButton
    assert not capsulas[0].findChildren(QPushButton)


def test_el_hueco_se_pone_donde_va_a_caer(escena, qt_app):
    padre, columna, arrastre = escena
    arrastre.empezar(columna._filas[0], columna, columna.mapToGlobal(QPoint(10, 10)))
    qt_app.processEvents()

    assert columna.findChildren(Hueco)


def test_cancelar_devuelve_el_pack_a_su_sitio(escena, qt_app):
    """Con Escape no se mueve nada: la fila vuelve y el hueco se va."""
    padre, columna, arrastre = escena
    fila = columna._filas[2]
    arrastre.empezar(fila, columna, columna.mapToGlobal(QPoint(10, 10)))
    qt_app.processEvents()

    arrastre.cancelar()
    qt_app.processEvents()

    assert fila.isVisible()
    assert not arrastre.activo
    assert not columna.findChildren(Hueco)


def test_soltar_avisa_de_donde_cayo(escena, qt_app):
    padre, columna, arrastre = escena
    recibido = []
    columna.soltado.connect(lambda u, i: recibido.append((u, i)))

    fila = columna._filas[3]
    # Arriba del todo: cae en la primera posición.
    arrastre.empezar(fila, columna, columna.mapToGlobal(QPoint(10, 0)))
    qt_app.processEvents()
    arrastre.soltar()

    assert recibido == [("u-3", 0)]


def test_no_se_desplaza_solo_en_el_centro_de_la_lista(columna):
    vista = columna._scroll.viewport()
    medio = vista.mapToGlobal(QPoint(vista.width() // 2, vista.height() // 2))
    assert columna.paso_de_borde(medio, banda=56, maximo=22) == 0


def test_cerca_del_borde_la_lista_se_desplaza_sola(columna):
    """Sin esto, llevar un pack a un sitio que no está en pantalla obliga a
    soltarlo a medio camino y volver a cogerlo."""
    vista = columna._scroll.viewport()
    arriba = vista.mapToGlobal(QPoint(vista.width() // 2, 2))
    abajo = vista.mapToGlobal(QPoint(vista.width() // 2, vista.height() - 2))

    assert columna.paso_de_borde(arriba, banda=56, maximo=22) < 0
    assert columna.paso_de_borde(abajo, banda=56, maximo=22) > 0


def test_el_desplazamiento_es_proporcional_a_lo_cerca_que_esta_el_borde(columna):
    """A saltos fijos es imposible parar donde uno quiere."""
    vista = columna._scroll.viewport()
    rozando = vista.mapToGlobal(QPoint(vista.width() // 2, 50))
    pegado = vista.mapToGlobal(QPoint(vista.width() // 2, 2))

    assert abs(columna.paso_de_borde(rozando, banda=56, maximo=22)) < \
           abs(columna.paso_de_borde(pegado, banda=56, maximo=22))
