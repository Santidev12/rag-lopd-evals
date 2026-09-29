"""Mide un recuperador contra el eval set: ¿aparece la fuente esperada entre las top-k?

Solo entran las preguntas `factual` y `cruzada`: son las únicas con una fuente esperada que
recuperar. Las `fuera_de_corpus` y `trampa` no tienen unidad que buscar por definición, y las
`temporal` piden a veces la versión histórica de un artículo — que no vive en el índice, porque
solo se indexan las unidades vigentes (`Norma.unidades_vigentes`). Medirlas aquí sin una política
de abstención delante daría un recall que no significa lo que parece.

Para una `cruzada`, contar acierto solo cuando aparecen **todas** sus fuentes es la medida
honesta: la mitad de las fuentes de una pregunta cruzada no basta para responderla.
"""

from __future__ import annotations

from dataclasses import dataclass

from rag_lopd.eval.modelo import EvalSet, Pregunta, TipoPregunta
from rag_lopd.retrieval.modelo import Recuperador

_TIPOS_CON_FUENTE = (TipoPregunta.FACTUAL, TipoPregunta.CRUZADA)


@dataclass(frozen=True)
class ResultadoEvaluacion:
    k: int
    total: int
    aciertos: int
    fallos: tuple[str, ...]
    """Ids de las preguntas falladas, para poder mirarlas una a una en vez de solo ver el número."""

    @property
    def recall(self) -> float:
        return self.aciertos / self.total if self.total else 0.0


def preguntas_evaluables(eval_set: EvalSet) -> list[Pregunta]:
    """Las preguntas aceptadas que tienen una fuente contra la que medir recuperación."""
    return [p for p in eval_set.aceptadas() if p.tipo in _TIPOS_CON_FUENTE]


def evaluar_recall(
    recuperador: Recuperador, eval_set: EvalSet, *, k: int = 10
) -> ResultadoEvaluacion:
    preguntas = preguntas_evaluables(eval_set)
    fallos: list[str] = []
    aciertos = 0
    for p in preguntas:
        recuperados = {str(r.id) for r in recuperador.buscar(p.pregunta, k=k)}
        esperadas = {str(f) for f in p.fuente}
        if esperadas <= recuperados:
            aciertos += 1
        else:
            fallos.append(p.id)
    return ResultadoEvaluacion(k=k, total=len(preguntas), aciertos=aciertos, fallos=tuple(fallos))
