"""Pruebas del Installer — la capa que escribe y borra en la carpeta del juego.

Todos sus fallos son destructivos o silenciosos: borrar lo que no era, dejar el
mismo pack dos veces, o extraer un zip encima de archivos ajenos. Los tests usan
una instalación falsa en `tmp_path`, así que nunca tocan el juego real.
"""

import json

import pytest
from conftest import addon, escribir_zip, manifiesto, mundo, pack

from mcpemod.core.contenido import Categoria, analizar
from mcpemod.core.installer import ErrorInstalacion, Installer
from mcpemod.core.mod import Instalado, nombre_de_carpeta


@pytest.fixture
def installer(store, instalacion):
    return Installer(store, instalacion)


def _instalar(installer, ruta, instalados=None):
    return installer.instalar(analizar(ruta), instalados or {})


# --- destino según el tipo declarado ---

def test_recursos_van_a_resource_packs(installer, instalacion, tmp_path):
    _instalar(installer, pack(tmp_path / "x.mcpack", nombre="Bonito", tipo="resources"))
    assert (instalacion.resource_packs / "Bonito").is_dir()

def test_datos_van_a_behavior_packs(installer, instalacion, tmp_path):
    _instalar(installer, pack(tmp_path / "x.mcpack", nombre="Mobs", tipo="data"))
    assert (instalacion.behavior_packs / "Mobs").is_dir()

def test_scripts_van_a_behavior_packs(installer, instalacion, tmp_path):
    _instalar(installer, pack(tmp_path / "x.mcpack", nombre="Scripts", tipo="script"))
    assert (instalacion.behavior_packs / "Scripts").is_dir()

def test_mundo_va_a_minecraftworlds(installer, instalacion, tmp_path):
    _instalar(installer, mundo(tmp_path / "MiMundo.mcworld"))
    assert (instalacion.mundos / "MiMundo" / "level.dat").is_file()

def test_la_extension_no_decide_el_destino(installer, instalacion, tmp_path):
    """Un `.zip` con manifiesto de comportamiento va a behavior_packs igual."""
    _instalar(installer, pack(tmp_path / "cualquiera.zip", nombre="Z", tipo="data"))
    assert (instalacion.behavior_packs / "Z").is_dir()
    assert not (instalacion.resource_packs / "Z").exists()


# --- contenido instalado ---

def test_el_contenido_se_extrae_a_la_raiz_de_la_carpeta(installer, instalacion, tmp_path):
    """El juego busca `manifest.json` en la raíz de la carpeta del pack."""
    _instalar(installer, pack(tmp_path / "x.mcpack", nombre="Bonito"))
    assert (instalacion.resource_packs / "Bonito" / "manifest.json").is_file()

def test_pack_con_carpeta_contenedora_se_aplana(installer, instalacion, tmp_path):
    """Si se extrajera tal cual, el manifiesto quedaría un nivel más abajo y el
    juego no cargaría el pack."""
    _instalar(installer, pack(tmp_path / "x.mcpack", prefijo="Mi Pack/", nombre="Bonito"))
    assert (instalacion.resource_packs / "Bonito" / "manifest.json").is_file()

def test_nombre_de_carpeta_legible(installer, instalacion, tmp_path):
    _instalar(installer, pack(tmp_path / "x.mcpack", nombre="Hide Armor | V1.2"))
    assert (instalacion.resource_packs / "Hide Armor V1.2").is_dir()

def test_nombre_de_carpeta_sin_caracteres_ilegales():
    assert nombre_de_carpeta("a/b:c*d?e") == "abcde"
    assert nombre_de_carpeta("   ") == "pack"


# --- dedupe por uuid ---

def test_reinstalar_reutiliza_la_carpeta_existente(installer, instalacion, tmp_path, store):
    """El caso real: el pack lo importó el juego con otro nombre de carpeta.

    El juego localiza los packs por uuid, así que crear una carpeta nueva
    dejaría el mismo pack dos veces en la lista del juego.
    """
    ajena = instalacion.resource_packs / "HideArmorV"
    ajena.mkdir()
    (ajena / "manifest.json").write_text(
        json.dumps(manifiesto(nombre="Hide Armor", uuid="uuid-hide", version=(1, 2, 0)))
    )
    previo = Instalado(uuid="uuid-hide", nombre="Hide Armor", version="1.2.0",
                       categoria=Categoria.RECURSO, ruta=ajena)

    _instalar(installer,
              pack(tmp_path / "Hide Armor v1.3.mcpack", nombre="Hide Armor",
                   uuid="uuid-hide", version=(1, 3, 0)),
              {"uuid-hide": previo})

    assert sorted(p.name for p in instalacion.resource_packs.iterdir()) == ["HideArmorV"]
    assert store.historial()[0].accion == "actualizar"
    assert store.historial()[0].version_anterior == "1.2.0"

def test_dos_packs_distintos_conviven(installer, instalacion, tmp_path):
    _instalar(installer, pack(tmp_path / "a.mcpack", nombre="Uno", uuid="u-1"))
    _instalar(installer, pack(tmp_path / "b.mcpack", nombre="Dos", uuid="u-2"))
    assert len(list(instalacion.resource_packs.iterdir())) == 2

def test_mismo_nombre_distinto_uuid_no_se_pisan(installer, instalacion, tmp_path):
    """Dos packs pueden llamarse igual siendo distintos; no pueden compartir carpeta."""
    _instalar(installer, pack(tmp_path / "a.mcpack", nombre="Pack", uuid="u-1"))
    _instalar(installer, pack(tmp_path / "b.mcpack", nombre="Pack", uuid="u-2"))
    assert sorted(p.name for p in instalacion.resource_packs.iterdir()) == ["Pack", "Pack (1)"]

def test_reinstalar_limpia_lo_anterior(installer, instalacion, tmp_path):
    escribir_zip(tmp_path / "a.mcpack", {
        "manifest.json": json.dumps(manifiesto(nombre="P", uuid="u")),
        "viejo.txt": "x",
    })
    _instalar(installer, tmp_path / "a.mcpack")
    carpeta = instalacion.resource_packs / "P"
    previo = Instalado(uuid="u", nombre="P", version="1.0.0",
                       categoria=Categoria.RECURSO, ruta=carpeta)

    escribir_zip(tmp_path / "b.mcpack", {
        "manifest.json": json.dumps(manifiesto(nombre="P", uuid="u", version=(2, 0, 0))),
        "nuevo.txt": "y",
    })
    _instalar(installer, tmp_path / "b.mcpack", {"u": previo})

    assert not (carpeta / "viejo.txt").exists()
    assert (carpeta / "nuevo.txt").exists()


# --- addons ---

def test_addon_reparte_sus_packs(installer, instalacion, tmp_path):
    _instalar(installer, addon(tmp_path / "M.mcaddon", {
        "RP.mcpack": dict(nombre="M RP", uuid="rp", tipo="resources"),
        "BP.mcpack": dict(nombre="M BP", uuid="bp", tipo="data"),
    }))
    assert (instalacion.resource_packs / "M RP" / "manifest.json").is_file()
    assert (instalacion.behavior_packs / "M BP" / "manifest.json").is_file()

def test_addon_no_deja_rastro_en_descargas(installer, tmp_path):
    """Los packs internos se materializan en un temporal, no junto al origen."""
    carpeta = tmp_path / "Descargas"
    ruta = addon(carpeta / "M.mcaddon", {
        "RP.mcpack": dict(nombre="M RP", uuid="rp", tipo="resources"),
        "BP.mcpack": dict(nombre="M BP", uuid="bp", tipo="data"),
    })
    _instalar(installer, ruta)
    assert [p.name for p in carpeta.iterdir()] == ["M.mcaddon"]


# --- seguridad ---

def test_zip_slip_rechazado(installer, instalacion, tmp_path):
    ruta = escribir_zip(tmp_path / "malicioso.mcpack", {
        "manifest.json": json.dumps(manifiesto(nombre="Malo", uuid="u")),
        "../../fuera.txt": "no deberia estar aqui",
    })
    with pytest.raises(ErrorInstalacion, match="fuera de su carpeta"):
        _instalar(installer, ruta)
    assert not (instalacion.com_mojang / "fuera.txt").exists()

def test_archivo_no_instalable(installer, tmp_path):
    ruta = escribir_zip(tmp_path / "nada.mcpack", {"leeme.txt": "hola"})
    assert analizar(ruta) is None


# --- reparar ---

def test_reparar_pack_sin_extraer(installer, instalacion, tmp_path, store):
    """Un `.mcpack` copiado a la carpeta sin extraer: el juego solo abre carpetas."""
    suelto = instalacion.resource_packs / "Bonito.mcpack"
    pack(tmp_path / "tmp.mcpack", nombre="Bonito", uuid="u")
    suelto.write_bytes((tmp_path / "tmp.mcpack").read_bytes())

    pieza = Instalado(uuid="u", nombre="Bonito", version="1.0.0",
                      categoria=Categoria.RECURSO, ruta=suelto, activo=False)
    installer.reparar(pieza, {})

    assert not suelto.exists()
    assert (instalacion.resource_packs / "Bonito" / "manifest.json").is_file()

def test_reparar_pack_anidado(installer, instalacion, store):
    """Un pack extraído con su carpeta dentro deja el manifiesto un nivel abajo."""
    carpeta = instalacion.resource_packs / "JavaCombat"
    interior = carpeta / "JavaCombat Bn"
    interior.mkdir(parents=True)
    (interior / "manifest.json").write_text(json.dumps(manifiesto(nombre="Java", uuid="u")))
    (interior / "textura.png").write_bytes(b"\x89PNG")

    pieza = Instalado(uuid="u", nombre="Java", version="1.0.0",
                      categoria=Categoria.RECURSO, ruta=carpeta, activo=False)
    installer.reparar(pieza, {})

    assert (carpeta / "manifest.json").is_file()
    assert (carpeta / "textura.png").is_file()
    assert not interior.exists()
    assert store.historial()[0].accion == "reparar"

def test_reparar_lo_que_ya_esta_bien_es_un_error(installer, instalacion):
    pieza = Instalado(uuid="u", nombre="X", version="1.0.0",
                      categoria=Categoria.RECURSO,
                      ruta=instalacion.resource_packs / "X", activo=True)
    with pytest.raises(ErrorInstalacion, match="ya está instalado"):
        installer.reparar(pieza, {})


# --- desinstalar ---

def test_desinstalar_borra_la_carpeta(installer, instalacion, tmp_path, store):
    _instalar(installer, pack(tmp_path / "x.mcpack", nombre="Bonito", uuid="u"))
    carpeta = instalacion.resource_packs / "Bonito"
    pieza = Instalado(uuid="u", nombre="Bonito", version="1.0.0",
                      categoria=Categoria.RECURSO, ruta=carpeta)

    installer.desinstalar(pieza)
    assert not carpeta.exists()
    assert store.historial()[0].accion == "desinstalar"
    assert store.origenes() == {}

def test_desinstalar_lo_que_ya_no_esta(installer, instalacion):
    pieza = Instalado(uuid="u", nombre="X", version=None,
                      categoria=Categoria.RECURSO,
                      ruta=instalacion.resource_packs / "fantasma")
    installer.desinstalar(pieza)  # no lanza
