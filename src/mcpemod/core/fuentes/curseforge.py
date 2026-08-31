"""Cliente de CurseForge.

La API oficial exige una clave: sin ella devuelve `403 Forbidden: API Key missing
or invalid`. Se consigue gratis en `console.curseforge.com`, y hasta que se pegue
en los ajustes esta fuente se declara no disponible y la app no la ofrece.

**CurseForge sirve las dos plataformas.** Minecraft Java y Minecraft Bedrock son
juegos distintos en su catálogo —se ve en las URLs, `/minecraft` frente a
`/minecraft-bedrock`— y pedir el juego equivocado devolvería mods de Java, que no
tienen nada que hacer aquí. Por eso el identificador del juego **no está escrito
en el código**: se pregunta por su slug al arrancar la primera consulta. Un
número fijo es un número que se puede equivocar hoy y quedarse obsoleto mañana.

Como segunda red, se descartan las publicaciones que no ofrecen ningún archivo
con extensión de Bedrock: un mod de Java se distribuye en `.jar`.
"""

from __future__ import annotations

from datetime import datetime

from ..red import ErrorRed, con_parametros, pedir
from .base import Descarga, Publicacion

_API = "https://api.curseforge.com/v1"

#: Cómo se llama Minecraft Bedrock en el catálogo. Es lo estable: los
#: identificadores numéricos son un detalle de su base de datos.
SLUG_BEDROCK = "minecraft-bedrock"

#: Lo que puede ser contenido de Bedrock. Un `.jar` es de Java y se descarta.
_EXTENSIONES = (".mcpack", ".mcaddon", ".mcworld", ".mctemplate", ".zip")

NOMBRE = "curseforge"
URL_CONSOLA = "https://console.curseforge.com"

#: El identificador del juego no cambia entre consultas ni depende de la clave,
#: así que se pregunta una vez por ejecución.
_id_juego_cache: int | None = None


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
            "searchFilter": texto,
            "index": (pagina - 1) * por_pagina,
            "pageSize": por_pagina,
        })

    def recientes(self, pagina: int = 1, por_pagina: int = 20) -> list[Publicacion]:
        return self._consultar({
            "sortField": 3,          # última actualización
            "sortOrder": "desc",
            "index": (pagina - 1) * por_pagina,
            "pageSize": por_pagina,
        })

    # ── Interno ───────────────────────────────────────────────────────────────

    def _cabeceras(self) -> dict[str, str]:
        return {"x-api-key": self._clave, "Accept": "application/json"}

    def _pedir(self, url: str):
        respuesta = pedir(url, cabeceras=self._cabeceras())
        if respuesta.codigo == 403:
            raise ErrorRed("CurseForge rechazó la clave")
        if respuesta.codigo != 200:
            raise ErrorRed(f"CurseForge respondió {respuesta.codigo}")
        return respuesta.json()

    def id_juego(self) -> int:
        """El identificador de Minecraft Bedrock, preguntado por su slug.

        Se busca en la lista de juegos en vez de fijarlo: es lo que garantiza que
        no se pidan por error los mods de Java, que viven bajo otro juego del
        mismo catálogo.
        """
        global _id_juego_cache
        if _id_juego_cache is not None:
            return _id_juego_cache

        datos = self._pedir(f"{_API}/games?pageSize=100")
        for juego in datos.get("data") or []:
            if str(juego.get("slug", "")).lower() == SLUG_BEDROCK:
                _id_juego_cache = int(juego["id"])
                return _id_juego_cache

        raise ErrorRed(
            f"CurseForge no lista ningún juego con el slug «{SLUG_BEDROCK}»; "
            "sin él no se puede distinguir Bedrock de Java"
        )

    def _consultar(self, parametros: dict) -> list[Publicacion]:
        if not self.disponible:
            raise ErrorRed("falta la clave de la API de CurseForge")

        datos = self._pedir(con_parametros(
            f"{_API}/mods/search", {"gameId": self.id_juego(), **parametros}
        ))
        publicaciones = (_a_publicacion(x) for x in datos.get("data") or [])
        return [p for p in publicaciones if es_de_bedrock(p)]


def es_de_bedrock(publicacion: Publicacion) -> bool:
    """Segunda red por si el catálogo devolviera contenido de otra plataforma.

    Una publicación sin archivos no se puede descartar por aquí, y tampoco sirve
    de nada instalarla; se deja pasar para que la trate quien corresponda.
    """
    if not publicacion.descargas:
        return True
    return any(
        d.nombre.lower().endswith(_EXTENSIONES) or d.url.lower().endswith(_EXTENSIONES)
        for d in publicacion.descargas
    )


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
            nombre=a.get("fileName") or a.get("displayName") or "",
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
