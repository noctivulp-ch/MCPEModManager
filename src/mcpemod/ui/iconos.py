"""Qué icono lleva cada acción de esta app.

Los iconos son de `wulf_qt` y genéricos a propósito; aquí se decide **qué
significa cada uno en este programa**, en un solo sitio. Esparcir los nombres por
los paneles acaba con dos botones que hacen lo mismo y llevan dibujos distintos.

La librería exige rasterizar al tamaño final y teñir al dibujar, y de eso se
encarga `icono()`. Lo que sí hay que respetar aquí:

- El icono **no es el objetivo táctil**: un botón con icono de 24 sigue midiendo
  sus 48. Los botones de `wulf_qt` ya lo hacen.
- **Con texto, el icono acompaña**; no lo sustituye. Un botón solo con dibujo
  obliga a adivinar, y esta app tiene acciones que se parecen entre sí —activar,
  quitar, extraer, desinstalar— donde adivinar sale caro.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QPushButton

from wulf_qt import IconoTamano, icono

from mcpemod.ui.estilo import LACA, SOBRE_METAL_

#: Un nombre por acción, no por dibujo: si mañana «instalar» pasa a verse de otra
#: forma, se cambia aquí y no en seis paneles.
#:
#: **Flecha, chevron y triángulo no son intercambiables.** El juego de iconos trae
#: los tres a propósito y cada uno dice una cosa distinta:
#:
#: - **Flecha** — algo se desplaza de verdad: el pack cambia de columna, sube o
#:   baja en el orden. Hay un objeto que se mueve.
#: - **Chevron** — una V abierta: continuidad. «Sigue por aquí», «vuelve». Se
#:   navega, pero nada cambia de sitio.
#: - **Triángulo** — forma cerrada que señala: «esto es lo elegido». El lleno es
#:   el cursor y el hueco el destino disponible. Esta app no recorre menús con
#:   cursor, así que no usa ninguno de los dos; están aquí para que quien venga
#:   detrás sepa que existen y por qué no aparecen.
#:
#: Poner un chevron donde toca una flecha no rompe nada, y por eso es fácil que
#: pase: la fila entera acaba diciendo «avanza» cuando lo que hace es mover.
INSTALAR = "descargar"
ACTUALIZAR = "actualizar"
#: Los tres botones de la barra de actualizaciones conviven, así que llevan tres
#: dibujos distintos y cada uno dice su parte del proceso: salir a preguntar a los
#: catálogos, rehacer el emparejamiento descartando lo guardado, y aplicar lo que
#: haya salido. Con el mismo dibujo se leen como el mismo botón tres veces.
COMPROBAR = "nube"
REVISAR = "sincronizar"
DESINSTALAR = "eliminar"
#: Extraer deja el pack como una carpeta normal, y eso es lo que dibuja. Las
#: flechas en diagonal se leen como «pantalla completa» en cualquier otra app.
EXTRAER = "carpeta"
#: Mover un pack de una columna a la otra y reordenarlo dentro de la suya: los
#: cuatro son la misma clase de gesto, así que llevan la misma clase de dibujo.
ACTIVAR = "flecha-derecha"
DESACTIVAR = "flecha-izquierda"
SUBIR = "flecha-arriba"
BAJAR = "flecha-abajo"
ASA = "menu"
SITIO = "enlace"
CARPETA = "carpeta"
ANADIR = "anadir"
CERRAR = "cerrar"
GUARDAR = "guardar"
RESTAURAR = "volver"
#: Ir a otra vista. Chevron y no flecha: aquí no se mueve nada, se avanza.
ATRAS = "chevron-izquierda"
ADELANTE = "chevron-derecha"
AJUSTES = "ajustes"
GLOBAL = "casa"
MUNDO = "cuadricula"
COPIAR = "copiar"
BUSCAR = "buscar"
#: El hueco de la portada cuando el pack no trae ninguna.
SIN_PORTADA = "imagen"

#: Las cuatro clases de cambio del historial, donde el dibujo es el único
#: marcador de qué pasó.
#:
#: Los estados de versión —al día, hay una nueva, la tuya es más nueva— **no**
#: llevan icono: viven dentro de un badge de 10 px y el juego solo tiene tres
#: tamaños, el menor de 20. Meter uno ahí obliga a salirse de la escala, que es
#: justo lo que la escala existe para impedir. Ahí manda la palabra.
NORMALIZAR = "sincronizar"
ESPERANDO = "pendiente"


def poner(boton: QPushButton, nombre: str, tamano: int = IconoTamano.CHICO,
          color: str | None = None, *, detras: bool = False) -> QPushButton:
    """Le pone su icono a un botón, teñido con el color del texto que lleva.

    El tinte sale del propio botón y no de quien llama: el primario va relleno de
    metal y su texto es oscuro, así que un icono con el color del pozo —claro—
    se desvanecía encima. Se lee la marca que le pone `boton_primario`.

    Tamaño chico por defecto: en un botón el icono va en línea con su etiqueta,
    que es justo para lo que la librería reserva ese tamaño.

    Con `detras`, el icono va **después** del texto: es lo que quieren los que
    apuntan hacia delante.
    """
    if color is None:
        primario = boton.property("primario") == "true"
        color = SOBRE_METAL_ if primario else LACA.texto_en_pozo
    boton.setIcon(icono(nombre, color, tamano))
    boton.setIconSize(QSize(tamano, tamano))
    if detras:
        # Qt no tiene «icono a la derecha»: se invierte la dirección de la pieza,
        # que es lo que coloca el icono al otro lado del texto. Un dibujo que
        # apunta hacia fuera pegado al borde de dentro se lee al revés de lo que
        # hace —«Activar ›» sí, «› Activar» no—.
        boton.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    return boton
