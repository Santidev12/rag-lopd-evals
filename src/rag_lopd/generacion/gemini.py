"""Gemini como `ModeloDeLenguaje`, por la API REST de Google (`generateContent`).

Se usa `generateContent` y no la Interactions API: la documentación de Google marca la segunda
como la recomendada para proyectos nuevos y `generateContent` como "legacy" pero plenamente
soportada y sin fecha de retirada. Para un cliente de una sola llamada sin estado, el contrato de
`generateContent` está más fijado y se lee mejor en los tests; si Google lo retira, es cambiar este
módulo: nada fuera de él sabe qué API hay debajo.

Solo se piden `temperature: 0` y `responseMimeType: application/json`. El esquema del JSON no se
manda a la API (campo `responseSchema`): va en el prompt y lo valida pydantic en `responder`, así
que no depende de qué subconjunto de JSON Schema acepte cada versión de la API.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx

from rag_lopd.config import Settings
from rag_lopd.generacion.modelo import Completado, Tarifa, Uso, buscar_tarifa
from rag_lopd.generacion.reintentos import post_con_reintentos

URL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
MODELO_POR_DEFECTO = "gemini-3.5-flash-lite"

#: USD por millón de tokens, de https://ai.google.dev/gemini-api/docs/pricing (oct-2026). Una
#: tarifa que no está aquí no se adivina: se pasa explícita, o el coste del README sería inventado.
TARIFAS: dict[str, Tarifa] = {
    "gemini-3.5-flash-lite": Tarifa(entrada_usd_mtok=0.30, salida_usd_mtok=2.50),
    "gemini-3.1-flash-lite": Tarifa(entrada_usd_mtok=0.25, salida_usd_mtok=1.50),
}


def tarifa_de(modelo: str) -> Tarifa:
    return buscar_tarifa(TARIFAS, modelo)


class GeminiModelo:
    """Una llamada, un texto. Reintenta con espera creciente ante límite de uso (429) o fallo
    transitorio del servidor: el nivel gratuito tiene un límite de peticiones por minuto bajo, y
    una pasada de 50 preguntas lo roza."""

    def __init__(
        self,
        settings: Settings,
        *,
        modelo: str = MODELO_POR_DEFECTO,
        tarifa: Tarifa | None = None,
        esperar: Callable[[float], None] = time.sleep,
    ) -> None:
        if not settings.google_api_key:
            raise ValueError("falta GOOGLE_API_KEY en .env: sin ella no se puede llamar a Gemini.")
        self.nombre = modelo
        self.tarifa = tarifa or tarifa_de(modelo)
        self._esperar = esperar
        self._cliente = httpx.Client(
            headers={"x-goog-api-key": settings.google_api_key},
            timeout=settings.http_timeout_seconds,
        )

    def completar(self, sistema: str, usuario: str) -> Completado:
        cuerpo = {
            "systemInstruction": {"parts": [{"text": sistema}]},
            "contents": [{"role": "user", "parts": [{"text": usuario}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        }
        respuesta = post_con_reintentos(
            self._cliente, URL.format(modelo=self.nombre), cuerpo, esperar=self._esperar
        )
        datos = respuesta.json()
        return Completado(texto=_texto(datos), uso=_uso(datos))

    def close(self) -> None:
        self._cliente.close()

    def __enter__(self) -> GeminiModelo:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()


def _texto(datos: dict[str, Any]) -> str:
    """El texto del primer candidato, sin las partes de razonamiento. Vacío si no hay candidato
    (respuesta bloqueada): `responder` lo registra como salida inválida en vez de romper la
    pasada entera."""
    candidatos = datos.get("candidates") or []
    if not candidatos:
        return ""
    partes = candidatos[0].get("content", {}).get("parts", [])
    return "".join(p["text"] for p in partes if "text" in p and not p.get("thought"))


def _uso(datos: dict[str, Any]) -> Uso:
    """Tokens facturados. La salida se calcula como total - entrada y no como
    `candidatesTokenCount`, porque el total incluye los tokens de razonamiento, que se pagan como
    salida aunque no aparezcan en el texto."""
    meta = datos.get("usageMetadata", {})
    entrada = int(meta.get("promptTokenCount", 0))
    candidatos = int(meta.get("candidatesTokenCount", 0))
    total = int(meta.get("totalTokenCount", 0))
    return Uso(tokens_entrada=entrada, tokens_salida=max(total - entrada, candidatos))
