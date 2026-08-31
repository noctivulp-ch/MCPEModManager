"""Trabajo en segundo plano cuyos resultados llegan al hilo de la interfaz.

**Sin señales de Qt entre hilos**, y es deliberado. Una señal que cruza de hilo
solo llega bien si el slot es un método de un `QObject` que vive en el hilo de
destino — pero conectar métodos así es lo que rompe el binario compilado: el
fallo de Nuitka salta en la **segunda** conexión de un método, sea cual sea
(`docs/decisiones/0008`). Las dos condiciones no se pueden cumplir a la vez.

La salida es no cruzar de hilo con Qt: el trabajo corre en un hilo normal de
Python y deja lo que produce en una cola, que un `QTimer` del hilo de la
interfaz vacía cada poco. Así la única conexión que queda es la del temporizador,
que vive entera dentro del hilo de la UI y va por `senales.conectar`.
"""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer

from mcpemod.senales import conectar

#: Cada cuánto se mira la cola. Suficientemente corto para que la lista parezca
#: llenarse sola, suficientemente largo para no despertar por nada.
_INTERVALO_MS = 80


class Tarea(QObject):
    """Un trabajo en segundo plano por vez, con sus mensajes recogidos en orden."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._cola: queue.Queue = queue.Queue()
        self._hilo: threading.Thread | None = None
        self._cancelado = threading.Event()
        self._al_mensaje: Callable[[tuple], None] | None = None

        self._reloj = QTimer(self)
        self._reloj.setInterval(_INTERVALO_MS)
        conectar(self._reloj.timeout, self._vaciar)

    @property
    def corriendo(self) -> bool:
        return self._hilo is not None and self._hilo.is_alive()

    def lanzar(
        self,
        trabajo: Callable[[Callable[..., None], threading.Event], None],
        al_mensaje: Callable[[tuple], None],
    ) -> bool:
        """Arranca `trabajo(emitir, cancelado)` en un hilo aparte.

        `emitir(*datos)` encola un mensaje que llegará a `al_mensaje` **en el
        hilo de la interfaz**. `cancelado` es un `Event` que el trabajo debe
        mirar entre pasos para poder pararse.

        Devuelve `False` si ya había uno en marcha: se hace uno por vez, que es
        lo que necesitan los paneles y ahorra tener que ordenar respuestas.
        """
        if self.corriendo:
            return False

        # Lo que quedara de la anterior se tira sin entregarlo: es respuesta a
        # una pregunta que ya no se hace.
        self._descartar()
        self._al_mensaje = al_mensaje
        self._cancelado = threading.Event()

        def envoltorio() -> None:
            try:
                trabajo(lambda *datos: self._cola.put(datos), self._cancelado)
            except Exception as e:  # noqa: BLE001 - el hilo no puede morir en silencio
                self._cola.put(("error_interno", str(e)))

        self._hilo = threading.Thread(target=envoltorio, daemon=True)
        self._hilo.start()
        self._reloj.start()
        return True

    def cancelar(self) -> None:
        self._cancelado.set()

    def parar(self, espera: float = 3.0) -> None:
        """Cancela y espera. Se llama al cerrar la ventana."""
        self._reloj.stop()
        self.cancelar()
        if self._hilo is not None and self._hilo.is_alive():
            self._hilo.join(espera)

    def _descartar(self) -> None:
        while True:
            try:
                self._cola.get_nowait()
            except queue.Empty:
                return

    def _vaciar(self) -> None:
        while True:
            try:
                mensaje = self._cola.get_nowait()
            except queue.Empty:
                break
            if self._al_mensaje is not None:
                self._al_mensaje(mensaje)

        if not self.corriendo:
            self._reloj.stop()
