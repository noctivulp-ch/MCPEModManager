"""Panel del contenido presente en la carpeta del juego."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from mcpemod.core import ErrorInstalacion, Installer, Instalado, Scanner
from mcpemod.senales import conectar
from mcpemod.ui.panel_lista import PanelLista
from mcpemod.ui.widgets import TarjetaInstalado


class PanelInstalados(PanelLista):
    def __init__(
        self,
        scanner: Scanner,
        installer: Installer,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("No hay nada instalado en esta instalación.", parent)
        self._scanner = scanner
        self._installer = installer
        conectar(scanner.instalados_cambiados, self.recargar)
        self.recargar()

    def recargar(self) -> None:
        tarjetas = []
        for pieza in self._scanner.leer_instalados():
            tarjeta = TarjetaInstalado(pieza)
            conectar(tarjeta.desinstalar_pedido, self._desinstalar)
            conectar(tarjeta.reparar_pedido, self._reparar)
            tarjetas.append(tarjeta)
        self._poner(tarjetas)

    def _desinstalar(self, pieza: Instalado) -> None:
        try:
            self._installer.desinstalar(pieza)
        except OSError as e:
            self._avisar(f"No se pudo desinstalar {pieza.nombre}: {e}")
        self._scanner.notificar_cambio()

    def _reparar(self, pieza: Instalado) -> None:
        try:
            self._installer.reparar(pieza, self._scanner.indice_por_uuid())
        except (ErrorInstalacion, OSError) as e:
            self._avisar(str(e))
        self._scanner.notificar_cambio()
