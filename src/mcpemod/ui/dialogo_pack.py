"""La ficha de un pack: qué es, qué dice su autor y qué variante se le aplica.

Una fila de la lista solo cabe el nombre y la versión, y eso deja fuera lo que
más se pregunta uno antes de activar algo: qué hace, quién lo hizo, de qué
depende. Todo eso está en el manifiesto y hasta ahora no se enseñaba en ninguna
parte.

Y las **variantes**. La documentación oficial las llama por lo que son: *«sub-packs
let players choose between different variations of a resource pack and switch
between them at any time»*. No son packs distintos, son las opciones del pack —
hojas redondas o normales, con efectos o sin ellos, cada cuánto aparece una
estructura—. El juego las enseña al pulsar sobre el pack en su propia lista, y
este es el sitio equivalente.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup, QHBoxLayout, QLabel, QRadioButton, QScrollArea, QVBoxLayout,
    QWidget,
)

from wulf_qt import (
    GAP_CELDA, PADDING_CELDA, PARED, Acciones, Dialogo, Tallado, boton,
    boton_primario,
)

from mcpemod.core.activacion import Ambito, ErrorActivacion
from mcpemod.core.manifiesto import Manifiesto
from mcpemod.core.miniatura import de_ruta, leer
from mcpemod.core.mod import Instalado
from mcpemod.senales import conectar
from mcpemod.ui import iconos
from mcpemod.ui.estilo import (
    AMBAR, GRIS, SOBRE_BANDEJA, TEXTO_EN_POZO, TEXTO_SECUNDARIO, VIOLETA,
)
from mcpemod.ui.widgets.badge import badge
from mcpemod.ui.widgets.miniatura import GRANDE, MiniaturaDe

#: Lo que el juego elige solo cuando nadie ha elegido. No es «sin variante»: la
#: documentación dice que sin elección coge «the highest memory_performance_tier
#: value that doesn't exceed the tier of the player's device».
AUTOMATICO = "  (automático)"


@dataclass(frozen=True)
class Ficha:
    """Lo que la ficha enseña, venga de donde venga.

    Un pack instalado y un archivo de la carpeta de descargas tienen las mismas
    cosas que contar —qué es, quién lo hizo, qué variantes trae— pero no son lo
    mismo: el segundo no está puesto en ninguna parte. Fabricar un `Instalado`
    falso para reaprovechar la ficha lo haría parecer instalado en cuanto
    cualquiera lo pasara a otra función.

    `pieza` solo lo trae lo que sí está instalado, y es lo único que permite
    elegir variante: la elección se guarda en la entrada de activación.
    """

    nombre: str
    version: str | None
    categoria: str
    portada_clave: str
    portada: object                      # callable, para no abrir el zip de más
    manifiesto: Manifiesto | None = None
    autores: tuple[str, ...] = ()
    url: str = ""
    licencia: str = ""
    marcas: tuple[tuple[str, str], ...] = ()
    pieza: Instalado | None = None


def de_instalado(pieza: Instalado, manifiesto: Manifiesto | None) -> Ficha:
    marcas = []
    if pieza.de_la_tienda:
        marcas.append(("Tienda", VIOLETA))
    if pieza.forma.etiqueta:
        marcas.append((pieza.forma.etiqueta, AMBAR))
    if pieza.licencia:
        marcas.append((pieza.licencia, GRIS))
    return Ficha(
        nombre=pieza.nombre, version=pieza.version,
        categoria=pieza.categoria.etiqueta,
        portada_clave=str(pieza.ruta), portada=lambda: leer(pieza),
        manifiesto=manifiesto, autores=pieza.autores, url=pieza.url,
        licencia=pieza.licencia, marcas=tuple(marcas), pieza=pieza,
    )


def de_componente(ruta, componente) -> Ficha:
    """Un pack dentro de un archivo que todavía no se ha instalado.

    El manifiesto ya viene leído en el componente: lo dejó ahí el análisis del
    archivo, así que no hay que volver a abrir el zip para la descripción.
    """
    m = componente.manifiesto
    return Ficha(
        nombre=componente.nombre, version=componente.version,
        categoria=componente.categoria.etiqueta,
        portada_clave=f"{ruta}|{componente.prefijo}|{componente.anidado_en}",
        portada=lambda: de_ruta(ruta, componente.prefijo, componente.anidado_en),
        manifiesto=m,
        autores=m.autores if m else (), url=m.url if m else "",
        licencia=m.licencia if m else "",
        marcas=(("sin instalar", GRIS),),
    )


class FichaPack(QWidget):
    """El cuerpo del diálogo. Aparte para poder probarlo sin abrir nada."""

    def __init__(
        self,
        ficha: Ficha,
        ambito: Ambito | None = None,
        activo: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._ficha = ficha
        self._pieza = ficha.pieza
        self._manifiesto = ficha.manifiesto
        # Sin pieza instalada no hay entrada de activación donde guardar la
        # elección, así que las variantes se enseñan y no se tocan.
        self._ambito = ambito if ficha.pieza is not None else None
        self._grupo: QButtonGroup | None = None

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(PARED)
        raiz.addLayout(self._cabecera())

        cuerpo = QVBoxLayout()
        cuerpo.setSpacing(GAP_CELDA)
        for bloque in self._bloques(activo):
            cuerpo.addWidget(bloque)
        cuerpo.addStretch()

        dentro = QWidget()
        dentro.setLayout(cuerpo)
        # Con scroll: la descripción de algunos packs es media pantalla, y sin
        # esto el diálogo crece hasta salirse.
        vista = QScrollArea()
        vista.setWidgetResizable(True)
        vista.setFrameShape(QScrollArea.Shape.NoFrame)
        vista.setWidget(dentro)
        raiz.addWidget(vista, stretch=1)

    # ── Partes ────────────────────────────────────────────────────────────────

    def _cabecera(self) -> QHBoxLayout:
        fila = QHBoxLayout()
        fila.setSpacing(GAP_CELDA)
        fila.addWidget(
            MiniaturaDe(self._ficha.portada_clave, self._ficha.portada, GRANDE),
            alignment=Qt.AlignmentFlag.AlignTop,
        )

        # Sin repetir el nombre: es el título del diálogo, y ahí se lee mejor
        # —completo y sin competir con la portada—.
        texto = QVBoxLayout()
        texto.setSpacing(2)
        senas = [f"v{self._ficha.version or '?'}", self._ficha.categoria]
        if self._ficha.autores:
            senas.append("de " + ", ".join(self._ficha.autores))
        linea = QLabel("  ·  ".join(senas))
        linea.setWordWrap(True)
        linea.setStyleSheet(f"color: {TEXTO_SECUNDARIO}; font-size: 11px;")
        texto.addWidget(linea)

        marcas = QHBoxLayout()
        marcas.setSpacing(GAP_CELDA // 3)
        for etiqueta, color in self._ficha.marcas:
            marcas.addWidget(badge(etiqueta, color))
        marcas.addStretch()
        texto.addLayout(marcas)

        fila.addLayout(texto, stretch=1)
        return fila

    def _bloques(self, activo: bool) -> list[QWidget]:
        bloques = []
        m = self._manifiesto

        if m and m.descripcion:
            bloques.append(_parrafo(m.descripcion))

        # Los `settings` de tipo label: la documentación los describe como «a
        # description of what the pack and sub-packs include». Es donde el autor
        # avisa de cosas como que hay que reiniciar el juego.
        for nota in (m.notas if m else ()):
            bloques.append(_parrafo(nota, secundario=True))

        if m and m.subpacks:
            bloques.append(self._variantes(m, activo))

        if m and m.dependencias:
            bloques.append(_seccion(
                f"Necesita otros {len(m.dependencias)} packs",
                "Si alguno falta, este no funciona del todo. El juego no avisa.",
            ))

        if not bloques:
            bloques.append(_parrafo(
                "Este pack no trae descripción en su manifiesto.", secundario=True
            ))
        return bloques

    def _variantes(self, m: Manifiesto, activo: bool) -> QWidget:
        caja = QWidget()
        columna = QVBoxLayout(caja)
        columna.setContentsMargins(0, 0, 0, 0)
        columna.setSpacing(GAP_CELDA // 2)

        columna.addWidget(_titulo("Variantes"))
        columna.addWidget(_nota(
            "Son las opciones del pack, no packs distintos. Cambiarlas mientras el "
            "juego está abierto no surte efecto: hay que reiniciarlo."
        ))

        if self._ambito is None or not activo:
            columna.addWidget(_nota(
                "Se elige desde la pestaña de activación, con el pack ya aplicado."
                if self._ambito is None else
                "Actívalo primero: la variante se guarda junto a la activación."
            ))
            for s in m.subpacks:
                columna.addWidget(_nota(f"   ·  {s.nombre}"))
            return caja

        elegido = self._ambito.subpack_de(self._pieza)
        self._grupo = QButtonGroup(self)

        # El sistema de diseño le da al radio la misma forma que a la casilla
        # —comparten la regla del indicador— y salía cuadrado. Son cosas
        # distintas: la casilla marca varias, el radio elige una. Redondearlo
        # entero es lo que las separa de un vistazo.
        caja.setStyleSheet(
            f"QRadioButton::indicator {{ border-radius: {PADDING_CELDA // 2}px; }}"
        )

        opciones = [(None, f"Lo elige el juego{AUTOMATICO}")]
        opciones += [(s.carpeta, s.nombre) for s in m.subpacks]
        for carpeta, etiqueta in opciones:
            radio = QRadioButton(etiqueta)
            radio.setChecked(carpeta == elegido)
            radio.setProperty("carpeta", carpeta)
            self._grupo.addButton(radio)
            columna.addWidget(radio)

        return caja

    # ── Guardar ───────────────────────────────────────────────────────────────

    @property
    def hay_variantes_que_guardar(self) -> bool:
        return self._grupo is not None

    def guardar_variante(self) -> str | None:
        """Aplica la variante marcada. Devuelve el error, o `None` si fue bien."""
        if self._grupo is None or self._ambito is None:
            return None
        marcado = self._grupo.checkedButton()
        if marcado is None:
            return None
        try:
            self._ambito.elegir_subpack(self._pieza, marcado.property("carpeta"))
        except (ErrorActivacion, OSError) as e:
            return str(e)
        return None


def _titulo(texto: str) -> QLabel:
    etiqueta = Tallado(texto, sobre=SOBRE_BANDEJA)
    etiqueta.setStyleSheet("font-size: 12px; font-weight: 600;")
    return etiqueta


def _parrafo(texto: str, secundario: bool = False) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setWordWrap(True)
    color = TEXTO_SECUNDARIO if secundario else TEXTO_EN_POZO
    etiqueta.setStyleSheet(f"color: {color}; font-size: 12px;")
    return etiqueta


def _nota(texto: str) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setWordWrap(True)
    etiqueta.setStyleSheet(f"color: {TEXTO_SECUNDARIO}; font-size: 11px;")
    return etiqueta


def _seccion(titulo: str, nota: str) -> QWidget:
    caja = QWidget()
    columna = QVBoxLayout(caja)
    columna.setContentsMargins(0, 0, 0, 0)
    columna.setSpacing(2)
    columna.addWidget(_titulo(titulo))
    columna.addWidget(_nota(nota))
    return caja


def dialogo_pack(
    ficha_datos: Ficha,
    ambito: Ambito | None = None,
    activo: bool = False,
    parent: QWidget | None = None,
) -> Dialogo:
    ficha = FichaPack(ficha_datos, ambito, activo)

    # `Acciones` decide dónde va cada botón: confirmar a la derecha, y lo que
    # actúa sobre el objeto —abrir el sitio del autor— lejos del pulgar.
    extras = []
    if ficha_datos.url:
        sitio = iconos.poner(boton("Sitio del pack"), iconos.SITIO)
        sitio.setToolTip(ficha_datos.url)
        conectar(sitio.clicked,
                 lambda: QDesktopServices.openUrl(QUrl(ficha_datos.url)))
        extras.append(sitio)

    aplicar = None
    if ficha.hay_variantes_que_guardar:
        aplicar = iconos.poner(boton_primario("Aplicar variante"), iconos.GUARDAR)

    cerrar = boton("Cerrar")
    dialogo = Dialogo(
        ficha_datos.nombre, ficha,
        Acciones(confirmar=aplicar, cancelar=cerrar, extras=extras or None),
        parent,
    )
    dialogo.resize(560, 520)

    conectar(cerrar.clicked, dialogo.reject)
    if aplicar is not None:
        conectar(aplicar.clicked, lambda: _aplicar(dialogo, ficha))
    return dialogo


def _aplicar(dialogo: Dialogo, ficha: FichaPack) -> None:
    error = ficha.guardar_variante()
    if error:
        from wulf_qt import mostrar_aviso
        mostrar_aviso(dialogo, error)
        return
    dialogo.accept()
