"""Panel del contenido presente en la carpeta del juego."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from mcpemod.core import ErrorInstalacion, Installer, Instalado, Scanner
from mcpemod.core.miniatura import manifiesto_de
from mcpemod.senales import conectar
from mcpemod.ui.dialogo_pack import dialogo_pack
from mcpemod.ui.panel_lista import PanelLista
from mcpemod.ui.widgets import TarjetaInstalado, agrupar, cabecera


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
        """Un solo panel, agrupado por tipo y alfabético dentro de cada grupo."""
        widgets = []
        for categoria, piezas in agrupar(
            self._scanner.leer_instalados(),
            categoria_de=lambda p: p.categoria,
            nombre_de=lambda p: p.nombre,
        ):
            widgets.append(cabecera(categoria, len(piezas)))
            for pieza in piezas:
                tarjeta = TarjetaInstalado(pieza)
                conectar(tarjeta.desinstalar_pedido, self._desinstalar)
                conectar(tarjeta.normalizar_pedido, self._normalizar)
                conectar(tarjeta.abrir, self._ficha)
                widgets.append(tarjeta)
        self._poner(widgets)

    def _ficha(self, pieza: Instalado) -> None:
        """La ficha del pack. Sin ámbito: aquí no se activa nada, así que las
        variantes se enseñan pero no se pueden elegir — eso es de activación."""
        dialogo_pack(pieza, manifiesto_de(pieza), parent=self.window()).exec()

    def _desinstalar(self, pieza: Instalado) -> None:
        try:
            self._installer.desinstalar(pieza)
        except OSError as e:
            self._avisar(f"No se pudo desinstalar {pieza.nombre}: {e}")
        self._scanner.notificar_cambio()

    def _normalizar(self, pieza: Instalado) -> None:
        try:
            self._installer.normalizar(pieza, self._scanner.indice())
        except (ErrorInstalacion, OSError) as e:
            self._avisar(str(e))
        self._scanner.notificar_cambio()
