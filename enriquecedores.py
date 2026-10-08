"""Traducción, explicación, subtítulo y resumen a partir de un proveedor."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace

from db import guardar_cache, leer_cache
from importers import codigo_de_parrafo, partir_parrafos
from models import (
    ENRIQUECEDORES,
    Card,
    ErrorEnriquecimiento,
    ResultadoEnriquecimiento,
)
from providers import LLMProvider
from registro import registrar_fallo

_SYSTEM = (
    "Respondes solo con un objeto JSON, sin markdown ni texto alrededor. "
    "Las cadenas van en español."
)
_TOPE_TROZO = 3500
_PREDICT_RESUMEN = 512
_PREDICT_TARJETA = 768
_CAMPOS_TARJETA = (
    "title",
    "subtitle",
    "original_text",
    "explanation",
)


class Traductor:
    """Rellena translation cuando el texto está en inglés."""

    name = "traductor"
    campos = ("translation",)

    def __init__(self, proveedor: LLMProvider):
        self._proveedor = proveedor

    def apply(
        self, card: Card, *, regenerar: bool = False
    ) -> ResultadoEnriquecimiento:
        """Traduce al español si lang es en. Si no, no llama al modelo."""
        if card.lang != "en":
            return ResultadoEnriquecimiento(
                tarjeta=card,
                cambio=False,
                aviso=_aviso_idioma(card.lang),
            )
        valor = _pedir_campo(
            self._proveedor,
            card,
            "translation",
            "Traduce el texto al español.",
            regenerar,
        )
        return ResultadoEnriquecimiento(
            tarjeta=replace(card, translation=valor),
            cambio=True,
            aviso="",
        )


class Explicador:
    """Rellena explanation con un resumen breve en español."""

    name = "explicador"
    campos = ("explanation",)

    def __init__(self, proveedor: LLMProvider):
        self._proveedor = proveedor

    def apply(
        self, card: Card, *, regenerar: bool = False
    ) -> ResultadoEnriquecimiento:
        """Resume el texto en español, en dos o tres frases."""
        valor = _pedir_campo(
            self._proveedor,
            card,
            "explanation",
            "Resume el texto en español, en 2 o 3 frases.",
            regenerar,
        )
        return ResultadoEnriquecimiento(
            tarjeta=replace(card, explanation=valor),
            cambio=True,
            aviso="",
        )


class Subtitulador:
    """Sugiere subtitle solo cuando está vacío."""

    name = "subtitulador"
    campos = ("subtitle",)

    def __init__(self, proveedor: LLMProvider):
        self._proveedor = proveedor

    def apply(
        self, card: Card, *, regenerar: bool = False
    ) -> ResultadoEnriquecimiento:
        """Propone un subtítulo breve. No toca uno que ya exista."""
        if card.subtitle.strip():
            return ResultadoEnriquecimiento(
                tarjeta=card,
                cambio=False,
                aviso="El subtítulo ya tiene texto.",
            )
        valor = _pedir_campo(
            self._proveedor,
            card,
            "subtitle",
            "Propón un subtítulo breve en español.",
            regenerar,
        )
        return ResultadoEnriquecimiento(
            tarjeta=replace(card, subtitle=valor),
            cambio=True,
            aviso="",
        )


def usar_proveedor(proveedor: LLMProvider) -> None:
    """Deja en ENRIQUECEDORES los tres enriquecedores de ese proveedor."""
    ENRIQUECEDORES.clear()
    ENRIQUECEDORES.extend(
        [Traductor(proveedor), Explicador(proveedor), Subtitulador(proveedor)]
    )


def _pedir_campo(
    proveedor: LLMProvider,
    card: Card,
    campo: str,
    instruccion: str,
    regenerar: bool,
) -> str:
    prompt = _prompt(card, campo, instruccion)
    clave = _clave(proveedor, prompt, card.original_text)
    if not regenerar:
        guardado = leer_cache(clave)
        if guardado is not None:
            valor = _campo_de_json(guardado, campo)
            if valor is not None:
                return valor
    bruto = proveedor.generar(_SYSTEM, prompt)
    valor = _campo_de_json(bruto, campo)
    if valor is None:
        reintento = (
            f"{prompt}\n\nLa respuesta anterior no era JSON válido:\n"
            f"{bruto[:500]}\n"
            f'Responde solo con {{"{campo}": "..."}}.'
        )
        bruto = proveedor.generar(_SYSTEM, reintento)
        valor = _campo_de_json(bruto, campo)
    if valor is None:
        raise ErrorEnriquecimiento(
            f"El modelo no devolvió un JSON válido con {campo}."
        )
    guardar_cache(clave, json.dumps({campo: valor}, ensure_ascii=False))
    return valor


def _prompt(card: Card, campo: str, instruccion: str) -> str:
    return (
        f"{instruccion}\n"
        f'Devuelve solo JSON con la clave "{campo}".\n'
        f"Capítulo: {card.chapter}\n"
        f"Título: {card.title}\n"
        f"Subtítulo: {card.subtitle}\n"
        f"Texto:\n{card.original_text}"
    )


def _clave(proveedor: LLMProvider, prompt: str, texto: str) -> str:
    material = f"{proveedor.nombre}\n{proveedor.modelo}\n{prompt}\n{texto}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _campo_de_json(bruto: str, campo: str) -> str | None:
    datos = _cargar_json(bruto)
    if datos is None:
        return None
    valor = datos.get(campo)
    if not isinstance(valor, str) or not valor.strip():
        return None
    return valor.strip()


@dataclass
class TarjetaPropuesta:
    """Tarjeta que el modelo sugiere y la persona aún no ha guardado."""

    title: str
    subtitle: str
    original_text: str
    explanation: str
    code: str
    code_lang: str
    translation: str = ""


@dataclass
class ResultadoResumen:
    """Resumen de una sección y las tarjetas propuestas."""

    resumen: str
    tarjetas: list[TarjetaPropuesta]
    avisos: list[str]


def sugerir_tarjetas(texto: str) -> int:
    """Elige 1, 2 o 3 tarjetas según las palabras del texto."""
    palabras = len(texto.split())
    if palabras < 150:
        return 1
    if palabras <= 400:
        return 2
    return 3


def resumir_seccion(
    proveedor: LLMProvider,
    texto: str,
    *,
    n: int,
    lang: str,
    regenerar: bool = False,
) -> ResultadoResumen:
    """Pide un resumen y n tarjetas. El código sale de las vallas del texto."""
    pedido = min(3, max(1, n))
    contexto = _contexto(proveedor, texto, regenerar)
    resumen = _pedir_resumen_seccion(proveedor, contexto, regenerar)
    tarjetas: list[TarjetaPropuesta] = []
    for indice in range(pedido):
        tarjetas.append(
            _pedir_una_tarjeta(
                proveedor,
                contexto,
                indice,
                pedido,
                lang,
                regenerar,
                resumen,
                tarjetas,
            )
        )
    return ResultadoResumen(
        resumen=resumen,
        tarjetas=tarjetas,
        avisos=_asignar_codigo(tarjetas, texto),
    )


def _aviso_idioma(lang: str) -> str:
    if lang == "es":
        return "El idioma es español: no se traduce."
    if not lang:
        return "No hay idioma detectado: no se traduce."
    return f"El idioma es {lang}: solo se traduce del inglés."


def _contexto(proveedor: LLMProvider, texto: str, regenerar: bool) -> str:
    """Deja el texto corto tal cual. El largo pasa a resúmenes y sus vallas."""
    if len(texto) <= _TOPE_TROZO:
        return texto
    frases = [
        _resumen_corto(proveedor, trozo, regenerar) for trozo in _trozos(texto)
    ]
    junto = "\n\n".join(frases)
    bloques = _bloques_codigo(texto)
    if not bloques:
        return junto
    return junto + "\n\n" + "\n\n".join(bloques)


def _trozos(texto: str) -> list[str]:
    partes = partir_parrafos(texto) or [texto]
    grupos: list[str] = []
    actual: list[str] = []
    tamano = 0
    for parte in partes:
        extra = len(parte) + 2
        if actual and tamano + extra > _TOPE_TROZO:
            grupos.append("\n\n".join(actual))
            actual = []
            tamano = 0
        actual.append(parte)
        tamano += extra
    if actual:
        grupos.append("\n\n".join(actual))
    return grupos


def _bloques_codigo(texto: str) -> list[str]:
    bloques: list[str] = []
    for parrafo in partir_parrafos(texto):
        codigo = codigo_de_parrafo(parrafo)
        if codigo is None:
            continue
        lang, interior = codigo
        marca = f"```{lang}" if lang else "```"
        bloques.append(f"{marca}\n{interior}\n```")
    return bloques


def _resumen_corto(proveedor: LLMProvider, trozo: str, regenerar: bool) -> str:
    prompt = (
        "Resume este trozo en español, en 2 frases.\n"
        'Devuelve solo JSON con la clave "resumen".\n'
        f"Texto:\n{trozo}"
    )
    datos = _pedir_json(
        proveedor,
        prompt,
        trozo,
        regenerar,
        _es_resumen_corto,
        "El modelo no devolvió un JSON válido con resumen.",
        _PREDICT_RESUMEN,
    )
    return str(datos["resumen"]).strip()


def _pedir_resumen_seccion(
    proveedor: LLMProvider, texto: str, regenerar: bool
) -> str:
    prompt = (
        "Resume el texto en español, en 3 a 5 frases.\n"
        'Devuelve solo JSON con la clave "resumen".\n'
        f"Texto:\n{texto}"
    )
    datos = _pedir_json(
        proveedor,
        prompt,
        texto,
        regenerar,
        _es_resumen_corto,
        "El modelo no devolvió un JSON válido con resumen.",
        _PREDICT_RESUMEN,
    )
    return str(datos["resumen"]).strip()


def _pedir_una_tarjeta(
    proveedor: LLMProvider,
    texto: str,
    indice: int,
    total: int,
    lang: str,
    regenerar: bool,
    resumen: str,
    anteriores: list[TarjetaPropuesta],
) -> TarjetaPropuesta:
    prompt = _prompt_tarjeta(texto, indice, total, lang, resumen, anteriores)
    datos = _pedir_json(
        proveedor,
        prompt,
        texto,
        regenerar,
        lambda item: _es_tarjeta(item, lang),
        "El modelo no devolvió un JSON válido con la tarjeta.",
        _PREDICT_TARJETA,
    )
    return _tarjeta_de_dict(datos, lang)


def _prompt_tarjeta(
    texto: str,
    indice: int,
    total: int,
    lang: str,
    resumen: str,
    anteriores: list[TarjetaPropuesta],
) -> str:
    claves = "title, subtitle, original_text, explanation"
    traduccion = ""
    if lang == "en":
        claves += ", translation"
        traduccion = " Incluye translation al español."
    ya = ""
    if anteriores:
        titulos = "; ".join(tarjeta.title for tarjeta in anteriores)
        ya = f"No repitas estas tarjetas: {titulos}.\n"
    return (
        f"{ya}"
        f"Escribe la tarjeta {indice + 1} de {total}.\n"
        f"Devuelve solo JSON con las claves {claves}. "
        "original_text es un fragmento copiado del texto. "
        "Si ese fragmento incluye un comando, cópialo tal cual."
        f"{traduccion}\n"
        f"Resumen:\n{resumen}\n"
        f"Texto:\n{texto}"
    )


def _pedir_json(
    proveedor: LLMProvider,
    prompt: str,
    texto: str,
    regenerar: bool,
    valido,
    mensaje: str,
    num_predict: int,
) -> dict[str, object]:
    clave = _clave(proveedor, prompt, texto)
    if not regenerar:
        guardado = leer_cache(clave)
        if guardado is not None:
            datos = _cargar_json(guardado)
            if datos is not None and valido(datos):
                return datos
    bruto = proveedor.generar(_SYSTEM, prompt, num_predict=num_predict)
    datos = _cargar_json(bruto)
    if datos is None or not valido(datos):
        registrar_fallo(_motivo_validacion(bruto, datos), bruto)
        reintento = (
            f"{prompt}\n\nLa respuesta anterior no era JSON válido:\n"
            f"{bruto[:500]}\n"
            "Responde solo con el JSON pedido."
        )
        bruto = proveedor.generar(_SYSTEM, reintento, num_predict=num_predict)
        datos = _cargar_json(bruto)
    if datos is None or not valido(datos):
        registrar_fallo(_motivo_validacion(bruto, datos), bruto)
        motivo = _motivo_validacion(bruto, datos)
        raise ErrorEnriquecimiento(
            f"{mensaje} Causa: {motivo}. Detalle en data/logs/ia.log."
        )
    guardar_cache(clave, json.dumps(datos, ensure_ascii=False))
    return datos


def _motivo_validacion(bruto: str, datos: dict[str, object] | None) -> str:
    """Distingue un JSON cortado, uno ilegible y uno al que le faltan campos."""
    if datos is not None:
        return "faltan campos"
    texto = bruto.strip()
    texto = re.sub(r"^```(?:json)?\s*", "", texto)
    texto = re.sub(r"\s*```$", "", texto).strip()
    if texto.startswith("{") and not texto.endswith("}"):
        return "cortado"
    return "no es JSON"


def _cargar_json(bruto: str) -> dict[str, object] | None:
    texto = bruto.strip()
    texto = re.sub(r"^```(?:json)?\s*", "", texto)
    texto = re.sub(r"\s*```$", "", texto).strip()
    inicio = texto.find("{")
    fin = texto.rfind("}")
    if inicio != -1 and fin >= inicio:
        texto = texto[inicio : fin + 1]
    return _objeto_json(texto) or _objeto_json(_reparar_json(texto))


def _reparar_json(texto: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", texto)


def _objeto_json(texto: str) -> dict[str, object] | None:
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError:
        return None
    if not isinstance(datos, dict):
        return None
    return datos


def _es_resumen_corto(datos: dict[str, object]) -> bool:
    resumen = datos.get("resumen")
    return isinstance(resumen, str) and bool(resumen.strip())


def _es_tarjeta(item: dict[str, object], lang: str) -> bool:
    for campo in _CAMPOS_TARJETA:
        if not isinstance(item.get(campo), str):
            return False
    if not str(item["title"]).strip() or not str(item["original_text"]).strip():
        return False
    if not str(item["explanation"]).strip():
        return False
    if lang == "en":
        traduccion = item.get("translation")
        return isinstance(traduccion, str) and bool(traduccion.strip())
    return True


def _tarjeta_de_dict(item: dict[str, object], lang: str) -> TarjetaPropuesta:
    traduccion = item.get("translation", "")
    if lang != "en" or not isinstance(traduccion, str):
        traduccion = ""
    return TarjetaPropuesta(
        title=str(item["title"]).strip(),
        subtitle=str(item["subtitle"]).strip(),
        original_text=str(item["original_text"]).strip(),
        explanation=str(item["explanation"]).strip(),
        code="",
        code_lang="",
        translation=traduccion.strip(),
    )


def _asignar_codigo(tarjetas: list[TarjetaPropuesta], fuente: str) -> list[str]:
    """Copia cada valla a la tarjeta cuyo texto la contiene."""
    bloques = _bloques_de_fuente(fuente)
    for tarjeta in tarjetas:
        for interior, lenguaje in bloques:
            if _contiene_codigo(tarjeta.original_text, interior):
                tarjeta.code = interior.strip("\n")
                tarjeta.code_lang = lenguaje
                break
    avisos: list[str] = []
    for interior, _lenguaje in bloques:
        if not any(
            _contiene_codigo(tarjeta.original_text, interior) for tarjeta in tarjetas
        ):
            avisos.append(
                "Un bloque de código de la sección no entró en ninguna tarjeta."
            )
            break
    return avisos


def _bloques_de_fuente(fuente: str) -> list[tuple[str, str]]:
    bloques: list[tuple[str, str]] = []
    for parrafo in partir_parrafos(fuente):
        codigo = codigo_de_parrafo(parrafo)
        if codigo is None:
            continue
        lenguaje, interior = codigo
        if interior.strip():
            bloques.append((interior, lenguaje))
    return bloques


def _contiene_codigo(original: str, interior: str) -> bool:
    codigo = interior.strip()
    if not codigo:
        return False
    if codigo in original:
        return True
    for linea in codigo.splitlines():
        limpia = linea.strip()
        if len(limpia) >= 2 and not limpia.startswith("#") and limpia in original:
            return True
    return False
