"""Tests de la CLI de generación, sin red: lo que se prueba es el cableado (guardar una pasada,
volver a resumirla, fallar con un mensaje claro), no el modelo."""

from __future__ import annotations

import json
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


def _fila(id_: str, tipo: str, fuente: list[str]) -> dict[str, object]:
    return {
        "id": id_,
        "pregunta": "¿En qué plazo debe notificarse una violación de seguridad a la autoridad?",
        "tipo": tipo,
        "respuesta": "Una respuesta de referencia.",
        "fuente": fuente,
        "estado": "aceptada",
    }


def test_resumir_recalcula_las_cifras_de_una_pasada_guardada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # sin eval set a mano: se usa lo guardado en la pasada
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
    assert "Aviso: no hay eval set" in resultado.output


def test_resumir_cuenta_contra_el_eval_set_actual_aunque_la_pasada_sea_vieja(
    tmp_path: Path,
) -> None:
    observaciones = [
        _observacion("f-1", TipoPregunta.FACTUAL, Estado.RESPONDE),
        _observacion("tr-1", TipoPregunta.TRAMPA, Estado.RESPONDE),
    ]
    fichero = tmp_path / "pasada.jsonl"
    fichero.write_text(
        "\n".join(o.model_dump_json() for o in observaciones) + "\n", encoding="utf-8"
    )
    eval_set = tmp_path / "eval.jsonl"
    eval_set.write_text(
        "\n".join(
            json.dumps(fila, ensure_ascii=False)
            for fila in (
                _fila("f-1", "factual", ["rgpd:art-33.1"]),
                _fila("tr-1", "factual", ["rgpd:art-57.3"]),  # corregida: ya no es trampa
            )
        )
        + "\n",
        encoding="utf-8",
    )

    resultado = runner.invoke(app, ["resumir", str(fichero), "--eval-set", str(eval_set)])

    assert resultado.exit_code == 0, resultado.output
    assert "realineada con el eval set: tr-1 (trampa -> factual)" in resultado.output
    assert "0/0 = 0.0%" in resultado.output  # ya no queda ninguna pregunta sin respuesta contestada


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


def _guardar_pasada_y_corpus(tmp_path: Path) -> Path:
    """Una pasada de una pregunta contestada, y el eval set y el corpus mínimos para juzgarla."""
    from rag_lopd.almacen import guardar
    from rag_lopd.model import Articulo, Granularidad, Norma, UnidadIndexable

    unidad = UnidadIndexable(
        id=Identificador.parse("rgpd:art-33.1"),
        texto="La notificación será en 72 horas.",
        granularidad=Granularidad.APARTADO,
        ruta="RGPD",
    )
    articulo = Articulo(
        id=Identificador.parse("rgpd:art-33"), titulo="t", ruta="RGPD", texto="", unidades=(unidad,)
    )
    guardar(
        Norma(slug="rgpd", titulo="RGPD", identificador_oficial="x", articulos=(articulo,)),
        tmp_path / "data" / "processed",
    )
    pasada = tmp_path / "pasada.jsonl"
    observacion = _observacion("f-1", TipoPregunta.FACTUAL, Estado.RESPONDE)
    pasada.write_text(observacion.model_dump_json() + "\n", encoding="utf-8")
    return pasada


def test_juzgar_sin_clave_de_deepinfra_falla_con_mensaje_claro(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DEEPINFRA_API_KEY", raising=False)
    pasada = _guardar_pasada_y_corpus(tmp_path)
    eval_set = tmp_path / "eval.jsonl"
    eval_set.write_text(
        '{"id": "f-1", "pregunta": "¿En qué plazo debe notificarse una violación de seguridad?", '
        '"tipo": "factual", "respuesta": "72 horas", "fuente": ["rgpd:art-33.1"], '
        '"estado": "aceptada"}\n',
        encoding="utf-8",
    )

    resultado = runner.invoke(app, ["juzgar", str(pasada), "--eval-set", str(eval_set)])

    assert resultado.exit_code == 1, resultado.output
    assert "DEEPINFRA_API_KEY" in resultado.output


def test_calibrar_muestra_acuerdo_y_discrepancias(tmp_path: Path) -> None:
    from rag_lopd.generacion.juez import Juicio, Veredicto

    juicios = tmp_path / "juicios.jsonl"
    juicios.write_text(
        Juicio(
            pregunta_id="f-1",
            tipo=TipoPregunta.FACTUAL,
            veredicto=Veredicto.CORRECTA,
            motivo="da el plazo",
        ).model_dump_json()
        + "\n",
        encoding="utf-8",
    )
    etiquetas = tmp_path / "etiquetas.jsonl"
    etiquetas.write_text('{"pregunta_id": "f-1", "veredicto": "incorrecta"}\n', encoding="utf-8")

    resultado = runner.invoke(app, ["calibrar", str(juicios), str(etiquetas)])

    assert resultado.exit_code == 0, resultado.output
    assert "1 respuestas con juicio y etiqueta" in resultado.output
    assert "f-1: etiqueta incorrecta, juez correcta - da el plazo" in resultado.output


def test_calibrar_con_varios_ficheros_las_ultimas_etiquetas_pisan_a_las_primeras(
    tmp_path: Path,
) -> None:
    from rag_lopd.generacion.juez import Juicio, Veredicto

    juicios = tmp_path / "juicios.jsonl"
    juicios.write_text(
        "\n".join(
            Juicio(
                pregunta_id=i, tipo=TipoPregunta.FACTUAL, veredicto=Veredicto.PARCIAL
            ).model_dump_json()
            for i in ("f-1", "f-2")
        )
        + "\n",
        encoding="utf-8",
    )
    primeras = tmp_path / "primeras.jsonl"
    primeras.write_text(
        '{"pregunta_id": "f-1", "veredicto": "correcta"}\n'
        '{"pregunta_id": "f-2", "veredicto": "parcial"}\n',
        encoding="utf-8",
    )
    ultimas = tmp_path / "ultimas.jsonl"
    ultimas.write_text('{"pregunta_id": "f-1", "veredicto": "parcial"}\n', encoding="utf-8")

    resultado = runner.invoke(app, ["calibrar", str(juicios), str(primeras), str(ultimas)])

    assert resultado.exit_code == 0, resultado.output
    assert "ultimas.jsonl: 1 etiquetas, 1 pisan a las anteriores" in resultado.output
    assert "2/2 = 100.0%" in resultado.output  # con la etiqueta pisada, juez y etiquetas coinciden
    assert "Discrepancias" not in resultado.output
