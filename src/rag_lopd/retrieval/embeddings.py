"""Embeddings vía DeepInfra: BGE-M3 servido como API, para indexar y para consultar.

Decisión deliberada de v0, distinta de lo que dejó abierto el ticket 04 (indexar en local con
BGE-M3 + llamar a la API solo para la consulta). Indexar las 728 unidades por la propia API
cuesta unos pocos céntimos una sola vez (0,01 $/millón de tokens) y evita meter
sentence-transformers + torch (varios GB) como dependencia solo para un paso que se corre una
vez. Si el corpus crece mucho (AEPD en v1) o el coste deja de ser trivial, se puede mover el
indexado a local sin tocar nada fuera de este módulo: `RecuperadorDenso` no sabe ni le importa
de dónde salen los vectores.
"""

from __future__ import annotations

from typing import Protocol

import httpx

from rag_lopd.config import Settings

ENDPOINT = "https://api.deepinfra.com/v1/openai/embeddings"
MODELO = "BAAI/bge-m3"

_TAMANO_LOTE_POR_DEFECTO = 32


class Embebedor(Protocol):
    """Cualquier fuente de embeddings cumple esto: texto en, vectores fuera, mismo orden."""

    def embeber(self, textos: list[str]) -> list[list[float]]: ...


class EmbebedorDeepInfra:
    """Embebe texto llamando al endpoint de embeddings (compatible con OpenAI) de DeepInfra.

    Trocea en lotes en vez de mandar las 728 unidades en una sola llamada: un cuerpo enorme
    tiene más de una forma de fallar (timeout, límite de tamaño no documentado) y trocear no
    cuesta nada.
    """

    def __init__(self, settings: Settings, *, tamano_lote: int = _TAMANO_LOTE_POR_DEFECTO) -> None:
        if not settings.deepinfra_api_key:
            raise ValueError(
                "falta DEEPINFRA_API_KEY en .env: sin ella no se puede llamar a DeepInfra."
            )
        self._tamano_lote = tamano_lote
        self._cliente = httpx.Client(
            headers={"Authorization": f"Bearer {settings.deepinfra_api_key}"},
            timeout=settings.http_timeout_seconds,
        )

    def embeber(self, textos: list[str]) -> list[list[float]]:
        vectores: list[list[float]] = []
        for inicio in range(0, len(textos), self._tamano_lote):
            lote = textos[inicio : inicio + self._tamano_lote]
            vectores.extend(self._embeber_lote(lote))
        return vectores

    def _embeber_lote(self, lote: list[str]) -> list[list[float]]:
        respuesta = self._cliente.post(
            ENDPOINT,
            json={"model": MODELO, "input": lote, "encoding_format": "float"},
        )
        respuesta.raise_for_status()
        # La API garantiza el orden mediante `index`, no mediante la posición en `data`.
        filas = sorted(respuesta.json()["data"], key=lambda fila: fila["index"])
        return [fila["embedding"] for fila in filas]

    def close(self) -> None:
        self._cliente.close()

    def __enter__(self) -> EmbebedorDeepInfra:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()
