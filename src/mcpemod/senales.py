"""Conexión de señales que sobrevive a la compilación con Nuitka.

Con Nuitka 4.1.3 + PySide6 6.11.2 + CPython 3.14.6, el binario compilado revienta
en la **segunda** conexión de un mismo método bound a una señal:

    SystemError: method_descriptor() returned a result with an exception set

La primera conexión deja una excepción pendiente a nivel C y la siguiente llamada
al descriptor explota. Interpretado no pasa; compilado sí, y en sitios normales:
un panel que se suscribe a dos señales, o un panel que escucha a sus N tarjetas.

`scripts/repro_nuitka_pyside_connect.py` reproduce el fallo sin nada del proyecto
y sirve para comprobar si una versión nueva del toolchain ya lo arregla — cuando
así sea, esto se retira y se vuelve a `senal.connect(slot)` directo.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import SignalInstance


def conectar(senal: SignalInstance, slot: Callable) -> None:
    """Como `senal.connect(slot)`, pero con el slot envuelto en una función libre.

    PySide6 mantiene viva la envoltura mientras exista el emisor, así que no hace
    falta guardarla: el emisor siempre muere antes o a la vez que el receptor en
    los usos de esta app.
    """
    senal.connect(lambda *args: slot(*args))
