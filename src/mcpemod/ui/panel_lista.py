"""Base común de los tres paneles: un título y una lista con scroll."""

from __future__ import annotations

from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from wulf_qt import PADDING_CELDA, PARED, Tallado, mostrar_aviso

from mcpemod.ui.estilo import SOBRE_BANDEJA


class PanelLista(QWidget):
    def __init__(self, vacio: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._texto_vacio = vacio

        self._raiz = raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, PARED, 0, 0)
        raiz.setSpacing(PARED)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        contenedor = QWidget()
        self._lista = QVBoxLayout(contenedor)
        self._lista.setContentsMargins(0, 0, 0, PADDING_CELDA)
        self._lista.setSpacing(PARED // 2)
        self._lista.addStretch()

        scroll.setWidget(contenedor)
        raiz.addWidget(scroll)

    def _cabecera(self, widget: QWidget) -> None:
        """Fija un widget encima de la lista, fuera del área con scroll."""
        self._raiz.insertWidget(0, widget)

    def _poner(self, widgets: list[QWidget]) -> None:
        """Reemplaza el contenido de la lista, dejando el stretch final en su sitio."""
        while self._lista.count() > 1:
            item = self._lista.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # Sacarlo del padre lo quita de la pantalla ya. `deleteLater`
                # solo marca para borrar, y hasta que el bucle de eventos lo
                # atiende el widget sigue pintándose encima de los nuevos.
                widget.setParent(None)
                widget.deleteLater()

        if not widgets:
            widgets = [Tallado(self._texto_vacio, sobre=SOBRE_BANDEJA)]

        for w in widgets:
            self._lista.insertWidget(self._lista.count() - 1, w)

    def _avisar(self, mensaje: str) -> None:
        mostrar_aviso(self.window(), mensaje)
