"""Una lista agrupada bajo títulos de categoría.

Sustituye a distinguir los tipos por el color de una etiqueta: los colores eran
un provisional que no sale de la laca, y con seis categorías tampoco se
recuerdan. Un título por grupo se lee sin aprenderse nada, y deja el orden
alfabético dentro de cada uno, que es como se busca algo por su nombre.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from wulf_qt import GAP_CELDA, PARED, Tallado

from mcpemod.core.contenido import Categoria
from mcpemod.ui.estilo import SOBRE_BANDEJA, TEXTO_SECUNDARIO

#: El orden en que se muestran los grupos. Lo que más se toca, primero.
ORDEN = (
    Categoria.RECURSO,
    Categoria.COMPORTAMIENTO,
    Categoria.SKIN,
    Categoria.PLANTILLA,
    Categoria.MUNDO,
)


def agrupar(elementos: Iterable, categoria_de: Callable, nombre_de: Callable) -> list[tuple]:
    """Los elementos por categoría, en orden fijo de grupo y alfabético dentro."""
    grupos: dict[Categoria, list] = {}
    for elemento in elementos:
        grupos.setdefault(categoria_de(elemento), []).append(elemento)

    ordenados = []
    for categoria in ORDEN:
        if categoria in grupos:
            ordenados.append((categoria, sorted(grupos[categoria], key=lambda e: nombre_de(e).lower())))
    # Cualquier categoría que no esté en el orden fijo, al final y no perdida.
    for categoria, elementos_ in grupos.items():
        if categoria not in ORDEN:
            ordenados.append((categoria, sorted(elementos_, key=lambda e: nombre_de(e).lower())))
    return ordenados


def cabecera(categoria: Categoria, cuantos: int) -> QWidget:
    """El título de un grupo, con cuántos trae."""
    contenedor = QWidget()
    caja = QVBoxLayout(contenedor)
    caja.setContentsMargins(0, GAP_CELDA // 2, 0, PARED // 2)
    caja.setSpacing(0)

    titulo = Tallado(f"{categoria.etiqueta}   ·   {cuantos}", sobre=SOBRE_BANDEJA)
    titulo.setAlignment(Qt.AlignmentFlag.AlignVCenter)
    titulo.setStyleSheet("font-size: 12px; font-weight: 600;")
    caja.addWidget(titulo)
    return contenedor


def aviso(texto: str) -> QLabel:
    """Una nota dentro de la lista: por qué un grupo no está, o está vacío."""
    etiqueta = QLabel(texto)
    etiqueta.setWordWrap(True)
    etiqueta.setStyleSheet(f"color: {TEXTO_SECUNDARIO}; font-size: 11px;")
    return etiqueta
