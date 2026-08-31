"""Los trabajos de red, fuera del hilo de la interfaz.

Cada trabajador vive en un hilo propio **persistente** y se le piden encargos por
señal. Es más aparato que crear uno por encargo, y hay dos razones para ello:

1. Una señal que cruza de hilo solo llega bien al hilo de la interfaz si el slot
   es un método de un `QObject` que vive allí. Con una función suelta —una
   lambda— Qt no tiene a quién preguntarle de qué hilo es y la ejecuta en el del
   trabajador, tocando widgets desde fuera del hilo de la UI. Eso revienta.
2. Ese método hay que conectarlo **una sola vez**. Conectar el mismo método
   repetidamente es justo lo que rompe el binario compilado
   (`docs/decisiones/0008`), y con un trabajador por encargo se conectaría uno
   por consulta.

Por eso aquí se usa `connect` directo y no `mcpemod.senales.conectar`: son
conexiones únicas entre hilos, que es el caso que el helper no cubre.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from PySide6.QtCore import QObject, QThread, Signal

from mcpemod.core.actualizaciones import Buscador
from mcpemod.core.red import ErrorRed

#: Cuántos packs se consultan a la vez. Casi todo el tiempo se va esperando
#: respuestas, así que unos pocos en paralelo acortan mucho el barrido; subirlo
#: más no gana nada, porque el reparto de cortesía de `red` espacia igual las
#: peticiones a un mismo servicio.
EN_PARALELO = 4


class Comprobador(QObject):
    """Pregunta a los catálogos por una lista de packs, sin bloquear la ventana."""

    #: Encargo: (buscador, lista de piezas). Se emite desde el hilo de la UI y
    #: se atiende en el del trabajador.
    pedir = Signal(object, object)

    avance = Signal(int, int, str)      # hechos, total, nombre en curso
    encontrado = Signal(object)         # Resultado
    terminado = Signal(int, str)        # comprobados, mensaje de error o ""

    def __init__(self) -> None:
        super().__init__()
        self._cancelado = False
        self.pedir.connect(self._atender)

    def cancelar(self) -> None:
        """Se llama desde el hilo de la UI; el trabajador lo mira entre packs."""
        self._cancelado = True

    def _atender(self, buscador: Buscador, piezas: list) -> None:
        self._cancelado = False
        total = len(piezas)
        hechos = 0
        error = ""

        with ThreadPoolExecutor(max_workers=EN_PARALELO) as pool:
            tareas = {pool.submit(buscador.comprobar, p): p for p in piezas}
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
                except Exception:  # noqa: BLE001 - un pack roto no para el barrido
                    hechos += 1
                    continue

                hechos += 1
                if resultado.encontrado:
                    self.encontrado.emit(resultado)

        self.terminado.emit(hechos, error)


class HiloDeTrabajo:
    """Un trabajador y su hilo, con el cierre ordenado que Qt exige.

    Salir dejando un `QThread` corriendo termina en un volcado: hay que pedirle
    que pare y esperarlo.
    """

    def __init__(self, trabajador: QObject) -> None:
        self.trabajador = trabajador
        self._hilo = QThread()
        trabajador.moveToThread(self._hilo)
        self._hilo.start()

    def parar(self, espera_ms: int = 3000) -> None:
        if not self._hilo.isRunning():
            return
        cancelar = getattr(self.trabajador, "cancelar", None)
        if cancelar is not None:
            cancelar()
        self._hilo.quit()
        self._hilo.wait(espera_ms)
