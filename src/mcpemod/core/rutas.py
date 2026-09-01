"""Instalaciones de Minecraft Bedrock detectadas en el sistema.

Un mismo equipo puede tener varias: la nativa de mcpelauncher y una por cada
flatpak. Todas comparten la misma estructura interna porque la crea el juego,
no el launcher — las carpetas de `com.mojang` existen idénticas incluso en una
instalación donde nunca se instaló nada.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

#: Dónde vive `games/com.mojang` en cada launcher conocido.
_RAICES_LAUNCHER = (
    ("Nativa", Path.home() / ".local/share/mcpelauncher"),
    ("mcpelauncher (flatpak)", Path.home() / ".var/app/io.mrarm.mcpelauncher/data/mcpelauncher"),
    ("MCPELauncher (flatpak)", Path.home() / ".var/app/com.mcpelauncher.MCPELauncher/data/mcpelauncher"),
    ("Trinity (flatpak)", Path.home() / ".var/app/com.trench.trinity.launcher/data/mcpelauncher"),
    ("Cianova (flatpak)", Path.home() / ".var/app/org.cianova.Launcher/data/mcpelauncher"),
)

APP_DATA = Path.home() / ".local/share/mcpemod"
DB_PATH = APP_DATA / "mods.db"


@dataclass(frozen=True)
class Instalacion:
    """Una instalación del juego: dónde va cada clase de contenido."""

    nombre: str
    raiz_launcher: Path
    com_mojang: Path

    @property
    def resource_packs(self) -> Path:
        return self.com_mojang / "resource_packs"

    @property
    def behavior_packs(self) -> Path:
        return self.com_mojang / "behavior_packs"

    @property
    def skin_packs(self) -> Path:
        return self.com_mojang / "skin_packs"

    @property
    def world_templates(self) -> Path:
        return self.com_mojang / "world_templates"

    @property
    def mundos(self) -> Path:
        return self.com_mojang / "minecraftWorlds"

    @property
    def respaldos_de_mundos(self) -> Path:
        """Dónde se guardan las copias de los mundos de esta instalación.

        Dentro de `com.mojang`, para que viajen con ella si se mueve o se copia,
        pero **fuera de `minecraftWorlds`**: ahí dentro el gestor —y el propio
        juego— los tomarían por mundos, y aparecerían duplicados.

        El nombre no coincide con ninguna carpeta del juego, así que este no la
        va a pisar ni a vaciar creyendo que es suya.
        """
        return self.com_mojang / "mcpemod_respaldos"

    @property
    def mods_nativos(self) -> Path:
        """Los `.so` del launcher — no son contenido del juego, pero se gestionan igual."""
        return self.raiz_launcher / "mods"

    @property
    def directorios_contenido(self) -> tuple[Path, ...]:
        return (
            self.resource_packs,
            self.behavior_packs,
            self.skin_packs,
            self.world_templates,
            self.mundos,
        )

    def contar_contenido(self) -> int:
        """Cuántos elementos tiene instalados — sirve para elegir la más usada."""
        return sum(
            len(list(d.iterdir())) for d in self.directorios_contenido if d.is_dir()
        )


def detectar_instalaciones() -> list[Instalacion]:
    """Las instalaciones presentes, de la que más contenido tiene a la que menos."""
    encontradas = [
        Instalacion(nombre=nombre, raiz_launcher=raiz, com_mojang=raiz / "games/com.mojang")
        for nombre, raiz in _RAICES_LAUNCHER
        if (raiz / "games/com.mojang").is_dir()
    ]
    encontradas.sort(key=lambda i: -i.contar_contenido())
    return encontradas


def carpeta_descargas() -> Path:
    """La carpeta de descargas del usuario, según su configuración regional.

    `~/Downloads` no vale como valor fijo: en un escritorio en español la carpeta
    real es `~/Descargas`, y `~/Downloads` puede existir a la vez, vacía.
    """
    variable = os.environ.get("XDG_DOWNLOAD_DIR")
    if variable and Path(variable).is_dir():
        return Path(variable)

    try:
        salida = subprocess.run(
            ["xdg-user-dir", "DOWNLOAD"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip()
        if salida and Path(salida).is_dir() and Path(salida) != Path.home():
            return Path(salida)
    except (OSError, subprocess.SubprocessError):
        pass

    for candidata in (Path.home() / "Descargas", Path.home() / "Downloads"):
        if candidata.is_dir():
            return candidata
    return Path.home() / "Downloads"
