# 0008 — Envolver los slots al conectar señales (workaround de Nuitka)

**Fecha:** 2026-08-30
**Estado:** Aceptada — provisional, atada a una versión del toolchain

## Contexto

Con Nuitka 4.1.3 + PySide6 6.11.2 + CPython 3.14.6, el binario compilado revienta
en la **segunda** conexión de un método de objeto a una señal:

```
SystemError: method_descriptor() returned a result with an exception set
```

La primera conexión deja una excepción pendiente a nivel C y la siguiente llamada
al descriptor explota. Interpretado no ocurre: solo compilado. Y ocurre en sitios
completamente normales — un panel suscrito a dos señales, o un panel escuchando a
sus N tarjetas.

**Corrección de alcance (2026-08-31).** La primera medición usó el mismo método
doce veces y concluyó que el problema era repetirlo. Es más amplio: salta a la
segunda conexión de **cualquier** método de objeto en el proceso, aunque sean
métodos distintos. Se vio al añadir la pestaña de actualizaciones, que conectaba
tres slots seguidos y moría en el segundo. No hay presupuesto de «una conexión
gratis»: ninguna vale.

Es lo que hacía que la app compilara sin arrancar. `tools/repro_nuitka_pyside_connect.py`
lo reproduce en 40 líneas sin nada del proyecto, y muestra que conectar una lambda
que llame al método funciona sin problema.

## Decisión

Todas las conexiones pasan por `mcpemod.senales.conectar(senal, slot)`, que
envuelve el slot en una función libre. Además, `build.sh` ejecuta el binario ya
compilado con `--autotest`: arranca la ventana, procesa un ciclo de eventos y sale.
Un ejecutable que compila y no arranca deja de ser algo que se descubre al abrirlo.

## Alternativas descartadas

- **Reemplazar el `protect()` del post-load de Nuitka** por una versión sin
  `hasattr` sobre objetos compilados: probado, no arregla nada. El fallo está en
  `SignalInstance.connect` con el bound method compilado, no en `protect` — con
  `protect` convertido en no-op el crash es idéntico.
- **Fijar Python 3.13**: probablemente funciona, pero cambia el intérprete de todo
  el sistema por un bug de una herramienta.
- **Distribuir sin compilar**: pierde el binario único, que es la razón de
  [ADR 0003](0003-nuitka-onefile.md).

## Cómo se vigila

Dos redes, porque la única forma de notarlo es compilando:

- **`tools/lint_conexiones.py`**, que `check.sh` ejecuta sobre `src/`: recorre
  el árbol de sintaxis y avisa de cualquier `connect` cuyo primer argumento sea
  un `objeto.metodo`.
- **`build.sh` ejecuta el binario ya compilado con `--autotest`**, y ese autotest
  no se limita a abrir la ventana: lanza también una tarea de fondo y espera su
  resultado, porque los hilos solo entran en juego al pulsar un botón y ahí es
  donde el fallo se había colado dos veces.

La comprobación de `build.sh` mira **la frase que imprime el binario**, no su
código de salida: el ejecutable de Nuitka sale con 0 aunque muera con un
traceback, y por eso una versión rota llegó a darse por buena.

## Consecuencias

Una indirección en cada conexión, y un helper que existe solo por un bug externo —
por eso lleva escrito el porqué y el repro al lado. Cuando una versión nueva del
toolchain lo arregle (`python tools/repro_nuitka_pyside_connect.py` compilado
pasa), `conectar()` se retira y se vuelve a `senal.connect(slot)`.

Lo que más costó es que este fallo y el de los hilos tiran en direcciones
opuestas: una señal entre hilos **necesita** un método de objeto para volver al
hilo de la interfaz, y aquí no se puede usar ninguno. La salida fue no cruzar de
hilo con Qt (ver [ADR 0019](0019-trabajos-en-segundo-plano.md)).

La envoltura mantiene viva una referencia al receptor mientras exista el emisor.
En esta app el emisor siempre muere antes o a la vez que el receptor, así que no
retiene nada; si eso deja de ser cierto en algún punto, hay que revisarlo.
