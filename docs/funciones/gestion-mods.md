# Gestión de mods

## Tipos soportados

| Extensión | Destino de instalación | Cómo se decide |
|-----------|------------------------|----------------|
| `.so` | `mods/` (copia directa) | Por extensión |
| `.mcpack` | `resource_packs/` o `behavior_packs/` | `modules[].type` del `manifest.json` |
| `.mcaddon` | Cada `.mcpack` interno va a su directorio | Se extraen los `.mcpack` que contenga |
| `.zip` | Si trae `manifest.json`, como pack; si no, a `mods/` | Contenido del zip |

Los packs se extraen a una carpeta con el nombre del archivo. Si esa carpeta ya
existe se **vacía antes** de extraer: reinstalar sobre ella dejaría archivos de la
versión anterior mezclados con los nuevos.

Los miembros del zip se validan antes de extraer — uno que apunte fuera de su
carpeta de destino (`../`) aborta la instalación.

## Actualizar

Un mod se identifica por su **nombre canónico**: el nombre del archivo sin la
versión. `MyMod-v1.2.3.so` y `MyMod-v1.3.0.so` son el mismo mod.

Al instalar, si ya hay un mod con ese canónico:
1. Se borran sus rutas instaladas (dejar la versión vieja en `mods/` hace que el
   launcher cargue el mod dos veces).
2. Se instala la nueva.
3. La acción se registra como `actualizar`, con la versión anterior.

Instalar una versión más vieja funciona igual — el botón dice "Revertir".
Reinstalar exactamente el mismo archivo no lo borra: la ruta de origen se excluye
de la limpieza.

Ver [ADR 0006](../decisiones/0006-nombre-canonico-para-actualizar.md).

## Desinstalar

Borra **todas** las rutas que la instalación dejó en disco (`rmtree` si es
carpeta) y elimina el registro. El archivo de origen en `~/Downloads` nunca se
toca: no forma parte de la instalación.

Ver [ADR 0007](../decisiones/0007-rutas-multiples-por-mod.md).

## Detección de versión

Por orden de prioridad:

1. `manifest.json` dentro del zip — `header.version`, sea lista (`[1,5,0]` →
   `"1.5.0"`) o string. Gana al nombre porque el nombre lo pone quien renombra el
   archivo y el manifest quien lo empaquetó.
2. Regex sobre el nombre: `v?(\d+\.\d+(?:\.\d+)*(?:[-_.][A-Za-z]\w*)?)`
3. Si no hay nada → `None` → "versión desconocida".

## Comparación de versiones

`comparar(v_instalada, v_descarga) → EstadoVersion`:

| Estado | Significado | Badge |
|--------|-------------|-------|
| `IGUAL` | Misma versión instalada | ✓ instalado |
| `NUEVA` | La descarga es más reciente | ↑ actualización |
| `ANTERIOR` | La descarga es más vieja | ↓ anterior |
| `DESCONOCIDA` | Alguna versión es `None` o no comparable | — |

Usa `packaging.version.Version`. Los pre-releases con guion bajo
(`2.0.0_beta`, que `packaging` rechaza) se normalizan a guion antes de comparar:
el sufijo es información real de orden y tirarla haría que dos betas
consecutivas se leyeran como la misma versión. Si ambas versiones son
incomparables pero idénticas como texto → `IGUAL`.

## Badge NEW

Aparece la primera vez que un archivo entra en la vista de Descargas, y se apaga
cuando el usuario **abre la pestaña Descargas** — no al escanear el directorio.
Marcarlo al escanear quemaría el aviso mientras el usuario está en otra pestaña,
que es justo cuando más falta hace.

La identidad es el SHA-256 del contenido, no el nombre: un archivo renombrado no
vuelve a ser nuevo, y uno con el mismo nombre pero contenido distinto sí lo es.
Ver [ADR 0004](../decisiones/0004-hash-sha256-para-badge-new.md).

## Descargas incompletas

Un archivo que aún se está descargando existe en la carpeta pero no está
completo. La lista de Descargas los omite: un zip que no se puede abrir, o un
`.so` de tamaño cero. Sin este filtro aparecen en la lista y pulsar Instalar da
un error de zip corrupto que no dice nada sobre la causa real.

## Historial

Toda acción se registra con `accion` (`instalar` | `actualizar` | `desinstalar`),
`archivo`, `version`, `version_anterior` (solo en actualizar) y `timestamp`.

El panel los muestra del más reciente al más antiguo. Cuando dos registros caen
en el mismo timestamp, desempata el `id` — sin eso el orden sería el que le
apetezca a SQLite.

## Observación de directorios

`Scanner` vigila con `QFileSystemWatcher`:

- `mods/`, `resource_packs/`, `behavior_packs/` → señal `mods_cambiados`
- `~/Downloads` → señal `descargas_cambiadas`

Qt deja de observar un directorio si desaparece; al recrearse hay que volver a
engancharlo o el panel se queda congelado sin avisar. `Scanner` lo re-observa en
cada evento.

Tras una acción de la propia app, el panel llama a `Scanner.notificar_cambio()`
en vez de esperar al watcher. Ver [ADR 0005](../decisiones/0005-qfilesystemwatcher-para-monitoreo.md).
