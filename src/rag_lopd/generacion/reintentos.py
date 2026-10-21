"""POST con reintentos para los clientes HTTP de los modelos.

Lo comparten todos los modelos que se llaman por REST (Gemini, DeepInfra): ante límite de uso
(429) o fallo transitorio del servidor se espera y se vuelve a intentar; ante cualquier otro error
se falla a la primera, porque reintentar un 400 solo gasta tiempo.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx

ESTADOS_REINTENTABLES = {429, 500, 502, 503, 504}
MAX_INTENTOS = 5
ESPERA_MAXIMA_SEGUNDOS = 60.0


def espera(respuesta: httpx.Response, intento: int) -> float:
    """`Retry-After` si el servidor lo da; si no, 2, 4, 8... segundos, con tope."""
    cabecera = respuesta.headers.get("retry-after")
    if cabecera is not None:
        try:
            return min(float(cabecera), ESPERA_MAXIMA_SEGUNDOS)
        except ValueError:
            pass
    return min(2.0**intento, ESPERA_MAXIMA_SEGUNDOS)


def post_con_reintentos(
    cliente: httpx.Client,
    url: str,
    cuerpo: dict[str, Any],
    *,
    esperar: Callable[[float], None],
) -> httpx.Response:
    for intento in range(1, MAX_INTENTOS + 1):
        respuesta = cliente.post(url, json=cuerpo)
        reintentable = respuesta.status_code in ESTADOS_REINTENTABLES
        if not reintentable or intento == MAX_INTENTOS:
            respuesta.raise_for_status()
            return respuesta
        esperar(espera(respuesta, intento))
    raise AssertionError("inalcanzable: el último intento siempre devuelve o lanza")
