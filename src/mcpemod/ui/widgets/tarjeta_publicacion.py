"""Tarjeta de una publicación del catálogo, para la pestaña Explorar."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from PySide6.QtWidgets import QSizePolicy

from wulf_qt import GAP_CELDA, Pozo, Tallado, boton, boton_primario

from mcpemod.core.fuentes import Publicacion
from mcpemod.ui import iconos
from mcpemod.ui.estilo import AMBAR, GRIS, SOBRE_POZO, TEXTO_SECUNDARIO, VERDE
from mcpemod.ui.widgets.badge import badge

#: Cuánto resumen cabe en una línea sin que la tarjeta crezca.
_LARGO_RESUMEN = 120
_LARGO_TITULO = 52


def _recortar(texto: str, largo: int) -> str:
    limpio = " ".join(texto.split())
    return limpio if len(limpio) <= largo else limpio[:largo].rstrip() + "…"


class TarjetaPublicacion(QWidget):
    instalar_pedido = Signal(object)

    def __init__(
        self,
        publicacion: Publicacion,
        instalado: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._p = publicacion
        self._instalado = instalado

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
        info.addWidget(self._resumen())
        info.addWidget(self._detalle())
        layout.addLayout(info, stretch=1)
        layout.addLayout(self._acciones())
        return contenedor

    def _fila_titulo(self) -> QHBoxLayout:
        fila = QHBoxLayout()
        fila.setSpacing(GAP_CELDA // 2)

        titulo = Tallado(_recortar(self._p.titulo, _LARGO_TITULO), sobre=SOBRE_POZO)
        titulo.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        titulo.setToolTip(self._p.titulo)
        fila.addWidget(titulo)

        if self._instalado:
            fila.addWidget(badge("✓ ya lo tienes", VERDE))
        if self._p.distribucion_bloqueada:
            marca = badge("solo desde su web", AMBAR)
            marca.setToolTip(
                "Quien lo publica no permite descargarlo desde aplicaciones\n"
                "de terceros. Se puede abrir su página e instalarlo a mano."
            )
            fila.addWidget(marca)
        for categoria in self._p.categorias[:2]:
            fila.addWidget(badge(categoria, GRIS))

        fila.addStretch()
        return fila

    def _resumen(self) -> QLabel:
        """El resumen del catálogo, recortado a una línea.

        Va con ancho ignorado a propósito: un resumen largo impondría su ancho
        natural al layout y empujaría los botones fuera de la tarjeta.
        """
        texto = " ".join((self._p.resumen or "").split())
        if len(texto) > _LARGO_RESUMEN:
            texto = texto[:_LARGO_RESUMEN].rstrip() + "…"

        lbl = QLabel(texto)
        lbl.setStyleSheet(f"color: {TEXTO_SECUNDARIO}; font-size: 11px;")
        lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        return lbl

    def _detalle(self) -> QLabel:
        partes = []
        if self._p.autor:
            partes.append(f"por {self._p.autor}")
        if self._p.descargas_totales:
            partes.append(f"{self._p.descargas_totales:,} descargas".replace(",", "."))
        if self._p.actualizado:
            partes.append(self._p.actualizado.strftime("%d/%m/%Y"))

        lbl = QLabel("  ·  ".join(partes))
        lbl.setStyleSheet(f"color: {TEXTO_SECUNDARIO}; font-size: 10px;")
        return lbl

    def _acciones(self) -> QHBoxLayout:
        fila = QHBoxLayout()
        fila.setSpacing(GAP_CELDA // 2)
        fila.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        if self._p.url:
            ver = iconos.poner(boton("Ver"), iconos.SITIO)
            ver.setToolTip(self._p.url)
            ver.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self._p.url)))
            fila.addWidget(ver)

        if self._p.ultima:
            btn = iconos.poner(boton_primario("Reinstalar" if self._instalado else "Instalar"),
                               iconos.INSTALAR)
            btn.clicked.connect(lambda: self.instalar_pedido.emit(self._p))
            fila.addWidget(btn)

        return fila
