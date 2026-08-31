# 0017 — Emparejar lo instalado con lo publicado, confirmando por uuid

**Fecha:** 2026-08-31
**Estado:** Aceptada

## Contexto

Para saber si un pack tiene versión nueva hay que encontrarlo en algún catálogo.
Lo natural sería preguntar por su `header.uuid`, que es su identidad real
([ADR 0009](0009-identidad-por-uuid.md)).

**Ningún catálogo lo indexa.** Se comprobó contra la API de MCPEDL: la respuesta
no contiene la palabra `uuid` en ningún campo. Es lógico — el uuid vive dentro
del zip, y el catálogo indexa metadatos, no contenido.

Buscar por título tampoco basta: hay diez «Hide Armor» de autores distintos, y
elegir el más popular sobrescribiría lo instalado con otro pack.

## Decisión

El emparejamiento va al revés de como se pediría, en tres pasos:

1. **Buscar** candidatos por título, con consultas de lo específico a lo general.
   El nombre del manifiesto suele traer la versión pegada («Hide Armor | V1.2») y
   eso no encuentra nada, así que se prueba también sin ella y recortado.
2. **Ordenar** poniendo delante los del mismo autor que declara
   `metadata.authors` del manifiesto instalado. Es la señal más barata y la que
   más acierta.
3. **Confirmar** leyendo el manifiesto publicado por `Range` y comparando el
   uuid. Solo el positivo cuenta: un archivo que no se pueda leer nunca produce
   un emparejamiento.

Leer el manifiesto remoto cuesta unas dos peticiones y menos del 1% del archivo
(ver [ADR 0018](0018-leer-manifiestos-remotos.md)).

### Dos niveles de confianza

Un pack puede cambiar de `uuid` entre versiones mayores — pasa de verdad: el
«Actual Guns 2» instalado en el equipo de prueba tiene `8533dbc2…` y el publicado
`dd5dac7a…`. Cuando eso ocurre no queda ninguna señal automática que demuestre
que son el mismo pack.

| Confianza | Cuándo | Qué se ofrece |
|---|---|---|
| `CONFIRMADO` | El uuid coincide | Botón **Actualizar** |
| `PROBABLE` | Mismo autor **y** título equivalente, uuid distinto | Badge «sin confirmar» y botón **Ver** |
| `NINGUNO` | No se encontró | No aparece |

Una coincidencia probable **no** cuenta como actualización. Instalarla encima
podría sobrescribir lo instalado con un pack que no es el mismo, y esa decisión
es del usuario con la publicación delante.

Se exigen las dos condiciones —autor y título— porque con una sola el catálogo
está lleno de candidatos que cumplirían.

## Coste, y cómo se acota

Un barrido de sesenta packs son cientos de peticiones. Tres cosas lo hacen
viable:

- **Techo por pack** (`MAX_LECTURAS`): sin él, un pack cuyos candidatos son
  addons grandes se lleva varios minutos él solo.
- **Caché de emparejamientos**, con el resultado negativo incluido. Los packs que
  no están en ningún catálogo son la mayor parte del coste y no van a aparecer
  mañana: se reintentan a la semana, no en cada arranque.
- **Varios packs a la vez**, con el reparto de cortesía de `red` espaciando las
  peticiones a cada servicio.

## Consecuencias

El primer barrido tarda; los siguientes salen de la caché al instante. Por eso la
pestaña muestra los resultados según llegan y se puede cancelar, en vez de dejar
la ventana quieta hasta el final.

La tasa de acierto depende de que el pack esté publicado y de que su título se
parezca a lo que se buscó. Un pack que no se encuentre no es un fallo del
gestor: mucho contenido instalado no está en ningún catálogo público.
