"""Lógica de instalación, desinstalación y actualización de mods."""

from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from .mod import EntradaHistorial, Mod, TipoArchivo
from .rutas import BEHAVIOR_PACKS_DIR, MODS_DIR, RESOURCE_PACKS_DIR
from .store import Store
from .version import detectar_version, nombre_canonico


class ErrorInstalacion(Exception):
    pass


class Installer:
    def __init__(self, store: Store) -> None:
        self._store = store

    def instalar(self, ruta: Path) -> Mod:
        tipo = TipoArchivo.desde_ruta(ruta)
        if tipo is None:
            raise ErrorInstalacion(f"Tipo de archivo no soportado: {ruta.suffix}")
        if not ruta.is_file():
            raise ErrorInstalacion(f"El archivo ya no existe: {ruta.name}")

        canonico = nombre_canonico(ruta.stem)
        anterior = self._store.buscar_por_canonico(canonico)
        version_anterior = anterior.version if anterior else None

        # La versión vieja se retira antes de poner la nueva: dejar las dos en
        # `mods/` es lo que hace que el launcher cargue dos veces el mismo mod.
        if anterior is not None:
            self._borrar_rutas(anterior, excepto=ruta)
            self._store.eliminar_mod(anterior.archivo)

        rutas = self._instalar_archivo(ruta, tipo)

        mod = Mod(
            nombre=ruta.stem,
            canonico=canonico,
            archivo=ruta.name,
            rutas=rutas,
            tipo=tipo,
            version=detectar_version(ruta),
            hash_sha256=Mod.calcular_hash(ruta),
            instalado=True,
            instalado_en=datetime.now(),
        )

        self._store.guardar_mod(mod)
        self._store.registrar(EntradaHistorial(
            accion="actualizar" if anterior else "instalar",
            archivo=ruta.name,
            version=mod.version,
            version_anterior=version_anterior,
        ))

        return mod

    def desinstalar(self, mod: Mod) -> None:
        self._borrar_rutas(mod)
        self._store.eliminar_mod(mod.archivo)
        self._store.registrar(EntradaHistorial(
            accion="desinstalar",
            archivo=mod.archivo,
            version=mod.version,
            version_anterior=None,
        ))

    # ── Instalación por tipo ──────────────────────────────────────────────────

    def _instalar_archivo(self, origen: Path, tipo: TipoArchivo) -> list[Path]:
        if tipo == TipoArchivo.SO:
            return [self._copiar(origen, MODS_DIR)]
        if tipo == TipoArchivo.MCPACK:
            return [self._instalar_pack(origen)]
        if tipo == TipoArchivo.MCADDON:
            return self._instalar_addon(origen)
        if tipo == TipoArchivo.ZIP:
            return [self._instalar_zip_generico(origen)]
        raise ErrorInstalacion(f"Tipo sin handler: {tipo}")

    def _copiar(self, origen: Path, destino_dir: Path) -> Path:
        destino_dir.mkdir(parents=True, exist_ok=True)
        destino = destino_dir / origen.name
        shutil.copy2(origen, destino)
        return destino

    def _instalar_pack(self, origen: Path, nombre_destino: str | None = None) -> Path:
        destino_dir = (
            RESOURCE_PACKS_DIR if self._detectar_tipo_pack(origen) == "resource"
            else BEHAVIOR_PACKS_DIR
        )
        return self._extraer_zip(origen, destino_dir, nombre_destino or origen.stem)

    def _instalar_addon(self, origen: Path) -> list[Path]:
        """Un `.mcaddon` es un zip de `.mcpack`s: cada uno va a su directorio.

        Los packs internos se materializan en un temporal y no junto al origen —
        escribir en `~/Downloads` durante una instalación ensucia lo que el
        usuario está mirando, y el nombre viene del zip (puede traer rutas).
        """
        rutas: list[Path] = []
        with zipfile.ZipFile(origen) as zf, tempfile.TemporaryDirectory() as tmp:
            for miembro in zf.namelist():
                if not miembro.lower().endswith(".mcpack"):
                    continue
                nombre = Path(miembro).name
                pack = Path(tmp) / nombre
                pack.write_bytes(zf.read(miembro))
                rutas.append(self._instalar_pack(pack))

        if not rutas:
            raise ErrorInstalacion(f"{origen.name} no contiene ningún .mcpack")
        return rutas

    def _instalar_zip_generico(self, origen: Path) -> Path:
        tipo_pack = self._detectar_tipo_pack(origen)
        if tipo_pack is None:
            return self._copiar(origen, MODS_DIR)
        destino_dir = RESOURCE_PACKS_DIR if tipo_pack == "resource" else BEHAVIOR_PACKS_DIR
        return self._extraer_zip(origen, destino_dir, origen.stem)

    # ── Utilidades de disco ───────────────────────────────────────────────────

    def _extraer_zip(self, origen: Path, destino_dir: Path, nombre: str) -> Path:
        destino_dir.mkdir(parents=True, exist_ok=True)
        carpeta = (destino_dir / nombre).resolve()

        # Reinstalar sobre una carpeta existente sin vaciarla deja archivos de la
        # versión anterior mezclados con los nuevos.
        if carpeta.exists():
            shutil.rmtree(carpeta)
        carpeta.mkdir(parents=True)

        try:
            with zipfile.ZipFile(origen) as zf:
                for miembro in zf.namelist():
                    objetivo = (carpeta / miembro).resolve()
                    if not objetivo.is_relative_to(carpeta):
                        raise ErrorInstalacion(
                            f"{origen.name} intenta escribir fuera de su carpeta: {miembro}"
                        )
                zf.extractall(carpeta)
        except zipfile.BadZipFile as e:
            shutil.rmtree(carpeta, ignore_errors=True)
            raise ErrorInstalacion(f"{origen.name} no es un archivo válido o está incompleto") from e

        return carpeta

    def _borrar_rutas(self, mod: Mod, excepto: Path | None = None) -> None:
        for ruta in mod.rutas:
            if excepto is not None and ruta == excepto:
                continue
            if ruta.is_dir():
                shutil.rmtree(ruta, ignore_errors=True)
            elif ruta.exists():
                ruta.unlink()

    def _detectar_tipo_pack(self, ruta: Path) -> str | None:
        """`"resource"`, `"behavior"`, o `None` si el zip no es un pack de Bedrock."""
        try:
            with zipfile.ZipFile(ruta) as zf:
                for nombre in zf.namelist():
                    if not nombre.endswith("manifest.json"):
                        continue
                    try:
                        datos = json.loads(zf.read(nombre))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
                    for modulo in datos.get("modules", []):
                        t = str(modulo.get("type", "")).lower()
                        if "resource" in t:
                            return "resource"
                        if "data" in t or "behavior" in t:
                            return "behavior"
                    # Manifest sin `modules` reconocibles: sigue siendo un pack.
                    return "resource"
        except (zipfile.BadZipFile, OSError):
            return None
        return None
