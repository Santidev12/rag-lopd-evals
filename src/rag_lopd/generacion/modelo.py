"""Los tipos de la generación y el contrato de cualquier modelo de lenguaje.

Igual que `Recuperador` para la recuperación: fijar `ModeloDeLenguaje` antes de tener tres modelos
es lo que permite medir Gemini, Claude o DeepSeek con el mismo prompt, el mismo validador de citas
y el mismo eval set. Todo lo que no está aquí es un detalle de un modelo concreto.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from rag_lopd.model import Identificador


class RedaccionAnterior(BaseModel):
    """Una versión histórica de un artículo: lo que decía entre `desde` y `hasta`."""

    model_config = ConfigDict(frozen=True)

    desde: date | None
    hasta: date
    texto: str


class Contexto(BaseModel):
    """Un artículo entero tal y como se le presenta al modelo (unidad de contexto, ADR 0001).

    `texto` es siempre la redacción **vigente**. Si el artículo se ha modificado, sus redacciones
    anteriores van aparte en `anteriores` (de la más antigua a la más reciente): quien arma el
    prompt decide si las enseña, nunca se mezclan con el texto vigente.
    """

    model_config = ConfigDict(frozen=True)

    id: Identificador
    ruta: str
    texto: str
    vigente_desde: date | None = None
    anteriores: tuple[RedaccionAnterior, ...] = ()


class Uso(BaseModel):
    """Tokens que facturó una llamada. Los de salida incluyen el razonamiento interno si el
    modelo lo tiene: es lo que se paga, no lo que se ve."""

    model_config = ConfigDict(frozen=True)

    tokens_entrada: int = 0
    tokens_salida: int = 0

    def __add__(self, otro: Uso) -> Uso:
        return Uso(
            tokens_entrada=self.tokens_entrada + otro.tokens_entrada,
            tokens_salida=self.tokens_salida + otro.tokens_salida,
        )


class Tarifa(BaseModel):
    """Dólares por millón de tokens. Vive junto al modelo porque cambia con él, no con el código."""

    model_config = ConfigDict(frozen=True)

    entrada_usd_mtok: float
    salida_usd_mtok: float

    def coste_usd(self, uso: Uso) -> float:
        return (
            uso.tokens_entrada * self.entrada_usd_mtok + uso.tokens_salida * self.salida_usd_mtok
        ) / 1_000_000


def buscar_tarifa(tarifas: dict[str, Tarifa], modelo: str) -> Tarifa:
    """La tarifa conocida de un modelo, o un error: nunca una tarifa adivinada, porque el coste
    que sale en el README sería inventado."""
    tarifa = tarifas.get(modelo)
    if tarifa is None:
        raise ValueError(
            f"no hay tarifa conocida para {modelo!r}: pásala explícita "
            f"(modelos con tarifa: {', '.join(sorted(tarifas))})."
        )
    return tarifa


class Completado(BaseModel):
    """Lo que devuelve cualquier modelo: el texto crudo y lo que costó."""

    model_config = ConfigDict(frozen=True)

    texto: str
    uso: Uso


class ModeloDeLenguaje(Protocol):
    """Cualquier modelo cumple esto: instrucción de sistema y mensaje de usuario dentro, texto y
    tokens fuera. Pedir JSON y validarlo es cosa de `responder`, no del modelo."""

    nombre: str
    tarifa: Tarifa

    def completar(self, sistema: str, usuario: str) -> Completado: ...


class Estado(StrEnum):
    """Por qué una `Respuesta` es lo que es. Distinguir las tres formas de no responder importa:
    abstenerse bien, abstenerse por no saber citar y romper el formato no se arreglan igual."""

    RESPONDE = "responde"
    ABSTIENE = "abstiene"
    """El modelo declaró `sin_respuesta`."""

    SIN_CITA_VALIDA = "sin_cita_valida"
    """El modelo quiso responder pero no citó ningún artículo de los que se le dieron. Una
    respuesta que no se puede comprobar contra la fuente cuenta como abstención."""

    SALIDA_INVALIDA = "salida_invalida"
    """El modelo no devolvió el JSON pedido. Es un fallo de formato, no una decisión."""


class Respuesta(BaseModel):
    model_config = ConfigDict(frozen=True)

    estado: Estado
    texto: str = ""
    citas: tuple[Identificador, ...] = ()
    """Solo las citas válidas: artículos que de verdad estaban en el contexto. Las inventadas se
    descartan (y se cuentan en `citas_descartadas`) en vez de colarse en la respuesta."""

    citas_descartadas: tuple[str, ...] = ()
    uso: Uso = Uso()

    @property
    def responde(self) -> bool:
        return self.estado is Estado.RESPONDE

    @property
    def se_abstiene(self) -> bool:
        """Todo lo que no es una respuesta con cita válida cuenta como callarse."""
        return not self.responde
