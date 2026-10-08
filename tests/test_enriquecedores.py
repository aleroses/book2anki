"""Enriquecedores con un proveedor falso, sin red."""

from __future__ import annotations

from pathlib import Path

import pytest

import db
from enriquecedores import Explicador, Subtitulador, Traductor
from exporter import COLUMNAS, exportar_tsv
from models import Card, ErrorEnriquecimiento
from providers import ApiProvider, ErrorProveedor, proveedor_desde_config


class ProveedorFalso:
    """Devuelve respuestas preparadas o lanza la excepción guardada."""

    nombre = "falso"
    modelo = "falso-modelo"

    def __init__(self, respuestas: list[object]):
        self._respuestas = list(respuestas)
        self.llamadas = 0

    def generar(self, system: str, prompt: str) -> str:
        self.llamadas += 1
        if not self._respuestas:
            raise ErrorProveedor("sin respuestas")
        valor = self._respuestas.pop(0)
        if isinstance(valor, Exception):
            raise valor
        return str(valor)

    def probar(self) -> str:
        return "ok"


@pytest.fixture(autouse=True)
def base_temporal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Apunta la base a un directorio temporal para no tocar data/."""
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.inicializar()


def _tarjeta(**cambios: str) -> Card:
    datos: dict[str, object] = {
        "source_id": 1,
        "section_id": 1,
        "chapter": "The workshop",
        "title": "The bench",
        "subtitle": "",
        "lang": "en",
        "original_text": "The clockmaker left the workshop before dawn.",
        "id": 1,
    }
    datos.update(cambios)
    return Card(**datos)  # type: ignore[arg-type]


def test_traduce_ingles() -> None:
    proveedor = ProveedorFalso(['{"translation": "El relojero salió."}'])
    resultado = Traductor(proveedor).apply(_tarjeta())
    assert resultado.cambio is True
    assert resultado.tarjeta.translation == "El relojero salió."
    assert proveedor.llamadas == 1


def test_no_traduce_espanol_ni_vacio() -> None:
    proveedor = ProveedorFalso(['{"translation": "no debería"}'])
    espanol = Traductor(proveedor).apply(_tarjeta(lang="es"))
    vacio = Traductor(proveedor).apply(_tarjeta(lang=""))
    assert espanol.cambio is False
    assert "español" in espanol.aviso
    assert vacio.cambio is False
    assert "idioma" in vacio.aviso
    assert proveedor.llamadas == 0
    assert espanol.tarjeta.translation == ""


def test_json_invalido_luego_valido() -> None:
    proveedor = ProveedorFalso(["no es json", '{"translation": "hola"}'])
    resultado = Traductor(proveedor).apply(_tarjeta())
    assert resultado.tarjeta.translation == "hola"
    assert proveedor.llamadas == 2


def test_json_invalido_dos_veces_no_cambia_la_tarjeta() -> None:
    proveedor = ProveedorFalso(["no", "tampoco"])
    tarjeta = _tarjeta()
    with pytest.raises(ErrorEnriquecimiento):
        Traductor(proveedor).apply(tarjeta)
    assert tarjeta.translation == ""
    assert proveedor.llamadas == 2
    with db.conectar() as conexion:
        total = conexion.execute("SELECT COUNT(*) FROM ai_cache").fetchone()[0]
    assert total == 0


def test_fallo_del_servicio_no_cambia_la_tarjeta() -> None:
    proveedor = ProveedorFalso(
        [ErrorProveedor("Ollama no está en marcha en http://127.0.0.1:11434.")]
    )
    tarjeta = _tarjeta()
    with pytest.raises(ErrorProveedor):
        Traductor(proveedor).apply(tarjeta)
    assert tarjeta.translation == ""


def test_cache_y_regenerar() -> None:
    proveedor = ProveedorFalso(
        ['{"translation": "hola"}', '{"translation": "adios"}']
    )
    traductor = Traductor(proveedor)
    tarjeta = _tarjeta()
    primera = traductor.apply(tarjeta)
    segunda = traductor.apply(tarjeta)
    assert primera.tarjeta.translation == "hola"
    assert segunda.tarjeta.translation == "hola"
    assert proveedor.llamadas == 1
    tercera = traductor.apply(tarjeta, regenerar=True)
    assert tercera.tarjeta.translation == "adios"
    assert proveedor.llamadas == 2


def test_explicacion() -> None:
    proveedor = ProveedorFalso(['{"explanation": "Sale antes del amanecer."}'])
    resultado = Explicador(proveedor).apply(_tarjeta(lang="es"))
    assert resultado.tarjeta.explanation == "Sale antes del amanecer."


def test_subtitulo_solo_si_esta_vacio() -> None:
    proveedor = ProveedorFalso(['{"subtitle": "El amanecer"}'])
    ocupado = Subtitulador(proveedor).apply(_tarjeta(subtitle="Ya tiene"))
    assert ocupado.cambio is False
    assert ocupado.tarjeta.subtitle == "Ya tiene"
    assert proveedor.llamadas == 0
    libre = Subtitulador(proveedor).apply(_tarjeta(subtitle=""))
    assert libre.tarjeta.subtitle == "El amanecer"
    assert proveedor.llamadas == 1


def test_tsv_incluye_traduccion_y_explicacion(tmp_path: Path) -> None:
    tarjeta = _tarjeta(translation="hola", explanation="breve")
    tarjeta.source_name = "nota.md"
    destino = exportar_tsv([tarjeta], tmp_path / "tarjetas.tsv")
    lineas = destino.read_text(encoding="utf-8").splitlines()
    cabecera = lineas[0].split("\t")
    assert cabecera == COLUMNAS
    assert "hola" in lineas[1]
    assert "breve" in lineas[1]


def test_api_sin_clave_no_llama_a_la_red() -> None:
    proveedor = ApiProvider(modelo="modelo", url="https://ejemplo.invalid/v1", clave="")
    with pytest.raises(ErrorProveedor, match="BOOK2ANKI_API_KEY"):
        proveedor.generar("sistema", "prompt")


def test_proveedor_desconocido() -> None:
    with pytest.raises(ErrorProveedor, match="ollama o api"):
        proveedor_desde_config("otro", "modelo")
