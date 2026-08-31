"""Pruebas del trabajo en segundo plano.

Lo que se comprueba no es la red sino **en qué hilo acaba corriendo cada cosa**,
que es lo que puede reventar la app sin dejar rastro: tocar un widget desde otro
hilo no da un error, da un volcado más adelante.

Detrás hay dos hallazgos que costaron encontrar y que se contradicen entre sí:

- Una señal que cruza de hilo solo llega bien al hilo de la interfaz si el slot
  es un método de un `QObject` que vive allí. Con una lambda, Qt la ejecuta en el
  hilo del emisor.
- Conectar un método de objeto es justo lo que rompe el binario compilado: el
  fallo de Nuitka salta en la **segunda** conexión de cualquier método.

Como no se pueden cumplir las dos, no se cruza de hilo con Qt: el trabajo deja
sus resultados en una cola que un `QTimer` del hilo de la interfaz vacía.
"""

import threading

import pytest
from PySide6.QtCore import QCoreApplication, QTimer

from mcpemod.ui.tareas import Tarea


@pytest.fixture(scope="session")
def qt_app():
    return QCoreApplication.instance() or QCoreApplication([])


def _correr_hasta(app, condicion, limite_ms=4000):
    """Deja correr el bucle de eventos hasta que se cumpla `condicion`."""
    agotado = {"si": False}
    tope = QTimer()
    tope.setSingleShot(True)
    tope.timeout.connect(lambda: (agotado.update(si=True), app.quit()))
    tope.start(limite_ms)

    reloj = QTimer()
    reloj.setInterval(10)
    reloj.timeout.connect(lambda: condicion() and app.quit())
    reloj.start()

    app.exec()
    reloj.stop()
    tope.stop()
    return not agotado["si"]


def test_los_mensajes_llegan_en_el_hilo_de_la_interfaz(qt_app):
    """Es la razón de que el trabajo no use señales de Qt entre hilos."""
    recibidos = []
    tarea = Tarea()

    def trabajo(emitir, cancelado):
        emitir("hola", threading.get_ident())

    tarea.lanzar(trabajo, lambda m: recibidos.append((m, threading.get_ident())))
    assert _correr_hasta(qt_app, lambda: bool(recibidos))
    tarea.parar()

    (mensaje, hilo_receptor), = recibidos
    assert mensaje[0] == "hola"
    assert hilo_receptor == threading.get_ident()
    # Y el trabajo sí corrió fuera: si no, no habría hecho falta nada de esto.
    assert mensaje[1] != threading.get_ident()


def test_los_mensajes_llegan_en_orden(qt_app):
    recibidos = []
    tarea = Tarea()
    tarea.lanzar(
        lambda emitir, cancelado: [emitir("n", i) for i in range(5)],
        lambda m: recibidos.append(m[1]),
    )
    assert _correr_hasta(qt_app, lambda: len(recibidos) == 5)
    tarea.parar()
    assert recibidos == [0, 1, 2, 3, 4]


def test_solo_un_trabajo_a_la_vez(qt_app):
    """Los paneles hacen uno por vez; así no hay que ordenar respuestas."""
    puerta = threading.Event()
    tarea = Tarea()

    assert tarea.lanzar(lambda emitir, cancelado: puerta.wait(2), lambda m: None)
    assert tarea.lanzar(lambda emitir, cancelado: None, lambda m: None) is False

    puerta.set()
    tarea.parar()


def test_cancelar_se_ve_desde_el_trabajo(qt_app):
    visto = []
    tarea = Tarea()

    def trabajo(emitir, cancelado):
        for i in range(200):
            if cancelado.is_set():
                emitir("cortado", i)
                return
            threading.Event().wait(0.01)
        emitir("terminado", 200)

    tarea.lanzar(trabajo, lambda m: visto.append(m))
    QTimer.singleShot(60, tarea.cancelar)
    assert _correr_hasta(qt_app, lambda: bool(visto))
    tarea.parar()

    assert visto[0][0] == "cortado"


def test_un_fallo_del_trabajo_no_se_pierde(qt_app):
    """Un hilo que muere en silencio deja la interfaz esperando para siempre."""
    recibidos = []
    tarea = Tarea()

    def trabajo(emitir, cancelado):
        raise RuntimeError("algo se rompió")

    tarea.lanzar(trabajo, lambda m: recibidos.append(m))
    assert _correr_hasta(qt_app, lambda: bool(recibidos))
    tarea.parar()

    assert recibidos[0][0] == "error_interno"
    assert "algo se rompió" in recibidos[0][1]


def test_parar_espera_al_hilo(qt_app):
    """Salir dejando trabajo vivo es lo que termina en un volcado."""
    tarea = Tarea()
    tarea.lanzar(lambda emitir, cancelado: cancelado.wait(5), lambda m: None)
    tarea.parar()
    assert not tarea.corriendo


def test_lo_que_quedo_de_la_anterior_no_ensucia_la_siguiente(qt_app):
    recibidos = []
    tarea = Tarea()
    tarea.lanzar(lambda emitir, cancelado: emitir("vieja"), lambda m: None)
    assert _correr_hasta(qt_app, lambda: not tarea.corriendo)

    tarea.lanzar(lambda emitir, cancelado: emitir("nueva"), lambda m: recibidos.append(m))
    assert _correr_hasta(qt_app, lambda: bool(recibidos))
    tarea.parar()

    assert [m[0] for m in recibidos] == ["nueva"]
