# Lluvia de ideas

Cosas que encajarían bien, anotadas al terminar la integración web. No son
compromisos: son candidatas, con lo que costaría y lo que daría a cambio.
Las tareas ya decididas viven en `ToDo.md`; esto es el paso anterior.

## Lo que el propio uso pide a gritos

**Actualizar todo.** Hay 21 packs con versión nueva. Actualizarlos de uno en uno
son 21 clics. Un botón que haga los confirmados de golpe, con su barra y su
resumen. Barato: la lógica ya está.

**Ver qué cambió antes de actualizar.** MCPEDL publica el `changelog` de cada
versión en el campo `revisions` y ahora mismo se ignora. Es lo que decide si una
actualización interesa o puede esperar.

**Deshacer una actualización.** Guardar el pack anterior en una papelera del
gestor antes de sobrescribirlo, y poder volver. Hoy actualizar es irreversible
salvo que el catálogo conserve el archivo viejo — que suele, pero no siempre.

**Filtrar la lista de instalados.** Con 62 elementos, encontrar uno es
desplazarse. Un campo de texto que filtre por nombre y autor.

**Separar por categorías con cabeceras.** Es lo que sustituye a los colores de
badge que hoy son un placeholder: en vez de distinguir por color, agrupar
`Recursos`, `Comportamiento`, `Mundos` bajo sus títulos.

## Lo que el juego permite y todavía no se toca

**Activar y desactivar.** Instalar deja el pack en su carpeta; que el juego lo
aplique es otra cosa —`global_resource_packs.json` y los `world_*_packs.json` de
cada mundo—. Es la pregunta abierta de `issues.md #3`, y la que más cambiaría lo
que la app puede hacer.

**Perfiles.** Conjuntos de packs activos con nombre: «Vanilla+», «PvP», «el
mundo de los niños». Depende de lo anterior.

**Gestión por mundo.** Cada mundo guarda su propia copia de los packs que usa.
Ver qué packs tiene un mundo, y sincronizarlos con la versión global, es una
vista que hoy no existe y el disco ya soporta.

**Dependencias.** Un behavior pack declara en `dependencies` el uuid de su
resource pack. Se leen y no se usan: se podría avisar al desinstalar algo de lo
que otro depende, y ofrecer instalar lo que falta.

**Skins y plantillas.** El código ya las clasifica y les da destino, pero no hay
ningún caso real con el que comprobarlo. Falta encontrar uno.

## Emparejamiento y catálogos

**Confirmar a mano una coincidencia probable.** Cuando un pack cambia de uuid
entre versiones mayores, el gestor no puede demostrarlo pero el usuario sí lo
sabe. Un «sí, es este» que quede recordado para siempre.

**Emparejar por parecido de contenido.** Para lo que la búsqueda por título no
encuentra: comparar la lista de archivos del pack instalado con la del publicado.
Dos versiones del mismo pack comparten casi todos los nombres de archivo. Caro,
pero resolvería buena parte de los 27 que hoy no se encuentran.

**Avisar al arrancar.** Comprobar en segundo plano al abrir la app y poner el
número en la pestaña: «Actualizaciones (21)». Sin pedirlo, sin bloquear.

**Más catálogos.** La interfaz `Fuente` está pensada para eso; añadir uno es un
archivo. Lo que aportaría algo distinto son los repositorios pequeños y los
sitios de addons que no están en MCPEDL ni en CurseForge.

**Modrinth queda descartado**: se comprobó contra su API y **no aloja contenido
de Bedrock**. Sus tipos de proyecto son `mod`, `modpack`, `resourcepack`,
`shader`, `plugin`, `datapack` y `minecraft_java_server`, y ninguno de sus
«loaders» es de Bedrock. Buscar «bedrock» ahí devuelve mods de Java que hablan
del bloque bedrock.

## Calidad de vida

**Icono y lanzador.** La app no tiene ni icono ni entrada en el menú.

**Miniaturas.** El catálogo publica una imagen por resultado. Hace falta
descargarlas en segundo plano y cachearlas: sin caché, veinte por página sería
peor que no ponerlas.

**Deshacer en general.** Desinstalar es un clic sin vuelta atrás. Una papelera
del gestor con lo borrado en los últimos N días cubriría eso y el deshacer de
actualizaciones con el mismo mecanismo.

**Exportar e importar la selección.** Un archivo con los uuid y versiones
instaladas, para rehacer el mismo conjunto en otro equipo o tras reinstalar.
Encaja con perfiles.

**Registro de lo que hace la red.** Hoy, si una comprobación no encuentra algo,
no hay forma de ver qué se preguntó. Un panel de diagnóstico con las consultas y
las respuestas ahorraría adivinar.

## Cosas que suenan bien y probablemente no valen la pena

**Un cliente de la tienda del juego.** El contenido de pago lo gestiona el juego
y está cifrado. No hay nada que hacer ahí, y ya está detectado para dejarlo en
paz ([ADR 0016](decisiones/0016-contenido-de-la-tienda.md)).

**Editar packs desde el gestor.** Es otro programa. Abrir la carpeta en el
explorador —que ya hace— cubre el 90% de lo que haría falta.

**Sincronizar entre equipos por la nube.** Mucho aparato para un problema que
resuelve mejor un `rsync`, y meter credenciales en esta app abriría una
superficie que hoy no tiene.
