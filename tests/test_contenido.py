"""Pruebas de identificación de contenido por lo que trae dentro, no por la extensión.

La extensión no decide nada: un `.zip` puede ser un resource pack y un `.mcpack`
puede ser cualquier cosa. Tener un `manifest.json` en la raíz tampoco basta —
los modpacks de CurseForge para Java también lo tienen.
"""

import json

from conftest import addon, escribir_zip, manifiesto, mundo, pack

from mcpemod.core.contenido import Categoria, analizar, categoria_de
from mcpemod.core.manifiesto import TIPOS_COMPORTAMIENTO, TIPOS_RECURSO


# --- destino según el tipo del módulo ---

def test_recursos_van_a_resource_packs():
    assert categoria_de(TIPOS_RECURSO) == Categoria.RECURSO

def test_datos_y_scripts_van_a_behavior_packs():
    assert categoria_de(frozenset({"data"})) == Categoria.COMPORTAMIENTO
    assert categoria_de(frozenset({"script"})) == Categoria.COMPORTAMIENTO
    assert categoria_de(TIPOS_COMPORTAMIENTO) == Categoria.COMPORTAMIENTO

def test_pack_mixto_va_a_comportamiento():
    """Un pack con módulos de recursos y de datos a la vez existe y es válido.

    Va a behavior_packs porque es donde el juego espera los `data` y los
    `script`; el módulo de recursos viaja con ellos.
    """
    assert categoria_de(frozenset({"resources", "data"})) == Categoria.COMPORTAMIENTO

def test_tipo_desconocido_no_tiene_destino():
    assert categoria_de(frozenset({"vete_a_saber"})) is None


# --- la extensión no decide ---

def test_zip_con_manifiesto_de_bedrock_es_un_pack(tmp_path):
    a = analizar(pack(tmp_path / "cualquiera.zip", nombre="Un pack"))
    assert a is not None
    assert a.componentes[0].categoria == Categoria.RECURSO
    assert a.componentes[0].nombre == "Un pack"

def test_mcpack_que_no_es_un_pack_se_descarta(tmp_path):
    ruta = escribir_zip(tmp_path / "mentira.mcpack", {"leeme.txt": "hola"})
    assert analizar(ruta) is None

def test_modpack_de_java_se_descarta(tmp_path):
    ruta = escribir_zip(tmp_path / "modpack.zip", {
        "manifest.json": json.dumps({
            "manifestType": "minecraftModpack", "name": "DeceasedCraft",
            "version": "5.10.16", "files": [],
        }),
        "overrides/config/x.toml": "a=1",
    })
    assert analizar(ruta) is None

def test_archivo_que_no_es_zip_se_descarta(tmp_path):
    ruta = tmp_path / "foto.png"
    ruta.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    assert analizar(ruta) is None

def test_archivo_vacio_se_descarta(tmp_path):
    ruta = tmp_path / "vacio.mcpack"
    ruta.write_bytes(b"")
    assert analizar(ruta) is None

def test_descarga_a_medias_se_descarta(tmp_path):
    """Un zip incompleto existe pero no se puede abrir."""
    ruta = tmp_path / "medio.mcpack"
    ruta.write_bytes(b"PK\x03\x04 truncado")
    assert analizar(ruta) is None


# --- identidad ---

def test_uuid_y_version_salen_del_manifiesto(tmp_path):
    a = analizar(pack(tmp_path / "x.mcpack", uuid="abc-123", version=(2, 5, 1)))
    c = a.componentes[0]
    assert c.uuid == "abc-123"
    assert c.version == "2.5.1"

def test_el_nombre_del_archivo_no_afecta_a_la_identidad(tmp_path):
    """Renombrar la descarga no cambia lo que es."""
    a = analizar(pack(tmp_path / "Pack-v9.9.9-FINAL(2).mcpack", uuid="u", version=(1, 0, 0)))
    assert a.componentes[0].version == "1.0.0"
    assert a.uuids == {"u"}


# --- addons ---

def test_addon_declara_una_pieza_por_pack_interno(tmp_path):
    ruta = addon(tmp_path / "Mundo.mcaddon", {
        "MundoRP.mcpack": dict(nombre="Mundo RP", uuid="rp-1", tipo="resources"),
        "MundoBP.mcpack": dict(nombre="Mundo BP", uuid="bp-1", tipo="data"),
    })
    a = analizar(ruta)
    assert {c.categoria for c in a.componentes} == {Categoria.RECURSO, Categoria.COMPORTAMIENTO}
    assert a.uuids == {"rp-1", "bp-1"}
    assert all(c.anidado_en for c in a.componentes)

def test_addon_como_carpetas_en_vez_de_mcpack(tmp_path):
    """Hay addons que traen los packs como subcarpetas, sin anidar zips."""
    ruta = escribir_zip(tmp_path / "Suelto.mcaddon", {
        "rp/manifest.json": json.dumps(manifiesto(nombre="RP", uuid="rp-2", tipo="resources")),
        "bp/manifest.json": json.dumps(manifiesto(nombre="BP", uuid="bp-2", tipo="data")),
    })
    a = analizar(ruta)
    assert a.uuids == {"rp-2", "bp-2"}
    assert {c.prefijo for c in a.componentes} == {"rp/", "bp/"}

def test_addon_vacio_se_descarta(tmp_path):
    ruta = escribir_zip(tmp_path / "Vacio.mcaddon", {"leeme.txt": "nada"})
    assert analizar(ruta) is None


# --- mundos ---

def test_mundo_se_reconoce_por_su_level_dat(tmp_path):
    """Un mundo no lleva manifiesto: lo identifica el `level.dat`."""
    a = analizar(mundo(tmp_path / "MiMundo.mcworld"))
    assert a.componentes[0].categoria == Categoria.MUNDO
    assert a.componentes[0].uuid == ""

def test_mundo_con_extension_zip(tmp_path):
    a = analizar(mundo(tmp_path / "copia_de_seguridad.zip"))
    assert a.componentes[0].categoria == Categoria.MUNDO


# --- pack con carpeta contenedora ---

def test_pack_empaquetado_con_su_carpeta(tmp_path):
    """Algunos packs se empaquetan con una carpeta dentro; hay que localizarla."""
    a = analizar(pack(tmp_path / "x.mcpack", prefijo="Mi Pack/", uuid="u"))
    assert a.componentes[0].prefijo == "Mi Pack/"
    assert a.componentes[0].uuid == "u"
