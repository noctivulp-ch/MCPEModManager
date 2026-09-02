"""Arrastrar un pack de una columna a otra, sin `QDrag`.

`QDrag.exec()` abre un bucle de eventos **modal** gestionado por la plataforma, y
mientras dura no llega nada que no sea del propio arrastre: sosteniendo un pack no
se podía girar la rueda para desplazar la lista, que es justo lo que hace falta
cuando el sitio donde quieres soltarlo no está en pantalla. Tampoco hay forma de
pintar un hueco donde va a caer: lo único que la API deja poner es una miniatura
pegada al puntero.

Aquí el arrastre se lleva a mano con los eventos de ratón de siempre. Cuesta más
código y da las cuatro cosas que faltaban:

- La fila **desaparece** de su lista en cuanto se levanta, en vez de quedarse
  duplicada bajo el puntero.
- Lo que se sostiene es una **cápsula**: el nombre y la versión, sin los botones,
  porque en el agarre no se pulsa nada.
- Un **hueco** enseña el sitio exacto donde va a caer, con su altura real.
- Cerca del borde la lista **se desplaza sola**, y la rueda sigue funcionando.

No se pierde nada por el camino: `QDrag` sirve para llevar algo a otra
aplicación, y aquí nunca se sale de la ventana.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from wulf_qt import PADDING_CELDA, Pozo

from mcpemod.senales import conectar
from mcpemod.ui.estilo import METAL, TEXTO_EN_POZO, TEXTO_SECUNDARIO

#: Cuánto hay que mover el ratón antes de dar el gesto por arrastre. Sin margen,
#: un clic con la mano poco firme levanta la fila y la suelta en otro sitio.
UMBRAL = 6

#: Franja del borde donde la lista empieza a desplazarse sola, y cuánto avanza
#: por tic en el borde mismo. Es proporcional: roza la banda y va despacio, llega
#: al borde y va rápido.
BANDA = 56
PASO_MAX = 22

#: Cada cuánto se revisa si toca desplazar. 16 ms ≈ un fotograma a 60 Hz.
INTERVALO = 16


class Capsula(QWidget):
    """Lo que se sostiene: el pack sin nada que se pueda pulsar.

    Va como hijo de la ventana y no como ventana propia: una ventana suelta
    parpadea al crearse y en Wayland ni siquiera se puede colocar donde uno
    quiere. `WA_TransparentForMouseEvents` es lo que impide que se tape a sí
    misma el widget que hay debajo, que es el que decide dónde cae.
    """

    def __init__(self, nombre: str, version: str, padre: QWidget) -> None:
        super().__init__(padre)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        caja = QVBoxLayout(self)
        caja.setContentsMargins(0, 0, 0, 0)

        dentro = QWidget()
        texto = QVBoxLayout(dentro)
        texto.setContentsMargins(0, 0, 0, 0)
        texto.setSpacing(2)

        titulo = QLabel(nombre)
        titulo.setStyleSheet(
            f"color: {TEXTO_EN_POZO}; font-size: 12px; font-weight: 600;"
        )
        texto.addWidget(titulo)

        detalle = QLabel(version)
        detalle.setStyleSheet(f"color: {TEXTO_SECUNDARIO}; font-size: 10px;")
        texto.addWidget(detalle)

        pozo = Pozo(dentro, padding=PADDING_CELDA // 2)
        # Con el nombre y no a secas: una hoja de estilo sin selector la heredan
        # todos los descendientes, y el canto salía repetido alrededor de cada
        # etiqueta de dentro.
        pozo.setObjectName("capsula")
        pozo.setStyleSheet(f"#capsula {{ border: 1px solid {METAL}; }}")
        caja.addWidget(pozo)


class Hueco(QWidget):
    """El sitio que va a ocupar el pack, con su altura.

    Con la altura de la fila que se levantó y no una fija: el hueco es la promesa
    de dónde va a quedar, y si mide otra cosa la lista da un salto al soltar.
    """

    def __init__(self, alto: int, padre: QWidget | None = None) -> None:
        super().__init__(padre)
        self.setFixedHeight(alto)
        # Un `QWidget` pelado no pinta el fondo ni el canto de su hoja de estilo:
        # hay que pedírselo. Sin esto el hueco existe y ocupa sitio, pero no se
        # ve — que era justo lo que tenía que hacer.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # Sin relleno: un hueco es la ausencia de algo, y pintarlo de un color
        # lo convierte en una fila más. El canto discontinuo ya dice que es un
        # sitio reservado y no una pieza.
        self.setStyleSheet(
            f"background: transparent; border: 1px dashed {METAL};"
            "border-radius: 4px;"
        )


class Arrastre(QObject):
    """Lleva el gesto de principio a fin, por encima de las dos columnas.

    Vive en el panel y no en una columna porque el gesto cruza de una a otra: la
    columna de origen no puede saber dónde acaba.
    """

    def __init__(self, escena: QWidget) -> None:
        super().__init__(escena)
        self._escena = escena
        self._columnas: list = []

        self._fila: QWidget | None = None
        self._origen = None
        self._capsula: Capsula | None = None
        self._hueco: Hueco | None = None
        self._destino = None
        self._posicion = 0
        #: Cancelado con Escape pero con el botón todavía pulsado. Sin esto, el
        #: siguiente movimiento del ratón vuelve a superar el umbral y levanta el
        #: pack otra vez: cancelar duraba hasta que movieras la mano.
        self._vetado = False

        self._reloj = QTimer(self)
        self._reloj.setInterval(INTERVALO)
        conectar(self._reloj.timeout, self._desplazar_si_toca)

    def registrar(self, *columnas) -> None:
        self._columnas = list(columnas)

    @property
    def activo(self) -> bool:
        return self._fila is not None

    # ── El gesto ──────────────────────────────────────────────────────────────

    def empezar(self, fila, columna, global_pos: QPoint) -> None:
        if self.activo or self._vetado:
            return
        self._fila = fila
        self._origen = columna

        pieza = fila.pieza
        self._capsula = Capsula(
            pieza.nombre, f"v{pieza.version or '?'}", self._escena
        )
        self._capsula.setFixedWidth(max(fila.width() // 2, 220))
        # El alto lo pone el contenido, y hay que pedirlo: un hijo al que nadie
        # coloca en un layout se queda con el tamaño mínimo y sale aplastado.
        self._capsula.adjustSize()
        self._capsula.show()
        self._capsula.raise_()

        self._hueco = Hueco(fila.height())
        # La fila se va **antes** de poner el hueco: si no, la lista crece de
        # golpe la altura de los dos y todo lo de debajo pega un salto.
        fila.hide()

        self._escena.window().installEventFilter(self)
        self._reloj.start()
        self.mover(global_pos)

    def mover(self, global_pos: QPoint) -> None:
        if not self.activo:
            return

        capsula = self._capsula
        # El puntero agarra la cápsula por su borde izquierdo y a media altura,
        # que es donde estaba el asa: así lo que se sostiene no salta de sitio
        # respecto a donde se pinchó.
        capsula.move(
            self._escena.mapFromGlobal(global_pos)
            - QPoint(0, capsula.height() // 2)
        )

        columna = self._columna_en(global_pos)
        if columna is None:
            self._quitar_hueco()
            self._destino = None
            return

        self._posicion = columna.indice_en(global_pos)
        if self._destino is not columna:
            self._quitar_hueco()
            self._destino = columna
        columna.poner_hueco(self._hueco, self._posicion)

    def soltar(self) -> None:
        destino, posicion = self._destino, self._posicion
        pieza = self._fila.pieza if self._fila else None
        self._terminar()
        if destino is not None and pieza is not None and pieza.uuid:
            destino.soltado.emit(pieza.uuid, posicion)

    def cancelar(self) -> None:
        """Escape: el pack vuelve a su sitio y no se mueve nada.

        Queda **vetado** hasta que se suelte el botón. Cancelar y seguir con el
        dedo apretado es lo normal —se cancela precisamente porque uno ya no
        quiere soltarlo ahí—, y sin el veto el gesto revivía al mover la mano.
        """
        fila = self._fila
        self._terminar()
        self._vetado = True
        if fila is not None:
            fila.show()

    def terminar_gesto(self) -> None:
        """Se ha soltado el botón, que es lo único que cierra un gesto.

        Suelta el pack si había uno en el aire, y en cualquier caso levanta el
        veto: a partir de aquí un pinchazo nuevo vuelve a poder arrastrar.
        """
        if self.activo:
            self.soltar()
        self._vetado = False

    def _terminar(self) -> None:
        self._reloj.stop()
        self._escena.window().removeEventFilter(self)
        self._quitar_hueco()
        if self._capsula is not None:
            # Esconder antes de destruir: `deleteLater` espera al siguiente ciclo
            # de eventos, y hasta entonces la cápsula se quedaba colgando del
            # puntero un fotograma después de haber soltado.
            self._capsula.hide()
            self._capsula.deleteLater()
        self._capsula = None
        self._hueco = None
        self._fila = None
        self._origen = None
        self._destino = None

    def _quitar_hueco(self) -> None:
        if self._hueco is not None and self._hueco.parent() is not None:
            self._hueco.setParent(None)

    def _columna_en(self, global_pos: QPoint):
        for columna in self._columnas:
            if columna.rect().contains(columna.mapFromGlobal(global_pos)):
                return columna
        return None

    # ── Desplazar mientras se sostiene ────────────────────────────────────────

    def eventFilter(self, obj, evento) -> bool:  # noqa: N802 (API de Qt)
        """La rueda y el Escape mientras se sostiene algo.

        La rueda va a la columna que hay **bajo el puntero**, no a la que tuviera
        el foco: sosteniendo un pack lo que se mira es dónde soltarlo.
        """
        if not self.activo:
            return False

        if evento.type() == QEvent.Type.Wheel:
            columna = self._columna_en(evento.globalPosition().toPoint())
            if columna is not None:
                columna.desplazar(-evento.angleDelta().y())
                self.mover(evento.globalPosition().toPoint())
                return True

        elif evento.type() == QEvent.Type.KeyPress:
            if evento.key() == Qt.Key.Key_Escape:
                self.cancelar()
                return True

        elif evento.type() == QEvent.Type.WindowDeactivate:
            # Cambiar de ventana con un pack en el aire: al volver no hay forma
            # de saber si el botón sigue pulsado, así que se deshace. La cápsula
            # se quedaba flotando encima de la otra aplicación.
            self.cancelar()

        return False

    def _desplazar_si_toca(self) -> None:
        """Cerca del borde, la lista avanza sola.

        Sin esto, mover un pack a un sitio que no está en pantalla obliga a
        soltarlo a medio camino y volver a cogerlo.
        """
        if not self.activo:
            return
        global_pos = self._escena.cursor().pos()
        columna = self._columna_en(global_pos)
        if columna is None:
            return

        paso = columna.paso_de_borde(global_pos, BANDA, PASO_MAX)
        if paso:
            columna.desplazar(paso)
            self.mover(global_pos)
