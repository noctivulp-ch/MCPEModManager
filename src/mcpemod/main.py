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

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from wulf_qt import Acento, Modo, aplicar  # noqa: E402

from mcpemod.core import DB_PATH, Installer, Scanner, Store, detectar_instalaciones  # noqa: E402
from mcpemod.ui import VentanaPrincipal  # noqa: E402

_SIN_JUEGO = (
    "No encontré ninguna instalación de Minecraft Bedrock.\n\n"
    "Se busca la carpeta games/com.mojang de mcpelauncher, tanto en la\n"
    "instalación nativa (~/.local/share/mcpelauncher) como en las flatpak."
)


def _trabajo_en_segundo_plano_funciona(app: QApplication) -> bool:
    """Comprueba el camino entero de una tarea de fondo, sin tocar la red.

    Es lo que el arranque a secas no cubre: los hilos solo entran en juego al
    pulsar un botón, y ahí es donde ha fallado el binario compilado más de una
    vez sin que la comprobación se enterara.
    """
    from PySide6.QtCore import QElapsedTimer

    from mcpemod.ui.tareas import Tarea

    recibidos: list = []
    tarea = Tarea()
    tarea.lanzar(lambda emitir, cancelado: emitir("ok"), recibidos.append)

    reloj = QElapsedTimer()
    reloj.start()
    while not recibidos and reloj.elapsed() < 5000:
        app.processEvents()

    tarea.parar()
    return bool(recibidos)


def main() -> None:
    # Arranca, dibuja un ciclo de eventos y sale con 0. Es lo que ejecuta
    # `build.sh` sobre el binario ya compilado: el toolchain puede producir un
    # ejecutable que compila y no arranca, y sin esto no se nota hasta abrirlo.
    autotest = "--autotest" in sys.argv

    app = QApplication(sys.argv)
    app.setApplicationName("MCPE Mod Manager")
    app.setOrganizationName("mcpemod")
    aplicar(app, Acento.ORO, Modo.OSCURO)

    instalaciones = detectar_instalaciones()
    if not instalaciones:
        if autotest:
            print("autotest: sin instalación de Bedrock; nada que hacer")
            return
        QMessageBox.critical(None, "MCPE Mod Manager", _SIN_JUEGO)
        sys.exit(1)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    store = Store(DB_PATH)
    scanner = Scanner(store, instalaciones[0])
    installer = Installer(store, instalaciones[0])

    ventana = VentanaPrincipal(store, scanner, installer, instalaciones)
    ventana.show()

    if autotest:
        app.processEvents()
        if not _trabajo_en_segundo_plano_funciona(app):
            print("autotest: el trabajo en segundo plano no devuelve resultados")
            sys.exit(1)
        ventana.close()
        print("autotest: la ventana arranca")
        return

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
