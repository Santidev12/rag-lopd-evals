"""Azure OpenAI como `ModeloDeLenguaje`, autenticado con Entra ID: sin ninguna clave.

El mismo código vale en tu máquina y desplegado. En local, `DefaultAzureCredential` usa la sesión de
`az login`; en Azure (Container Apps) usará la **identidad gestionada** del servicio, sin cambiar
una línea. Por eso no hay `AZURE_OPENAI_API_KEY`: no hay secreto que guardar, rotar ni filtrar.

Requisito fácil de olvidar: ser propietario de la suscripción **no basta**. Entra ID exige el rol de
datos *Cognitive Services OpenAI User* sobre el recurso, asignado a quien llama.

Como con Gemini, solo se pide `temperature: 0` y JSON simple (`response_format: json_object`), sin
esquema: el formato lo valida `responder`. Así el único cambio frente a la línea base es el modelo.

**El filtro de contenido** no es un error del modelo. Las dos formas que se reconocen vienen de la
investigación del ticket de filtros y están **sin verificar** contra el servicio real:

- un 400 con `error.code == "content_filter"` (el prompt activó una política): no se generó nada;
- un 200 con `finish_reason == "content_filter"`: se generó y se cortó la salida.

En ambos casos se devuelve un `Completado` con `bloqueo` y `responder` lo convierte en
`Estado.BLOQUEADO`. Cualquier otro 400 sigue siendo un error.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Generator
from typing import Any

import httpx

from rag_lopd.config import Settings
from rag_lopd.generacion.modelo import Completado, Tarifa, Uso
from rag_lopd.generacion.reintentos import post_con_reintentos

AMBITO = "https://cognitiveservices.azure.com/.default"
"""El ámbito de Entra ID para los servicios cognitivos de Azure (también Azure OpenAI)."""

_FILTRO = "content_filter"


class _AuthBearer(httpx.Auth):
    """Pone el token en **cada** petición, reintentos incluidos: el token caduca (~1 h), y una
    pasada larga no puede llevar el mismo de principio a fin."""

    def __init__(self, token_provider: Callable[[], str]) -> None:
        self._token_provider = token_provider

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        try:
            token = self._token_provider()
        except Exception as error:
            # azure-identity lanza excepciones propias según el motivo; aquí solo importa decirle a
            # quien lo ejecuta qué hacer, sin que la CLI tenga que conocerlas todas.
            raise ValueError(
                f"no se pudo obtener el token de Entra ID ({type(error).__name__}). "
                "¿Has hecho `az login`? ¿Tienes asignado el rol «Cognitive Services OpenAI User» "
                "sobre el recurso?"
            ) from error
        request.headers["Authorization"] = f"Bearer {token}"
        yield request


def proveedor_de_token_entra() -> Callable[[], str]:
    """El proveedor de tokens de verdad. Construirlo no sale a la red: el token solo se pide al
    llamarlo.

    Se importa `azure.identity` aquí dentro y no arriba para que importar el módulo no cueste nada y
    los tests y las demás partes del proyecto no dependan de él."""
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider

    return get_bearer_token_provider(DefaultAzureCredential(), AMBITO)


class AzureOpenAIModelo:
    """Una llamada, un texto. Mismos reintentos que Gemini ante 429, fallo del servidor o timeout.

    La `tarifa` es obligatoria y explícita: el precio de un despliegue (regional, Data Zone, global)
    cambia, y una tarifa adivinada convertiría el coste del README en un invento."""

    def __init__(
        self,
        settings: Settings,
        *,
        tarifa: Tarifa,
        despliegue: str | None = None,
        token_provider: Callable[[], str] | None = None,
        esperar: Callable[[float], None] = time.sleep,
    ) -> None:
        if not settings.azure_openai_endpoint:
            raise ValueError(
                "falta AZURE_OPENAI_ENDPOINT en .env (la URL del recurso, p. ej. "
                "https://mi-recurso.openai.azure.com): sin ella no se puede llamar a Azure OpenAI."
            )
        nombre = despliegue or settings.azure_openai_deployment
        if not nombre:
            raise ValueError(
                "falta AZURE_OPENAI_DEPLOYMENT en .env (el nombre del despliegue del modelo) o "
                "pasarlo con --despliegue."
            )
        self.nombre = nombre
        self.tarifa = tarifa
        self._esperar = esperar
        self._url = (
            f"{settings.azure_openai_endpoint.rstrip('/')}/openai/deployments/{nombre}"
            f"/chat/completions?api-version={settings.azure_openai_api_version}"
        )
        self._cliente = httpx.Client(
            auth=_AuthBearer(token_provider or proveedor_de_token_entra()),
            timeout=settings.http_timeout_seconds,
        )

    def completar(self, sistema: str, usuario: str) -> Completado:
        cuerpo = {
            "messages": [
                {"role": "system", "content": sistema},
                {"role": "user", "content": usuario},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        try:
            respuesta = post_con_reintentos(self._cliente, self._url, cuerpo, esperar=self._esperar)
        except httpx.HTTPStatusError as error:
            if _es_bloqueo_del_prompt(error.response):
                return Completado(texto="", uso=Uso(), bloqueo="prompt")
            raise
        datos = respuesta.json()
        opciones = datos.get("choices") or [{}]
        opcion = opciones[0]
        texto = (opcion.get("message") or {}).get("content") or ""
        uso = _uso(datos)
        if opcion.get("finish_reason") == _FILTRO:
            return Completado(texto=texto, uso=uso, bloqueo="salida")
        return Completado(texto=texto, uso=uso)

    def close(self) -> None:
        self._cliente.close()

    def __enter__(self) -> AzureOpenAIModelo:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()


def _es_bloqueo_del_prompt(respuesta: httpx.Response) -> bool:
    """¿Es este error el filtro de contenido y no un fallo de verdad? Solo un 400 con el código del
    filtro (o la violación de política anidada). Un cuerpo ilegible es un error normal."""
    if respuesta.status_code != 400:
        return False
    try:
        cuerpo = respuesta.json()
    except ValueError:
        return False
    error = cuerpo.get("error") if isinstance(cuerpo, dict) else None
    if not isinstance(error, dict):
        return False
    interno = error.get("innererror")
    return error.get("code") == _FILTRO or (
        isinstance(interno, dict) and interno.get("code") == "ResponsibleAIPolicyViolation"
    )


def _uso(datos: dict[str, Any]) -> Uso:
    """Tokens facturados, con la misma forma que otras APIs compatibles con OpenAI."""
    uso = datos.get("usage") or {}
    return Uso(
        tokens_entrada=int(uso.get("prompt_tokens", 0)),
        tokens_salida=int(uso.get("completion_tokens", 0)),
    )
