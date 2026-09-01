"""Pruebas de la activación de packs.

Lo que se comprueba aquí tiene consecuencias que el juego no explica: un
`pack_id` o una `version` que no cuadren con el manifiesto hacen que el pack
simplemente no aparezca. Por eso se valida antes de escribir, y por eso la
escritura no puede dejar el archivo a medias.
"""

import json

import pytest
from conftest import manifiesto

from mcpemod.core.activacion import (
    ErrorActivacion, Global, Mundo, Referencia, escribir, leer, mundos_de,
)
from mcpemod.core.contenido import Categoria
from mcpemod.core.mod import Forma, Instalado


def _instalado(instalacion, nombre="Bonito", uuid="u-1", version="1.2.3",
               categoria=Categoria.RECURSO, **kw):
    carpeta = (instalacion.resource_packs if categoria == Categoria.RECURSO
               else instalacion.behavior_packs) / nombre[:10]
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "manifest.json").write_text(json.dumps(manifiesto(
        nombre=nombre, uuid=uuid,
        version=tuple(int(x) for x in version.split(".")),
        tipo="resources" if categoria == Categoria.RECURSO else "data",
    )))
    (carpeta / "textura.png").write_bytes(b"\x89PNG")
    return Instalado(uuid=uuid, nombre=nombre, version=version,
                     categoria=categoria, ruta=carpeta, **kw)


@pytest.fixture
def mundo(instalacion):
    carpeta = instalacion.mundos / "bE2ZIuTv+eY="
    carpeta.mkdir(parents=True)
    (carpeta / "level.dat").write_bytes(b"nivel")
    (carpeta / "levelname.txt").write_text("DurDream")
    return Mundo(instalacion, carpeta)


# --- leer y escribir ---

def test_leer_un_archivo_de_activacion(tmp_path):
    archivo = tmp_path / "world_resource_packs.json"
    archivo.write_text(json.dumps([
        {"pack_id": "u-1", "version": [1, 2, 3], "subpack": "variante"},
        {"pack_id": "u-2", "version": [2, 0, 0]},
    ]))
    refs = leer(archivo)
    assert [r.uuid for r in refs] == ["u-1", "u-2"]
    assert refs[0].subpack == "variante"
    assert refs[1].subpack is None

def test_leer_lo_que_no_existe_o_esta_roto(tmp_path):
    assert leer(tmp_path / "no-existe.json") == []
    roto = tmp_path / "roto.json"
    roto.write_text("{esto no es json")
    assert leer(roto) == []

def test_escribir_conserva_el_orden_y_el_subpack(tmp_path):
    archivo = tmp_path / "a.json"
    escribir(archivo, [Referencia("u-1", (1, 0, 0), "v"), Referencia("u-2", (2, 0, 0))])
    datos = json.loads(archivo.read_text())
    assert [d["pack_id"] for d in datos] == ["u-1", "u-2"]
    assert datos[0]["subpack"] == "v"
    assert "subpack" not in datos[1]

def test_escribir_no_deja_temporales(tmp_path):
    archivo = tmp_path / "a.json"
    escribir(archivo, [Referencia("u-1", (1, 0, 0))])
    assert [p.name for p in tmp_path.iterdir()] == ["a.json"]


# --- global ---

def test_activar_global(instalacion):
    ambito = Global(instalacion)
    pieza = _instalado(instalacion)
    ambito.activar(pieza)

    refs = ambito.activos(Categoria.RECURSO)
    assert [(r.uuid, r.version) for r in refs] == [("u-1", (1, 2, 3))]

def test_la_version_tiene_que_cuadrar_con_el_manifiesto(instalacion):
    """Si no cuadra, el juego no carga el pack y no dice por qué."""
    ambito = Global(instalacion)
    ambito.activar(_instalado(instalacion, version="2.0.49"))
    assert ambito.activos(Categoria.RECURSO)[0].version == (2, 0, 49)

def test_activar_dos_veces_no_duplica(instalacion):
    ambito = Global(instalacion)
    pieza = _instalado(instalacion)
    ambito.activar(pieza)
    ambito.activar(pieza)
    assert len(ambito.activos(Categoria.RECURSO)) == 1

def test_desactivar_global(instalacion):
    ambito = Global(instalacion)
    pieza = _instalado(instalacion)
    ambito.activar(pieza)
    ambito.desactivar(pieza)
    assert ambito.activos(Categoria.RECURSO) == []

def test_no_hay_activacion_global_de_comportamiento(instalacion):
    """Cambian el contenido del mundo, así que van por mundo."""
    ambito = Global(instalacion)
    pieza = _instalado(instalacion, uuid="u-bp", categoria=Categoria.COMPORTAMIENTO)
    with pytest.raises(ErrorActivacion, match="comportamiento"):
        ambito.activar(pieza)

def test_el_orden_se_puede_cambiar(instalacion):
    """El último de la lista gana cuando dos packs tocan lo mismo."""
    ambito = Global(instalacion)
    for i in (1, 2, 3):
        ambito.activar(_instalado(instalacion, nombre=f"Pack{i}", uuid=f"u-{i}"))
    assert [r.uuid for r in ambito.activos(Categoria.RECURSO)] == ["u-1", "u-2", "u-3"]

    ambito.reordenar(Categoria.RECURSO, ["u-3", "u-1", "u-2"])
    assert [r.uuid for r in ambito.activos(Categoria.RECURSO)] == ["u-3", "u-1", "u-2"]

def test_reordenar_no_pierde_lo_que_no_se_menciona(instalacion):
    ambito = Global(instalacion)
    for i in (1, 2, 3):
        ambito.activar(_instalado(instalacion, nombre=f"Pack{i}", uuid=f"u-{i}"))
    ambito.reordenar(Categoria.RECURSO, ["u-3"])
    assert set(r.uuid for r in ambito.activos(Categoria.RECURSO)) == {"u-1", "u-2", "u-3"}


# --- lo que no se puede activar ---

def test_lo_de_la_tienda_no_se_activa(instalacion):
    pieza = _instalado(instalacion, de_la_tienda=True)
    with pytest.raises(ErrorActivacion, match="tienda"):
        Global(instalacion).activar(pieza)

def test_lo_que_no_esta_en_forma_de_carpeta_no_se_activa(instalacion):
    """Un `.mcpack` sin extraer no tiene qué copiarse ni qué referenciar."""
    pieza = _instalado(instalacion, forma=Forma.EMPAQUETADO)
    with pytest.raises(ErrorActivacion, match="extráelo"):
        Global(instalacion).activar(pieza)

def test_sin_uuid_o_sin_version_no_se_activa(instalacion):
    with pytest.raises(ErrorActivacion, match="uuid"):
        Global(instalacion).activar(_instalado(instalacion, uuid=""))
    with pytest.raises(ErrorActivacion, match="versión"):
        Global(instalacion).activar(
            Instalado(uuid="u", nombre="X", version=None,
                      categoria=Categoria.RECURSO, ruta=instalacion.resource_packs))


# --- mundos ---

def test_activar_en_un_mundo_copia_el_pack_dentro(instalacion, mundo):
    """Un mundo usa su copia, no la instalación: sin copiar, la entrada no sirve."""
    pieza = _instalado(instalacion)
    mundo.activar(pieza)

    assert [r.uuid for r in mundo.activos(Categoria.RECURSO)] == ["u-1"]
    copiado = list(mundo.carpeta_de(Categoria.RECURSO).iterdir())
    assert len(copiado) == 1
    assert (copiado[0] / "manifest.json").is_file()
    assert (copiado[0] / "textura.png").is_file()

def test_la_carpeta_copiada_no_pasa_de_diez_caracteres(instalacion, mundo):
    """Es requisito: por encima, en Xbox la ruta se pasa y el pack no carga."""
    pieza = _instalado(instalacion, nombre="Un nombre larguísimo de pack", uuid="u-l")
    mundo.activar(pieza)
    copiado = list(mundo.carpeta_de(Categoria.RECURSO).iterdir())
    assert len(copiado[0].name) <= 10

def test_el_mundo_admite_packs_de_comportamiento(instalacion, mundo):
    pieza = _instalado(instalacion, uuid="u-bp", nombre="ElBP",
                       categoria=Categoria.COMPORTAMIENTO)
    mundo.activar(pieza)
    assert [r.uuid for r in mundo.activos(Categoria.COMPORTAMIENTO)] == ["u-bp"]
    assert (mundo.carpeta / "world_behavior_packs.json").is_file()

def test_reactivar_reutiliza_la_copia_que_ya_estaba(instalacion, mundo):
    pieza = _instalado(instalacion)
    mundo.activar(pieza)
    nombre_original = next(mundo.carpeta_de(Categoria.RECURSO).iterdir()).name

    mundo.activar(pieza)
    copias = list(mundo.carpeta_de(Categoria.RECURSO).iterdir())
    assert [c.name for c in copias] == [nombre_original]

def test_copias_dice_que_version_tiene_el_mundo(instalacion, mundo):
    """Es lo que permite ver el desfase con lo instalado."""
    mundo.activar(_instalado(instalacion, version="1.0.0"))
    assert mundo.copias() == {"u-1": "1.0.0"}

def test_desactivar_en_un_mundo_quita_la_entrada(instalacion, mundo):
    pieza = _instalado(instalacion)
    mundo.activar(pieza)
    mundo.desactivar(pieza)
    assert mundo.activos(Categoria.RECURSO) == []

def test_quitar_la_copia_es_aparte(instalacion, mundo):
    """Desactivar deja la copia: borrarla impide volver atrás sin descargar."""
    pieza = _instalado(instalacion)
    mundo.activar(pieza)
    mundo.desactivar(pieza)
    assert list(mundo.carpeta_de(Categoria.RECURSO).iterdir())

    mundo.quitar_copia(pieza)
    assert list(mundo.carpeta_de(Categoria.RECURSO).iterdir()) == []


def test_se_listan_los_mundos_por_su_nombre(instalacion, mundo):
    otro = instalacion.mundos / "Z3wUVLhslwU="
    otro.mkdir()
    (otro / "level.dat").write_bytes(b"x")
    (otro / "levelname.txt").write_text("Aventura")
    # Una carpeta sin level.dat no es un mundo.
    (instalacion.mundos / "basura").mkdir()

    assert [m.nombre for m in mundos_de(instalacion)] == ["Aventura", "DurDream"]
