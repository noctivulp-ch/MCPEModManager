# 0019 — Trabajadores persistentes para lo que toca la red

**Fecha:** 2026-08-31
**Estado:** Aceptada

## Contexto

Comprobar actualizaciones y buscar en un catálogo son peticiones de red. En el
hilo de la interfaz dejan la ventana quieta — cuatro minutos en el caso del
barrido completo, que es inaceptable.

El primer intento fue lo obvio: un trabajador por encargo, movido a un `QThread`
que se limpia solo al terminar, con las señales conectadas por el helper
`senales.conectar`. Se caía con un volcado, sin excepción ni rastro.

## Lo que estaba pasando

Dos cosas a la vez, y cada una tapaba a la otra.

**1. Una lambda no vuelve al hilo de la interfaz.** Qt decide dónde ejecutar un
slot mirando de qué hilo es el `QObject` que lo recibe. Una función suelta no
tiene ninguno, así que la ejecuta en el hilo del emisor — el del trabajador. Y
`senales.conectar` envuelve todo en lambda, porque es lo que necesita el
workaround de Nuitka ([ADR 0008](0008-workaround-nuitka-pyside-connect.md)).
Resultado: los slots tocaban widgets desde fuera del hilo de la UI.

Medido, con un receptor real en cada caso:

| Cómo se conecta | Dónde corre el slot |
|---|---|
| `senal.connect(lambda: ...)` | hilo del trabajador |
| `senal.connect(lambda, QueuedConnection)` | no llega nunca |
| `senal.connect(objeto.metodo)` | hilo de la interfaz |

**2. Guardar el trabajador para cancelarlo.** El panel se quedaba con una
referencia a un objeto que Qt ya había borrado con `deleteLater`, y tocarlo era
el otro camino al mismo volcado.

## Decisión

Un trabajador **persistente** por panel, en su propio hilo, al que se le piden
encargos por señal:

```python
self._trabajo = HiloDeTrabajo(Explorador())
self._trabajo.trabajador.listo.connect(self._al_recibir)   # una sola vez
...
self._trabajo.trabajador.pedir.emit(fuente, texto, pagina, tanda)
```

Esto resuelve las dos cosas de una vez:

- El slot es un método del panel, que vive en el hilo de la interfaz, así que Qt
  lo despacha allí. Se usa `connect` directo y **no** `senales.conectar`.
- Se conecta **una sola vez**, que es lo que el fallo de Nuitka tolera. Con un
  trabajador por encargo habría una conexión por consulta, que es justo lo que
  lo dispara.
- No hay referencias a objetos borrados: el trabajador vive tanto como el panel.

Las respuestas que ya no interesan se descartan por número de tanda, no
cancelando el trabajador. Al escribir rápido se solapan consultas y llegan
desordenadas.

`HiloDeTrabajo.parar()` se llama al cerrar la ventana: salir con un `QThread`
corriendo termina en un volcado.

## Consecuencias

`tests/test_trabajo.py` comprueba la afinidad de hilo, incluido un test que
**documenta el límite de `conectar`**: si algún día deja de fallar, es que Qt
cambió de comportamiento y este aparato se puede simplificar.

El primer diagnóstico costó porque medirlo lo alteraba: envolver el slot para ver
en qué hilo corría lo convertía en una función suelta, que es justo el caso malo.
Hubo que instrumentar el código real, no una envoltura.
