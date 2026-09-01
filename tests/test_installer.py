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
from mcpemod.core.mod import Forma, Instalado, nombre_de_carpeta


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

def test_la_carpeta_se_nombra_como_lo_haria_el_juego(installer, instalacion, tmp_path):
    """No es cosmético: el juego deriva la carpeta del nombre del pack, y si ya
    existe reemplaza su contenido. Con otro nombre, el mismo pack acabaría dos
    veces — una por cada vía de instalación."""
    _instalar(installer, pack(tmp_path / "x.mcpack", nombre="§fHide §bArmor§6 | §aV1.2§r"))
    assert (instalacion.resource_packs / "HideArmorV").is_dir()

def test_nombre_de_carpeta_sin_caracteres_ilegales():
    assert nombre_de_carpeta("a/b:c*d?e") == "abcde"
    assert nombre_de_carpeta("   ") == "pack"


# --- dedupe por uuid ---

def test_actualizar_reutiliza_la_carpeta_aunque_cambie_el_uuid(installer, instalacion,
                                                               tmp_path, store):
    """El caso que obligó a rehacer la identidad.

    Hay autores que cambian el `header.uuid` en cada publicación. Lo estable es
    el nombre, y es lo que usa el juego: misma carpeta destino, contenido
    reemplazado. Emparejando por uuid quedarían las dos versiones instaladas.
    """
    ajena = instalacion.resource_packs / "DéesseUIPa"
    ajena.mkdir()
    (ajena / "manifest.json").write_text(
        json.dumps(manifiesto(nombre="Déesse UI Pack", uuid="uuid-v131",
                              version=(1, 3, 1)))
    )
    previo = Instalado(uuid="uuid-v131", nombre="Déesse UI Pack", version="1.3.1",
                       categoria=Categoria.RECURSO, ruta=ajena)

    _instalar(installer,
              pack(tmp_path / "deesse.mcpack", nombre="Déesse UI Pack",
                   uuid="uuid-v139-distinto", version=(1, 3, 9)),
              {previo.clave: previo})

    assert sorted(p.name for p in instalacion.resource_packs.iterdir()) == ["DéesseUIPa"]
    assert store.historial()[0].accion == "actualizar"
    assert store.historial()[0].version_anterior == "1.3.1"

def test_la_version_en_el_nombre_no_impide_reconocerlo(installer, instalacion, tmp_path):
    """Otros autores meten la versión dentro del `header.name`."""
    ajena = instalacion.resource_packs / "HideArmorV"
    ajena.mkdir()
    (ajena / "manifest.json").write_text(
        json.dumps(manifiesto(nombre="Hide Armor | V1.2", uuid="u", version=(1, 2, 0)))
    )
    previo = Instalado(uuid="u", nombre="Hide Armor | V1.2", version="1.2.0",
                       categoria=Categoria.RECURSO, ruta=ajena)

    _instalar(installer,
              pack(tmp_path / "hide.mcpack", nombre="Hide Armor | V1.3.1",
                   uuid="u", version=(1, 3, 1)),
              {previo.clave: previo})

    assert sorted(p.name for p in instalacion.resource_packs.iterdir()) == ["HideArmorV"]

def test_dos_packs_distintos_conviven(installer, instalacion, tmp_path):
    _instalar(installer, pack(tmp_path / "a.mcpack", nombre="Uno", uuid="u-1"))
    _instalar(installer, pack(tmp_path / "b.mcpack", nombre="Dos", uuid="u-2"))
    assert len(list(instalacion.resource_packs.iterdir())) == 2

def test_packs_hermanos_no_se_pisan(installer, instalacion, tmp_path):
    """«Better Foliage Texture Pack NG» y «… FG» son packs distintos que conviven.

    Sus nombres solo chocan tras el recorte a diez caracteres, y ahí el sufijo
    los separa — igual que hace el juego.
    """
    _instalar(installer, pack(tmp_path / "a.mcpack",
                              nombre="Better Foliage Texture Pack NG", uuid="u-1"))
    _instalar(installer, pack(tmp_path / "b.mcpack",
                              nombre="Better Foliage Texture Pack FG", uuid="u-2"))
    assert sorted(p.name for p in instalacion.resource_packs.iterdir()) == [
        "BetterFoli", "BetterFoli (1)"
    ]

def test_reinstalar_limpia_lo_anterior(installer, instalacion, tmp_path):
    escribir_zip(tmp_path / "a.mcpack", {
        "manifest.json": json.dumps(manifiesto(nombre="P", uuid="u")),
        "viejo.txt": "x",
    })
    _instalar(installer, tmp_path / "a.mcpack")
    carpeta = instalacion.resource_packs / "P"
    previo = Instalado(uuid="u", nombre="P", version="1.0.0",
                       categoria=Categoria.RECURSO, ruta=carpeta)
    indice = {previo.clave: previo}

    escribir_zip(tmp_path / "b.mcpack", {
        "manifest.json": json.dumps(manifiesto(nombre="P", uuid="u", version=(2, 0, 0))),
        "nuevo.txt": "y",
    })
    _instalar(installer, tmp_path / "b.mcpack", indice)

    assert not (carpeta / "viejo.txt").exists()
    assert (carpeta / "nuevo.txt").exists()


# --- addons ---

def test_addon_reparte_sus_packs(installer, instalacion, tmp_path):
    _instalar(installer, addon(tmp_path / "M.mcaddon", {
        "RP.mcpack": dict(nombre="M RP", uuid="rp", tipo="resources"),
        "BP.mcpack": dict(nombre="M BP", uuid="bp", tipo="data"),
    }))
    assert (instalacion.resource_packs / "MRP" / "manifest.json").is_file()
    assert (instalacion.behavior_packs / "MBP" / "manifest.json").is_file()

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

def test_normalizar_pack_sin_extraer(installer, instalacion, tmp_path):
    """Un `.mcpack` sin extraer se instala de verdad y el archivo suelto se va."""
    suelto = instalacion.resource_packs / "Bonito.mcpack"
    pack(tmp_path / "tmp.mcpack", nombre="Bonito", uuid="u")
    suelto.write_bytes((tmp_path / "tmp.mcpack").read_bytes())

    pieza = Instalado(uuid="u", nombre="Bonito", version="1.0.0",
                      categoria=Categoria.RECURSO, ruta=suelto,
                      forma=Forma.EMPAQUETADO)
    installer.normalizar(pieza, {})

    assert not suelto.exists()
    assert (instalacion.resource_packs / "Bonito" / "manifest.json").is_file()

def test_normalizar_pack_con_carpeta_dentro(installer, instalacion, store):
    """Sube el contenido un nivel, sin perder nada por el camino."""
    carpeta = instalacion.resource_packs / "JavaCombat"
    interior = carpeta / "JavaCombat Bn"
    interior.mkdir(parents=True)
    (interior / "manifest.json").write_text(json.dumps(manifiesto(nombre="Java", uuid="u")))
    (interior / "textura.png").write_bytes(b"\x89PNG")

    pieza = Instalado(uuid="u", nombre="Java", version="1.0.0",
                      categoria=Categoria.RECURSO, ruta=carpeta, forma=Forma.ANIDADO)
    installer.normalizar(pieza, {})

    assert (carpeta / "manifest.json").is_file()
    assert (carpeta / "textura.png").is_file()
    assert not interior.exists()
    assert store.historial()[0].accion == "normalizar"

def test_normalizar_una_carpeta_normal_es_un_error(installer, instalacion):
    pieza = Instalado(uuid="u", nombre="X", version="1.0.0",
                      categoria=Categoria.RECURSO,
                      ruta=instalacion.resource_packs / "X", forma=Forma.CARPETA)
    with pytest.raises(ErrorInstalacion, match="ya está en forma de carpeta"):
        installer.normalizar(pieza, {})


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


def test_actualizar_desde_un_addon_no_instala_lo_demas(installer, instalacion, tmp_path):
    """Un pack puede estar publicado dentro de un addon que trae más cosas.

    Pasa de verdad: en el equipo de prueba, «CSO Terrorists» se empareja con el
    addon de «Actual Guns 2», que lo lleva dentro. Actualizar el uno no puede
    instalar el otro de propina.
    """
    ruta = addon(tmp_path / "Combo.mcaddon", {
        "Quiero.mcpack": dict(nombre="El que quiero", uuid="u-1", tipo="resources"),
        "NoQuiero.mcpack": dict(nombre="El otro", uuid="u-2", tipo="resources"),
    })
    from mcpemod.core.identidad import clave_de_pack

    installer.instalar(analizar(ruta), {}, solo={clave_de_pack("El que quiero")})

    assert [p.name for p in instalacion.resource_packs.iterdir()] == ["Elquequier"]


def test_instalar_un_addon_entero_sigue_trayendolo_todo(installer, instalacion, tmp_path):
    ruta = addon(tmp_path / "Combo.mcaddon", {
        "A.mcpack": dict(nombre="Uno", uuid="u-1", tipo="resources"),
        "B.mcpack": dict(nombre="Dos", uuid="u-2", tipo="data"),
    })
    installer.instalar(analizar(ruta), {})
    assert (instalacion.resource_packs / "Uno").is_dir()
    assert (instalacion.behavior_packs / "Dos").is_dir()


def test_si_lo_descargado_no_trae_ese_pack_se_dice(installer, tmp_path):
    ruta = pack(tmp_path / "otro.mcpack", nombre="Otra cosa", uuid="u-9")
    with pytest.raises(ErrorInstalacion, match="no contiene el pack"):
        installer.instalar(analizar(ruta), {}, solo={"elquequeria"})


def test_actualizar_un_pack_sin_extraer_retira_el_archivo_viejo(installer, instalacion,
                                                                tmp_path):
    """El caso que se coló en una prueba real, con «Realistic Rain Graphics».

    Lo instalado era un `.mcpack` sin extraer y lo nuevo es una carpeta, así que
    no se sobrescriben solos: quedaban los dos con el mismo uuid y el juego veía
    el pack dos veces.
    """
    suelto = instalacion.resource_packs / "Realistic Rain pack v3.1.mcpack"
    pack(tmp_path / "viejo.mcpack", nombre="Realistic Rain Graphics", uuid="u-lluvia",
         version=(3, 1, 0))
    suelto.write_bytes((tmp_path / "viejo.mcpack").read_bytes())

    previo = Instalado(uuid="u-lluvia", nombre="Realistic Rain Graphics",
                       version="3.1.0", categoria=Categoria.RECURSO,
                       ruta=suelto, forma=Forma.EMPAQUETADO)

    _instalar(installer,
              pack(tmp_path / "nuevo.mcpack", nombre="Realistic Rain Graphics v3.9",
                   uuid="u-lluvia", version=(3, 9, 0)),
              {previo.uuid: previo, previo.clave: previo})

    quedan = sorted(p.name for p in instalacion.resource_packs.iterdir())
    assert quedan == ["RealisticR"]
    assert not suelto.exists()


def test_actualizar_no_borra_el_archivo_que_se_esta_instalando(installer, instalacion,
                                                               tmp_path):
    """Extraer un pack usa su propio archivo como origen: no puede desaparecer
    a mitad de la operación."""
    suelto = instalacion.resource_packs / "Suelto.mcpack"
    pack(tmp_path / "tmp.mcpack", nombre="Suelto", uuid="u-1")
    suelto.write_bytes((tmp_path / "tmp.mcpack").read_bytes())

    previo = Instalado(uuid="u-1", nombre="Suelto", version="1.0.0",
                       categoria=Categoria.RECURSO, ruta=suelto,
                       forma=Forma.EMPAQUETADO)

    # El origen es el propio archivo suelto, como en «Extraer».
    installer.instalar(analizar(suelto), {previo.uuid: previo})
    assert suelto.exists()
    assert (instalacion.resource_packs / "Suelto").is_dir()


def test_al_actualizar_vale_el_uuid_si_el_nombre_cambio(installer, instalacion, tmp_path):
    """Un autor puede cambiar el nombre del pack entre versiones.

    Se vio en un ensayo sobre la instalación real: «BP | Fabulous Furnished» se
    publica como «Fabulous Furniture | v2.2.16 - With biomes». El emparejamiento
    lo había confirmado por uuid, pero el filtro de instalación miraba solo el
    nombre y rechazaba lo que acababa de descargar.
    """
    ruta = pack(tmp_path / "nuevo.mcpack", nombre="Fabulous Furniture - With biomes",
                uuid="u-mismo", version=(2, 2, 16))

    installer.instalar(analizar(ruta), {}, solo={"bpfabulousfurnished", "u-mismo"})

    assert [p.name for p in instalacion.resource_packs.iterdir()] == ["FabulousFu"]


def test_al_actualizar_manda_el_uuid_sobre_el_nombre(installer, instalacion, tmp_path):
    """Dos packs hermanos suelen compartir `header.name`.

    Es el caso de «Silk Touch Spawners», cuyo pack de recursos y de
    comportamiento se llaman igual: eligiendo por nombre se instalaba el que no
    era, encima del otro.
    """
    from conftest import escribir_zip, manifiesto
    import json as _json

    ruta = escribir_zip(tmp_path / "ambos.mcaddon", {
        "rp/manifest.json": _json.dumps(
            manifiesto(nombre="Silk Touch Spawners", uuid="uuid-rp", tipo="resources")),
        "bp/manifest.json": _json.dumps(
            manifiesto(nombre="Silk Touch Spawners", uuid="uuid-bp", tipo="data")),
    })

    # Se pide el de comportamiento, por uuid; el nombre coincide con los dos.
    installer.instalar(analizar(ruta), {}, solo={"silktouchspawners", "uuid-bp"})

    assert list(instalacion.resource_packs.iterdir()) == []
    assert [p.name for p in instalacion.behavior_packs.iterdir()] == ["SilkTouchS"]
