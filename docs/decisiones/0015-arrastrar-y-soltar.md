# 0015 — Arrastrar decide por lo que es cada cosa

**Fecha:** 2026-08-30
**Estado:** Aceptada

## Contexto

Instalar exigía que el archivo estuviera en una carpeta vigilada. Para un pack
que acaba de llegar a otro sitio —el escritorio, un pendrive, la carpeta de un
proyecto— eso obliga a moverlo primero o a añadir su carpeta entera.

Arrastrarlo a la ventana es el gesto que la gente intenta primero.

## Decisión

La ventana acepta arrastres y decide por lo que es cada cosa, sin preguntar:

| Lo que se suelta | Qué pasa |
|---|---|
| Archivo que es contenido de Bedrock | Se instala |
| Carpeta | Se añade a las vigiladas |
| Cualquier otra cosa | Se dice que no lo es, y nada más |

Una carpeta soltada **no** se intenta instalar aunque tenga un `manifest.json`
dentro. Es ambigua —puede ser un pack extraído o el sitio donde se guardan las
descargas— y vigilarla no destruye nada mientras que instalarla por error sí.
Si de verdad era un pack, aparece en la lista al instante y se instala con un
clic.

Instalar sin confirmar es aceptable: es reversible con el botón que hay al lado,
y soltar un pack sobre un gestor de packs no admite otra lectura. Lo que sí hace
falta es decir después qué pasó con cada archivo, y de eso se encarga
`soltar.Resultado`, que resume instalados, carpetas nuevas, errores e ignorados
en un solo aviso.

Mientras se arrastra, un velo cubre la ventana con el texto de lo que va a pasar.
Un gesto que no da señal de estar funcionando se abandona a mitad.

## Consecuencias

La lógica vive en `ui/soltar.py`, separada de los eventos de Qt: lo que puede
equivocarse es la decisión, no que Qt entregue el evento. Se prueba sin ventana.

Soltar varios elementos a la vez funciona y se procesan de uno en uno; el aviso
final los resume en vez de encadenar mensajes.

---

## Revisión (2026-09-01): el gesto se lleva a mano, sin `QDrag`

`QDrag.exec()` abre un bucle de eventos **modal** de la plataforma. Mientras
dura no llega nada que no sea del propio arrastre, y eso costaba cuatro cosas:

- Sosteniendo un pack no se podía girar la rueda para desplazar la lista, que es
  justo cuando hace falta: el sitio donde quieres soltarlo casi nunca está en
  pantalla.
- La fila seguía en su sitio mientras una copia colgaba del puntero, así que el
  mismo pack se veía dos veces.
- Lo único que la API deja pintar es una miniatura pegada al cursor. No hay forma
  de enseñar dónde va a caer.
- Tampoco de desplazar la lista solo al acercarse al borde.

Ahora lo lleva `ui/widgets/arrastre.py` con los eventos de ratón de siempre,
apoyado en el **agarre implícito** de Qt: quien recibe el `press` recibe todo el
movimiento hasta el `release`, esté el puntero donde esté. Por eso el asa puede
conducir un gesto que acaba en la otra columna.

Con eso: la fila se esconde al levantarla, lo que se sostiene es una **cápsula**
—nombre y versión, sin botones, porque en el agarre no se pulsa nada—, un
**hueco** con la altura real enseña dónde va a caer, y cerca del borde la lista
avanza sola, con un paso proporcional a lo metido que esté el puntero en la
banda. `Escape` cancela y devuelve el pack a su sitio.

No se pierde nada: `QDrag` sirve para llevar algo a **otra aplicación**, y este
gesto nunca sale de la ventana.

El cambio destapó un fallo de conteo que antes no podía darse: `_posicion_en`
contaba también las filas ocultas, y como ahora la que se arrastra lo está, todo
lo que cayera por debajo del pack movido se colocaba un sitio más allá del hueco
que se había enseñado. Con el orden decidiendo qué textura se ve, eso no se nota
hasta entrar al juego. Hay una prueba que lo fija.

