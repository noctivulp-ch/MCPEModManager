"""Pestaña de activación: qué packs se aplican, en el juego y en cada mundo.

Dos vistas. La primera lista los ámbitos —el juego entero y cada mundo—; al
entrar en uno se ve su gestión, con lo inactivo a la izquierda y lo activo a la
derecha.

**Antes de tocar un mundo se respalda.** No es opcional: un mundo es lo único de
aquí que no se puede volver a descargar, y si el respaldo falla el cambio no se
hace.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMessageBox, QStackedWidget, QVBoxLayout, QWidget,
)

from wulf_qt import (
    GAP_CELDA, PARED, IconoTamano, Pozo, Tallado, boton, boton_plano, boton_primario,
    icono,
)

from mcpemod.core import Installer, Instalado, Scanner
from mcpemod.core.activacion import (
    Ambito, ErrorActivacion, Global, Mundo, mundos_de,
)
from mcpemod.core.contenido import Categoria
from mcpemod.core.respaldo_mundo import ErrorRespaldo, existente, guardar, restaurar
from mcpemod.senales import conectar
from mcpemod.ui import iconos
from mcpemod.ui.estilo import SOBRE_BANDEJA, TEXTO_SECUNDARIO
from mcpemod.core.miniatura import manifiesto_de
from mcpemod.ui.dialogo_pack import de_instalado, dialogo_pack
from mcpemod.ui.widgets import ColumnaPacks
from mcpemod.ui.widgets.arrastre import Arrastre

_SIN_COMPORTAMIENTO = (
    "Los packs de comportamiento no se activan aquí: cambian el contenido del "
    "mundo, así que van en cada mundo."
)


def _packs(cuantos: int) -> str:
    return "pack" if cuantos == 1 else "packs"


class PanelActivacion(QWidget):
    def __init__(
        self,
        scanner: Scanner,
        installer: Installer,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._scanner = scanner
        self._installer = installer
        self._ambito: Ambito | None = None
        #: Lo copiado con Ctrl+C, a la espera de un Ctrl+V.
        self._copiado: str = ""

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, PARED, 0, 0)
        raiz.setSpacing(PARED)

        self._vistas = QStackedWidget()
        self._vistas.addWidget(self._construir_lista())
        self._vistas.addWidget(self._construir_gestion())
        raiz.addWidget(self._vistas)

        conectar(scanner.instalados_cambiados, self.recargar)
        self.recargar()

    # ── Vista de ámbitos ──────────────────────────────────────────────────────

    def _construir_lista(self) -> QWidget:
        contenedor = QWidget()
        raiz = QVBoxLayout(contenedor)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(PARED)

        raiz.addWidget(Tallado("¿Dónde quieres gestionar los packs?", sobre=SOBRE_BANDEJA))
        self._lista_ambitos = QVBoxLayout()
        self._lista_ambitos.setSpacing(PARED // 2)
        envoltorio = QWidget()
        envoltorio.setLayout(self._lista_ambitos)
        raiz.addWidget(envoltorio)
        raiz.addStretch()
        return contenedor

    def _fila_ambito(self, ambito: Ambito, detalle: str) -> QWidget:
        contenedor = QWidget()
        fila = QHBoxLayout(contenedor)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(GAP_CELDA)

        # Global y un mundo se gestionan igual pero no son la misma cosa, y en una
        # lista donde los nombres los pone el jugador el dibujo es lo único que
        # los separa sin leer.
        marca = QLabel()
        dibujo = iconos.MUNDO if isinstance(ambito, Mundo) else iconos.GLOBAL
        marca.setPixmap(
            icono(dibujo, TEXTO_SECUNDARIO, IconoTamano.NORMAL).pixmap(
                IconoTamano.NORMAL, IconoTamano.NORMAL
            )
        )
        fila.addWidget(marca)

        info = QVBoxLayout()
        info.setSpacing(2)
        titulo = Tallado(ambito.nombre, sobre=SOBRE_BANDEJA)
        info.addWidget(titulo)
        lbl = QLabel(detalle)
        lbl.setStyleSheet(f"color: {TEXTO_SECUNDARIO}; font-size: 11px;")
        info.addWidget(lbl)
        fila.addLayout(info, stretch=1)

        entrar = iconos.poner(boton_primario("Gestionar"), iconos.ADELANTE, detras=True)
        conectar(entrar.clicked, lambda: self._entrar(ambito))
        fila.addWidget(entrar)
        return Pozo(contenedor)

    def recargar(self) -> None:
        while self._lista_ambitos.count():
            # La referencia se guarda antes: tras `setParent(None)` el item ya no
            # devuelve su widget.
            widget = self._lista_ambitos.takeAt(0).widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        instalacion = self._scanner.instalacion
        general = Global(instalacion)
        activos = len(general.activos(Categoria.RECURSO))
        self._lista_ambitos.addWidget(self._fila_ambito(
            general,
            f"{activos} {_packs(activos)} de recursos aplicados a todo el juego",
        ))

        for mundo in mundos_de(instalacion):
            n = len(mundo.uuids_activos())
            desfasados = self._desfases(mundo)
            detalle = f"{n} {_packs(n)} activos"
            if desfasados:
                detalle += f"  ·  {len(desfasados)} con versión más vieja que la instalada"
            self._lista_ambitos.addWidget(self._fila_ambito(mundo, detalle))

        if self._ambito is not None:
            self._refrescar_gestion()

    def _desfases(self, mundo: Mundo) -> dict[str, str]:
        """Qué packs tiene el mundo en una versión anterior a la instalada."""
        instalado = {p.uuid: p for p in self._scanner.leer_instalados() if p.uuid}
        desfases = {}
        for uuid, version in mundo.copias().items():
            pieza = instalado.get(uuid)
            if pieza and pieza.version and version and pieza.version != version:
                desfases[uuid] = version
        return desfases

    # ── Vista de gestión ──────────────────────────────────────────────────────

    def _construir_gestion(self) -> QWidget:
        contenedor = QWidget()
        raiz = QVBoxLayout(contenedor)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(PARED)

        raiz.addWidget(self._barra_gestion())

        columnas = QHBoxLayout()
        columnas.setSpacing(PARED)
        self._inactivos = ColumnaPacks("Disponibles", "No queda nada por activar.")
        self._activos = ColumnaPacks("Aplicados", "Ninguno activo todavía.")
        conectar(self._inactivos.accion, self._al_pedir)
        conectar(self._activos.accion, self._al_pedir)
        conectar(self._inactivos.abrir, lambda p: self._ficha(p, activo=False))
        conectar(self._activos.abrir, lambda p: self._ficha(p, activo=True))
        conectar(self._inactivos.soltado, lambda u, i: self._al_soltar(u, i, activar=False))
        conectar(self._activos.soltado, lambda u, i: self._al_soltar(u, i, activar=True))

        # El coordinador del arrastre vive aquí y no en una columna: el gesto
        # empieza en una y acaba en la otra, y la de origen no puede saber dónde.
        self._arrastre = Arrastre(self)
        self._arrastre.registrar(self._inactivos, self._activos)
        self._inactivos.arrastre = self._activos.arrastre = self._arrastre
        columnas.addWidget(self._inactivos)
        columnas.addWidget(self._activos)

        envoltorio = QWidget()
        envoltorio.setLayout(columnas)
        raiz.addWidget(envoltorio)
        return contenedor

    def _barra_gestion(self) -> QWidget:
        contenedor = QWidget()
        fila = QHBoxLayout(contenedor)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(GAP_CELDA)

        volver = iconos.poner(boton_plano("Volver"), iconos.ATRAS)
        conectar(volver.clicked, self._salir)
        fila.addWidget(volver)

        self._lbl_ambito = QLabel()
        self._lbl_ambito.setStyleSheet("font-weight: 600;")
        fila.addWidget(self._lbl_ambito)
        fila.addStretch()

        self._lbl_respaldo = QLabel()
        self._lbl_respaldo.setStyleSheet(f"color: {TEXTO_SECUNDARIO}; font-size: 11px;")
        fila.addWidget(self._lbl_respaldo)

        self._btn_respaldar = iconos.poner(boton("Guardar respaldo"), iconos.GUARDAR)
        conectar(self._btn_respaldar.clicked, self._respaldar_ahora)
        fila.addWidget(self._btn_respaldar)

        self._btn_restaurar = iconos.poner(boton("Restaurar"), iconos.RESTAURAR)
        conectar(self._btn_restaurar.clicked, self._restaurar)
        fila.addWidget(self._btn_restaurar)

        return Pozo(contenedor)

    def _entrar(self, ambito: Ambito) -> None:
        self._ambito = ambito
        self._lbl_ambito.setText(ambito.nombre)
        es_mundo = isinstance(ambito, Mundo)
        for widget in (self._btn_respaldar, self._btn_restaurar, self._lbl_respaldo):
            widget.setVisible(es_mundo)
        self._refrescar_gestion()
        self._vistas.setCurrentIndex(1)

    def _salir(self) -> None:
        self._ambito = None
        self._vistas.setCurrentIndex(0)
        self.recargar()

    def _refrescar_gestion(self) -> None:
        ambito = self._ambito
        if ambito is None:
            return

        piezas = [p for p in self._scanner.leer_instalados() if p.categoria in ambito.categorias]
        activos_uuid = ambito.uuids_activos()
        desfases = self._desfases(ambito) if isinstance(ambito, Mundo) else {}

        # Los aplicados van en el orden del juego, no alfabético: es el orden en
        # que se aplican y el último gana.
        por_uuid = {p.uuid: p for p in piezas}
        aplicados = []
        for categoria in ambito.categorias:
            aplicados += [por_uuid[r.uuid] for r in ambito.activos(categoria) if r.uuid in por_uuid]

        disponibles = [p for p in piezas if p.uuid not in activos_uuid]
        nota = _SIN_COMPORTAMIENTO if isinstance(ambito, Global) else None

        self._inactivos.poner(disponibles, activo=False, nota=nota)
        self._activos.poner(aplicados, activo=True, desfases=desfases, agrupado=False)
        self._actualizar_respaldo()

    # ── Acciones ──────────────────────────────────────────────────────────────

    def _al_pedir(self, pieza: Instalado, que: str) -> None:
        ambito = self._ambito
        if ambito is None:
            return
        if isinstance(ambito, Mundo) and not self._respaldar_antes_de_tocar(ambito):
            return

        try:
            if que == "activar":
                ambito.activar(pieza)
            elif que == "desactivar":
                ambito.desactivar(pieza)
            else:
                self._mover(ambito, pieza, arriba=(que == "subir"))
        except (ErrorActivacion, OSError) as e:
            self._avisar(str(e))
            return

        self._refrescar_gestion()

    def _ficha(self, pieza: Instalado, activo: bool) -> None:
        """La ficha del pack, con su ámbito: es donde se elige la variante.

        Solo con el pack ya aplicado se puede elegir — la variante se guarda
        dentro de la entrada de activación, así que sin entrada no hay dónde.
        """
        dialogo = dialogo_pack(
            de_instalado(pieza, manifiesto_de(pieza)),
            self._ambito, activo, parent=self.window(),
        )
        if dialogo.exec() and activo:
            self._refrescar_gestion()

    def _al_soltar(self, uuid: str, posicion: int, activar: bool) -> None:
        """Un pack soltado en una columna: la columna dice qué significa.

        En la de aplicados, activar —y dejarlo en el hueco donde cayó, porque el
        orden es lo que decide cuál gana—. En la de disponibles, quitar.
        """
        ambito = self._ambito
        if ambito is None:
            return
        pieza = next(
            (p for p in self._scanner.leer_instalados() if p.uuid == uuid), None
        )
        if pieza is None:
            return

        estaba = uuid in ambito.uuids_activos()
        if activar == estaba and not activar:
            return  # ya estaba fuera: soltarlo ahí no cambia nada

        if isinstance(ambito, Mundo) and not self._respaldar_antes_de_tocar(ambito):
            return

        try:
            if activar:
                if not estaba:
                    ambito.activar(pieza)
                self._colocar_en(ambito, pieza, posicion)
            else:
                ambito.desactivar(pieza)
        except (ErrorActivacion, OSError) as e:
            self._avisar(str(e))
            return
        self._refrescar_gestion()

    def _colocar_en(self, ambito: Ambito, pieza: Instalado, posicion: int) -> None:
        """Deja el pack en ese hueco del orden de aplicación."""
        uuids = [r.uuid for r in ambito.activos(pieza.categoria)]
        if pieza.uuid in uuids:
            uuids.remove(pieza.uuid)
        uuids.insert(max(0, min(posicion, len(uuids))), pieza.uuid)
        ambito.reordenar(pieza.categoria, uuids)

    def copiar_seleccion(self) -> None:
        """`Ctrl+C`: se queda con el pack que esté bajo el puntero."""
        pieza = self._pieza_bajo_el_puntero()
        if pieza is None:
            return
        self._copiado = pieza.uuid
        self._avisar(f"Copiado: {pieza.nombre}. Ctrl+V donde quieras ponerlo.")

    def pegar(self) -> None:
        """`Ctrl+V`: lo pone en la columna y el hueco donde esté el puntero."""
        if not self._copiado:
            return
        for columna, activar in ((self._activos, True), (self._inactivos, False)):
            if columna.underMouse():
                uuid = self._copiado
                local = columna.mapFromGlobal(self.cursor().pos())
                self._al_soltar(uuid, columna._posicion_en(local.y()), activar=activar)
                return

    def _pieza_bajo_el_puntero(self) -> Instalado | None:
        from mcpemod.ui.widgets.columna_packs import FilaPack

        widget = self.window().childAt(self.window().mapFromGlobal(self.cursor().pos()))
        while widget is not None:
            if isinstance(widget, FilaPack):
                return widget.pieza
            widget = widget.parentWidget()
        return None

    def _mover(self, ambito: Ambito, pieza: Instalado, arriba: bool) -> None:
        categoria = pieza.categoria
        uuids = [r.uuid for r in ambito.activos(categoria)]
        if pieza.uuid not in uuids:
            return
        i = uuids.index(pieza.uuid)
        j = i - 1 if arriba else i + 1
        if not 0 <= j < len(uuids):
            return
        uuids[i], uuids[j] = uuids[j], uuids[i]
        ambito.reordenar(categoria, uuids)

    # ── Respaldo ──────────────────────────────────────────────────────────────

    def _carpeta_respaldos(self):
        return self._scanner.instalacion.respaldos_de_mundos

    def _actualizar_respaldo(self) -> None:
        if not isinstance(self._ambito, Mundo):
            return
        previo = existente(self._ambito.carpeta, self._carpeta_respaldos())
        self._lbl_respaldo.setText(
            f"Respaldo: {previo.fecha:%d/%m/%Y %H:%M}" if previo else "Sin respaldo todavía"
        )
        self._btn_restaurar.setEnabled(previo is not None)

    def _respaldar_antes_de_tocar(self, mundo: Mundo) -> bool:
        """Respalda antes de cambiar nada. Si falla, el cambio no se hace."""
        try:
            guardar(mundo.carpeta, self._carpeta_respaldos())
        except ErrorRespaldo as e:
            self._avisar(f"No se pudo respaldar el mundo, así que no se ha tocado nada.\n\n{e}")
            return False
        self._actualizar_respaldo()
        return True

    def _respaldar_ahora(self) -> None:
        mundo = self._ambito
        if not isinstance(mundo, Mundo):
            return

        previo = existente(mundo.carpeta, self._carpeta_respaldos())
        if previo is not None and not self._confirmar_sobrescritura(previo):
            return
        try:
            nuevo = guardar(mundo.carpeta, self._carpeta_respaldos())
        except ErrorRespaldo as e:
            self._avisar(str(e))
            return
        self._actualizar_respaldo()
        self._avisar(f"Respaldo guardado: {nuevo.descripcion}")

    def _confirmar_sobrescritura(self, previo) -> bool:
        """Se guarda uno por mundo, así que guardar otro pierde el anterior."""
        respuesta = QMessageBox.question(
            self, "Sustituir el respaldo",
            f"Ya hay un respaldo de este mundo:\n\n    {previo.descripcion}\n\n"
            "Guardar uno nuevo lo sustituye y no se podrá volver a él.\n¿Seguir?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return respuesta == QMessageBox.StandardButton.Yes

    def _restaurar(self) -> None:
        mundo = self._ambito
        if not isinstance(mundo, Mundo):
            return
        previo = existente(mundo.carpeta, self._carpeta_respaldos())
        if previo is None:
            return

        respuesta = QMessageBox.question(
            self, "Restaurar el mundo",
            f"Se va a dejar «{mundo.nombre}» como estaba el "
            f"{previo.fecha:%d/%m/%Y a las %H:%M}.\n\n"
            "Todo lo jugado desde entonces se pierde.\n¿Seguir?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return

        try:
            restaurar(mundo.carpeta, self._carpeta_respaldos())
        except ErrorRespaldo as e:
            self._avisar(str(e))
            return
        self._scanner.notificar_cambio()
        self._refrescar_gestion()
        self._avisar(f"«{mundo.nombre}» restaurado.")

    def _avisar(self, mensaje: str) -> None:
        from wulf_qt import mostrar_aviso
        mostrar_aviso(self.window(), mensaje)
