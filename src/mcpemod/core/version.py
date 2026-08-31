"""Comparación de versiones de packs.

Las versiones salen del `header.version` del manifiesto, no del nombre del
archivo: el nombre lo pone quien renombra la descarga y el manifiesto quien
empaquetó el pack.
"""

from __future__ import annotations

from enum import Enum

from packaging.version import InvalidVersion, Version


class EstadoVersion(Enum):
    IGUAL = "igual"
    NUEVA = "nueva"
    ANTERIOR = "anterior"
    DESCONOCIDA = "desconocida"


def _parsear(version: str) -> Version | None:
    """`Version` tolerando los separadores que usan los empaquetadores de mods.

    `packaging` rechaza `2.0.0_beta` pero acepta `2.0.0-beta`. El sufijo
    pre-release es información real de orden y tirarla haría que dos betas
    consecutivas se leyeran como la misma versión.
    """
    for candidata in (version, version.replace("_", "-")):
        try:
            return Version(candidata)
        except InvalidVersion:
            continue
    return None


def comparar(instalada: str | None, candidata: str | None) -> EstadoVersion:
    """Qué es `candidata` respecto de `instalada`."""
    if instalada is None or candidata is None:
        return EstadoVersion.DESCONOCIDA

    va, vb = _parsear(instalada), _parsear(candidata)
    if va is None or vb is None:
        return EstadoVersion.IGUAL if instalada == candidata else EstadoVersion.DESCONOCIDA
    if va == vb:
        return EstadoVersion.IGUAL
    return EstadoVersion.NUEVA if vb > va else EstadoVersion.ANTERIOR
