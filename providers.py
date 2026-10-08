"""Proveedores de texto: Ollama en local o una API compatible con OpenAI."""

from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod

import requests

from registro import registrar_fallo, registrar_llamada

from config import (
    API_KEY,
    API_MODELO,
    API_URL,
    LLM_TIMEOUT,
    OLLAMA_MODELO,
    OLLAMA_URL,
    PROVEEDOR,
)


class ErrorProveedor(Exception):
    """Fallo al hablar con el modelo. El mensaje ya está en español."""


class LLMProvider(ABC):
    """Genera texto a partir de un sistema y un prompt."""

    nombre: str
    modelo: str

    @abstractmethod
    def generar(self, system: str, prompt: str, *, num_predict: int = 768) -> str:
        """Devuelve el texto del modelo."""

    @abstractmethod
    def probar(self) -> str:
        """Comprueba la conexión y devuelve un mensaje en español."""


class OllamaProvider(LLMProvider):
    """Habla con Ollama en local por HTTP."""

    def __init__(self, modelo: str, url: str = OLLAMA_URL, timeout: float = LLM_TIMEOUT):
        self.nombre = "ollama"
        self.modelo = modelo
        self._url = url.rstrip("/")
        self._timeout = timeout

    def generar(self, system: str, prompt: str, *, num_predict: int = 768) -> str:
        """Pide un chat y devuelve el contenido, en JSON si el modelo obedece."""
        inicio = time.perf_counter()
        try:
            respuesta = requests.post(
                f"{self._url}/api/chat",
                json={
                    "model": self.modelo,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {
                        "num_ctx": 4096,
                        "temperature": 0.2,
                        "num_predict": num_predict,
                        "repeat_penalty": 1.1,
                    },
                },
                timeout=self._timeout,
            )
        except requests.ConnectionError as exc:
            raise _ollama_apagado(self._url) from exc
        except requests.Timeout as exc:
            registrar_fallo("tiempo agotado", "")
            raise _tiempo_agotado() from exc
        except requests.RequestException as exc:
            raise ErrorProveedor("No se pudo hablar con Ollama.") from exc
        registrar_llamada(
            self.nombre,
            self.modelo,
            prompt,
            time.perf_counter() - inicio,
            respuesta.text,
        )
        if not respuesta.ok:
            raise _error_ollama(respuesta, self.modelo)
        return _texto_ollama(respuesta)

    def probar(self) -> str:
        """Comprueba que Ollama responde y que el modelo está descargado."""
        try:
            respuesta = requests.get(
                f"{self._url}/api/tags",
                timeout=min(self._timeout, 5),
            )
        except requests.ConnectionError as exc:
            raise _ollama_apagado(self._url) from exc
        except requests.Timeout as exc:
            raise _tiempo_agotado() from exc
        except requests.RequestException as exc:
            raise ErrorProveedor("No se pudo hablar con Ollama.") from exc
        if not respuesta.ok:
            raise ErrorProveedor("Ollama no respondió a la prueba de conexión.")
        try:
            datos = respuesta.json()
        except ValueError as exc:
            raise ErrorProveedor("Ollama no respondió a la prueba de conexión.") from exc
        nombres = [
            str(item.get("name", ""))
            for item in datos.get("models") or []
            if isinstance(item, dict)
        ]
        if not _modelo_descargado(self.modelo, nombres):
            raise ErrorProveedor(
                f"El modelo {self.modelo} no está descargado. "
                f"Prueba: ollama pull {self.modelo}"
            )
        return f"Conexión correcta. Modelo {self.modelo} disponible."


class ApiProvider(LLMProvider):
    """Habla con una API de chat. La clave solo vive en el entorno."""

    def __init__(
        self,
        modelo: str,
        url: str = API_URL,
        clave: str = API_KEY,
        timeout: float = LLM_TIMEOUT,
    ):
        self.nombre = "api"
        self.modelo = modelo
        self._url = url.rstrip("/")
        self._clave = clave
        self._timeout = timeout

    def generar(self, system: str, prompt: str, *, num_predict: int = 768) -> str:
        """Pide un chat y devuelve el contenido del primer mensaje."""
        self._exigir_config()
        try:
            respuesta = requests.post(
                self._chat_url(),
                headers=self._cabeceras(),
                json={
                    "model": self.modelo,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                },
                timeout=self._timeout,
            )
        except requests.Timeout as exc:
            raise _tiempo_agotado() from exc
        except requests.RequestException as exc:
            raise ErrorProveedor("No se pudo hablar con la API.") from exc
        if respuesta.status_code in (401, 403):
            raise ErrorProveedor("La API rechazó la clave.")
        if not respuesta.ok:
            raise ErrorProveedor("La API rechazó la petición.")
        return _texto_api(respuesta)

    def probar(self) -> str:
        """Comprueba que la API acepta la clave."""
        self._exigir_config()
        try:
            respuesta = requests.get(
                self._models_url(),
                headers=self._cabeceras(),
                timeout=min(self._timeout, 15),
            )
        except requests.Timeout as exc:
            raise _tiempo_agotado() from exc
        except requests.RequestException as exc:
            raise ErrorProveedor("No se pudo hablar con la API.") from exc
        if respuesta.status_code in (401, 403):
            raise ErrorProveedor("La API rechazó la clave.")
        if not respuesta.ok:
            raise ErrorProveedor("La API no respondió a la prueba de conexión.")
        return f"Conexión correcta. Modelo {self.modelo} configurado."

    def _exigir_config(self) -> None:
        if not self._url:
            raise ErrorProveedor("Falta la variable BOOK2ANKI_API_URL.")
        if not self.modelo.strip():
            raise ErrorProveedor("Falta la variable BOOK2ANKI_API_MODEL.")
        if not self._clave:
            raise ErrorProveedor("Falta la variable BOOK2ANKI_API_KEY.")

    def _cabeceras(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._clave}"}

    def _chat_url(self) -> str:
        if self._url.endswith("/chat/completions"):
            return self._url
        return f"{self._url}/chat/completions"

    def _models_url(self) -> str:
        base = self._url
        if base.endswith("/chat/completions"):
            base = base[: -len("/chat/completions")]
        return f"{base}/models"


class FalsoProvider(LLMProvider):
    """Respuestas fijas para probar la interfaz. No usa la red."""

    def __init__(self) -> None:
        self.nombre = "falso"
        self.modelo = "falso"

    def generar(self, system: str, prompt: str, *, num_predict: int = 768) -> str:
        """Devuelve JSON de estudio, de un trozo o de un solo campo."""
        if "title, subtitle, original_text, explanation" in prompt:
            return _json_tarjeta(prompt)
        if "tarjetas" in prompt:
            return _json_estudio(prompt)
        if "resumen" in prompt:
            return (
                '{"resumen": "Resumen de prueba en tres frases. '
                'Cubre el texto de la sección. Sirve para estudiar."}'
            )
        if "translation" in prompt:
            return '{"translation": "Traducción de prueba."}'
        if "explanation" in prompt:
            return '{"explanation": "Explicación de prueba en dos frases."}'
        if "subtitle" in prompt:
            return '{"subtitle": "Subtítulo de prueba"}'
        return '{"resumen": "Resumen de prueba."}'

    def probar(self) -> str:
        """Confirma que este proveedor no llama a la red."""
        return "Proveedor de prueba: no usa la red."


def proveedor_desde_config(
    nombre: str | None = None, modelo: str | None = None
) -> LLMProvider:
    """Construye el proveedor elegido, con el modelo indicado o el de config."""
    elegido = (nombre if nombre is not None else PROVEEDOR).strip().lower()
    if elegido == "falso":
        return FalsoProvider()
    if elegido == "api":
        return ApiProvider(modelo=_modelo(modelo, API_MODELO))
    if elegido == "ollama":
        return OllamaProvider(modelo=_modelo(modelo, OLLAMA_MODELO))
    raise ErrorProveedor("El proveedor debe ser ollama o api.")


def _json_tarjeta(prompt: str) -> str:
    """Arma una sola tarjeta. Si el prompt trae una valla, el texto la copia."""
    numero = re.search(r"tarjeta (\d+) de", prompt)
    indice = numero.group(1) if numero else "1"
    valla = re.search(r"```([A-Za-z0-9_+-]*)\n(.*?)```", prompt, re.DOTALL)
    original = "Texto de prueba de la sección."
    if valla is not None:
        original = valla.group(2).strip("\n")
    datos = {
        "title": f"Tarjeta {indice}",
        "subtitle": "de prueba",
        "original_text": original,
        "explanation": "Explicación de prueba en dos frases. Resume el trozo.",
    }
    if "translation" in prompt:
        datos["translation"] = "Traducción de prueba."
    return json.dumps(datos, ensure_ascii=False)


def _json_estudio(prompt: str) -> str:
    """Arma el JSON de resumen copiando, si hay, un bloque del propio prompt."""
    coincidencia = re.search(r"exactamente (\d+)", prompt)
    cantidad = int(coincidencia.group(1)) if coincidencia else 1
    cantidad = min(3, max(1, cantidad))
    valla = re.search(r"```([A-Za-z0-9_+-]*)\n(.*?)```", prompt, re.DOTALL)
    codigo = ""
    lenguaje = ""
    if valla is not None:
        lenguaje = valla.group(1)
        codigo = valla.group(2).strip("\n")
    tarjetas = []
    for indice in range(cantidad):
        tarjeta = {
            "title": f"Tarjeta {indice + 1}",
            "subtitle": "de prueba",
            "original_text": "Texto de prueba de la sección.",
            "explanation": "Explicación de prueba en dos frases. Resume el trozo.",
            "code": codigo if indice == 0 else "",
            "code_lang": lenguaje if indice == 0 else "",
        }
        if "translation" in prompt:
            tarjeta["translation"] = "Traducción de prueba."
        tarjetas.append(tarjeta)
    return json.dumps(
        {
            "resumen": (
                "Resumen de prueba en tres frases. "
                "Cubre el texto de la sección. Sirve para estudiar."
            ),
            "tarjetas": tarjetas,
        },
        ensure_ascii=False,
    )


def _modelo(pedido: str | None, defecto: str) -> str:
    texto = (pedido or "").strip()
    return texto or defecto


def _ollama_apagado(url: str) -> ErrorProveedor:
    return ErrorProveedor(
        f"Ollama no está en marcha en {url}. Arráncalo con ollama serve."
    )


def _tiempo_agotado() -> ErrorProveedor:
    return ErrorProveedor(
        "El modelo no respondió a tiempo. Detalle en data/logs/ia.log."
    )


def _error_ollama(respuesta: requests.Response, modelo: str) -> ErrorProveedor:
    detalle = ""
    try:
        cuerpo = respuesta.json()
    except ValueError:
        cuerpo = None
    if isinstance(cuerpo, dict):
        detalle = str(cuerpo.get("error", ""))
    if respuesta.status_code == 404 or "not found" in detalle.lower():
        return ErrorProveedor(
            f"El modelo {modelo} no está descargado. Prueba: ollama pull {modelo}"
        )
    if "repeat" in detalle.lower():
        return ErrorProveedor(
            "El modelo se quedó repitiendo la misma salida. "
            "Causa: cortado. Detalle en data/logs/ia.log."
        )
    return ErrorProveedor(
        "Ollama rechazó la petición. Detalle en data/logs/ia.log."
    )


def _texto_ollama(respuesta: requests.Response) -> str:
    try:
        datos = respuesta.json()
    except ValueError as exc:
        raise ErrorProveedor("Ollama no devolvió texto.") from exc
    mensaje = datos.get("message") if isinstance(datos, dict) else None
    contenido = mensaje.get("content") if isinstance(mensaje, dict) else None
    if isinstance(contenido, dict):
        contenido = json.dumps(contenido, ensure_ascii=False)
    if not isinstance(contenido, str) or not contenido.strip():
        raise ErrorProveedor("Ollama no devolvió texto.")
    return contenido


def _texto_api(respuesta: requests.Response) -> str:
    try:
        datos = respuesta.json()
    except ValueError as exc:
        raise ErrorProveedor("La API no devolvió texto.") from exc
    try:
        contenido = datos["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ErrorProveedor("La API no devolvió texto.") from exc
    if not isinstance(contenido, str) or not contenido.strip():
        raise ErrorProveedor("La API no devolvió texto.")
    return contenido


def _modelo_descargado(modelo: str, nombres: list[str]) -> bool:
    pedido = modelo.strip()
    for nombre in nombres:
        if nombre == pedido or nombre.split(":")[0] == pedido:
            return True
        if nombre.startswith(pedido + ":"):
            return True
    return False
