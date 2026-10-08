"""El registro de las pruebas no escribe en data/logs/."""

from pathlib import Path

import pytest

import registro


@pytest.fixture(autouse=True)
def log_temporal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Apunta el log de la IA a un archivo temporal."""
    monkeypatch.setattr(registro, "RUTA_LOG", tmp_path / "ia.log")
