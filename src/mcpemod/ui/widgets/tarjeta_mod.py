"""Tarjeta visual para un mod — instalado o en descargas."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from wulf_qt import GAP_CELDA, PADDING_CELDA, Pozo, Tallado, boton, boton_primario

from mcpemod.core.mod import EstadoVersion, Mod
from mcpemod.core.version import comparar
from mcpemod.ui.estilo import AMBAR, GRIS, INDIGO, SOBRE_POZO, TEXTO_SECUNDARIO, VERDE


class TarjetaMod(QWidget):
    instalar_pedido = Signal(object)
    desinstalar_pedido = Signal(object)

    def __init__(
        self,
        mod: Mod,
        mod_instalado: Mod | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._mod = mod
        self._estado = comparar(mod_instalado.version, mod.version) if mod_instalado else None
        self._ya_instalado = mod_instalado is not None

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.addWidget(Pozo(self._contenido()))

    def _contenido(self) -> QWidget:
        contenedor = QWidget()
        layout = QVBoxLayout(contenedor)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(GAP_CELDA // 2)

        layout.addLayout(self._fila_titulo())
        layout.addLayout(self._fila_version())
        layout.addLayout(self._fila_acciones())
        return contenedor

    def _fila_titulo(self) -> QHBoxLayout:
        fila = QHBoxLayout()
        fila.setSpacing(GAP_CELDA // 2)

        nombre = Tallado(self._mod.nombre, sobre=SOBRE_POZO)
        nombre.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        fila.addWidget(nombre)

        if self._mod.primera_vez:
            fila.addWidget(_badge("NEW", VERDE))
        if self._mod.tipo is not None and self._mod.tipo.value != ".so":
            fila.addWidget(_badge(self._mod.tipo.value.lstrip(".").upper(), INDIGO))

        fila.addStretch()
        return fila

    def _fila_version(self) -> QHBoxLayout:
        fila = QHBoxLayout()
        fila.setSpacing(GAP_CELDA // 2)

        lbl = QLabel(self._mod.version or "versión desconocida")
        lbl.setStyleSheet(f"color: {TEXTO_SECUNDARIO}; font-size: 11px;")
        fila.addWidget(lbl)

        badge = {
            EstadoVersion.NUEVA: ("↑ actualización", AMBAR),
            EstadoVersion.ANTERIOR: ("↓ anterior", GRIS),
            EstadoVersion.IGUAL: ("✓ instalado", VERDE),
        }.get(self._estado)
        if badge:
            fila.addWidget(_badge(*badge))
        elif self._ya_instalado:
            fila.addWidget(_badge("· ya instalado", GRIS))

        fila.addStretch()
        return fila

    def _fila_acciones(self) -> QHBoxLayout:
        fila = QHBoxLayout()
        fila.addStretch()

        if self._mod.instalado:
            btn = boton("Desinstalar")
            btn.clicked.connect(lambda: self.desinstalar_pedido.emit(self._mod))
        else:
            etiqueta = "Actualizar" if self._estado == EstadoVersion.NUEVA else "Instalar"
            if self._estado == EstadoVersion.ANTERIOR:
                etiqueta = "Revertir"
            btn = boton_primario(etiqueta)
            btn.clicked.connect(lambda: self.instalar_pedido.emit(self._mod))

        fila.addWidget(btn)
        return fila


def _badge(texto: str, color: str) -> QLabel:
    lbl = QLabel(texto)
    lbl.setStyleSheet(
        f"background: {color}22; color: {color}; border: 1px solid {color}55;"
        f"border-radius: 3px; padding: 1px {PADDING_CELDA // 3}px;"
        "font-size: 10px; font-weight: bold;"
    )
    return lbl
