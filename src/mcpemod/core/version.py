"""Detección, normalización y comparación de versiones."""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

from packaging.version import InvalidVersion, Version

from .mod import EstadoVersion

_PATRON_VERSION = re.compile(r"v?(\d+\.\d+(?:\.\d+)*(?:[-_.][A-Za-z]\w*)?)", re.IGNORECASE)
_COLA_SEPARADORES = re.compile(r"[\s._\-]+$")


def detectar_version(ruta: Path) -> str | None:
    if ruta.suffix.lower() in (".mcpack", ".mcaddon", ".zip"):
        version = _desde_manifest(ruta)
        if version:
            return version

    match = _PATRON_VERSION.search(ruta.stem)
    return match.group(1) if match else None


def nombre_canonico(stem: str) -> str:
    """El nombre del mod sin su versión — la clave con la que se rastrea.

    `MyMod-v1.2.3` y `MyMod-v1.3.0` son el mismo mod en dos versiones. Sin esto
    el gestor los trataría como dos mods distintos y "actualizar" instalaría el
    nuevo dejando el viejo activo al lado.
    """
    base = _PATRON_VERSION.sub("", stem)
    base = _COLA_SEPARADORES.sub("", base).strip()
    return base or stem


def _desde_manifest(ruta: Path) -> str | None:
    try:
        with zipfile.ZipFile(ruta) as zf:
            for nombre in zf.namelist():
                if nombre.endswith("manifest.json") and nombre.count("/") <= 1:
                    with zf.open(nombre) as f:
                        datos = json.load(f)
                    v = datos.get("header", {}).get("version")
                    if isinstance(v, list):
                        return ".".join(str(x) for x in v)
                    if isinstance(v, str):
                        return v
    except (zipfile.BadZipFile, OSError, json.JSONDecodeError, UnicodeDecodeError):
        pass
    return None


def _parsear(version: str) -> Version | None:
    """`Version` tolerando los separadores que usan los empaquetadores de mods.

    `packaging` rechaza `2.0.0_beta`, pero acepta `2.0.0-beta`. El sufijo
    pre-release es información real de orden y tirarla haría que dos betas
    consecutivas se leyeran como la misma versión.
    """
    for candidata in (version, version.replace("_", "-")):
        try:
            return Version(candidata)
        except InvalidVersion:
            continue
    return None


def comparar(version_a: str | None, version_b: str | None) -> EstadoVersion:
    """Qué es `version_b` respecto de `version_a`."""
    if version_a is None or version_b is None:
        return EstadoVersion.DESCONOCIDA

    va, vb = _parsear(version_a), _parsear(version_b)
    if va is None or vb is None:
        return EstadoVersion.IGUAL if version_a == version_b else EstadoVersion.DESCONOCIDA

    if va == vb:
        return EstadoVersion.IGUAL
    return EstadoVersion.NUEVA if vb > va else EstadoVersion.ANTERIOR
