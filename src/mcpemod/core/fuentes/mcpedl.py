"""Cliente de MCPEDL.

API pública, sin autenticación. El parámetro de búsqueda es `s`: `search`, `q` y
`query` se aceptan sin error y se **ignoran**, devolviendo lo último publicado —
una trampa silenciosa que cuesta ver, porque la respuesta parece correcta.

MCPEDL agrega contenido de CurseForge además del propio: en una muestra de 50
publicaciones, las 50 traían `source: "curseforge"` con descarga desde
`forgecdn.net`.
"""

from __future__ import annotations

from datetime import datetime

from ..red import ErrorRed, con_parametros, pedir
from .base import Descarga, Publicacion

_API = "https://api.mcpedl.com/api/submissions"
NOMBRE = "mcpedl"


class MCPEDL:
    nombre = NOMBRE
    etiqueta = "MCPEDL"

    @property
    def disponible(self) -> bool:
        return True

    def buscar(self, texto: str, pagina: int = 1, por_pagina: int = 20) -> list[Publicacion]:
        return self._consultar({"s": texto, "page": pagina, "per_page": por_pagina})

    def recientes(self, pagina: int = 1, por_pagina: int = 20) -> list[Publicacion]:
        return self._consultar({"page": pagina, "per_page": por_pagina})

    def _consultar(self, parametros: dict) -> list[Publicacion]:
        respuesta = pedir(con_parametros(_API, parametros))
        if respuesta.codigo != 200:
            raise ErrorRed(f"MCPEDL respondió {respuesta.codigo}")
        datos = respuesta.json()
        return [_a_publicacion(x) for x in datos.get("data") or []]


def _fecha(texto) -> datetime | None:
    if not isinstance(texto, str) or not texto:
        return None
    limpio = texto.replace("Z", "+00:00").replace(" ", "T", 1)
    try:
        return datetime.fromisoformat(limpio).replace(tzinfo=None)
    except ValueError:
        return None


def _a_publicacion(x: dict) -> Publicacion:
    descargas = tuple(
        Descarga(
            nombre=d.get("name") or d.get("filename") or "",
            url=d.get("downloadUrl") or "",
            tamano=int(d.get("fileLength") or 0),
            fecha=_fecha(d.get("fileDate")),
        )
        for d in (x.get("downloads") or [])
        if d.get("downloadUrl")
    )
    return Publicacion(
        fuente=NOMBRE,
        id=str(x.get("submission_id") or x.get("id") or ""),
        titulo=x.get("title") or "",
        autor=x.get("display_name") or x.get("username") or "",
        url=x.get("url") or "",
        descargas=descargas,
        resumen=x.get("short_description") or x.get("summary") or "",
        imagen=(x.get("thumbnails") or {}).get("medium") or x.get("image"),
        descargas_totales=int(x.get("downloadCount") or 0),
        actualizado=_fecha(x.get("update_date") or x.get("sort_date")),
        categorias=tuple(
            c.get("name", "") for c in (x.get("categories") or []) if isinstance(c, dict)
        ),
    )
