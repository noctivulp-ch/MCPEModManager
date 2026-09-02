"""La portada del pack y la relectura de su manifiesto.

La portada es lo que distingue tres packs llamados «Better Foliage…» sin leer el
renglón entero. Si falla, la lista sigue funcionando pero vuelve a ser una
columna de texto — un fallo que no rompe nada y por eso puede quedarse.

La relectura del manifiesto sí importa más: es de donde salen la descripción y
las variantes de la ficha, y devolver `None` deja la ficha vacía sin decir por
qué.
"""

import json

from mcpemod.core.contenido import Categoria
from mcpemod.core.miniatura import leer, manifiesto_de
from mcpemod.core.mod import Forma, Instalado

from conftest import escribir_zip, manifiesto

PNG = b"\x89PNG\r\n\x1a\n falso"


def _pieza(ruta, forma=Forma.CARPETA):
    return Instalado(uuid="u", nombre="P", version="1.0.0",
                     categoria=Categoria.RECURSO, ruta=ruta, forma=forma)


def test_la_portada_de_una_carpeta(tmp_path):
    carpeta = tmp_path / "pack"
    carpeta.mkdir()
    (carpeta / "pack_icon.png").write_bytes(PNG)
    assert leer(_pieza(carpeta)) == PNG


def test_la_portada_de_un_pack_anidado(tmp_path):
    """Un pack extraído con su carpeta contenedora la tiene un nivel más abajo."""
    dentro = tmp_path / "pack" / "de verdad"
    dentro.mkdir(parents=True)
    (dentro / "pack_icon.png").write_bytes(PNG)
    assert leer(_pieza(tmp_path / "pack")) == PNG


def test_la_portada_de_un_mcpack_sin_extraer(tmp_path):
    """No hace falta extraerlo: es un zip."""
    archivo = escribir_zip(tmp_path / "x.mcpack", {
        "manifest.json": json.dumps(manifiesto()), "pack_icon.png": PNG,
    })
    assert leer(_pieza(archivo, Forma.EMPAQUETADO)) == PNG


def test_un_mundo_usa_su_propia_captura(tmp_path):
    """El juego guarda `world_icon.jpeg` al salir. Es otro nombre para lo mismo."""
    carpeta = tmp_path / "mundo"
    carpeta.mkdir()
    (carpeta / "world_icon.jpeg").write_bytes(PNG)
    assert leer(_pieza(carpeta)) == PNG


def test_un_pack_sin_portada_no_es_un_fallo(tmp_path):
    carpeta = tmp_path / "pack"
    carpeta.mkdir()
    assert leer(_pieza(carpeta)) is None


def test_un_zip_roto_no_interrumpe_el_listado(tmp_path):
    """Se enseña sin portada. Reventar aquí dejaría la lista entera sin pintar."""
    archivo = tmp_path / "roto.mcpack"
    archivo.write_bytes(b"esto no es un zip")
    assert leer(_pieza(archivo, Forma.EMPAQUETADO)) is None


def test_una_portada_enorme_no_se_lee(tmp_path):
    """Un icono de pack pesa unos KB. Lo que pese megas no es una portada, y
    leerlo entero para encogerlo a 34 px sale caro."""
    from mcpemod.core.miniatura import MAXIMO

    carpeta = tmp_path / "pack"
    carpeta.mkdir()
    (carpeta / "pack_icon.png").write_bytes(b"\x00" * (MAXIMO + 1))
    assert leer(_pieza(carpeta)) is None


def test_el_manifiesto_se_relee_de_la_carpeta(tmp_path):
    carpeta = tmp_path / "pack"
    carpeta.mkdir()
    (carpeta / "manifest.json").write_text(json.dumps(manifiesto(
        nombre="Con variantes",
        subpacks=[{"folder_name": "sp1", "name": "Una"}],
    )))
    m = manifiesto_de(_pieza(carpeta))
    assert m is not None and m.subpacks[0].carpeta == "sp1"


def test_el_manifiesto_se_relee_de_un_mcpack(tmp_path):
    archivo = escribir_zip(tmp_path / "x.mcpack", {
        "manifest.json": json.dumps(manifiesto(nombre="Empaquetado")),
    })
    m = manifiesto_de(_pieza(archivo, Forma.EMPAQUETADO))
    assert m is not None and m.nombre == "Empaquetado"


def test_un_manifiesto_ilegible_deja_la_ficha_sin_datos(tmp_path):
    """`None` y no una excepción: la ficha se abre igual con lo que ya se sabe
    del pack, que es más útil que un error."""
    carpeta = tmp_path / "pack"
    carpeta.mkdir()
    (carpeta / "manifest.json").write_text("{ esto no es json")
    assert manifiesto_de(_pieza(carpeta)) is None


# ── La portada de algo que todavía no está instalado ─────────────────────────

def test_cada_pack_de_un_mcaddon_lleva_su_propia_portada(tmp_path):
    """Un `.mcaddon` trae el pack de recursos y el de comportamiento, y cada uno
    tiene su cara. Coger la primera que aparezca les pondría la misma."""
    from mcpemod.core.miniatura import de_ruta

    rp = escribir_zip(tmp_path / "rp.mcpack", {
        "manifest.json": json.dumps(manifiesto(tipo="resources")),
        "pack_icon.png": b"PORTADA-RP",
    })
    bp = escribir_zip(tmp_path / "bp.mcpack", {
        "manifest.json": json.dumps(manifiesto(tipo="data")),
        "pack_icon.png": b"PORTADA-BP",
    })
    addon = escribir_zip(tmp_path / "todo.mcaddon", {
        "rp.mcpack": rp.read_bytes(), "bp.mcpack": bp.read_bytes(),
    })

    assert de_ruta(addon, anidado_en="rp.mcpack") == b"PORTADA-RP"
    assert de_ruta(addon, anidado_en="bp.mcpack") == b"PORTADA-BP"


def test_el_prefijo_acota_donde_se_busca(tmp_path):
    """Con prefijo se busca solo ahí: si no, el segundo pack de un zip heredaría
    la portada del primero."""
    from mcpemod.core.miniatura import de_ruta

    archivo = escribir_zip(tmp_path / "dos.zip", {
        "uno/manifest.json": "{}", "uno/pack_icon.png": b"UNO",
        "dos/manifest.json": "{}", "dos/pack_icon.png": b"DOS",
    })
    assert de_ruta(archivo, prefijo="uno/") == b"UNO"
    assert de_ruta(archivo, prefijo="dos/") == b"DOS"


def test_un_mcpack_de_descargas_da_su_portada_sin_extraerlo(tmp_path):
    from mcpemod.core.miniatura import de_ruta

    archivo = escribir_zip(tmp_path / "x.mcpack", {
        "manifest.json": json.dumps(manifiesto()), "pack_icon.png": PNG,
    })
    assert de_ruta(archivo) == PNG
