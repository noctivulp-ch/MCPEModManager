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

## Identidad: qué pack es, y qué versión

La norma de Bedrock: el `header.uuid` identifica el pack y debe ser estable entre
versiones; lo que sube es `header.version`, y al reimportar *"the new pack will
replace the old one if the version is higher, and ignored if it's the same or
lower"*.

En la práctica hay autores que cambian el uuid en cada publicación —uno llega a
codificar el número de versión dentro del uuid—. Para el juego cada versión suya
es un pack nuevo y se le acumulan; el gestor los reconoce por el **nombre** y
reemplaza en vez de duplicar.

Al instalar:

1. Se busca ese **uuid** entre lo que ya hay en disco; si no aparece, el nombre.
2. Si aparece, se reemplaza **esa carpeta**, con el nombre que tuviera.
3. Se registra como `actualizar`, con la versión anterior.

A diferencia del juego, el gestor **sí deja volver a una versión anterior**: el
juego ignora una reimportación de versión igual o menor.

La carpeta de un pack nuevo se nombra **como la nombraría el juego**: sin los
códigos `§`, sin barras verticales ni espacios, recortada a diez caracteres.
`§fHide §bArmor§6 | §aV1.2§r` → `HideArmorV`. No es cosmético: con otro nombre, el
mismo pack acabaría dos veces, una por cada vía de instalación.

La comparación de nombres ignora la versión metida dentro («Hide Armor | V1.2» y
«… | V1.3.1» son el mismo pack) pero no los sufijos que distinguen hermanos
(«NG» / «FG», «RP» / «BP»), que son packs distintos y conviven instalados.

Ver [ADR 0020](../decisiones/0020-nombre-identifica-uuid-versiona.md).

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

## La página del pack

Algunos manifiestos declaran `metadata.url`, la página de quien lo publica —7 de
los 43 packs del equipo de prueba—. Cuando está, la tarjeta muestra un botón
**Sitio** que la abre.

Sirve además para emparejar: esa dirección señala la publicación directamente, así
que al buscar en un catálogo el candidato cuya URL coincide se mira antes que
ningún otro. Es la pista más fuerte que hay, por delante del autor.

También se lee `metadata.license` y se muestra junto a los detalles.

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

## Actualizaciones

La pestaña **Actualizaciones** pregunta a los catálogos si hay versión nueva de
lo que hay instalado.

Los catálogos no indexan ni por uuid ni por nombre de manifiesto, así que el
emparejamiento va al revés: se buscan candidatos por título, se ponen delante los
del mismo autor, y se **confirma** leyendo el manifiesto publicado. Solo el
positivo cuenta.

Confirma si coincide **el nombre del pack o el uuid**. Hacen falta las dos
señales porque los autores no son consistentes:

| | uuid | nombre | Qué lo empareja |
|---|---|---|---|
| Déesse UI | cambia cada versión | estable | el nombre |
| Hide Armor | estable | lleva la versión dentro | el uuid |

| Confianza | Qué significa | Qué se ofrece |
|---|---|---|
| Confirmado | El publicado es este pack | **Actualizar** |
| «sin confirmar» | Mismo autor y título parecido, pero el manifiesto no lo confirma | **Ver**, para decidir |
| No aparece | No se encontró | — |

Una coincidencia sin confirmar **no** cuenta como actualización: instalarla
encima podría sobrescribir con un pack que no es el mismo.

Si el uuid publicado es el mismo que el instalado, es exactamente esa versión y
tampoco se ofrece — por más que el número de versión diga otra cosa.

Quedan fuera el contenido de la tienda, lo que no tiene uuid (los mundos) y lo
que no declara versión.

Actualizar descarga el archivo a un temporal y lo pasa por el mismo camino que
uno de una carpeta vigilada, así que el destino lo decide la misma lógica que en
una instalación normal y reutiliza la carpeta que ya existía.

Se instala **solo el pack que se actualiza**: lo publicado puede ser un addon con
más cosas dentro, y actualizar uno no debe traer de propina lo que nadie pidió.
En el equipo de prueba pasa con «CSO Terrorists», que está publicado dentro del
addon de «Actual Guns 2».

**Actualizar todo** hace de una vez las confirmadas. Las que no lo están quedan
fuera: pueden ser otro pack del mismo autor, y eso se decide una por una mirando
su publicación. Si alguna falla, las demás siguen y al final se dice cuáles no
salieron.

### Coste

El primer barrido de sesenta packs lleva unos minutos: son cientos de peticiones.
La pestaña muestra los resultados según llegan y se puede cancelar. Lo
comprobado se guarda —también lo no encontrado, que es la mayor parte— así que
los barridos siguientes salen de la caché al instante y solo se vuelve a
preguntar pasadas doce horas, o una semana para lo que no apareció.

Ver [ADR 0017](../decisiones/0017-emparejar-con-los-catalogos.md) y
[ADR 0018](../decisiones/0018-leer-manifiestos-remotos.md).

## Explorar

La pestaña **Explorar** busca en el catálogo y instala sin pasar por el
navegador. Sin texto muestra las novedades; con texto, busca. Se espera un
momento desde la última tecla antes de consultar, y las respuestas de consultas
ya superadas se descartan.

Instalar descarga el archivo y lo pasa por el mismo camino que uno de una carpeta
vigilada. Además se recuerda de qué publicación vino cada uuid, así que la
pestaña de Actualizaciones ya no tendrá que buscarlo.

## Fuentes

| Fuente | Estado |
|---|---|
| MCPEDL | Siempre disponible, sin autenticación. Sirve también el catálogo de Bedrock de CurseForge |
| CurseForge | Necesita una clave gratuita de `console.curseforge.com`, que se pega en **Ajustes**. Sin ella no se ofrece |

La clave la pone el usuario y no viene con la app: los términos de CurseForge
dicen que es intransferible y que no puede compartirse con terceros. Ver
[ADR 0021](../decisiones/0021-clave-de-curseforge.md).

En CurseForge, además, quien publica puede desactivar la descarga desde
aplicaciones de terceros. Esas publicaciones aparecen marcadas con «solo desde su
web» y con enlace a su página: se pueden mirar e instalar a mano, pero el gestor
no las descarga por detrás.

## Rutas del sistema en la interfaz

Las rutas que muestra la app (la de la instalación activa y las carpetas
vigiladas) son botones, no texto: un clic las abre en el explorador de archivos,
que es lo que se quiere hacer con ellas casi siempre. Se abrevian con `~` y se
recortan por la izquierda cuando no caben — el final identifica el sitio mucho
mejor que el principio, que casi siempre es `~/.local/share`.
