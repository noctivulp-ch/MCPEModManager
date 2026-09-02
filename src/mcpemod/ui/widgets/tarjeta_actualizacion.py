"""Tarjeta de un pack instalado frente a lo que se ha encontrado publicado."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from wulf_qt import GAP_CELDA, Pozo, Tallado, boton, boton_primario

from mcpemod.core.actualizaciones import Confianza, Resultado
from mcpemod.core.version import EstadoVersion
from mcpemod.ui import iconos
from mcpemod.ui.estilo import AMBAR, GRIS, SOBRE_POZO, TEXTO_SECUNDARIO, VERDE
from mcpemod.ui.widgets.badge import badge
from mcpemod.ui.widgets.miniatura import Miniatura


class TarjetaActualizacion(QWidget):
    actualizar_pedido = Signal(object)
    abrir = Signal(object)

    def __init__(self, resultado: Resultado, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._r = resultado

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.addWidget(Pozo(self._contenido()))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, evento) -> None:  # noqa: N802 (API de Qt)
        if evento.button() == Qt.MouseButton.LeftButton:
            self.abrir.emit(self._r.pieza)
        super().mouseReleaseEvent(evento)

    def _contenido(self) -> QWidget:
        contenedor = QWidget()
        layout = QHBoxLayout(contenedor)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(GAP_CELDA)

        layout.addWidget(Miniatura(self._r.pieza),
                         alignment=Qt.AlignmentFlag.AlignVCenter)

        info = QVBoxLayout()
        info.setSpacing(GAP_CELDA // 4)
        info.addLayout(self._fila_titulo())
        info.addWidget(self._detalle())
        layout.addLayout(info, stretch=1)
        layout.addLayout(self._acciones())
        return contenedor

    def _fila_titulo(self) -> QHBoxLayout:
        fila = QHBoxLayout()
        fila.setSpacing(GAP_CELDA // 2)

        nombre = Tallado(self._r.pieza.nombre, sobre=SOBRE_POZO)
        nombre.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        fila.addWidget(nombre)

        if self._r.hay_actualizacion:
            fila.addWidget(badge("↑ actualización", AMBAR))
        elif self._r.estado == EstadoVersion.IGUAL:
            fila.addWidget(badge("✓ al día", VERDE))
        elif self._r.estado == EstadoVersion.ANTERIOR:
            fila.addWidget(badge("↓ la tuya es más nueva", GRIS))

        if self._r.confianza is Confianza.PROBABLE:
            # El uuid no coincide: puede ser el mismo pack republicado o uno
            # distinto del mismo autor. Decirlo es lo único honesto.
            marca = badge("sin confirmar", GRIS)
            marca.setToolTip(
                "Mismo autor y título casi idéntico, pero el identificador\n"
                "interno no coincide. Hay autores que lo cambian al publicar\n"
                "una versión mayor. Ábrelo y compruébalo antes de instalarlo."
            )
            fila.addWidget(marca)

        fila.addStretch()
        return fila

    def _detalle(self) -> QLabel:
        version = f"v{self._r.pieza.version or '?'}"
        if self._r.version_remota:
            version += f" → v{self._r.version_remota}"
        partes = [version]

        if self._r.publicacion:
            partes.append(self._r.publicacion.titulo)
            if self._r.publicacion.autor:
                partes.append(f"por {self._r.publicacion.autor}")

        lbl = QLabel("  ·  ".join(partes))
        lbl.setStyleSheet(f"color: {TEXTO_SECUNDARIO}; font-size: 11px;")
        return lbl

    def _acciones(self) -> QHBoxLayout:
        fila = QHBoxLayout()
        fila.setSpacing(GAP_CELDA // 2)
        fila.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        publicacion = self._r.publicacion
        if publicacion and publicacion.url:
            ver = iconos.poner(boton("Ver"), iconos.SITIO)
            ver.setToolTip(publicacion.url)
            ver.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(publicacion.url)))
            fila.addWidget(ver)

        if self._r.hay_actualizacion and self._r.descarga:
            btn = iconos.poner(boton_primario("Actualizar"), iconos.ACTUALIZAR)
            btn.clicked.connect(lambda: self.actualizar_pedido.emit(self._r))
            fila.addWidget(btn)

        return fila
