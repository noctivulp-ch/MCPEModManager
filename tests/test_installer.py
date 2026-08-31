"""Pruebas del Installer — la única capa que borra y escribe en el sistema real.

Todos los fallos que puede tener aquí son destructivos o silenciosos:
desinstalar algo que no era, dejar dos versiones del mismo mod cargando a la vez,
o extraer un zip por encima de archivos que no le pertenecen. Los tests
redirigen los tres directorios de destino a `tmp_path`, así que nunca tocan el
mcpelauncher real.
"""

import io
import json
import zipfile

import pytest

from mcpemod.core import installer as modulo_installer
from mcpemod.core.installer import ErrorInstalacion, Installer
from mcpemod.core.mod import TipoArchivo
from mcpemod.core.store import Store


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    mods = tmp_path / "mods"
    resource = tmp_path / "resource_packs"
    behavior = tmp_path / "behavior_packs"
    descargas = tmp_path / "Downloads"
    for d in (mods, resource, behavior, descargas):
        d.mkdir()

    monkeypatch.setattr(modulo_installer, "MODS_DIR", mods)
    monkeypatch.setattr(modulo_installer, "RESOURCE_PACKS_DIR", resource)
    monkeypatch.setattr(modulo_installer, "BEHAVIOR_PACKS_DIR", behavior)

    store = Store(tmp_path / "test.db")
    return {
        "store": store, "installer": Installer(store),
        "mods": mods, "resource": resource, "behavior": behavior,
        "descargas": descargas,
    }


def _so(entorno, nombre, contenido=b"ELF"):
    ruta = entorno["descargas"] / nombre
    ruta.write_bytes(contenido)
    return ruta


def _pack(entorno, nombre, tipo="resources", extra=None):
    manifest = {"header": {"version": [1, 0, 0]}, "modules": [{"type": tipo}]}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        for archivo, datos in (extra or {}).items():
            zf.writestr(archivo, datos)
    ruta = entorno["descargas"] / nombre
    ruta.write_bytes(buf.getvalue())
    return ruta


# --- .so ---

def test_instalar_so(entorno):
    mod = entorno["installer"].instalar(_so(entorno, "MyMod-v1.0.0.so"))
    assert (entorno["mods"] / "MyMod-v1.0.0.so").is_file()
    assert mod.version == "1.0.0"
    assert mod.canonico == "MyMod"

def test_instalar_registra_en_historial(entorno):
    entorno["installer"].instalar(_so(entorno, "MyMod-v1.0.0.so"))
    hist = entorno["store"].historial()
    assert [e.accion for e in hist] == ["instalar"]

def test_tipo_no_soportado(entorno):
    ruta = entorno["descargas"] / "notas.txt"
    ruta.write_text("hola")
    with pytest.raises(ErrorInstalacion):
        entorno["installer"].instalar(ruta)

def test_archivo_inexistente(entorno):
    with pytest.raises(ErrorInstalacion):
        entorno["installer"].instalar(entorno["descargas"] / "fantasma.so")


# --- actualización ---

def test_actualizar_retira_la_version_anterior(entorno):
    """El fallo que esto previene: dos `.so` del mismo mod en `mods/` a la vez.

    El launcher carga todo lo que hay en la carpeta, así que dejar la versión
    vieja al lado de la nueva no es "un archivo de más" — es el mod cargado dos
    veces, que es lo que hace crashear al juego.
    """
    inst = entorno["installer"]
    inst.instalar(_so(entorno, "MyMod-v1.0.0.so"))
    inst.instalar(_so(entorno, "MyMod-v1.1.0.so"))

    assert not (entorno["mods"] / "MyMod-v1.0.0.so").exists()
    assert (entorno["mods"] / "MyMod-v1.1.0.so").is_file()
    assert len(entorno["store"].mods_instalados()) == 1

def test_actualizar_se_registra_como_actualizacion(entorno):
    inst = entorno["installer"]
    inst.instalar(_so(entorno, "MyMod-v1.0.0.so"))
    inst.instalar(_so(entorno, "MyMod-v1.1.0.so"))
    ultima = entorno["store"].historial()[0]
    assert ultima.accion == "actualizar"
    assert ultima.version == "1.1.0"
    assert ultima.version_anterior == "1.0.0"

def test_dos_mods_distintos_conviven(entorno):
    inst = entorno["installer"]
    inst.instalar(_so(entorno, "MyMod-v1.0.0.so"))
    inst.instalar(_so(entorno, "OtroMod-v1.0.0.so"))
    assert len(entorno["store"].mods_instalados()) == 2

def test_reinstalar_el_mismo_archivo_no_lo_borra(entorno):
    """Reinstalar borra la versión anterior; si el origen ES esa versión, se pierde."""
    inst = entorno["installer"]
    origen = _so(entorno, "MyMod-v1.0.0.so")
    inst.instalar(origen)
    inst.instalar(origen)
    assert origen.is_file()
    assert (entorno["mods"] / "MyMod-v1.0.0.so").is_file()


# --- packs ---

def test_instalar_mcpack_resource(entorno):
    mod = entorno["installer"].instalar(_pack(entorno, "Bonito.mcpack", "resources"))
    assert (entorno["resource"] / "Bonito").is_dir()
    assert mod.rutas == [entorno["resource"] / "Bonito"]

def test_instalar_mcpack_behavior(entorno):
    entorno["installer"].instalar(_pack(entorno, "Mobs.mcpack", "data"))
    assert (entorno["behavior"] / "Mobs").is_dir()

def test_reinstalar_pack_limpia_lo_anterior(entorno):
    inst = entorno["installer"]
    inst.instalar(_pack(entorno, "Pack.mcpack", "resources", {"viejo.txt": "x"}))
    assert (entorno["resource"] / "Pack" / "viejo.txt").exists()

    (entorno["descargas"] / "Pack.mcpack").unlink()
    inst.instalar(_pack(entorno, "Pack.mcpack", "resources", {"nuevo.txt": "y"}))
    assert not (entorno["resource"] / "Pack" / "viejo.txt").exists()
    assert (entorno["resource"] / "Pack" / "nuevo.txt").exists()

def test_zip_sin_manifest_va_a_mods(entorno):
    ruta = entorno["descargas"] / "cosas.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("leeme.txt", "hola")
    ruta.write_bytes(buf.getvalue())

    entorno["installer"].instalar(ruta)
    assert (entorno["mods"] / "cosas.zip").is_file()

def test_zip_incompleto_da_error_legible(entorno):
    ruta = entorno["descargas"] / "medio.mcpack"
    ruta.write_bytes(b"PK\x03\x04 truncado")
    with pytest.raises(ErrorInstalacion, match="incompleto|no es un archivo"):
        entorno["installer"].instalar(ruta)

def test_zip_slip_rechazado(entorno):
    """Un zip con `../` fuera de su carpeta escribiría donde no le corresponde."""
    ruta = entorno["descargas"] / "malicioso.mcpack"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"modules": [{"type": "resources"}]}))
        zf.writestr("../../fuera.txt", "no deberia estar aqui")
    ruta.write_bytes(buf.getvalue())

    with pytest.raises(ErrorInstalacion, match="fuera de su carpeta"):
        entorno["installer"].instalar(ruta)
    assert not (entorno["resource"].parent.parent / "fuera.txt").exists()


# --- .mcaddon ---

def test_instalar_mcaddon_reparte_sus_packs(entorno):
    addon = entorno["descargas"] / "Mundo.mcaddon"
    interno = io.BytesIO()
    with zipfile.ZipFile(interno, "w") as zf:
        recurso = io.BytesIO()
        with zipfile.ZipFile(recurso, "w") as rp:
            rp.writestr("manifest.json", json.dumps({"modules": [{"type": "resources"}]}))
        comportamiento = io.BytesIO()
        with zipfile.ZipFile(comportamiento, "w") as bp:
            bp.writestr("manifest.json", json.dumps({"modules": [{"type": "data"}]}))
        zf.writestr("MundoRP.mcpack", recurso.getvalue())
        zf.writestr("MundoBP.mcpack", comportamiento.getvalue())
    addon.write_bytes(interno.getvalue())

    mod = entorno["installer"].instalar(addon)
    assert (entorno["resource"] / "MundoRP").is_dir()
    assert (entorno["behavior"] / "MundoBP").is_dir()
    assert len(mod.rutas) == 2
    # El `.mcaddon` de Descargas no es una ruta instalada: borrarlo al
    # desinstalar destruiría el archivo del usuario.
    assert addon not in mod.rutas

def test_mcaddon_vacio_da_error(entorno):
    addon = entorno["descargas"] / "Vacio.mcaddon"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("leeme.txt", "nada")
    addon.write_bytes(buf.getvalue())
    with pytest.raises(ErrorInstalacion, match="no contiene"):
        entorno["installer"].instalar(addon)


# --- desinstalar ---

def test_desinstalar_so(entorno):
    inst = entorno["installer"]
    mod = inst.instalar(_so(entorno, "MyMod-v1.0.0.so"))
    inst.desinstalar(mod)
    assert not (entorno["mods"] / "MyMod-v1.0.0.so").exists()
    assert entorno["store"].mods_instalados() == []
    assert entorno["store"].historial()[0].accion == "desinstalar"

def test_desinstalar_pack_borra_la_carpeta(entorno):
    inst = entorno["installer"]
    mod = inst.instalar(_pack(entorno, "Bonito.mcpack", "resources"))
    inst.desinstalar(mod)
    assert not (entorno["resource"] / "Bonito").exists()

def test_desinstalar_mcaddon_no_toca_descargas(entorno):
    inst = entorno["installer"]
    addon = entorno["descargas"] / "Mundo.mcaddon"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        rp = io.BytesIO()
        with zipfile.ZipFile(rp, "w") as z:
            z.writestr("manifest.json", json.dumps({"modules": [{"type": "resources"}]}))
        zf.writestr("MundoRP.mcpack", rp.getvalue())
    addon.write_bytes(buf.getvalue())

    mod = inst.instalar(addon)
    inst.desinstalar(mod)
    assert not (entorno["resource"] / "MundoRP").exists()
    assert addon.is_file()

def test_desinstalar_lo_que_ya_no_esta_en_disco(entorno):
    inst = entorno["installer"]
    mod = inst.instalar(_so(entorno, "MyMod-v1.0.0.so"))
    (entorno["mods"] / "MyMod-v1.0.0.so").unlink()
    inst.desinstalar(mod)
    assert entorno["store"].mods_instalados() == []


def test_tipo_registrado_coincide_con_la_extension(entorno):
    mod = entorno["installer"].instalar(_pack(entorno, "Bonito.mcpack"))
    assert mod.tipo == TipoArchivo.MCPACK
