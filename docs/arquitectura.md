# Arquitectura

Gestor de contenido para Minecraft Bedrock en Linux: resource packs, behavior
packs, addons, skins, plantillas y mundos, dentro de la carpeta `com.mojang` del
juego.

## Las dos ideas que gobiernan el diseño

**1. Qué es un archivo se decide por su contenido.** La extensión no se mira
nunca. Un `.zip` puede ser un resource pack y un `.mcpack` puede ser cualquier
cosa. Lo que identifica a Bedrock es un `manifest.json` con `header.uuid` y un
`modules[].type` conocido — un modpack de CurseForge para Java también tiene
`manifest.json` en la raíz. Ver [ADR 0010](decisiones/0010-identificar-por-contenido.md).

**2. La identidad de un pack es el `header.uuid` de su manifiesto.** Es lo que
usa el propio juego: `minecraftpe/global_resource_pack_settings.json` guarda los
ajustes de cada pack bajo su `pack_id`, nunca bajo una ruta. De ahí sale el
reconocimiento de actualizaciones y la ausencia de duplicados. Ver
[ADR 0009](decisiones/0009-identidad-por-uuid.md).

## Estructura

```
MCPEModManager/
├── check.sh                # estático + pruebas + arranque real de la UI
├── build.sh                # Nuitka onefile, y comprueba que el binario arranca
├── docs/                   # Esta documentación
├── scripts/                # Sondas de diagnóstico
├── src/mcpemod/
│   ├── core/
│   │   ├── manifiesto.py   # Lectura del manifest.json — la identidad
│   │   ├── contenido.py    # Qué es un archivo, mirando dentro
│   │   ├── rutas.py        # Instalaciones detectadas y carpeta de descargas
│   │   ├── scanner.py      # Estado del disco y observación de directorios
│   │   ├── installer.py    # Instalar / actualizar / reparar / desinstalar
│   │   ├── store.py        # SQLite: historial, orígenes, vistos
│   │   ├── mod.py          # Instalado, EntradaHistorial, nombre de carpeta
│   │   └── version.py      # Comparación de versiones
│   ├── ui/
│   │   ├── ventana.py           # Selector de instalación + pestañas
│   │   ├── panel_lista.py       # Base de los tres paneles
│   │   ├── panel_instalados.py
│   │   ├── panel_descargas.py   # Pestaña «Carpetas»
│   │   ├── panel_historial.py
│   │   ├── estilo.py            # Colores derivados de la laca activa
│   │   ├── soltar.py            # Qué hacer con lo que se arrastra a la ventana
│   │   ├── trabajo.py           # La comprobación de red, fuera del hilo de la UI
│   │   └── widgets/
│   ├── senales.py          # Conexión de señales que sobrevive a Nuitka
│   └── main.py
└── tests/
```

## Capas

### Core (`mcpemod/core/`)

Toda la lógica. La única dependencia de Qt es `scanner.py`, que usa
`QFileSystemWatcher` y `Signal` — y solo de `QtCore`, sin nada gráfico. El resto
es Python puro.

`manifiesto.py` y `contenido.py` no tocan disco de escritura ni conocen la
instalación: solo leen y clasifican.

### UI (`mcpemod/ui/`)

Widgets de PySide6 sobre el sistema de diseño `wulf_qt`. Los paneles no tocan el
disco: piden datos al `Scanner` y acciones al `Installer`.

## Fuente de verdad

**Lo instalado se lee del disco, no de la base.** El jugador importa packs desde
el propio juego sin pasar por el gestor, y una lista construida solo desde la
base no los mostraría. `Scanner.leer_instalados()` recorre las carpetas de la
instalación activa y lee cada `manifest.json`.

La base guarda solo lo que el disco no sabe:

| Tabla | Para qué |
|---|---|
| `historial` | Qué pasó y cuándo |
| `origenes` | De qué archivo salió cada uuid |
| `vistos` | Hashes ya mostrados, para el badge NEW |
| `carpetas` | Dónde buscar contenido descargado |
| `emparejamientos` | Qué publicación es cada uuid, y qué no se encontró |
| `ajustes` | La clave de CurseForge |

## Flujo de datos

```
QFileSystemWatcher ──▶ Scanner.{instalados,descargas}_cambiados
                                  │
                                  ▼
                       Panel{Instalados,Descargas}.recargar()
                                  │
                                  ▼
              Scanner.leer_instalados()   Scanner.leer_descargas()
                       │                            │
                       ▼                            ▼
            manifest.json del disco         contenido.analizar()
```

Tras una acción propia, el panel llama a `Scanner.notificar_cambio()` en vez de
esperar al watcher, que tarda en reaccionar.

## Dónde va cada cosa

El destino lo decide el tipo del módulo declarado en el manifiesto. El pack nunca
declara una ruta:

| `modules[].type` | Carpeta |
|---|---|
| `resources` | `resource_packs/` |
| `data`, `script`, `client_data` | `behavior_packs/` |
| `skin_pack` | `skin_packs/` |
| `world_template` | `world_templates/` |
| *(sin manifiesto, con `level.dat`)* | `minecraftWorlds/` |

Un pack con módulos de recursos y de datos a la vez va a `behavior_packs/`: es
donde el juego espera los `data` y los `script`.

## Instalaciones

Un equipo puede tener varias (la nativa de mcpelauncher y una por flatpak), cada
una con su `games/com.mojang`. `detectar_instalaciones()` las encuentra y la
ventana deja elegir. Ver [ADR 0012](decisiones/0012-varias-instalaciones.md).

Las carpetas donde se busca contenido descargado son una lista editable, sembrada
con `xdg-user-dir DOWNLOAD` (aquí, `~/Descargas`). Se pueden añadir y quitar
todas menos la última. Ver [ADR 0013](decisiones/0013-carpetas-vigiladas-multiples.md).

## Pruebas

```bash
fish check.sh    # todo: estático, unitarios y arranque real de la UI
```

Los unitarios no tocan el juego: construyen una instalación falsa en `tmp_path`.
`tests/smoke_ui.py` no es un test de pytest a propósito — necesita
`QApplication`, y existe porque los fallos que dejaron una versión sin arrancar
(llamadas a `wulf_qt` con firmas equivocadas) no los ve ni pyflakes ni pytest.

Para comprobar contra datos reales:

```bash
python scripts/auditar_instalacion.py   # solo lectura, no toca nada
python scripts/captura_ui.py salida.png # captura la ventana sin pantalla
```
