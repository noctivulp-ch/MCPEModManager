"""Pruebas de detección, normalización y comparación de versiones.

`comparar()` y `detectar_version()` determinan qué badge muestra la UI
(↑ actualización, ↓ anterior, ✓ instalado). Un error aquí produce indicadores
incorrectos — el usuario vería "actualización" para un archivo más viejo.

`nombre_canonico()` es la clave con la que se rastrea un mod entre versiones:
si `MyMod-v1.2.3` y `MyMod-v1.3.0` no colapsan al mismo nombre, actualizar
instala el nuevo dejando el viejo activo al lado.
"""

import io
import json
import zipfile

from mcpemod.core.mod import EstadoVersion
from mcpemod.core.version import comparar, detectar_version, nombre_canonico


def _zip_con_manifest(destino, manifest):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
    destino.write_bytes(buf.getvalue())
    return destino


# --- comparar ---

def test_comparar_igual():
    assert comparar("1.0.0", "1.0.0") == EstadoVersion.IGUAL

def test_comparar_version_nueva():
    assert comparar("1.0.0", "2.0.0") == EstadoVersion.NUEVA

def test_comparar_version_anterior():
    assert comparar("2.0.0", "1.0.0") == EstadoVersion.ANTERIOR

def test_comparar_none_izquierda():
    assert comparar(None, "1.0.0") == EstadoVersion.DESCONOCIDA

def test_comparar_none_derecha():
    assert comparar("1.0.0", None) == EstadoVersion.DESCONOCIDA

def test_comparar_ambos_none():
    assert comparar(None, None) == EstadoVersion.DESCONOCIDA

def test_comparar_version_invalida_igual():
    assert comparar("nightly", "nightly") == EstadoVersion.IGUAL

def test_comparar_version_invalida_distinta():
    assert comparar("nightly", "stable") == EstadoVersion.DESCONOCIDA

def test_comparar_semver_patch():
    assert comparar("1.0.0", "1.0.1") == EstadoVersion.NUEVA
    assert comparar("1.0.1", "1.0.0") == EstadoVersion.ANTERIOR

def test_comparar_prerelease_con_guion_bajo():
    # `packaging` rechaza "2.0.0_beta"; normalizarlo a "-beta" lo hace comparable.
    assert comparar("2.0.0_beta", "2.0.0") == EstadoVersion.NUEVA
    assert comparar("2.0.0_alpha", "2.0.0_beta") == EstadoVersion.NUEVA

def test_comparar_prerelease_igual():
    assert comparar("2.0.0_beta", "2.0.0_beta") == EstadoVersion.IGUAL


# --- detectar_version ---

def test_detectar_version_desde_nombre(tmp_path):
    archivo = tmp_path / "MyMod-v1.2.3.so"
    archivo.touch()
    assert detectar_version(archivo) == "1.2.3"

def test_detectar_version_con_prerelease(tmp_path):
    archivo = tmp_path / "mod_2.0.0_beta.mcpack"
    archivo.touch()
    assert detectar_version(archivo) == "2.0.0_beta"

def test_detectar_version_sin_version(tmp_path):
    archivo = tmp_path / "random_mod.so"
    archivo.touch()
    assert detectar_version(archivo) is None

def test_detectar_version_desde_manifest(tmp_path):
    archivo = _zip_con_manifest(tmp_path / "pack.mcpack", {"header": {"version": [1, 5, 0]}})
    assert detectar_version(archivo) == "1.5.0"

def test_detectar_version_manifest_string(tmp_path):
    archivo = _zip_con_manifest(tmp_path / "pack.mcpack", {"header": {"version": "3.0.0"}})
    assert detectar_version(archivo) == "3.0.0"

def test_manifest_gana_al_nombre(tmp_path):
    # El nombre lo pone quien renombra el archivo; el manifest, quien lo empaquetó.
    archivo = _zip_con_manifest(tmp_path / "pack-v9.9.9.mcpack", {"header": {"version": [1, 0, 0]}})
    assert detectar_version(archivo) == "1.0.0"

def test_detectar_version_zip_corrupto(tmp_path):
    archivo = tmp_path / "bad.mcpack"
    archivo.write_bytes(b"not a zip")
    assert detectar_version(archivo) is None


# --- nombre_canonico ---

def test_canonico_quita_version_con_v():
    assert nombre_canonico("MyMod-v1.2.3") == "MyMod"

def test_canonico_quita_version_sin_v():
    assert nombre_canonico("MyMod_2.0.0") == "MyMod"

def test_canonico_quita_prerelease():
    assert nombre_canonico("mod_2.0.0_beta") == "mod"

def test_canonico_sin_version_devuelve_el_nombre():
    assert nombre_canonico("libToolbox64") == "libToolbox64"

def test_canonico_colapsa_dos_versiones_del_mismo_mod():
    assert nombre_canonico("MyMod-v1.2.3") == nombre_canonico("MyMod-v1.3.0")
