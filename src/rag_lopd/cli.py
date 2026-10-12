"""Punto de entrada de la línea de comandos.

Cada paso del pipeline es un subcomando, para que el README pueda decir exactamente qué hay
que teclear para reproducir los números.
"""

from __future__ import annotations

import typer

from rag_lopd import __version__
from rag_lopd.almacen import guardar
from rag_lopd.config import Settings, get_settings
from rag_lopd.descarga import Descargador
from rag_lopd.eval.cli import app as app_eval
from rag_lopd.fuentes import lopdgdd, rgpd
from rag_lopd.generacion.cli import app as app_generacion
from rag_lopd.model import Norma
from rag_lopd.retrieval.cli import app as app_retrieval

FUENTES = ("rgpd", "lopdgdd")

app = typer.Typer(
    help="RAG evaluado sobre normativa española de protección de datos.",
    no_args_is_help=True,
    add_completion=False,
)


app.add_typer(app_eval, name="eval")
app.add_typer(app_retrieval, name="retrieval")
app.add_typer(app_generacion, name="generacion")


@app.command()
def info() -> None:
    """Muestra la versión y la configuración efectiva (sin exponer las claves)."""
    settings = get_settings()
    typer.echo(f"rag-lopd-evals {__version__}")
    typer.echo(f"  BOE      : {settings.boe_api_base} ({settings.boe_lopdgdd_id})")
    typer.echo(f"  Cellar   : {settings.cellar_base}/{settings.rgpd_celex}")
    typer.echo(f"  Datos    : {settings.data_dir.resolve()}")
    typer.echo(f"  DeepInfra: {'configurada' if settings.deepinfra_api_key else 'sin configurar'}")
    typer.echo(f"  Google   : {'configurada' if settings.google_api_key else 'sin configurar'}")


@app.command()
def ingest(
    fuente: str = typer.Argument("todo", help="rgpd, lopdgdd o todo."),
) -> None:
    """Descarga las normas, las normaliza y las deja en `data/processed/`."""
    objetivos: tuple[str, ...]
    if fuente == "todo":
        objetivos = FUENTES
    elif fuente in FUENTES:
        objetivos = (fuente,)
    else:
        raise typer.BadParameter(
            f"fuente desconocida: {fuente!r}. Opciones: {', '.join(FUENTES)} o 'todo'."
        )

    settings = get_settings()
    descargador = Descargador(
        settings.raw_dir,
        timeout=settings.http_timeout_seconds,
        user_agent=settings.user_agent,
    )

    for nombre in objetivos:
        norma = _traer(nombre, descargador, settings)
        _informar(norma, settings)


def _traer(nombre: str, descargador: Descargador, settings: Settings) -> Norma:
    typer.echo(f"Ingiriendo {nombre} (caché en {settings.raw_dir})...")
    if nombre == "rgpd":
        return rgpd.ingerir(descargador, settings.cellar_base, settings.rgpd_celex)
    return lopdgdd.ingerir(descargador, settings.boe_api_base, settings.boe_lopdgdd_id)


def _informar(norma: Norma, settings: Settings) -> None:
    ruta_norma, ruta_unidades = guardar(norma, settings.processed_dir)
    partida = norma.proporcion_partida_en_apartados()

    typer.echo(f"  {len(norma.articulos)} preceptos, {len(norma.unidades_vigentes())} unidades")
    typer.echo(f"  {partida:.1%} partidas en apartados")
    typer.echo(f"  -> {ruta_norma}")
    typer.echo(f"  -> {ruta_unidades}")

    if norma.slug == lopdgdd.SLUG and partida < lopdgdd.UMBRAL_PARTIDO:
        # Fallar aquí, y no más adelante, es deliberado: un corpus peor no se nota en los
        # tests, se nota tres pasos después en unos números de retrieval que ya nadie sabe
        # por qué bajaron.
        typer.secho(
            f"  ERROR: por debajo del umbral ({lopdgdd.UMBRAL_PARTIDO:.0%}). "
            "La regex de apartados se ha roto o el BOE ha cambiado el formato.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)


if __name__ == "__main__":  # pragma: no cover
    app()
