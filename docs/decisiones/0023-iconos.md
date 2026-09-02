# 0023 — Los iconos dicen la acción, y las flechas dicen el movimiento

Estado: Aceptada
Fecha: 2026-09-01

## Contexto

La UI señalizaba con glifos de texto: `≡` para el asa de arrastre, `↑ ↓` para
reordenar, `✕` para quitar, `↗` para abrir una ruta, `⟳` en el historial. Eso ya
había fallado una vez: los botones de reordenar tuvieron que pasar a decir
«Subir» y «Bajar» con palabras porque `▲▼` salían como cajas vacías —el glifo no
estaba en la fuente del botón—. Un símbolo que depende de qué fuente resuelva el
sistema no es una decisión de diseño, es una apuesta.

`wulf_qt` incorporó un juego de ochenta iconos de trazo con su pieza `icono()`,
que resuelve tamaño y teñido. Eso quita la apuesta: el dibujo viaja con la
librería.

## Decisión

**Un módulo decide qué icono lleva cada acción de esta app.**
`mcpemod/ui/iconos.py`. Los paneles piden `iconos.DESINSTALAR`, no `"eliminar"`.
El juego es genérico a propósito; qué significa cada dibujo *aquí* es una
decisión de esta app y vive en un solo sitio. Repartir los nombres por los
paneles termina con dos botones que hacen lo mismo y llevan dibujos distintos.

**Flecha, chevron y triángulo no son intercambiables.** El juego trae los tres
porque dicen tres cosas:

| | qué dice | dónde |
|---|---|---|
| **Flecha** | algo se desplaza de verdad | Activar, Quitar, Subir, Bajar |
| **Chevron** | V abierta, continuidad: «sigue por aquí» | Volver, Gestionar, Anterior, Siguiente |
| **Triángulo** | forma cerrada que señala: «esto es lo elegido» | en ningún sitio, todavía |

Activar y Quitar llevaban chevron y estaba mal: mueven un pack de una columna a
la otra, y eso es desplazamiento, no navegación. El triángulo es el cursor de un
menú que se recorre —lleno el cursor, hueco el destino disponible—; esta app no
tiene ninguno, así que no lo usa. Queda anotado para que quien venga detrás sepa
que existe y por qué no aparece.

**Un dibujo que apunta hacia delante va detrás del texto.** «Activar →», no
«→ Activar». Qt no tiene «icono a la derecha»: se invierte la dirección de la
pieza, y eso lo hace `iconos.poner(..., detras=True)`.

**El tinte lo decide el botón, no quien llama.** El primario va relleno de metal
y su texto es oscuro; un icono con el color del pozo —claro— se desvanecía
encima. `poner()` lee la marca que deja `boton_primario` y tiñe con
`SOBRE_METAL`. Se vio en la captura, no en el código.

**Con texto, el icono acompaña; no lo sustituye.** Esta app tiene acciones que se
parecen —activar, quitar, extraer, desinstalar— y ahí adivinar sale caro. Las
excepciones son las que caben en una fila que ya lleva tres botones y cuyo dibujo
*es* la explicación: Subir, Bajar, cerrar una carpeta vigilada. Todas con
tooltip.

**Los badges de estado no llevan icono.** «↑ actualización», «✓ al día» viven en
una etiqueta de 10 px y el juego solo tiene tres tamaños, el menor de 20. Meter
uno obliga a salirse de la escala, que es justo lo que la escala existe para
impedir. Ahí manda la palabra.

**Dos botones vecinos no comparten dibujo.** «Comprobar», «Volver a comprobar» y
«Actualizar todo» conviven en la misma barra: con el mismo icono circular se leen
como el mismo botón tres veces. Llevan `nube` (salir a preguntar), `sincronizar`
(rehacer el emparejamiento) y `actualizar` (aplicar).

## Consecuencias

El asa de arrastre es ahora el icono `menu` —tres barras horizontales, que es
literalmente lo que se pidió— dentro de una zona de 28 px: el icono mide 20 y lo
que se agarra no es el trazo sino la zona. **Ningún tamaño del juego es el
objetivo táctil**; un icono de 24 en un botón sigue necesitando sus 48 alrededor,
y de eso se encargan las piezas de `wulf_qt`.

El historial gana lo que más se nota: cuatro dibujos con su color en lugar de
`↓ ↑ ✕ ⟳`. Se distingue qué pasó sin leer la línea.

Los SVG **no se leen del disco**: `wulf_qt` los incrusta como texto en
`_iconos_datos.py`. Es lo que hace que funcionen en el binario de Nuitka, donde
cualquier ruta calculada desde `__file__` apunta fuera del bundle. Nada que
añadir a `build.sh`.

## Alternativas descartadas

**Seguir con glifos de texto.** Es lo que ya había, y el precedente de `▲▼` dice
lo que pasa: se descubre al mirar una captura, no al compilar.

**Icono solo, sin texto, en todos los botones.** Ahorra anchura y cuesta
precisión justo donde no sobra: desinstalar y quitar de la lista activa son
cosas distintas y ninguna se deshace sola.
