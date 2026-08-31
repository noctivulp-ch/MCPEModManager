"""Ventana principal del gestor."""

from __future__ import annotations

from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QMainWindow, QTabWidget, QWidget,
)

from wulf_qt import GAP_CELDA, Bandeja, Pozo, boton_plano, mostrar_aviso

from mcpemod.core import Instalacion, Installer, Scanner, Store
from mcpemod.senales import conectar
from mcpemod.ui import soltar
from mcpemod.ui.dialogo_ajustes import dialogo_ajustes
from mcpemod.ui.panel_actualizaciones import PanelActualizaciones
from mcpemod.ui.panel_descargas import PanelDescargas
from mcpemod.ui.panel_historial import PanelHistorial
from mcpemod.ui.panel_instalados import PanelInstalados
from mcpemod.ui.widgets import VeloSoltar, boton_ruta

_TITULO = "MCPE Mod Manager"
_ANCHO_MIN = 820
_ALTO_MIN = 560

_TAB_CARPETAS = 1
_TAB_HISTORIAL = 3


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

        self._velo = VeloSoltar(self)
        self.setAcceptDrops(True)

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
        self._panel_actualizaciones = PanelActualizaciones(
            self._store, self._scanner, self._installer
        )
        self._panel_historial = PanelHistorial(self._store)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.addTab(self._panel_instalados, "Instalado")
        self._tabs.addTab(self._panel_descargas, "Carpetas")
        self._tabs.addTab(self._panel_actualizaciones, "Actualizaciones")
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
        self._fila_barra = fila = QHBoxLayout(contenedor)
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

        # Las carpetas vigiladas se listan en la pestaña Carpetas, que es donde
        # se gestionan; repetirlas aquí solo cabría si fueran una.
        self._boton_ruta = boton_ruta(self._scanner.instalacion.com_mojang)
        fila.addWidget(self._boton_ruta)

        ajustes = boton_plano("Ajustes")
        conectar(ajustes.clicked, self._abrir_ajustes)
        fila.addWidget(ajustes)

        return Pozo(contenedor)

    def _abrir_ajustes(self) -> None:
        dialogo_ajustes(self._store, self).exec()

    def _actualizar_ruta(self) -> None:
        nuevo = boton_ruta(self._scanner.instalacion.com_mojang)
        self._fila_barra.replaceWidget(self._boton_ruta, nuevo)
        self._boton_ruta.deleteLater()
        self._boton_ruta = nuevo

    def _al_elegir_instalacion(self, indice: int) -> None:
        instalacion = self._combo.itemData(indice)
        if instalacion is None or instalacion == self._scanner.instalacion:
            return
        self._installer.cambiar_instalacion(instalacion)
        self._scanner.cambiar_instalacion(instalacion)
        self._actualizar_ruta()

    # ── Arrastrar y soltar ────────────────────────────────────────────────────

    def dragEnterEvent(self, evento: QDragEnterEvent) -> None:  # noqa: N802 (API de Qt)
        if soltar.admite(soltar.rutas_de(evento.mimeData())):
            evento.acceptProposedAction()
            self._velo.mostrar_sobre(self.centralWidget())

    def dragLeaveEvent(self, evento: QDragLeaveEvent) -> None:  # noqa: N802 (API de Qt)
        self._velo.hide()
        super().dragLeaveEvent(evento)

    def dropEvent(self, evento: QDropEvent) -> None:  # noqa: N802 (API de Qt)
        self._velo.hide()
        rutas = soltar.rutas_de(evento.mimeData())
        if not soltar.admite(rutas):
            return
        evento.acceptProposedAction()

        resultado = soltar.procesar(rutas, self._scanner, self._installer)
        if resultado.hubo_algo or resultado.ignorados:
            mostrar_aviso(self, resultado.mensaje())

    def _al_cambiar_tab(self, indice: int) -> None:
        if indice == _TAB_CARPETAS:
            self._panel_descargas.marcar_vistas()
        elif indice == _TAB_HISTORIAL:
            self._panel_historial.recargar()
