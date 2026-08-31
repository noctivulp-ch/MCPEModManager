"""Punto de entrada de MCPE Mod Manager."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

# `wulf_qt` es una librería local sin instalar. Nuitka la bundlea en el binario,
# así que solo se busca en disco cuando el import falla — de lo contrario el
# ejecutable intentaría abrir una ruta del entorno de desarrollo.
try:
    importlib.import_module("wulf_qt")
except ImportError:
    _RAIZ = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(_RAIZ / "#Libs/wulfenite_ui/PyQT/src"))

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from wulf_qt import Acento, Modo, aplicar  # noqa: E402

from mcpemod.core import DB_PATH, Installer, Scanner, Store, detectar_instalaciones  # noqa: E402
from mcpemod.ui import VentanaPrincipal  # noqa: E402

_SIN_JUEGO = (
    "No encontré ninguna instalación de Minecraft Bedrock.\n\n"
    "Se busca la carpeta games/com.mojang de mcpelauncher, tanto en la\n"
    "instalación nativa (~/.local/share/mcpelauncher) como en las flatpak."
)


def _diagnostico() -> int:
    """Informe de por qué la app ve —o no ve— lo que ve.

    Existe porque los fallos que más cuestan de entender son los que no dan
    error: una comprobación que no encuentra nada puede ser que no haya nada,
    que no haya red, o que el binario compilado no lleve los certificados.
    """
    from mcpemod.core import Scanner, carpeta_descargas
    from mcpemod.core.fuentes import fuentes_disponibles
    from mcpemod.core.red import ErrorRed, pedir

    print(f"Python      : {sys.version.split()[0]}")
    print(f"Compilado   : {'sí' if '__compiled__' in globals() else 'no'}")
    print(f"Descargas   : {carpeta_descargas()}")

    instalaciones = detectar_instalaciones()
    print(f"\nInstalaciones ({len(instalaciones)}):")
    for i in instalaciones:
        print(f"  {i.nombre:<26} {i.contar_contenido():>3} elementos  {i.com_mojang}")
    if not instalaciones:
        return 1

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    store = Store(DB_PATH)
    scanner = Scanner(store, instalaciones[0])
    piezas = scanner.leer_instalados()
    print(f"\nInstalado en «{instalaciones[0].nombre}»: {len(piezas)} elementos")
    print(f"  con uuid y versión (comprobables): "
          f"{sum(1 for p in piezas if p.gestionable and p.uuid and p.version)}")
    print(f"  de la tienda (no se comprueban)  : {sum(1 for p in piezas if not p.gestionable)}")

    guardados = store.emparejamientos()
    print(f"\nEmparejamientos guardados: {len(guardados)}"
          f"  ({sum(1 for g in guardados.values() if g['encontrado'])} encontrados)")

    print("\nRed:")
    for etiqueta, url in (("MCPEDL (API)", "https://api.mcpedl.com/api/submissions?per_page=1"),
                          ("CDN de packs", "https://edge.forgecdn.net/")):
        try:
            r = pedir(url)
            print(f"  {etiqueta:<14} HTTP {r.codigo}  {len(r.cuerpo)} bytes")
        except ErrorRed as e:
            print(f"  {etiqueta:<14} FALLA — {e}")

    print(f"\nFuentes disponibles: {[f.etiqueta for f in fuentes_disponibles(store.ajuste('clave_curseforge'))]}")

    if "--comprobar" in sys.argv or "--comprobar-todo" in sys.argv:
        _probar_comprobacion(store, scanner, todos="--comprobar-todo" in sys.argv)
    return 0


def _probar_comprobacion(store, scanner, todos: bool = False) -> None:
    """Un barrido corto de verdad, con la misma maquinaria que usa la pestaña.

    Es lo que el resto del diagnóstico no cubre: que el trabajo de fondo funcione
    **en el ejecutable**, con red y con la base real. Un fallo de esquema o de
    empaquetado no se ve de otra forma — desde dentro de la app se manifiesta
    como «cero resultados».
    """
    import traceback

    from PySide6.QtCore import QCoreApplication, QElapsedTimer

    from mcpemod.core.actualizaciones import Buscador
    from mcpemod.core.fuentes import fuentes_disponibles
    from mcpemod.ui.tareas import Tarea
    from mcpemod.ui.trabajo import comprobar_todos

    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    buscador = Buscador(store, fuentes_disponibles(store.ajuste("clave_curseforge")))
    pendientes = buscador.pendientes(scanner.leer_instalados())
    if not todos:
        pendientes = pendientes[:4]
    if not pendientes:
        print("\nNada que comprobar: todo está comprobado hace poco.")
        return

    # Primero uno sin hilo ni pool, para que un fallo se vea entero en vez de
    # quedarse contado como «uno que falló».
    print(f"\nComprobando {len(pendientes)} packs con la maquinaria de la pestaña.")
    print(f"  [directo] {pendientes[0].nombre[:44]}")
    try:
        r = buscador.comprobar(pendientes[0])
        print(f"  [directo] confianza={r.confianza.value}  remota={r.version_remota}")
    except Exception as e:  # noqa: BLE001 - es un diagnóstico: se quiere ver todo
        print(f"  [directo] EXCEPCIÓN {type(e).__name__}: {e}")
        traceback.print_exc()

    recibidos: list = []
    tarea = Tarea()
    tarea.lanzar(
        lambda emitir, cancelado: comprobar_todos(buscador, pendientes, emitir, cancelado),
        recibidos.append,
    )

    reloj = QElapsedTimer()
    reloj.start()
    limite = 900_000 if todos else 120_000
    while tarea.corriendo and reloj.elapsed() < limite:
        app.processEvents()
    app.processEvents()
    tarea.parar()

    encontrados = [m for m in recibidos if m[0] == "encontrado"]
    for _, resultado in encontrados:
        print(f"  {resultado.pieza.nombre[:38]:<38} "
              f"v{resultado.pieza.version} → v{resultado.version_remota}")

    fin = [m for m in recibidos if m[0] == "terminado"]
    print(f"  → {len(encontrados)} encontrados de {len(pendientes)}")
    if fin and fin[0][2]:
        print(f"  → error: {fin[0][2]}")
    if not recibidos:
        print("  → NADA llegó del hilo de trabajo")


def _trabajo_en_segundo_plano_funciona(app: QApplication) -> bool:
    """Comprueba el camino entero de una tarea de fondo, sin tocar la red.

    Es lo que el arranque a secas no cubre: los hilos solo entran en juego al
    pulsar un botón, y ahí es donde ha fallado el binario compilado más de una
    vez sin que la comprobación se enterara.
    """
    from PySide6.QtCore import QElapsedTimer

    from mcpemod.ui.tareas import Tarea

    recibidos: list = []
    tarea = Tarea()
    tarea.lanzar(lambda emitir, cancelado: emitir("ok"), recibidos.append)

    reloj = QElapsedTimer()
    reloj.start()
    while not recibidos and reloj.elapsed() < 5000:
        app.processEvents()

    tarea.parar()
    return bool(recibidos)


def main() -> None:
    # Arranca, dibuja un ciclo de eventos y sale con 0. Es lo que ejecuta
    # `build.sh` sobre el binario ya compilado: el toolchain puede producir un
    # ejecutable que compila y no arranca, y sin esto no se nota hasta abrirlo.
    autotest = "--autotest" in sys.argv
    if "--diagnostico" in sys.argv:
        sys.exit(_diagnostico())

    app = QApplication(sys.argv)
    app.setApplicationName("MCPE Mod Manager")
    app.setOrganizationName("mcpemod")
    aplicar(app, Acento.ORO, Modo.OSCURO)

    instalaciones = detectar_instalaciones()
    if not instalaciones:
        if autotest:
            print("autotest: sin instalación de Bedrock; nada que hacer")
            return
        QMessageBox.critical(None, "MCPE Mod Manager", _SIN_JUEGO)
        sys.exit(1)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    store = Store(DB_PATH)
    scanner = Scanner(store, instalaciones[0])
    installer = Installer(store, instalaciones[0])

    ventana = VentanaPrincipal(store, scanner, installer, instalaciones)
    ventana.show()

    if autotest:
        app.processEvents()
        if not _trabajo_en_segundo_plano_funciona(app):
            print("autotest: el trabajo en segundo plano no devuelve resultados")
            sys.exit(1)
        ventana.close()
        print("autotest: la ventana arranca")
        return

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
