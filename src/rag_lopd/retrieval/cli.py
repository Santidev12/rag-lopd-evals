"""CLI del retrieval: construir el índice denso, medir cualquier motor contra el eval set, y
consultar a mano.

Separado del `eval.cli` a propósito: aquello valida y tabula el eval set en sí mismo, esto mide
un motor de recuperación. `--motor` es el único punto donde este fichero sabe que hay más de un
motor — el contrato `Recuperador` hace el resto.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from rag_lopd.config import Settings, get_settings
from rag_lopd.eval.almacen import leer as leer_eval_set
from rag_lopd.eval.modelo import EvalSet
from rag_lopd.model import UnidadIndexable
from rag_lopd.retrieval import abstencion, indice_denso
from rag_lopd.retrieval.bm25 import RecuperadorBM25
from rag_lopd.retrieval.corpus import cargar_unidades
from rag_lopd.retrieval.denso import RecuperadorDenso
from rag_lopd.retrieval.embeddings import MODELO, EmbebedorDeepInfra
from rag_lopd.retrieval.evaluacion import Nivel, evaluar_recall

_NIVELES: tuple[Nivel, ...] = ("apartado", "articulo")
_MOTORES = ("bm25", "denso")

app = typer.Typer(help="Recuperación: los motores disponibles y su medida contra el eval set.")

_EVAL_SET_POR_DEFECTO = Path("eval/candidatas-v0.jsonl")


def _exigir_corpus(unidades: list[UnidadIndexable], settings: Settings) -> None:
    if not unidades:
        typer.secho(
            f"No hay unidades indexadas en {settings.processed_dir}. "
            "Ejecuta antes 'rag-lopd ingest'.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)


@app.command()
def indexar(
    con_ruta: Annotated[
        bool, typer.Option("--con-ruta/--sin-ruta", help="Anteponer la ruta jerárquica.")
    ] = True,
) -> None:
    """Embebe el corpus con BGE-M3 vía DeepInfra y guarda el índice denso en disco.

    Llama a una API de pago (céntimos, no euros) y tarda según el tamaño del corpus: es un paso
    deliberadamente aparte de `evaluar` o `buscar`, no algo que se repita en cada consulta.
    """
    settings = get_settings()
    unidades = cargar_unidades(settings.processed_dir)
    _exigir_corpus(unidades, settings)

    ruta_salida = indice_denso.ruta_indice(settings, con_ruta=con_ruta)
    typer.echo(f"Embebiendo {len(unidades)} unidades con {MODELO} vía DeepInfra...")
    with EmbebedorDeepInfra(settings) as embebedor:
        vectores = indice_denso.construir(unidades, embebedor, con_ruta=con_ruta)
    indice_denso.guardar(ruta_salida, unidades, vectores)
    typer.echo(f"-> {ruta_salida} ({vectores.shape[0]} vectores de dimensión {vectores.shape[1]})")


def _evaluar_bm25(unidades: list[UnidadIndexable], eval_set: EvalSet, k: int) -> None:
    for con_ruta in (True, False):
        recuperador = RecuperadorBM25(unidades, con_ruta=con_ruta)
        etiqueta = "con ruta jerárquica" if con_ruta else "sin ruta jerárquica"
        for nivel in _NIVELES:
            resultado = evaluar_recall(recuperador, eval_set, k=k, nivel=nivel)
            typer.echo(
                f"BM25 ({etiqueta}, nivel {nivel}) @k={k}: "
                f"{resultado.aciertos}/{resultado.total} = {resultado.recall:.1%}"
            )
            if resultado.fallos:
                typer.echo(f"  falladas: {', '.join(resultado.fallos)}")
        typer.echo("")


def _evaluar_denso(
    settings: Settings, unidades: list[UnidadIndexable], eval_set: EvalSet, k: int
) -> None:
    with EmbebedorDeepInfra(settings) as embebedor:
        for con_ruta in (True, False):
            ruta_indice = indice_denso.ruta_indice(settings, con_ruta=con_ruta)
            bandera = "--con-ruta" if con_ruta else "--sin-ruta"
            if not ruta_indice.exists():
                typer.secho(
                    f"No existe {ruta_indice}. Constrúyelo antes con "
                    f"'rag-lopd retrieval indexar {bandera}'.",
                    fg=typer.colors.YELLOW,
                )
                continue

            unidades_indice, vectores = indice_denso.cargar(ruta_indice, unidades)
            recuperador = RecuperadorDenso(unidades_indice, vectores, embebedor)
            etiqueta = "con ruta jerárquica" if con_ruta else "sin ruta jerárquica"
            for nivel in _NIVELES:
                resultado = evaluar_recall(recuperador, eval_set, k=k, nivel=nivel)
                typer.echo(
                    f"Denso ({etiqueta}, nivel {nivel}) @k={k}: "
                    f"{resultado.aciertos}/{resultado.total} = {resultado.recall:.1%}"
                )
                if resultado.fallos:
                    typer.echo(f"  falladas: {', '.join(resultado.fallos)}")
            typer.echo("")


@app.command()
def evaluar(
    eval_set_path: Annotated[Path, typer.Option("--eval-set")] = _EVAL_SET_POR_DEFECTO,
    k: Annotated[int, typer.Option("--k", help="Cuántos resultados cuentan como top-k.")] = 10,
    motor: Annotated[str, typer.Option("--motor", help="bm25 o denso.")] = "bm25",
) -> None:
    """Recall@k sobre las preguntas factual y cruzada, a nivel apartado y a nivel artículo."""
    if motor not in _MOTORES:
        typer.secho(
            f"motor desconocido: {motor!r}. Usa {' o '.join(_MOTORES)}.", fg=typer.colors.RED
        )
        raise typer.Exit(code=1)

    settings = get_settings()
    unidades = cargar_unidades(settings.processed_dir)
    _exigir_corpus(unidades, settings)
    eval_set = leer_eval_set(eval_set_path)

    typer.echo(f"{len(unidades)} unidades indexadas · eval set: {eval_set_path}")
    typer.echo("")

    if motor == "bm25":
        _evaluar_bm25(unidades, eval_set, k)
    else:
        _evaluar_denso(settings, unidades, eval_set, k)


@app.command()
def puntuaciones(
    eval_set_path: Annotated[Path, typer.Option("--eval-set")] = _EVAL_SET_POR_DEFECTO,
    k: Annotated[int, typer.Option("--k")] = 10,
) -> None:
    """Score denso (sin ruta) para las 50 preguntas aceptadas, ordenado de mayor a menor.

    Diagnóstico para el ticket 12 (política de abstención): no mide recall, mide si el score por
    sí solo separa las preguntas con respuesta en el corpus de las que no la tienen
    (`fuera_de_corpus` y `trampa`, marcadas aquí como SIN RESPUESTA).
    """
    settings = get_settings()
    unidades = cargar_unidades(settings.processed_dir)
    _exigir_corpus(unidades, settings)
    eval_set = leer_eval_set(eval_set_path)

    ruta_indice = indice_denso.ruta_indice(settings, con_ruta=False)
    if not ruta_indice.exists():
        typer.secho(
            f"No existe {ruta_indice}. Constrúyelo con 'rag-lopd retrieval indexar --sin-ruta'.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    with EmbebedorDeepInfra(settings) as embebedor:
        unidades_indice, vectores = indice_denso.cargar(ruta_indice, unidades)
        recuperador = RecuperadorDenso(unidades_indice, vectores, embebedor)
        resultados = abstencion.puntuaciones(recuperador, eval_set, k=k)

    for r in sorted(resultados, key=lambda r: r.top1, reverse=True):
        marca = "SIN RESPUESTA" if r.debe_abstenerse else ""
        typer.echo(
            f"{r.pregunta.id:8} {r.pregunta.tipo.value:16} "
            f"top1={r.top1:.3f}  media={r.media_top_k:.3f}  {marca}"
        )


@app.command()
def buscar(
    consulta: Annotated[str, typer.Argument(help="La consulta en lenguaje natural.")],
    k: Annotated[int, typer.Option("--k")] = 5,
    sin_ruta: Annotated[bool, typer.Option("--sin-ruta")] = False,
    motor: Annotated[str, typer.Option("--motor", help="bm25 o denso.")] = "bm25",
) -> None:
    """Busca a mano una consulta y enseña las k unidades más relevantes."""
    if motor not in _MOTORES:
        typer.secho(
            f"motor desconocido: {motor!r}. Usa {' o '.join(_MOTORES)}.", fg=typer.colors.RED
        )
        raise typer.Exit(code=1)

    settings = get_settings()
    unidades = cargar_unidades(settings.processed_dir)
    _exigir_corpus(unidades, settings)

    if motor == "bm25":
        resultados = RecuperadorBM25(unidades, con_ruta=not sin_ruta).buscar(consulta, k=k)
    else:
        ruta_indice = indice_denso.ruta_indice(settings, con_ruta=not sin_ruta)
        if not ruta_indice.exists():
            typer.secho(
                f"No existe {ruta_indice}. Constrúyelo antes con 'rag-lopd retrieval indexar'.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
        with EmbebedorDeepInfra(settings) as embebedor:
            unidades_indice, vectores = indice_denso.cargar(ruta_indice, unidades)
            resultados = RecuperadorDenso(unidades_indice, vectores, embebedor).buscar(
                consulta, k=k
            )

    for resultado in resultados:
        typer.echo(f"[{resultado.score:6.2f}] {resultado.id} — {resultado.ruta}")
