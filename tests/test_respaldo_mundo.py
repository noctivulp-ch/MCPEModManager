"""Pruebas del respaldo de mundos.

Un mundo es lo único de aquí que no se puede volver a descargar, así que estas
pruebas no comprueban que la función «no dé error»: comprueban que **lo guardado
sirve para restaurar** y que un fallo a mitad no se lleva por delante lo que
había.
"""

import shutil

import pytest

from mcpemod.core.respaldo_mundo import (
    ErrorRespaldo, existente, guardar, restaurar,
)


@pytest.fixture
def mundo(tmp_path):
    """Un mundo con lo mínimo que lo hace un mundo, y algo dentro que perder."""
    carpeta = tmp_path / "minecraftWorlds" / "bE2ZIuTv+eY="
    (carpeta / "db").mkdir(parents=True)
    (carpeta / "level.dat").write_bytes(b"\x00nivel original")
    (carpeta / "levelname.txt").write_text("DurDream")
    (carpeta / "db" / "000001.log").write_bytes(b"partida de meses")
    (carpeta / "resource_packs" / "UnPack").mkdir(parents=True)
    (carpeta / "resource_packs" / "UnPack" / "manifest.json").write_text("{}")
    return carpeta


@pytest.fixture
def respaldos(tmp_path):
    return tmp_path / "mcpemod_respaldos"


# --- guardar ---

def test_guardar_deja_un_respaldo_utilizable(mundo, respaldos):
    r = guardar(mundo, respaldos)
    assert r.ruta.is_file()
    assert r.nombre == "DurDream"
    assert r.bytes > 0

def test_hay_uno_por_mundo(mundo, respaldos):
    """No una pila que crezca sola: son cientos de megas cada uno."""
    guardar(mundo, respaldos)
    guardar(mundo, respaldos)
    assert len(list(respaldos.glob("*.tar.zst"))) == 1

def test_se_puede_saber_que_habia_antes_de_sustituirlo(mundo, respaldos):
    """Quien vaya a sobrescribirlo tiene que poder avisar de qué se pierde."""
    assert existente(mundo, respaldos) is None
    guardar(mundo, respaldos)
    previo = existente(mundo, respaldos)
    assert previo is not None
    assert "DurDream" in previo.descripcion

def test_una_carpeta_que_no_es_un_mundo_se_rechaza(tmp_path, respaldos):
    falso = tmp_path / "no-es-un-mundo"
    falso.mkdir()
    (falso / "cualquier.txt").write_text("hola")
    with pytest.raises(ErrorRespaldo, match="level.dat"):
        guardar(falso, respaldos)

def test_los_respaldos_no_viven_entre_los_mundos(mundo, respaldos):
    """Dentro de `minecraftWorlds` se verían como mundos más."""
    guardar(mundo, respaldos)
    assert respaldos.parent != mundo.parent
    assert list(mundo.parent.glob("*.tar.zst")) == []


# --- restaurar ---

def test_restaurar_devuelve_el_contenido(mundo, respaldos):
    guardar(mundo, respaldos)
    (mundo / "db" / "000001.log").write_bytes(b"ROTO")
    (mundo / "level.dat").unlink()

    restaurar(mundo, respaldos)
    assert (mundo / "level.dat").read_bytes() == b"\x00nivel original"
    assert (mundo / "db" / "000001.log").read_bytes() == b"partida de meses"

def test_restaurar_devuelve_tambien_los_packs_del_mundo(mundo, respaldos):
    guardar(mundo, respaldos)
    shutil.rmtree(mundo / "resource_packs")

    restaurar(mundo, respaldos)
    assert (mundo / "resource_packs" / "UnPack" / "manifest.json").is_file()

def test_restaurar_sin_respaldo(mundo, respaldos):
    with pytest.raises(ErrorRespaldo, match="No hay respaldo"):
        restaurar(mundo, respaldos)


# --- que un fallo no se lleve nada por delante ---

def test_si_falla_comprimir_sigue_estando_el_anterior(mundo, respaldos, monkeypatch):
    """El respaldo viejo no se toca hasta que el nuevo está escrito y comprobado."""
    from mcpemod.core import respaldo_mundo

    guardar(mundo, respaldos)
    antes = existente(mundo, respaldos).ruta.read_bytes()

    def revienta(*a, **kw):
        raise ErrorRespaldo("se acabó el disco")

    monkeypatch.setattr(respaldo_mundo, "_comprimir", revienta)
    with pytest.raises(ErrorRespaldo):
        guardar(mundo, respaldos)

    assert existente(mundo, respaldos).ruta.read_bytes() == antes

def test_un_respaldo_ilegible_no_se_da_por_bueno(mundo, respaldos):
    """Un `tar` que no da error no basta: tiene que servir para restaurar."""
    guardar(mundo, respaldos)
    existente(mundo, respaldos).ruta.write_bytes(b"esto no es un tar")
    with pytest.raises(ErrorRespaldo):
        restaurar(mundo, respaldos)

def test_si_el_respaldo_no_trae_mundo_no_se_restaura(mundo, respaldos, tmp_path):
    """Restaurar algo sin `level.dat` encima de un mundo bueno lo destruiría."""
    import subprocess
    respaldos.mkdir(parents=True, exist_ok=True)
    vacio = tmp_path / "vacio" / mundo.name
    vacio.mkdir(parents=True)
    (vacio / "solo_esto.txt").write_text("nada")
    subprocess.run(["tar", "--zstd", "-cf",
                    str(respaldos / f"{mundo.name}.tar.zst"),
                    "-C", str(vacio.parent), mundo.name], check=True)

    with pytest.raises(ErrorRespaldo):
        restaurar(mundo, respaldos)
    # Y el mundo que había sigue intacto.
    assert (mundo / "level.dat").read_bytes() == b"\x00nivel original"
