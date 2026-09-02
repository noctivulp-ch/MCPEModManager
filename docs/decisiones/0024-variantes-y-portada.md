# 0024 — Las variantes son las opciones del pack, y la portada lo identifica

Estado: Aceptada
Fecha: 2026-09-01

## Contexto

Una fila de la lista solo cabe el nombre y la versión. Eso deja fuera lo que uno
se pregunta antes de activar algo —qué hace, quién lo hizo, de qué depende— y,
sobre todo, deja fuera los **subpacks**, que el gestor leía y descartaba.

La documentación oficial dice lo que son: *«sub-packs let players choose between
different variations of a resource pack and switch between them at any time»*. No
son packs distintos: son las opciones del pack. En este equipo los traen 16 de 62
piezas, y son opciones de verdad — densidad del bosque en seis grados, si el
monstruo aparece solo de noche, con efectos o sin ellos, cada cuánto sale una
estructura.

Además, tres packs instalados se llaman «Better Foliage…» y dos de ellos se
diferencian por dos letras al final. Distinguirlos obligaba a leer el renglón
entero.

## Decisión

**La portada del pack se enseña en cada fila.** Es el `pack_icon.png` que el
juego usa en su propia lista, y lo traen 48 de las 50 carpetas de este equipo;
los mundos usan `world_icon.jpeg`, que es otro nombre para lo mismo. Con los dos,
62 de 62. Se lee de la carpeta, un nivel más abajo si el pack está anidado, y
del `.mcpack` sin extraer, que es un zip.

Se escala **sin suavizar**. Las texturas de Minecraft son de 16×16 y se amplían
con el vecino más cercano: es lo que hace que un bloque se vea como un bloque.
Con la interpolación por defecto una portada de 16 px llega a 34 como una mancha.

**Pulsar un pack abre su ficha**, con la descripción, el autor, la licencia, las
dependencias y las variantes. No choca con arrastrar: eso solo empieza desde el
asa, que se come sus propios eventos de ratón.

**La carpeta y el nombre de una variante no son lo mismo.** `folder_name` es lo
que se escribe en el archivo de activación; `name` es *«the name players see when
choosing your sub-pack»*. En un pack de este equipo la carpeta es `with_vfx` y el
nombre «With VFX effect». Escribir el nombre donde va la carpeta deja al juego
buscando una variante que no existe, **y no avisa**: el pack se aplica sin ella.

**No elegir no es no tener ninguna.** Sin elección el juego coge sola *«the
highest memory_performance_tier value that doesn't exceed the tier of the
player's device»*. Por eso la primera opción es «Lo elige el juego (automático)»
y no «Ninguna»: son cosas distintas y la segunda no existe.

**Elegir una variante no reactiva el pack.** Se cambia el campo de su entrada y
nada más. Desactivar y volver a activar lo mandaría al final de la lista, y el
orden es lo que decide cuál gana cuando dos packs tocan lo mismo.

**Solo se elige con el pack ya activo.** La variante vive dentro de la entrada de
activación: sin entrada no hay dónde ponerla. En la pestaña de instalados las
variantes se enseñan pero no se pueden tocar, y se dice por qué.

**Los `settings` de tipo `label` se enseñan como notas del autor.** La
documentación los describe como *«a description of what the pack and sub-packs
include»*, y es donde algunos avisan de cosas que el gestor no puede saber: «You
must restart Minecraft for the changes to take effect», «Subpacks can only be
changed while in the main menu».

## Consecuencias

Se limpian los caracteres del **Área de Uso Privado** (U+E000–U+F8FF) además de
los códigos `§x`. Son los glifos de la fuente de Minecraft —corazones, comida,
escudos— y dentro del juego dibujan algo; fuera son cajas vacías. Un pack llama a
su variante ` Monochrome Icons`.

Del `name` de una variante se usa solo la primera línea: hay autores que meten la
explicación entera ahí, uno de este equipo con cuatro párrafos. Lo que explica el
pack va en las notas, que es su sitio.

El manifiesto se **relee** al abrir la ficha en vez de guardarlo entero en el
listado: la descripción y las variantes solo hacen falta para un pack a la vez,
no para los sesenta de la lista.

`QRadioButton` sale con forma de casilla: el sistema de diseño le da al indicador
la misma regla que a `QCheckBox`, con el mismo `border-radius`. Se corrige en el
diálogo, pero el sitio de arreglarlo es la librería — una casilla marca varias
cosas y un radio elige una, y con la misma forma no se distinguen.

## Alternativas descartadas

**Un desplegable en vez de opciones a la vista.** Ocupa menos, pero elegir una
variante es justo el momento en que se quieren ver todas: «Rare / Common / Normal
(recommended)» se compara de un vistazo y en un desplegable no.

**Gestionar también los `values` de `global_resource_pack_settings.json`.** Son
las opciones que el jugador marca dentro del juego y las escribe el propio juego.
Sin un `settings` de tipo `toggle` o `slider` en el manifiesto —solo dos packs
traen `settings`, y ambos únicamente con `label`— no hay forma de saber qué
claves existen ni qué significan. Inventarlas sería escribir a ciegas.
