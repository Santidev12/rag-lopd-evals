"""Tests de EmbebedorDeepInfra: la llamada HTTP real está mockeada con respx. Nada aquí sale a
internet ni gasta un céntimo de verdad."""

from __future__ import annotations

import httpx
import pytest
import respx

from rag_lopd.config import Settings
from rag_lopd.retrieval.embeddings import ENDPOINT, EmbebedorDeepInfra


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {"deepinfra_api_key": "clave-de-prueba"}
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _respuesta(vectores: list[list[float]]) -> httpx.Response:
    datos = [{"object": "embedding", "index": i, "embedding": v} for i, v in enumerate(vectores)]
    return httpx.Response(
        200, json={"object": "list", "data": datos, "model": "BAAI/bge-m3", "usage": {}}
    )


@respx.mock
def test_embeber_devuelve_un_vector_por_texto() -> None:
    respx.post(ENDPOINT).mock(return_value=_respuesta([[0.1, 0.2], [0.3, 0.4]]))

    vectores = EmbebedorDeepInfra(_settings()).embeber(["uno", "dos"])

    assert vectores == [[0.1, 0.2], [0.3, 0.4]]


@respx.mock
def test_embeber_reordena_por_index_no_por_posicion_en_la_respuesta() -> None:
    # La API no promete devolver `data` en el mismo orden que `input`: el índice de cada fila
    # es lo único fiable para saber a qué texto corresponde cada vector.
    respuesta = httpx.Response(
        200,
        json={
            "object": "list",
            "data": [
                {"object": "embedding", "index": 1, "embedding": [9.0]},
                {"object": "embedding", "index": 0, "embedding": [1.0]},
            ],
            "model": "BAAI/bge-m3",
            "usage": {},
        },
    )
    respx.post(ENDPOINT).mock(return_value=respuesta)

    vectores = EmbebedorDeepInfra(_settings()).embeber(["primero", "segundo"])

    assert vectores == [[1.0], [9.0]]


@respx.mock
def test_embeber_trocea_en_lotes() -> None:
    ruta = respx.post(ENDPOINT).mock(return_value=_respuesta([[1.0], [2.0]]))

    EmbebedorDeepInfra(_settings(), tamano_lote=2).embeber(["a", "b", "c", "d", "e"])

    assert ruta.call_count == 3  # lotes de 2, 2 y 1 para 5 textos


def test_sin_clave_no_se_puede_construir() -> None:
    with pytest.raises(ValueError, match="DEEPINFRA_API_KEY"):
        EmbebedorDeepInfra(_settings(deepinfra_api_key=None))
