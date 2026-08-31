"""Pruebas de la base: historial, origen de cada pack y archivos vistos.

Lo instalado no se guarda aquí — la fuente de verdad es el disco. La base guarda
lo que el disco no sabe: qué pasó y cuándo, y de qué archivo salió cada pack.
"""

from datetime import datetime

from mcpemod.core.mod import EntradaHistorial


# --- historial ---

def test_registrar_y_leer(store):
    store.registrar(EntradaHistorial("instalar", "Bonito", "Recursos", "1.0.0", None,
                                     uuid="u"))
    hist = store.historial()
    assert len(hist) == 1
    assert (hist[0].accion, hist[0].nombre, hist[0].categoria) == ("instalar", "Bonito", "Recursos")

def test_orden_descendente(store):
    for accion in ("instalar", "actualizar", "desinstalar"):
        store.registrar(EntradaHistorial(accion, "X", "Recursos", "1.0", None))
    assert [e.accion for e in store.historial()] == ["desinstalar", "actualizar", "instalar"]

def test_desempata_por_id(store):
    """Tres registros en el mismo instante tienen el mismo timestamp."""
    ts = datetime.now()
    for accion in ("instalar", "actualizar", "reparar"):
        store.registrar(EntradaHistorial(accion, "X", "Recursos", "1.0", None, timestamp=ts))
    assert [e.accion for e in store.historial()] == ["reparar", "actualizar", "instalar"]

def test_limite(store):
    for n in range(10):
        store.registrar(EntradaHistorial("instalar", f"P{n}", "Recursos", "1.0", None))
    assert len(store.historial(limite=3)) == 3


# --- origen ---

def test_recordar_de_donde_vino_un_pack(store):
    store.registrar_origen("u-1", "Hide Armor - [ v1.2 ].mcpack")
    archivo, cuando = store.origenes()["u-1"]
    assert archivo == "Hide Armor - [ v1.2 ].mcpack"
    assert isinstance(cuando, datetime)

def test_reinstalar_actualiza_el_origen(store):
    store.registrar_origen("u-1", "viejo.mcpack")
    store.registrar_origen("u-1", "nuevo.mcpack")
    assert store.origenes()["u-1"][0] == "nuevo.mcpack"

def test_olvidar_origen(store):
    store.registrar_origen("u-1", "x.mcpack")
    store.olvidar_origen("u-1")
    assert store.origenes() == {}


# --- vistos ---

def test_es_nuevo_sin_marcar(store):
    assert store.es_nuevo("hash_desconocido") is True

def test_marcar_visto(store):
    store.marcar_visto("hash_abc")
    assert store.es_nuevo("hash_abc") is False

def test_marcar_visto_idempotente(store):
    store.marcar_visto("hash_abc")
    store.marcar_visto("hash_abc")
    assert store.es_nuevo("hash_abc") is False


# --- esquema anterior ---

def test_base_del_gestor_anterior_se_abre(tmp_path):
    """La primera versión indexaba por nombre de archivo y guardaba los mods en
    una tabla `mods`. La identidad correcta —el uuid— no está ahí ni se puede
    deducir, así que esa tabla se descarta; el historial se conserva.
    """
    import sqlite3

    from mcpemod.core.store import Store

    db = tmp_path / "vieja.db"
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE mods (id INTEGER PRIMARY KEY, nombre TEXT, archivo TEXT UNIQUE,
                           tipo TEXT, version TEXT, hash TEXT, ruta TEXT,
                           instalado_en TEXT);
        CREATE TABLE historial (id INTEGER PRIMARY KEY AUTOINCREMENT, accion TEXT NOT NULL,
                                archivo TEXT NOT NULL, version TEXT,
                                version_anterior TEXT, timestamp TEXT NOT NULL);
        CREATE TABLE vistos (hash TEXT PRIMARY KEY);
    """)
    con.execute("INSERT INTO mods VALUES (1,'M','m.so','.so','1.0','h','/x', ?)",
                (datetime.now().isoformat(),))
    con.execute("INSERT INTO historial (accion, archivo, version, version_anterior, timestamp)"
                " VALUES ('instalar','m.so','1.0',NULL,?)", (datetime.now().isoformat(),))
    con.execute("INSERT INTO vistos VALUES ('hash_viejo')")
    con.commit()
    con.close()

    store = Store(db)
    assert store.es_nuevo("hash_viejo") is False
    hist = store.historial()
    assert [(e.accion, e.nombre) for e in hist] == [("instalar", "m.so")]
    assert hist[0].uuid == ""


def test_base_sin_las_columnas_nuevas_se_migra(tmp_path):
    """`CREATE TABLE IF NOT EXISTS` no toca una tabla que ya existe.

    Sin migrar, una base de una versión anterior falla **al escribir**, no al
    abrir: el error aparece lejos, en mitad de una comprobación, y desde la app
    se ve como «cero resultados».
    """
    import sqlite3

    from mcpemod.core.store import Store

    db = tmp_path / "anterior.db"
    con = sqlite3.connect(db)
    con.execute("""
        CREATE TABLE emparejamientos (
            uuid TEXT PRIMARY KEY, encontrado INTEGER NOT NULL, fuente TEXT,
            id_publicacion TEXT, titulo TEXT, autor TEXT, url_publicacion TEXT,
            version_remota TEXT, url_descarga TEXT, nombre_archivo TEXT,
            comprobado_en TEXT NOT NULL
        )
    """)
    con.execute(
        "INSERT INTO emparejamientos (uuid, encontrado, titulo, comprobado_en)"
        " VALUES ('viejo', 1, 'Ya estaba', ?)", (datetime.now().isoformat(),)
    )
    con.commit()
    con.close()

    store = Store(db)
    store.guardar_emparejamiento("u-1", encontrado=True, titulo="Nuevo",
                                 confianza="confirmado", uuid_remoto="v-9")

    guardados = store.emparejamientos()
    assert guardados["u-1"]["uuid_remoto"] == "v-9"
    assert guardados["u-1"]["confianza"] == "confirmado"
    # Y lo que ya había sigue ahí.
    assert guardados["viejo"]["titulo"] == "Ya estaba"
