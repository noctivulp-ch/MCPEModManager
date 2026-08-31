# 0016 — El contenido de la tienda se detecta y no se toca

**Fecha:** 2026-08-31
**Estado:** Aceptada

## Contexto

Minecraft Bedrock tiene una tienda propia (Marketplace) desde la que se compran
mundos, texturas y addons. Ese contenido lo descarga, actualiza y borra el juego
por su cuenta.

Para el gestor eso importa por dos motivos. Buscarle versiones nuevas en un
catálogo público como MCPEDL es trabajo tirado —no está ahí— y ofrecer
desinstalarlo es ofrecer pelearse con el juego, que volverá a bajarlo.

## Cómo se distingue

El contenido comprado viene cifrado y firmado. Cada pack trae dos archivos que
no tiene ninguno descargado por fuera:

| Archivo | Qué es |
|---|---|
| `contents.json` | Índice cifrado. Bytes 4–8 = `fc b9 cf 9b`, y a continuación el uuid del pack |
| `signatures.json` | Firma del contenido |

Comprobado en el equipo de prueba: **los 4 packs de `premium_cache` los traen los
dos; los 43 de `com.mojang` no traen ninguno.** Cero falsos positivos en ambos
sentidos.

Se comprueba la cabecera binaria y no solo que el archivo exista, para que un
`contents.json` cualquiera de un pack normal no lo marque por error.

Además hay una separación por ubicación: la tienda guarda su contenido en
`premium_cache/`, en la raíz del launcher y **fuera de `com.mojang`**. Pero no se
usa como criterio, porque un pack premium puede acabar copiado dentro de un
mundo, y ahí el marcador sigue valiendo.

## Decisión

`Instalado.de_la_tienda` sale de esos marcadores, y `Instalado.gestionable` es su
negación. El contenido de la tienda:

- Se **muestra** en la lista, con el badge `Tienda` — está instalado y ocupa
  sitio; no verlo es peor que verlo.
- **No** ofrece desinstalar ni extraer: en su lugar dice «lo gestiona el juego».
- **Queda fuera** de la búsqueda de actualizaciones.

`premium_cache/` no se escanea: es caché del juego, no una instalación del
usuario, y listarlo confundiría lo que el gestor puede tocar con lo que no.

## Consecuencias

Si Mojang cambia el formato de empaquetado, la detección deja de reconocerlo y
esos packs pasarían a tratarse como normales — se les buscarían actualizaciones
sin encontrar nada, que es un desperdicio pero no un daño. El botón de
desinstalar sí volvería a aparecer; si el formato cambia, hay que revisar esto.
