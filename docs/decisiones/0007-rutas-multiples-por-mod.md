# 0007 — Un mod tiene varias rutas instaladas

**Fecha:** 2026-08-30
**Estado:** Aceptada

## Contexto

El modelo original guardaba una sola `ruta` por mod. Eso funciona para un `.so`,
pero no para un `.mcaddon`: es un contenedor de varios `.mcpack` que se reparten
entre `resource_packs/` y `behavior_packs/`.

La implementación inicial rellenaba esa `ruta` única con la ruta **del archivo de
origen en `~/Downloads`**. Desinstalar hacía `unlink()` sobre ella: borraba el
`.mcaddon` descargado del usuario y dejaba los packs instalados intactos —
exactamente lo contrario de lo que pedía la acción.

## Decisión

`Mod.rutas: list[Path]` — todo lo que la instalación dejó en disco, y solo eso.
Se persiste como JSON en la columna `rutas`. Desinstalar recorre la lista y borra
cada entrada (`rmtree` si es carpeta, `unlink` si es archivo). El archivo de
origen nunca entra en la lista.

## Alternativas descartadas

- **Una fila por ruta en la base**: normaliza bien, pero obliga a un JOIN y a
  reconstruir el mod desde varias filas para una lista que nunca pasa de dos o
  tres elementos.
- **Registrar el `.mcaddon` como un mod y sus packs como mods hijos**: modela una
  jerarquía que el usuario no ve ni maneja — instala y desinstala el addon
  entero.

## Consecuencias

La columna `rutas` es JSON: no se puede consultar con SQL. No hace falta —
ninguna consulta filtra por ruta. La migración desde el esquema anterior
convierte la `ruta` única en una lista de un elemento (ver `store._migrar`).
