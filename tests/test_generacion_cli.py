"""Tests de la CLI de generación, sin red: lo que se prueba es el cableado (guardar una pasada,
volver a resumirla, fallar con un mensaje claro), no el modelo."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from rag_lopd.config import get_settings
from rag_lopd.eval.modelo import TipoPregunta
from rag_lopd.generacion.cli import app
from rag_lopd.generacion.evaluacion import Observacion
from rag_lopd.generacion.modelo import Estado, Respuesta, Uso
from rag_lopd.model import Identificador

runner = CliRunner()


@pytest.fixture(autouse=True)
def _aislar_configuracion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Un `.env` real en el directorio de trabajo no debe colarse en estos tests.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _observacion(id_: str, tipo: TipoPregunta, estado: Estado) -> Observacion:
    return Observacion(
        pregunta_id=id_,
        tipo=tipo,
        fuente=()
        if tipo in {TipoPregunta.TRAMPA, TipoPregunta.FUERA_DE_CORPUS}
        else (Identificador.parse("rgpd:art-33.1"),),
        contextos=(Identificador.parse("rgpd:art-33"),),
        respuesta=Respuesta(
            estado=estado,
            citas=(Identificador.parse("rgpd:art-33"),) if estado is Estado.RESPONDE else (),
            uso=Uso(tokens_entrada=1_000, tokens_salida=100),
        ),
    )


def test_resumir_recalcula_las_cifras_de_una_pasada_guardada(tmp_path: Path) -> None:
    observaciones = [
        _observacion("f-1", TipoPregunta.FACTUAL, Estado.RESPONDE),
        _observacion("tr-1", TipoPregunta.TRAMPA, Estado.RESPONDE),
    ]
    fichero = tmp_path / "pasada.jsonl"
    fichero.write_text(
        "\n".join(o.model_dump_json() for o in observaciones) + "\n", encoding="utf-8"
    )

    resultado = runner.invoke(app, ["resumir", str(fichero)])

    assert resultado.exit_code == 0, resultado.output
    assert "2 observaciones" in resultado.output
    assert "Sobre-respuesta" in resultado.output
    assert "1/1 = 100.0%" in resultado.output  # la trampa se contestó: sobre-respuesta total


def test_resumir_con_un_modelo_sin_tarifa_falla_con_mensaje_claro(tmp_path: Path) -> None:
    fichero = tmp_path / "pasada.jsonl"
    fichero.write_text("", encoding="utf-8")

    resultado = runner.invoke(app, ["resumir", str(fichero), "--modelo", "gemini-inventado"])

    assert resultado.exit_code == 1
    assert "no hay tarifa conocida" in resultado.output


def test_preguntar_sin_corpus_dice_que_hay_que_ingerir() -> None:
    resultado = runner.invoke(app, ["preguntar", "¿plazo para notificar una brecha?"])

    assert resultado.exit_code == 1
    assert "rag-lopd ingest" in resultado.output


def test_un_prompt_desconocido_falla_antes_de_cargar_nada() -> None:
    resultado = runner.invoke(app, ["preguntar", "¿plazo?", "--prompt", "v9"])

    assert resultado.exit_code == 1
    assert "no hay prompt 'v9'" in resultado.output
