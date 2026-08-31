# 0013 — Varias carpetas vigiladas, y ninguna es intocable

**Fecha:** 2026-08-30
**Estado:** Aceptada

## Contexto

El gestor miraba una sola carpeta, la de descargas del sistema. Es un
predeterminado razonable pero no una regla: el contenido descargado acaba
repartido —una carpeta de packs aparte, un disco externo, la carpeta de un
proyecto— y obligar a moverlo todo a `~/Descargas` para poder instalarlo es
trabajo que la app debería ahorrar, no crear.

## Decisión

Las carpetas vigiladas son una lista editable, persistida en la tabla `carpetas`
de la base:

- En la primera ejecución se siembra con `xdg-user-dir DOWNLOAD`.
- Se pueden añadir otras desde la pestaña de Descargas.
- Se puede quitar **cualquiera**, incluida la inicial: no tiene estatus especial.
- **Siempre queda al menos una.** `Store.quitar_carpeta()` devuelve `False` si se
  intenta quitar la última, y la barra ni siquiera dibuja el botón en ese caso —
  un botón que solo puede fallar es peor que no tenerlo.

`Scanner` observa todas con el mismo `QFileSystemWatcher` y las recorre en orden
de alta. Una carpeta que desaparece del disco se salta sin romper la lectura; se
mantiene en la lista y se muestra marcada, porque puede ser un disco externo
desconectado y borrarla sola sería perder la configuración del usuario.

## Consecuencias

Reconocer una descarga cuesta abrir su zip, y con varias carpetas eso se repite
en cada refresco. `Scanner` cachea el análisis por `(ruta, tamaño, mtime)`, así
que un archivo solo se vuelve a leer si cambió.

Vigilar una carpeta y una subcarpeta suya es legítimo y no duplica nada: la
lectura descarta por ruta resuelta.

La procedencia de cada archivo solo se muestra cuando hay más de una carpeta; con
una sola es obvia y solo estorba.
