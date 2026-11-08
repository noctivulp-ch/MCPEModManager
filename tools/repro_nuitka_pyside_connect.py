"""Repro del fallo de `Signal.connect` con métodos bound bajo Nuitka.

Con Nuitka 4.1.3 + PySide6 6.11.2 + CPython 3.14.6, un binario compilado revienta
en la **segunda** conexión de un mismo método bound a una señal:

    SystemError: method_descriptor() returned a result with an exception set

La primera conexión pasa, deja una excepción pendiente a nivel C, y la siguiente
llamada al descriptor explota. Interpretado no falla; compilado sí. Conectar una
lambda que llame al método evita el problema — es el workaround que usa
`mcpemod.senales.conectar`.

Este script no depende del proyecto: sirve para comprobar si una versión nueva
del toolchain ya lo arregla, y entonces retirar el workaround.

Uso:
    python tools/repro_nuitka_pyside_connect.py          # interpretado: pasa
    python -m nuitka --onefile --enable-plugin=pyside6 \
        --output-filename=repro tools/repro_nuitka_pyside_connect.py
    ./repro                                                # compilado: falla
"""
import sys
from PySide6.QtCore import QCoreApplication, QObject, Signal


class Emisor(QObject):
    disparo = Signal()


class Receptor(QObject):
    def __init__(self):
        super().__init__()
        self.contador = 0

    def al_disparar(self):
        self.contador += 1


def probar(etiqueta, hacer_connect, n=12):
    emisor, receptor = Emisor(), Receptor()
    for i in range(n):
        try:
            hacer_connect(emisor, receptor)
        except BaseException as e:
            print(f"{etiqueta}: falla en la conexión #{i + 1} — {type(e).__name__}: {e}")
            return
    emisor.disparo.emit()
    print(f"{etiqueta}: OK, {receptor.contador}/{n} llamadas")


def main():
    QCoreApplication(sys.argv)
    probar("bound method", lambda e, r: e.disparo.connect(r.al_disparar))
    probar("lambda", lambda e, r: e.disparo.connect(lambda: r.al_disparar()))
    probar("bound method x1", lambda e, r: e.disparo.connect(r.al_disparar), n=1)


if __name__ == "__main__":
    main()
