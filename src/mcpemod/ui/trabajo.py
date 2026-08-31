"""El barrido de actualizaciones, para correr en un hilo aparte.

Es una función normal, no un `QObject` con señales: los resultados vuelven por la
cola de `mcpemod.ui.tareas`. El porqué está ahí.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from mcpemod.core import Instalado
from mcpemod.core.actualizaciones import Buscador
from mcpemod.core.red import ErrorRed

#: Cuántos packs se consultan a la vez. Casi todo el tiempo se va esperando
#: respuestas, así que unos pocos en paralelo acortan mucho el barrido; subirlo
#: más no gana nada, porque el reparto de cortesía de `red` espacia igual las
#: peticiones a un mismo servicio.
EN_PARALELO = 4


def comprobar_todos(
    buscador: Buscador,
    piezas: list[Instalado],
    emitir: Callable[..., None],
    cancelado: threading.Event,
) -> None:
    """Pregunta a los catálogos por cada pack, informando según van saliendo.

    Mensajes: `("avance", hechos, total, nombre)`, `("encontrado", resultado)` y
    `("terminado", hechos, error)`.
    """
    total = len(piezas)
    hechos = 0
    error = ""

    with ThreadPoolExecutor(max_workers=EN_PARALELO) as pool:
        tareas = {pool.submit(buscador.comprobar, p): p for p in piezas}
        for tarea in as_completed(tareas):
            pieza = tareas[tarea]
            if cancelado.is_set():
                for pendiente in tareas:
                    pendiente.cancel()
                break

            emitir("avance", hechos, total, pieza.nombre)
            try:
                resultado = tarea.result()
            except ErrorRed as e:
                # Sin red no tiene sentido seguir con los cincuenta que faltan.
                error = str(e)
                for pendiente in tareas:
                    pendiente.cancel()
                break
            except Exception:  # noqa: BLE001 - un pack roto no para el barrido
                hechos += 1
                continue

            hechos += 1
            if resultado.encontrado:
                emitir("encontrado", resultado)

    emitir("terminado", hechos, error)
