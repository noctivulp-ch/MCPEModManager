"""Panel de actualizaciones: qué packs instalados tienen versión nueva publicada."""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from wulf_qt import GAP_CELDA, PARED, Pozo, boton, boton_primario, barra_progreso

from mcpemod.core import ErrorInstalacion, Installer, Scanner, Store, analizar
from mcpemod.core.actualizaciones import Buscador, Resultado
from mcpemod.core.fuentes import fuentes_disponibles
from mcpemod.core.red import ErrorRed, descargar
from mcpemod.senales import conectar
from mcpemod.ui.ajustes import CLAVE_CURSEFORGE
from mcpemod.ui.estilo import TEXTO_SECUNDARIO
from mcpemod.ui.panel_lista import PanelLista
from mcpemod.ui.tareas import Tarea
from mcpemod.ui.trabajo import comprobar_todos, instalar_publicado
from mcpemod.ui.widgets import TarjetaActualizacion

_VACIO = (
    "Todavía no se ha comprobado nada.\n"
    "Pulsa «Comprobar» para preguntar a los catálogos por tus packs."
)

#: Cada cuánto se rehace la lista mientras entran resultados. Rehacerla en cada
#: uno son cuarenta repintados seguidos, y se ven como un parpadeo; agrupándolos
#: la lista sigue llenándose a la vista pero de tres en tres.
_REFRESCO_MS = 350


class PanelActualizaciones(PanelLista):
    def __init__(
        self,
        store: Store,
        scanner: Scanner,
        installer: Installer,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(_VACIO, parent)
        self._store = store
        self._scanner = scanner
        self._installer = installer
        self._resultados: dict[str, Resultado] = {}
        self._fallos: list[str] = []
        self._tarea = Tarea(self)

        self._refresco = QTimer(self)
        self._refresco.setSingleShot(True)
        self._refresco.setInterval(_REFRESCO_MS)
        conectar(self._refresco.timeout, self._repoblar)

        self._cabecera(self._barra())
        conectar(scanner.instalados_cambiados, self._recargar_desde_cache)
        self._recargar_desde_cache()

    # ── Cabecera ──────────────────────────────────────────────────────────────

    def _barra(self) -> QWidget:
        contenedor = QWidget()
        raiz = QVBoxLayout(contenedor)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(PARED // 2)

        fila = QHBoxLayout()
        fila.setSpacing(GAP_CELDA)

        self._lbl_estado = QLabel()
        self._lbl_estado.setStyleSheet(f"color: {TEXTO_SECUNDARIO}; font-size: 11px;")
        fila.addWidget(self._lbl_estado)
        fila.addStretch()

        self._btn_comprobar = boton_primario("Comprobar")
        conectar(self._btn_comprobar.clicked, self._comprobar)
        fila.addWidget(self._btn_comprobar)

        self._btn_todo = boton("Actualizar todo")
        self._btn_todo.hide()
        conectar(self._btn_todo.clicked, self._actualizar_todo)
        fila.addWidget(self._btn_todo)

        self._btn_cancelar = boton("Cancelar")
        self._btn_cancelar.hide()
        conectar(self._btn_cancelar.clicked, self._cancelar)
        fila.addWidget(self._btn_cancelar)

        envoltorio = QWidget()
        envoltorio.setLayout(fila)
        raiz.addWidget(envoltorio)

        self._progreso = barra_progreso()
        self._progreso.hide()
        raiz.addWidget(self._progreso)

        return Pozo(contenedor)

    # ── Comprobación ──────────────────────────────────────────────────────────

    def _buscador(self) -> Buscador:
        clave = self._store.ajuste(CLAVE_CURSEFORGE)
        return Buscador(self._store, fuentes_disponibles(clave))

    def parar(self) -> None:
        """Corta el trabajo en curso. Se llama al cerrar la ventana."""
        self._tarea.parar()

    def _comprobar(self) -> None:
        if self._tarea.corriendo:
            return

        buscador = self._buscador()
        pendientes = buscador.pendientes(self._scanner.leer_instalados())
        if not pendientes:
            self._lbl_estado.setText("Todo comprobado hace poco. Nada que preguntar.")
            return

        self._btn_comprobar.hide()
        self._btn_cancelar.show()
        self._progreso.setRange(0, len(pendientes))
        self._progreso.setValue(0)
        self._progreso.show()
        self._tarea.lanzar(
            lambda emitir, cancelado: comprobar_todos(
                buscador, pendientes, emitir, cancelado
            ),
            self._al_mensaje,
        )

    def _cancelar(self) -> None:
        if self._tarea.corriendo:
            self._tarea.cancelar()
            self._lbl_estado.setText("Cancelando…")

    def _al_mensaje(self, mensaje: tuple) -> None:
        """Reparte lo que llega del hilo de trabajo. Corre en el hilo de la UI."""
        clase, *datos = mensaje
        if clase == "avance":
            self._al_avanzar(*datos)
        elif clase == "encontrado":
            self._al_encontrar(*datos)
        elif clase == "terminado":
            self._al_terminar(*datos)
        elif clase == "instalando":
            hechos, total, nombre = datos
            self._progreso.setValue(hechos)
            self._lbl_estado.setText(f"Actualizando {hechos + 1} de {total}:  {nombre}")
        elif clase == "instalado":
            # La tarjeta se quita al terminar, no en mitad: retirarla ahora
            # movería bajo el cursor las que vienen detrás.
            self._resultados.pop(datos[0], None)
        elif clase == "fallo":
            self._fallos.append(f"{datos[0]}: {datos[1]}")
        elif clase == "fin_instalacion":
            self._al_terminar_instalacion(*datos)
        elif clase == "error_interno":
            self._al_terminar(0, datos[0])

    def _al_avanzar(self, hechos: int, total: int, nombre: str) -> None:
        self._progreso.setValue(hechos)
        self._lbl_estado.setText(f"Comprobando {hechos + 1} de {total}:  {nombre}")

    def _al_encontrar(self, resultado: Resultado) -> None:
        self._resultados[resultado.pieza.uuid] = resultado
        # Se agrupa: durante un barrido llegan de a ráfagas.
        if not self._refresco.isActive():
            self._refresco.start()

    def _al_terminar(self, comprobados: int, error: str) -> None:
        self._progreso.hide()
        self._btn_cancelar.hide()
        self._btn_comprobar.show()

        if error:
            self._lbl_estado.setText(f"Se cortó: {error}")
        else:
            self._lbl_estado.setText(self._resumen(comprobados))
        self._repoblar()

    def _resumen(self, comprobados: int) -> str:
        con_actualizacion = sum(1 for r in self._resultados.values() if r.hay_actualizacion)
        partes = [f"{comprobados} comprobados"]
        partes.append(
            f"{con_actualizacion} con actualización" if con_actualizacion
            else "ninguno con actualización"
        )
        return "  ·  ".join(partes)

    # ── Lista ─────────────────────────────────────────────────────────────────

    def _recargar_desde_cache(self) -> None:
        piezas = self._scanner.leer_instalados()
        self._resultados = {
            r.pieza.uuid: r for r in self._buscador().desde_cache(piezas)
        }
        if self._resultados:
            self._lbl_estado.setText(self._resumen(len(self._resultados)))
        self._repoblar()

    def _pendientes_de_actualizar(self) -> list[Resultado]:
        return [r for r in self._resultados.values() if r.hay_actualizacion]

    def _actualizar_todo(self) -> None:
        """Instala de una vez todas las actualizaciones confirmadas.

        Solo las confirmadas: una coincidencia sin confirmar puede ser otro pack,
        y eso se decide de una en una mirando su publicación.
        """
        pendientes = self._pendientes_de_actualizar()
        if not pendientes or self._tarea.corriendo:
            return

        self._fallos = []
        self._btn_comprobar.hide()
        self._btn_todo.hide()
        self._btn_cancelar.show()
        self._progreso.setRange(0, len(pendientes))
        self._progreso.setValue(0)
        self._progreso.show()

        indice = self._scanner.indice()
        self._tarea.lanzar(
            lambda emitir, cancelado: instalar_publicado(
                pendientes, self._installer, indice, emitir, cancelado
            ),
            self._al_mensaje,
        )

    def _al_terminar_instalacion(self, instalados: int, fallidos: list) -> None:
        self._progreso.hide()
        self._btn_cancelar.hide()
        self._btn_comprobar.show()

        partes = [f"{instalados} actualizados"]
        if fallidos:
            partes.append(f"{len(fallidos)} fallaron")
        self._lbl_estado.setText("  ·  ".join(partes))

        if self._fallos:
            self._avisar("\n".join(self._fallos[:5]))
        self._scanner.notificar_cambio()
        self._repoblar()

    def _repoblar(self) -> None:
        self._refresco.stop()
        # Primero lo accionable, y dentro de eso lo confirmado: una lista donde
        # hay que buscar la actualización entre cincuenta «al día» no sirve.
        ordenados = sorted(
            self._resultados.values(),
            key=lambda r: (not r.hay_actualizacion, not r.seguro, r.pieza.nombre.lower()),
        )
        tarjetas = []
        for resultado in ordenados:
            tarjeta = TarjetaActualizacion(resultado)
            conectar(tarjeta.actualizar_pedido, self._actualizar)
            tarjetas.append(tarjeta)
        self._poner(tarjetas)

        cuantas = len(self._pendientes_de_actualizar())
        self._btn_todo.setText(f"Actualizar las {cuantas}" if cuantas > 1 else "Actualizar")
        self._btn_todo.setVisible(cuantas > 1 and not self._tarea.corriendo)

    # ── Actualizar ────────────────────────────────────────────────────────────

    def _actualizar(self, resultado: Resultado) -> None:
        """Descarga la versión publicada y la instala encima de la que hay.

        Se baja a un temporal y se pasa por el mismo camino que un archivo de
        una carpeta vigilada: así el emparejamiento por uuid decide el destino y
        reutiliza la carpeta existente, igual que en una instalación normal.
        """
        if resultado.descarga is None:
            return

        try:
            with tempfile.TemporaryDirectory() as tmp:
                destino = Path(tmp) / (resultado.descarga.nombre or "descarga.mcpack")
                with destino.open("wb") as f:
                    descargar(resultado.descarga.url, f)

                analisis = analizar(destino)
                if analisis is None:
                    self._avisar(f"Lo descargado de {resultado.publicacion.titulo} "
                                 "no es contenido instalable")
                    return
                self._installer.instalar(
                    analisis, self._scanner.indice(),
                    solo={resultado.pieza.clave, resultado.pieza.uuid},
                )
        except (ErrorRed, ErrorInstalacion, OSError) as e:
            self._avisar(str(e))
            return

        self._resultados.pop(resultado.pieza.uuid, None)
        self._scanner.notificar_cambio()
        self._avisar(f"Actualizado a v{resultado.version_remota}")
