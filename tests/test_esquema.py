"""Migración y TSV de código. La base es temporal."""

from __future__ import annotations

import csv
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

import db
from exporter import COLUMNAS, exportar_tsv
from models import Card, Section


@pytest.fixture
def base_temporal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Apunta db.py a un archivo que no es data/book2anki.db."""
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    destino = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", destino)
    return destino


def test_migracion_conserva_la_fila_vieja(base_temporal: Path) -> None:
    conexion = sqlite3.connect(base_temporal)
    conexion.execute(
        """
        CREATE TABLE cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            section_id INTEGER NOT NULL,
            chapter TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            subtitle TEXT NOT NULL DEFAULT '',
            lang TEXT NOT NULL DEFAULT '',
            original_text TEXT NOT NULL,
            audio TEXT NOT NULL DEFAULT '',
            translation TEXT NOT NULL DEFAULT '',
            explanation TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            tags TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )
        """
    )
    conexion.execute(
        """
        INSERT INTO cards (source_id, section_id, original_text, created_at)
        VALUES (1, 1, 'texto viejo', '2020-01-01T00:00:00+00:00')
        """
    )
    conexion.commit()
    conexion.close()

    db.inicializar()
    conexion = sqlite3.connect(base_temporal)
    conexion.row_factory = sqlite3.Row
    columnas = {str(fila["name"]) for fila in conexion.execute("PRAGMA table_info(cards)")}
    assert {"code", "code_lang"} <= columnas
    fila = conexion.execute(
        "SELECT original_text, code, code_lang FROM cards"
    ).fetchone()
    assert fila["original_text"] == "texto viejo"
    assert fila["code"] == ""
    assert fila["code_lang"] == ""
    tablas = {
        str(fila[0])
        for fila in conexion.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert "section_summaries" in tablas
    conexion.close()


def test_resumen_y_restablecer(base_temporal: Path) -> None:
    db.inicializar()
    fuente_id = db.guardar_fuente(
        "nota.md",
        "/tmp/nota.md",
        "archivo",
        [
            Section(
                heading="Uno",
                level=1,
                position=0,
                chapter="Uno",
                title="",
                subtitle="",
                body="cuerpo",
            )
        ],
    )
    seccion_id = db.listar_secciones(fuente_id)[0].id
    assert seccion_id is not None
    db.guardar_resumen(seccion_id, "Resumen guardado.")
    assert db.leer_resumen(seccion_id) == "Resumen guardado."
    db.restablecer_todo()
    assert db.leer_resumen(seccion_id) is None


def test_tsv_codigo_en_html_es_una_sola_fila(tmp_path: Path) -> None:
    tarjeta = Card(
        source_id=1,
        section_id=1,
        chapter="",
        title="Terminal",
        subtitle="",
        lang="es",
        original_text="texto",
        code="if a < b:\n    echo",
        code_lang="bash",
        source_name="nota.md",
    )
    destino = exportar_tsv([tarjeta], tmp_path / "tarjetas.tsv")
    with destino.open(encoding="utf-8", newline="") as archivo:
        filas = list(csv.reader(archivo, delimiter="\t"))
    assert filas[0] == COLUMNAS
    assert len(filas) == 2
    celda = filas[1][COLUMNAS.index("code")]
    assert celda == '<pre><code class="language-bash">if a &lt; b:<br>    echo</code></pre>'
    assert "\n" not in celda
    assert filas[1][COLUMNAS.index("code_lang")] == "bash"


def test_book2anki_db_cambia_la_ruta(tmp_path: Path) -> None:
    destino = tmp_path / "copia.db"
    entorno = os.environ.copy()
    entorno["BOOK2ANKI_DB"] = str(destino)
    resultado = subprocess.run(
        [sys.executable, "-c", "import config; print(config.DB_PATH)"],
        cwd=Path(__file__).resolve().parents[1],
        env=entorno,
        check=True,
        capture_output=True,
        text=True,
    )
    assert resultado.stdout.strip() == str(destino)
