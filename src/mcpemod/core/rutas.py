"""Rutas del sistema para mcpelauncher y la app."""

from pathlib import Path

MCPE_DATA = Path.home() / ".local/share/mcpelauncher"
MODS_DIR = MCPE_DATA / "mods"
RESOURCE_PACKS_DIR = MCPE_DATA / "games/com.mojang/minecraftpe/resource_packs"
BEHAVIOR_PACKS_DIR = MCPE_DATA / "games/com.mojang/minecraftpe/behavior_packs"

#: Todo lo que el gestor instala vive en alguno de estos. Es lo que se observa
#: y lo que se recorre para saber qué hay puesto.
DIRECTORIOS_INSTALACION = (MODS_DIR, RESOURCE_PACKS_DIR, BEHAVIOR_PACKS_DIR)

APP_DATA = Path.home() / ".local/share/mcpemod"
DB_PATH = APP_DATA / "mods.db"
DESCARGAS_DIR = Path.home() / "Downloads"

EXTENSIONES_SOPORTADAS = {".so", ".mcpack", ".mcaddon", ".zip"}
