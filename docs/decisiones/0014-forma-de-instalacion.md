# 0014 — La forma de instalación se describe, no se juzga

**Fecha:** 2026-08-30
**Estado:** Aceptada

## Contexto

En una instalación real, el contenido aparece de tres formas:

| Forma | Qué es |
|---|---|
| `CARPETA` | Carpeta con `manifest.json` en su raíz. Lo que produce este gestor. |
| `EMPAQUETADO` | Un `.mcpack` copiado a la carpeta sin extraer. |
| `ANIDADO` | Extraído con su carpeta contenedora dentro, con el manifiesto un nivel más abajo. |

La primera versión de esto las etiquetaba como **«⚠ el juego no lo carga»** y
ofrecía «Reparar». Era una afirmación sobre el comportamiento del juego que no se
había comprobado — y es falsa: el juego sí usa esas formas, aunque no sea lo
ideal. Corresponden a otra manera de instalar, que este gestor no produce.

## Decisión

`Instalado.forma` describe cómo está puesta la pieza y nada más. El badge dice
`sin extraer` o `carpeta anidada`, sin predicar nada sobre el juego, y la acción
se llama **Extraer** (`Installer.normalizar`), no «Reparar».

El motivo que se le da al usuario es el real: dejarlo como carpeta permite
actualizarlo y desinstalarlo igual que el resto. No que estuviera roto.

## Alternativas descartadas

- **Ocultar esas piezas**: están instaladas y ocupan sitio; no verlas es peor que
  verlas.
- **Normalizarlas solas al detectarlas**: modificar la carpeta del juego sin que
  nadie lo pida, por una preferencia de formato del gestor.
- **Mantener «Reparar»**: la palabra afirma que algo está mal.

## Consecuencias

Es una lección sobre el resto del proyecto: las etiquetas de la interfaz son
afirmaciones sobre el dominio y valen lo que valga su evidencia. Aquí no la
había. Cuando la evidencia existe —el `pack_id` de
`global_resource_pack_settings.json` en la
[ADR 0009](0009-identidad-por-uuid.md)— se cita.
