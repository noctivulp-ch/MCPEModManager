# 0019 — El trabajo de fondo no cruza de hilo con Qt

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

## El callejón sin salida

El primer arreglo fue un trabajador persistente por panel, con las señales
conectadas por `connect` directo a métodos del panel: eso da la afinidad de hilo
correcta. Y con una sola conexión por trabajador parecía esquivar el fallo de
Nuitka.

No lo esquivaba. Ese fallo **no tolera ninguna** conexión de método de objeto —
salta a la segunda del proceso, aunque sean métodos distintos ([ADR 0008](0008-workaround-nuitka-pyside-connect.md)).
El binario compilado moría al abrir la pestaña de actualizaciones, que conectaba
tres slots seguidos.

Los dos requisitos se contradicen:

- Para volver al hilo de la interfaz hace falta un método de objeto.
- Para que el binario arranque no puede haber ninguno.

## Decisión

No cruzar de hilo con Qt. El trabajo corre en un **hilo normal de Python** y deja
lo que produce en una `queue.Queue`, que un `QTimer` del hilo de la interfaz
vacía cada 80 ms:

```python
self._tarea = Tarea(self)
self._tarea.lanzar(
    lambda emitir, cancelado: comprobar_todos(buscador, piezas, emitir, cancelado),
    self._al_mensaje,
)
```

La única conexión que queda es la del temporizador, que vive entera dentro del
hilo de la interfaz y va por `senales.conectar` como todas las demás.

Ventajas que no se buscaban pero salieron gratis:

- El trabajo es una **función normal**, no un `QObject` con señales: se prueba sin
  Qt de por medio.
- Un fallo del trabajo llega como un mensaje más (`error_interno`) en vez de morir
  en silencio dentro de un hilo.
- `Tarea.parar()` cancela y espera, que es lo que hay que hacer al cerrar la
  ventana.

Se hace **un trabajo por vez**: es lo que los paneles necesitan y ahorra tener
que ordenar respuestas que llegan desordenadas.

## Consecuencias

`tests/test_trabajo.py` comprueba la afinidad de hilo, incluido un test que
**documenta el límite de `conectar`**: si algún día deja de fallar, es que Qt
cambió de comportamiento y este aparato se puede simplificar.

El primer diagnóstico costó porque medirlo lo alteraba: envolver el slot para ver
en qué hilo corría lo convertía en una función suelta, que es justo el caso malo.
Hubo que instrumentar el código real, no una envoltura.
