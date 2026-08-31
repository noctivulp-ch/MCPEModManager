"""Panel de historial de cambios."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from wulf_qt import GAP_CELDA, Pozo

from mcpemod.core import EntradaHistorial, Store
from mcpemod.ui.estilo import AMBAR, CIAN, GRIS, ROJO, TEXTO_SECUNDARIO, VERDE
from mcpemod.ui.panel_lista import PanelLista

_ACCIONES = {
    "instalar": ("↓", VERDE),
    "actualizar": ("↑", AMBAR),
    "desinstalar": ("✕", ROJO),
    "reparar": ("⟳", CIAN),
}


class PanelHistorial(PanelLista):
    def __init__(self, store: Store, parent: QWidget | None = None) -> None:
        super().__init__("Todavía no hay cambios registrados.", parent)
        self._store = store
        self.recargar()

    def recargar(self) -> None:
        self._poner([_fila(e) for e in self._store.historial()])


def _fila(e: EntradaHistorial) -> QWidget:
    contenedor = QWidget()
    layout = QHBoxLayout(contenedor)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(GAP_CELDA)

    icono, color = _ACCIONES.get(e.accion, ("·", GRIS))
    lbl_icono = QLabel(icono)
    lbl_icono.setStyleSheet(f"color: {color}; font-size: 14px; font-weight: bold;")
    layout.addWidget(lbl_icono)

    info = QVBoxLayout()
    info.setSpacing(2)

    lbl_nombre = QLabel(e.nombre)
    lbl_nombre.setStyleSheet("font-weight: 600; font-size: 12px;")
    info.addWidget(lbl_nombre)

    detalle = e.accion
    if e.categoria:
        detalle += f" · {e.categoria}"
    if e.version:
        detalle += f" · v{e.version}"
    if e.version_anterior and e.accion == "actualizar":
        detalle += f"  (antes: v{e.version_anterior})"
    lbl_detalle = QLabel(detalle)
    lbl_detalle.setStyleSheet(f"color: {TEXTO_SECUNDARIO}; font-size: 11px;")
    info.addWidget(lbl_detalle)

    layout.addLayout(info)
    layout.addStretch()

    lbl_ts = QLabel(e.timestamp.strftime("%d/%m/%Y %H:%M"))
    lbl_ts.setStyleSheet(f"color: {TEXTO_SECUNDARIO}; font-size: 10px;")
    layout.addWidget(lbl_ts)

    return Pozo(contenedor)
