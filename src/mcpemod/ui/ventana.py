"""Ventana principal del gestor de mods."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QTabWidget, QWidget

from wulf_qt import Bandeja

from mcpemod.core import Installer, Scanner, Store
from mcpemod.ui.panel_descargas import PanelDescargas
from mcpemod.ui.panel_historial import PanelHistorial
from mcpemod.ui.panel_instalados import PanelInstalados

_TITULO = "MCPE Mod Manager"
_ANCHO_MIN = 800
_ALTO_MIN = 560

_TAB_DESCARGAS = 1
_TAB_HISTORIAL = 2


class VentanaPrincipal(QMainWindow):
    def __init__(self, store: Store, scanner: Scanner, installer: Installer) -> None:
        super().__init__()
        self._store = store
        self._scanner = scanner
        self._installer = installer
        self._construir()
        scanner.mods_cambiados.connect(self._panel_historial.recargar)

    def _construir(self) -> None:
        self.setWindowTitle(_TITULO)
        self.setMinimumSize(_ANCHO_MIN, _ALTO_MIN)
        self.resize(1000, 660)

        raiz = QWidget()
        self.setCentralWidget(raiz)

        layout_raiz = QHBoxLayout(raiz)
        layout_raiz.setContentsMargins(0, 0, 0, 0)
        layout_raiz.setSpacing(0)

        bandeja = Bandeja()
        layout_raiz.addWidget(bandeja)

        self._panel_instalados = PanelInstalados(self._scanner, self._installer)
        self._panel_descargas = PanelDescargas(self._scanner, self._installer)
        self._panel_historial = PanelHistorial(self._store)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.addTab(self._panel_instalados, "Instalados")
        self._tabs.addTab(self._panel_descargas, "Descargas")
        self._tabs.addTab(self._panel_historial, "Historial")
        self._tabs.currentChanged.connect(self._al_cambiar_tab)

        bandeja.agregar(self._tabs)

    def _al_cambiar_tab(self, indice: int) -> None:
        if indice == _TAB_DESCARGAS:
            self._panel_descargas.marcar_vistas()
        elif indice == _TAB_HISTORIAL:
            self._panel_historial.recargar()
