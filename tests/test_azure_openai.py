"""Tests del cliente de Azure OpenAI: la llamada HTTP está mockeada con respx y el token es de
mentira. Nada aquí sale a internet, pide credenciales ni gasta un céntimo.

Las formas del error de filtro de contenido (400 con `content_filter`, `finish_reason` en el 200)
son las que describe la investigación del ticket de filtros, **sin verificar** contra el servicio:
se comprueban con una llamada real al desplegar."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from rag_lopd.config import Settings
from rag_lopd.generacion.azure_openai import AzureOpenAIModelo, proveedor_de_token_entra
from rag_lopd.generacion.modelo import Tarifa, Uso

ENDPOINT = "https://mi-recurso.openai.azure.com"
DESPLIEGUE = "gpt-4-1-mini"
URL = f"{ENDPOINT}/openai/deployments/{DESPLIEGUE}/chat/completions"
TARIFA = Tarifa(entrada_usd_mtok=1.0, salida_usd_mtok=2.0)


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "azure_openai_endpoint": ENDPOINT,
        "azure_openai_deployment": DESPLIEGUE,
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type,call-arg]


def _ok(contenido: str | None = '{"sin_respuesta": true}', finish: str = "stop") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [
                {"message": {"role": "assistant", "content": contenido}, "finish_reason": finish}
            ],
            "usage": {"prompt_tokens": 5_600, "completion_tokens": 110, "total_tokens": 5_710},
        },
    )


def _filtro_en_el_prompt() -> httpx.Response:
    return httpx.Response(
        400,
        json={
            "error": {
                "code": "content_filter",
                "message": "The response was filtered due to the prompt triggering policy.",
                "innererror": {"code": "ResponsibleAIPolicyViolation"},
            }
        },
    )


def _modelo(**kwargs: object) -> AzureOpenAIModelo:
    esperas: list[float] = []
    llamadas_al_token: list[int] = []

    def token() -> str:
        llamadas_al_token.append(1)
        return "token-de-prueba"

    modelo = AzureOpenAIModelo(
        kwargs.pop("settings", _settings()),  # type: ignore[arg-type]
        tarifa=TARIFA,
        token_provider=token,
        esperar=esperas.append,
        **kwargs,  # type: ignore[arg-type]
    )
    modelo.esperas = esperas  # type: ignore[attr-defined]
    modelo.llamadas_al_token = llamadas_al_token  # type: ignore[attr-defined]
    return modelo


@respx.mock
def test_completar_llama_al_despliegue_con_el_token_y_pide_json_sin_temperatura() -> None:
    ruta = respx.post(URL).mock(return_value=_ok())

    _modelo().completar("instrucción", "pregunta")

    peticion = ruta.calls.last.request
    assert peticion.url.params["api-version"] == "2024-10-21"
    assert peticion.headers["authorization"] == "Bearer token-de-prueba"
    cuerpo = json.loads(peticion.content)
    assert cuerpo["messages"] == [
        {"role": "system", "content": "instrucción"},
        {"role": "user", "content": "pregunta"},
    ]
    assert cuerpo["temperature"] == 0
    assert cuerpo["response_format"] == {"type": "json_object"}


@respx.mock
def test_completar_devuelve_el_texto_y_los_tokens() -> None:
    respx.post(URL).mock(return_value=_ok('{"sin_respuesta": true}'))

    completado = _modelo().completar("s", "u")

    assert completado.texto == '{"sin_respuesta": true}'
    assert completado.uso == Uso(tokens_entrada=5_600, tokens_salida=110)
    assert completado.bloqueo is None


@respx.mock
def test_el_endpoint_con_barra_final_y_otra_version_de_api_se_respetan() -> None:
    ruta = respx.post(URL).mock(return_value=_ok())
    settings = _settings(
        azure_openai_endpoint=f"{ENDPOINT}/", azure_openai_api_version="2025-01-01"
    )

    _modelo(settings=settings).completar("s", "u")

    assert ruta.calls.last.request.url.params["api-version"] == "2025-01-01"


@respx.mock
def test_el_token_se_pide_en_cada_intento_porque_caduca() -> None:
    respx.post(URL).mock(side_effect=[httpx.Response(429), _ok()])
    modelo = _modelo()

    modelo.completar("s", "u")

    assert len(modelo.llamadas_al_token) == 2  # type: ignore[attr-defined]


@respx.mock
def test_reintenta_ante_un_tiempo_de_espera_agotado() -> None:
    ruta = respx.post(URL).mock(side_effect=[httpx.ReadTimeout("lento"), _ok()])

    _modelo().completar("s", "u")

    assert ruta.call_count == 2


# --- el filtro de contenido ---------------------------------------------------------------------


@respx.mock
def test_un_400_de_filtro_en_el_prompt_es_un_bloqueo_y_no_un_error_ni_se_reintenta() -> None:
    ruta = respx.post(URL).mock(return_value=_filtro_en_el_prompt())

    completado = _modelo().completar("s", "u")

    assert completado.bloqueo == "prompt"
    assert completado.texto == ""
    assert completado.uso == Uso()
    assert ruta.call_count == 1


@respx.mock
def test_un_200_con_finish_reason_de_filtro_es_un_bloqueo_de_la_salida_y_cuenta_los_tokens() -> (
    None
):
    respx.post(URL).mock(return_value=_ok(contenido=None, finish="content_filter"))

    completado = _modelo().completar("s", "u")

    assert completado.bloqueo == "salida"
    assert completado.uso == Uso(tokens_entrada=5_600, tokens_salida=110)


@respx.mock
def test_otro_400_sigue_siendo_un_error() -> None:
    respx.post(URL).mock(
        return_value=httpx.Response(400, json={"error": {"code": "invalid_request_error"}})
    )

    with pytest.raises(httpx.HTTPStatusError):
        _modelo().completar("s", "u")


@respx.mock
def test_un_400_sin_cuerpo_json_sigue_siendo_un_error() -> None:
    respx.post(URL).mock(return_value=httpx.Response(400, text="Bad Request"))

    with pytest.raises(httpx.HTTPStatusError):
        _modelo().completar("s", "u")


@respx.mock
def test_si_no_hay_token_el_error_dice_que_hacer_y_no_llama_al_servicio() -> None:
    ruta = respx.post(URL).mock(return_value=_ok())

    def sin_sesion() -> str:
        raise RuntimeError("no hay sesión")

    modelo = AzureOpenAIModelo(_settings(), tarifa=TARIFA, token_provider=sin_sesion)

    with pytest.raises(ValueError, match="az login"):
        modelo.completar("s", "u")
    assert ruta.call_count == 0


# --- configuración ------------------------------------------------------------------------------


def test_sin_endpoint_no_se_puede_construir() -> None:
    with pytest.raises(ValueError, match="AZURE_OPENAI_ENDPOINT"):
        AzureOpenAIModelo(
            _settings(azure_openai_endpoint=None), tarifa=TARIFA, token_provider=lambda: "t"
        )


def test_sin_despliegue_no_se_puede_construir() -> None:
    with pytest.raises(ValueError, match="AZURE_OPENAI_DEPLOYMENT"):
        AzureOpenAIModelo(
            _settings(azure_openai_deployment=None), tarifa=TARIFA, token_provider=lambda: "t"
        )


def test_el_despliegue_pasado_explicito_manda_sobre_el_de_la_configuracion() -> None:
    modelo = AzureOpenAIModelo(
        _settings(azure_openai_deployment=None),
        despliegue="otro",
        tarifa=TARIFA,
        token_provider=lambda: "t",
    )

    assert modelo.nombre == "otro"


def test_el_coste_sale_de_la_tarifa_explicita() -> None:
    modelo = _modelo()

    assert modelo.tarifa.coste_usd(Uso(tokens_entrada=1_000_000, tokens_salida=500_000)) == 2.0


def test_el_proveedor_de_token_por_defecto_se_construye_sin_pedir_nada() -> None:
    # Construirlo no debe salir a la red: el token solo se pide cuando se llama al proveedor.
    assert callable(proveedor_de_token_entra())
