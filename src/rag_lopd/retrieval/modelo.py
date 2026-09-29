"""El contrato de recuperación: qué entra y qué sale, sin importar el motor de dentro.

Fijar esto ahora, antes de tener un motor híbrido de verdad, es lo que permite que BM25 hoy y
denso/RRF/reranker mañana se midan con exactamente el mismo harness y el mismo eval set. Ningún
motor debería exponer nada que no esté aquí.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from rag_lopd.model import Identificador


class Resultado(BaseModel):
    """Una unidad recuperada, con su puntuación.

    La puntuación no es comparable entre motores (BM25 y coseno de un embedding no viven en la
    misma escala): sirve para ordenar dentro de un mismo motor, no para combinar a ojo.
    """

    model_config = ConfigDict(frozen=True)

    id: Identificador
    score: float
    texto: str
    ruta: str


class Recuperador(Protocol):
    """Cualquier motor de recuperación cumple esto: consulta en texto, hasta k unidades fuera,
    ordenadas de más a menos relevante según su propio criterio."""

    def buscar(self, consulta: str, *, k: int = 10) -> list[Resultado]: ...
