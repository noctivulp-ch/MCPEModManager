"""La portada del pack, al tamaño de una fila.

Las texturas de Minecraft son de 16×16 px y se amplían **sin suavizar**: es lo
que hace que un bloque se vea como un bloque. Escalar una portada con
interpolación la convierte en una mancha borrosa, que es justo lo contrario de lo
que el pack quiere enseñar.

Se guarda lo ya leído porque una lista de cuarenta packs pide cuarenta portadas,
y al reconstruirla —cada vez que se activa o se mueve algo— las pide otra vez.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QWidget

from wulf_qt import icono

from mcpemod.core.miniatura import leer
from mcpemod.core.mod import Instalado
from mcpemod.ui import iconos
from mcpemod.ui.estilo import TEXTO_SECUNDARIO

#: En la fila de una lista y en la cabecera del detalle.
CHICA = 34
GRANDE = 72

_cache: dict[tuple[str, int], QPixmap] = {}


def _sin_suavizar(datos: bytes, lado: int) -> QPixmap | None:
    origen = QPixmap()
    if not origen.loadFromData(datos):
        return None
    # `FastTransformation` es el vecino más cercano: mantiene el píxel cuadrado.
    # Con el suavizado por defecto una portada de 16×16 llega a 34 como una
    # mancha de color.
    return origen.scaled(
        lado, lado,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.FastTransformation,
    )


def pixmap_de(pieza: Instalado, lado: int = CHICA) -> QPixmap:
    """La portada del pack, o un marcador si no trae ninguna."""
    clave = (str(pieza.ruta), lado)
    if clave in _cache:
        return _cache[clave]

    datos = leer(pieza)
    px = _sin_suavizar(datos, lado) if datos else None
    if px is None or px.isNull():
        px = _marcador(lado)
    _cache[clave] = px
    return px


def _marcador(lado: int) -> QPixmap:
    """Para los que no traen portada: el hueco se ocupa igual.

    Dejarlo vacío desalinea el nombre de esa fila respecto a todas las demás, y
    una lista con un solo renglón corrido llama más la atención que la portada
    que falta.
    """
    lienzo = QPixmap(lado, lado)
    lienzo.fill(Qt.GlobalColor.transparent)
    dibujo = icono(iconos.SIN_PORTADA, TEXTO_SECUNDARIO, lado * 2 // 3)
    pintor = QPainter(lienzo)
    dibujo.paint(pintor, (lado - lado * 2 // 3) // 2, (lado - lado * 2 // 3) // 2,
                 lado * 2 // 3, lado * 2 // 3)
    pintor.end()
    return lienzo


class Miniatura(QLabel):
    def __init__(self, pieza: Instalado, lado: int = CHICA,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(lado, lado)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setPixmap(pixmap_de(pieza, lado))


def olvidar() -> None:
    """Vacía lo guardado. Al reinstalar un pack su portada puede haber cambiado."""
    _cache.clear()
