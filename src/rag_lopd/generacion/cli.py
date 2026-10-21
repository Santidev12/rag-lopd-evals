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
from rag_lopd.eval.modelo import EvalSet, TipoPregunta
from rag_lopd.generacion import deepinfra
from rag_lopd.generacion.contexto import contextos_para, indexar_articulos
from rag_lopd.generacion.deepinfra import DeepInfraModelo
from rag_lopd.generacion.evaluacion import (
    Observacion,
    Resumen,
    evaluar_generacion,
    realinear,
    resumir,
)
from rag_lopd.generacion.gemini import MODELO_POR_DEFECTO, GeminiModelo, tarifa_de
from rag_lopd.generacion.juez import VERSION as VERSION_JUEZ
from rag_lopd.generacion.juez import (
    Etiqueta,
    Juicio,
    Veredicto,
    calibrar,
    juzgar_pasada,
    leer_etiquetas,
    leer_juicios,
    resumir_juicios,
)
from rag_lopd.generacion.modelo import Tarifa
from rag_lopd.generacion.prompt import PROMPT_POR_DEFECTO, Prompt, prompt_de
from rag_lopd.generacion.responder import responder
from rag_lopd.model import UnidadIndexable
from rag_lopd.retrieval import indice_denso
from rag_lopd.retrieval.corpus import cargar_unidades, cargar_unidades_con_historia
from rag_lopd.retrieval.denso import RecuperadorDenso
from rag_lopd.retrieval.embeddings import EmbebedorDeepInfra

app = typer.Typer(help="Generación: responder con cita o abstenerse, y medirlo.")

_EVAL_SET_POR_DEFECTO = Path("eval/candidatas-v0.jsonl")

_MODELO = Annotated[str, typer.Option("--modelo", help="Modelo de Gemini.")]
_PROMPT = Annotated[
    str,
    typer.Option("--prompt", help="Versión del prompt: v1 (base) o v2 (con vigencia)."),
]
_K = Annotated[
    int, typer.Option("--k", help="Unidades que se recuperan (se agrupan en artículos).")
]


def _fallar(mensaje: str) -> typer.Exit:
    typer.secho(mensaje, fg=typer.colors.RED)
    return typer.Exit(code=1)


def _corpus_e_indice(
    settings: Settings,
) -> tuple[list[UnidadIndexable], list[UnidadIndexable], Path]:
    """Las unidades vigentes (lo que se indexa), todas las unidades con su historia (lo que el
    generador puede enseñar) y la ruta del índice denso (sin ruta jerárquica: la variante elegida
    en el ticket 11), o un error claro si falta algo."""
    vigentes = cargar_unidades(settings.processed_dir)
    if not vigentes:
        raise _fallar(f"No hay unidades en {settings.processed_dir}. Ejecuta 'rag-lopd ingest'.")
    try:
        todas = cargar_unidades_con_historia(settings.processed_dir)
    except FileNotFoundError as error:
        raise _fallar(
            f"Falta la norma completa ({error.filename}). Ejecuta 'rag-lopd ingest'."
        ) from error
    ruta = indice_denso.ruta_indice(settings, con_ruta=False)
    if not ruta.exists():
        raise _fallar(f"No existe {ruta}. Constrúyelo con 'rag-lopd retrieval indexar --sin-ruta'.")
    return vigentes, todas, ruta


def _elegir_prompt(version: str) -> Prompt:
    try:
        return prompt_de(version)
    except ValueError as error:
        raise _fallar(f"Error: {error}") from error


@app.command()
def preguntar(
    pregunta: Annotated[str, typer.Argument(help="La pregunta, en lenguaje natural.")],
    k: _K = 10,
    modelo: _MODELO = MODELO_POR_DEFECTO,
    prompt: _PROMPT = PROMPT_POR_DEFECTO.version,
) -> None:
    """Recupera, genera y enseña la respuesta (o la abstención) con su cita y su coste."""
    settings = get_settings()
    politica = _elegir_prompt(prompt)
    unidades, todas, ruta = _corpus_e_indice(settings)
    indice = indexar_articulos(todas)

    try:
        with (
            EmbebedorDeepInfra(settings) as embebedor,
            GeminiModelo(settings, modelo=modelo) as llm,
        ):
            unidades_indice, vectores = indice_denso.cargar(ruta, unidades)
            recuperador = RecuperadorDenso(unidades_indice, vectores, embebedor)
            contextos = contextos_para(recuperador.buscar(pregunta, k=k), indice)
            respuesta = responder(llm, pregunta, contextos, politica)
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
    prompt: _PROMPT = PROMPT_POR_DEFECTO.version,
) -> None:
    """Corre las preguntas aceptadas contra recuperación densa + generación y las resume.

    Llama al modelo de verdad (céntimos). Cada observación se guarda en `data/runs/` según
    termina, para poder volver a resumirla con `resumir` sin repetir la llamada.
    """
    settings = get_settings()
    politica = _elegir_prompt(prompt)
    unidades, todas, ruta = _corpus_e_indice(settings)
    eval_set = leer_eval_set(eval_set_path)
    indice = indexar_articulos(todas)

    sello = datetime.now().strftime("%Y%m%d-%H%M%S")
    salida = settings.data_dir / "runs" / f"{modelo}-prompt{politica.version}-k{k}-{sello}.jsonl"
    salida.parent.mkdir(parents=True, exist_ok=True)

    def guardar(observacion: Observacion) -> None:
        with salida.open("a", encoding="utf-8") as fichero:
            fichero.write(observacion.model_dump_json() + "\n")
        typer.echo(f"  {observacion.pregunta_id} {observacion.respuesta.estado.value}")

    typer.echo(
        f"{modelo} · prompt {politica.version} · k={k} · {len(eval_set.aceptadas())} preguntas"
    )
    try:
        with (
            EmbebedorDeepInfra(settings) as embebedor,
            GeminiModelo(settings, modelo=modelo) as llm,
        ):
            unidades_indice, vectores = indice_denso.cargar(ruta, unidades)
            recuperador = RecuperadorDenso(unidades_indice, vectores, embebedor)
            observaciones = evaluar_generacion(
                llm, recuperador, indice, eval_set, k=k, prompt=politica, al_terminar=guardar
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
    eval_set_path: Annotated[Path, typer.Option("--eval-set")] = _EVAL_SET_POR_DEFECTO,
) -> None:
    """Recalcula las cifras de una pasada guardada, sin llamar a ningún modelo.

    Cuenta contra el eval set actual (tipo y fuente de cada pregunta), no contra el de cuando se
    hizo la pasada. Sin eval set a mano, usa lo que la pasada guardó y lo avisa.
    """
    try:
        tarifa = tarifa_de(modelo)
    except ValueError as error:
        raise _fallar(f"Error: {error}") from error
    eval_set = leer_eval_set(eval_set_path) if eval_set_path.exists() else None
    if eval_set is None:
        typer.secho(
            f"Aviso: no hay eval set en {eval_set_path}; se usan el tipo y la fuente que guardó "
            "la pasada.",
            fg=typer.colors.YELLOW,
        )
    observaciones = _leer_observaciones(fichero, eval_set)
    typer.echo(f"{fichero.name}: {len(observaciones)} observaciones")
    _imprimir_resumen(resumir(observaciones), tarifa)


# --- el juez ------------------------------------------------------------------------------------

_MODELO_JUEZ = Annotated[
    str, typer.Option("--modelo-juez", help="Modelo de DeepInfra que hace de juez.")
]


def _leer_observaciones(fichero: Path, eval_set: EvalSet | None = None) -> list[Observacion]:
    """Lee una pasada; con eval set, realinea tipo y fuente y dice qué preguntas cambiaron."""
    lineas = [x for x in fichero.read_text(encoding="utf-8").splitlines() if x.strip()]
    guardadas = [Observacion.model_validate_json(x) for x in lineas]
    if eval_set is None:
        return guardadas
    try:
        alineadas = realinear(guardadas, eval_set)
    except ValueError as error:
        raise _fallar(f"Error: {error}") from error
    for antes, ahora in zip(guardadas, alineadas, strict=True):
        if antes.tipo is not ahora.tipo or antes.fuente != ahora.fuente:
            typer.echo(
                f"  realineada con el eval set: {antes.pregunta_id} "
                f"({antes.tipo.value} -> {ahora.tipo.value})"
            )
    return alineadas


def _ruta_juicios(fichero: Path, modelo_juez: str) -> Path:
    """Junto a la pasada y con el juez y la rúbrica en el nombre: dos jueces o dos versiones de la
    rúbrica sobre la misma pasada no se pisan."""
    juez = modelo_juez.rsplit("/", 1)[-1].lower()
    return fichero.with_name(f"{fichero.stem}.juez-{juez}-{VERSION_JUEZ}.jsonl")


def _imprimir_resumen_juicios(observaciones: list[Observacion], juicios: dict[str, Juicio]) -> None:
    resumen = resumir_juicios(observaciones, juicios)
    typer.echo("")
    typer.echo("Exactitud (respondibles contestadas correctamente; callar cuenta como fallo):")
    typer.echo(f"  {resumen.exactitud}")
    typer.echo("Exactitud de las contestadas (el contenido, sin contar lo que se calla):")
    typer.echo(f"  {resumen.exactitud_de_las_contestadas}")
    typer.echo(f"  parciales: {resumen.parciales} · incorrectas: {resumen.incorrectas}")
    typer.echo("Exactitud por tipo:")
    for tipo, proporcion in resumen.exactitud_por_tipo.items():
        typer.echo(f"  {tipo.value:16} {proporcion}")
    typer.echo("Sobre-respuesta grave (sin respuesta, contesta y afirma algo sin base):")
    typer.echo(f"  {resumen.sobre_respuesta_grave}")
    if resumen.juicios_invalidos:
        typer.secho(
            f"ATENCIÓN: {resumen.juicios_invalidos} juicio(s) sin el JSON pedido: no cuentan "
            "como correctos.",
            fg=typer.colors.YELLOW,
        )
    typer.echo(
        f"Tokens del juez: {resumen.uso.tokens_entrada} entrada, {resumen.uso.tokens_salida} salida"
    )


@app.command()
def juzgar(
    fichero: Annotated[Path, typer.Argument(help="Un fichero de data/runs/ (pasada de evaluar).")],
    eval_set_path: Annotated[Path, typer.Option("--eval-set")] = _EVAL_SET_POR_DEFECTO,
    modelo_juez: _MODELO_JUEZ = deepinfra.MODELO_POR_DEFECTO,
) -> None:
    """Juzga si el contenido de cada respuesta de una pasada es correcto, contra la referencia.

    Llama al juez (céntimos). Guarda cada juicio junto a la pasada según termina; si se repite
    el comando no se paga de nuevo lo ya juzgado.
    """
    settings = get_settings()
    eval_set = leer_eval_set(eval_set_path)
    observaciones = _leer_observaciones(fichero, eval_set)
    unidades = cargar_unidades(settings.processed_dir)
    if not unidades:
        raise _fallar(f"No hay unidades en {settings.processed_dir}. Ejecuta 'rag-lopd ingest'.")

    salida = _ruta_juicios(fichero, modelo_juez)
    previos = leer_juicios(salida.read_text(encoding="utf-8")) if salida.exists() else {}
    typer.echo(
        f"{fichero.name}: {len(observaciones)} observaciones · juez {modelo_juez} · rúbrica "
        f"{VERSION_JUEZ} · {len(previos)} ya juzgadas"
    )

    def guardar(juicio: Juicio) -> None:
        with salida.open("a", encoding="utf-8") as destino:
            destino.write(juicio.model_dump_json() + "\n")
        typer.echo(f"  {juicio.pregunta_id} {juicio.veredicto.value}")

    try:
        with DeepInfraModelo(settings, modelo=modelo_juez) as juez:
            juicios = juzgar_pasada(
                juez, observaciones, eval_set, unidades, previos=previos, al_terminar=guardar
            )
    except (ValueError, httpx.HTTPError) as error:
        typer.secho(f"Error: {error}\nLo ya juzgado queda en {salida}.", fg=typer.colors.RED)
        raise typer.Exit(code=1) from error

    typer.echo(f"\nGuardado en {salida}")
    _imprimir_resumen_juicios(observaciones, juicios)
    dudosos = [j for j in juicios.values() if j.veredicto is not Veredicto.CORRECTA]
    if dudosos:
        typer.echo("\nNo correctas, con el motivo del juez (revísalas a mano):")
        for juicio in sorted(dudosos, key=lambda j: j.pregunta_id):
            typer.echo(f"  {juicio.pregunta_id} {juicio.veredicto.value}: {juicio.motivo}")


@app.command("calibrar")
def calibrar_juez(
    juicios_path: Annotated[Path, typer.Argument(help="Los juicios guardados por `juzgar`.")],
    etiquetas_paths: Annotated[
        list[Path],
        typer.Argument(help="Etiquetas manuales (JSONL). Cada fichero pisa al anterior por id."),
    ],
) -> None:
    """Compara al juez con etiquetas manuales: acuerdo, kappa y discrepancias. No llama a nadie.

    Con varios ficheros de etiquetas, las de los últimos prevalecen: `preliminares` primero y
    después las de quien las revisó a mano.
    """
    juicios = leer_juicios(juicios_path.read_text(encoding="utf-8"))
    por_id: dict[str, Etiqueta] = {}
    for ruta in etiquetas_paths:
        propias = leer_etiquetas(ruta.read_text(encoding="utf-8"))
        pisadas = [e.pregunta_id for e in propias if e.pregunta_id in por_id]
        por_id.update({e.pregunta_id: e for e in propias})
        typer.echo(f"{ruta.name}: {len(propias)} etiquetas, {len(pisadas)} pisan a las anteriores")
    etiquetas = list(por_id.values())
    acuerdo = calibrar(juicios, etiquetas)
    typer.echo(f"{acuerdo.casos} respuestas con juicio y etiqueta")
    typer.echo(f"Acuerdo exacto (3 niveles):        {acuerdo.bruto}")
    typer.echo(f"Acuerdo en correcta / no correcta: {acuerdo.binario}")
    typer.echo(f"Kappa de Cohen (3 niveles):        {acuerdo.kappa:.2f}")
    typer.echo("Matriz (etiqueta -> juez):")
    for (etiqueta, juez), veces in sorted(acuerdo.matriz.items(), key=lambda x: str(x[0])):
        typer.echo(f"  {etiqueta.value:11} -> {juez.value:11} {veces}")
    if acuerdo.discrepancias:
        typer.echo("\nDiscrepancias:")
        for d in acuerdo.discrepancias:
            typer.echo(
                f"  {d.pregunta_id}: etiqueta {d.etiqueta.value}, juez {d.juez.value} "
                f"- {d.motivo_del_juez}"
            )
