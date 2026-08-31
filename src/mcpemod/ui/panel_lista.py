"""Base común de los tres paneles: un título y una lista con scroll."""

from __future__ import annotations

from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from wulf_qt import GAP_CELDA, PADDING_CELDA, PARED, Tallado, mostrar_aviso

from mcpemod.ui.estilo import SOBRE_BANDEJA


class PanelLista(QWidget):
    def __init__(self, titulo: str, vacio: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._texto_vacio = vacio

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(PARED)

        raiz.addWidget(Tallado(titulo, sobre=SOBRE_BANDEJA))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        contenedor = QWidget()
        self._lista = QVBoxLayout(contenedor)
        self._lista.setContentsMargins(0, 0, 0, PADDING_CELDA)
        self._lista.setSpacing(GAP_CELDA // 2)
        self._lista.addStretch()

        scroll.setWidget(contenedor)
        raiz.addWidget(scroll)

    def _poner(self, widgets: list[QWidget]) -> None:
        """Reemplaza el contenido de la lista, dejando el stretch final en su sitio."""
        while self._lista.count() > 1:
            item = self._lista.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

        if not widgets:
            widgets = [Tallado(self._texto_vacio, sobre=SOBRE_BANDEJA)]

        for w in widgets:
            self._lista.insertWidget(self._lista.count() - 1, w)

    def _avisar(self, mensaje: str) -> None:
        mostrar_aviso(self.window(), mensaje)
