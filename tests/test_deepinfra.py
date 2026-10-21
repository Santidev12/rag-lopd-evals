"""Tests del cliente de chat de DeepInfra: la llamada HTTP está mockeada con respx."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from rag_lopd.config import Settings
from rag_lopd.generacion.deepinfra import ENDPOINT, MODELO_POR_DEFECTO, DeepInfraModelo, tarifa_de
from rag_lopd.generacion.modelo import Tarifa, Uso


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {"deepinfra_api_key": "clave-de-prueba"}
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _ok(contenido: str | None = '{"veredicto": "correcta"}') -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"role": "assistant", "content": contenido}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150},
        },
    )


def _modelo(**kwargs: object) -> DeepInfraModelo:
    esperas: list[float] = []
    modelo = DeepInfraModelo(_settings(), esperar=esperas.append, **kwargs)  # type: ignore[arg-type]
    modelo.esperas = esperas  # type: ignore[attr-defined]
    return modelo


@respx.mock
def test_completar_manda_el_modelo_fijado_el_sistema_y_el_usuario() -> None:
    ruta = respx.post(ENDPOINT).mock(return_value=_ok())

    _modelo().completar("instrucción", "pregunta")

    peticion = ruta.calls.last.request
    cuerpo = json.loads(peticion.content)
    assert peticion.headers["authorization"] == "Bearer clave-de-prueba"
    assert cuerpo["model"] == MODELO_POR_DEFECTO
    assert MODELO_POR_DEFECTO.endswith("-0731")  # versión fechada: un juez no cambia sin avisar
    assert cuerpo["messages"] == [
        {"role": "system", "content": "instrucción"},
        {"role": "user", "content": "pregunta"},
    ]
    # Solo lo verificado: un parámetro no soportado tumbaría toda la pasada con un 400.
    assert set(cuerpo) == {"model", "messages", "temperature"}
    assert cuerpo["temperature"] == 0


@respx.mock
def test_completar_devuelve_el_texto_y_el_uso() -> None:
    respx.post(ENDPOINT).mock(return_value=_ok("hola"))

    completado = _modelo().completar("s", "u")

    assert completado.texto == "hola"
    assert completado.uso == Uso(tokens_entrada=120, tokens_salida=30)


@respx.mock
def test_quita_un_bloque_de_pensamiento_incrustado_en_el_contenido() -> None:
    respx.post(ENDPOINT).mock(return_value=_ok('<think>dudo...\nmmm</think>\n{"a": 1}'))

    assert _modelo().completar("s", "u").texto == '{"a": 1}'


@respx.mock
@pytest.mark.parametrize("cuerpo", [{"choices": []}, {}, None])
def test_sin_contenido_devuelve_texto_vacio_en_vez_de_romper_la_pasada(
    cuerpo: dict[str, object] | None,
) -> None:
    respuesta = _ok(None) if cuerpo is None else httpx.Response(200, json=cuerpo)
    respx.post(ENDPOINT).mock(return_value=respuesta)

    assert _modelo().completar("s", "u").texto == ""


@respx.mock
def test_reintenta_ante_429_respetando_retry_after() -> None:
    ruta = respx.post(ENDPOINT).mock(
        side_effect=[httpx.Response(429, headers={"retry-after": "3"}), _ok()]
    )
    modelo = _modelo()

    modelo.completar("s", "u")

    assert ruta.call_count == 2
    assert modelo.esperas == [3.0]  # type: ignore[attr-defined]


@respx.mock
def test_un_error_del_cliente_no_se_reintenta() -> None:
    ruta = respx.post(ENDPOINT).mock(return_value=httpx.Response(402))

    with pytest.raises(httpx.HTTPStatusError):
        _modelo().completar("s", "u")

    assert ruta.call_count == 1


def test_sin_clave_no_se_puede_construir() -> None:
    with pytest.raises(ValueError, match="DEEPINFRA_API_KEY"):
        DeepInfraModelo(_settings(deepinfra_api_key=None))


def test_las_tarifas_conocidas_y_una_desconocida_que_no_se_adivina() -> None:
    assert tarifa_de(MODELO_POR_DEFECTO) == Tarifa(entrada_usd_mtok=0.06, salida_usd_mtok=0.18)
    with pytest.raises(ValueError, match="no hay tarifa conocida"):
        tarifa_de("deepseek-ai/inventado")
