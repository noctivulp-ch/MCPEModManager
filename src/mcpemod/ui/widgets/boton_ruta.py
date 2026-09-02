"""Una ruta del sistema que se puede abrir, en vez de solo leer.

Enseñar una ruta como texto obliga a copiarla a mano para llegar a ella. Como
botón, un clic la abre en el explorador de archivos — que es lo que se quiere
hacer con ella el 90% de las veces.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from wulf_qt import boton

from mcpemod.ui import iconos

_LARGO_MAX = 52


def abreviar(ruta: Path) -> str:
    """La ruta con `~` y con el medio elidido si no cabe.

    Se recorta por la izquierda: el final —la carpeta concreta— identifica el
    sitio mucho mejor que el principio, que casi siempre es `~/.local/share`.
    """
    try:
        texto = "~/" + str(ruta.relative_to(Path.home()))
    except ValueError:
        texto = str(ruta)

    if len(texto) <= _LARGO_MAX:
        return texto
    return "…" + texto[-(_LARGO_MAX - 1):]


def boton_ruta(ruta: Path, prefijo: str = ""):
    """Un botón que abre `ruta` en el explorador de archivos."""
    existe = ruta.is_dir()
    # El icono de carpeta dice que esto lleva a un sitio del disco; sin él un
    # botón con una ruta dentro se lee como una etiqueta más.
    etiqueta = f"{prefijo}{abreviar(ruta)}" if existe else f"{prefijo}{abreviar(ruta)}  (no existe)"

    b = iconos.poner(boton(etiqueta), iconos.CARPETA)
    b.setEnabled(existe)
    b.setToolTip(f"Abrir {ruta} en el explorador de archivos" if existe
                 else f"{ruta}\nno existe ahora mismo")
    b.setStyleSheet("text-align: left; font-size: 11px; padding: 2px 10px;")
    if existe:
        b.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(ruta))))
    return b
