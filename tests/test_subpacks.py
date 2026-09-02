"""Las variantes de un pack: leerlas del manifiesto y elegir una.

La documentación oficial las describe por lo que son: *«sub-packs let players
choose between different variations of a resource pack and switch between them at
any time»*. En este equipo 16 packs las traen y son opciones de verdad —densidad
del bosque, si el monstruo aparece solo de noche, con efectos o sin ellos—.

Lo que se prueba es lo que sale caro si falla en silencio: **escribir el nombre
legible donde va la carpeta** deja al juego buscando una variante que no existe,
y no avisa — el pack simplemente se aplica sin ella.
"""

import json

import pytest

from mcpemod.core.activacion import ErrorActivacion, Global
from mcpemod.core.contenido import Categoria
from mcpemod.core.manifiesto import desde_datos, limpiar_formato
from mcpemod.core.mod import Instalado

from conftest import manifiesto


def _con_subpacks(*subpacks, **extra):
    return json.dumps(manifiesto(subpacks=list(subpacks), **extra)).encode()


def test_la_carpeta_y_el_nombre_no_son_lo_mismo():
    """`folder_name` es lo que se escribe; `name` es «the name players see».

    En un pack de este equipo la carpeta es `with_vfx` y el nombre «With VFX
    effect». Confundirlos activa una variante que no existe, y el juego no avisa.
    """
    m = desde_datos(_con_subpacks(
        {"folder_name": "with_vfx", "name": "With VFX effect", "memory_tier": 2}
    ))
    assert m.subpacks[0].carpeta == "with_vfx"
    assert m.subpacks[0].nombre == "With VFX effect"
    assert m.subpacks[0].memoria == 2


def test_una_variante_sin_carpeta_se_descarta():
    """Sin `folder_name` no hay nada que escribir: enseñarla sería ofrecer algo
    que no se puede aplicar."""
    m = desde_datos(_con_subpacks(
        {"name": "Solo un nombre"},
        {"folder_name": "sp1", "name": "Buena"},
    ))
    assert [s.carpeta for s in m.subpacks] == ["sp1"]


def test_sin_nombre_se_enseña_la_carpeta():
    m = desde_datos(_con_subpacks({"folder_name": "sp1"}))
    assert m.subpacks[0].nombre == "sp1"


def test_del_nombre_se_usa_solo_la_primera_linea():
    """Hay autores que meten la explicación entera en el `name`, con saltos de
    línea: uno de este equipo escribe cuatro párrafos ahí. Para elegir hace falta
    una línea."""
    m = desde_datos(_con_subpacks(
        {"folder_name": "sp1", "name": "Iconos monocromos\nSolo negro y gris.\nY más."}
    ))
    assert m.subpacks[0].nombre == "Iconos monocromos"


def test_se_quitan_los_glifos_de_la_fuente_del_juego():
    """Los caracteres del Área de Uso Privado dibujan iconos dentro de Minecraft
    y cajas vacías en cualquier otra fuente."""
    assert limpiar_formato(" Monochrome §aIcons") == "Monochrome Icons"


def test_las_notas_salen_de_los_labels_de_settings():
    """La documentación las llama «a description of what the pack and sub-packs
    include». Es donde el autor avisa de que hay que reiniciar el juego."""
    m = desde_datos(json.dumps(manifiesto(settings=[
        {"type": "label", "text": "§lHay que reiniciar Minecraft.§r"},
        {"type": "toggle", "text": "No es una nota", "name": "x"},
    ])).encode())
    assert m.notas == ("Hay que reiniciar Minecraft.",)


# ── Elegir una ───────────────────────────────────────────────────────────────

def _pieza(instalacion, uuid, nombre="Pack"):
    carpeta = instalacion.com_mojang / "resource_packs" / nombre
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "manifest.json").write_text(json.dumps(manifiesto(nombre=nombre, uuid=uuid)))
    return Instalado(uuid=uuid, nombre=nombre, version="1.0.0",
                     categoria=Categoria.RECURSO, ruta=carpeta)


def test_elegir_variante_no_mueve_el_pack_de_sitio(instalacion):
    """Reactivar con otra variante lo mandaría al final, y el orden es lo que
    decide cuál gana cuando dos packs tocan lo mismo."""
    general = Global(instalacion)
    a = _pieza(instalacion, "aaaaaaaa-1111-1111-1111-111111111111", "A")
    b = _pieza(instalacion, "bbbbbbbb-2222-2222-2222-222222222222", "B")
    general.activar(a)
    general.activar(b)

    general.elegir_subpack(a, "with_vfx")

    activos = general.activos(Categoria.RECURSO)
    assert [r.uuid for r in activos] == [a.uuid, b.uuid]
    assert activos[0].subpack == "with_vfx"


def test_quitar_la_variante_devuelve_la_decision_al_juego(instalacion):
    """`None` no es «sin variante»: sin elección el juego coge sola la más alta
    que quepa en el aparato."""
    general = Global(instalacion)
    a = _pieza(instalacion, "aaaaaaaa-1111-1111-1111-111111111111", "A")
    general.activar(a, subpack="sp1")
    assert general.subpack_de(a) == "sp1"

    general.elegir_subpack(a, None)

    assert general.subpack_de(a) is None
    assert "subpack" not in json.loads(
        general.archivo_de(Categoria.RECURSO).read_text())[0]


def test_no_se_puede_elegir_variante_de_lo_que_no_esta_activo(instalacion):
    """La variante se guarda dentro de la entrada de activación: sin entrada no
    hay dónde ponerla, y escribirla igual la perdería sin decir nada."""
    general = Global(instalacion)
    a = _pieza(instalacion, "aaaaaaaa-1111-1111-1111-111111111111", "A")

    with pytest.raises(ErrorActivacion, match="no está activo"):
        general.elegir_subpack(a, "sp1")
