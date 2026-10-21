from pathlib import Path

from rag_lopd.config import Settings


def test_defaults_apuntan_a_las_fuentes_correctas() -> None:
    settings = Settings(_env_file=None)

    # Cellar, no eur-lex.europa.eu: eur-lex bloquea a los clientes que no son navegador.
    assert "publications.europa.eu" in settings.cellar_base
    assert settings.rgpd_celex.startswith("0"), (
        "debe ser la versión consolidada, no el acto original"
    )
    assert settings.boe_lopdgdd_id == "BOE-A-2018-16673"


def test_las_rutas_derivadas_cuelgan_de_data_dir() -> None:
    settings = Settings(_env_file=None, data_dir=Path("/tmp/corpus"))

    assert settings.raw_dir == Path("/tmp/corpus/raw")
    assert settings.processed_dir == Path("/tmp/corpus/processed")


def test_las_variables_de_entorno_ganan_a_los_valores_por_defecto(monkeypatch) -> None:
    monkeypatch.setenv("HTTP_TIMEOUT_SECONDS", "5")

    assert Settings(_env_file=None).http_timeout_seconds == 5.0


def test_las_claves_no_se_filtran_al_repr() -> None:
    settings = Settings(_env_file=None, deepinfra_api_key="secreto-que-no-debe-salir")

    assert "secreto-que-no-debe-salir" not in repr(settings)
