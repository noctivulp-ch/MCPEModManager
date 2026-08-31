# 0010 — Qué es un archivo se decide por su contenido

**Fecha:** 2026-08-30
**Estado:** Aceptada

## Contexto

La primera versión decidía por la extensión: `.so`, `.mcpack`, `.mcaddon`, `.zip`.
Eso falla por los dos lados. Un resource pack distribuido como `.zip` no se
reconoce, y un `.mcpack` que en realidad es cualquier otra cosa se acepta y
revienta al instalar.

Tampoco basta con "tiene un `manifest.json` en la raíz". Un modpack de CurseForge
para Java también lo tiene:

```json
{ "manifestType": "minecraftModpack", "manifestVersion": 1,
  "name": "DeceasedCraft - Urban Zombie Apocalypse", "version": "5.10.16",
  "minecraft": { "version": "1.20.1", "modLoaders": [...] }, "files": [...] }
```

En la carpeta de descargas del equipo de prueba había dos de estos entre 129
archivos. Con el criterio del manifiesto a secas, el gestor los ofrecía.

## Decisión

`mcpemod.core.contenido.analizar()` abre el archivo y decide por lo que hay
dentro. La extensión no se mira en ningún momento.

| Se reconoce por | Es |
|---|---|
| `manifest.json` con `header.uuid` **y** `modules[].type` conocido | Pack de Bedrock; el tipo del módulo decide la carpeta |
| `level.dat` en la raíz | Mundo |
| `.mcpack` / `.mcworld` internos, o varios manifiestos en subcarpetas | Addon: una pieza por cada uno |
| Nada de lo anterior | No instalable |

El tipo del módulo (`resources`, `data`, `script`, `skin_pack`, `world_template`)
es lo único que el pack declara sobre su destino, y no es una ruta: el juego lo
mapea a una de sus carpetas. Se comprueba en cualquier addon instalado —
`ActualGuns` está en `resource_packs` con `type: resources` y en
`behavior_packs` con `type: data, script`, mismo nombre y uuid distintos.

## Alternativas descartadas

- **Extensión con contenido como respaldo**: mantiene el problema, solo lo hace
  menos frecuente y más difícil de razonar.
- **Fiarse del nombre del archivo para la versión**: el nombre lo pone quien
  renombra la descarga; `header.version` lo pone quien empaquetó el pack.

## Consecuencias

Reconocer una descarga cuesta abrir el zip y leer su manifiesto. Se hace sobre la
carpeta entera, así que hay un tope de miembros por encima del cual el archivo se
descarta sin inspeccionar a fondo: a partir de ahí no es contenido de Bedrock.

Un archivo a medio descargar no se puede abrir como zip, así que el mismo camino
lo descarta sin necesidad de un caso especial.
