"""Exportación de tarjetas a TSV."""

from __future__ import annotations

import csv
import html
import re
from pathlib import Path

from models import Card

COLUMNAS = [
    "id",
    "source",
    "chapter",
    "title",
    "subtitle",
    "lang",
    "original_text",
    "audio",
    "translation",
    "explanation",
    "notes",
    "tags",
    "code",
    "code_lang",
]

_LENGUAJE_HTML = re.compile(r"^[A-Za-z0-9_+-]+$")


def html_codigo(codigo: str, lenguaje: str) -> str:
    """Envuelve el código en HTML. Los saltos pasan a <br> para no partir el TSV."""
    if not str(codigo).strip():
        return ""
    cuerpo = html.escape(str(codigo))
    cuerpo = cuerpo.replace("\r\n", "\n").replace("\r", "\n")
    cuerpo = cuerpo.replace("\n", "<br>").replace("\t", " ")
    lang = lenguaje.strip()
    clase = f' class="language-{lang}"' if _LENGUAJE_HTML.match(lang) else ""
    return f"<pre><code{clase}>{cuerpo}</code></pre>"


def celda(valor: object) -> str:
    """Sustituye saltos de línea por <br> y tabuladores por espacios."""
    texto = "" if valor is None else str(valor)
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    return texto.replace("\n", "<br>").replace("\t", " ")


def filas_tsv(tarjetas: list[Card]) -> list[list[str]]:
    """Convierte tarjetas en filas ya escapadas, sin la cabecera."""
    filas: list[list[str]] = []
    for tarjeta in tarjetas:
        valores = {
            "id": "" if tarjeta.id is None else tarjeta.id,
            "source": tarjeta.source_name,
            "chapter": tarjeta.chapter,
            "title": tarjeta.title,
            "subtitle": tarjeta.subtitle,
            "lang": tarjeta.lang,
            "original_text": tarjeta.original_text,
            "audio": tarjeta.audio,
            "translation": tarjeta.translation,
            "explanation": tarjeta.explanation,
            "notes": tarjeta.notes,
            "tags": tarjeta.tags,
            "code": html_codigo(tarjeta.code, tarjeta.code_lang),
            "code_lang": tarjeta.code_lang,
        }
        filas.append([celda(valores[columna]) for columna in COLUMNAS])
    return filas


def exportar_tsv(tarjetas: list[Card], destino: Path) -> Path:
    """Escribe un TSV en UTF-8 y devuelve la ruta creada."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(
            archivo,
            delimiter="\t",
            quoting=csv.QUOTE_MINIMAL,
            lineterminator="\n",
        )
        escritor.writerow(COLUMNAS)
        escritor.writerows(filas_tsv(tarjetas))
    return destino
