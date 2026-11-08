# Tema: modo y metal

La app usa el sistema de diseño Wulfenite (`wulf_qt`): una laca clara u oscura
y un metal de acento (oro, jade o peltre). Por defecto arranca en **oscuro con
oro**.

Otra combinación se elige con una variable de entorno, `modo-metal`:

```bash
MCPEMOD_TEMA=claro-peltre mcpemod
MCPEMOD_TEMA=oscuro-jade mcpemod
```

Un valor que no se entiende se ignora y queda el de por defecto.

## Por qué al arrancar y no en caliente

`mcpemod/ui/estilo.py` lee la variable **una sola vez, al importarse**, y deriva
de ella los colores que usan los paneles. Esos colores se copian en los widgets
al construirlos: `Tallado` exige el color real del fondo para calcular su relieve
(ver `CLAUDE.md` del proyecto, «Biblioteca UI»). Cambiar de tema con la ventana
abierta dejaría cada widget con el color del tema anterior, así que el cambio en
caliente necesitaría reconstruir la ventana entera. No se ha hecho: por ahora no
hay selector en Ajustes.

## Quién lo usa

- `main.py` aplica a la `QApplication` el mismo modo y metal que `estilo.py`.
- `tools/capturas/capturas.py` saca cada variante del README en un proceso
  aparte, con su `MCPEMOD_TEMA`.
