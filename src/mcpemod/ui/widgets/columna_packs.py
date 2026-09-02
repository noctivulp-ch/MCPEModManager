"""Una columna de packs con scroll, agrupada por categoría.

Es la mitad de la vista de activación: una para lo inactivo y otra para lo
activo. Van separadas y no como una lista con casillas porque lo que se quiere
ver de un vistazo es **qué está puesto**, y eso se lee mejor como dos montones
que como una marca por fila.

Los packs se mueven de tres maneras, y las tres hacen lo mismo:

- **Arrastrando por el asa** (`≡`) — a la otra columna para activar o quitar, o
  dentro de la de activos para cambiar el orden. El asa existe para que arrastrar
  no compita con desplazar la lista: agarrar por cualquier sitio haría imposible
  hacer scroll con el ratón. El gesto lo lleva `arrastre.Arrastre`, que es de
  quien salen la cápsula, el hueco y el desplazamiento automático.
- **Con los botones**, para quien no quiera arrastrar.
- **Copiando y pegando** (`Ctrl+C` / `Ctrl+V`), que pega donde esté el puntero.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QFontMetrics, QMouseEvent
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from wulf_qt import (
    GAP_CELDA, PADDING_CELDA, PARED, IconoTamano, Pozo, Tallado, boton, icono,
)

from mcpemod.core import Instalado
from mcpemod.senales import conectar
from mcpemod.ui import iconos
from mcpemod.ui.estilo import (
    AMBAR, SOBRE_BANDEJA, TEXTO_EN_POZO, TEXTO_SECUNDARIO, VIOLETA,
)
from mcpemod.ui.widgets.arrastre import UMBRAL
from mcpemod.ui.widgets.badge import badge
from mcpemod.ui.widgets.lista_por_categoria import agrupar, cabecera
from mcpemod.ui.widgets.miniatura import Miniatura


class NombreElidido(QLabel):
    """El nombre del pack, recortado con puntos suspensivos al ancho que le toque.

    Recortar por número de caracteres no vale: lo que sobra depende de cuántos
    botones lleve la fila y de cuánta anchura le deje el badge, y eso solo se sabe
    cuando Qt ya ha repartido el sitio. Sin esto el nombre se corta en seco a
    media letra y no hay forma de distinguir «Better Trees by Da…» de un pack que
    de verdad se llame así.
    """

    def __init__(self, texto: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entero = " ".join(texto.split())
        self.setToolTip(self._entero)
        self.setWordWrap(False)
        self.setText(self._entero)

    def resizeEvent(self, evento) -> None:  # noqa: N802 (API de Qt)
        super().resizeEvent(evento)
        metricas = QFontMetrics(self.font())
        self.setText(metricas.elidedText(
            self._entero, Qt.TextElideMode.ElideRight, self.width()
        ))


class Asa(QLabel):
    """Por donde se agarra una fila para arrastrarla.

    Es una zona pequeña y marcada a propósito: si se pudiera arrastrar desde
    cualquier parte de la fila, desplazar la lista con el ratón sería imposible.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setToolTip("Arrastra para mover o cambiar de lado")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Ancho de sobra alrededor del dibujo: el icono mide 20 y el asa 28,
        # porque lo que se agarra con el ratón no es el trazo sino la zona.
        self.setFixedWidth(28)
        self.setPixmap(
            icono(iconos.ASA, TEXTO_SECUNDARIO, IconoTamano.CHICO).pixmap(
                IconoTamano.CHICO, IconoTamano.CHICO
            )
        )
        self._pinchado: QPoint | None = None

    def mousePressEvent(self, evento: QMouseEvent) -> None:  # noqa: N802 (API de Qt)
        if evento.button() != Qt.MouseButton.LeftButton:
            return
        self._pinchado = evento.globalPosition().toPoint()
        self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, evento: QMouseEvent) -> None:  # noqa: N802 (API de Qt)
        """Mientras el botón siga pulsado, los eventos llegan aquí.

        Es el agarre implícito de Qt: quien recibe el `press` recibe todo el
        movimiento hasta el `release`, esté el puntero donde esté. Por eso el asa
        puede conducir un arrastre que acaba en la otra columna.
        """
        if self._pinchado is None:
            return
        ahora = evento.globalPosition().toPoint()
        arrastre = self._arrastre()
        if arrastre is None:
            return
        if not arrastre.activo:
            if (ahora - self._pinchado).manhattanLength() < UMBRAL:
                return
            fila, columna = self._fila_y_columna()
            if fila is None or columna is None:
                return
            arrastre.empezar(fila, columna, ahora)
        arrastre.mover(ahora)

    def mouseReleaseEvent(self, evento: QMouseEvent) -> None:  # noqa: N802 (API de Qt)
        self._pinchado = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        arrastre = self._arrastre()
        if arrastre is not None:
            arrastre.terminar_gesto()

    def _fila_y_columna(self):
        fila = self.parentWidget()
        while fila is not None and not isinstance(fila, FilaPack):
            fila = fila.parentWidget()
        columna = fila
        while columna is not None and not isinstance(columna, ColumnaPacks):
            columna = columna.parentWidget()
        return fila, columna

    def _arrastre(self):
        """El coordinador del gesto, que vive en el panel y no en la columna."""
        _, columna = self._fila_y_columna()
        return columna.arrastre if columna is not None else None


class FilaPack(QWidget):
    """Un pack dentro de una columna, con lo que se puede hacerle desde ahí."""

    accion = Signal(object, str)   # pieza, "activar" | "desactivar" | "subir" | "bajar"
    #: Se ha pulsado la fila: se pide su ficha.
    abrir = Signal(object)

    def __init__(
        self,
        pieza: Instalado,
        activo: bool,
        desfase: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._pieza = pieza
        self._activo = activo
        self._desfase = desfase

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.addWidget(Pozo(self._contenido(), padding=PADDING_CELDA // 2))

    @property
    def pieza(self) -> Instalado:
        return self._pieza

    def mouseReleaseEvent(self, evento: QMouseEvent) -> None:  # noqa: N802 (API de Qt)
        """Pulsar la fila abre su ficha.

        No choca con arrastrar: eso solo empieza desde el asa, que se come sus
        propios eventos de ratón y nunca llegan aquí.
        """
        if evento.button() == Qt.MouseButton.LeftButton:
            self.abrir.emit(self._pieza)
        super().mouseReleaseEvent(evento)

    def _contenido(self) -> QWidget:
        contenedor = QWidget()
        fila = QHBoxLayout(contenedor)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(GAP_CELDA // 2)

        if self._pieza.uuid:
            fila.addWidget(Asa(contenedor))
        fila.addWidget(Miniatura(self._pieza))

        info = QVBoxLayout()
        info.setSpacing(2)
        info.addLayout(self._titulo())

        detalle = [f"v{self._pieza.version or '?'}"]
        if self._desfase:
            detalle.append(f"el mundo tiene v{self._desfase}")
        lbl = QLabel("  ·  ".join(detalle))
        lbl.setStyleSheet(f"color: {TEXTO_SECUNDARIO}; font-size: 10px;")
        lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        info.addWidget(lbl)
        fila.addLayout(info, stretch=1)

        fila.addLayout(self._acciones())
        return contenedor

    def _titulo(self) -> QHBoxLayout:
        fila = QHBoxLayout()
        fila.setSpacing(GAP_CELDA // 3)

        # Un `QLabel` y no un `Tallado`: el relieve parte el texto en dos líneas
        # cuando no cabe —lo pinta con ajuste de línea y no se puede apagar— y en
        # una fila estrecha eso descuadra todo. Aquí manda que quepa en una línea.
        nombre = NombreElidido(self._pieza.nombre)
        nombre.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        nombre.setStyleSheet(f"color: {TEXTO_EN_POZO}; font-size: 12px; font-weight: 600;")
        # Con ancho ignorado: un nombre largo impondría el suyo a la columna y
        # empujaría los botones fuera de la tarjeta.
        nombre.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        fila.addWidget(nombre, stretch=1)

        # Solo lo que se puede accionar desde aquí. «Sin extraer» es cierto pero
        # se extrae en Instalado, no en esta columna: aquí únicamente le comía
        # anchura al nombre, que es lo que sí hace falta leer.
        if self._pieza.de_la_tienda:
            fila.addWidget(badge("Tienda", VIOLETA))
        if self._desfase:
            marca = badge("desfasado", AMBAR)
            marca.setToolTip(
                "El mundo usa su propia copia, más vieja que la instalada.\n"
                "Actualizar el pack no le llega: hay que ponerlo aquí otra vez."
            )
            fila.addWidget(marca)

        fila.addStretch()
        return fila

    def _acciones(self) -> QHBoxLayout:
        fila = QHBoxLayout()
        fila.setSpacing(2)
        fila.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        if self._activo:
            # El orden importa: el último de la lista gana. Solo el dibujo y sin
            # palabra: en una fila que ya lleva tres botones, «Subir»/«Bajar»
            # ocupan más de lo que aclaran, y una flecha dice exactamente eso.
            for dibujo, que, ayuda in (
                (iconos.SUBIR, "subir", "Subir — se aplica antes, así que pierde ante los de abajo"),
                (iconos.BAJAR, "bajar", "Bajar — se aplica después, así que gana"),
            ):
                b = iconos.poner(boton(""), dibujo)
                b.setToolTip(ayuda)
                conectar(b.clicked, lambda q=que: self.accion.emit(self._pieza, q))
                fila.addWidget(b)

            quitar = iconos.poner(boton("Quitar"), iconos.DESACTIVAR)
            conectar(quitar.clicked, lambda: self.accion.emit(self._pieza, "desactivar"))
            fila.addWidget(quitar)
        else:
            poner = iconos.poner(boton("Activar"), iconos.ACTIVAR, detras=True)
            conectar(poner.clicked, lambda: self.accion.emit(self._pieza, "activar"))
            fila.addWidget(poner)

        return fila


class ColumnaPacks(QWidget):
    """Una de las dos mitades: título, y la lista agrupada con scroll."""

    accion = Signal(object, str)
    #: uuid del pack soltado y en qué posición de esta columna cayó.
    soltado = Signal(str, int)
    abrir = Signal(object)

    def __init__(self, titulo: str, vacio: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vacio = vacio
        self._filas: list[FilaPack] = []
        #: Lo pone el panel: el gesto cruza de una columna a la otra, así que
        #: quien lo lleva tiene que estar por encima de las dos.
        self.arrastre = None

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(PARED // 2)

        self._titulo = Tallado(titulo, sobre=SOBRE_BANDEJA)
        raiz.addWidget(self._titulo)
        self._encabezado = titulo

        self._scroll = scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        # La columna nunca desplaza en horizontal: lo que no cabe se recorta.
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        contenedor = QWidget()
        self._lista = QVBoxLayout(contenedor)
        self._lista.setContentsMargins(0, 0, 0, PADDING_CELDA)
        self._lista.setSpacing(PARED // 2)
        self._lista.addStretch()
        scroll.setWidget(contenedor)
        raiz.addWidget(scroll)

    def poner(
        self,
        piezas: list[Instalado],
        activo: bool,
        desfases: dict[str, str] | None = None,
        agrupado: bool = True,
        nota: str | None = None,
    ) -> None:
        """Reemplaza el contenido. `desfases` marca qué versión tiene el mundo."""
        self._titulo.setText(f"{self._encabezado}   ·   {len(piezas)}")
        self.setUpdatesEnabled(False)
        try:
            self._reemplazar(self._construir(piezas, activo, desfases or {}, agrupado, nota))
        finally:
            self.setUpdatesEnabled(True)

    # ── Arrastrar, soltar y pegar ─────────────────────────────────────────────

    # ── Lo que necesita el coordinador del arrastre ──────────────────────────

    def indice_en(self, global_pos: QPoint) -> int:
        """En qué hueco de la lista cae ese punto de la pantalla."""
        return self._posicion_en(self.mapFromGlobal(global_pos).y())

    def poner_hueco(self, hueco: QWidget, posicion: int) -> None:
        """Deja el hueco en esa posición, y solo si no estaba ya ahí.

        La comprobación no es un ahorro: reinsertarlo en cada movimiento del
        ratón lo hace parpadear.
        """
        if self._lista.indexOf(hueco) == self._indice_de_layout(posicion):
            return
        if hueco.parent() is not None:
            hueco.setParent(None)
        self._lista.insertWidget(self._indice_de_layout(posicion), hueco)

    def desplazar(self, delta: int) -> None:
        barra = self._scroll.verticalScrollBar()
        barra.setValue(barra.value() + delta)

    def paso_de_borde(self, global_pos: QPoint, banda: int, maximo: int) -> int:
        """Cuánto desplazar por estar cerca de un borde. 0 si no toca.

        Proporcional a lo metido que esté el puntero en la banda: rozándola va
        despacio y pegado al borde va rápido. A saltos fijos es imposible parar
        donde uno quiere.
        """
        vista = self._scroll.viewport()
        local = vista.mapFromGlobal(global_pos)
        if not vista.rect().contains(QPoint(vista.width() // 2, local.y())):
            return 0

        if local.y() < banda:
            return -round(maximo * (banda - local.y()) / banda)
        desde_abajo = vista.height() - local.y()
        if desde_abajo < banda:
            return round(maximo * (banda - desde_abajo) / banda)
        return 0

    def _indice_de_layout(self, posicion: int) -> int:
        """De «entre la fila visible N y la N+1» al índice del layout.

        No coinciden: en medio hay cabeceras de categoría, avisos y el propio
        hueco, que no son filas pero sí ocupan un sitio en el layout.
        """
        vistas = 0
        for i in range(self._lista.count()):
            widget = self._lista.itemAt(i).widget()
            if not isinstance(widget, FilaPack) or not widget.isVisible():
                continue
            if vistas == posicion:
                return i
            vistas += 1
        return max(0, self._lista.count() - 1)   # antes del `addStretch` final

    def pegar_en_el_puntero(self, uuid: str) -> None:
        """Coloca `uuid` donde esté el ratón. Es el `Ctrl+V`."""
        local = self.mapFromGlobal(self.cursor().pos())
        self.soltado.emit(uuid, self._posicion_en(local.y()))

    def _posicion_en(self, y_en_la_columna: int) -> int:
        """En qué hueco de la lista cae esa altura.

        Se compara con el centro de cada fila: soltar en la mitad de arriba pone
        antes, en la de abajo pone después, que es lo que uno espera al colocar
        algo entre dos cosas.

        Cuenta **solo las filas visibles**, porque la que se está arrastrando
        está escondida y quien recibe esta posición la reinserta sobre una lista
        de la que ya la ha quitado. Contando las ocultas, todo lo que cayera por
        debajo del pack movido se colocaba un sitio más allá.
        """
        visibles = 0
        for fila in self._filas:
            if not fila.isVisible():
                continue
            centro = fila.mapTo(self, fila.rect().center()).y()
            if y_en_la_columna < centro:
                return visibles
            visibles += 1
        return visibles

    def _construir(self, piezas, activo, desfases, agrupado, nota) -> list[QWidget]:
        widgets: list[QWidget] = []
        self._filas = []
        if nota:
            from mcpemod.ui.widgets.lista_por_categoria import aviso
            widgets.append(aviso(nota))

        def fila(pieza: Instalado) -> QWidget:
            f = FilaPack(pieza, activo, desfases.get(pieza.uuid))
            conectar(f.accion, lambda p, q: self.accion.emit(p, q))
            conectar(f.abrir, lambda p: self.abrir.emit(p))
            self._filas.append(f)
            return f

        if not agrupado:
            # Los activos van en su orden, que es el que aplica el juego.
            widgets.extend(fila(p) for p in piezas)
            return widgets

        for categoria, delgrupo in agrupar(
            piezas, categoria_de=lambda p: p.categoria, nombre_de=lambda p: p.nombre
        ):
            widgets.append(cabecera(categoria, len(delgrupo)))
            widgets.extend(fila(p) for p in delgrupo)
        return widgets

    def _reemplazar(self, widgets: list[QWidget]) -> None:
        while self._lista.count() > 1:
            item = self._lista.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        if not widgets:
            from mcpemod.ui.widgets.lista_por_categoria import aviso
            widgets = [aviso(self._vacio)]
        for w in widgets:
            self._lista.insertWidget(self._lista.count() - 1, w)
