"""Arranque real de la UI sin display: construye la ventana y recorre las pestañas.

No es un test de pytest a propósito — necesita `QApplication` y toca los
directorios reales del sistema. Existe porque los tres fallos que dejaron la app
sin arrancar (firmas de `wulf_qt` mal llamadas) eran invisibles para la suite
unitaria y para pyflakes: solo se ven construyendo los widgets.

Uso: QT_QPA_PLATFORM=offscreen python tests/smoke_ui.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PySide6.QtWidgets import QApplication

from wulf_qt import Acento, Modo, aplicar

from mcpemod.core import EntradaHistorial, Installer, Mod, Scanner, Store, TipoArchivo
from mcpemod.ui import VentanaPrincipal
from mcpemod.ui.widgets import TarjetaMod


def main() -> int:
    app = QApplication(sys.argv)
    aplicar(app, Acento.ORO, Modo.OSCURO)

    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "smoke.db")
        store.registrar(EntradaHistorial("instalar", "x.so", "1.0.0", None))
        store.registrar(EntradaHistorial("actualizar", "x.so", "1.1.0", "1.0.0"))
        store.registrar(EntradaHistorial("desinstalar", "x.so", "1.1.0", None))

        scanner = Scanner(store)
        ventana = VentanaPrincipal(store, scanner, Installer(store))
        ventana.show()

        for indice in range(3):
            ventana._tabs.setCurrentIndex(indice)
            app.processEvents()

        # Las tarjetas se construyen con y sin contraparte instalada; ambas ramas
        # tocan código distinto (badges de versión, etiqueta del botón).
        base = Mod(
            nombre="Demo-v1.0.0", canonico="Demo", archivo="Demo-v1.0.0.so",
            rutas=[Path(tmp) / "Demo-v1.0.0.so"], tipo=TipoArchivo.SO,
            version="1.0.0", hash_sha256="0" * 64, primera_vez=True,
        )
        nueva = Mod(
            nombre="Demo-v2.0.0", canonico="Demo", archivo="Demo-v2.0.0.so",
            rutas=[Path(tmp) / "Demo-v2.0.0.so"], tipo=TipoArchivo.SO,
            version="2.0.0", hash_sha256="1" * 64,
        )
        for mod, instalado in ((base, None), (nueva, base), (base, nueva), (base, base)):
            TarjetaMod(mod, mod_instalado=instalado)

        instalado = Mod(**{**base.__dict__, "instalado": True})
        TarjetaMod(instalado)

        app.processEvents()

    print("smoke UI: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
