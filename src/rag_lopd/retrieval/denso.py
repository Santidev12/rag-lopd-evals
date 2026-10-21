"""Recuperador denso: similitud coseno sobre un índice de embeddings ya calculado.

Separado a propósito de cómo se generan los vectores (`embeddings.py`, `indice_denso.py`): este
motor solo sabe buscar sobre un array ya construido. Cumple el mismo contrato `Recuperador` que
`RecuperadorBM25`, así que `evaluar_recall` lo mide exactamente igual sin cambiar una línea.
"""

from __future__ import annotations

import numpy as np

from rag_lopd.model import UnidadIndexable
from rag_lopd.retrieval.embeddings import Embebedor
from rag_lopd.retrieval.modelo import Resultado


class RecuperadorDenso:
    """`vectores` debe estar normalizado a norma 1 por fila (lo que hace `indice_denso.construir`)
    y en el mismo orden que `unidades`, fila a fila."""

    def __init__(
        self, unidades: list[UnidadIndexable], vectores: np.ndarray, embebedor: Embebedor
    ) -> None:
        if len(unidades) != vectores.shape[0]:
            raise ValueError(
                f"{len(unidades)} unidades pero {vectores.shape[0]} vectores: "
                "el índice denso no está alineado con el corpus cargado."
            )
        self._unidades = unidades
        self._vectores = vectores
        self._embebedor = embebedor

    def buscar(self, consulta: str, *, k: int = 10) -> list[Resultado]:
        vector_consulta = np.array(self._embebedor.embeber([consulta])[0], dtype=np.float32)
        vector_consulta = vector_consulta / np.linalg.norm(vector_consulta)

        puntuaciones = self._vectores @ vector_consulta
        orden = np.argsort(-puntuaciones)[:k]
        return [
            Resultado(
                id=self._unidades[i].id,
                score=float(puntuaciones[i]),
                texto=self._unidades[i].texto,
                ruta=self._unidades[i].ruta,
            )
            for i in orden
        ]
