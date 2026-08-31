"""Pruebas del trabajo de red fuera del hilo de la interfaz.

Lo que se comprueba aquí no es la red sino **en qué hilo acaba corriendo cada
cosa**, que es lo que puede reventar la app sin dejar rastro: tocar un widget
desde otro hilo no da un error, da un volcado más adelante.

Detrás hay un descubrimiento que costó encontrar: una señal que cruza de hilo
solo llega bien al hilo de la interfaz si el slot es un método de un `QObject`
que vive allí. Conectada a una función suelta —una lambda, como hace el helper
`mcpemod.senales.conectar`— Qt la ejecuta en el hilo del emisor.
"""

import threading

import pytest
from PySide6.QtCore import QCoreApplication, QObject, QTimer

from mcpemod.senales import conectar
from mcpemod.ui.trabajo import HiloDeTrabajo
from mcpemod.ui.trabajo_catalogo import Explorador


@pytest.fixture(scope="session")
def qt_app():
    return QCoreApplication.instance() or QCoreApplication([])


class Receptor(QObject):
    def __init__(self):
        super().__init__()
        self.hilos = []
        self.recibido = []

    def recibir(self, *args):
        self.hilos.append(threading.get_ident())
        self.recibido.append(args)


class FuenteFalsa:
    nombre = "falsa"
    etiqueta = "Falsa"
    disponible = True

    def buscar(self, texto, pagina=1, por_pagina=20):
        return [f"buscado:{texto}"]

    def recientes(self, pagina=1, por_pagina=20):
        return ["reciente"]


def _correr_hasta(app, condicion, limite_ms=5000):
    fin = {"corta": False}
    QTimer.singleShot(limite_ms, lambda: (fin.update(corta=True), app.quit()))
    temporizador = QTimer()
    temporizador.setInterval(10)
    temporizador.timeout.connect(lambda: condicion() and app.quit())
    temporizador.start()
    app.exec()
    temporizador.stop()
    return not fin["corta"]


def test_el_slot_corre_en_el_hilo_de_la_interfaz(qt_app):
    """Es la razón de todo el aparato de trabajadores persistentes."""
    receptor = Receptor()
    trabajo = HiloDeTrabajo(Explorador())
    trabajo.trabajador.listo.connect(receptor.recibir)

    trabajo.trabajador.pedir.emit(FuenteFalsa(), "", 1, 1)
    assert _correr_hasta(qt_app, lambda: bool(receptor.hilos))
    trabajo.parar()

    assert receptor.hilos == [threading.get_ident()]


def test_una_lambda_no_vuelve_al_hilo_de_la_interfaz(qt_app):
    """Documenta el límite de `senales.conectar`, que envuelve en lambda.

    Si esto empieza a fallar es que Qt cambió de comportamiento y el aparato de
    trabajadores persistentes se puede simplificar.
    """
    receptor = Receptor()
    trabajo = HiloDeTrabajo(Explorador())
    conectar(trabajo.trabajador.listo, receptor.recibir)

    trabajo.trabajador.pedir.emit(FuenteFalsa(), "", 1, 1)
    assert _correr_hasta(qt_app, lambda: bool(receptor.hilos))
    trabajo.parar()

    assert receptor.hilos != [threading.get_ident()]


def test_la_consulta_llega_con_su_tanda(qt_app):
    receptor = Receptor()
    trabajo = HiloDeTrabajo(Explorador())
    trabajo.trabajador.listo.connect(receptor.recibir)

    trabajo.trabajador.pedir.emit(FuenteFalsa(), "xray", 1, 7)
    assert _correr_hasta(qt_app, lambda: bool(receptor.recibido))
    trabajo.parar()

    tanda, resultados, error = receptor.recibido[0]
    assert (tanda, resultados, error) == (7, ["buscado:xray"], "")


def test_sin_texto_pide_las_novedades(qt_app):
    receptor = Receptor()
    trabajo = HiloDeTrabajo(Explorador())
    trabajo.trabajador.listo.connect(receptor.recibir)

    trabajo.trabajador.pedir.emit(FuenteFalsa(), "   ", 1, 1)
    assert _correr_hasta(qt_app, lambda: bool(receptor.recibido))
    trabajo.parar()

    assert receptor.recibido[0][1] == ["reciente"]


def test_un_error_de_red_llega_como_mensaje(qt_app):
    from mcpemod.core.red import ErrorRed

    class Rota(FuenteFalsa):
        def recientes(self, pagina=1, por_pagina=20):
            raise ErrorRed("sin conexión")

    receptor = Receptor()
    trabajo = HiloDeTrabajo(Explorador())
    trabajo.trabajador.listo.connect(receptor.recibir)

    trabajo.trabajador.pedir.emit(Rota(), "", 1, 1)
    assert _correr_hasta(qt_app, lambda: bool(receptor.recibido))
    trabajo.parar()

    assert receptor.recibido[0][2] == "sin conexión"


def test_parar_deja_el_hilo_cerrado(qt_app):
    """Salir con un QThread corriendo termina en un volcado."""
    trabajo = HiloDeTrabajo(Explorador())
    trabajo.parar()
    assert not trabajo._hilo.isRunning()
