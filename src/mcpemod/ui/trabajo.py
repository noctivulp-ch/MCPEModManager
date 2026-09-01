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
    fallos: list[str] = []

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
            except Exception as e:  # noqa: BLE001 - un pack roto no para el barrido
                # Pero tampoco desaparece: tragarse esto en silencio fue lo que
                # hizo que un fallo de esquema se viera como «cero resultados».
                fallos.append(f"{pieza.nombre}: {type(e).__name__}: {e}")
                hechos += 1
                continue

            hechos += 1
            if resultado.encontrado:
                emitir("encontrado", resultado)

    if not error and fallos:
        error = (f"{len(fallos)} fallaron. El primero — {fallos[0]}"
                 if len(fallos) > 1 else fallos[0])

    emitir("terminado", hechos, error)


def instalar_publicado(
    resultados: list,
    installer,
    indice_por_pack: dict,
    emitir: Callable[..., None],
    cancelado: threading.Event,
) -> None:
    """Descarga e instala una lista de actualizaciones confirmadas.

    Cada una se baja a un temporal y se pasa por el mismo camino que un archivo
    de una carpeta vigilada: así el destino lo decide la misma lógica que en una
    instalación normal, y no hay un segundo camino que mantener.

    Mensajes: `("instalando", hechos, total, nombre)`, `("instalado", uuid)`,
    `("fallo", nombre, motivo)` y `("fin_instalacion", instalados, fallidos)`.
    """
    import tempfile
    from pathlib import Path

    from mcpemod.core import ErrorInstalacion, analizar
    from mcpemod.core.red import descargar

    hechos = instalados = 0
    fallidos: list[str] = []
    total = len(resultados)

    for resultado in resultados:
        if cancelado.is_set():
            break
        emitir("instalando", hechos, total, resultado.pieza.nombre)
        hechos += 1

        descarga = resultado.descarga
        if descarga is None:
            fallidos.append(resultado.pieza.nombre)
            emitir("fallo", resultado.pieza.nombre, "no hay archivo que descargar")
            continue

        try:
            with tempfile.TemporaryDirectory() as tmp:
                destino = Path(tmp) / (descarga.nombre or "descarga.mcpack")
                with destino.open("wb") as f:
                    descargar(descarga.url, f)

                analisis = analizar(destino)
                if analisis is None:
                    raise ErrorInstalacion("lo descargado no es contenido instalable")
                # Solo el pack que se estaba actualizando: lo publicado puede ser
                # un addon con más cosas dentro, y no se instala lo que nadie pidió.
                # Las dos señales: el emparejamiento pudo confirmarse por
                # cualquiera, y el autor puede haber cambiado el nombre.
                installer.instalar(
                    analisis, indice_por_pack,
                    solo={resultado.pieza.clave, resultado.pieza.uuid},
                )
        except Exception as e:  # noqa: BLE001 - uno que falle no para los demás
            fallidos.append(resultado.pieza.nombre)
            emitir("fallo", resultado.pieza.nombre, str(e))
            continue

        instalados += 1
        emitir("instalado", resultado.pieza.uuid)

    emitir("fin_instalacion", instalados, fallidos)
