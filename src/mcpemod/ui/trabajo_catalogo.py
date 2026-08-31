"""Una consulta al catálogo, para correr en un hilo aparte.

Función normal y no `QObject` con señales, por lo mismo que en
`mcpemod.ui.trabajo`: los resultados vuelven por la cola de
`mcpemod.ui.tareas`.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from mcpemod.core.fuentes import Fuente
from mcpemod.core.red import ErrorRed


def consultar(
    fuente: Fuente,
    texto: str,
    pagina: int,
    emitir: Callable[..., None],
    cancelado: threading.Event,
) -> None:
    """Busca si hay texto, pide novedades si no.

    Mensaje: `("listo", publicaciones, error)`.
    """
    texto = texto.strip()
    try:
        resultados = (
            fuente.buscar(texto, pagina=pagina) if texto
            else fuente.recientes(pagina=pagina)
        )
    except ErrorRed as e:
        emitir("listo", [], str(e))
        return

    # Una consulta que el usuario ya descartó no debe pisar lo que mira ahora.
    if not cancelado.is_set():
        emitir("listo", resultados, "")
