"""Pruebas de persistencia SQLite (Store).

`Store` es la única capa que toca la base — si algo falla aquí, toda la app
trabaja sobre datos incorrectos. Los tests cubren:

1. Que `guardar_mod` con el mismo archivo reemplace al anterior en lugar de
   duplicarlo — sin esto la lista de instalados mostraría el mismo mod dos veces.
2. Que `buscar_por_canonico` encuentre un mod aunque su archivo tenga otra
   versión en el nombre — es lo que convierte "instalar" en "actualizar".
3. Que las rutas sobrevivan al viaje a la base: un `.mcaddon` deja varias y
   desinstalar tiene que poder borrarlas todas.
4. Que `es_nuevo()` sea estable entre sesiones (la base persiste; los tests usan
   `tmp_path` para aislarse entre sí).
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from mcpemod.core.mod import EntradaHistorial, Mod, TipoArchivo
from mcpemod.core.store import Store


@pytest.fixture
def store(tmp_path) -> Store:
    return Store(tmp_path / "test.db")


def _mod(nombre="TestMod", canonico="TestMod", archivo="testmod.so",
         version="1.0.0", rutas=None, instalado_en=None) -> Mod:
    return Mod(
        nombre=nombre,
        canonico=canonico,
        archivo=archivo,
        rutas=rutas or [Path("/tmp/testmod.so")],
        tipo=TipoArchivo.SO,
        version=version,
        hash_sha256="abc123",
        instalado=True,
        instalado_en=instalado_en or datetime.now(),
    )


# --- mods instalados ---

def test_guardar_y_listar(store):
    store.guardar_mod(_mod())
    lista = store.mods_instalados()
    assert len(lista) == 1
    assert lista[0].nombre == "TestMod"

def test_guardar_sobreescribe_duplicado(store):
    store.guardar_mod(_mod(version="1.0.0"))
    store.guardar_mod(_mod(version="2.0.0"))
    lista = store.mods_instalados()
    assert len(lista) == 1
    assert lista[0].version == "2.0.0"

def test_eliminar_mod(store):
    store.guardar_mod(_mod())
    store.eliminar_mod("testmod.so")
    assert store.mods_instalados() == []

def test_rutas_multiples_sobreviven(store):
    rutas = [Path("/packs/uno"), Path("/behavior/dos")]
    store.guardar_mod(_mod(archivo="addon.mcaddon", rutas=rutas))
    assert store.mods_instalados()[0].rutas == rutas

def test_buscar_por_canonico(store):
    store.guardar_mod(_mod(nombre="MyMod-v1.0.0", canonico="MyMod", archivo="MyMod-v1.0.0.so"))
    encontrado = store.buscar_por_canonico("MyMod")
    assert encontrado is not None
    assert encontrado.nombre == "MyMod-v1.0.0"

def test_buscar_por_canonico_devuelve_el_mas_reciente(store):
    ayer = datetime.now() - timedelta(days=1)
    store.guardar_mod(_mod(archivo="viejo.so", version="1.0.0", instalado_en=ayer))
    store.guardar_mod(_mod(archivo="nuevo.so", version="2.0.0"))
    assert store.buscar_por_canonico("TestMod").version == "2.0.0"

def test_buscar_por_canonico_no_encontrado(store):
    assert store.buscar_por_canonico("NoExiste") is None

def test_buscar_por_archivo(store):
    store.guardar_mod(_mod())
    assert store.buscar_por_archivo("testmod.so") is not None
    assert store.buscar_por_archivo("otro.so") is None


# --- historial ---

def test_registrar_historial(store):
    store.registrar(EntradaHistorial("instalar", "testmod.so", "1.0.0", None))
    hist = store.historial()
    assert len(hist) == 1
    assert hist[0].accion == "instalar"

def test_historial_orden_descendente(store):
    for accion in ("instalar", "actualizar", "desinstalar"):
        store.registrar(EntradaHistorial(accion, "x.so", "1.0", None))
    hist = store.historial()
    assert hist[0].accion == "desinstalar"
    assert hist[-1].accion == "instalar"

def test_historial_desempata_por_id(store):
    # Tres registros en el mismo milisegundo tienen el mismo timestamp; sin el
    # desempate por id el orden sería el que le apetezca a SQLite.
    ts = datetime.now()
    for accion in ("instalar", "actualizar", "desinstalar"):
        store.registrar(EntradaHistorial(accion, "x.so", "1.0", None, timestamp=ts))
    assert [e.accion for e in store.historial()] == ["desinstalar", "actualizar", "instalar"]


# --- vistos (badge NEW) ---

def test_es_nuevo_sin_marcar(store):
    assert store.es_nuevo("hash_desconocido") is True

def test_marcar_visto_y_comprobar(store):
    store.marcar_visto("hash_abc")
    assert store.es_nuevo("hash_abc") is False

def test_marcar_visto_idempotente(store):
    store.marcar_visto("hash_abc")
    store.marcar_visto("hash_abc")
    assert store.es_nuevo("hash_abc") is False


# --- migración desde el esquema inicial ---

def test_migracion_desde_esquema_v1(tmp_path):
    """Una base creada por la primera versión tiene `ruta` y no `canonico`.

    Vive en `~/.local/share/` y sobrevive a las reinstalaciones, así que abrirla
    con el esquema nuevo no puede perder lo que ya había registrado.
    """
    db = tmp_path / "v1.db"
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE mods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL, archivo TEXT NOT NULL UNIQUE, tipo TEXT NOT NULL,
            version TEXT, hash TEXT NOT NULL, ruta TEXT NOT NULL,
            instalado_en TEXT NOT NULL
        );
    """)
    con.execute(
        "INSERT INTO mods (nombre, archivo, tipo, version, hash, ruta, instalado_en) "
        "VALUES ('MyMod-v1.0.0', 'MyMod-v1.0.0.so', '.so', '1.0.0', 'h', '/mods/x.so', ?)",
        (datetime.now().isoformat(),),
    )
    con.commit()
    con.close()

    mods = Store(db).mods_instalados()
    assert len(mods) == 1
    assert mods[0].canonico == "MyMod"
    assert mods[0].rutas == [Path("/mods/x.so")]
