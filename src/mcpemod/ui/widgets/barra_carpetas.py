"""Selector de las carpetas donde el gestor busca contenido descargado.

Arranca con la carpeta de descargas del sistema, pero no está atada a ella: se
pueden añadir otras y quitar cualquiera, incluida la inicial. Siempre queda al
menos una — quedarse sin ninguna dejaría la pestaña vacía para siempre y sin
nada que pulsar para recuperarla.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from wulf_qt import GAP_CELDA, PARED, boton_plano

from mcpemod.senales import conectar
from mcpemod.ui.estilo import TEXTO_SECUNDARIO
from mcpemod.ui.widgets.boton_ruta import boton_ruta


class BarraCarpetas(QWidget):
    agregar_pedido = Signal(object)
    quitar_pedido = Signal(object)

    def __init__(self, carpetas: list[Path], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._raiz = QVBoxLayout(self)
        self._raiz.setContentsMargins(0, 0, 0, 0)
        self._raiz.setSpacing(PARED // 2)
        self.poner(carpetas)

    def poner(self, carpetas: list[Path]) -> None:
        while self._raiz.count():
            item = self._raiz.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

        cabecera = QHBoxLayout()
        cabecera.setSpacing(GAP_CELDA // 2)

        titulo = QLabel("Buscando contenido descargado en:")
        titulo.setStyleSheet(f"color: {TEXTO_SECUNDARIO}; font-size: 11px;")
        cabecera.addWidget(titulo)
        cabecera.addStretch()

        agregar = boton_plano("+ Añadir carpeta")
        conectar(agregar.clicked, self._elegir_carpeta)
        cabecera.addWidget(agregar)

        contenedor = QWidget()
        contenedor.setLayout(cabecera)
        self._raiz.addWidget(contenedor)

        # Con una sola carpeta no se ofrece quitarla: siempre queda una, y un
        # botón que solo puede fallar es peor que no tenerlo.
        ultima = len(carpetas) <= 1
        for carpeta in carpetas:
            self._raiz.addWidget(self._fila(carpeta, quitable=not ultima))

    def _fila(self, carpeta: Path, quitable: bool) -> QWidget:
        contenedor = QWidget()
        fila = QHBoxLayout(contenedor)
        fila.setContentsMargins(GAP_CELDA // 2, 0, 0, 0)
        fila.setSpacing(GAP_CELDA // 2)

        fila.addWidget(boton_ruta(carpeta))
        fila.addStretch()

        if quitable:
            quitar = boton_plano("✕")
            quitar.setToolTip(f"Dejar de mirar {carpeta}")
            conectar(quitar.clicked, lambda: self.quitar_pedido.emit(carpeta))
            fila.addWidget(quitar)

        return contenedor

    def _elegir_carpeta(self) -> None:
        elegida = QFileDialog.getExistingDirectory(
            self, "Añadir carpeta a vigilar", str(Path.home())
        )
        if elegida:
            self.agregar_pedido.emit(Path(elegida))
