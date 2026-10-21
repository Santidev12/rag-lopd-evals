"""Diagnóstico para diseñar la política de abstención (ticket 12).

No decide nada por sí solo: mide si el score de recuperación separa las preguntas que sí tienen
respuesta en el corpus de las que no (`Pregunta.debe_abstenerse` — `fuera_de_corpus` y `trampa`).
A diferencia de `evaluacion.evaluar_recall`, esto corre sobre las 50 preguntas aceptadas, no solo
sobre las 27 factual/cruzada: aquí la pregunta no es si se encuentra la fuente correcta, es si el
*score* ya distingue "hay algo que encontrar" de "no hay nada que encontrar".
"""

from __future__ import annotations

from dataclasses import dataclass

from rag_lopd.eval.modelo import EvalSet, Pregunta
from rag_lopd.retrieval.modelo import Recuperador


@dataclass(frozen=True)
class Puntuacion:
    """El score de recuperación para una pregunta, con su etiqueta real de abstención."""

    pregunta: Pregunta
    top1: float
    media_top_k: float

    @property
    def debe_abstenerse(self) -> bool:
        return self.pregunta.debe_abstenerse


def puntuaciones(recuperador: Recuperador, eval_set: EvalSet, *, k: int = 10) -> list[Puntuacion]:
    """El score del mejor resultado y la media del top-k, para cada pregunta aceptada."""
    resultados: list[Puntuacion] = []
    for pregunta in eval_set.aceptadas():
        encontrados = recuperador.buscar(pregunta.pregunta, k=k)
        if not encontrados:
            resultados.append(Puntuacion(pregunta=pregunta, top1=0.0, media_top_k=0.0))
            continue
        scores = [r.score for r in encontrados]
        resultados.append(
            Puntuacion(pregunta=pregunta, top1=scores[0], media_top_k=sum(scores) / len(scores))
        )
    return resultados
