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

    # Contenido de la tienda: su tarjeta no lleva botones, así que es una rama
    # distinta de la de un pack normal.
    from mcpemod.core.manifiesto import MAGIA_CONTENTS
    comprado = inst.resource_packs / "yQZQHkZBH9Q="
    comprado.mkdir()
    (comprado / "manifest.json").write_text(_manifiesto("Comprado", "uuid-tienda"))
    (comprado / "contents.json").write_bytes(b"\x00" * 4 + MAGIA_CONTENTS)
    (comprado / "signatures.json").write_bytes(b"\x00" * 16)

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


def _probar_arrastre(app, ventana, raiz: Path) -> None:
    """Recorre el ciclo entero de arrastre, que es donde vive el velo."""
    from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
    from PySide6.QtGui import QDragEnterEvent, QDropEvent

    suelto = _pack(raiz / "fuera" / "Arrastrado.mcpack", "Arrastrado", "uuid-drag")
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(suelto))])
    posicion = QPoint(10, 10)
    botones = Qt.MouseButton.LeftButton
    sin_teclas = Qt.KeyboardModifier.NoModifier

    ventana.dragEnterEvent(
        QDragEnterEvent(posicion, Qt.DropAction.CopyAction, mime, botones, sin_teclas)
    )
    app.processEvents()
    assert ventana._velo.isVisible(), "el velo no apareció al arrastrar"

    ventana.dropEvent(
        QDropEvent(posicion, Qt.DropAction.CopyAction, mime, botones, sin_teclas)
    )
    app.processEvents()
    assert not ventana._velo.isVisible(), "el velo se quedó puesto tras soltar"


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

        # Dos carpetas vigiladas: la barra dibuja los botones de quitar solo
        # cuando hay más de una, así que con una sola no se ejercitan.
        segunda = raiz / "Mods bajados"
        segunda.mkdir()
        _pack(segunda / "Otro.mcpack", "Otro pack", "uuid-otro")
        scanner.agregar_carpeta(segunda)
        installer = Installer(store, instalacion)

        # Genera historial de las cuatro acciones, para que el panel las pinte todas.
        installer.instalar(analizar(descargas / "Nuevo.mcpack"), scanner.indice_por_uuid())
        installer.instalar(analizar(descargas / "Bonito v2.mcpack"), scanner.indice_por_uuid())
        suelto = next(p for p in scanner.leer_instalados() if p.forma.normalizable)
        installer.normalizar(suelto, scanner.indice_por_uuid())
        gestionable = next(p for p in scanner.leer_instalados() if p.gestionable)
        installer.desinstalar(gestionable)

        ventana = VentanaPrincipal(store, scanner, installer, [instalacion])
        ventana.show()

        for indice in range(3):
            ventana._tabs.setCurrentIndex(indice)
            app.processEvents()

        _probar_arrastre(app, ventana, raiz)

        assert store.historial(), "el historial quedó vacío"

    print("smoke UI: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
