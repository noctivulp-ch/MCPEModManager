"""Cliente de CurseForge.

La API oficial exige una clave: sin ella devuelve `403 Forbidden: API Key missing
or invalid`. Se consigue gratis en `console.curseforge.com`, y hasta que se pegue
en los ajustes esta fuente se declara no disponible y la app no la ofrece.

No es urgente tenerla: MCPEDL ya sirve el catálogo de Bedrock de CurseForge, con
descarga directa desde el mismo CDN. Esto añade el catálogo completo y sus
filtros propios.
"""

from __future__ import annotations

from datetime import datetime

from ..red import ErrorRed, con_parametros, pedir
from .base import Descarga, Publicacion

_API = "https://api.curseforge.com/v1"
#: Minecraft Bedrock en la nomenclatura de CurseForge.
_ID_JUEGO = 432
_ID_CLASE_ADDONS = 4471

NOMBRE = "curseforge"
URL_CONSOLA = "https://console.curseforge.com"


class CurseForge:
    nombre = NOMBRE
    etiqueta = "CurseForge"

    def __init__(self, clave: str | None = None) -> None:
        self._clave = (clave or "").strip()

    @property
    def disponible(self) -> bool:
        return bool(self._clave)

    def buscar(self, texto: str, pagina: int = 1, por_pagina: int = 20) -> list[Publicacion]:
        return self._consultar({
            "gameId": _ID_JUEGO,
            "classId": _ID_CLASE_ADDONS,
            "searchFilter": texto,
            "index": (pagina - 1) * por_pagina,
            "pageSize": por_pagina,
        })

    def recientes(self, pagina: int = 1, por_pagina: int = 20) -> list[Publicacion]:
        return self._consultar({
            "gameId": _ID_JUEGO,
            "classId": _ID_CLASE_ADDONS,
            "sortField": 3,          # última actualización
            "sortOrder": "desc",
            "index": (pagina - 1) * por_pagina,
            "pageSize": por_pagina,
        })

    def _consultar(self, parametros: dict) -> list[Publicacion]:
        if not self.disponible:
            raise ErrorRed("falta la clave de la API de CurseForge")

        respuesta = pedir(
            con_parametros(f"{_API}/mods/search", parametros),
            cabeceras={"x-api-key": self._clave, "Accept": "application/json"},
        )
        if respuesta.codigo == 403:
            raise ErrorRed("CurseForge rechazó la clave")
        if respuesta.codigo != 200:
            raise ErrorRed(f"CurseForge respondió {respuesta.codigo}")
        return [_a_publicacion(x) for x in respuesta.json().get("data") or []]


def _fecha(texto) -> datetime | None:
    if not isinstance(texto, str) or not texto:
        return None
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _a_publicacion(x: dict) -> Publicacion:
    descargas = tuple(
        Descarga(
            nombre=a.get("displayName") or a.get("fileName") or "",
            url=a.get("downloadUrl") or "",
            tamano=int(a.get("fileLength") or 0),
            fecha=_fecha(a.get("fileDate")),
        )
        for a in (x.get("latestFiles") or [])
        if a.get("downloadUrl")
    )
    autores = x.get("authors") or []
    return Publicacion(
        fuente=NOMBRE,
        id=str(x.get("id") or ""),
        titulo=x.get("name") or "",
        autor=autores[0].get("name", "") if autores else "",
        url=(x.get("links") or {}).get("websiteUrl") or "",
        descargas=descargas,
        resumen=x.get("summary") or "",
        imagen=(x.get("logo") or {}).get("thumbnailUrl"),
        descargas_totales=int(x.get("downloadCount") or 0),
        actualizado=_fecha(x.get("dateModified")),
        categorias=tuple(
            c.get("name", "") for c in (x.get("categories") or []) if isinstance(c, dict)
        ),
    )
