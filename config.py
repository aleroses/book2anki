"""Rutas y constantes de la aplicación."""

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DATA_DIR = RAIZ / "data"
_DB_ELEGIDA = os.environ.get("BOOK2ANKI_DB", "").strip()
DB_PATH = Path(_DB_ELEGIDA) if _DB_ELEGIDA else DATA_DIR / "book2anki.db"
EXPORT_DIR = DATA_DIR / "exportaciones"
SIN_TITULO = "(sin título)"
RAM_GB = int(os.environ.get("BOOK2ANKI_RAM_GB", "8"))

PROVEEDOR = os.environ.get("BOOK2ANKI_PROVEEDOR", "ollama")
OLLAMA_URL = os.environ.get("BOOK2ANKI_OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODELO = os.environ.get("BOOK2ANKI_OLLAMA_MODELO", "qwen2.5:3b")
API_URL = os.environ.get("BOOK2ANKI_API_URL", "")
API_MODELO = os.environ.get("BOOK2ANKI_API_MODEL", "")
API_KEY = os.environ.get("BOOK2ANKI_API_KEY", "")
LLM_TIMEOUT = float(os.environ.get("BOOK2ANKI_LLM_TIMEOUT", "120"))
