# 0012 — El gestor trabaja sobre una instalación elegible

**Fecha:** 2026-08-30
**Estado:** Aceptada

## Contexto

En el equipo de prueba hay cinco instalaciones de mcpelauncher: la nativa y
cuatro flatpak, cada una con su propia carpeta `games/com.mojang`. Dos tienen
contenido de verdad (63 y 15 elementos) y tres solo un mundo.

Una ruta fija en el código habría trabajado a ciegas sobre una que quizá no es la
que se juega — y el fallo sería silencioso: la lista sale vacía, que se lee igual
que "no tienes nada instalado".

El esqueleto de carpetas dentro de `com.mojang` es idéntico en las cinco,
incluidas las que nunca instalaron nada. Lo crea el juego al arrancar, no el
launcher, así que la forma de leer una instalación sirve para todas.

## Decisión

`detectar_instalaciones()` recorre las rutas conocidas de cada launcher y
devuelve las que tienen `games/com.mojang`, ordenadas por cantidad de contenido.
La ventana las lista en un selector y arranca con la primera; cambiar de
instalación recarga los paneles y reapunta el observador de directorios.

La carpeta de descargas se resuelve igual de dinámica, con `xdg-user-dir`: en un
escritorio en español es `~/Descargas`, y `~/Downloads` puede existir a la vez y
estar vacía — que es exactamente lo que pasaba en el equipo de prueba.

## Alternativas descartadas

- **Fijar la instalación nativa**: es la que se usa hoy, pero deja de valer en
  cuanto se cambie de launcher, y no avisa de que ha dejado de valer.
- **Autodetectar sin selector**: si acierta mal no hay forma de corregirlo desde
  la app, y el usuario no tiene manera de saber sobre qué está trabajando.

## Consecuencias

La instalación activa es estado que atraviesa `Scanner` e `Installer`, y ambos
tienen que poder cambiarla en caliente. A cambio, la ventana muestra siempre
sobre qué carpeta se está trabajando.

La lista de launchers conocidos está escrita en `rutas.py` y hay que ampliarla si
aparece uno nuevo. Se detecta por la existencia de `games/com.mojang`, así que
añadir uno es una línea.
