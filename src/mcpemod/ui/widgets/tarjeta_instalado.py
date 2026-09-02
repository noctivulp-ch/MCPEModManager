"""Tarjeta de una pieza de contenido presente en la carpeta del juego."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from wulf_qt import GAP_CELDA, Pozo, Tallado, boton, boton_primario

from mcpemod.core import Instalado
from mcpemod.ui import iconos
from mcpemod.ui.estilo import AMBAR, SOBRE_POZO, TEXTO_SECUNDARIO, VIOLETA
from mcpemod.ui.widgets.badge import badge


class TarjetaInstalado(QWidget):
    desinstalar_pedido = Signal(object)
    normalizar_pedido = Signal(object)

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

        # El tipo lo dice el título del grupo; repetirlo en cada tarjeta con un
        # color propio era ruido, y esos colores no salían de la laca.
        # La forma no es un problema: el juego admite las tres. Se señala porque
        # solo la de carpeta permite actualizar y desinstalar como el resto.
        if self._pieza.de_la_tienda:
            fila.addWidget(badge("Tienda", VIOLETA))
        if self._pieza.forma.etiqueta:
            fila.addWidget(badge(self._pieza.forma.etiqueta, AMBAR))

        fila.addStretch()
        return fila

    def _detalle(self) -> QLabel:
        partes = []
        if self._pieza.version:
            partes.append(f"v{self._pieza.version}")
        partes.append(f"carpeta: {self._pieza.ruta.name}")
        if self._pieza.origen:
            partes.append(f"desde: {self._pieza.origen}")
        if self._pieza.licencia:
            partes.append(self._pieza.licencia)

        lbl = QLabel("  ·  ".join(partes))
        lbl.setStyleSheet(f"color: {TEXTO_SECUNDARIO}; font-size: 11px;")
        return lbl

    def _fila_acciones(self) -> QHBoxLayout:
        fila = QHBoxLayout()
        fila.setSpacing(GAP_CELDA // 2)
        fila.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Lo de la tienda lo descarga y borra el juego: darle un botón de
        # desinstalar sería ofrecer pelearse con él.
        if not self._pieza.gestionable:
            nota = QLabel("lo gestiona el juego")
            nota.setStyleSheet(f"color: {TEXTO_SECUNDARIO}; font-size: 11px;")
            fila.addWidget(nota)
            return fila

        # Pocos packs declaran su página en `metadata.url`, pero cuando está es
        # el camino directo al sitio de quien lo hizo.
        if self._pieza.url:
            sitio = iconos.poner(boton("Sitio"), iconos.SITIO)
            sitio.setToolTip(self._pieza.url)
            sitio.clicked.connect(
                lambda: QDesktopServices.openUrl(QUrl(self._pieza.url))
            )
            fila.addWidget(sitio)

        if self._pieza.forma.normalizable:
            btn = iconos.poner(boton_primario("Extraer"), iconos.EXTRAER)
            btn.setToolTip(
                "Deja el pack como una carpeta normal, para poder actualizarlo\n"
                "y desinstalarlo igual que el resto. El juego admite las dos formas."
            )
            btn.clicked.connect(lambda: self.normalizar_pedido.emit(self._pieza))
            fila.addWidget(btn)

        btn = iconos.poner(boton("Desinstalar"), iconos.DESINSTALAR)
        btn.clicked.connect(lambda: self.desinstalar_pedido.emit(self._pieza))
        fila.addWidget(btn)
        return fila
