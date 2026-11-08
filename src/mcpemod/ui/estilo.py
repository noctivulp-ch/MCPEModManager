"""Colores derivados de la laca activa.

Los paneles necesitan el color **real** de la superficie sobre la que pintan:
`Tallado` lo exige para calcular el relieve, y los textos secundarios se leen de
la laca en vez de inventar grises que no pertenecen al sistema.
"""

from __future__ import annotations

import os

from wulf_qt.tokens import LACAS, METALES, SOBRE_METAL, Acento, Modo


def _tema_elegido() -> tuple[Modo, Acento]:
    """`MCPEMOD_TEMA=claro-peltre`; por defecto, oscuro con oro.

    Se lee una sola vez, al importar: los colores de abajo se copian en los
    widgets al construirlos. Ver docs/funciones/tema.md.
    """
    modo, _, acento = os.environ.get("MCPEMOD_TEMA", "").partition("-")
    try:
        return Modo(modo or Modo.OSCURO.value), Acento(acento or Acento.ORO.value)
    except ValueError:
        return Modo.OSCURO, Acento.ORO


MODO, ACENTO = _tema_elegido()
LACA = LACAS[MODO]

METAL = METALES[ACENTO][MODO]
#: Lo que se lee —y se dibuja— encima del metal: el botón primario va
#: relleno, así que un icono teñido con el color del pozo se pierde en él.
SOBRE_METAL_ = SOBRE_METAL[ACENTO][MODO]

SOBRE_BANDEJA = LACA.bandeja
SOBRE_POZO = LACA.pozo
TEXTO_EN_POZO = LACA.texto_en_pozo
TEXTO_SECUNDARIO = LACA.texto_secundario_en_pozo
TEXTO_ATENUADO = LACA.texto_atenuado_en_bandeja

VERDE = "#22c55e"
AMBAR = "#f59e0b"
ROJO = "#ef4444"
GRIS = "#94a3b8"
INDIGO = "#6366f1"
CIAN = "#06b6d4"
VIOLETA = "#a855f7"

#: Un color por clase de contenido, para distinguirlas de un vistazo.
COLOR_CATEGORIA = {
    "recurso": INDIGO,
    "comportamiento": CIAN,
    "skin": VIOLETA,
    "plantilla": "#eab308",
    "mundo": VERDE,
}
