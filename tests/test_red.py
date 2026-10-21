"""Tests que salen a internet de verdad.

Están marcados con `red` y **excluidos por defecto** (ver `addopts` en pyproject.toml): la suite
normal tiene que correr sin conexión, rápido y sin depender de que un servidor esté de pie.

Se ejecutan a propósito, con `uv run pytest -m red`, cuando interesa saber si las fuentes
siguen donde estaban y si el parser aguanta el documento completo — no solo el recorte.
"""

from datetime import date
from pathlib import Path

import pytest

from rag_lopd.config import Settings
from rag_lopd.descarga import Descargador
from rag_lopd.fuentes import lopdgdd, rgpd

pytestmark = pytest.mark.red


@pytest.fixture(scope="module")
def descargador(tmp_path_factory: pytest.TempPathFactory) -> Descargador:
    directorio: Path = tmp_path_factory.mktemp("descargas")
    return Descargador(directorio, user_agent=Settings(_env_file=None).user_agent)


def test_el_rgpd_entero_se_ingiere(descargador: Descargador) -> None:
    settings = Settings(_env_file=None)

    norma = rgpd.ingerir(descargador, settings.cellar_base, settings.rgpd_celex)

    assert len(norma.articulos) == 99, "el RGPD tiene 99 artículos"
    assert norma.proporcion_partida_en_apartados() > 0.90


def test_la_lopdgdd_entera_se_ingiere_por_encima_del_umbral(descargador: Descargador) -> None:
    settings = Settings(_env_file=None)

    norma = lopdgdd.ingerir(
        descargador, settings.boe_api_base, settings.boe_lopdgdd_id, hoy=date.today()
    )

    assert len(norma.articulos) > 130
    assert norma.proporcion_partida_en_apartados() >= lopdgdd.UMBRAL_PARTIDO
    assert str(norma.articulos[0].id).startswith("lopdgdd:art-")
