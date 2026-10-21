"""Mide un recuperador contra el eval set: ¿aparece la fuente esperada entre las top-k?

Solo entran las preguntas `factual` y `cruzada`: son las únicas con una fuente esperada que
recuperar. Las `fuera_de_corpus` y `trampa` no tienen unidad que buscar por definición, y las
`temporal` piden a veces la versión histórica de un artículo — que no vive en el índice, porque
solo se indexan las unidades vigentes (`Norma.unidades_vigentes`). Medirlas aquí sin una política
de abstención delante daría un recall que no significa lo que parece.

Para una `cruzada`, contar acierto solo cuando aparecen **todas** sus fuentes es la medida
honesta: la mitad de las fuentes de una pregunta cruzada no basta para responderla.

Hay dos niveles a los que medir, y no dan el mismo número:

- `apartado`: ¿recuperamos la unidad indexable exacta? Es la medida estricta.
- `articulo`: ¿recuperamos *algo* del mismo artículo? Por el ADR 0001 (small-to-big), al
  generador no se le entrega el apartado suelto, se le entrega el artículo entero. Si se recupera
  el apartado 1 de un artículo y la fuente esperada es su apartado 5, el generador ve el 5 igual
  — el fallo a nivel apartado no es un fallo real de cara al sistema. `articulo` es la medida que
  de verdad predice si el generador va a tener el texto que necesita delante.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from rag_lopd.eval.modelo import EvalSet, Pregunta, TipoPregunta
from rag_lopd.model import Identificador
from rag_lopd.retrieval.modelo import Recuperador, Resultado

_TIPOS_CON_FUENTE = (TipoPregunta.FACTUAL, TipoPregunta.CRUZADA)

Nivel = Literal["apartado", "articulo"]


@dataclass(frozen=True)
class ResultadoEvaluacion:
    k: int
    nivel: Nivel
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


def _identificadores(fuente: tuple[Identificador, ...], nivel: Nivel) -> set[str]:
    if nivel == "articulo":
        return {str(f.unidad_de_contexto) for f in fuente}
    return {str(f) for f in fuente}


def _identificadores_recuperados(resultados: list[Resultado], nivel: Nivel) -> set[str]:
    if nivel == "articulo":
        return {str(r.id.unidad_de_contexto) for r in resultados}
    return {str(r.id) for r in resultados}


def evaluar_recall(
    recuperador: Recuperador, eval_set: EvalSet, *, k: int = 10, nivel: Nivel = "apartado"
) -> ResultadoEvaluacion:
    preguntas = preguntas_evaluables(eval_set)
    fallos: list[str] = []
    aciertos = 0
    for p in preguntas:
        recuperados = _identificadores_recuperados(recuperador.buscar(p.pregunta, k=k), nivel)
        esperadas = _identificadores(p.fuente, nivel)
        if esperadas <= recuperados:
            aciertos += 1
        else:
            fallos.append(p.id)
    return ResultadoEvaluacion(
        k=k, nivel=nivel, total=len(preguntas), aciertos=aciertos, fallos=tuple(fallos)
    )
