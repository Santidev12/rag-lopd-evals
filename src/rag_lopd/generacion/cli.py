"""CLI de la generación: preguntar a mano y medir la política de abstención.

`evaluar` llama de verdad al modelo (cuesta céntimos) y va guardando cada observación en
`data/runs/` según termina. `resumir` vuelve a calcular las cifras desde un fichero guardado sin
llamar a nadie: ajustar cómo se reporta no debería costar dinero.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated

import httpx
import typer

from rag_lopd.config import Settings, get_settings
from rag_lopd.eval.almacen import leer as leer_eval_set
from rag_lopd.eval.modelo import TipoPregunta
from rag_lopd.generacion.contexto import contextos_para, indexar_articulos
from rag_lopd.generacion.evaluacion import Observacion, Resumen, evaluar_generacion, resumir
from rag_lopd.generacion.gemini import MODELO_POR_DEFECTO, GeminiModelo, tarifa_de
from rag_lopd.generacion.modelo import Tarifa
from rag_lopd.generacion.prompt import VERSION as VERSION_PROMPT
from rag_lopd.generacion.responder import responder
from rag_lopd.model import UnidadIndexable
from rag_lopd.retrieval import indice_denso
from rag_lopd.retrieval.corpus import cargar_unidades
from rag_lopd.retrieval.denso import RecuperadorDenso
from rag_lopd.retrieval.embeddings import EmbebedorDeepInfra

app = typer.Typer(help="Generación: responder con cita o abstenerse, y medirlo.")

_EVAL_SET_POR_DEFECTO = Path("eval/candidatas-v0.jsonl")

_MODELO = Annotated[str, typer.Option("--modelo", help="Modelo de Gemini.")]
_K = Annotated[
    int, typer.Option("--k", help="Unidades que se recuperan (se agrupan en artículos).")
]


def _fallar(mensaje: str) -> typer.Exit:
    typer.secho(mensaje, fg=typer.colors.RED)
    return typer.Exit(code=1)


def _corpus_e_indice(settings: Settings) -> tuple[list[UnidadIndexable], Path]:
    """El corpus cargado y la ruta del índice denso (sin ruta jerárquica: la variante elegida en
    el ticket 11), o un error claro si falta alguno de los dos."""
    unidades = cargar_unidades(settings.processed_dir)
    if not unidades:
        raise _fallar(f"No hay unidades en {settings.processed_dir}. Ejecuta 'rag-lopd ingest'.")
    ruta = indice_denso.ruta_indice(settings, con_ruta=False)
    if not ruta.exists():
        raise _fallar(f"No existe {ruta}. Constrúyelo con 'rag-lopd retrieval indexar --sin-ruta'.")
    return unidades, ruta


@app.command()
def preguntar(
    pregunta: Annotated[str, typer.Argument(help="La pregunta, en lenguaje natural.")],
    k: _K = 10,
    modelo: _MODELO = MODELO_POR_DEFECTO,
) -> None:
    """Recupera, genera y enseña la respuesta (o la abstención) con su cita y su coste."""
    settings = get_settings()
    unidades, ruta = _corpus_e_indice(settings)
    indice = indexar_articulos(unidades)

    try:
        with (
            EmbebedorDeepInfra(settings) as embebedor,
            GeminiModelo(settings, modelo=modelo) as llm,
        ):
            unidades_indice, vectores = indice_denso.cargar(ruta, unidades)
            recuperador = RecuperadorDenso(unidades_indice, vectores, embebedor)
            contextos = contextos_para(recuperador.buscar(pregunta, k=k), indice)
            respuesta = responder(llm, pregunta, contextos)
            tarifa = llm.tarifa
    except (ValueError, httpx.HTTPError) as error:
        raise _fallar(f"Error: {error}") from error

    typer.echo(f"Artículos dados al modelo: {', '.join(str(c.id) for c in contextos)}")
    typer.echo(f"Estado: {respuesta.estado.value}")
    if respuesta.texto:
        typer.echo(f"\n{respuesta.texto}\n")
    if respuesta.citas:
        typer.echo(f"Citas: {', '.join(str(c) for c in respuesta.citas)}")
    if respuesta.citas_descartadas:
        typer.echo(f"Citas descartadas (no estaban en el contexto): {respuesta.citas_descartadas}")
    typer.echo(
        f"Tokens: {respuesta.uso.tokens_entrada} entrada, {respuesta.uso.tokens_salida} salida "
        f"· {tarifa.coste_usd(respuesta.uso):.5f} USD"
    )


def _imprimir_resumen(resumen: Resumen, tarifa: Tarifa) -> None:
    typer.echo("")
    typer.echo("Sobre-respuesta (sin respuesta y contesta; menos es mejor):")
    typer.echo(f"  {resumen.sobre_respuesta}")
    typer.echo("Abstención indebida (con respuesta y calla; menos es mejor):")
    typer.echo(f"  {resumen.abstencion_indebida}")
    typer.echo("Contexto completo (llegaron todos los artículos de la fuente):")
    typer.echo(f"  {resumen.contexto_completo}")
    typer.echo("Cita cubre la fuente (de las contestadas):")
    typer.echo(f"  {resumen.cita_cubre_fuente}")
    typer.echo("Comportamiento correcto por tipo:")
    for tipo in TipoPregunta:
        typer.echo(f"  {tipo.value:16} {resumen.comportamiento_por_tipo[tipo]}")
    if resumen.salidas_invalidas:
        typer.secho(
            f"ATENCIÓN: {resumen.salidas_invalidas} salida(s) sin el JSON pedido: contaminan "
            "las cifras de arriba.",
            fg=typer.colors.YELLOW,
        )
    typer.echo(
        f"Tokens: {resumen.uso.tokens_entrada} entrada, {resumen.uso.tokens_salida} salida "
        f"· {tarifa.coste_usd(resumen.uso):.4f} USD en total"
    )


@app.command()
def evaluar(
    eval_set_path: Annotated[Path, typer.Option("--eval-set")] = _EVAL_SET_POR_DEFECTO,
    k: _K = 10,
    modelo: _MODELO = MODELO_POR_DEFECTO,
) -> None:
    """Corre las preguntas aceptadas contra recuperación densa + generación y las resume.

    Llama al modelo de verdad (céntimos). Cada observación se guarda en `data/runs/` según
    termina, para poder volver a resumirla con `resumir` sin repetir la llamada.
    """
    settings = get_settings()
    unidades, ruta = _corpus_e_indice(settings)
    eval_set = leer_eval_set(eval_set_path)
    indice = indexar_articulos(unidades)

    sello = datetime.now().strftime("%Y%m%d-%H%M%S")
    salida = settings.data_dir / "runs" / f"{modelo}-prompt{VERSION_PROMPT}-k{k}-{sello}.jsonl"
    salida.parent.mkdir(parents=True, exist_ok=True)

    def guardar(observacion: Observacion) -> None:
        with salida.open("a", encoding="utf-8") as fichero:
            fichero.write(observacion.model_dump_json() + "\n")
        typer.echo(f"  {observacion.pregunta_id} {observacion.respuesta.estado.value}")

    typer.echo(
        f"{modelo} · prompt {VERSION_PROMPT} · k={k} · {len(eval_set.aceptadas())} preguntas"
    )
    try:
        with (
            EmbebedorDeepInfra(settings) as embebedor,
            GeminiModelo(settings, modelo=modelo) as llm,
        ):
            unidades_indice, vectores = indice_denso.cargar(ruta, unidades)
            recuperador = RecuperadorDenso(unidades_indice, vectores, embebedor)
            observaciones = evaluar_generacion(
                llm, recuperador, indice, eval_set, k=k, al_terminar=guardar
            )
            tarifa = llm.tarifa
    except (ValueError, httpx.HTTPError) as error:
        typer.secho(f"Error: {error}\nLo ya contestado queda en {salida}.", fg=typer.colors.RED)
        raise typer.Exit(code=1) from error

    typer.echo(f"\nGuardado en {salida}")
    _imprimir_resumen(resumir(observaciones), tarifa)


@app.command("resumir")
def resumir_fichero(
    fichero: Annotated[Path, typer.Argument(help="Un fichero de data/runs/.")],
    modelo: _MODELO = MODELO_POR_DEFECTO,
) -> None:
    """Recalcula las cifras de una pasada guardada, sin llamar a ningún modelo."""
    lineas = [x for x in fichero.read_text(encoding="utf-8").splitlines() if x.strip()]
    observaciones = [Observacion.model_validate_json(x) for x in lineas]
    try:
        tarifa = tarifa_de(modelo)
    except ValueError as error:
        raise _fallar(f"Error: {error}") from error
    typer.echo(f"{fichero.name}: {len(observaciones)} observaciones")
    _imprimir_resumen(resumir(observaciones), tarifa)
