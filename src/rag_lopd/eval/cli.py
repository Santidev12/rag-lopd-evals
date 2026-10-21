"""Subcomandos `rag-lopd eval`."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from rag_lopd.config import get_settings
from rag_lopd.eval.almacen import leer
from rag_lopd.eval.modelo import REPARTO_OBJETIVO, Estado, EvalSet, TipoPregunta
from rag_lopd.eval.validacion import (
    cargar_corpus,
    fuentes_inexistentes,
    identificadores_del_corpus,
)

app = typer.Typer(help="El eval set: validarlo, ver su estado y exportarlo para revisión.")

RUTA_POR_DEFECTO = Path("eval/candidatas-v0.jsonl")
RUTA_TABLA = Path("docs/eval-candidatas.md")


@app.command()
def validar(ruta: Annotated[Path, typer.Argument()] = RUTA_POR_DEFECTO) -> None:
    """Comprueba las reglas del eval set y que todas sus fuentes existen en el corpus."""
    eval_set = leer(ruta)
    typer.echo(f"{len(eval_set.preguntas)} preguntas leídas de {ruta}")

    settings = get_settings()
    if not (settings.processed_dir / "rgpd.json").exists():
        typer.secho(
            "  Sin corpus en disco: no puedo comprobar las fuentes. Ejecuta `rag-lopd ingest`.",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=0)

    huerfanas = fuentes_inexistentes(
        eval_set, identificadores_del_corpus(cargar_corpus(settings.processed_dir))
    )
    if huerfanas:
        for identificador, fuentes in huerfanas.items():
            typer.secho(f"  {identificador}: fuentes inexistentes {fuentes}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.secho(
        f"  las {len(eval_set.fuentes())} fuentes existen en el corpus", fg=typer.colors.GREEN
    )


@app.command()
def stats(ruta: Annotated[Path, typer.Argument()] = RUTA_POR_DEFECTO) -> None:
    """Reparto por tipo y estado de la revisión."""
    eval_set = leer(ruta)
    reparto = eval_set.reparto()
    aceptadas = eval_set.reparto(solo_aceptadas=True)

    typer.echo(f"{ruta} — {len(eval_set.preguntas)} preguntas")
    typer.echo(f"{'tipo':<18}{'total':>7}{'aceptadas':>11}{'objetivo':>10}{'faltan':>8}")
    for tipo in TipoPregunta:
        faltan = REPARTO_OBJETIVO[tipo] - aceptadas[tipo]
        typer.echo(
            f"{tipo.value:<18}{reparto[tipo]:>7}{aceptadas[tipo]:>11}"
            f"{REPARTO_OBJETIVO[tipo]:>10}{faltan:>8}"
        )
    for estado in Estado:
        cuantas = sum(1 for p in eval_set.preguntas if p.estado is estado)
        typer.echo(f"  {estado.value}: {cuantas}")


@app.command()
def tabla(
    ruta: Annotated[Path, typer.Argument()] = RUTA_POR_DEFECTO,
    destino: Annotated[Path, typer.Option("--destino", "-d")] = RUTA_TABLA,
) -> None:
    """Exporta el eval set como tabla markdown, para revisarlo cómodamente."""
    eval_set = leer(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(_markdown(eval_set), encoding="utf-8")
    typer.echo(f"-> {destino}")


def _markdown(eval_set: EvalSet) -> str:
    lineas = [
        f"# Candidatas del eval set — `{eval_set.version}`",
        "",
        "Generadas leyendo el corpus normalizado y **pendientes de revisión humana**. Marca cada",
        "una en el `.jsonl` poniendo `estado` a `aceptada` o `descartada`; si la descartas,",
        "deja el motivo en `notas`.",
        "Por qué se descartó una pregunta es material del README.",
        "",
    ]
    for tipo in TipoPregunta:
        deste = [p for p in eval_set.preguntas if p.tipo is tipo]
        if not deste:
            continue
        lineas += [
            f"## {tipo.value} ({len(deste)})",
            "",
            "| id | pregunta | respuesta esperada | fuente | notas |",
            "| --- | --- | --- | --- | --- |",
        ]
        for p in deste:
            fuente = "<br>".join(f"`{f}`" for f in p.fuente) or "—"
            lineas.append(
                f"| `{p.id}` | {p.pregunta} | {p.respuesta} | {fuente} | {p.notas or ''} |"
            )
        lineas.append("")
    return "\n".join(lineas)
