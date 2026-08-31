"""Panel de los archivos instalables que hay en la carpeta de descargas."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QWidget

from mcpemod.core import Analisis, ErrorInstalacion, Installer, Scanner
from mcpemod.senales import conectar
from mcpemod.ui.panel_lista import PanelLista
from mcpemod.ui.widgets import TarjetaDescarga


class PanelDescargas(PanelLista):
    def __init__(
        self,
        scanner: Scanner,
        installer: Installer,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("No hay contenido de Bedrock en tu carpeta de descargas.", parent)
        self._scanner = scanner
        self._installer = installer
        self._rutas: list[Path] = []
        conectar(scanner.descargas_cambiadas, self.recargar)
        conectar(scanner.instalados_cambiados, self.recargar)
        self.recargar()

    def recargar(self) -> None:
        analisis = self._scanner.leer_descargas()
        instalados = self._scanner.indice_por_uuid()
        self._rutas = [a.ruta for a in analisis]

        tarjetas = []
        for a in analisis:
            tarjeta = TarjetaDescarga(a, instalados, es_nuevo=self._scanner.es_nuevo(a.ruta))
            conectar(tarjeta.instalar_pedido, self._instalar)
            tarjetas.append(tarjeta)
        self._poner(tarjetas)

    def marcar_vistas(self) -> None:
        """El badge NEW se apaga al mirar la pestaña, no al escanear la carpeta.

        Marcarlos al escanear quemaría el aviso mientras el usuario está en otra
        pestaña, que es justo cuando más falta hace.
        """
        self._scanner.marcar_vistos(self._rutas)

    def _instalar(self, analisis: Analisis) -> None:
        try:
            self._installer.instalar(analisis, self._scanner.indice_por_uuid())
        except (ErrorInstalacion, OSError) as e:
            self._avisar(str(e))
        self._scanner.notificar_cambio()
