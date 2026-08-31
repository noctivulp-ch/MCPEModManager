"""Pruebas del emparejamiento entre lo instalado y lo publicado.

Ningún catálogo indexa por `header.uuid`, así que el emparejamiento va al revés:
se buscan candidatos por título y autor, y se **confirma** leyendo el manifiesto
publicado. Lo que se prueba aquí es que solo el positivo cuenta —un candidato
que no se pueda leer nunca produce un emparejamiento— y que el coste está
acotado, porque sin eso una comprobación de sesenta packs no termina.

No tocan la red: el catálogo y la lectura remota son dobles.
"""

import pytest

from mcpemod.core import actualizaciones
from mcpemod.core.actualizaciones import (
    MAX_LECTURAS, Buscador, Confianza, _consultas, _ordenar, _sin_adornos,
)
from mcpemod.core.contenido import Categoria
from mcpemod.core.fuentes import Descarga, Publicacion
from mcpemod.core.manifiesto import Manifiesto
from mcpemod.core.mod import Instalado
from mcpemod.core.red import ErrorRed
from mcpemod.core.version import EstadoVersion


def _instalado(nombre="Bonito", uuid="u-1", version="1.0.0", autores=("Alguien",), **kw):
    return Instalado(
        uuid=uuid, nombre=nombre, version=version, categoria=Categoria.RECURSO,
        ruta=__import__("pathlib").Path("/tmp/x"), autores=autores, **kw
    )


def _publicacion(titulo="Bonito", autor="Alguien", id="p-1", url_archivo="https://cdn/a.mcpack",
                 descargas_totales=0):
    return Publicacion(
        fuente="falsa", id=id, titulo=titulo, autor=autor,
        url=f"https://catalogo/{id}", descargas_totales=descargas_totales,
        descargas=(Descarga(nombre="a.mcpack", url=url_archivo),),
    )


def _manifiesto(uuid, version="2.0.0", nombre="Bonito"):
    return Manifiesto(uuid=uuid, nombre=nombre, version=version,
                      tipos=frozenset({"resources"}))


class FuenteFalsa:
    nombre = "falsa"
    etiqueta = "Falsa"

    def __init__(self, por_consulta=None, error=False):
        self._por_consulta = por_consulta or {}
        self._error = error
        self.consultas = []

    @property
    def disponible(self):
        return True

    def buscar(self, texto, pagina=1, por_pagina=20):
        self.consultas.append(texto)
        if self._error:
            raise ErrorRed("sin red")
        return self._por_consulta.get(texto, [])

    def recientes(self, pagina=1, por_pagina=20):
        return []


@pytest.fixture
def remoto(monkeypatch):
    """Sustituye la lectura del manifiesto publicado y cuenta las llamadas."""
    estado = {"por_url": {}, "llamadas": []}

    def leer(url):
        estado["llamadas"].append(url)
        m = estado["por_url"].get(url)
        return [m] if m else []

    monkeypatch.setattr(actualizaciones, "leer_manifiestos", leer)
    return estado


# --- limpieza de nombres y consultas ---

def test_sin_adornos_quita_la_version():
    assert _sin_adornos("Better Trees by Daniye v1.4.0") == "Better Trees by Daniye"

def test_sin_adornos_quita_corchetes_y_barras():
    assert _sin_adornos("Hide Armor | V1.2") == "Hide Armor"
    assert _sin_adornos("CSO Terrorists V1.0 [RP]") == "CSO Terrorists"

def test_consultas_van_de_lo_especifico_a_lo_general():
    """Un título largo no encuentra nada: el catálogo exige todas las palabras."""
    consultas = _consultas(_instalado(nombre="Better Foliage Texture Pack NG"))
    assert consultas[0] == "Better Foliage Texture Pack NG"
    assert "Better Foliage Texture" in consultas
    assert "Better Foliage" in consultas

def test_consultas_sin_repetidos():
    consultas = _consultas(_instalado(nombre="Stay True"))
    assert len(consultas) == len(set(consultas))


# --- orden de candidatos ---

def test_el_mismo_autor_va_primero():
    """Es la señal más barata y la que más acierta: el catálogo está lleno de
    reediciones con el mismo nombre."""
    pieza = _instalado(nombre="Bonito", autores=("Athan213",))
    candidatos = [
        _publicacion(titulo="Bonito", autor="Otro", id="p-otro", descargas_totales=9999),
        _publicacion(titulo="Bonito", autor="Athan213", id="p-bueno"),
    ]
    assert _ordenar(candidatos, pieza)[0].id == "p-bueno"

def test_a_igualdad_de_autor_manda_el_titulo():
    pieza = _instalado(nombre="Bonito", autores=())
    candidatos = [
        _publicacion(titulo="Bonito Deluxe Remasterizado", id="p-largo"),
        _publicacion(titulo="Bonito", id="p-exacto"),
    ]
    assert _ordenar(candidatos, pieza)[0].id == "p-exacto"


# --- confirmación por uuid ---

def test_confirma_y_detecta_la_version_nueva(store, remoto):
    remoto["por_url"]["https://cdn/a.mcpack"] = _manifiesto("u-2", "2.0.0", "Bonito")
    fuente = FuenteFalsa({"Bonito": [_publicacion()]})

    r = Buscador(store, [fuente]).comprobar(_instalado(uuid="u-1", version="1.0.0"))
    assert r.confianza is Confianza.CONFIRMADO
    assert r.version_remota == "2.0.0"
    assert r.estado == EstadoVersion.NUEVA
    assert r.hay_actualizacion

def test_otro_pack_no_confirma(store, remoto):
    """Ni el uuid ni el nombre coinciden: es otro pack."""
    remoto["por_url"]["https://cdn/a.mcpack"] = _manifiesto("otro-uuid", nombre="Otra cosa")
    fuente = FuenteFalsa({"Bonito": [_publicacion(autor="Ajeno")]})

    r = Buscador(store, [fuente]).comprobar(_instalado(uuid="u-1"))
    assert r.confianza is not Confianza.CONFIRMADO

def test_confirma_por_nombre_aunque_cambie_el_uuid(store, remoto):
    """Hay autores que cambian el uuid en cada versión; el nombre es lo estable."""
    remoto["por_url"]["https://cdn/a.mcpack"] = _manifiesto("uuid-nuevo", "2.0.0", "Bonito")
    fuente = FuenteFalsa({"Bonito": [_publicacion()]})

    r = Buscador(store, [fuente]).comprobar(_instalado(uuid="uuid-viejo", version="1.0.0"))
    assert r.confianza is Confianza.CONFIRMADO
    assert r.hay_actualizacion

def test_confirma_por_uuid_aunque_cambie_el_nombre(store, remoto):
    """Otros meten la versión en el nombre y mantienen el uuid."""
    remoto["por_url"]["https://cdn/a.mcpack"] = _manifiesto("u-1", "1.3.1", "Hide Armor | V1.3.1")
    fuente = FuenteFalsa({"Hide Armor | V1.2": [_publicacion(titulo="Hide Armor")]})

    r = Buscador(store, [fuente]).comprobar(
        _instalado(nombre="Hide Armor | V1.2", uuid="u-1", version="1.2.0"))
    assert r.confianza is Confianza.CONFIRMADO

def test_el_mismo_uuid_publicado_no_es_una_actualizacion(store, remoto):
    """Si el uuid es el mismo, es la versión que ya está — diga lo que diga el
    número de versión, que algunos autores suben sin cambiar el contenido."""
    remoto["por_url"]["https://cdn/a.mcpack"] = _manifiesto("u-1", "9.9.9")
    fuente = FuenteFalsa({"Bonito": [_publicacion()]})

    r = Buscador(store, [fuente]).comprobar(_instalado(uuid="u-1", version="1.0.0"))
    assert r.misma_version
    assert not r.hay_actualizacion

def test_no_encontrado_si_no_hay_candidatos(store, remoto):
    r = Buscador(store, [FuenteFalsa()]).comprobar(_instalado())
    assert not r.encontrado
    assert r.estado == EstadoVersion.DESCONOCIDA

def test_un_archivo_ilegible_no_empareja(store, remoto):
    """Que no se pueda leer significa «no confirmado», no «es este»."""
    fuente = FuenteFalsa({"Bonito": [_publicacion()]})
    r = Buscador(store, [fuente]).comprobar(_instalado(uuid="u-1", autores=()))
    assert r.confianza is Confianza.NINGUNO


# --- coincidencia probable ---

def test_mismo_autor_y_titulo_pero_otro_pack_es_probable(store, remoto):
    """El manifiesto publicado no confirma, pero el parecido es fuerte."""
    remoto["por_url"]["https://cdn/a.mcpack"] = _manifiesto("uuid-nuevo", nombre="Otra cosa")
    fuente = FuenteFalsa({"Bonito": [_publicacion(titulo="Bonito", autor="Alguien")]})

    r = Buscador(store, [fuente]).comprobar(_instalado(uuid="u-viejo", autores=("Alguien",)))
    assert r.confianza is Confianza.PROBABLE
    assert r.encontrado

def test_una_probable_no_cuenta_como_actualizacion(store, remoto):
    """Instalarla encima podría sobrescribir con un pack que no es el mismo."""
    remoto["por_url"]["https://cdn/a.mcpack"] = _manifiesto("uuid-nuevo", nombre="Otra cosa")
    fuente = FuenteFalsa({"Bonito": [_publicacion(autor="Alguien")]})

    r = Buscador(store, [fuente]).comprobar(_instalado(uuid="u-viejo", version="1.0.0"))
    assert r.confianza is Confianza.PROBABLE
    assert r.hay_actualizacion is False

def test_sin_autor_no_hay_probable(store, remoto):
    """Solo el título es demasiado poco: el catálogo está lleno de homónimos."""
    remoto["por_url"]["https://cdn/a.mcpack"] = _manifiesto("uuid-nuevo", nombre="Otra cosa")
    fuente = FuenteFalsa({"Bonito": [_publicacion(autor="Cualquiera")]})

    r = Buscador(store, [fuente]).comprobar(_instalado(uuid="u-1", autores=()))
    assert r.confianza is Confianza.NINGUNO


# --- coste acotado ---

def test_no_pasa_del_presupuesto_de_lecturas(store, remoto):
    """Sin techo, un pack con candidatos pesados se lleva minutos él solo."""
    muchos = [_publicacion(titulo="Otro", autor="Nadie", id=f"p-{i}",
                           url_archivo=f"https://cdn/{i}.mcpack") for i in range(20)]
    fuente = FuenteFalsa({c: muchos for c in _consultas(_instalado(nombre="Bonito Pack Grande"))})

    Buscador(store, [fuente]).comprobar(_instalado(nombre="Bonito Pack Grande", autores=()))
    assert len(remoto["llamadas"]) <= MAX_LECTURAS

def test_solo_se_mira_el_archivo_mas_reciente(store, remoto):
    """Las versiones viejas llevan el mismo uuid: no aportan y cada una cuesta."""
    publicacion = Publicacion(
        fuente="falsa", id="p", titulo="Bonito", autor="Alguien", url="u",
        descargas=tuple(
            Descarga(nombre=f"v{i}", url=f"https://cdn/{i}.mcpack") for i in range(5)
        ),
    )
    fuente = FuenteFalsa({"Bonito": [publicacion]})
    Buscador(store, [fuente]).comprobar(_instalado(uuid="u-1", autores=()))
    assert len(remoto["llamadas"]) == 1


# --- caché ---

def test_lo_encontrado_se_recuerda(store, remoto):
    remoto["por_url"]["https://cdn/a.mcpack"] = _manifiesto("u-1", "2.0.0")
    fuente = FuenteFalsa({"Bonito": [_publicacion()]})
    pieza = _instalado(uuid="u-1")

    Buscador(store, [fuente]).comprobar(pieza)
    guardados = Buscador(store, [fuente]).desde_cache([pieza])
    assert [g.version_remota for g in guardados] == ["2.0.0"]

def test_lo_no_encontrado_tambien_se_recuerda(store, remoto):
    """Volver a buscar en cada arranque los packs que no están en ningún
    catálogo es la mayor parte del coste, y no cambia de un día para otro."""
    pieza = _instalado(uuid="u-1")
    Buscador(store, [FuenteFalsa()]).comprobar(pieza)

    fuente = FuenteFalsa()
    assert Buscador(store, [fuente]).pendientes([pieza]) == []

def test_lo_ya_comprobado_no_vuelve_a_pendientes(store, remoto):
    remoto["por_url"]["https://cdn/a.mcpack"] = _manifiesto("u-1")
    fuente = FuenteFalsa({"Bonito": [_publicacion()]})
    pieza = _instalado(uuid="u-1")
    b = Buscador(store, [fuente])

    assert b.pendientes([pieza]) == [pieza]
    b.comprobar(pieza)
    assert b.pendientes([pieza]) == []

def test_lo_nunca_visto_se_comprueba_primero(store, remoto):
    """Es donde está toda la información nueva."""
    remoto["por_url"]["https://cdn/a.mcpack"] = _manifiesto("u-1")
    fuente = FuenteFalsa({"Bonito": [_publicacion()]})
    visto, nuevo = _instalado(uuid="u-1"), _instalado(uuid="u-2", nombre="Aaa")
    b = Buscador(store, [fuente])
    b.comprobar(visto)

    assert b.pendientes([visto, nuevo])[0].uuid == "u-2"


# --- qué se comprueba y qué no ---

def test_lo_de_la_tienda_no_se_comprueba(store):
    """Lo gestiona el juego y no está en los catálogos públicos."""
    pieza = _instalado(uuid="u-1", de_la_tienda=True)
    assert Buscador(store, [FuenteFalsa()]).pendientes([pieza]) == []

def test_sin_uuid_no_se_comprueba(store):
    """Un mundo no tiene manifiesto: no hay nada con lo que confirmar."""
    pieza = _instalado(uuid="")
    assert Buscador(store, [FuenteFalsa()]).pendientes([pieza]) == []

def test_sin_version_no_se_comprueba(store):
    pieza = _instalado(version=None)
    assert Buscador(store, [FuenteFalsa()]).pendientes([pieza]) == []


# --- errores ---

def test_sin_red_no_inventa_resultados(store, remoto):
    r = Buscador(store, [FuenteFalsa(error=True)]).comprobar(_instalado())
    assert not r.encontrado
