"""Aceptar archivos y carpetas soltados sobre la ventana.

Arrastrar es el gesto natural para "toma esto": un pack se instala, una carpeta
se empieza a vigilar. Se decide por lo que es cada cosa, no preguntando.

Instalar sin confirmar es aceptable porque es reversible —el botón Desinstalar
está justo al lado— y porque soltar un pack sobre un gestor de packs no admite
otra lectura. Lo que sí hace falta es decir después qué pasó con cada archivo,
que es lo que devuelve `Resultado`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QMimeData

from mcpemod.core import ErrorInstalacion, Installer, Scanner, analizar


@dataclass
class Resultado:
    instalados: list[str] = field(default_factory=list)
    carpetas: list[str] = field(default_factory=list)
    ignorados: list[str] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)

    @property
    def hubo_algo(self) -> bool:
        return bool(self.instalados or self.carpetas or self.errores)

    def mensaje(self) -> str:
        partes = []
        if self.instalados:
            partes.append(f"Instalado: {', '.join(self.instalados)}")
        if self.carpetas:
            partes.append(f"Ahora también miro: {', '.join(self.carpetas)}")
        if self.errores:
            partes.extend(self.errores)
        if self.ignorados:
            cuantos = len(self.ignorados)
            if cuantos == 1:
                partes.append(f"{self.ignorados[0]} no es contenido de Bedrock")
            else:
                partes.append(f"{cuantos} archivos no son contenido de Bedrock")
        return "\n".join(partes)


def rutas_de(mime: QMimeData) -> list[Path]:
    """Las rutas locales de un arrastre, o vacío si no trae ninguna."""
    if not mime.hasUrls():
        return []
    return [
        Path(url.toLocalFile())
        for url in mime.urls()
        if url.isLocalFile() and url.toLocalFile()
    ]


def admite(rutas: list[Path]) -> bool:
    return any(r.exists() for r in rutas)


def procesar(rutas: list[Path], scanner: Scanner, installer: Installer) -> Resultado:
    """Instala los archivos que sean contenido y vigila las carpetas."""
    resultado = Resultado()
    vigiladas = scanner.carpetas()

    for ruta in rutas:
        if not ruta.exists():
            continue

        if ruta.is_dir():
            # Una carpeta soltada podría ser un pack ya extraído, pero también
            # —y más a menudo— el sitio donde se guardan las descargas. Vigilarla
            # no destruye nada; instalarla por error, sí.
            if ruta in vigiladas:
                resultado.ignorados.append(f"{ruta.name} (ya vigilada)")
            else:
                scanner.agregar_carpeta(ruta)
                vigiladas = scanner.carpetas()
                resultado.carpetas.append(ruta.name)
            continue

        analisis = analizar(ruta)
        if analisis is None:
            resultado.ignorados.append(ruta.name)
            continue

        try:
            installer.instalar(analisis, scanner.indice_por_uuid())
            resultado.instalados.append(analisis.nombre)
        except (ErrorInstalacion, OSError) as e:
            resultado.errores.append(f"{ruta.name}: {e}")

    if resultado.instalados:
        scanner.notificar_cambio()
    return resultado
