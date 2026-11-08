"""Avisa de conexiones de señal que romperían el binario compilado.

El fallo de Nuitka (`docs/decisiones/0008`) salta en la **segunda** conexión de
un método de objeto en todo el proceso, sea cual sea el método. En el intérprete
no se nota; en el ejecutable, la ventana no abre.

Por eso toda conexión va por `mcpemod.senales.conectar`, que envuelve el slot en
una función libre. Este script busca las que se hayan escapado.

Uso: python tools/lint_conexiones.py [directorio…]
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

#: Aquí vive el helper: es el único sitio donde `connect` se llama a pelo.
_EXENTOS = {"senales.py"}


def _es_metodo_de_objeto(nodo: ast.expr) -> bool:
    """`objeto.metodo` sí; `lambda: …` y `funcion` no."""
    return isinstance(nodo, ast.Attribute)


def revisar(ruta: Path) -> list[tuple[int, str]]:
    if ruta.name in _EXENTOS:
        return []
    try:
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    except SyntaxError:
        return []

    hallazgos = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call):
            continue
        funcion = nodo.func
        if not (isinstance(funcion, ast.Attribute) and funcion.attr == "connect"):
            continue
        # `sqlite3.connect(...)` no tiene nada que ver.
        if isinstance(funcion.value, ast.Name) and funcion.value.id == "sqlite3":
            continue
        if nodo.args and _es_metodo_de_objeto(nodo.args[0]):
            hallazgos.append((nodo.lineno, ast.unparse(nodo)[:88]))
    return hallazgos


def main(argv: list[str]) -> int:
    raices = [Path(a) for a in argv[1:]] or [Path("src")]
    total = 0
    for raiz in raices:
        for archivo in sorted(raiz.rglob("*.py")):
            for linea, fragmento in revisar(archivo):
                total += 1
                print(f"{archivo}:{linea}: conecta un método de objeto — usa "
                      f"mcpemod.senales.conectar\n    {fragmento}")
    if total:
        print(f"\n{total} conexión(es) que romperían el binario compilado.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
