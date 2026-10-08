"""Lectura de archivos y carpetas, y partición en secciones y párrafos."""

from __future__ import annotations

import os
import re
from pathlib import Path

from langdetect import DetectorFactory, LangDetectException, detect_langs

from config import SIN_TITULO
from db import guardar_fuente
from models import Section

DetectorFactory.seed = 0

_ENCABEZADO = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")
_CIERRE_ATX = re.compile(r"\s+#+\s*$")
_ABRE_VALLA = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")
_CIERRA_VALLA = re.compile(r"^( {0,3})(`{3,}|~{3,})[ \t]*$")
_LENGUAJE = re.compile(r"[A-Za-z0-9_+-]+")
_EXTENSIONES = {".md", ".txt"}
_MIN_CARACTERES = 20
_MIN_PROBABILIDAD = 0.8


class ErrorImportacion(Exception):
    """Fallo de importación que se puede mostrar en la interfaz."""


def detectar_idioma(texto: str) -> str:
    """Devuelve el código de idioma, o cadena vacía si no es fiable."""
    limpio = " ".join(texto.split())
    if len(limpio) < _MIN_CARACTERES:
        return ""
    try:
        candidatos = detect_langs(limpio)
    except LangDetectException:
        return ""
    if not candidatos or candidatos[0].prob < _MIN_PROBABILIDAD:
        return ""
    return candidatos[0].lang


def leer_texto(ruta: Path) -> str:
    """Lee un archivo en UTF-8 y, si la codificación no cuadra, en Latin-1."""
    if not ruta.is_file():
        raise ErrorImportacion(f"No se encontró el archivo: {ruta}")
    try:
        return ruta.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        try:
            return ruta.read_text(encoding="latin-1")
        except OSError as exc:
            raise ErrorImportacion(f"No se pudo leer {ruta.name}: {exc}") from exc
    except OSError as exc:
        raise ErrorImportacion(f"No se pudo leer {ruta.name}: {exc}") from exc


def partir_parrafos(cuerpo: str) -> list[str]:
    """Divide el cuerpo en párrafos. Una valla de código es un solo párrafo."""
    parrafos: list[str] = []
    actual: list[str] = []
    valla: tuple[str, int] | None = None

    def cerrar() -> None:
        nonlocal actual
        texto = "\n".join(actual).strip()
        actual = []
        if texto:
            parrafos.append(texto)

    for linea in cuerpo.splitlines():
        if valla is not None:
            actual.append(linea)
            if _cierra_valla(linea, valla[0], valla[1]):
                valla = None
                cerrar()
            continue
        abierta = _abrir_valla(linea)
        if abierta is not None:
            cerrar()
            valla = (abierta[0], abierta[1])
            actual.append(linea)
            continue
        if not linea.strip():
            cerrar()
            continue
        actual.append(linea)
    cerrar()
    return parrafos


def codigo_de_parrafo(parrafo: str) -> tuple[str, str] | None:
    """Si el párrafo es una valla cerrada, devuelve (lenguaje, interior)."""
    lineas = parrafo.splitlines()
    if len(lineas) < 2:
        return None
    abierta = _abrir_valla(lineas[0])
    if abierta is None or not _cierra_valla(lineas[-1], abierta[0], abierta[1]):
        return None
    return abierta[2], "\n".join(lineas[1:-1])


def texto_sin_vallas(texto: str) -> str:
    """Quita las vallas de código para detectar el idioma de la prosa."""
    lineas: list[str] = []
    valla: tuple[str, int] | None = None
    for linea in texto.splitlines():
        if valla is not None:
            if _cierra_valla(linea, valla[0], valla[1]):
                valla = None
            continue
        abierta = _abrir_valla(linea)
        if abierta is not None:
            valla = (abierta[0], abierta[1])
            continue
        lineas.append(linea)
    return "\n".join(lineas)


def partir_secciones(texto: str) -> list[Section]:
    """Parte un texto en secciones según los encabezados Markdown."""
    pila: list[tuple[int, str]] = []
    secciones: list[Section] = []
    cuerpo: list[str] = []
    actual: tuple[str, int, str, str, str] | None = None
    posicion = 0
    valla: tuple[str, int] | None = None

    def cerrar() -> None:
        nonlocal posicion, cuerpo
        bloque = "\n".join(cuerpo).strip()
        cuerpo = []
        if actual is None:
            if not bloque:
                return
            secciones.append(
                Section(
                    heading=SIN_TITULO,
                    level=0,
                    position=posicion,
                    chapter="",
                    title="",
                    subtitle="",
                    body=bloque,
                )
            )
            posicion += 1
            return
        if not bloque:
            return
        heading, level, chapter, title, subtitle = actual
        secciones.append(
            Section(
                heading=heading,
                level=level,
                position=posicion,
                chapter=chapter,
                title=title,
                subtitle=subtitle,
                body=bloque,
            )
        )
        posicion += 1

    for linea in texto.splitlines():
        if valla is not None:
            cuerpo.append(linea)
            if _cierra_valla(linea, valla[0], valla[1]):
                valla = None
            continue
        abierta = _abrir_valla(linea)
        if abierta is not None:
            cuerpo.append(linea)
            valla = (abierta[0], abierta[1])
            continue
        coincidencia = _ENCABEZADO.match(linea)
        if coincidencia is None:
            cuerpo.append(linea)
            continue
        cerrar()
        nivel = len(coincidencia.group(1))
        heading = _CIERRE_ATX.sub("", coincidencia.group(2)).strip()
        while pila and pila[-1][0] >= nivel:
            pila.pop()
        pila.append((nivel, heading))
        chapter, title, subtitle = _contexto(pila)
        actual = (heading, nivel, chapter, title, subtitle)

    cerrar()
    if secciones:
        return secciones
    return [
        Section(
            heading=SIN_TITULO,
            level=0,
            position=0,
            chapter="",
            title="",
            subtitle="",
            body=texto.strip(),
        )
    ]


def planificar_importacion(ruta: str) -> list[tuple[Path, str, str]]:
    """Resuelve un archivo o carpeta sin escribir en la base.

    Cada entrada es (ruta absoluta, kind, nombre).
    """
    texto = ruta.strip()
    if not texto:
        raise ErrorImportacion("Indica la ruta de un archivo o de una carpeta.")
    path = Path(texto).expanduser()
    try:
        path = path.resolve()
    except OSError as exc:
        raise ErrorImportacion(f"Ruta no válida: {exc}") from exc
    if not path.exists():
        raise ErrorImportacion(f"No existe la ruta: {path}")
    if path.is_file():
        _validar_archivo(path, "archivo")
        return [(path, "archivo", path.name)]
    if path.is_dir():
        archivos = listar_markdown(path)
        if not archivos:
            raise ErrorImportacion("La carpeta no contiene archivos .md.")
        return [
            (archivo, "obsidian", archivo.relative_to(path).as_posix())
            for archivo in archivos
        ]
    raise ErrorImportacion("La ruta no es un archivo ni una carpeta.")


def importar_plan(entradas: list[tuple[Path, str, str]]) -> list[int]:
    """Inserta entradas ya resueltas y devuelve los ids de fuente."""
    return [
        _importar_archivo(path, kind, nombre) for path, kind, nombre in entradas
    ]


def importar_ruta(ruta: str) -> list[int]:
    """Importa un archivo o cada .md de una carpeta. Devuelve ids de fuente."""
    return importar_plan(planificar_importacion(ruta))


def listar_markdown(carpeta: Path) -> list[Path]:
    """Recorre una carpeta y devuelve los .md, sin entrar en ocultos."""
    encontrados: list[Path] = []
    for directorio, subdirs, archivos in os.walk(carpeta):
        subdirs[:] = sorted(
            nombre for nombre in subdirs if not nombre.startswith(".")
        )
        for nombre in sorted(archivos):
            if nombre.startswith(".") or not nombre.lower().endswith(".md"):
                continue
            encontrados.append(Path(directorio) / nombre)
    return encontrados


def _validar_archivo(path: Path, kind: str) -> None:
    if path.name.startswith("."):
        raise ErrorImportacion("No se importan archivos ocultos.")
    if kind == "archivo" and path.suffix.lower() not in _EXTENSIONES:
        raise ErrorImportacion("El archivo debe tener extensión .md o .txt.")


def _importar_archivo(path: Path, kind: str, nombre: str) -> int:
    _validar_archivo(path, kind)
    texto = leer_texto(path)
    return guardar_fuente(nombre, str(path), kind, partir_secciones(texto))


def _abrir_valla(linea: str) -> tuple[str, int, str] | None:
    """Si la línea abre una valla, devuelve (marca, largo, lenguaje)."""
    coincidencia = _ABRE_VALLA.match(linea)
    if coincidencia is None:
        return None
    valla = coincidencia.group(2)
    info = coincidencia.group(3)
    if valla[0] == "`" and "`" in info:
        return None
    return valla[0], len(valla), _lenguaje(info)


def _cierra_valla(linea: str, marca: str, largo: int) -> bool:
    """Dice si la línea cierra la valla abierta."""
    coincidencia = _CIERRA_VALLA.match(linea)
    if coincidencia is None:
        return False
    valla = coincidencia.group(2)
    return valla[0] == marca and len(valla) >= largo


def _lenguaje(info: str) -> str:
    token = info.strip().split(" ", 1)[0] if info.strip() else ""
    if _LENGUAJE.fullmatch(token):
        return token
    return ""


def _contexto(pila: list[tuple[int, str]]) -> tuple[str, str, str]:
    """Saca chapter, title y subtitle de la pila de encabezados."""
    chapter = ""
    title = ""
    subtitle = ""
    for nivel, texto in pila:
        if nivel == 1:
            chapter = texto
        elif nivel == 2:
            title = texto
        elif nivel == 3:
            subtitle = texto
    return chapter, title, subtitle
