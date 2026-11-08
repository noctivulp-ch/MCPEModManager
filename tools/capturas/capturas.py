#!/usr/bin/env python3
"""Regenera las tres capturas del README (docs/capturas/*.png).

    python3 tools/capturas/capturas.py

Construye la ventana con la plataforma `offscreen` de Qt —no aparece nada en
pantalla— sobre una instalación de Bedrock inventada en un temporal: los packs,
sus iconos y el mundo los crea este script, así que no se lee el juego real ni
sale ningún dato ajeno. Saca «Instalado» en oscuro con oro, la activación de un
mundo en claro con peltre, y une claro y oscuro con jade en un corte diagonal.

El tema de la app se fija al importar (`MCPEMOD_TEMA`, ver docs/funciones/tema.md),
así que cada variante se saca en un proceso aparte. Ese proceso lleva `HOME` en
el temporal: la ruta que enseña la ventana sale como `~/.local/share/…` y nada
puede tocar la carpeta personal de verdad.

Necesita la app instalada (o `src/` y `wulf_qt` en el PYTHONPATH), Pillow y NumPy.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image  # noqa: E402
from PySide6.QtCore import QBuffer, QEvent, QIODevice, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from wulf_qt import aplicar  # noqa: E402

from corte_diagonal import componer  # noqa: E402

SALIDA = RAIZ / "docs" / "capturas"
ANCHO, ALTO = 1180, 960

#: (nombre, tipo de módulo, versión, color del icono). Inventados.
PACKS = [
    ("Cielo Suave", "resources", (2, 1, 0), "#5b8fd9"),
    ("Hojas Vivas", "resources", (1, 4, 2), "#4caf6a"),
    ("Agua Clara", "resources", (3, 0, 0), "#3fb6c4"),
    ("Antorchas Cálidas", "resources", (1, 0, 3), "#e0913a"),
    ("Interfaz Limpia", "resources", (5, 2, 0), "#9a7bd1"),
    ("Herramientas Extra", "data", (1, 2, 0), "#c9604f"),
    ("Granja Fácil", "data", (0, 9, 1), "#a8b84a"),
]


def _icono(color: str) -> bytes:
    imagen = QImage(128, 128, QImage.Format.Format_ARGB32)
    imagen.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(imagen)
    gradiente = QLinearGradient(0, 0, 128, 128)
    base = QColor(color)
    gradiente.setColorAt(0, base.lighter(135))
    gradiente.setColorAt(1, base.darker(140))
    pintor.fillRect(0, 0, 128, 128, gradiente)
    pintor.fillRect(32, 32, 64, 64, base.lighter(160))
    pintor.end()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    imagen.save(buffer, "PNG")
    return bytes(buffer.data())


def _manifiesto(nombre: str, tipo: str, version: tuple[int, ...]) -> str:
    uuid = f"00000000-0000-4000-8000-{hashlib.sha256(nombre.encode()).hexdigest()[:12]}"
    return json.dumps({
        "format_version": 2,
        "header": {"name": nombre, "description": "Pack de demostración",
                   "uuid": uuid, "version": list(version), "min_engine_version": [1, 21, 0]},
        "modules": [{"type": tipo, "uuid": uuid[:-1] + "1", "version": list(version)}],
        "metadata": {"authors": ["NoctiVulp"]},
    })


def _preparar(raiz: Path):
    from mcpemod.core.rutas import Instalacion

    instalacion = Instalacion("Nativa", raiz / "mcpelauncher", raiz / "mcpelauncher/games/com.mojang")
    for carpeta in instalacion.directorios_contenido:
        carpeta.mkdir(parents=True)
    (instalacion.com_mojang / "minecraftpe").mkdir(parents=True, exist_ok=True)

    for nombre, tipo, version, color in PACKS:
        padre = instalacion.resource_packs if tipo == "resources" else instalacion.behavior_packs
        carpeta = padre / nombre.replace(" ", "")[:10]
        carpeta.mkdir()
        (carpeta / "manifest.json").write_text(_manifiesto(nombre, tipo, version))
        (carpeta / "pack_icon.png").write_bytes(_icono(color))

    mundo = instalacion.mundos / "AbCdEfGhIjk="
    mundo.mkdir()
    (mundo / "level.dat").write_bytes(b"nivel")
    (mundo / "levelname.txt").write_text("Isla del faro")

    descargas = Path.home() / "Descargas"
    descargas.mkdir()
    for nombre, tipo, version, color in (("Cielo Suave", "resources", (2, 2, 0), "#5b8fd9"),
                                         ("Nubes Altas", "resources", (1, 0, 0), "#8fa6c9")):
        with zipfile.ZipFile(descargas / f"{nombre}.mcpack", "w") as zf:
            zf.writestr("manifest.json", _manifiesto(nombre, tipo, version))
            zf.writestr("pack_icon.png", _icono(color))
    return instalacion, descargas


def _asentar(app: QApplication) -> None:
    for _ in range(6):
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
        app.processEvents()


def _activar_algunos(instalacion) -> None:
    from mcpemod.core import Scanner, Store
    from mcpemod.core.activacion import Global, mundos_de

    scanner = Scanner(Store(Path.home() / "activar.db"), instalacion)
    por_nombre = {p.nombre: p for p in scanner.leer_instalados()}
    mundo = mundos_de(instalacion)[0]
    for nombre in ("Agua Clara", "Cielo Suave", "Herramientas Extra"):
        mundo.activar(por_nombre[nombre])
    Global(instalacion).activar(por_nombre["Interfaz Limpia"])


def capturar_variante(vista: str, destino: Path) -> None:
    """Lo que hace el proceso hijo: una ventana, una vista, un PNG."""
    from mcpemod.core import Installer, Scanner, Store, rutas, scanner as modulo_scanner
    from mcpemod.core.activacion import mundos_de
    from mcpemod.ui import VentanaPrincipal
    from mcpemod.ui.estilo import ACENTO, MODO

    app = QApplication(sys.argv)
    aplicar(app, ACENTO, MODO)
    instalacion, descargas = _preparar(Path.home() / ".local/share")
    rutas.carpeta_descargas = lambda: descargas
    modulo_scanner.carpeta_descargas = lambda: descargas
    _activar_algunos(instalacion)

    store = Store(Path.home() / "capturas.db")
    scanner = Scanner(store, instalacion)
    ventana = VentanaPrincipal(store, scanner, Installer(store, instalacion), [instalacion])
    ventana.resize(ANCHO, ALTO)
    ventana.show()
    _asentar(app)

    if vista == "activacion":
        ventana._tabs.setCurrentIndex(1)
        panel = ventana._panel_activacion
        panel.recargar()
        _asentar(app)
        panel._entrar(mundos_de(instalacion)[0])
    else:
        ventana._tabs.setCurrentIndex(0)
    _asentar(app)
    ventana.grab().save(str(destino))


def _hijo(vista: str, tema: str, destino: Path) -> None:
    with tempfile.TemporaryDirectory() as casa:
        entorno = dict(os.environ, HOME=casa, MCPEMOD_TEMA=tema, QT_QPA_PLATFORM="offscreen")
        subprocess.run([sys.executable, __file__, "--variante", vista, str(destino)],
                       env=entorno, check=True)


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    _hijo("instalado", "oscuro-oro", SALIDA / "instalado-oscuro-oro.png")
    _hijo("activacion", "claro-peltre", SALIDA / "activacion-claro-peltre.png")
    with tempfile.TemporaryDirectory() as tmp:
        claro, oscuro = Path(tmp, "claro.png"), Path(tmp, "oscuro.png")
        _hijo("instalado", "claro-jade", claro)
        _hijo("instalado", "oscuro-jade", oscuro)
        componer(Image.open(claro), Image.open(oscuro), 0.035, 3).save(
            SALIDA / "instalado-claro-oscuro.png", optimize=True)
    print("\n".join(sorted(p.name for p in SALIDA.glob("*.png"))))


if __name__ == "__main__":
    if sys.argv[1:2] == ["--variante"]:
        capturar_variante(sys.argv[2], Path(sys.argv[3]))
    else:
        main()
