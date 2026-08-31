"""Punto de entrada de MCPE Mod Manager."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

# `wulf_qt` es una librería local sin instalar. Nuitka la bundlea en el binario,
# así que solo se busca en disco cuando el import falla — de lo contrario el
# ejecutable intentaría abrir una ruta del entorno de desarrollo.
try:
    importlib.import_module("wulf_qt")
except ImportError:
    _RAIZ = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(_RAIZ / "#Libs/wulfenite_ui/PyQT/src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from wulf_qt import Acento, Modo, aplicar  # noqa: E402

from mcpemod.core import Installer, Scanner, Store  # noqa: E402
from mcpemod.core.rutas import APP_DATA, DB_PATH  # noqa: E402
from mcpemod.ui import VentanaPrincipal  # noqa: E402


def main() -> None:
    APP_DATA.mkdir(parents=True, exist_ok=True)

    app = QApplication(sys.argv)
    app.setApplicationName("MCPE Mod Manager")
    app.setOrganizationName("mcpemod")
    aplicar(app, Acento.ORO, Modo.OSCURO)

    store = Store(DB_PATH)
    scanner = Scanner(store)
    installer = Installer(store)

    ventana = VentanaPrincipal(store, scanner, installer)
    ventana.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
