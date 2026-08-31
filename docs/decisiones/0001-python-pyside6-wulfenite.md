# 0001 — Python + PySide6 + wulfenite como stack

**Fecha:** 2026-08-30
**Estado:** Aceptada

## Contexto

El usuario quería una app de escritorio Linux para gestionar mods de mcpelauncher. Tenía experiencia con Python y Qt, y el workspace ya incluía `wulfenite_ui` — un sistema de diseño Qt propio construido previamente.

## Decisión

Python 3.14 + PySide6 6.6+ como stack. `wulf_qt` (wulfenite) como sistema de diseño, referenciado como librería local en `../#Libs/wulfenite_ui/PyQT/src/`.

## Alternativas descartadas

- **Electron / web**: el usuario prefiere Qt y la app debe integrarse con paths del sistema Linux de forma directa.
- **PyGTK / wxPython**: el usuario ya tiene wulfenite construido para Qt; usar otro toolkit tiraría ese trabajo.

## Consecuencias

`wulf_qt` no se instala vía pip — es una dependencia de path local. El `sys.path.insert` en cada módulo UI lo resuelve en desarrollo. En el binario compilado (Nuitka), está bundleado y el insert no se ejecuta (ver [0003](0003-nuitka-onefile.md)).
