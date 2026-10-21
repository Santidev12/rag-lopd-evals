"""Tests del informe estático: lo que se prueba es qué dice la página y que no se pueda colar
HTML desde los datos, no su aspecto."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rag_lopd.cli import app
from rag_lopd.eval.modelo import EvalSet, Pregunta, TipoPregunta
from rag_lopd.generacion.evaluacion import Observacion
from rag_lopd.generacion.gemini import tarifa_de
from rag_lopd.generacion.juez import Juicio, Veredicto
from rag_lopd.generacion.modelo import Estado, Respuesta, Uso
from rag_lopd.informe import construir_informe
from rag_lopd.model import Identificador
from rag_lopd.retrieval.evaluacion import RecallMedido

NOMBRE = "gemini-3.5-flash-lite-promptv2-k10-20261021-161822.jsonl"
TARIFA = tarifa_de("gemini-3.5-flash-lite")


def _pregunta(id_: str, tipo: TipoPregunta, fuente: tuple[str, ...] = ()) -> Pregunta:
    return Pregunta(
        id=id_,
        pregunta=f"¿Qué dice la norma sobre el caso número {id_} de este eval set?",
        tipo=tipo,
        respuesta="La referencia: 72 horas.",
        fuente=tuple(Identificador.parse(f) for f in fuente),
        estado="aceptada",  # type: ignore[arg-type]
    )


def _obs(
    id_: str,
    tipo: TipoPregunta,
    estado: Estado,
    *,
    fuente: tuple[str, ...] = (),
    texto: str = "",
    latencia: float | None = None,
) -> Observacion:
    articulo = Identificador.parse("rgpd:art-33")
    return Observacion(
        pregunta_id=id_,
        tipo=tipo,
        fuente=tuple(Identificador.parse(f) for f in fuente),
        contextos=(articulo,),
        respuesta=Respuesta(
            estado=estado,
            texto=texto,
            citas=(articulo,) if estado is Estado.RESPONDE else (),
            uso=Uso(tokens_entrada=1_000, tokens_salida=100),
        ),
        latencia_s=latencia,
    )


def _juicio(id_: str, tipo: TipoPregunta, veredicto: Veredicto) -> Juicio:
    return Juicio(pregunta_id=id_, tipo=tipo, veredicto=veredicto, motivo="porque sí")


def _caso() -> tuple[list[Observacion], EvalSet]:
    f, foc = TipoPregunta.FACTUAL, TipoPregunta.FUERA_DE_CORPUS
    eval_set = EvalSet(
        version="t",
        preguntas=(
            _pregunta("e-001", f, ("rgpd:art-33.1",)),
            _pregunta("e-002", f, ("rgpd:art-33.1",)),
            _pregunta("e-003", foc),
            _pregunta("e-004", foc),
        ),
    )
    observaciones = [
        _obs(
            "e-001", f, Estado.RESPONDE, fuente=("rgpd:art-33.1",), texto="72 horas", latencia=2.0
        ),
        _obs("e-002", f, Estado.ABSTIENE, fuente=("rgpd:art-33.1",), latencia=4.0),
        _obs("e-003", foc, Estado.ABSTIENE, latencia=3.0),
        _obs("e-004", foc, Estado.RESPONDE, texto="inventado", latencia=5.0),
    ]
    return observaciones, eval_set


def _html(**kwargs: object) -> str:
    observaciones, eval_set = _caso()
    return construir_informe(
        observaciones,
        eval_set,
        modelo="gemini-3.5-flash-lite",
        tarifa=TARIFA,
        nombre_pasada=NOMBRE,
        fecha=date(2026, 10, 21),
        **kwargs,  # type: ignore[arg-type]
    )


def test_el_informe_es_una_pagina_autocontenida_con_los_numeros() -> None:
    html = _html()

    assert html.startswith("<!doctype html>")
    assert "<script" not in html
    assert "http://" not in html and "https://" not in html
    assert "Sobre-respuesta" in html and "Abstención indebida" in html
    assert "1/2" in html  # una de las dos fuera de corpus se contestó
    assert "prompt <code>v2</code>" in html
    assert "2026-10-21" in html


def test_las_preguntas_que_fallan_salen_abiertas_y_las_que_aciertan_no() -> None:
    html = _html()

    # e-002 calla teniendo la respuesta, e-004 sobre-responde: las dos en «Dónde falla».
    assert "Dónde falla (2)" in html
    assert "Abstención indebida: calló teniendo la respuesta" in html
    assert "Sobre-respuesta: contestó sin respuesta en el corpus" in html
    assert 'id="e-002" open' in html and 'id="e-004" open' in html
    # La sección «Dónde falla» las abre, y la lista completa las repite cerradas.
    assert html.count('id="e-001"') == 1 and 'id="e-001" open' not in html


def test_sin_juicios_no_se_inventa_un_acierto() -> None:
    sin = _html()
    con = _html(
        juicios={"e-001": _juicio("e-001", TipoPregunta.FACTUAL, Veredicto.CORRECTA)},
        nombre_juicios="x.juez-deepseek-v4-flash-v2.jsonl",
    )

    assert "Contestó (contenido sin juzgar)" in sin
    assert "Exactitud" not in sin
    assert "Contestó correctamente" in con
    assert "Exactitud" in con
    assert "juez <code>deepseek-v4-flash</code>" in con


def test_un_contenido_incorrecto_o_parcial_se_marca() -> None:
    parcial = _html(juicios={"e-001": _juicio("e-001", TipoPregunta.FACTUAL, Veredicto.PARCIAL)})
    grave = _html(
        juicios={"e-004": _juicio("e-004", TipoPregunta.FUERA_DE_CORPUS, Veredicto.INCORRECTA)}
    )

    assert "la respuesta es parcial" in parcial
    assert "Sobre-respuesta grave" in grave


def test_lo_que_dice_el_modelo_se_escapa() -> None:
    observaciones, eval_set = _caso()
    observaciones[0] = _obs(
        "e-001",
        TipoPregunta.FACTUAL,
        Estado.RESPONDE,
        fuente=("rgpd:art-33.1",),
        texto='<script>alert("x")</script> <img src=x onerror=1>',
    )

    html = construir_informe(
        observaciones,
        eval_set,
        modelo="gemini-3.5-flash-lite",
        tarifa=TARIFA,
        nombre_pasada=NOMBRE,
        fecha=date(2026, 10, 21),
    )

    assert "<script" not in html and "<img" not in html
    assert "&lt;script&gt;" in html


def test_la_latencia_sin_desglose_lo_avisa_y_con_desglose_lo_enseña() -> None:
    sin = _html()
    assert "anterior al desglose" in sin

    observaciones, eval_set = _caso()
    desglosadas = [
        o.model_copy(update={"latencia_recuperacion_s": 0.5, "latencia_generacion_s": 1.5})
        for o in observaciones
    ]
    con = construir_informe(
        desglosadas,
        eval_set,
        modelo="gemini-3.5-flash-lite",
        tarifa=TARIFA,
        nombre_pasada=NOMBRE,
        fecha=date(2026, 10, 21),
    )
    assert "Recuperar (embeber + buscar)" in con and "anterior al desglose" not in con


def test_el_recall_se_muestra_por_k_y_a_nivel_articulo() -> None:
    def medida(nivel: str, k: int, aciertos: int, fallos: tuple[str, ...]) -> RecallMedido:
        return RecallMedido(
            motor="denso",
            con_ruta=False,
            nivel=nivel,
            k=k,
            total=28,
            aciertos=aciertos,
            fallos=fallos,  # type: ignore[arg-type]
        )

    html = _html(
        recall=[
            medida("articulo", 5, 22, ("e-021",)),
            medida("articulo", 20, 26, ("e-021",)),
            RecallMedido(
                motor="bm25",
                con_ruta=False,
                nivel="articulo",
                k=10,
                total=27,
                aciertos=13,
                fallos=(),
            ),
        ]
    )

    assert "@5" in html and "@20" in html and "@10" not in html
    assert "22/28" in html and "78,6 %" in html
    assert "e-021" in html


def test_una_pasada_con_preguntas_que_el_eval_set_no_tiene_falla() -> None:
    observaciones, _ = _caso()
    vacio = EvalSet(version="t", preguntas=())

    with pytest.raises(ValueError, match="e-001"):
        construir_informe(
            observaciones,
            vacio,
            modelo="m",
            tarifa=TARIFA,
            nombre_pasada=NOMBRE,
            fecha=date(2026, 10, 21),
        )


def test_el_comando_escribe_el_informe_desde_ficheros_guardados(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    observaciones, eval_set = _caso()
    pasada = tmp_path / NOMBRE
    pasada.write_text(
        "\n".join(o.model_dump_json() for o in observaciones) + "\n", encoding="utf-8"
    )
    ruta_eval = tmp_path / "eval.jsonl"
    ruta_eval.write_text(
        "\n".join(p.model_dump_json() for p in eval_set.preguntas) + "\n", encoding="utf-8"
    )
    salida = tmp_path / "out" / "informe.html"

    resultado = CliRunner().invoke(
        app, ["informe", str(pasada), "--eval-set", str(ruta_eval), "--salida", str(salida)]
    )

    assert resultado.exit_code == 0, resultado.output
    assert "Informe con 4 preguntas" in resultado.output
    assert "Dónde falla (2)" in salida.read_text(encoding="utf-8")
