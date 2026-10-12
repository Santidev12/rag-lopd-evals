"""Pregunta + artículos recuperados -> `Respuesta`: la política de abstención, ejecutada.

Tres controles, en este orden, y los tres son medibles por separado:

1. El modelo puede declarar `sin_respuesta` (la vía de abstención explícita).
2. Si responde, tiene que citar, y cada cita se valida contra los artículos que *de verdad* se le
   dieron. Una cita inventada se descarta; una respuesta sin ninguna cita válida no se puede
   comprobar contra la fuente, así que cuenta como abstención.
3. Si no devuelve el JSON pedido, es un fallo de formato y se registra como tal: no se disfraza
   de abstención ni de respuesta.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, ValidationError

from rag_lopd.generacion.modelo import Contexto, Estado, ModeloDeLenguaje, Respuesta
from rag_lopd.generacion.prompt import PROMPT_POR_DEFECTO, Prompt
from rag_lopd.model import Identificador

_VALLA_CODIGO = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


class _Salida(BaseModel):
    """El JSON que se le pide al modelo. Privado: lo que sale hacia fuera es `Respuesta`."""

    sin_respuesta: bool
    respuesta: str = ""
    citas: list[str] = Field(default_factory=list)


def _sin_valla_de_codigo(texto: str) -> str:
    """Algunos modelos envuelven el JSON en ```json ... ``` aunque se les pida lo contrario."""
    encaje = _VALLA_CODIGO.match(texto)
    return encaje.group(1) if encaje else texto.strip()


def _validar_citas(
    crudas: list[str], contextos: list[Contexto]
) -> tuple[tuple[Identificador, ...], tuple[str, ...]]:
    """Separa las citas que apuntan a un artículo del contexto de las que no.

    Se cita a nivel artículo (lo que ve el modelo); si cita un apartado ("rgpd:art-33.1") se
    acepta y se reduce a su artículo, porque el contexto entregado es el artículo entero.
    """
    permitidos = {str(c.id) for c in contextos}
    validas: list[Identificador] = []
    descartadas: list[str] = []
    for cruda in crudas:
        try:
            articulo = Identificador.parse(cruda.strip()).unidad_de_contexto
        except ValueError:
            descartadas.append(cruda)
            continue
        if str(articulo) not in permitidos:
            descartadas.append(cruda)
        elif articulo not in validas:
            validas.append(articulo)
    return tuple(validas), tuple(descartadas)


def responder(
    modelo: ModeloDeLenguaje,
    pregunta: str,
    contextos: list[Contexto],
    prompt: Prompt = PROMPT_POR_DEFECTO,
) -> Respuesta:
    completado = modelo.completar(prompt.sistema, prompt.usuario(pregunta, contextos))
    uso = completado.uso

    try:
        salida = _Salida.model_validate_json(_sin_valla_de_codigo(completado.texto))
    except ValidationError:
        return Respuesta(estado=Estado.SALIDA_INVALIDA, texto=completado.texto, uso=uso)

    if salida.sin_respuesta:
        return Respuesta(estado=Estado.ABSTIENE, uso=uso)

    if not salida.respuesta.strip():
        return Respuesta(estado=Estado.SALIDA_INVALIDA, texto=completado.texto, uso=uso)

    validas, descartadas = _validar_citas(salida.citas, contextos)
    estado = Estado.RESPONDE if validas else Estado.SIN_CITA_VALIDA
    return Respuesta(
        estado=estado,
        texto=salida.respuesta,
        citas=validas,
        citas_descartadas=descartadas,
        uso=uso,
    )
