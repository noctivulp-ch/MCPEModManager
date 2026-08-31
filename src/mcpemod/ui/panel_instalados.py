"""Panel de mods instalados en mcpelauncher."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from mcpemod.core import Installer, Mod, Scanner
from mcpemod.ui.panel_lista import PanelLista
from mcpemod.ui.widgets import TarjetaMod


class PanelInstalados(PanelLista):
    def __init__(
        self,
        scanner: Scanner,
        installer: Installer,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Mods instalados", "No hay ningún mod instalado.", parent)
        self._scanner = scanner
        self._installer = installer
        scanner.mods_cambiados.connect(self.recargar)
        self.recargar()

    def recargar(self) -> None:
        tarjetas = []
        for mod in self._scanner.leer_instalados():
            tarjeta = TarjetaMod(mod)
            tarjeta.desinstalar_pedido.connect(self._desinstalar)
            tarjetas.append(tarjeta)
        self._poner(tarjetas)

    def _desinstalar(self, mod: Mod) -> None:
        try:
            self._installer.desinstalar(mod)
        except OSError as e:
            self._avisar(f"No se pudo desinstalar {mod.nombre}: {e}")
        self._scanner.notificar_cambio()
