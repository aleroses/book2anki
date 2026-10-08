"""Registro de llamadas al modelo. No guarda claves."""

from __future__ import annotations

import logging
from pathlib import Path

from config import DATA_DIR

RUTA_LOG = DATA_DIR / "logs" / "ia.log"


def registrar_llamada(
    proveedor: str,
    modelo: str,
    prompt: str,
    segundos: float,
    cuerpo: str,
) -> None:
    """Anota proveedor, modelo, tamaño del prompt, tiempo y la respuesta cruda."""
    _escribir(
        f"llamada proveedor={proveedor} modelo={modelo} "
        f"prompt_chars={len(prompt)} segundos={segundos:.2f}\n"
        f"{cuerpo}"
    )


def registrar_fallo(motivo: str, bruto: str) -> None:
    """Anota por qué la respuesta no pasó la validación."""
    _escribir(f"fallo motivo={motivo}\n{bruto}")


def _escribir(texto: str) -> None:
    log = logging.getLogger("book2anki.ia")
    ruta = Path(RUTA_LOG)
    if getattr(log, "_ruta", None) != ruta:
        for manejador in list(log.handlers):
            log.removeHandler(manejador)
            manejador.close()
        ruta.parent.mkdir(parents=True, exist_ok=True)
        archivo = logging.FileHandler(ruta, encoding="utf-8")
        archivo.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        log.addHandler(archivo)
        log.setLevel(logging.INFO)
        log.propagate = False
        log._ruta = ruta  # type: ignore[attr-defined]
    log.info(texto)
