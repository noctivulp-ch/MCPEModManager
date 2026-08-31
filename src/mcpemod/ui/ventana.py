"""Ventana principal del gestor."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget,
)

from wulf_qt import GAP_CELDA, Bandeja, Pozo

from mcpemod.core import Instalacion, Installer, Scanner, Store, carpeta_descargas
from mcpemod.senales import conectar
from mcpemod.ui.estilo import TEXTO_SECUNDARIO
from mcpemod.ui.panel_descargas import PanelDescargas
from mcpemod.ui.panel_historial import PanelHistorial
from mcpemod.ui.panel_instalados import PanelInstalados

_TITULO = "MCPE Mod Manager"
_ANCHO_MIN = 820
_ALTO_MIN = 560

_TAB_DESCARGAS = 1
_TAB_HISTORIAL = 2


class VentanaPrincipal(QMainWindow):
    def __init__(
        self,
        store: Store,
        scanner: Scanner,
        installer: Installer,
        instalaciones: list[Instalacion],
    ) -> None:
        super().__init__()
        self._store = store
        self._scanner = scanner
        self._installer = installer
        self._instalaciones = instalaciones
        self._construir()
        conectar(scanner.instalados_cambiados, self._panel_historial.recargar)

    def _construir(self) -> None:
        self.setWindowTitle(_TITULO)
        self.setMinimumSize(_ANCHO_MIN, _ALTO_MIN)
        self.resize(1040, 700)

        raiz = QWidget()
        self.setCentralWidget(raiz)
        layout_raiz = QHBoxLayout(raiz)
        layout_raiz.setContentsMargins(0, 0, 0, 0)
        layout_raiz.setSpacing(0)

        bandeja = Bandeja()
        layout_raiz.addWidget(bandeja)

        bandeja.agregar(self._barra_instalacion())

        self._panel_instalados = PanelInstalados(self._scanner, self._installer)
        self._panel_descargas = PanelDescargas(self._scanner, self._installer)
        self._panel_historial = PanelHistorial(self._store)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.addTab(self._panel_instalados, "Instalado")
        self._tabs.addTab(self._panel_descargas, "Descargas")
        self._tabs.addTab(self._panel_historial, "Historial")
        conectar(self._tabs.currentChanged, self._al_cambiar_tab)

        bandeja.agregar(self._tabs)

    def _barra_instalacion(self) -> QWidget:
        """Selector de instalación del juego.

        Un mismo equipo puede tener la nativa y varias flatpak, cada una con su
        propia carpeta `com.mojang`. Sin poder elegir, el gestor trabajaría a
        ciegas sobre una que quizá no es la que se juega.
        """
        contenedor = QWidget()
        fila = QHBoxLayout(contenedor)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(GAP_CELDA)

        fila.addWidget(QLabel("Instalación:"))

        self._combo = QComboBox()
        for instalacion in self._instalaciones:
            self._combo.addItem(
                f"{instalacion.nombre}  ({instalacion.contar_contenido()} elementos)",
                userData=instalacion,
            )
        self._combo.setCurrentIndex(
            max(0, self._instalaciones.index(self._scanner.instalacion))
        )
        conectar(self._combo.currentIndexChanged, self._al_elegir_instalacion)
        fila.addWidget(self._combo, stretch=1)

        detalle = QVBoxLayout()
        detalle.setSpacing(1)
        self._lbl_ruta = QLabel()
        self._lbl_descargas = QLabel(f"Descargas: {carpeta_descargas()}")
        for lbl in (self._lbl_ruta, self._lbl_descargas):
            lbl.setStyleSheet(f"color: {TEXTO_SECUNDARIO}; font-size: 10px;")
            detalle.addWidget(lbl)
        fila.addLayout(detalle)

        self._actualizar_ruta()
        return Pozo(contenedor)

    def _actualizar_ruta(self) -> None:
        self._lbl_ruta.setText(f"Juego: {self._scanner.instalacion.com_mojang}")

    def _al_elegir_instalacion(self, indice: int) -> None:
        instalacion = self._combo.itemData(indice)
        if instalacion is None or instalacion == self._scanner.instalacion:
            return
        self._installer.cambiar_instalacion(instalacion)
        self._scanner.cambiar_instalacion(instalacion)
        self._actualizar_ruta()

    def _al_cambiar_tab(self, indice: int) -> None:
        if indice == _TAB_DESCARGAS:
            self._panel_descargas.marcar_vistas()
        elif indice == _TAB_HISTORIAL:
            self._panel_historial.recargar()
