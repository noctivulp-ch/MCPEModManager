# 0004 — Hash SHA-256 para el badge NEW

**Fecha:** 2026-08-30
**Estado:** Aceptada

## Contexto

El badge NEW debe aparecer la primera vez que un archivo aparece en la carpeta Descargas y no volver a mostrarse aunque el usuario cierre y reabra la app.

## Decisión

Identidad del archivo = SHA-256 de su contenido. La tabla `vistos` guarda los hashes ya mostrados.

## Alternativas descartadas

- **Por nombre de archivo**: el mismo archivo renombrado activaría el badge; un archivo distinto con el mismo nombre no lo activaría. Ambos comportamientos son incorrectos.
- **Por ruta completa**: rompería si el usuario mueve el archivo dentro de Downloads.
- **Por inode/mtime**: frágil con copias y sistemas de archivos remotos.

## Consecuencias

Leer el hash requiere leer todo el archivo al escanearlo. Para archivos grandes de mods (típicamente 1–50 MB) esto es aceptable. Si en el futuro hay archivos de cientos de MB, se puede cambiar a un hash parcial (primeros+últimos N bytes) sin cambiar la interfaz pública de `Store`.
