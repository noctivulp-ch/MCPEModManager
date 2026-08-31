"""Panel de archivos en la carpeta de descargas."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from mcpemod.core import ErrorInstalacion, Installer, Mod, Scanner
from mcpemod.senales import conectar
from mcpemod.ui.panel_lista import PanelLista
from mcpemod.ui.widgets import TarjetaMod


class PanelDescargas(PanelLista):
    def __init__(
        self,
        scanner: Scanner,
        installer: Installer,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            "Descargas disponibles",
            "No hay archivos instalables en ~/Downloads.",
            parent,
        )
        self._scanner = scanner
        self._installer = installer
        self._mods: list[Mod] = []
        conectar(scanner.descargas_cambiadas, self.recargar)
        conectar(scanner.mods_cambiados, self.recargar)
        self.recargar()

    def recargar(self) -> None:
        self._mods = self._scanner.leer_descargas()
        instalados = {m.canonico: m for m in self._scanner.leer_instalados()}

        tarjetas = []
        for mod in self._mods:
            tarjeta = TarjetaMod(mod, mod_instalado=instalados.get(mod.canonico))
            conectar(tarjeta.instalar_pedido, self._instalar)
            tarjetas.append(tarjeta)
        self._poner(tarjetas)

    def marcar_vistas(self) -> None:
        """El badge NEW se apaga cuando el usuario mira la pestaña, no antes.

        Marcarlos al leer el directorio quemaría el aviso mientras el usuario
        está en otra pestaña, que es justo cuando más falta hace.
        """
        self._scanner.marcar_vistas(self._mods)

    def _instalar(self, mod: Mod) -> None:
        try:
            self._installer.instalar(mod.origen)
        except (ErrorInstalacion, OSError) as e:
            self._avisar(str(e))
        self._scanner.notificar_cambio()
