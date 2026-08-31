"""Emparejar lo instalado con lo publicado, y saber qué tiene versión nueva.

Qué pack es lo dice su **nombre**; qué versión, el uuid (ver
`mcpemod.core.identidad`). Eso ordena todo lo de aquí:

1. Se buscan candidatos por título y autor, que es lo que el catálogo indexa.
2. Se ordenan poniendo delante los del mismo autor que declara el manifiesto
   instalado — es la señal más barata y la que más acierta.
3. Se **confirma** leyendo el manifiesto publicado por `Range` y comparando el
   nombre del pack. Solo el positivo cuenta: un candidato que no se pueda leer
   nunca produce un emparejamiento.

El uuid no sirve para emparejar, pero sí dice algo una vez emparejado: si el
publicado tiene el mismo uuid que el instalado, es **exactamente la misma
versión**, aunque el número de versión diga otra cosa.

Confirmar cuesta peticiones, así que el resultado se guarda: un pack ya
emparejado no se vuelve a buscar, solo se le mira la versión.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from .fuentes import Descarga, Fuente, Publicacion
from .identidad import clave_de_pack
from .mod import Instalado
from .red import ErrorRed
from .store import Store
from .version import EstadoVersion, comparar
from .zip_remoto import leer_manifiestos

#: Cuántos candidatos se miran por consulta. Si no está entre los primeros es
#: que la búsqueda no lo encontró, y mirar más solo multiplica el coste.
MAX_CANDIDATOS = 3

#: Techo de manifiestos remotos leídos por pack, sumando todas sus consultas.
#: Es lo que acota el peor caso: sin él, un pack cuyos candidatos son addons
#: grandes se lleva varios minutos él solo, y con sesenta por delante eso no
#: termina nunca.
MAX_LECTURAS = 5

#: Cuánto vale un emparejamiento antes de volver a mirarle la versión.
VIGENCIA = timedelta(hours=12)

#: Cuánto se espera antes de reintentar un pack que no se encontró. Los packs
#: que no están en ningún catálogo son muchos y no van a aparecer mañana.
REINTENTO_FALLIDO = timedelta(days=7)


class Confianza(Enum):
    """Cuánto se sabe de que la publicación encontrada es el pack instalado."""

    #: El manifiesto publicado declara el mismo nombre de pack. Es la identidad
    #: que usa el juego para reconocer una actualización.
    CONFIRMADO = "confirmado"
    #: El nombre no coincide del todo, pero es del mismo autor y se parece mucho.
    #: Queda a criterio de quien mira.
    PROBABLE = "probable"
    NINGUNO = "ninguno"


def _es_el_mismo_pack(manifiesto, pieza: Instalado) -> bool:
    """Si el manifiesto publicado es el mismo pack que el instalado.

    Hacen falta las dos señales porque los autores no son consistentes, y cada
    una cubre lo que la otra pierde:

    - Unos mantienen el **nombre** y cambian el uuid en cada versión (uno del
      equipo de prueba codifica el número de versión dentro del uuid).
    - Otros mantienen el **uuid** y meten la versión en el nombre, que así cambia
      en cada publicación.

    Con una sola señal, la mitad de los packs quedaría sin emparejar.
    """
    if manifiesto.uuid and manifiesto.uuid == pieza.uuid:
        return True
    return bool(pieza.clave) and clave_de_pack(manifiesto.nombre) == pieza.clave


class _Presupuesto:
    """Cuántas lecturas remotas quedan para un pack."""

    def __init__(self, maximo: int) -> None:
        self._quedan = maximo

    @property
    def agotado(self) -> bool:
        return self._quedan <= 0

    def gastar(self) -> bool:
        if self.agotado:
            return False
        self._quedan -= 1
        return True


@dataclass(frozen=True)
class Resultado:
    """Lo que se sabe de un pack instalado respecto de su publicación."""

    pieza: Instalado
    publicacion: Publicacion | None = None
    descarga: Descarga | None = None
    version_remota: str | None = None
    #: El uuid del manifiesto publicado: identifica la versión, no el pack.
    uuid_remoto: str | None = None
    confianza: Confianza = Confianza.NINGUNO

    @property
    def encontrado(self) -> bool:
        return self.publicacion is not None

    @property
    def seguro(self) -> bool:
        return self.confianza is Confianza.CONFIRMADO

    @property
    def estado(self) -> EstadoVersion:
        if not self.encontrado:
            return EstadoVersion.DESCONOCIDA
        return comparar(self.pieza.version, self.version_remota)

    @property
    def hay_actualizacion(self) -> bool:
        """Solo cuenta como actualización lo confirmado, y con versión mayor.

        Una coincidencia probable puede ser otro pack del mismo autor: ofrecerla
        sobrescribiría lo instalado con algo que no es.

        El uuid **no** entra en esta cuenta. Lo normal es que sea el mismo entre
        versiones —es lo que dice la norma: identifica el pack, no la versión— así
        que exigir que cambie dejaba fuera casi todas las actualizaciones reales.
        Fue un residuo de haber tenido esa idea al revés.
        """
        return self.seguro and self.estado == EstadoVersion.NUEVA


class Buscador:
    def __init__(self, store: Store, fuentes: list[Fuente]) -> None:
        self._store = store
        self._fuentes = fuentes

    def pendientes(self, piezas: list[Instalado]) -> list[Instalado]:
        """Los packs a los que toca mirar, en orden de utilidad.

        Se descarta lo que el gestor no puede actualizar de todas formas: lo de
        la tienda lo lleva el juego, y sin uuid o sin versión no hay nada que
        comparar.
        """
        ahora = datetime.now()
        cache = self._store.emparejamientos()
        listos = []

        for pieza in piezas:
            if not pieza.gestionable or not pieza.uuid or not pieza.version:
                continue
            guardado = cache.get(pieza.uuid)
            if guardado is None:
                listos.append(pieza)
                continue
            espera = VIGENCIA if guardado["encontrado"] else REINTENTO_FALLIDO
            if ahora - guardado["comprobado_en"] > espera:
                listos.append(pieza)

        # Lo nunca comprobado primero: es donde está toda la información nueva.
        listos.sort(key=lambda p: (p.uuid in cache, p.nombre.lower()))
        return listos

    def desde_cache(self, piezas: list[Instalado]) -> list[Resultado]:
        """Lo que ya se sabe, sin tocar la red."""
        cache = self._store.emparejamientos()
        resultados = []
        for pieza in piezas:
            guardado = cache.get(pieza.uuid) if pieza.uuid else None
            if guardado is None or not guardado["encontrado"]:
                continue
            resultados.append(Resultado(
                pieza=pieza,
                publicacion=Publicacion(
                    fuente=guardado["fuente"], id=guardado["id_publicacion"],
                    titulo=guardado["titulo"], autor=guardado["autor"],
                    url=guardado["url_publicacion"],
                ),
                descarga=Descarga(
                    nombre=guardado["nombre_archivo"] or "",
                    url=guardado["url_descarga"] or "",
                ) if guardado["url_descarga"] else None,
                version_remota=guardado["version_remota"],
                uuid_remoto=guardado["uuid_remoto"],
                confianza=Confianza(guardado["confianza"] or "ninguno"),
            ))
        return resultados

    def comprobar(self, pieza: Instalado) -> Resultado:
        """Busca y confirma un pack. Hace red; llamar fuera del hilo de la UI."""
        guardado = self._store.emparejamientos().get(pieza.uuid)
        if guardado and guardado["encontrado"]:
            resultado = self._revisar_conocido(pieza, guardado)
            if resultado is not None:
                return resultado

        for fuente in self._fuentes:
            resultado = self._buscar_en(fuente, pieza)
            if resultado is not None:
                self._guardar(pieza, resultado)
                return resultado

        self._store.guardar_emparejamiento(pieza.uuid, encontrado=False)
        return Resultado(pieza=pieza)

    # ── Interno ───────────────────────────────────────────────────────────────

    def _revisar_conocido(self, pieza: Instalado, guardado: dict) -> Resultado | None:
        """Vuelve a mirar la publicación que ya se le conoce a este pack."""
        fuente = next((f for f in self._fuentes if f.nombre == guardado["fuente"]), None)
        if fuente is None:
            return None
        try:
            candidatos = fuente.buscar(guardado["titulo"], por_pagina=MAX_CANDIDATOS)
        except ErrorRed:
            return None

        publicacion = next((c for c in candidatos if c.id == guardado["id_publicacion"]), None)
        if publicacion is None:
            return None
        return self._confirmar(pieza, publicacion)

    def _buscar_en(self, fuente: Fuente, pieza: Instalado) -> Resultado | None:
        lecturas = _Presupuesto(MAX_LECTURAS)
        probable = None

        for consulta in _consultas(pieza):
            try:
                candidatos = fuente.buscar(consulta, por_pagina=MAX_CANDIDATOS * 2)
            except ErrorRed:
                return None

            ordenados = _ordenar(candidatos, pieza)
            for candidato in ordenados[:MAX_CANDIDATOS]:
                if lecturas.agotado:
                    break
                resultado = self._confirmar(pieza, candidato, lecturas)
                if resultado is not None:
                    return resultado

            if probable is None:
                probable = _probable(ordenados, pieza)

            # Una consulta que ya trajo al autor dio lo que podía dar: seguir con
            # versiones más vagas del nombre solo trae ruido, y cada una cuesta
            # otra tanda de lecturas.
            if probable is not None or lecturas.agotado:
                break

        if probable is not None:
            return Resultado(
                pieza=pieza, publicacion=probable, descarga=probable.ultima,
                confianza=Confianza.PROBABLE,
            )
        return None

    def _confirmar(
        self, pieza: Instalado, publicacion: Publicacion,
        lecturas: _Presupuesto | None = None,
    ) -> Resultado | None:
        """Lee el manifiesto publicado y acepta si es el mismo pack.

        Se miran todos los manifiestos del archivo porque un `.mcaddon` trae
        varios packs dentro y el instalado puede ser cualquiera de ellos.

        Solo se mira el archivo más reciente: las versiones viejas que el
        catálogo conserva llevan el mismo uuid, así que no aportan nada nuevo y
        cada una cuesta otra lectura.
        """
        descarga = publicacion.ultima
        if descarga is None or (lecturas is not None and not lecturas.gastar()):
            return None

        for manifiesto in leer_manifiestos(descarga.url):
            if not _es_el_mismo_pack(manifiesto, pieza):
                continue
            return Resultado(
                pieza=pieza, publicacion=publicacion, descarga=descarga,
                version_remota=manifiesto.version, uuid_remoto=manifiesto.uuid,
                confianza=Confianza.CONFIRMADO,
            )
        return None

    def _guardar(self, pieza: Instalado, resultado: Resultado) -> None:
        self._store.guardar_emparejamiento(
            pieza.uuid, encontrado=True,
            fuente=resultado.publicacion.fuente,
            id_publicacion=resultado.publicacion.id,
            titulo=resultado.publicacion.titulo,
            autor=resultado.publicacion.autor,
            url_publicacion=resultado.publicacion.url,
            confianza=resultado.confianza.value,
            version_remota=resultado.version_remota,
            uuid_remoto=resultado.uuid_remoto,
            url_descarga=resultado.descarga.url if resultado.descarga else None,
            nombre_archivo=resultado.descarga.nombre if resultado.descarga else None,
        )


def _consultas(pieza: Instalado) -> list[str]:
    """Qué preguntarle al catálogo, de lo más específico a lo más general.

    El nombre del manifiesto suele traer la versión pegada («Hide Armor | V1.2»),
    y eso estrecha la búsqueda hasta no encontrar nada: se prueba también sin
    ella.
    """
    nombre = pieza.nombre.strip()
    consultas = [nombre]

    limpio = _sin_adornos(nombre)
    if limpio and limpio != nombre:
        consultas.append(limpio)

    # Los títulos largos no encuentran nada: el catálogo busca por coincidencia
    # de todas las palabras, y el nombre del manifiesto suele traer de más.
    palabras = limpio.split()
    for cuantas in (3, 2):
        if len(palabras) > cuantas:
            consultas.append(" ".join(palabras[:cuantas]))
    return list(dict.fromkeys(c for c in consultas if len(c) >= 3))


def _sin_adornos(nombre: str) -> str:
    """Quita marcas de versión y sufijos de tipo del nombre de un pack."""
    limpio = re.sub(r"[\[(].*?[\])]", " ", nombre)
    limpio = re.sub(r"\bv?\d+(\.\d+)+\b", " ", limpio, flags=re.IGNORECASE)
    limpio = re.sub(r"\b(rp|bp|resource pack|behavior pack|addon|add-on)\b", " ",
                    limpio, flags=re.IGNORECASE)
    limpio = re.sub(r"[|·:_]+", " ", limpio)
    return re.sub(r"\s+", " ", limpio).strip(" -–—")


def _ordenar(candidatos: list[Publicacion], pieza: Instalado) -> list[Publicacion]:
    """Primero los que más se parecen, para gastar las pocas lecturas en ellos.

    La señal más fuerte es la página que el propio pack declara en
    `metadata.url`: cuando está, señala directamente su publicación y no hay nada
    que adivinar. La declaran pocos, así que después va el autor, que sale de
    `metadata.authors` y es lo que distingue el pack original de las diez
    reediciones con el mismo nombre.
    """
    autores = {a.lower() for a in pieza.autores}
    objetivo = _sin_adornos(pieza.nombre).lower()
    declarada = _normalizar_url(pieza.url)

    def puntuar(c: Publicacion) -> tuple:
        misma_url = bool(declarada) and _normalizar_url(c.url) == declarada
        mismo_autor = any(a and a in c.autor.lower() for a in autores)
        titulo = _sin_adornos(c.titulo).lower()
        return (
            not misma_url,
            not mismo_autor,
            not (titulo == objetivo),
            not (objetivo in titulo or titulo in objetivo),
            -c.descargas_totales,
        )

    return sorted(candidatos, key=puntuar)


def _normalizar_url(url: str) -> str:
    """Para comparar direcciones que solo difieren en la barra final o el `www`."""
    return url.strip().lower().rstrip("/").replace("://www.", "://") if url else ""


def _probable(candidatos: list[Publicacion], pieza: Instalado) -> Publicacion | None:
    """El candidato que casi seguro es este pack, aunque el uuid no lo confirme.

    Hace falta porque hay autores que cambian el `header.uuid` al publicar una
    versión mayor, y entonces no queda ninguna señal automática que lo demuestre.
    Se exige mismo autor **y** título equivalente: con una sola de las dos, el
    catálogo está lleno de reediciones que cumplirían.
    """
    autores = {a.lower() for a in pieza.autores if a}
    if not autores:
        return None

    objetivo = _sin_adornos(pieza.nombre).lower()
    if len(objetivo) < 4:
        return None

    for c in candidatos:
        if not any(a in c.autor.lower() for a in autores):
            continue
        titulo = _sin_adornos(c.titulo).lower()
        if titulo == objetivo or objetivo in titulo or titulo in objetivo:
            return c
    return None
