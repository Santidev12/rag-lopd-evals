"""Punto de entrada de la línea de comandos.

Cada paso del pipeline será un subcomando de aquí, para que el README pueda decir
exactamente qué hay que teclear para reproducir los números.
"""

import typer

from rag_lopd import __version__
from rag_lopd.config import get_settings

app = typer.Typer(
    help="RAG evaluado sobre normativa española de protección de datos.",
    no_args_is_help=True,
    add_completion=False,
)


@app.command()
def info() -> None:
    """Muestra la versión y la configuración efectiva (sin exponer las claves)."""
    settings = get_settings()
    typer.echo(f"rag-lopd-evals {__version__}")
    typer.echo(f"  BOE      : {settings.boe_api_base} ({settings.boe_lopdgdd_id})")
    typer.echo(f"  Cellar   : {settings.cellar_base}/{settings.rgpd_celex}")
    typer.echo(f"  Datos    : {settings.data_dir.resolve()}")
    typer.echo(f"  DeepInfra: {'configurada' if settings.deepinfra_api_key else 'sin configurar'}")
