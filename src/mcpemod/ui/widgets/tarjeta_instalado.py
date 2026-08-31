"""Tarjeta de una pieza de contenido presente en la carpeta del juego."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from wulf_qt import GAP_CELDA, Pozo, Tallado, boton, boton_primario

from mcpemod.core import Instalado
from mcpemod.ui.estilo import AMBAR, COLOR_CATEGORIA, GRIS, SOBRE_POZO, TEXTO_SECUNDARIO
from mcpemod.ui.widgets.badge import badge


class TarjetaInstalado(QWidget):
    desinstalar_pedido = Signal(object)
    reparar_pedido = Signal(object)

    def __init__(self, pieza: Instalado, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pieza = pieza

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.addWidget(Pozo(self._contenido()))

    def _contenido(self) -> QWidget:
        contenedor = QWidget()
        layout = QHBoxLayout(contenedor)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(GAP_CELDA)

        info = QVBoxLayout()
        info.setSpacing(GAP_CELDA // 4)
        info.addLayout(self._fila_titulo())
        info.addWidget(self._detalle())
        layout.addLayout(info, stretch=1)

        layout.addLayout(self._fila_acciones())
        return contenedor

    def _fila_titulo(self) -> QHBoxLayout:
        fila = QHBoxLayout()
        fila.setSpacing(GAP_CELDA // 2)

        nombre = Tallado(self._pieza.nombre, sobre=SOBRE_POZO)
        nombre.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        fila.addWidget(nombre)

        categoria = self._pieza.categoria
        fila.addWidget(badge(categoria.etiqueta, COLOR_CATEGORIA.get(categoria.value, GRIS)))
        if not self._pieza.activo:
            fila.addWidget(badge("⚠ el juego no lo carga", AMBAR))

        fila.addStretch()
        return fila

    def _detalle(self) -> QLabel:
        partes = []
        if self._pieza.version:
            partes.append(f"v{self._pieza.version}")
        partes.append(f"carpeta: {self._pieza.ruta.name}")
        if self._pieza.origen:
            partes.append(f"desde: {self._pieza.origen}")

        lbl = QLabel("  ·  ".join(partes))
        lbl.setStyleSheet(f"color: {TEXTO_SECUNDARIO}; font-size: 11px;")
        return lbl

    def _fila_acciones(self) -> QHBoxLayout:
        fila = QHBoxLayout()
        fila.setSpacing(GAP_CELDA // 2)
        fila.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        if not self._pieza.activo:
            btn_reparar = boton_primario("Reparar")
            btn_reparar.clicked.connect(lambda: self.reparar_pedido.emit(self._pieza))
            fila.addWidget(btn_reparar)

        btn = boton("Desinstalar")
        btn.clicked.connect(lambda: self.desinstalar_pedido.emit(self._pieza))
        fila.addWidget(btn)
        return fila
