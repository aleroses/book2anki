"""Persistencia SQLite de fuentes, secciones y tarjetas."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from config import DATA_DIR, DB_PATH
from models import Card, Section, Source


def conectar() -> sqlite3.Connection:
    """Abre la base y activa las claves foráneas."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conexion = sqlite3.connect(DB_PATH)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion


def inicializar() -> None:
    """Crea las tablas si todavía no existen."""
    with conectar() as conexion:
        conexion.executescript(
            """
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                path TEXT NOT NULL,
                kind TEXT NOT NULL,
                imported_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL
                    REFERENCES sources(id) ON DELETE CASCADE,
                heading TEXT NOT NULL,
                level INTEGER NOT NULL,
                position INTEGER NOT NULL,
                chapter TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                subtitle TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL
                    REFERENCES sources(id) ON DELETE CASCADE,
                section_id INTEGER NOT NULL
                    REFERENCES sections(id) ON DELETE CASCADE,
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
            );

            CREATE INDEX IF NOT EXISTS idx_sections_source
                ON sections(source_id, position);
            CREATE INDEX IF NOT EXISTS idx_cards_section
                ON cards(section_id);

            CREATE TABLE IF NOT EXISTS ai_cache (
                clave TEXT PRIMARY KEY,
                valor TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        _migrar(conexion)


def guardar_fuente(
    name: str, path: str, kind: str, secciones: list[Section]
) -> int:
    """Inserta una fuente y sus secciones. Devuelve el id de la fuente."""
    with conectar() as conexion:
        cursor = conexion.execute(
            """
            INSERT INTO sources (name, path, kind, imported_at)
            VALUES (?, ?, ?, ?)
            """,
            (name, path, kind, _ahora()),
        )
        source_id = _id_insertado(cursor)
        conexion.executemany(
            """
            INSERT INTO sections (
                source_id, heading, level, position,
                chapter, title, subtitle, body
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    source_id,
                    seccion.heading,
                    seccion.level,
                    seccion.position,
                    seccion.chapter,
                    seccion.title,
                    seccion.subtitle,
                    seccion.body,
                )
                for seccion in secciones
            ],
        )
    return source_id


def listar_fuentes() -> list[Source]:
    """Devuelve las fuentes de la más reciente a la más antigua."""
    with conectar() as conexion:
        filas = conexion.execute(
            """
            SELECT id, name, path, kind, imported_at
            FROM sources
            ORDER BY id DESC
            """
        ).fetchall()
    return [
        Source(
            id=fila["id"],
            name=fila["name"],
            path=fila["path"],
            kind=fila["kind"],
            imported_at=fila["imported_at"],
        )
        for fila in filas
    ]


def listar_secciones(source_id: int) -> list[Section]:
    """Devuelve las secciones de una fuente, en orden de lectura."""
    with conectar() as conexion:
        filas = conexion.execute(
            """
            SELECT id, source_id, heading, level, position,
                   chapter, title, subtitle, body
            FROM sections
            WHERE source_id = ?
            ORDER BY position
            """,
            (source_id,),
        ).fetchall()
    return [_fila_a_seccion(fila) for fila in filas]


def obtener_seccion(section_id: int) -> Section | None:
    """Devuelve una sección, o None si no existe."""
    with conectar() as conexion:
        fila = conexion.execute(
            """
            SELECT id, source_id, heading, level, position,
                   chapter, title, subtitle, body
            FROM sections
            WHERE id = ?
            """,
            (section_id,),
        ).fetchone()
    if fila is None:
        return None
    return _fila_a_seccion(fila)


def crear_tarjeta(tarjeta: Card) -> int:
    """Guarda una tarjeta nueva y devuelve su id."""
    with conectar() as conexion:
        cursor = conexion.execute(
            """
            INSERT INTO cards (
                source_id, section_id, chapter, title, subtitle, lang,
                original_text, audio, translation, explanation,
                code, code_lang, notes, tags, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tarjeta.source_id,
                tarjeta.section_id,
                tarjeta.chapter,
                tarjeta.title,
                tarjeta.subtitle,
                tarjeta.lang,
                tarjeta.original_text,
                tarjeta.audio,
                tarjeta.translation,
                tarjeta.explanation,
                tarjeta.code,
                tarjeta.code_lang,
                tarjeta.notes,
                tarjeta.tags,
                _ahora(),
            ),
        )
        return _id_insertado(cursor)


def listar_tarjetas() -> list[Card]:
    """Devuelve todas las tarjetas con el nombre de su fuente."""
    with conectar() as conexion:
        filas = conexion.execute(
            """
            SELECT c.id, c.source_id, c.section_id, c.chapter, c.title,
                   c.subtitle, c.lang, c.original_text, c.audio,
                   c.translation, c.explanation, c.code, c.code_lang,
                   c.notes, c.tags, c.created_at, s.name AS source_name
            FROM cards AS c
            JOIN sources AS s ON s.id = c.source_id
            ORDER BY c.id
            """
        ).fetchall()
    return [_fila_a_tarjeta(fila) for fila in filas]


def textos_de_seccion(section_id: int) -> set[str]:
    """Textos ya convertidos en tarjeta dentro de una sección."""
    with conectar() as conexion:
        filas = conexion.execute(
            "SELECT original_text FROM cards WHERE section_id = ?",
            (section_id,),
        ).fetchall()
    return {str(fila["original_text"]).strip() for fila in filas}


def guardar_enriquecimiento(
    card_id: int,
    translation: str,
    explanation: str,
    subtitle: str | None = None,
) -> None:
    """Guarda translation y explanation, y subtitle solo si se indica."""
    with conectar() as conexion:
        if subtitle is None:
            conexion.execute(
                """
                UPDATE cards
                SET translation = ?, explanation = ?
                WHERE id = ?
                """,
                (translation, explanation, card_id),
            )
            return
        conexion.execute(
            """
            UPDATE cards
            SET translation = ?, explanation = ?, subtitle = ?
            WHERE id = ?
            """,
            (translation, explanation, subtitle, card_id),
        )


def leer_cache(clave: str) -> str | None:
    """Devuelve la respuesta guardada para esa clave, o None."""
    with conectar() as conexion:
        fila = conexion.execute(
            "SELECT valor FROM ai_cache WHERE clave = ?",
            (clave,),
        ).fetchone()
    if fila is None:
        return None
    return str(fila["valor"])


def guardar_cache(clave: str, valor: str) -> None:
    """Guarda o sustituye la respuesta de una clave."""
    with conectar() as conexion:
        conexion.execute(
            """
            INSERT INTO ai_cache (clave, valor, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(clave) DO UPDATE SET
                valor = excluded.valor,
                created_at = excluded.created_at
            """,
            (clave, valor, _ahora()),
        )


def guardar_resumen(section_id: int, summary: str) -> None:
    """Guarda o sustituye el resumen editado de una sección."""
    with conectar() as conexion:
        conexion.execute(
            """
            INSERT INTO section_summaries (section_id, summary, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(section_id) DO UPDATE SET
                summary = excluded.summary,
                updated_at = excluded.updated_at
            """,
            (section_id, summary, _ahora()),
        )


def leer_resumen(section_id: int) -> str | None:
    """Devuelve el resumen guardado, o None si esa sección no tiene."""
    with conectar() as conexion:
        fila = conexion.execute(
            "SELECT summary FROM section_summaries WHERE section_id = ?",
            (section_id,),
        ).fetchone()
    if fila is None:
        return None
    return str(fila["summary"])


def actualizar_tarjeta(
    card_id: int,
    title: str,
    subtitle: str,
    notes: str,
    tags: str,
    original_text: str,
    lang: str,
    code: str,
    code_lang: str,
) -> None:
    """Actualiza los campos editables de una tarjeta."""
    with conectar() as conexion:
        conexion.execute(
            """
            UPDATE cards
            SET title = ?, subtitle = ?, notes = ?, tags = ?,
                original_text = ?, lang = ?, code = ?, code_lang = ?
            WHERE id = ?
            """,
            (
                title,
                subtitle,
                notes,
                tags,
                original_text,
                lang,
                code,
                code_lang,
                card_id,
            ),
        )


def borrar_tarjetas(ids: list[int]) -> None:
    """Elimina las tarjetas indicadas."""
    if not ids:
        return
    with conectar() as conexion:
        conexion.executemany(
            "DELETE FROM cards WHERE id = ?",
            [(card_id,) for card_id in ids],
        )


def contar_tarjetas_de(source_ids: list[int]) -> int:
    """Cuenta las tarjetas de las fuentes indicadas."""
    if not source_ids:
        return 0
    marcas = ", ".join("?" for _ in source_ids)
    with conectar() as conexion:
        fila = conexion.execute(
            f"SELECT COUNT(*) AS total FROM cards WHERE source_id IN ({marcas})",
            source_ids,
        ).fetchone()
    return int(fila["total"])


def fuentes_con_rutas(paths: list[str]) -> list[Source]:
    """Devuelve las fuentes cuyo path absoluto está en la lista."""
    if not paths:
        return []
    marcas = ", ".join("?" for _ in paths)
    with conectar() as conexion:
        filas = conexion.execute(
            f"""
            SELECT id, name, path, kind, imported_at
            FROM sources
            WHERE path IN ({marcas})
            ORDER BY id DESC
            """,
            paths,
        ).fetchall()
    return [
        Source(
            id=fila["id"],
            name=fila["name"],
            path=fila["path"],
            kind=fila["kind"],
            imported_at=fila["imported_at"],
        )
        for fila in filas
    ]


def borrar_todas_las_tarjetas() -> int:
    """Borra todas las tarjetas y deja fuentes y secciones. Devuelve cuántas eran."""
    with conectar() as conexion:
        total = int(conexion.execute("SELECT COUNT(*) AS total FROM cards").fetchone()["total"])
        conexion.execute("DELETE FROM cards")
    return total


def borrar_fuente(source_id: int) -> tuple[int, int]:
    """Borra una fuente. Las secciones y tarjetas caen por ON DELETE CASCADE.

    Devuelve (secciones, tarjetas) que tenía. Falla si el cascade no las elimina.
    """
    with conectar() as conexion:
        if conexion.execute(
            "SELECT 1 FROM sources WHERE id = ?", (source_id,)
        ).fetchone() is None:
            raise RuntimeError("No existe la fuente.")
        secciones = int(
            conexion.execute(
                "SELECT COUNT(*) AS total FROM sections WHERE source_id = ?",
                (source_id,),
            ).fetchone()["total"]
        )
        tarjetas = int(
            conexion.execute(
                "SELECT COUNT(*) AS total FROM cards WHERE source_id = ?",
                (source_id,),
            ).fetchone()["total"]
        )
        conexion.execute("DELETE FROM sources WHERE id = ?", (source_id,))
        huerfanas_secciones = int(
            conexion.execute(
                "SELECT COUNT(*) AS total FROM sections WHERE source_id = ?",
                (source_id,),
            ).fetchone()["total"]
        )
        huerfanas_tarjetas = int(
            conexion.execute(
                "SELECT COUNT(*) AS total FROM cards WHERE source_id = ?",
                (source_id,),
            ).fetchone()["total"]
        )
        if huerfanas_secciones or huerfanas_tarjetas:
            raise RuntimeError(
                "El borrado en cascada no eliminó las secciones o las tarjetas."
            )
    return secciones, tarjetas


def restablecer_todo() -> tuple[int, int, int]:
    """Vacía fuentes, secciones y tarjetas, y reinicia los autoincrementales.

    Devuelve (fuentes, secciones, tarjetas) que había.
    """
    with conectar() as conexion:
        fuentes = int(
            conexion.execute("SELECT COUNT(*) AS total FROM sources").fetchone()["total"]
        )
        secciones = int(
            conexion.execute("SELECT COUNT(*) AS total FROM sections").fetchone()["total"]
        )
        tarjetas = int(
            conexion.execute("SELECT COUNT(*) AS total FROM cards").fetchone()["total"]
        )
        conexion.execute("DELETE FROM section_summaries")
        conexion.execute("DELETE FROM cards")
        conexion.execute("DELETE FROM sections")
        conexion.execute("DELETE FROM sources")
        secuencia = conexion.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'sqlite_sequence'
            """
        ).fetchone()
        if secuencia is not None:
            conexion.execute(
                """
                DELETE FROM sqlite_sequence
                WHERE name IN ('sources', 'sections', 'cards')
                """
            )
    return fuentes, secciones, tarjetas


def _migrar(conexion: sqlite3.Connection) -> None:
    """Añade code, code_lang y section_summaries sin borrar filas."""
    columnas = {
        str(fila["name"]) for fila in conexion.execute("PRAGMA table_info(cards)")
    }
    if "code" not in columnas:
        conexion.execute(
            "ALTER TABLE cards ADD COLUMN code TEXT NOT NULL DEFAULT ''"
        )
    if "code_lang" not in columnas:
        conexion.execute(
            "ALTER TABLE cards ADD COLUMN code_lang TEXT NOT NULL DEFAULT ''"
        )
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS section_summaries (
            section_id INTEGER PRIMARY KEY
                REFERENCES sections(id) ON DELETE CASCADE,
            summary TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


def _ahora() -> str:
    """Marca de tiempo UTC en ISO 8601, sin microsegundos."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _id_insertado(cursor: sqlite3.Cursor) -> int:
    """Lee el id de la última fila insertada."""
    if cursor.lastrowid is None:
        raise RuntimeError("SQLite no devolvió el id insertado.")
    return int(cursor.lastrowid)


def _fila_a_seccion(fila: sqlite3.Row) -> Section:
    return Section(
        id=fila["id"],
        source_id=fila["source_id"],
        heading=fila["heading"],
        level=fila["level"],
        position=fila["position"],
        chapter=fila["chapter"],
        title=fila["title"],
        subtitle=fila["subtitle"],
        body=fila["body"],
    )


def _fila_a_tarjeta(fila: sqlite3.Row) -> Card:
    claves = fila.keys()
    return Card(
        id=fila["id"],
        source_id=fila["source_id"],
        section_id=fila["section_id"],
        chapter=fila["chapter"],
        title=fila["title"],
        subtitle=fila["subtitle"],
        lang=fila["lang"],
        original_text=fila["original_text"],
        audio=fila["audio"],
        translation=fila["translation"],
        explanation=fila["explanation"],
        code=fila["code"] if "code" in claves else "",
        code_lang=fila["code_lang"] if "code_lang" in claves else "",
        notes=fila["notes"],
        tags=fila["tags"],
        created_at=fila["created_at"],
        source_name=fila["source_name"] if "source_name" in claves else "",
    )
