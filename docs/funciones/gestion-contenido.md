# Gestión de contenido

## Qué reconoce, y cómo

La extensión no se mira en ningún momento. `contenido.analizar()` abre el archivo
y decide por lo que hay dentro:

| Lo que encuentra | Qué es |
|---|---|
| `manifest.json` con `header.uuid` **y** `modules[].type` conocido | Pack de Bedrock |
| `level.dat` en la raíz | Mundo |
| `.mcpack` / `.mcworld` internos, o varios manifiestos en subcarpetas | Addon: una pieza por cada uno |
| Cualquier otra cosa | No instalable |

Lo que esto descarta correctamente y un filtro por extensión no: los modpacks de
CurseForge para Java, que traen `manifest.json` en la raíz igual que un pack, y
las descargas a medias, que no se pueden abrir como zip.

Lo que esto acepta y un filtro por extensión no: un resource pack distribuido
como `.zip`, o un mundo con cualquier nombre.

## Dónde acaba cada cosa

El tipo del módulo es lo único que el pack declara sobre su destino, y no es una
ruta: el juego lo mapea a una de sus carpetas.

| `modules[].type` | Carpeta |
|---|---|
| `resources` | `resource_packs/` |
| `data`, `script`, `client_data` | `behavior_packs/` |
| `skin_pack` | `skin_packs/` |
| `world_template` | `world_templates/` |
| *(sin manifiesto, con `level.dat`)* | `minecraftWorlds/` |

Un addon se reparte: cada pack interno va a la carpeta que le toca por su tipo, y
cada uno cuenta como una pieza independiente con su propio uuid.

El contenido se extrae **a la raíz** de la carpeta de destino. Si el archivo trae
una carpeta contenedora dentro, se aplana: el juego busca `manifest.json` en la
raíz de la carpeta del pack y no lo carga si está un nivel más abajo.

## Identidad y actualizaciones

La identidad es el `header.uuid` del manifiesto — lo mismo que usa el juego. Al
instalar:

1. Se busca ese uuid entre lo que ya hay en disco.
2. Si aparece, se reemplaza **esa carpeta**, con el nombre que tuviera. Un pack
   que importó el juego como `HideArmorV` se actualiza dentro de `HideArmorV`.
3. Se registra como `actualizar`, con la versión anterior.

Instalar una versión más vieja funciona igual y el botón dice "Revertir";
reinstalar la misma, "Reinstalar".

El nombre de la carpeta para un pack nuevo es el nombre real del pack, limpio de
códigos de color `§x` y de caracteres que el sistema de archivos no admite:
`Hide Armor | V1.2` → `Hide Armor V1.2`. Ver
[ADR 0011](../decisiones/0011-nombre-de-carpeta-legible.md).

## Reparar

Dos formas de que algo esté en la carpeta y el juego no lo cargue, las dos
presentes en instalaciones reales:

- **Sin extraer** — un `.mcpack` copiado a `resource_packs/`. El juego solo abre
  carpetas. Reparar lo instala de verdad y borra el archivo suelto.
- **Manifiesto anidado** — el pack se extrajo con su carpeta contenedora dentro,
  así que `manifest.json` quedó un nivel por debajo. Reparar sube el contenido.

En la lista aparecen con `⚠ el juego no lo carga` y un botón **Reparar**.
`scripts/auditar_instalacion.py` los enumera sin tocar nada.

## Desinstalar

Borra la carpeta del pack y olvida su origen. El archivo del que salió, en la
carpeta de descargas, no se toca nunca: no forma parte de la instalación.

## Versiones

Salen del `header.version` del manifiesto, sea lista (`[1,2,0]`) o texto. Nunca
del nombre del archivo: el nombre lo pone quien renombra la descarga.

| Estado | Significado | Badge |
|---|---|---|
| `IGUAL` | Misma versión instalada | ✓ instalado |
| `NUEVA` | La descarga es más reciente | ↑ actualización |
| `ANTERIOR` | La descarga es más vieja | ↓ anterior |
| `DESCONOCIDA` | Falta alguna versión o no son comparables | — |

Se comparan con `packaging.version`. Los pre-releases con guion bajo
(`2.0.0_beta`, que `packaging` rechaza) se normalizan a guion: el sufijo es
información real de orden.

## Nombres de los packs

`header.name` no siempre es un nombre:

- Lleva códigos de color (`§fHide §bArmor§6 | §aV1.2§r`), que se limpian.
- Puede ser una clave de localización. Cuatro packs del equipo de prueba se
  llaman literalmente `pack.name`; su nombre real está en `texts/en_US.lang`, y
  se resuelve desde ahí.

El `manifest.json` se lee con un parser tolerante: los packs reales traen BOM,
comentarios `//` y comas colgantes, y `json.loads` a secas los rechaza enteros.

## Badge NEW

Aparece la primera vez que un archivo entra en la lista de descargas y se apaga
al **abrir la pestaña Descargas**, no al escanear la carpeta: marcarlo al escanear
quemaría el aviso mientras el usuario está en otra pestaña.

La identidad es el SHA-256 del contenido, no el nombre. Ver
[ADR 0004](../decisiones/0004-hash-sha256-para-badge-new.md).

## Historial

Cada acción se registra con `accion` (`instalar` · `actualizar` · `reparar` ·
`desinstalar`), nombre, categoría, versión, versión anterior y momento. Se
muestra del más reciente al más antiguo; cuando dos caen en el mismo instante,
desempata el `id`.

## Observación de directorios

`Scanner` vigila con `QFileSystemWatcher` las cinco carpetas de contenido de la
instalación activa y la carpeta de descargas. Qt deja de observar un directorio
si desaparece, así que se re-engancha en cada evento.

Tras una acción de la propia app se llama a `Scanner.notificar_cambio()` en vez
de esperar al watcher. Ver [ADR 0005](../decisiones/0005-qfilesystemwatcher-para-monitoreo.md).
