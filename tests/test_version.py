"""Pruebas de comparación de versiones.

`comparar()` decide qué badge muestra la tarjeta de una descarga: ↑ actualización,
↓ anterior o ✓ instalado. Las versiones salen del `header.version` del
manifiesto, nunca del nombre del archivo.
"""

from mcpemod.core.version import EstadoVersion, comparar


def test_igual():
    assert comparar("1.0.0", "1.0.0") == EstadoVersion.IGUAL

def test_mas_nueva():
    assert comparar("1.0.0", "2.0.0") == EstadoVersion.NUEVA

def test_mas_vieja():
    assert comparar("2.0.0", "1.0.0") == EstadoVersion.ANTERIOR

def test_patch():
    assert comparar("1.0.0", "1.0.1") == EstadoVersion.NUEVA
    assert comparar("1.0.1", "1.0.0") == EstadoVersion.ANTERIOR

def test_longitudes_distintas():
    # `header.version` puede venir con dos componentes o con cuatro.
    assert comparar("1.2", "1.2.0") == EstadoVersion.IGUAL
    assert comparar("1.2", "1.2.1") == EstadoVersion.NUEVA

def test_sin_version_a_un_lado():
    assert comparar(None, "1.0.0") == EstadoVersion.DESCONOCIDA
    assert comparar("1.0.0", None) == EstadoVersion.DESCONOCIDA
    assert comparar(None, None) == EstadoVersion.DESCONOCIDA

def test_prerelease_con_guion_bajo():
    """`packaging` rechaza `2.0.0_beta`; normalizarlo a `-beta` lo hace comparable."""
    assert comparar("2.0.0_beta", "2.0.0") == EstadoVersion.NUEVA
    assert comparar("2.0.0_alpha", "2.0.0_beta") == EstadoVersion.NUEVA
    assert comparar("2.0.0_beta", "2.0.0_beta") == EstadoVersion.IGUAL

def test_versiones_no_comparables():
    assert comparar("nightly", "nightly") == EstadoVersion.IGUAL
    assert comparar("nightly", "stable") == EstadoVersion.DESCONOCIDA
