# 0005 — QFileSystemWatcher para monitoreo de directorios

**Fecha:** 2026-08-30
**Estado:** Aceptada

## Contexto

La app debe detectar automáticamente cuando el usuario copia un archivo a Downloads o cuando un mod se instala/desinstala, sin que tenga que recargar manualmente.

## Decisión

`QFileSystemWatcher` de Qt. `Scanner` lo instancia en su `__init__` y observa `MODS_DIR` y `DOWNLOADS_DIR`. Emite señales Qt (`mods_cambiados`, `descargas_cambiadas`) que los paneles reciben directamente.

## Alternativas descartadas

- **Polling con QTimer**: no es reactivo; un intervalo de 2s hace la UI sentirse lenta, un intervalo de 100ms consume CPU innecesariamente.
- **watchdog (Python)**: librería externa que duplica lo que Qt ya ofrece gratuitamente.
- **inotify directo**: más bajo nivel sin ventaja sobre QFileSystemWatcher para este uso.

## Consecuencias

`Scanner` hereda de `QObject` porque `QFileSystemWatcher` requiere un event loop Qt activo. Esto significa que `Scanner` no se puede instanciar fuera de un contexto con `QApplication` activa — no es un problema en la app, pero sí significa que los tests unitarios del scanner requieren `QApplication`. Por eso los tests de scanner están excluidos de la suite actual (que es core-only).
