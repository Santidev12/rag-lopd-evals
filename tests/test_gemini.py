"""Tests del cliente de Gemini: la llamada HTTP está mockeada con respx. Nada aquí sale a internet
ni gasta un céntimo."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from rag_lopd.config import Settings
from rag_lopd.generacion.gemini import MODELO_POR_DEFECTO, URL, GeminiModelo, tarifa_de
from rag_lopd.generacion.modelo import Tarifa, Uso

ENDPOINT = URL.format(modelo=MODELO_POR_DEFECTO)


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {"google_api_key": "clave-de-prueba"}
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _ok(texto: str = '{"sin_respuesta": true}', **uso: int) -> httpx.Response:
    metadatos = {"promptTokenCount": 100, "candidatesTokenCount": 20, "totalTokenCount": 120}
    metadatos.update(uso)
    return httpx.Response(
        200,
        json={
            "candidates": [{"content": {"parts": [{"text": texto}]}, "finishReason": "STOP"}],
            "usageMetadata": metadatos,
        },
    )


def _modelo(**kwargs: object) -> GeminiModelo:
    esperas: list[float] = []
    modelo = GeminiModelo(_settings(), esperar=esperas.append, **kwargs)  # type: ignore[arg-type]
    modelo.esperas = esperas  # type: ignore[attr-defined]
    return modelo


@respx.mock
def test_completar_manda_sistema_usuario_y_pide_json_sin_temperatura() -> None:
    ruta = respx.post(ENDPOINT).mock(return_value=_ok())

    _modelo().completar("instrucción", "pregunta")

    peticion = ruta.calls.last.request
    cuerpo = json.loads(peticion.content)
    assert peticion.headers["x-goog-api-key"] == "clave-de-prueba"
    assert cuerpo["systemInstruction"]["parts"][0]["text"] == "instrucción"
    assert cuerpo["contents"] == [{"role": "user", "parts": [{"text": "pregunta"}]}]
    assert cuerpo["generationConfig"] == {"temperature": 0, "responseMimeType": "application/json"}


@respx.mock
def test_completar_devuelve_el_texto_y_el_uso() -> None:
    respx.post(ENDPOINT).mock(return_value=_ok('{"sin_respuesta": false}'))

    completado = _modelo().completar("s", "u")

    assert completado.texto == '{"sin_respuesta": false}'
    assert completado.uso == Uso(tokens_entrada=100, tokens_salida=20)


@respx.mock
def test_los_tokens_de_razonamiento_cuentan_como_salida() -> None:
    # total (400) - entrada (100) = 300 de salida facturada, aunque el texto solo traiga 20:
    # el resto fue razonamiento interno, que se paga igual.
    respx.post(ENDPOINT).mock(return_value=_ok(totalTokenCount=400))

    assert _modelo().completar("s", "u").uso == Uso(tokens_entrada=100, tokens_salida=300)


@respx.mock
def test_ignora_las_partes_de_razonamiento_en_el_texto() -> None:
    respuesta = httpx.Response(
        200,
        json={
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "pensando...", "thought": True},
                            {"text": '{"sin_respuesta": true}'},
                        ]
                    }
                }
            ],
            "usageMetadata": {},
        },
    )
    respx.post(ENDPOINT).mock(return_value=respuesta)

    assert _modelo().completar("s", "u").texto == '{"sin_respuesta": true}'


@respx.mock
def test_sin_candidatos_devuelve_texto_vacio_en_vez_de_romper_la_pasada() -> None:
    # Una respuesta bloqueada no trae `candidates`. Romper aquí tiraría el resto de la pasada.
    respx.post(ENDPOINT).mock(
        return_value=httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})
    )

    assert _modelo().completar("s", "u").texto == ""


@respx.mock
def test_reintenta_ante_429_respetando_retry_after() -> None:
    ruta = respx.post(ENDPOINT).mock(
        side_effect=[httpx.Response(429, headers={"retry-after": "7"}), _ok()]
    )
    modelo = _modelo()

    modelo.completar("s", "u")

    assert ruta.call_count == 2
    assert modelo.esperas == [7.0]  # type: ignore[attr-defined]


@respx.mock
def test_la_espera_crece_sin_retry_after_y_tras_el_ultimo_intento_falla() -> None:
    ruta = respx.post(ENDPOINT).mock(return_value=httpx.Response(503))
    modelo = _modelo()

    with pytest.raises(httpx.HTTPStatusError):
        modelo.completar("s", "u")

    assert ruta.call_count == 5
    assert modelo.esperas == [2.0, 4.0, 8.0, 16.0]  # type: ignore[attr-defined]


@respx.mock
def test_un_error_del_cliente_no_se_reintenta() -> None:
    ruta = respx.post(ENDPOINT).mock(return_value=httpx.Response(400))

    with pytest.raises(httpx.HTTPStatusError):
        _modelo().completar("s", "u")

    assert ruta.call_count == 1


def test_sin_clave_no_se_puede_construir() -> None:
    with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
        GeminiModelo(_settings(google_api_key=None))


def test_una_tarifa_desconocida_no_se_adivina() -> None:
    with pytest.raises(ValueError, match="no hay tarifa conocida"):
        GeminiModelo(_settings(), modelo="gemini-inventado")

    # ... pero se puede pasar explícita.
    modelo = GeminiModelo(
        _settings(),
        modelo="gemini-inventado",
        tarifa=Tarifa(entrada_usd_mtok=1.0, salida_usd_mtok=2.0),
    )
    assert modelo.tarifa == Tarifa(entrada_usd_mtok=1.0, salida_usd_mtok=2.0)


def test_coste_en_dolares() -> None:
    tarifa = tarifa_de("gemini-3.5-flash-lite")  # 0,30 / 2,50 USD por millón

    assert tarifa.coste_usd(Uso(tokens_entrada=1_000_000, tokens_salida=1_000_000)) == 2.80
    assert tarifa.coste_usd(Uso(tokens_entrada=5_000, tokens_salida=300)) == pytest.approx(0.00225)
