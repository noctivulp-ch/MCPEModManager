# Arquitectura

Gestor de mods para mcpelauncher-linux. Instala, desinstala y rastrea archivos
`.so`, `.mcpack`, `.mcaddon` y `.zip` directamente en el entorno de Minecraft
Bedrock en Linux.

## Estructura

```
MCPEModManager/
├── pyproject.toml          # Dependencias: PySide6, packaging
├── check.sh                # sintaxis + imports + pyflakes + pytest + arranque UI
├── build.sh                # Nuitka onefile → dist/mcpemod
├── docs/                   # Esta documentación
├── src/mcpemod/
│   ├── core/               # Lógica de negocio
│   │   ├── mod.py          # Mod, EntradaHistorial, EstadoVersion, TipoArchivo
│   │   ├── rutas.py        # Rutas del sistema
│   │   ├── store.py        # Persistencia SQLite (+ migración de esquema)
│   │   ├── installer.py    # Instalar / actualizar / desinstalar
│   │   ├── scanner.py      # Estado del disco y observación de directorios
│   │   └── version.py      # Detección, normalización y comparación de versiones
│   ├── ui/
│   │   ├── ventana.py           # QMainWindow + QTabWidget dentro de una Bandeja
│   │   ├── panel_lista.py       # Base de los tres paneles (título + scroll)
│   │   ├── panel_instalados.py
│   │   ├── panel_descargas.py
│   │   ├── panel_historial.py
│   │   ├── estilo.py            # Colores derivados de la laca activa
│   │   └── widgets/tarjeta_mod.py
│   └── main.py             # Punto de entrada
└── tests/                  # Unitarios + smoke_ui.py (arranque real, sin display)
```

## Capas

### Core (`mcpemod/core/`)

Toda la lógica de negocio. La única dependencia de Qt es `scanner.py`, que usa
`QFileSystemWatcher` y `Signal` — y solo de `QtCore`, sin nada gráfico. El resto
(`mod`, `rutas`, `store`, `installer`, `version`) es Python puro y se prueba sin
Qt de por medio.

### UI (`mcpemod/ui/`)

Widgets de PySide6 con el sistema de diseño `wulf_qt`. Los paneles no tocan el
disco: piden datos al `Scanner` y acciones al `Installer`. Los tres heredan de
`PanelLista`, que aporta el título tallado, el scroll y el estado vacío.

## Flujo de datos

```
QFileSystemWatcher ──▶ Scanner.{mods,descargas}_cambiados
                                  │
                                  ▼
                       Panel{Instalados,Descargas}.recargar()
                                  │
                                  ▼
                     Scanner.leer_{instalados,descargas}()
                            │              │
                            ▼              ▼
                          Store          disco
```

Al pulsar Instalar o Desinstalar, el panel llama al `Installer` y después a
`Scanner.notificar_cambio()`. El watcher tarda en reaccionar y no cubre lo que se
escribe fuera de los directorios observados, así que sin esa notificación
explícita la vista se quedaría desactualizada tras la propia acción del usuario.

## Fuente de verdad del estado instalado

`Scanner.leer_instalados()` combina dos fuentes:

1. **La base** — lo que el gestor instaló, incluidos los packs extraídos, que no
   viven en `mods/` y por tanto no se pueden descubrir recorriéndolo.
2. **El disco** — los `.so` que el usuario copió a mano a `mods/`. Son mods
   puestos aunque el gestor no los conozca; ignorarlos haría que la lista
   mintiera.

Los registros de la base cuyas rutas ya no existen se purgan al leer: alguien
borró el mod por fuera y la base dejó de reflejar el disco.

## Rutas del sistema

```
~/.local/share/mcpelauncher/mods/                           mods .so activos
~/.local/share/mcpelauncher/games/com.mojang/minecraftpe/
    resource_packs/                                         resource packs
    behavior_packs/                                         behavior packs
~/.local/share/mcpemod/mods.db                              base del gestor
~/Downloads/                                                carpeta observada
```

## Pruebas

```bash
fish check.sh    # todo: estático, unitarios y arranque real de la UI
```

Los unitarios de `tests/` no tocan el sistema real: redirigen los directorios de
destino a `tmp_path`. `tests/smoke_ui.py` no es un test de pytest a propósito —
necesita `QApplication`, y existe porque los fallos que dejaron la primera
versión sin arrancar (llamadas a `wulf_qt` con firmas equivocadas) no los ve ni
pyflakes ni la suite unitaria: solo se ven construyendo los widgets.
