"""Acceso HTTP: lo mínimo, con las cortesías que se le deben a un servicio ajeno.

Se usa `urllib` y no `requests` a propósito: es una dependencia menos que Nuitka
tiene que empaquetar, y lo que hace falta aquí son peticiones GET con cabeceras.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

__version_app__ = "0.1"

#: Identifica la app ante el servicio. Un agente genérico es lo que hace que un
#: servicio bloquee a todo el mundo cuando uno abusa.
AGENTE = f"mcpemod/{__version_app__} (+gestor local de packs de Bedrock)"

TIMEOUT = 20

#: Pausa mínima entre peticiones a un mismo servicio. No lo pide nadie: evita
#: que una comprobación de sesenta packs parezca un ataque.
#:
#: El reparto es acumulativo entre hilos, así que este número fija el techo de
#: peticiones por segundo del barrido entero, no de cada hilo. Con un valor alto
#: la comprobación en paralelo deja de servir de nada, porque los hilos acaban
#: haciendo cola sobre el mismo dominio.
PAUSA = 0.08

_ultima_peticion: dict[str, float] = {}
_turno = threading.Lock()


class ErrorRed(Exception):
    pass


@dataclass(frozen=True)
class Respuesta:
    codigo: int
    cuerpo: bytes
    cabeceras: dict[str, str]
    url_final: str

    def json(self):
        try:
            return json.loads(self.cuerpo.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as e:
            raise ErrorRed(f"la respuesta no es JSON: {e}") from e


def _esperar_turno(url: str) -> None:
    """Espacia las peticiones a un mismo servicio, también entre hilos.

    La comprobación de actualizaciones consulta varios packs a la vez; sin este
    reparto, tres hilos golpean el mismo servicio a la vez y la cortesía que
    intenta el retardo deja de existir.
    """
    dominio = urllib.parse.urlparse(url).netloc
    with _turno:
        ahora = time.monotonic()
        proximo = max(ahora, _ultima_peticion.get(dominio, 0.0) + PAUSA)
        _ultima_peticion[dominio] = proximo
        espera = proximo - ahora
    if espera > 0:
        time.sleep(espera)


def pedir(
    url: str,
    *,
    cabeceras: dict[str, str] | None = None,
    metodo: str = "GET",
    timeout: int = TIMEOUT,
) -> Respuesta:
    _esperar_turno(url)
    peticion = urllib.request.Request(
        url, method=metodo, headers={"User-Agent": AGENTE, **(cabeceras or {})}
    )
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as r:
            return Respuesta(
                codigo=r.status,
                cuerpo=r.read() if metodo != "HEAD" else b"",
                cabeceras={k.lower(): v for k, v in r.headers.items()},
                url_final=r.url,
            )
    except urllib.error.HTTPError as e:
        # Un 4xx es información, no un fallo de red: quien llama decide si un
        # 403 significa "falta la clave" o "este pack ya no existe".
        return Respuesta(
            codigo=e.code,
            cuerpo=e.read(),
            cabeceras={k.lower(): v for k, v in (e.headers or {}).items()},
            url_final=e.url or url,
        )
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise ErrorRed(f"no se pudo conectar con {urllib.parse.urlparse(url).netloc}: {e}") from e


def con_parametros(base: str, parametros: dict) -> str:
    limpios = {k: v for k, v in parametros.items() if v is not None}
    return f"{base}?{urllib.parse.urlencode(limpios)}"


def descargar(url: str, destino, progreso=None) -> int:
    """Descarga `url` a un archivo abierto en binario. Devuelve los bytes escritos.

    `progreso(bytes, total)` se llama cada bloque; `total` es 0 si el servidor no
    dice cuánto ocupa.
    """
    _esperar_turno(url)
    peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    escritos = 0
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT) as r:
            total = int(r.headers.get("Content-Length") or 0)
            while bloque := r.read(65536):
                destino.write(bloque)
                escritos += len(bloque)
                if progreso is not None:
                    progreso(escritos, total)
    except (urllib.error.URLError, OSError) as e:
        raise ErrorRed(f"falló la descarga: {e}") from e
    return escritos
