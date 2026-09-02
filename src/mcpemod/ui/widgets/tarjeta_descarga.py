"""Tarjeta de un archivo de la carpeta de descargas.

Un archivo puede traer varias piezas —un `.mcaddon` suele traer un pack de
recursos y uno de comportamiento— y cada una se compara por separado contra lo
que hay instalado, porque cada una tiene su propio uuid y su propia versión.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from wulf_qt import GAP_CELDA, Pozo, Tallado, boton_primario

from mcpemod.core import Analisis, Componente, Instalado
from mcpemod.core.version import EstadoVersion, comparar
from mcpemod.ui import iconos
from mcpemod.ui.estilo import (
    AMBAR, COLOR_CATEGORIA, GRIS, SOBRE_POZO, TEXTO_SECUNDARIO, VERDE,
)
from mcpemod.ui.widgets.badge import badge

_ETIQUETA_ESTADO = {
    EstadoVersion.NUEVA: ("↑ actualización", AMBAR),
    EstadoVersion.ANTERIOR: ("↓ anterior", GRIS),
    EstadoVersion.IGUAL: ("✓ instalado", VERDE),
}


class TarjetaDescarga(QWidget):
    instalar_pedido = Signal(object)

    def __init__(
        self,
        analisis: Analisis,
        instalados: dict[str, Instalado],
        es_nuevo: bool = False,
        mostrar_carpeta: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._analisis = analisis
        self._instalados = instalados
        self._es_nuevo = es_nuevo
        self._mostrar_carpeta = mostrar_carpeta

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
        for componente in self._analisis.componentes:
            info.addLayout(self._fila_componente(componente))
        layout.addLayout(info, stretch=1)

        layout.addLayout(self._fila_acciones())
        return contenedor

    def _fila_titulo(self) -> QHBoxLayout:
        fila = QHBoxLayout()
        fila.setSpacing(GAP_CELDA // 2)

        nombre = Tallado(self._analisis.ruta.name, sobre=SOBRE_POZO)
        nombre.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        fila.addWidget(nombre)
        if self._es_nuevo:
            fila.addWidget(badge("NEW", VERDE))
        fila.addStretch()

        if self._mostrar_carpeta:
            lbl = QLabel(str(self._analisis.ruta.parent))
            lbl.setStyleSheet(f"color: {TEXTO_SECUNDARIO}; font-size: 10px;")
            fila.addWidget(lbl)
        return fila

    def _fila_componente(self, componente: Componente) -> QHBoxLayout:
        fila = QHBoxLayout()
        fila.setSpacing(GAP_CELDA // 2)
        fila.setContentsMargins(GAP_CELDA // 2, 0, 0, 0)

        categoria = componente.categoria
        fila.addWidget(badge(categoria.etiqueta, COLOR_CATEGORIA.get(categoria.value, GRIS)))

        texto = componente.nombre
        if componente.version:
            texto += f"  v{componente.version}"
        lbl = QLabel(texto)
        lbl.setStyleSheet(f"color: {TEXTO_SECUNDARIO}; font-size: 11px;")
        fila.addWidget(lbl)

        etiqueta = _ETIQUETA_ESTADO.get(self._estado(componente))
        if etiqueta:
            fila.addWidget(badge(*etiqueta))

        fila.addStretch()
        return fila

    def _estado(self, componente: Componente) -> EstadoVersion | None:
        instalado = self._instalados.get(componente.uuid) if componente.uuid else None
        if instalado is None:
            return None
        return comparar(instalado.version, componente.version)

    def _etiqueta_boton(self) -> str:
        estados = {self._estado(c) for c in self._analisis.componentes}
        if EstadoVersion.NUEVA in estados:
            return "Actualizar"
        if estados == {EstadoVersion.ANTERIOR}:
            return "Revertir"
        if None not in estados and estados:
            return "Reinstalar"
        return "Instalar"

    def _fila_acciones(self) -> QHBoxLayout:
        fila = QHBoxLayout()
        fila.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        etiqueta = self._etiqueta_boton()
        dibujo = iconos.ACTUALIZAR if etiqueta == "Actualizar" else iconos.INSTALAR
        btn = iconos.poner(boton_primario(etiqueta), dibujo)
        btn.clicked.connect(lambda: self.instalar_pedido.emit(self._analisis))
        fila.addWidget(btn)
        return fila
