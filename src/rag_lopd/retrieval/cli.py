"""CLI del retrieval: medir el baseline BM25 contra el eval set, y consultar a mano.

Separado del `eval.cli` a propósito: aquello valida y tabula el eval set en sí mismo, esto lo usa
para medir un motor de recuperación. Cuando exista un segundo motor (denso, híbrido), añade su
propio flag aquí — el contrato de `Recuperador` no cambia.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from rag_lopd.config import get_settings
from rag_lopd.eval.almacen import leer as leer_eval_set
from rag_lopd.retrieval.bm25 import RecuperadorBM25
from rag_lopd.retrieval.corpus import cargar_unidades
from rag_lopd.retrieval.evaluacion import evaluar_recall

app = typer.Typer(help="Recuperación: el baseline BM25 y su medida contra el eval set.")

_EVAL_SET_POR_DEFECTO = Path("eval/candidatas-v0.jsonl")


@app.command()
def evaluar(
    eval_set_path: Annotated[Path, typer.Option("--eval-set")] = _EVAL_SET_POR_DEFECTO,
    k: Annotated[int, typer.Option("--k", help="Cuántos resultados cuentan como top-k.")] = 10,
) -> None:
    """Recall@k de BM25 sobre las preguntas factual y cruzada, con y sin ruta jerárquica."""
    settings = get_settings()
    unidades = cargar_unidades(settings.processed_dir)
    if not unidades:
        typer.secho(
            f"No hay unidades indexadas en {settings.processed_dir}. "
            "Ejecuta antes 'rag-lopd ingest'.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    eval_set = leer_eval_set(eval_set_path)

    typer.echo(f"{len(unidades)} unidades indexadas · eval set: {eval_set_path}")
    typer.echo("")
    for con_ruta in (True, False):
        recuperador = RecuperadorBM25(unidades, con_ruta=con_ruta)
        resultado = evaluar_recall(recuperador, eval_set, k=k)
        etiqueta = "con ruta jerárquica" if con_ruta else "sin ruta jerárquica"
        typer.echo(
            f"BM25 ({etiqueta}) @k={k}: "
            f"{resultado.aciertos}/{resultado.total} = {resultado.recall:.1%}"
        )
        if resultado.fallos:
            typer.echo(f"  falladas: {', '.join(resultado.fallos)}")


@app.command()
def buscar(
    consulta: Annotated[str, typer.Argument(help="La consulta en lenguaje natural.")],
    k: Annotated[int, typer.Option("--k")] = 5,
    sin_ruta: Annotated[bool, typer.Option("--sin-ruta")] = False,
) -> None:
    """Busca a mano una consulta y enseña las k unidades más relevantes."""
    settings = get_settings()
    unidades = cargar_unidades(settings.processed_dir)
    if not unidades:
        typer.secho(
            f"No hay unidades indexadas en {settings.processed_dir}. "
            "Ejecuta antes 'rag-lopd ingest'.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    recuperador = RecuperadorBM25(unidades, con_ruta=not sin_ruta)
    for resultado in recuperador.buscar(consulta, k=k):
        typer.echo(f"[{resultado.score:6.2f}] {resultado.id} — {resultado.ruta}")
