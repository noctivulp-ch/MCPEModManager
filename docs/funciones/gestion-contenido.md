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

## Formas de instalación

El contenido aparece en la carpeta del juego de tres formas, y **las tres son
válidas** — el juego las admite. Solo la primera es la que produce este gestor:

| Forma | Qué es | Badge |
|---|---|---|
| Carpeta | `manifest.json` en la raíz de la carpeta | — |
| Empaquetado | Un `.mcpack` copiado sin extraer | `sin extraer` |
| Anidado | Extraído con su carpeta contenedora dentro | `carpeta anidada` |

El botón **Extraer** deja las dos últimas como la primera. No las arregla: las
uniforma, para que actualizarlas y desinstalarlas funcione igual que con el
resto. Ver [ADR 0014](../decisiones/0014-forma-de-instalacion.md).

`scripts/auditar_instalacion.py` las enumera sin tocar nada.

## Contenido de la tienda

Lo comprado en el Marketplace lo gestiona el juego: lo descarga, lo actualiza y
lo borra él. Se reconoce porque viene cifrado y firmado —trae `contents.json`
con su cabecera binaria y `signatures.json`, que ningún pack descargado por fuera
tiene— y en la lista sale con el badge `Tienda` y sin botones: «lo gestiona el
juego».

Queda fuera de la búsqueda de actualizaciones: ese contenido no está en los
catálogos públicos y comprobarlo sería trabajo tirado.

Ver [ADR 0016](../decisiones/0016-contenido-de-la-tienda.md).

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

Cada acción se registra con `accion` (`instalar` · `actualizar` · `normalizar` ·
`desinstalar`), nombre, categoría, versión, versión anterior y momento. Se
muestra del más reciente al más antiguo; cuando dos caen en el mismo instante,
desempata el `id`.

## Arrastrar y soltar

Se puede soltar cualquier cosa sobre la ventana, desde donde sea:

| Lo que se suelta | Qué pasa |
|---|---|
| Archivo que es contenido de Bedrock | Se instala |
| Carpeta | Se añade a las vigiladas |
| Cualquier otra cosa | Se avisa, y nada más |

Una carpeta no se intenta instalar aunque tenga un `manifest.json` dentro: es
ambigua, y vigilarla no destruye nada mientras que instalarla por error sí.

Soltar varios a la vez funciona; el aviso final resume qué pasó con cada uno.
Ver [ADR 0015](../decisiones/0015-arrastrar-y-soltar.md).

## Carpetas vigiladas

El gestor busca contenido descargado en una lista de carpetas, no en una sola.
Arranca con la del sistema (`xdg-user-dir DOWNLOAD`; en un escritorio en español,
`~/Descargas`), y desde la pestaña **Carpetas** se pueden añadir otras —con el
botón o arrastrándolas— y quitar cualquiera: la inicial no tiene estatus especial.

Siempre queda al menos una: quedarse sin ninguna dejaría la pestaña vacía para
siempre y sin nada que pulsar para recuperarla. Con una sola carpeta el botón de
quitar ni se dibuja.

Una carpeta que desaparece del disco (un externo desconectado) se salta sin
romper nada y se muestra marcada, pero no se borra de la lista.

Ver [ADR 0013](../decisiones/0013-carpetas-vigiladas-multiples.md).

## Observación de directorios

`Scanner` vigila con `QFileSystemWatcher` las cinco carpetas de contenido de la
instalación activa y todas las carpetas vigiladas. Qt deja de observar un
directorio si desaparece, así que se re-engancha en cada evento.

Analizar un archivo cuesta abrir su zip, y con varias carpetas eso se repetiría
en cada refresco: el análisis se cachea por `(ruta, tamaño, mtime)`, de modo que
un archivo solo se relee si cambió.

Tras una acción de la propia app se llama a `Scanner.notificar_cambio()` en vez
de esperar al watcher. Ver [ADR 0005](../decisiones/0005-qfilesystemwatcher-para-monitoreo.md).

## Rutas del sistema en la interfaz

Las rutas que muestra la app (la de la instalación activa y las carpetas
vigiladas) son botones, no texto: un clic las abre en el explorador de archivos,
que es lo que se quiere hacer con ellas casi siempre. Se abrevian con `~` y se
recortan por la izquierda cuando no caben — el final identifica el sitio mucho
mejor que el principio, que casi siempre es `~/.local/share`.
