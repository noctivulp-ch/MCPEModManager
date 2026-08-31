"""Arranque real de la UI sin pantalla: construye la ventana y la recorre entera.

No es un test de pytest a propósito — necesita `QApplication`. Existe porque los
fallos que dejaron una versión de esta app sin arrancar (llamadas a `wulf_qt` con
firmas equivocadas) no los ve ni pyflakes ni la suite unitaria: solo aparecen
construyendo los widgets de verdad.

Trabaja sobre una instalación falsa en un temporal, así que no toca el juego.

Uso: QT_QPA_PLATFORM=offscreen python tests/smoke_ui.py
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path

from PySide6.QtWidgets import QApplication

from wulf_qt import Acento, Modo, aplicar

from mcpemod.core import Installer, Scanner, Store, analizar
from mcpemod.core.rutas import Instalacion
from mcpemod.ui import VentanaPrincipal


def _manifiesto(nombre, uuid, tipo="resources", version=(1, 0, 0)):
    return json.dumps({
        "format_version": 2,
        "header": {"name": nombre, "uuid": uuid, "version": list(version)},
        "modules": [{"type": tipo, "uuid": uuid, "version": list(version)}],
    })


def _pack(destino: Path, nombre, uuid, **kw) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w") as zf:
        zf.writestr("manifest.json", _manifiesto(nombre, uuid, **kw))
        zf.writestr("pack_icon.png", b"\x89PNG")
    return destino


def _preparar(raiz: Path) -> tuple[Instalacion, Path]:
    inst = Instalacion("Prueba", raiz, raiz / "games/com.mojang")
    for carpeta in inst.directorios_contenido:
        carpeta.mkdir(parents=True)

    # Un pack normal, uno que el juego no carga y un mundo: las tres formas que
    # tiene la tarjeta de instalado.
    activo = inst.resource_packs / "Bonito"
    activo.mkdir()
    (activo / "manifest.json").write_text(_manifiesto("Bonito", "uuid-bonito"))

    _pack(inst.resource_packs / "SinExtraer.mcpack", "Sin extraer", "uuid-suelto")

    mundo = inst.mundos / "bE2ZIuTv+eY="
    mundo.mkdir()
    (mundo / "level.dat").write_bytes(b"nivel")
    (mundo / "levelname.txt").write_text("Mi mundo")

    descargas = raiz / "Descargas"
    _pack(descargas / "Bonito v2.mcpack", "Bonito", "uuid-bonito", version=(2, 0, 0))
    _pack(descargas / "Nuevo.mcpack", "Pack nuevo", "uuid-nuevo", tipo="data")

    addon = descargas / "Combo.mcaddon"
    with zipfile.ZipFile(addon, "w") as zf:
        for nombre_interno, uuid, tipo in (("RP.mcpack", "u-rp", "resources"),
                                           ("BP.mcpack", "u-bp", "data")):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as interno:
                interno.writestr("manifest.json", _manifiesto(nombre_interno, uuid, tipo))
            zf.writestr(nombre_interno, buf.getvalue())

    return inst, descargas


def main() -> int:
    app = QApplication(sys.argv)
    aplicar(app, Acento.ORO, Modo.OSCURO)

    with tempfile.TemporaryDirectory() as tmp:
        raiz = Path(tmp)
        instalacion, descargas = _preparar(raiz)

        from mcpemod.core import rutas, scanner as modulo_scanner
        rutas.carpeta_descargas = lambda: descargas
        modulo_scanner.carpeta_descargas = lambda: descargas

        store = Store(raiz / "smoke.db")
        scanner = Scanner(store, instalacion)
        installer = Installer(store, instalacion)

        # Genera historial de las cuatro acciones, para que el panel las pinte todas.
        installer.instalar(analizar(descargas / "Nuevo.mcpack"), scanner.indice_por_uuid())
        installer.instalar(analizar(descargas / "Bonito v2.mcpack"), scanner.indice_por_uuid())
        suelto = next(p for p in scanner.leer_instalados() if not p.activo)
        installer.reparar(suelto, scanner.indice_por_uuid())
        installer.desinstalar(scanner.leer_instalados()[0])

        ventana = VentanaPrincipal(store, scanner, installer, [instalacion])
        ventana.show()

        for indice in range(3):
            ventana._tabs.setCurrentIndex(indice)
            app.processEvents()

        assert store.historial(), "el historial quedó vacío"

    print("smoke UI: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
