"""Pruebas de los clientes de catálogo.

No tocan la red: se les da la respuesta JSON tal como la devuelven los servicios
de verdad —recortada de una llamada real— y se comprueba que la traducción a
`Publicacion` conserva lo que la app necesita.

Lo que se prueba aquí es la traducción, que es lo que puede equivocarse en
silencio: un campo que se lee del sitio que no era da una publicación plausible
pero mal.
"""

import json

import pytest

from mcpemod.core.fuentes import CurseForge, MCPEDL
from mcpemod.core.fuentes.curseforge import _a_publicacion as cf_publicacion
from mcpemod.core.fuentes.mcpedl import _a_publicacion as mcpedl_publicacion
from mcpemod.core.red import ErrorRed, Respuesta

_MCPEDL = {
    "slug": "koth-king-of-the-hill",
    "source": "curseforge",
    "title": "Koth (King Of The Hill)",
    "short_description": "Easy to configure.",
    "url": "https://www.curseforge.com/minecraft-bedrock/addons/koth",
    "downloadCount": 783,
    "submission_id": 4346001667622,
    "display_name": "FeatherStudios",
    "username": "featherstudios",
    "update_date": "2026-08-31 06:30:48",
    "thumbnails": {"medium": "https://r2.mcpedl.com/x.png"},
    "categories": [{"name": "Addons"}, {"name": "Minigames"}],
    "downloads": [
        {"name": "Koth [v1.0.3]", "filename": "Koth [v1.0.3].mcpack",
         "downloadUrl": "https://edge.forgecdn.net/files/8775/552/Koth.mcpack",
         "fileLength": 946805, "fileDate": "2026-08-31T05:55:50.42Z"},
        {"name": "Koth [v1.0.2]", "filename": "Koth [v1.0.2].mcpack",
         "downloadUrl": "https://edge.forgecdn.net/files/8764/172/Koth2.mcpack",
         "fileLength": 942408, "fileDate": "2026-08-29T20:07:46.907Z"},
    ],
}

_CURSEFORGE = {
    "id": 1234,
    "name": "Un pack",
    "summary": "Resumen",
    "downloadCount": 900,
    "dateModified": "2026-08-30T10:00:00Z",
    "authors": [{"name": "Alguien"}],
    "links": {"websiteUrl": "https://www.curseforge.com/x"},
    "logo": {"thumbnailUrl": "https://media.forgecdn.net/x.png"},
    "categories": [{"name": "Texture Packs"}],
    "latestFiles": [
        {"displayName": "Pack v2", "fileName": "pack-v2.mcpack",
         "downloadUrl": "https://edge.forgecdn.net/files/1/2/pack.mcpack",
         "fileLength": 100, "fileDate": "2026-08-30T10:00:00Z"},
    ],
}


# --- MCPEDL ---

def test_mcpedl_traduce_lo_esencial():
    p = mcpedl_publicacion(_MCPEDL)
    assert p.fuente == "mcpedl"
    assert p.titulo == "Koth (King Of The Hill)"
    assert p.autor == "FeatherStudios"
    assert p.descargas_totales == 783
    assert p.categorias == ("Addons", "Minigames")

def test_mcpedl_la_primera_descarga_es_la_ultima():
    """El catálogo las lista de la más nueva a la más vieja."""
    p = mcpedl_publicacion(_MCPEDL)
    assert len(p.descargas) == 2
    assert p.ultima.nombre == "Koth [v1.0.3]"

def test_mcpedl_prefiere_el_nombre_visible_del_autor():
    p = mcpedl_publicacion({**_MCPEDL, "display_name": "Nombre Bonito"})
    assert p.autor == "Nombre Bonito"

def test_mcpedl_descarta_archivos_sin_url():
    p = mcpedl_publicacion({**_MCPEDL, "downloads": [{"name": "roto"}]})
    assert p.descargas == ()
    assert p.ultima is None

def test_mcpedl_publicacion_sin_nada():
    p = mcpedl_publicacion({})
    assert p.titulo == ""
    assert p.descargas == ()

def test_mcpedl_usa_el_parametro_de_busqueda_correcto(monkeypatch):
    """`search`, `q` y `query` se aceptan y se ignoran: devuelven lo último
    publicado, que parece un resultado válido. El parámetro real es `s`."""
    vistas = []

    def falsa(url, **kw):
        vistas.append(url)
        return Respuesta(200, json.dumps({"data": []}).encode(), {}, url)

    monkeypatch.setattr("mcpemod.core.fuentes.mcpedl.pedir", falsa)
    MCPEDL().buscar("hide armor")
    assert "s=hide+armor" in vistas[0]

def test_mcpedl_error_del_servicio(monkeypatch):
    monkeypatch.setattr("mcpemod.core.fuentes.mcpedl.pedir",
                        lambda url, **kw: Respuesta(503, b"", {}, url))
    with pytest.raises(ErrorRed):
        MCPEDL().buscar("x")


# --- CurseForge ---

def test_curseforge_sin_clave_no_esta_disponible():
    assert CurseForge().disponible is False
    assert CurseForge("   ").disponible is False
    assert CurseForge("una-clave").disponible is True

def test_curseforge_sin_clave_no_intenta_la_peticion():
    """Sin clave la respuesta es un 403 seguro: mejor decirlo que gastar la vuelta."""
    with pytest.raises(ErrorRed, match="clave"):
        CurseForge().buscar("x")

def test_curseforge_manda_la_clave(monkeypatch):
    vistas = []

    def falsa(url, cabeceras=None, **kw):
        vistas.append(cabeceras or {})
        return Respuesta(200, json.dumps({"data": []}).encode(), {}, url)

    monkeypatch.setattr("mcpemod.core.fuentes.curseforge.pedir", falsa)
    CurseForge("mi-clave").buscar("x")
    assert vistas[0].get("x-api-key") == "mi-clave"

def test_curseforge_clave_rechazada(monkeypatch):
    monkeypatch.setattr("mcpemod.core.fuentes.curseforge.pedir",
                        lambda url, **kw: Respuesta(403, b"", {}, url))
    with pytest.raises(ErrorRed, match="rechazó la clave"):
        CurseForge("mala").buscar("x")

def test_curseforge_traduce_lo_esencial():
    p = cf_publicacion(_CURSEFORGE)
    assert p.fuente == "curseforge"
    assert p.titulo == "Un pack"
    assert p.autor == "Alguien"
    assert p.ultima.url.endswith("pack.mcpack")


# --- fuentes disponibles ---

def test_solo_se_ofrecen_las_que_pueden_responder():
    from mcpemod.core.fuentes import fuentes_disponibles
    assert [f.nombre for f in fuentes_disponibles()] == ["mcpedl"]
    assert [f.nombre for f in fuentes_disponibles("clave")] == ["mcpedl", "curseforge"]
