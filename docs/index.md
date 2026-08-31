# MCPEModManager — Documentación

Gestor de mods para mcpelauncher-linux. Instala, desinstala y rastrea archivos `.so`, `.mcpack`, `.mcaddon` y `.zip` directamente en el entorno de Minecraft Bedrock en Linux.

## Arquitectura

- [Arquitectura general](arquitectura.md) — capas, flujo de datos, dependencias

## Funciones

- [Gestión de mods](funciones/gestion-mods.md) — instalar, desinstalar, versiones, historial, badge NEW

## Decisiones

- [Índice de decisiones (ADRs)](decisiones/index.md)

## Herramientas

- `check.sh` — sintaxis, importaciones, pyflakes, pruebas y arranque real de la UI
- `build.sh` — compila con Nuitka y comprueba que el binario arranca
- [`scripts/`](../scripts/) — sondas de diagnóstico que vale la pena conservar
