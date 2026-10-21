"""Tests del diagnóstico de abstención: no mide recall, mide si el score distingue preguntas con
respuesta de preguntas sin ella. Recuperador de mentira, para aislar el cálculo del motor real.
"""

from __future__ import annotations

from rag_lopd.eval.modelo import EvalSet, Pregunta, TipoPregunta
from rag_lopd.model import Identificador
from rag_lopd.retrieval.abstencion import puntuaciones
from rag_lopd.retrieval.modelo import Resultado


class _RecuperadorPorPregunta:
    """Devuelve una lista de resultados distinta según el texto exacto de la consulta — a
    diferencia de `_RecuperadorFijo` (siempre la misma lista), aquí hace falta simular que
    preguntas distintas obtienen scores distintos."""

    def __init__(self, respuestas: dict[str, list[Resultado]]) -> None:
        self._respuestas = respuestas

    def buscar(self, consulta: str, *, k: int = 10) -> list[Resultado]:
        return self._respuestas.get(consulta, [])[:k]


def _resultado(score: float) -> Resultado:
    return Resultado(id=Identificador.parse("rgpd:art-1"), score=score, texto="", ruta="")


def _pregunta(
    id_: str,
    tipo: TipoPregunta,
    texto: str,
    *,
    fuente: tuple[str, ...] = (),
    estado: str = "aceptada",
) -> Pregunta:
    return Pregunta(
        id=id_,
        pregunta=texto,
        tipo=tipo,
        respuesta="una respuesta cualquiera, aquí no se evalúa",
        fuente=tuple(Identificador.parse(f) for f in fuente),
        estado=estado,
    )


def test_puntuaciones_calcula_top1_y_media_del_top_k() -> None:
    pregunta_factual = _pregunta(
        "f-1",
        TipoPregunta.FACTUAL,
        "En qué plazo debe notificarse una violación de seguridad a la autoridad",
        fuente=("rgpd:art-33.1",),
    )
    recuperador = _RecuperadorPorPregunta(
        {pregunta_factual.pregunta: [_resultado(0.9), _resultado(0.6), _resultado(0.3)]}
    )
    eval_set = EvalSet(version="test", preguntas=(pregunta_factual,))

    resultado = puntuaciones(recuperador, eval_set, k=3)

    assert len(resultado) == 1
    assert resultado[0].top1 == 0.9
    assert resultado[0].media_top_k == (0.9 + 0.6 + 0.3) / 3
    assert resultado[0].debe_abstenerse is False


def test_puntuaciones_marca_fuera_de_corpus_y_trampa_como_debe_abstenerse() -> None:
    fuera_de_corpus = _pregunta(
        "foc-1", TipoPregunta.FUERA_DE_CORPUS, "Qué sanción impuso la AEPD a tal empresa en 2024"
    )
    trampa = _pregunta(
        "trampa-1", TipoPregunta.TRAMPA, "Qué plazo de supresión aplica a los datos biométricos"
    )
    recuperador = _RecuperadorPorPregunta(
        {
            fuera_de_corpus.pregunta: [_resultado(0.4)],
            trampa.pregunta: [_resultado(0.5)],
        }
    )
    eval_set = EvalSet(version="test", preguntas=(fuera_de_corpus, trampa))

    resultado = {p.pregunta.id: p for p in puntuaciones(recuperador, eval_set)}

    assert resultado["foc-1"].debe_abstenerse is True
    assert resultado["trampa-1"].debe_abstenerse is True


def test_puntuaciones_sin_resultados_da_cero_en_vez_de_fallar() -> None:
    pregunta = _pregunta(
        "foc-1", TipoPregunta.FUERA_DE_CORPUS, "Qué sanción impuso la AEPD a tal empresa en 2024"
    )
    recuperador = _RecuperadorPorPregunta({})
    eval_set = EvalSet(version="test", preguntas=(pregunta,))

    resultado = puntuaciones(recuperador, eval_set)

    assert resultado[0].top1 == 0.0
    assert resultado[0].media_top_k == 0.0


def test_puntuaciones_deja_fuera_las_preguntas_no_aceptadas() -> None:
    candidata = _pregunta(
        "c-1",
        TipoPregunta.FACTUAL,
        "En qué plazo debe notificarse una violación de seguridad a la autoridad",
        fuente=("rgpd:art-33.1",),
        estado="candidata",
    )
    aceptada = _pregunta(
        "a-1",
        TipoPregunta.FACTUAL,
        "Qué debe incluir el registro de actividades de tratamiento",
        fuente=("rgpd:art-30.1",),
        estado="aceptada",
    )
    recuperador = _RecuperadorPorPregunta(
        {candidata.pregunta: [_resultado(0.9)], aceptada.pregunta: [_resultado(0.5)]}
    )
    eval_set = EvalSet(version="test", preguntas=(candidata, aceptada))

    resultado = puntuaciones(recuperador, eval_set)

    assert [p.pregunta.id for p in resultado] == ["a-1"]
