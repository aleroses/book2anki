"""Modelos de datos y el protocolo de los enriquecedores."""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class Source:
    """Archivo importado, suelto o desde una carpeta de Obsidian."""

    id: int
    name: str
    path: str
    kind: str
    imported_at: str


@dataclass
class Section:
    """Trozo de un archivo delimitado por encabezados Markdown."""

    heading: str
    level: int
    position: int
    chapter: str
    title: str
    subtitle: str
    body: str
    id: int | None = None
    source_id: int | None = None


@dataclass
class Card:
    """Tarjeta elegida a mano.

    audio queda vacío hasta una etapa posterior.
    """

    source_id: int
    section_id: int
    chapter: str
    title: str
    subtitle: str
    lang: str
    original_text: str
    audio: str = ""
    translation: str = ""
    explanation: str = ""
    code: str = ""
    code_lang: str = ""
    notes: str = ""
    tags: str = ""
    id: int | None = None
    created_at: str = ""
    source_name: str = ""


@dataclass
class ResultadoEnriquecimiento:
    """Qué hizo un enriquecedor con una tarjeta."""

    tarjeta: Card
    cambio: bool
    aviso: str


class ErrorEnriquecimiento(Exception):
    """El JSON no valió. La tarjeta no se modifica."""


class Enriquecedor(Protocol):
    """Traducción, explicación o subtítulo. El audio queda para después."""

    name: str
    campos: tuple[str, ...]

    def apply(
        self, card: Card, *, regenerar: bool = False
    ) -> ResultadoEnriquecimiento:
        """Devuelve la tarjeta y si cambió algún campo."""
        ...


# usar_proveedor la rellena con el modelo elegido en la sesión.
ENRIQUECEDORES: list[Enriquecedor] = []
