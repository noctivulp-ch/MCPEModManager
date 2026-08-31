"""Ajustes del gestor.

Hoy solo hay uno, la clave de CurseForge, pero vive en un diálogo propio porque
es un dato que se pega una vez y no se vuelve a mirar: darle sitio permanente en
una pestaña sería gastarlo en algo de uso único.
"""

from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel, QLineEdit, QVBoxLayout, QWidget

from wulf_qt import GAP_CELDA, Acciones, Dialogo, boton, boton_plano, boton_primario

from mcpemod.core import Store
from mcpemod.core.fuentes import URL_CONSOLA
from mcpemod.ui.ajustes import CLAVE_CURSEFORGE
from mcpemod.ui.estilo import TEXTO_SECUNDARIO

_EXPLICACION = (
    "CurseForge exige una clave para consultar su catálogo. Es gratuita.\n"
    "Sin ella la app usa MCPEDL, que ya sirve el catálogo de Bedrock de\n"
    "CurseForge con descarga directa desde el mismo sitio."
)


def dialogo_ajustes(store: Store, parent: QWidget | None = None) -> Dialogo:
    cuerpo = QWidget()
    layout = QVBoxLayout(cuerpo)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(GAP_CELDA // 2)

    titulo = QLabel("Clave de la API de CurseForge")
    titulo.setStyleSheet("font-weight: 600;")
    layout.addWidget(titulo)

    nota = QLabel(_EXPLICACION)
    nota.setStyleSheet(f"color: {TEXTO_SECUNDARIO}; font-size: 11px;")
    layout.addWidget(nota)

    campo = QLineEdit(store.ajuste(CLAVE_CURSEFORGE))
    campo.setPlaceholderText("pega aquí la clave, o déjalo vacío")
    # No es una contraseña, pero se queda en pantalla y no hace falta leerla.
    campo.setEchoMode(QLineEdit.EchoMode.Password)
    campo.setMinimumWidth(360)
    layout.addWidget(campo)

    enlace = boton_plano("Conseguir una clave en console.curseforge.com")
    enlace.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(URL_CONSOLA)))
    layout.addWidget(enlace)

    guardar = boton_primario("Guardar")
    cancelar = boton("Cancelar")
    acciones = Acciones(confirmar=guardar, cancelar=cancelar)

    dialogo = Dialogo("Ajustes", cuerpo, acciones, parent)
    guardar.clicked.connect(
        lambda: (store.guardar_ajuste(CLAVE_CURSEFORGE, campo.text().strip()),
                 dialogo.accept())
    )
    cancelar.clicked.connect(dialogo.reject)
    return dialogo
