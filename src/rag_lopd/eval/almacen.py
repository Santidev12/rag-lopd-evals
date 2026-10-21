"""Lectura y escritura del eval set en JSONL.

JSONL y no JSON a propósito: una pregunta por línea hace que el diff de git sea legible. Cuando
Santiago acepte o descarte una candidata, el commit enseñará exactamente qué cambió en cuál.
"""

from __future__ import annotations

from pathlib import Path

from rag_lopd.eval.modelo import EvalSet, Pregunta


def leer(ruta: Path, *, version: str | None = None) -> EvalSet:
    crudas = ruta.read_text(encoding="utf-8").splitlines()
    lineas = [linea for linea in crudas if linea.strip()]
    return EvalSet(
        version=version or ruta.stem,
        preguntas=tuple(Pregunta.model_validate_json(linea) for linea in lineas),
    )


def escribir(eval_set: EvalSet, ruta: Path) -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    lineas = [p.model_dump_json() for p in eval_set.preguntas]
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return ruta
