# 0003 — Nuitka onefile para distribución

**Fecha:** 2026-08-30
**Estado:** Aceptada

## Contexto

La app necesita ejecutarse desde `~/.local/bin/mcpemod` sin instalar dependencias a mano. `wulf_qt` es una librería local que no está en pip.

## Decisión

Nuitka 4.1.3 con `--onefile` y `--enable-plugin=pyside6`. El binario compilado (`dist/mcpemod`, ~16 MB) se crea con `fish build.sh`. Un symlink en `~/.local/bin/mcpemod` apunta siempre al mismo path `dist/mcpemod`, así que cada recompilación actualiza el binario automáticamente sin tocar el enlace.

## Problema resuelto: sys.path en el binario

Los módulos UI tienen `sys.path.insert(0, <ruta-a-wulfenite>)`. Dentro del binario Nuitka, `__file__` vive en `/tmp/onefile_...` con una profundidad diferente — los `parents[N]` explotan con `IndexError`.

**Solución:** el insert está dentro de `try/except ImportError`. En el binario, `import wulf_qt` funciona directamente (está bundleado) y el insert nunca se ejecuta.

## Alternativas descartadas

- **PyInstaller**: más común pero genera más problemas con PySide6 en Wayland/Linux; Nuitka compile a C nativo con mejor rendimiento.
- **AppImage / Flatpak**: demasiado para un tool de desarrollo personal.

## Consecuencias

- Python 3.14 es "experimentalmente soportado" por Nuitka 4.1.3. El aviso es inofensivo en la práctica.
- `ccache` acelera recompilaciones: solo se recompilan los C files afectados por los cambios.
- El binario NO es portable a otras máquinas (linkea contra las libs del sistema).
