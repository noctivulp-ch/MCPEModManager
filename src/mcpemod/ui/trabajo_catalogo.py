"""Consultas al catálogo fuera del hilo de la interfaz.

Mismo patrón que `mcpemod.ui.trabajo`, y por las mismas razones: trabajador
persistente en su hilo, encargos por señal y una única conexión de vuelta.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from mcpemod.core.red import ErrorRed


class Explorador(QObject):
    """Busca en un catálogo, o pide sus novedades si no hay texto."""

    #: Encargo: (fuente, texto, página, tanda).
    pedir = Signal(object, str, int, int)

    #: Respuesta: (tanda, list[Publicacion], error). La tanda vuelve tal cual
    #: porque al escribir rápido se solapan consultas y llegan desordenadas: el
    #: panel se queda con la suya y descarta las viejas.
    listo = Signal(int, object, str)

    def __init__(self) -> None:
        super().__init__()
        self.pedir.connect(self._atender)

    def _atender(self, fuente, texto: str, pagina: int, tanda: int) -> None:
        texto = texto.strip()
        try:
            resultados = (
                fuente.buscar(texto, pagina=pagina) if texto
                else fuente.recientes(pagina=pagina)
            )
        except ErrorRed as e:
            self.listo.emit(tanda, [], str(e))
            return
        self.listo.emit(tanda, resultados, "")
