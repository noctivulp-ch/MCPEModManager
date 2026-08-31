"""La etiqueta pequeña de color que llevan las tarjetas."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel

from mcpemod.ui.estilo import GRIS


def badge(texto: str, color: str = GRIS) -> QLabel:
    lbl = QLabel(texto)
    lbl.setStyleSheet(
        f"background: {color}22; color: {color}; border: 1px solid {color}55;"
        "border-radius: 3px; padding: 1px 6px; font-size: 10px; font-weight: bold;"
    )
    return lbl
