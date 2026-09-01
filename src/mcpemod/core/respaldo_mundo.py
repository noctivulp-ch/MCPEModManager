"""Copia de seguridad de un mundo, antes de tocarlo.

Un mundo es lo único de aquí que no se puede volver a descargar. Un pack se baja
otra vez; una partida de meses, no. Por eso **ningún cambio en un mundo se hace
sin respaldarlo antes**, y si el respaldo falla el cambio no se hace: es la
diferencia entre una app que gestiona y una que arriesga.

Se guarda **uno por mundo**, no una pila que crezca sola: son cientos de megas
cada uno. Sustituir el anterior es una pérdida real, así que quien llame tiene
que saber qué había —`existente()`— y avisar antes.

Viven en `Instalacion.respaldos_de_mundos`, dentro de `com.mojang` para que
acompañen a la instalación si se mueve, y **fuera de `minecraftWorlds`** porque
ahí dentro se verían como mundos más.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

#: Sin esto un mundo no es un mundo, y un respaldo que no lo tenga no sirve.
_IMPRESCINDIBLE = "level.dat"


class ErrorRespaldo(Exception):
    pass


@dataclass(frozen=True)
class Respaldo:
    mundo: str
    nombre: str
    ruta: Path
    fecha: datetime
    bytes: int

    @property
    def descripcion(self) -> str:
        return (f"{self.nombre} · {self.fecha:%d/%m/%Y %H:%M} · "
                f"{self.bytes / 1024 / 1024:.0f} MB")


def _archivo_de(carpeta_mundo: Path, carpeta_respaldos: Path) -> Path:
    # El nombre de carpeta del mundo es su identidad en disco y ya viene
    # codificado por el juego; se usa tal cual para que haya uno por mundo.
    seguro = carpeta_mundo.name.replace("/", "_")
    return carpeta_respaldos / f"{seguro}.tar.zst"


def existente(carpeta_mundo: Path, carpeta_respaldos: Path) -> Respaldo | None:
    """El respaldo que ya hay de este mundo, si lo hay."""
    archivo = _archivo_de(carpeta_mundo, carpeta_respaldos)
    if not archivo.is_file():
        return None
    info = archivo.stat()
    return Respaldo(
        mundo=carpeta_mundo.name,
        nombre=_nombre_del_mundo(carpeta_mundo),
        ruta=archivo,
        fecha=datetime.fromtimestamp(info.st_mtime),
        bytes=info.st_size,
    )


def _nombre_del_mundo(carpeta: Path) -> str:
    etiqueta = carpeta / "levelname.txt"
    if etiqueta.is_file():
        leido = etiqueta.read_text(encoding="utf-8", errors="replace").strip()
        if leido:
            return leido
    return carpeta.name


def guardar(carpeta_mundo: Path, carpeta_respaldos: Path) -> Respaldo:
    """Respalda el mundo, **sustituyendo** el respaldo anterior si lo había.

    El anterior no se borra hasta que el nuevo está escrito y comprobado: si algo
    falla a mitad, lo que había sigue estando.
    """
    if not (carpeta_mundo / _IMPRESCINDIBLE).is_file():
        raise ErrorRespaldo(f"{carpeta_mundo.name} no parece un mundo: falta {_IMPRESCINDIBLE}")

    carpeta_respaldos.mkdir(parents=True, exist_ok=True)
    destino = _archivo_de(carpeta_mundo, carpeta_respaldos)

    with tempfile.TemporaryDirectory(dir=carpeta_respaldos) as tmp:
        provisional = Path(tmp) / "nuevo.tar.zst"
        _comprimir(carpeta_mundo, provisional)
        _comprobar(provisional)
        # `replace` es atómico dentro del mismo sistema de archivos: o está el
        # nuevo entero o sigue el viejo, nunca un archivo a medias.
        provisional.replace(destino)

    return existente(carpeta_mundo, carpeta_respaldos)


def restaurar(carpeta_mundo: Path, carpeta_respaldos: Path) -> None:
    """Devuelve el mundo al estado del respaldo, reemplazando lo que haya."""
    archivo = _archivo_de(carpeta_mundo, carpeta_respaldos)
    if not archivo.is_file():
        raise ErrorRespaldo(f"No hay respaldo de {carpeta_mundo.name}")
    _comprobar(archivo)

    padre = carpeta_mundo.parent
    with tempfile.TemporaryDirectory(dir=padre) as tmp:
        # Se extrae al lado y se intercambia: si la extracción falla a mitad, el
        # mundo que hay sigue intacto.
        _extraer(archivo, Path(tmp))
        extraido = Path(tmp) / carpeta_mundo.name
        if not (extraido / _IMPRESCINDIBLE).is_file():
            raise ErrorRespaldo("el respaldo no contiene un mundo utilizable")

        retirado = Path(tmp) / "anterior"
        if carpeta_mundo.exists():
            carpeta_mundo.rename(retirado)
        try:
            extraido.rename(carpeta_mundo)
        except OSError:
            if retirado.exists():
                retirado.rename(carpeta_mundo)
            raise


def _orden_tar() -> list[str]:
    return ["tar", "--zstd" if shutil.which("zstd") else "-z"]


def _comprimir(carpeta_mundo: Path, destino: Path) -> None:
    orden = [*_orden_tar(), "-cf", str(destino),
             "-C", str(carpeta_mundo.parent), carpeta_mundo.name]
    _ejecutar(orden, "no se pudo comprimir el mundo")


def _extraer(archivo: Path, destino: Path) -> None:
    _ejecutar([*_orden_tar(), "-xf", str(archivo), "-C", str(destino)],
              "no se pudo extraer el respaldo")


def _comprobar(archivo: Path) -> None:
    """Que el archivo se pueda leer y traiga un mundo dentro.

    Un `tar` que no da error no basta: el respaldo tiene que servir para
    restaurar, y eso se comprueba mirándolo, no suponiéndolo.
    """
    resultado = subprocess.run(
        [*_orden_tar(), "-tf", str(archivo)],
        capture_output=True, text=True, check=False,
    )
    if resultado.returncode != 0:
        raise ErrorRespaldo(f"el respaldo no se puede leer: {resultado.stderr.strip()[:120]}")
    if not any(l.rstrip("/").endswith(_IMPRESCINDIBLE) for l in resultado.stdout.splitlines()):
        raise ErrorRespaldo(f"el respaldo no contiene {_IMPRESCINDIBLE}")


def _ejecutar(orden: list[str], fallo: str) -> None:
    resultado = subprocess.run(orden, capture_output=True, text=True, check=False)
    if resultado.returncode != 0:
        raise ErrorRespaldo(f"{fallo}: {resultado.stderr.strip()[:160]}")
