"""Panel para navegar el catálogo e instalar sin pasar por el navegador."""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget,
)

from wulf_qt import GAP_CELDA, PARED, IconoTamano, Pozo, boton, boton_plano, icono

from mcpemod.core import ErrorInstalacion, Installer, Scanner, Store, analizar
from mcpemod.core.fuentes import Publicacion, fuentes_disponibles
from mcpemod.core.red import ErrorRed, descargar
from mcpemod.senales import conectar
from mcpemod.ui import iconos
from mcpemod.ui.ajustes import CLAVE_CURSEFORGE
from mcpemod.ui.estilo import TEXTO_SECUNDARIO
from mcpemod.ui.panel_lista import PanelLista
from mcpemod.ui.tareas import Tarea
from mcpemod.ui.trabajo_catalogo import consultar
from mcpemod.ui.widgets import TarjetaPublicacion

#: Lo que se espera desde la última tecla antes de consultar. Sin esto, escribir
#: «xray» lanza cuatro búsquedas y la última en llegar no es la del texto final.
_RETARDO_TECLEO = 400


class PanelExplorar(PanelLista):
    def __init__(
        self,
        store: Store,
        scanner: Scanner,
        installer: Installer,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Escribe algo para buscar, o mira las novedades.", parent)
        self._store = store
        self._scanner = scanner
        self._installer = installer
        self._pagina = 1
        self._tarea = Tarea(self)

        self._temporizador = QTimer(self)
        self._temporizador.setSingleShot(True)
        self._temporizador.setInterval(_RETARDO_TECLEO)
        conectar(self._temporizador.timeout, self._consultar)

        self._cabecera(self._barra())
        self._consultar()

    # ── Cabecera ──────────────────────────────────────────────────────────────

    def _barra(self) -> QWidget:
        contenedor = QWidget()
        raiz = QVBoxLayout(contenedor)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(PARED // 2)

        fila = QHBoxLayout()
        fila.setSpacing(GAP_CELDA)

        # `wulf_qt.BarraBusqueda` es un slider de reproducción, no un campo de
        # texto: el nombre engaña.
        self._busqueda = QLineEdit()
        self._busqueda.setPlaceholderText("Buscar packs, addons, mundos…")
        self._busqueda.setClearButtonEnabled(True)
        # Dentro del campo y no al lado: es el sitio que la librería reserva para
        # el tamaño chico, y aquí distingue de un vistazo el campo de búsqueda del
        # selector de fuente que lleva pegado.
        self._busqueda.addAction(
            icono(iconos.BUSCAR, TEXTO_SECUNDARIO, IconoTamano.CHICO),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        conectar(self._busqueda.textChanged, self._al_teclear)
        fila.addWidget(self._busqueda, stretch=1)

        self._combo = QComboBox()
        for fuente in self._fuentes():
            self._combo.addItem(fuente.etiqueta, userData=fuente)
        conectar(self._combo.currentIndexChanged, self._al_cambiar_fuente)
        self._combo.setVisible(self._combo.count() > 1)
        fila.addWidget(self._combo)

        envoltorio = QWidget()
        envoltorio.setLayout(fila)
        raiz.addWidget(envoltorio)

        pie = QHBoxLayout()
        pie.setSpacing(GAP_CELDA // 2)

        self._lbl_estado = QLabel()
        self._lbl_estado.setStyleSheet(f"color: {TEXTO_SECUNDARIO}; font-size: 11px;")
        pie.addWidget(self._lbl_estado)
        pie.addStretch()

        self._btn_anterior = iconos.poner(boton_plano("Anterior"), iconos.ATRAS)
        conectar(self._btn_anterior.clicked, lambda: self._ir_a(self._pagina - 1))
        pie.addWidget(self._btn_anterior)

        self._btn_siguiente = iconos.poner(boton("Siguiente"), iconos.ADELANTE, detras=True)
        conectar(self._btn_siguiente.clicked, lambda: self._ir_a(self._pagina + 1))
        pie.addWidget(self._btn_siguiente)

        pie_widget = QWidget()
        pie_widget.setLayout(pie)
        raiz.addWidget(pie_widget)

        return Pozo(contenedor)

    def _fuentes(self):
        return fuentes_disponibles(self._store.ajuste(CLAVE_CURSEFORGE))

    def refrescar_fuentes(self) -> None:
        """Vuelve a mirar qué catálogos hay, tras tocar los ajustes."""
        actual = self._combo.currentText()
        self._combo.clear()
        for fuente in self._fuentes():
            self._combo.addItem(fuente.etiqueta, userData=fuente)
        self._combo.setVisible(self._combo.count() > 1)
        indice = self._combo.findText(actual)
        if indice >= 0:
            self._combo.setCurrentIndex(indice)

    # ── Consulta ──────────────────────────────────────────────────────────────

    def _al_teclear(self, _texto: str) -> None:
        self._pagina = 1
        self._temporizador.start()

    def _al_cambiar_fuente(self, _indice: int) -> None:
        self._pagina = 1
        self._consultar()

    def _ir_a(self, pagina: int) -> None:
        if pagina < 1:
            return
        self._pagina = pagina
        self._consultar()

    def _consultar(self) -> None:
        fuente = self._combo.currentData()
        if fuente is None:
            self._lbl_estado.setText("No hay ningún catálogo disponible.")
            return

        # Al escribir rápido se solapan consultas: la anterior se cancela para
        # que su respuesta no pise la que se está pidiendo.
        self._tarea.cancelar()
        self._lbl_estado.setText("Buscando…")

        texto, pagina = self._busqueda.text(), self._pagina
        self._tarea.lanzar(
            lambda emitir, cancelado: consultar(fuente, texto, pagina, emitir, cancelado),
            self._al_mensaje,
        )

    def _al_mensaje(self, mensaje: tuple) -> None:
        """Reparte lo que llega del hilo de trabajo. Corre en el hilo de la UI."""
        clase, *datos = mensaje
        if clase == "listo":
            self._al_recibir(*datos)
        elif clase == "error_interno":
            self._lbl_estado.setText(datos[0])

    def _al_recibir(self, publicaciones: list, error: str) -> None:
        if error:
            self._lbl_estado.setText(error)
            return

        # El catálogo no publica el uuid, así que no se puede saber si algo está
        # instalado sin abrir su archivo. Lo que sí se sabe de balde es qué
        # publicaciones dejaron algo instalado, que cubre lo que puso el gestor.
        conocidas = self._instalados_por_publicacion()

        tarjetas = []
        for publicacion in publicaciones:
            tarjeta = TarjetaPublicacion(publicacion, instalado=publicacion.id in conocidas)
            conectar(tarjeta.instalar_pedido, self._instalar)
            tarjetas.append(tarjeta)
        self._poner(tarjetas)

        self._btn_anterior.setEnabled(self._pagina > 1)
        self._btn_siguiente.setEnabled(bool(publicaciones))
        self._lbl_estado.setText(
            f"{len(publicaciones)} resultados  ·  página {self._pagina}"
            if publicaciones else "Sin resultados."
        )

    def parar(self) -> None:
        """Corta el trabajo en curso. Se llama al cerrar la ventana."""
        self._tarea.parar()

    def _instalados_por_publicacion(self) -> set[str]:
        return {
            datos["id_publicacion"]
            for datos in self._store.emparejamientos().values()
            if datos["encontrado"] and datos["id_publicacion"]
        }

    # ── Instalar ──────────────────────────────────────────────────────────────

    def _instalar(self, publicacion: Publicacion) -> None:
        descarga = publicacion.ultima
        if descarga is None:
            return

        try:
            with tempfile.TemporaryDirectory() as tmp:
                destino = Path(tmp) / (descarga.nombre or "descarga.mcpack")
                with destino.open("wb") as f:
                    descargar(descarga.url, f)

                analisis = analizar(destino)
                if analisis is None:
                    self._avisar(f"Lo descargado de {publicacion.titulo} "
                                 "no es contenido instalable")
                    return
                self._installer.instalar(analisis, self._scanner.indice())

                # Se recuerda de dónde vino para que la pestaña de
                # actualizaciones no tenga que volver a buscarlo.
                for uuid in analisis.uuids:
                    self._store.guardar_emparejamiento(
                        uuid, encontrado=True, fuente=publicacion.fuente,
                        id_publicacion=publicacion.id, titulo=publicacion.titulo,
                        autor=publicacion.autor, url_publicacion=publicacion.url,
                        confianza="confirmado", url_descarga=descarga.url,
                        nombre_archivo=descarga.nombre,
                    )
        except (ErrorRed, ErrorInstalacion, OSError) as e:
            self._avisar(str(e))
            return

        self._scanner.notificar_cambio()
        self._avisar(f"Instalado: {publicacion.titulo}")
