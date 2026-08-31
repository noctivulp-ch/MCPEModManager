# 0006 — Nombre canónico para rastrear actualizaciones

**Fecha:** 2026-08-30
**Estado:** Aceptada

## Contexto

Los mods de MCPE se distribuyen con la versión dentro del nombre del archivo:
`MyMod-v1.2.3.so`, `MyMod-v1.3.0.so`. La primera implementación buscaba el mod
instalado por el nombre del archivo exacto (`ruta.stem`), así que dos versiones
del mismo mod eran, para el gestor, dos mods distintos.

Consecuencia: instalar una versión nueva se registraba como "instalar" en vez de
"actualizar", y —lo grave— dejaba el `.so` viejo en `mods/`. El launcher carga
todo lo que hay en esa carpeta, así que el mod quedaba cargado dos veces.

## Decisión

Cada mod tiene un **nombre canónico**: su nombre sin la versión, obtenido
quitando del stem lo que capture el patrón de versión y limpiando los
separadores que queden colgando. `Mod.canonico` se persiste y se indexa, y
`Store.buscar_por_canonico()` es lo que decide si una instalación es nueva o una
actualización. Al actualizar, las rutas del mod anterior se borran antes de
poner las nuevas.

## Alternativas descartadas

- **Hash del contenido**: identifica un archivo, no un mod. Dos versiones del
  mismo mod tienen hashes distintos por definición.
- **Preguntar al usuario qué actualiza a qué**: convierte cada instalación en un
  diálogo, y el 95% de los casos son obvios por el nombre.
- **Leer un identificador del `manifest.json`**: existe para packs (`header.uuid`)
  pero no para los `.so`, que son el caso principal.

## Consecuencias

Dos mods realmente distintos cuyos nombres colapsen al mismo canónico se
tratarían como versiones del mismo — instalar uno desinstalaría el otro. Es poco
probable con nombres reales, pero es el modo de fallo a vigilar si aparece un
reporte raro. El `uuid` del manifest sería el desempate natural para packs si
llega a hacer falta.
