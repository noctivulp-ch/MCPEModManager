from .base import Descarga, Fuente, Publicacion
from .curseforge import URL_CONSOLA, CurseForge
from .mcpedl import MCPEDL

__all__ = ["URL_CONSOLA", "CurseForge", "Descarga", "Fuente", "MCPEDL", "Publicacion"]


def fuentes_disponibles(clave_curseforge: str | None = None) -> list[Fuente]:
    """Las fuentes que se pueden consultar ahora mismo, en orden de preferencia."""
    return [f for f in (MCPEDL(), CurseForge(clave_curseforge)) if f.disponible]
