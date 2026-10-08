"""Resumen de sección con un proveedor falso, sin red y con base temporal."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import db
import providers
from enriquecedores import _cargar_json, resumir_seccion, sugerir_tarjetas
from models import ErrorEnriquecimiento
from providers import ErrorProveedor, OllamaProvider, proveedor_desde_config


class ProveedorFalso:
    """Devuelve respuestas preparadas, en orden."""

    nombre = "falso"
    modelo = "falso-modelo"

    def __init__(self, respuestas: list[object]):
        self._respuestas = list(respuestas)
        self.llamadas = 0
        self.predicts: list[int] = []

    def generar(
        self, system: str, prompt: str, *, num_predict: int = 768
    ) -> str:
        self.llamadas += 1
        self.predicts.append(num_predict)
        if not self._respuestas:
            raise ErrorProveedor("sin respuestas")
        valor = self._respuestas.pop(0)
        if isinstance(valor, Exception):
            raise valor
        return str(valor)


class SegunPrompt:
    """Resume trozos, arma el resumen y luego una tarjeta por llamada."""

    nombre = "falso"
    modelo = "falso-modelo"

    def __init__(self) -> None:
        self.llamadas = 0
        self.resumenes = 0
        self.tarjetas = 0

    def generar(
        self, system: str, prompt: str, *, num_predict: int = 768
    ) -> str:
        self.llamadas += 1
        if "title, subtitle, original_text, explanation" in prompt:
            self.tarjetas += 1
            numero = "1"
            marca = __import__("re").search(r"tarjeta (\d+) de", prompt)
            if marca:
                numero = marca.group(1)
            return json.dumps(
                {
                    "title": f"Tarjeta {numero}",
                    "subtitle": "",
                    "original_text": "echo hola",
                    "explanation": "Explica el comando en dos frases.",
                },
                ensure_ascii=False,
            )
        self.resumenes += 1
        if "trozo" in prompt:
            return '{"resumen": "Primera frase del trozo. Segunda frase."}'
        return (
            '{"resumen": "Resumen en tres frases. '
            'Cubre la sección. Sirve para estudiar."}'
        )


@pytest.fixture(autouse=True)
def base_temporal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Apunta la base a un directorio temporal para no tocar data/."""
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.inicializar()


def _resumen() -> str:
    return (
        '{"resumen": "Resumen en tres frases. '
        'Cubre la sección. Sirve para estudiar."}'
    )


def _tarjeta(
    indice: int = 1,
    *,
    original: str = "Texto de la sección.",
    translation: str | None = None,
    campos: dict[str, str] | None = None,
) -> str:
    datos: dict[str, str] = {
        "title": f"Tarjeta {indice}",
        "subtitle": "",
        "original_text": original,
        "explanation": "Explica el párrafo en dos frases.",
    }
    if translation is not None:
        datos["translation"] = translation
    if campos is not None:
        datos = campos
    return json.dumps(datos, ensure_ascii=False)


def test_sugerir_tarjetas_por_volumen() -> None:
    assert sugerir_tarjetas(" ".join(["palabra"] * 149)) == 1
    assert sugerir_tarjetas(" ".join(["palabra"] * 150)) == 2
    assert sugerir_tarjetas(" ".join(["palabra"] * 400)) == 2
    assert sugerir_tarjetas(" ".join(["palabra"] * 401)) == 3


@pytest.mark.parametrize("cantidad", [1, 2, 3])
def test_varias_llamadas_una_por_tarjeta(cantidad: int) -> None:
    respuestas = [_resumen()] + [_tarjeta(indice + 1) for indice in range(cantidad)]
    proveedor = ProveedorFalso(respuestas)
    resultado = resumir_seccion(
        proveedor, "Texto de la sección.", n=cantidad, lang="es"
    )
    assert len(resultado.tarjetas) == cantidad
    assert resultado.resumen.startswith("Resumen")
    assert resultado.avisos == []
    assert proveedor.llamadas == 1 + cantidad
    assert proveedor.predicts[0] == 512
    assert proveedor.predicts[1:] == [768] * cantidad


def test_codigo_de_la_valla_si_el_texto_lo_contiene() -> None:
    texto = "La terminal lista archivos.\n\n```bash\nls -l\n```"
    proveedor = ProveedorFalso([_resumen(), _tarjeta(original="Antes\nls -l\nDespués")])
    resultado = resumir_seccion(proveedor, texto, n=1, lang="es")
    assert resultado.tarjetas[0].code == "ls -l"
    assert resultado.tarjetas[0].code_lang == "bash"
    assert resultado.avisos == []


def test_codigo_que_nadie_cita_deja_aviso() -> None:
    texto = "La terminal lista archivos.\n\n```bash\nls -l\n```"
    proveedor = ProveedorFalso([_resumen(), _tarjeta(original="Solo prosa.")])
    resultado = resumir_seccion(proveedor, texto, n=1, lang="es")
    assert resultado.tarjetas[0].code == ""
    assert resultado.tarjetas[0].code_lang == ""
    assert any("no entró" in aviso for aviso in resultado.avisos)


def test_valla_markdown_y_texto_alrededor() -> None:
    envuelto = "```json\n" + _resumen() + "\n```"
    alrededor = "Toma esto: " + _tarjeta() + " Gracias."
    proveedor = ProveedorFalso([envuelto, alrededor])
    resultado = resumir_seccion(proveedor, "Texto de la sección.", n=1, lang="es")
    assert resultado.tarjetas[0].title == "Tarjeta 1"
    assert proveedor.llamadas == 2


def test_coma_final_se_repara() -> None:
    resumen = '{"resumen": "Resumen en tres frases. Cubre la sección.",}'
    tarjeta = _tarjeta().rstrip("}") + ",}"
    proveedor = ProveedorFalso([resumen, tarjeta])
    resultado = resumir_seccion(proveedor, "Texto de la sección.", n=1, lang="es")
    assert resultado.tarjetas[0].title == "Tarjeta 1"


def test_json_cortado_dice_la_causa() -> None:
    cortado = '{"resumen": "se quedó a medias'
    proveedor = ProveedorFalso([cortado, cortado])
    with pytest.raises(ErrorEnriquecimiento, match="Causa: cortado") as exc:
        resumir_seccion(proveedor, "Texto de la sección.", n=1, lang="es")
    assert "data/logs/ia.log" in str(exc.value)
    assert proveedor.llamadas == 2


def test_campos_faltantes_dice_la_causa() -> None:
    proveedor = ProveedorFalso(
        [_resumen(), '{"title": "Solo el título"}', '{"subtitle": ""}']
    )
    with pytest.raises(ErrorEnriquecimiento, match="Causa: faltan campos") as exc:
        resumir_seccion(proveedor, "Texto de la sección.", n=1, lang="es")
    assert "data/logs/ia.log" in str(exc.value)


def test_texto_sin_json_dice_la_causa() -> None:
    proveedor = ProveedorFalso(["no es json", "tampoco es json"])
    with pytest.raises(ErrorEnriquecimiento, match="Causa: no es JSON"):
        resumir_seccion(proveedor, "Texto de la sección.", n=1, lang="es")
    with db.conectar() as conexion:
        total = conexion.execute("SELECT COUNT(*) AS total FROM ai_cache").fetchone()
    assert int(total["total"]) == 0


def test_json_invalido_luego_valido() -> None:
    proveedor = ProveedorFalso(["no es json", _resumen(), _tarjeta()])
    resultado = resumir_seccion(proveedor, "Texto de la sección.", n=1, lang="es")
    assert proveedor.llamadas == 3
    assert resultado.tarjetas[0].title == "Tarjeta 1"


def test_la_segunda_llamada_sale_de_cache() -> None:
    proveedor = ProveedorFalso([_resumen(), _tarjeta(), _resumen(), _tarjeta(2)])
    primero = resumir_seccion(proveedor, "Texto de la sección.", n=1, lang="es")
    segundo = resumir_seccion(proveedor, "Texto de la sección.", n=1, lang="es")
    assert primero.tarjetas[0].title == segundo.tarjetas[0].title
    assert proveedor.llamadas == 2
    tercero = resumir_seccion(
        proveedor, "Texto de la sección.", n=1, lang="es", regenerar=True
    )
    assert tercero.tarjetas[0].title == "Tarjeta 2"
    assert proveedor.llamadas == 4


def test_ingles_incluye_traduccion() -> None:
    proveedor = ProveedorFalso([_resumen(), _tarjeta(translation="El texto.")])
    resultado = resumir_seccion(
        proveedor, "The terminal lists files in the folder.", n=1, lang="en"
    )
    assert resultado.tarjetas[0].translation == "El texto."
    espanol = ProveedorFalso([_resumen(), _tarjeta(translation="No debería quedar.")])
    sin_traduccion = resumir_seccion(
        espanol, "La terminal lista los archivos.", n=1, lang="es"
    )
    assert sin_traduccion.tarjetas[0].translation == ""


def test_seccion_larga_parte_llamadas() -> None:
    texto = (
        ("palabra " * 200)
        + "\n\n```bash\necho hola\n```\n\n"
        + ("otra " * 800)
    )
    assert len(texto) > 3500
    proveedor = SegunPrompt()
    resultado = resumir_seccion(proveedor, texto, n=1, lang="es")
    assert proveedor.resumenes > 1
    assert proveedor.tarjetas == 1
    assert resultado.tarjetas[0].code == "echo hola"
    assert resultado.tarjetas[0].code_lang == "bash"


def test_cargar_json_casos() -> None:
    assert _cargar_json('```json\n{"resumen": "Hola."}\n```') == {"resumen": "Hola."}
    assert _cargar_json('nota {"resumen": "Hola."} fin') == {"resumen": "Hola."}
    assert _cargar_json('{"resumen": "Hola.",}') == {"resumen": "Hola."}
    assert _cargar_json('{"resumen": "se cortó') is None


def test_proveedor_falso_no_usa_la_red() -> None:
    proveedor = proveedor_desde_config("falso")
    assert "no usa la red" in proveedor.probar()
    prompt = (
        "Devuelve solo JSON con las claves "
        "title, subtitle, original_text, explanation.\n"
        "Texto:\n```bash\nls -l\n```"
    )
    datos = json.loads(proveedor.generar("sistema", prompt))
    assert datos["original_text"] == "ls -l"
    assert "code" not in datos


def test_ollama_envia_opciones(monkeypatch: pytest.MonkeyPatch) -> None:
    capturado: dict[str, object] = {}

    class Respuesta:
        ok = True
        text = "{}"

        def json(self) -> dict[str, object]:
            return {"message": {"content": '{"resumen": "Hola."}'}}

    def post(url: str, json: dict[str, object], timeout: float) -> Respuesta:
        capturado["url"] = url
        capturado["json"] = json
        return Respuesta()

    monkeypatch.setattr(providers.requests, "post", post)
    OllamaProvider("qwen2.5:3b").generar("sistema", "hola", num_predict=512)
    cuerpo = capturado["json"]
    assert isinstance(cuerpo, dict)
    assert cuerpo["options"] == {
        "num_ctx": 4096,
        "temperature": 0.2,
        "num_predict": 512,
        "repeat_penalty": 1.1,
    }
    assert cuerpo["format"] == "json"
