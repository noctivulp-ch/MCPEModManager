"""Una columna de packs con scroll, agrupada por categoría.

Es la mitad de la vista de activación: una para lo inactivo y otra para lo
activo. Van separadas y no como una lista con casillas porque lo que se quiere
ver de un vistazo es **qué está puesto**, y eso se lee mejor como dos montones
que como una marca por fila.

Los packs se mueven de tres maneras, y las tres hacen lo mismo:

- **Arrastrando por el asa** (`≡`) — a la otra columna para activar o quitar, o
  dentro de la de activos para cambiar el orden. El asa existe para que arrastrar
  no compita con desplazar la lista: agarrar por cualquier sitio haría imposible
  hacer scroll con el ratón.
- **Con los botones**, para quien no quiera arrastrar.
- **Copiando y pegando** (`Ctrl+C` / `Ctrl+V`), que pega donde esté el puntero.
"""

from __future__ import annotations

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QDrag, QMouseEvent
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from wulf_qt import GAP_CELDA, PADDING_CELDA, PARED, Pozo, Tallado, boton

from mcpemod.core import Instalado
from mcpemod.senales import conectar
from mcpemod.ui.estilo import (
    AMBAR, SOBRE_BANDEJA, TEXTO_EN_POZO, TEXTO_SECUNDARIO, VIOLETA,
)
from mcpemod.ui.widgets.badge import badge
from mcpemod.ui.widgets.lista_por_categoria import agrupar, cabecera


#: Con qué se identifica un pack al arrastrarlo. Un tipo propio para que no se
#: confunda con texto arrastrado desde fuera de la app.
MIME_PACK = "application/x-mcpemod-pack"

#: Un nombre más largo se parte en dos líneas y descuadra la fila; el completo
#: queda en el tooltip.
_LARGO_NOMBRE = 30


def _recortar(nombre: str) -> str:
    limpio = " ".join(nombre.split())
    return limpio if len(limpio) <= _LARGO_NOMBRE else limpio[:_LARGO_NOMBRE].rstrip() + "…"


class Asa(QLabel):
    """Por donde se agarra una fila para arrastrarla.

    Es una zona pequeña y marcada a propósito: si se pudiera arrastrar desde
    cualquier parte de la fila, desplazar la lista con el ratón sería imposible.
    """

    def __init__(self, uuid: str, parent: QWidget | None = None) -> None:
        super().__init__("≡", parent)
        self._uuid = uuid
        self.setToolTip("Arrastra para mover o cambiar de lado")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedWidth(20)
        self.setStyleSheet(f"color: {TEXTO_SECUNDARIO}; font-size: 15px;")

    def mousePressEvent(self, evento: QMouseEvent) -> None:  # noqa: N802 (API de Qt)
        if evento.button() != Qt.MouseButton.LeftButton:
            return
        datos = QMimeData()
        datos.setData(MIME_PACK, self._uuid.encode())

        arrastre = QDrag(self)
        arrastre.setMimeData(datos)
        # La miniatura es la fila entera, no el asa: se arrastra el pack.
        fila = self.parentWidget()
        if fila is not None:
            arrastre.setPixmap(fila.grab())
        arrastre.exec(Qt.DropAction.MoveAction)


class FilaPack(QWidget):
    """Un pack dentro de una columna, con lo que se puede hacerle desde ahí."""

    accion = Signal(object, str)   # pieza, "activar" | "desactivar" | "subir" | "bajar"

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

    def _contenido(self) -> QWidget:
        contenedor = QWidget()
        fila = QHBoxLayout(contenedor)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(GAP_CELDA // 2)

        if self._pieza.uuid:
            fila.addWidget(Asa(self._pieza.uuid, contenedor))

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
        nombre = QLabel(_recortar(self._pieza.nombre))
        nombre.setWordWrap(False)
        nombre.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        nombre.setStyleSheet(f"color: {TEXTO_EN_POZO}; font-size: 12px; font-weight: 600;")
        # Con ancho ignorado: un nombre largo impondría el suyo a la columna y
        # empujaría los botones fuera de la tarjeta.
        nombre.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        nombre.setToolTip(self._pieza.nombre)
        fila.addWidget(nombre, stretch=1)

        if self._pieza.de_la_tienda:
            fila.addWidget(badge("Tienda", VIOLETA))
        elif self._pieza.forma.etiqueta:
            fila.addWidget(badge(self._pieza.forma.etiqueta, AMBAR))
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
            # El orden importa: el último de la lista gana.
            # Con palabras y no con flechas: los glifos ↑↓ no están en la fuente
            # de los botones y salen como cajas vacías.
            for etiqueta, que, ayuda in (
                ("Subir", "subir", "Se aplica antes, así que pierde ante los de abajo"),
                ("Bajar", "bajar", "Se aplica después, así que gana"),
            ):
                b = boton(etiqueta)
                b.setToolTip(ayuda)
                conectar(b.clicked, lambda q=que: self.accion.emit(self._pieza, q))
                fila.addWidget(b)

            quitar = boton("Quitar")
            conectar(quitar.clicked, lambda: self.accion.emit(self._pieza, "desactivar"))
            fila.addWidget(quitar)
        else:
            poner = boton("Activar")
            conectar(poner.clicked, lambda: self.accion.emit(self._pieza, "activar"))
            fila.addWidget(poner)

        return fila


class ColumnaPacks(QWidget):
    """Una de las dos mitades: título, y la lista agrupada con scroll."""

    accion = Signal(object, str)
    #: uuid del pack soltado y en qué posición de esta columna cayó.
    soltado = Signal(str, int)

    def __init__(self, titulo: str, vacio: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vacio = vacio
        self._filas: list[FilaPack] = []
        self.setAcceptDrops(True)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(PARED // 2)

        self._titulo = Tallado(titulo, sobre=SOBRE_BANDEJA)
        raiz.addWidget(self._titulo)
        self._encabezado = titulo

        scroll = QScrollArea()
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

    def dragEnterEvent(self, evento) -> None:  # noqa: N802 (API de Qt)
        if evento.mimeData().hasFormat(MIME_PACK):
            evento.acceptProposedAction()

    def dragMoveEvent(self, evento) -> None:  # noqa: N802 (API de Qt)
        if evento.mimeData().hasFormat(MIME_PACK):
            evento.acceptProposedAction()

    def dropEvent(self, evento) -> None:  # noqa: N802 (API de Qt)
        datos = evento.mimeData()
        if not datos.hasFormat(MIME_PACK):
            return
        evento.acceptProposedAction()
        uuid = bytes(datos.data(MIME_PACK)).decode()
        self.soltado.emit(uuid, self._posicion_en(evento.position().toPoint().y()))

    def pegar_en_el_puntero(self, uuid: str) -> None:
        """Coloca `uuid` donde esté el ratón. Es el `Ctrl+V`."""
        local = self.mapFromGlobal(self.cursor().pos())
        self.soltado.emit(uuid, self._posicion_en(local.y()))

    def _posicion_en(self, y_en_la_columna: int) -> int:
        """En qué hueco de la lista cae esa altura.

        Se compara con el centro de cada fila: soltar en la mitad de arriba pone
        antes, en la de abajo pone después, que es lo que uno espera al colocar
        algo entre dos cosas.
        """
        for indice, fila in enumerate(self._filas):
            if not fila.isVisible():
                continue
            centro = fila.mapTo(self, fila.rect().center()).y()
            if y_en_la_columna < centro:
                return indice
        return len(self._filas)

    def _construir(self, piezas, activo, desfases, agrupado, nota) -> list[QWidget]:
        widgets: list[QWidget] = []
        self._filas = []
        if nota:
            from mcpemod.ui.widgets.lista_por_categoria import aviso
            widgets.append(aviso(nota))

        def fila(pieza: Instalado) -> QWidget:
            f = FilaPack(pieza, activo, desfases.get(pieza.uuid))
            conectar(f.accion, lambda p, q: self.accion.emit(p, q))
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
