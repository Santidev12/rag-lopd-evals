"""Validación del eval set contra el corpus real.

El modelo comprueba que una pregunta es coherente consigo misma. Esto comprueba lo otro: que las
fuentes que declara existen de verdad. Es la defensa contra el fallo más silencioso de todos —
una fuente inventada o mal tecleada hace que el recall de esa pregunta sea 0 para siempre, y el
sistema parezca peor de lo que es sin que nadie entienda por qué.
"""

from __future__ import annotations

from pathlib import Path

from rag_lopd.almacen import cargar
from rag_lopd.eval.modelo import EvalSet
from rag_lopd.model import Norma


def identificadores_del_corpus(normas: list[Norma]) -> set[str]:
    return {str(u.id) for n in normas for u in n.unidades_vigentes()}


def cargar_corpus(directorio: Path, slugs: tuple[str, ...] = ("rgpd", "lopdgdd")) -> list[Norma]:
    return [cargar(slug, directorio) for slug in slugs]


def fuentes_inexistentes(eval_set: EvalSet, corpus: set[str]) -> dict[str, list[str]]:
    """Por cada pregunta, las fuentes que no existen en el corpus. Vacío si todo cuadra."""
    fallos: dict[str, list[str]] = {}
    for pregunta in eval_set.preguntas:
        huerfanas = [str(f) for f in pregunta.fuente if str(f) not in corpus]
        if huerfanas:
            fallos[pregunta.id] = huerfanas
    return fallos
