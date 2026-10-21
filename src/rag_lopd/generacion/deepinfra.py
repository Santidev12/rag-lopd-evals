"""Modelos de chat servidos por DeepInfra (endpoint compatible con OpenAI) como `ModeloDeLenguaje`.

Se usa para el **juez**: tiene que ser de otra familia que el generador (Gemini) para que no se
favorezca a sí mismo, y DeepInfra ya está en el proyecto por los embeddings (misma clave).

Solo se mandan `model`, `messages` y `temperature: 0`. No se manda `response_format` ni ningún
parámetro de razonamiento: no están verificados para este modelo, y un parámetro no soportado
convierte toda la pasada en un 400. El JSON lo pide el prompt y lo valida pydantic, igual que con
Gemini. El id lleva la fecha (`-0731`) a propósito: un juez que cambia sin avisar invalida la
comparación entre pasadas.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from typing import Any

import httpx

from rag_lopd.config import Settings
from rag_lopd.generacion.modelo import Completado, Tarifa, Uso, buscar_tarifa
from rag_lopd.generacion.reintentos import post_con_reintentos

ENDPOINT = "https://api.deepinfra.com/v1/openai/chat/completions"
MODELO_POR_DEFECTO = "deepseek-ai/DeepSeek-V4-Flash-0731"

#: USD por millón de tokens, de la página de cada modelo en https://deepinfra.com (oct-2026).
#: El alias sin fecha (`DeepSeek-V4-Flash`) cuesta 0,09 de entrada y apunta a lo que DeepInfra
#: decida: por eso se fija la versión con fecha.
TARIFAS: dict[str, Tarifa] = {
    "deepseek-ai/DeepSeek-V4-Flash-0731": Tarifa(entrada_usd_mtok=0.06, salida_usd_mtok=0.18),
    "deepseek-ai/DeepSeek-V4-Flash": Tarifa(entrada_usd_mtok=0.09, salida_usd_mtok=0.18),
}

_BLOQUE_PENSAMIENTO = re.compile(r"<think>.*?</think>", re.DOTALL)


def tarifa_de(modelo: str) -> Tarifa:
    return buscar_tarifa(TARIFAS, modelo)


class DeepInfraModelo:
    """Una llamada, un texto. Mismos reintentos que Gemini ante 429 o fallo del servidor."""

    def __init__(
        self,
        settings: Settings,
        *,
        modelo: str = MODELO_POR_DEFECTO,
        tarifa: Tarifa | None = None,
        esperar: Callable[[float], None] = time.sleep,
    ) -> None:
        if not settings.deepinfra_api_key:
            raise ValueError(
                "falta DEEPINFRA_API_KEY en .env: sin ella no se puede llamar a DeepInfra."
            )
        self.nombre = modelo
        self.tarifa = tarifa or tarifa_de(modelo)
        self._esperar = esperar
        self._cliente = httpx.Client(
            headers={"Authorization": f"Bearer {settings.deepinfra_api_key}"},
            timeout=settings.http_timeout_seconds,
        )

    def completar(self, sistema: str, usuario: str) -> Completado:
        cuerpo = {
            "model": self.nombre,
            "messages": [
                {"role": "system", "content": sistema},
                {"role": "user", "content": usuario},
            ],
            "temperature": 0,
        }
        respuesta = post_con_reintentos(self._cliente, ENDPOINT, cuerpo, esperar=self._esperar)
        datos = respuesta.json()
        return Completado(texto=_texto(datos), uso=_uso(datos))

    def close(self) -> None:
        self._cliente.close()

    def __enter__(self) -> DeepInfraModelo:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()


def _texto(datos: dict[str, Any]) -> str:
    """El contenido del primer mensaje, sin un posible bloque `<think>` incrustado. Vacío si no
    hay ninguno: quien lo use lo registra como salida inválida en vez de romper la pasada."""
    opciones = datos.get("choices") or []
    if not opciones:
        return ""
    contenido = opciones[0].get("message", {}).get("content") or ""
    return _BLOQUE_PENSAMIENTO.sub("", contenido).strip()


def _uso(datos: dict[str, Any]) -> Uso:
    """Tokens facturados. En esta API `completion_tokens` ya incluye el razonamiento, si lo hay."""
    uso = datos.get("usage") or {}
    return Uso(
        tokens_entrada=int(uso.get("prompt_tokens", 0)),
        tokens_salida=int(uso.get("completion_tokens", 0)),
    )
