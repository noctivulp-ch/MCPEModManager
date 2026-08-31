"""El aviso que cubre la ventana mientras se arrastra algo encima.

Sin él, arrastrar sobre la ventana no da ninguna señal de que vaya a pasar algo
— y un gesto que no se sabe si está funcionando se abandona a mitad.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from mcpemod.ui.estilo import LACA, SOBRE_BANDEJA

_OPACIDAD = 0.93


def _rgba(hex_color: str, alfa: float) -> str:
    """`rgba()` a partir de un `#RRGGBB`.

    En QSS un color de ocho dígitos se lee como `#AARRGGBB`, no como
    `#RRGGBBAA`: escribirlo así da un color equivocado y opaco, que es
    exactamente lo que no sirve para un velo.
    """
    crudo = hex_color.lstrip("#")
    r, g, b = (int(crudo[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alfa})"


class VeloSoltar(QLabel):
    def __init__(self, parent: QWidget) -> None:
        super().__init__("Suelta para instalar\n(una carpeta se añade a las vigiladas)", parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"background: {_rgba(SOBRE_BANDEJA, _OPACIDAD)};"
            f"color: {LACA.texto_en_bandeja};"
            f"border: 2px dashed {LACA.texto_atenuado_en_bandeja};"
            "border-radius: 8px; font-size: 16px; font-weight: 600;"
        )
        self.hide()

    def mostrar_sobre(self, area: QWidget) -> None:
        # `geometry()` y no `rect()`: el velo cuelga de la ventana, así que
        # necesita las coordenadas del área dentro de ella, no las propias.
        self.setGeometry(area.geometry())
        self.raise_()
        self.show()
