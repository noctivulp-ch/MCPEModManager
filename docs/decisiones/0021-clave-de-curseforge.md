# 0021 — La clave de CurseForge la pone el usuario

**Fecha:** 2026-08-31
**Estado:** Aceptada

## Contexto

La API de CurseForge exige una clave. Otros launchers de código abierto integran
CurseForge sin pedírsela a nadie, así que la pregunta era obligada: ¿cómo lo
hacen, y se puede hacer igual?

**La traen embebida en el código y en los binarios.** En PrismLauncher eso motivó
un informe de incumplimiento de los términos de servicio, que citaba:

> §2.2 — *"each Developer will be issued a unique API Key (the «API Key»), which
> is **non-transferable and may not be shared with any third party**."*
>
> §9.b — *"Developer shall … promptly delete or destroy all copies of any API Key"*
>
> — [PrismLauncher/PrismLauncher#263](https://github.com/PrismLauncher/PrismLauncher/issues/263)

El informe proponía lo estándar: un servidor propio que guarde la clave y haga de
intermediario. Se cerró **como «not planned»**.

## Decisión

La clave la pone el usuario, en Ajustes. Sin ella, CurseForge se declara no
disponible y la app no lo ofrece.

No se embebe ninguna clave. No es una cuestión de prudencia legal abstracta: la
clave identifica a quien la pidió, y repartirla dentro de un programa hace
responder a esa persona por el uso que le dé cualquiera. Un intermediario propio
sería lo correcto, pero esta app no tiene servidor ni razón para tenerlo.

Tampoco es urgente: **MCPEDL ya sirve el catálogo de Bedrock de CurseForge**, con
descarga directa desde el mismo CDN y sin autenticación. En una muestra de 50
publicaciones, las 50 traían `source: "curseforge"`.

## Distribución cerrada por el autor

Hay una segunda cosa que la API impone y que conviene respetar. Los autores
pueden desactivar la distribución de su proyecto por servicios de terceros; la
API entonces devuelve sus archivos **sin `downloadUrl`**.

Existe el apaño —reconstruir a mano la dirección del CDN— y hay herramientas que
lo hacen. Aquí no: es una decisión deliberada de quien publica, y saltársela con
un truco de construcción de URLs es exactamente lo que esa opción existe para
impedir.

Esas publicaciones se muestran marcadas con «solo desde su web» y con enlace a su
página. Se pueden mirar y se pueden instalar a mano; lo que no se hace es
descargarlas por detrás.

## Consecuencias

La pestaña de CurseForge no existe hasta que alguien pegue una clave, y para la
mayoría no hará falta nunca. Lo que aporta sobre MCPEDL es el catálogo completo y
sus filtros propios.

Si alguna vez hubiera un servidor del proyecto, el intermediario con la clave
sería la forma correcta de quitarle ese paso al usuario. Queda anotado, no
planificado.
