"""Leer los manifiestos de un pack publicado sin descargarlo entero.

Es lo que hace viable emparejar lo instalado con lo publicado. Ningún catálogo
expone el `header.uuid` —vive dentro del zip— pero los CDN que sirven los packs
aceptan `Range`, así que se puede leer solo lo necesario.

Un zip se lee desde el final, donde está su directorio central, así que hacen
falta unas pocas lecturas pequeñas y salteadas. `zipfile` las hace de a trocitos
—ocho bytes por aquí, cuarenta por allá— y sobre HTTP cada trocito es una
petición entera: por eso las lecturas se agrupan en bloques.
"""

from __future__ import annotations

import io
import zipfile

from .manifiesto import Manifiesto, ManifiestoInvalido, desde_zip
from .red import AGENTE, ErrorRed, pedir

#: Por encima de esto no se intenta: un pack de Bedrock no ocupa tanto.
_MAX_BYTES = 512 * 1024 * 1024

#: Cuánto se trae de una vez. Sobre HTTP manda la latencia, no los bytes: pedir
#: 32 KB cuesta lo mismo que pedir 40, y cubre de sobra el directorio central de
#: un pack normal y la cabecera del `manifest.json`.
_BLOQUE = 32 * 1024

#: Un `.mcaddon` trae sus packs dentro como archivos completos, y para leer sus
#: manifiestos hay que traérselos enteros. Por encima de esto no compensa.
_MAX_ANIDADO = 3 * 1024 * 1024

_MAX_ANIDADOS_POR_ARCHIVO = 3

_EXTENSIONES_ANIDADAS = (".mcpack", ".mcworld", ".mctemplate")


class ArchivoRemoto(io.RawIOBase):
    """Un archivo HTTP que se recorre como si fuera local, leyendo por bloques."""

    def __init__(self, url: str) -> None:
        cabecera = pedir(url, metodo="HEAD")
        if cabecera.codigo >= 400:
            raise ErrorRed(f"el servidor respondió {cabecera.codigo}")
        if cabecera.cabeceras.get("accept-ranges") != "bytes":
            raise ErrorRed("el servidor no admite descargas parciales")

        self._url = cabecera.url_final
        self.size = int(cabecera.cabeceras.get("content-length") or 0)
        if not 0 < self.size <= _MAX_BYTES:
            raise ErrorRed(f"tamaño no utilizable: {self.size} bytes")

        self._pos = 0
        self._bloques: dict[int, bytes] = {}
        self.peticiones = 0
        self.bytes_leidos = 0

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._pos

    def seek(self, desplazamiento: int, desde: int = io.SEEK_SET) -> int:
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self._pos, io.SEEK_END: self.size}[desde]
        self._pos = max(0, min(base + desplazamiento, self.size))
        return self._pos

    def read(self, cuantos: int = -1) -> bytes:
        if cuantos < 0:
            cuantos = self.size - self._pos
        if cuantos <= 0 or self._pos >= self.size:
            return b""

        fin = min(self._pos + cuantos, self.size)
        trozos = []
        posicion = self._pos
        while posicion < fin:
            indice = posicion // _BLOQUE
            bloque = self._bloque(indice)
            dentro = posicion - indice * _BLOQUE
            trozo = bloque[dentro:dentro + (fin - posicion)]
            if not trozo:
                break
            trozos.append(trozo)
            posicion += len(trozo)

        self._pos = posicion
        return b"".join(trozos)

    def _bloque(self, indice: int) -> bytes:
        if indice not in self._bloques:
            inicio = indice * _BLOQUE
            final = min(inicio + _BLOQUE, self.size) - 1
            respuesta = pedir(self._url, cabeceras={"Range": f"bytes={inicio}-{final}"})
            if respuesta.codigo not in (200, 206):
                raise ErrorRed(f"el servidor respondió {respuesta.codigo} a un Range")
            self._bloques[indice] = respuesta.cuerpo
            self.peticiones += 1
            self.bytes_leidos += len(respuesta.cuerpo)
        return self._bloques[indice]


def _manifiestos_de(zf: zipfile.ZipFile, con_anidados: bool) -> list[Manifiesto]:
    encontrados = []

    for nombre in zf.namelist():
        if nombre.rsplit("/", 1)[-1] == "manifest.json" and nombre.count("/") <= 1:
            try:
                manifiesto = desde_zip(zf, nombre)
            except (ManifiestoInvalido, KeyError, OSError, ValueError):
                continue
            if manifiesto.es_bedrock:
                encontrados.append(manifiesto)

    if not con_anidados:
        return encontrados

    # Un `.mcaddon` no tiene manifiesto propio: lo que identifica su contenido
    # son los de los packs que lleva dentro. Sin mirarlos, un addon publicado no
    # se puede emparejar con nada — y muchos packs se distribuyen así.
    anidados = [
        i for i in zf.infolist()
        if i.filename.lower().endswith(_EXTENSIONES_ANIDADAS) and i.file_size <= _MAX_ANIDADO
    ]
    # Cada anidado se trae entero; un addon con muchos no compensa sondearlo.
    for info in anidados[:_MAX_ANIDADOS_POR_ARCHIVO]:
        try:
            with zf.open(info) as f, zipfile.ZipFile(io.BytesIO(f.read())) as anidado:
                encontrados.extend(_manifiestos_de(anidado, con_anidados=False))
        except (zipfile.BadZipFile, OSError, ValueError, ErrorRed):
            continue

    return encontrados


def leer_manifiestos(url: str) -> list[Manifiesto]:
    """Todos los manifiestos de Bedrock que hay en el archivo publicado en `url`.

    Vacío significa «no se pudo leer», no «no es un pack»: engloba tanto que el
    archivo sea otra cosa como que el servidor no admita `Range` o se caiga. Se
    usa para confirmar candidatos, y ahí solo cuenta el positivo — una lista
    vacía nunca puede producir un emparejamiento equivocado.
    """
    try:
        with zipfile.ZipFile(ArchivoRemoto(url)) as zf:
            return _manifiestos_de(zf, con_anidados=True)
    except (zipfile.BadZipFile, ManifiestoInvalido, KeyError, ValueError, ErrorRed, OSError):
        return []


def leer_manifiesto(url: str) -> Manifiesto | None:
    """El primer manifiesto del archivo, o `None`."""
    encontrados = leer_manifiestos(url)
    return encontrados[0] if encontrados else None


__all__ = ["AGENTE", "ArchivoRemoto", "ErrorRed", "leer_manifiesto", "leer_manifiestos"]
