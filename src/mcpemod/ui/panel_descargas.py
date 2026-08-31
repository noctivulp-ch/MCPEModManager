"""Panel del contenido instalable que hay en las carpetas vigiladas."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QWidget

from mcpemod.core import Analisis, ErrorInstalacion, Installer, Scanner
from mcpemod.senales import conectar
from mcpemod.ui.panel_lista import PanelLista
from mcpemod.ui.widgets import BarraCarpetas, TarjetaDescarga


class PanelDescargas(PanelLista):
    def __init__(
        self,
        scanner: Scanner,
        installer: Installer,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("No hay contenido de Bedrock en las carpetas vigiladas.", parent)
        self._scanner = scanner
        self._installer = installer
        self._rutas: list[Path] = []

        self._barra = BarraCarpetas(scanner.carpetas())
        conectar(self._barra.agregar_pedido, self._agregar_carpeta)
        conectar(self._barra.quitar_pedido, self._quitar_carpeta)
        self._cabecera(self._barra)

        conectar(scanner.descargas_cambiadas, self.recargar)
        conectar(scanner.instalados_cambiados, self.recargar)
        conectar(scanner.carpetas_cambiadas, self._recargar_carpetas)
        self.recargar()

    def recargar(self) -> None:
        analisis = self._scanner.leer_descargas()
        instalados = self._scanner.indice_por_uuid()
        self._rutas = [a.ruta for a in analisis]
        varias = len(self._scanner.carpetas()) > 1

        tarjetas = []
        for a in analisis:
            tarjeta = TarjetaDescarga(
                a, instalados,
                es_nuevo=self._scanner.es_nuevo(a.ruta),
                # Con una sola carpeta la procedencia es obvia y solo estorba.
                mostrar_carpeta=varias,
            )
            conectar(tarjeta.instalar_pedido, self._instalar)
            tarjetas.append(tarjeta)
        self._poner(tarjetas)

    def marcar_vistas(self) -> None:
        """El badge NEW se apaga al mirar la pestaña, no al escanear la carpeta.

        Marcarlos al escanear quemaría el aviso mientras el usuario está en otra
        pestaña, que es justo cuando más falta hace.
        """
        self._scanner.marcar_vistos(self._rutas)

    def _recargar_carpetas(self) -> None:
        self._barra.poner(self._scanner.carpetas())

    def _agregar_carpeta(self, carpeta: Path) -> None:
        if carpeta in self._scanner.carpetas():
            self._avisar(f"Ya estaba vigilando {carpeta}")
            return
        self._scanner.agregar_carpeta(carpeta)

    def _quitar_carpeta(self, carpeta: Path) -> None:
        if not self._scanner.quitar_carpeta(carpeta):
            self._avisar("Tiene que quedar al menos una carpeta vigilada")

    def _instalar(self, analisis: Analisis) -> None:
        try:
            self._installer.instalar(analisis, self._scanner.indice())
        except (ErrorInstalacion, OSError) as e:
            self._avisar(str(e))
        self._scanner.notificar_cambio()
