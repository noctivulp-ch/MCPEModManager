# 0009 — La identidad de un pack es el uuid de su manifiesto

**Fecha:** 2026-08-30
**Estado:** Corregida por [0020](0020-nombre-identifica-uuid-versiona.md) — el `header.uuid` identifica la **versión**, no el pack: hay autores que lo cambian en cada publicación. La identidad del pack es su `header.name`. — reemplaza a [0006](0006-nombre-canonico-para-actualizar.md)

## Contexto

Hacía falta saber cuándo dos archivos son el mismo contenido, para que instalar
una versión nueva sea una actualización y no un duplicado.

La ADR 0006 lo resolvía con un "nombre canónico": el nombre del archivo sin su
versión. Funciona con `.so` de launcher, pero no con contenido de Bedrock — y es
contenido de Bedrock lo que gestiona esta app. El nombre del archivo lo pone
quien lo descarga y no tiene relación con lo que hay dentro.

Al inspeccionar una instalación real apareció el dato que zanja la cuestión.
El juego guarda los ajustes de cada pack en
`minecraftpe/global_resource_pack_settings.json`, y lo hace así:

```json
{ "pack_id": "d32875ff-438d-4436-9c8c-e6dc3c6d6348", "last_used": 28066303, ... }
```

Referencia el `header.uuid` del manifiesto. **Nunca una ruta ni un nombre.** Ese
es el identificador que usa el propio juego.

## Decisión

La identidad de una pieza de contenido es su `header.uuid`. De ahí sale todo:

- **Actualizar** — antes de instalar se busca ese uuid entre lo que hay en disco.
  Si aparece, se reemplaza esa carpeta conservando su nombre, aunque la haya
  creado el juego y se llame de otra forma.
- **Estado en la lista de descargas** — el badge (↑ actualización, ✓ instalado)
  compara el `header.version` del archivo contra el del uuid instalado.
- **Duplicados** — dos carpetas con el mismo uuid son el mismo pack dos veces, y
  la auditoría las señala.

Los mundos no tienen manifiesto y por tanto no tienen uuid; se identifican por su
carpeta, que es como los distingue el juego.

## Consecuencias

Saber qué hay instalado obliga a leer todos los manifiestos de las carpetas del
juego. Son unas decenas de archivos JSON pequeños y el coste no se nota.

El nombre de la carpeta deja de importar: se elige legible (ver
[0011](0011-nombre-de-carpeta-legible.md)) en vez de replicar el recorte a diez
caracteres con el que quedan las carpetas que crea el juego al importar.
