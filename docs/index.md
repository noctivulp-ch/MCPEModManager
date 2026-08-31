# MCPEModManager — Documentación

Gestor de contenido para Minecraft Bedrock en Linux: resource packs, behavior
packs, addons, skins, plantillas y mundos, dentro de la carpeta `com.mojang` del
juego.

Dos ideas gobiernan el diseño, y las dos salen de inspeccionar una instalación
real:

- **Qué es un archivo se decide por su contenido**, nunca por su extensión.
- **La identidad de un pack es el `header.uuid` de su manifiesto** — es lo que
  usa el propio juego.

## Arquitectura

- [Arquitectura general](arquitectura.md) — capas, fuente de verdad, flujo de datos

## Funciones

- [Gestión de contenido](funciones/gestion-contenido.md) — reconocer, instalar,
  actualizar desde los catálogos, desinstalar, versiones, historial

## Decisiones

- [Índice de decisiones (ADRs)](decisiones/index.md)

## Herramientas

| | |
|---|---|
| `fish check.sh` | Sintaxis, importaciones, pyflakes, pruebas y arranque real de la UI |
| `fish build.sh` | Compila con Nuitka y comprueba que el binario arranca |
| `scripts/auditar_instalacion.py` | Audita las instalaciones reales, en solo lectura |
| `scripts/captura_ui.py` | Captura la ventana en un PNG, sin pantalla |
| `scripts/repro_nuitka_pyside_connect.py` | Repro del fallo de Nuitka que documenta la ADR 0008 |
