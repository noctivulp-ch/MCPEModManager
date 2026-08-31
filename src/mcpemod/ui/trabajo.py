"""Comprobar actualizaciones sin congelar la ventana.

Consultar sesenta packs son cientos de peticiones y varios minutos. Hacerlo en
el hilo de la interfaz la deja tildada todo ese rato, así que va en uno aparte
que informa de cada pack en cuanto lo termina — la lista se llena a la vista en
lugar de aparecer entera al final.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from PySide6.QtCore import QObject, QThread, Signal

from mcpemod.core import Instalado
from mcpemod.core.actualizaciones import Buscador
from mcpemod.core.red import ErrorRed


#: Cuántos packs se consultan a la vez. Casi todo el tiempo se va esperando
#: respuestas, así que unos pocos en paralelo acortan mucho el barrido; subirlo
#: más no gana nada porque el reparto de cortesía de `red` espacia igual las
#: peticiones a un mismo servicio.
EN_PARALELO = 4


class Comprobador(QObject):
    """Recorre una lista de packs preguntando a los catálogos."""

    avance = Signal(int, int, str)      # hechos, total, nombre en curso
    encontrado = Signal(object)         # Resultado
    terminado = Signal(int, str)        # comprobados, mensaje de error o ""

    def __init__(self, buscador: Buscador, piezas: list[Instalado]) -> None:
        super().__init__()
        self._buscador = buscador
        self._piezas = piezas
        self._cancelado = False

    def cancelar(self) -> None:
        self._cancelado = True

    def ejecutar(self) -> None:
        total = len(self._piezas)
        hechos = 0
        error = ""

        with ThreadPoolExecutor(max_workers=EN_PARALELO) as pool:
            tareas = {
                pool.submit(self._buscador.comprobar, p): p for p in self._piezas
            }
            for tarea in as_completed(tareas):
                pieza = tareas[tarea]
                if self._cancelado:
                    for pendiente in tareas:
                        pendiente.cancel()
                    break

                self.avance.emit(hechos, total, pieza.nombre)
                try:
                    resultado = tarea.result()
                except ErrorRed as e:
                    # Sin red no tiene sentido seguir con los cincuenta que faltan.
                    error = str(e)
                    for pendiente in tareas:
                        pendiente.cancel()
                    break
                except Exception as e:  # noqa: BLE001 - un pack roto no para el barrido
                    self.avance.emit(hechos, total, f"{pieza.nombre}: {e}")
                    hechos += 1
                    continue

                hechos += 1
                if resultado.encontrado:
                    self.encontrado.emit(resultado)

        self.terminado.emit(hechos, error)


def en_hilo(trabajador: Comprobador) -> QThread:
    """Arranca `trabajador` en un hilo propio que se limpia solo al acabar."""
    hilo = QThread()
    trabajador.moveToThread(hilo)
    hilo.started.connect(trabajador.ejecutar)
    trabajador.terminado.connect(hilo.quit)
    hilo.finished.connect(trabajador.deleteLater)
    hilo.finished.connect(hilo.deleteLater)
    hilo.start()
    return hilo
