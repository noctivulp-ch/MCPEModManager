"""Pruebas de la lectura de un pack publicado sin descargarlo entero.

No tocan la red: se sirve un zip en memoria a través de un `pedir` falso que
respeta `Range` igual que un CDN. Lo que se prueba es que se lee el manifiesto
correcto gastando pocas peticiones, y que un archivo que no es un pack se
descarta en vez de dar un resultado inventado.
"""

import io
import json
import zipfile

import pytest
from conftest import manifiesto

from mcpemod.core import zip_remoto
from mcpemod.core.red import ErrorRed, Respuesta


def _zip(miembros: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for nombre, datos in miembros.items():
            zf.writestr(nombre, datos if isinstance(datos, bytes) else str(datos))
    return buf.getvalue()


def _pack_bytes(**kwargs) -> bytes:
    return _zip({
        "manifest.json": json.dumps(manifiesto(**kwargs)),
        # Relleno para que el manifiesto y el directorio central caigan en
        # bloques distintos, como en un pack real.
        "textura.png": b"\x89PNG" + b"\x00" * 90_000,
    })


@pytest.fixture
def servidor(monkeypatch):
    """Un CDN falso que sirve Range, y cuenta las peticiones que recibe."""
    estado = {"cuerpo": b"", "peticiones": 0, "admite_range": True, "codigo": 200}

    def pedir(url, cabeceras=None, metodo="GET", **kw):
        estado["peticiones"] += 1
        cuerpo = estado["cuerpo"]
        if estado["codigo"] != 200:
            return Respuesta(estado["codigo"], b"", {}, url)
        if metodo == "HEAD":
            cabeceras_r = {"content-length": str(len(cuerpo))}
            if estado["admite_range"]:
                cabeceras_r["accept-ranges"] = "bytes"
            return Respuesta(200, b"", cabeceras_r, url)

        rango = (cabeceras or {}).get("Range", "")
        inicio, _, fin = rango.removeprefix("bytes=").partition("-")
        i, f = int(inicio), int(fin)
        return Respuesta(206, cuerpo[i:f + 1], {}, url)

    monkeypatch.setattr(zip_remoto, "pedir", pedir)
    return estado


# --- lectura ---

def test_lee_el_manifiesto_de_un_pack(servidor):
    servidor["cuerpo"] = _pack_bytes(nombre="Bonito", uuid="u-1", version=(1, 2, 3))
    m = zip_remoto.leer_manifiesto("https://cdn/x.mcpack")
    assert (m.uuid, m.nombre, m.version) == ("u-1", "Bonito", "1.2.3")

def test_no_descarga_el_archivo_entero(servidor):
    """Es la razón de existir de todo esto: leer el uuid sin bajar el pack."""
    servidor["cuerpo"] = _pack_bytes(nombre="Bonito", uuid="u-1")
    zip_remoto.leer_manifiesto("https://cdn/x.mcpack")
    assert servidor["peticiones"] <= 4

def test_servidor_sin_range_no_inventa_resultado(servidor):
    servidor["cuerpo"] = _pack_bytes(uuid="u-1")
    servidor["admite_range"] = False
    assert zip_remoto.leer_manifiesto("https://cdn/x.mcpack") is None

def test_archivo_que_no_es_zip(servidor):
    servidor["cuerpo"] = b"esto no es un zip" * 100
    assert zip_remoto.leer_manifiestos("https://cdn/x.mcpack") == []

def test_zip_sin_manifiesto_de_bedrock(servidor):
    servidor["cuerpo"] = _zip({"leeme.txt": "hola"})
    assert zip_remoto.leer_manifiestos("https://cdn/x.zip") == []

def test_modpack_de_java_no_cuenta(servidor):
    servidor["cuerpo"] = _zip({
        "manifest.json": json.dumps({"manifestType": "minecraftModpack", "name": "X"}),
    })
    assert zip_remoto.leer_manifiestos("https://cdn/x.zip") == []

def test_error_del_servidor(servidor):
    servidor["codigo"] = 404
    assert zip_remoto.leer_manifiestos("https://cdn/x.mcpack") == []


# --- addons ---

def test_lee_los_manifiestos_dentro_de_un_addon(servidor):
    """Muchos packs se publican como `.mcaddon`, sin manifiesto propio: lo que
    los identifica son los de los packs que llevan dentro."""
    rp = _zip({"manifest.json": json.dumps(manifiesto(nombre="RP", uuid="u-rp"))})
    bp = _zip({"manifest.json": json.dumps(manifiesto(nombre="BP", uuid="u-bp", tipo="data"))})
    servidor["cuerpo"] = _zip({"RP.mcpack": rp, "BP.mcpack": bp})

    uuids = {m.uuid for m in zip_remoto.leer_manifiestos("https://cdn/x.mcaddon")}
    assert uuids == {"u-rp", "u-bp"}

def test_un_anidado_enorme_se_salta(servidor, monkeypatch):
    monkeypatch.setattr(zip_remoto, "_MAX_ANIDADO", 10)
    rp = _zip({"manifest.json": json.dumps(manifiesto(uuid="u-rp"))})
    servidor["cuerpo"] = _zip({"RP.mcpack": rp})
    assert zip_remoto.leer_manifiestos("https://cdn/x.mcaddon") == []

def test_anidado_corrupto_no_rompe_el_resto(servidor):
    bueno = _zip({"manifest.json": json.dumps(manifiesto(uuid="u-ok"))})
    servidor["cuerpo"] = _zip({"roto.mcpack": b"no soy un zip", "bien.mcpack": bueno})
    assert [m.uuid for m in zip_remoto.leer_manifiestos("https://cdn/x.mcaddon")] == ["u-ok"]


# --- ArchivoRemoto ---

def test_tamano_cero_se_rechaza(servidor):
    servidor["cuerpo"] = b""
    with pytest.raises(ErrorRed):
        zip_remoto.ArchivoRemoto("https://cdn/x")

def test_las_lecturas_repetidas_no_repiten_peticiones(servidor):
    servidor["cuerpo"] = _pack_bytes(uuid="u-1")
    remoto = zip_remoto.ArchivoRemoto("https://cdn/x.mcpack")
    remoto.seek(0)
    remoto.read(100)
    antes = remoto.peticiones
    remoto.seek(0)
    remoto.read(100)
    assert remoto.peticiones == antes
