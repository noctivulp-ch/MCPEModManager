# Activación de packs: cómo decide el juego qué se aplica

Instalar un pack y **activarlo** son cosas distintas. Instalar lo deja en la
carpeta del juego; activarlo es lo que hace que se aplique, y eso se decide en
unos archivos JSON aparte.

Este documento describe el mecanismo. El gestor **hoy no escribe en ninguno de
estos archivos** — ver [ADR 0016](../decisiones/0016-contenido-de-la-tienda.md)
para lo que sí toca y lo que no.

## Cómo se activa un pack

Un pack se activa **listándolo** en el archivo que corresponda. Copiarlo a la
carpeta no activa nada.

El formato es siempre un array de objetos, y `pack_id` y `version` tienen que
coincidir **exactamente** con el `header` del manifiesto: un desajuste hace que
el pack no cargue, sin más explicación.

```json
[
  { "pack_id": "46da45b0-a168-4813-9a24-5f41bd7eb45a",
    "subpack": "particles_on_custom_sound",
    "version": [3, 9, 0] }
]
```

`subpack` es opcional: nombra la variante elegida, de las que el pack declara en
`subpacks` de su manifiesto.

**El orden del array importa.** Los packs se aplican en ese orden, así que el
último gana cuando dos tocan lo mismo.

## Dónde vive cada cosa

### Global — se aplica a todo el juego

```
minecraftpe/global_resource_packs.json          ← los activos, en orden
minecraftpe/global_resource_pack_settings.json  ← los ajustes de cada uno
```

**No existe un `global_behavior_packs.json`.** Los packs de comportamiento
cambian el contenido del mundo, así que solo se activan por mundo. Es una
asimetría real, no un archivo que falte.

`global_resource_pack_settings.json` guarda las opciones que el pack expone en su
manifiesto (`settings`), indexadas por `pack_id`:

```json
{ "pack_id": "d32875ff-…", "last_used": 28066303,
  "values": { "athan213:hide_armor.leftArm": true } }
```

Es la prueba de que **en ejecución el juego identifica los packs por uuid**, no
por carpeta ni por nombre — ver [ADR 0020](../decisiones/0020-nombre-identifica-uuid-versiona.md).

### Por mundo

```
minecraftWorlds/<mundo>/world_resource_packs.json          ← activos en ese mundo
minecraftWorlds/<mundo>/world_behavior_packs.json
minecraftWorlds/<mundo>/world_resource_pack_history.json   ← los que estuvieron
minecraftWorlds/<mundo>/world_behavior_pack_history.json
minecraftWorlds/<mundo>/resource_packs/                    ← copias propias
minecraftWorlds/<mundo>/behavior_packs/
```

Activar un pack de comportamiento **activa también su pack de recursos asociado**
si lo declara en `dependencies`.

Los `_history.json` guardan lo que alguna vez estuvo activo, con nombre, uuid,
versión y `can_be_redownloaded`. Sirven para avisar de que a un mundo le falta
algo que usaba.

## Cada mundo lleva su propia copia

Esto es lo que más consecuencias tiene. **Un mundo no usa el pack instalado
globalmente: usa la copia que guarda dentro de sí.**

De ahí salen dos cosas:

- **Desinstalar un pack global no rompe ningún mundo.** El mundo conserva la suya.
- **Actualizar un pack global no actualiza los mundos.** Siguen con su copia y con
  la versión vieja anotada en su `world_*_packs.json`.

Medido tras actualizar 35 packs en el equipo de prueba: los dos mundos DurDream
quedaron con **15 packs desfasados** cada uno.

```
Silk Touch Spawners        mundo v1.0.20    global v1.0.24
TerraNova                  mundo v0.1.3     global v0.1.39
MrCrayfish Furniture [BP]  mundo v2.2.0     global v2.4.0
…
```

Actualizar un mundo sería: copiar el pack nuevo a su carpeta interna y **subir la
versión en su `world_*_packs.json`**, porque la referencia también apunta a la
vieja.

## El límite de diez caracteres

Los nombres de carpeta de packs dentro de un mundo o plantilla **deben tener diez
caracteres o menos**. No es una convención: está documentado, y el motivo es una
limitación de longitud de rutas en Xbox que impide cargarlos.

> *"Resource pack and behavior pack folder names in world templates must be 10
> characters or shorter, as this is due to an issue on Xbox where long paths may
> cause resource or behavior packs to not load properly."*
> — [Create a World Template from an Exported World](https://learn.microsoft.com/en-us/minecraft/creator/documents/packagingaworldtemplate)

Es la explicación del nombrado que el gestor replica
([ADR 0020](../decisiones/0020-nombre-identifica-uuid-versiona.md)): el recorte se
había deducido observando las carpetas, y resulta que tiene una razón documentada.
Las 25 carpetas de packs de los mundos del equipo de prueba lo cumplen.

## Cómo lo hace el gestor

La pestaña **Activación** lista los ámbitos —el juego entero y cada mundo— y al
entrar en uno muestra **dos columnas**: lo disponible a la izquierda, lo aplicado
a la derecha.

La de disponibles va agrupada por tipo y alfabética dentro de cada grupo. **La de
aplicados va en el orden del juego**, que es lo que decide cuál gana: el de abajo
se aplica después.

Un pack se mueve de tres maneras, y las tres hacen lo mismo:

| | |
|---|---|
| **Arrastrar por el asa** (`≡`) | A la otra columna para activar o quitar; dentro de la de aplicados, para cambiar el orden. El asa es una zona pequeña a propósito: agarrar por cualquier parte de la fila haría imposible desplazar la lista con el ratón |
| **Botones** | `Activar`, `Quitar`, `Subir`, `Bajar` |
| **`Ctrl+C` / `Ctrl+V`** | Copia el pack bajo el puntero y lo pega en la columna y el hueco donde esté el ratón |

Al soltar, el hueco se decide por **el centro de cada fila**: en la mitad de
arriba se coloca antes, en la de abajo después.

### Lo que no se puede activar, y por qué

El gestor lo comprueba **antes de escribir**, porque un `pack_id` o una `version`
que no cuadren hacen que el pack no cargue y el juego no dice por qué.

- Lo que está **sin extraer**: no hay carpeta que copiar ni versión que anotar.
- Lo de la **tienda**: lo gestiona el juego.
- Lo que no declara uuid o versión.
- Packs de **comportamiento en el ámbito global**: no existe esa activación, y la
  columna lo dice en vez de dejar un hueco sin explicar.

### Escritura sin dejar nada a medias

Los archivos de activación se escriben en un temporal al lado y se sustituyen de
golpe. Un archivo truncado aquí deja al mundo sin sus packs.


## Respaldo de mundos

Un mundo es lo único de aquí que no se puede volver a descargar. Un pack se baja
otra vez; una partida de meses, no. Por eso **ningún cambio en un mundo se hace
sin respaldarlo antes**, y si el respaldo falla el cambio no se hace.

### Dónde

```
com.mojang/mcpemod_respaldos/<carpeta-del-mundo>.tar.zst
```

Dentro de `com.mojang`, para que acompañen a la instalación si se mueve o se
copia. **Fuera de `minecraftWorlds`**, porque ahí dentro se verían como mundos
más —tanto para este gestor como para el juego— y aparecerían duplicados. El
nombre no coincide con ninguna carpeta del juego, así que este no la va a pisar.

### Uno por mundo

Se guarda **uno solo por mundo**, no una pila: un mundo real ocupa decenas de
megas comprimido. Guardar otra vez **sustituye** el anterior, y eso es una
pérdida real: quien lo pida tiene que ver antes de qué fecha era el que se va a
perder (`existente()` lo devuelve).

### Que sirva para restaurar

Un `tar` que no da error no basta. Al guardar y al restaurar se comprueba que el
archivo se puede leer y que **trae un `level.dat` dentro**; si no, se rechaza.

Las dos operaciones están hechas para que un fallo a mitad no se lleve nada:

- **Guardar** escribe en un temporal y solo entonces sustituye el anterior, con
  un `replace` atómico. Si algo falla, sigue estando el que había.
- **Restaurar** extrae al lado, comprueba, y solo entonces intercambia. Si la
  extracción falla o lo extraído no es un mundo, el mundo que hay no se toca.

Medido sobre un mundo real de 15 782 archivos: 69 MB comprimidos, y la
restauración devuelve el árbol **idéntico** —misma huella de todos los archivos—.
