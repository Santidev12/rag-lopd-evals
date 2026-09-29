"""Tests del baseline BM25 y del harness que lo mide contra el eval set.

Nada aquí toca red ni el corpus real: las unidades y las preguntas son de mentira, a propósito,
para que el test siga significando lo mismo aunque cambie el corpus.
"""

from __future__ import annotations

from rag_lopd.eval.modelo import EvalSet, Pregunta, TipoPregunta
from rag_lopd.model import Granularidad, Identificador, UnidadIndexable
from rag_lopd.retrieval.bm25 import RecuperadorBM25
from rag_lopd.retrieval.evaluacion import evaluar_recall, preguntas_evaluables


def _unidad(id_texto: str, texto: str, ruta: str) -> UnidadIndexable:
    return UnidadIndexable(
        id=Identificador.parse(id_texto),
        texto=texto,
        granularidad=Granularidad.APARTADO,
        ruta=ruta,
    )


UNIDADES = [
    _unidad(
        "rgpd:art-17.1",
        "El interesado tendrá derecho a obtener la supresión de sus datos personales.",
        "RGPD · Capítulo III · Artículo 17",
    ),
    _unidad(
        "rgpd:art-33.1",
        "El responsable notificará la violación de seguridad a la autoridad en 72 horas.",
        "RGPD · Capítulo IV · Sección 2 · Artículo 33",
    ),
    _unidad(
        "lopdgdd:art-15.1",
        "Los menores de catorce años no pueden prestar consentimiento sin autorización.",
        "LOPDGDD · Título II · Capítulo I · Artículo 15",
    ),
]


def test_bm25_recupera_la_unidad_con_los_terminos_de_la_consulta() -> None:
    recuperador = RecuperadorBM25(UNIDADES, con_ruta=True)

    resultados = recuperador.buscar("plazo para notificar una violación de seguridad", k=1)

    assert len(resultados) == 1
    assert str(resultados[0].id) == "rgpd:art-33.1"


def test_bm25_devuelve_como_mucho_k_resultados() -> None:
    recuperador = RecuperadorBM25(UNIDADES, con_ruta=True)

    assert len(recuperador.buscar("datos personales", k=2)) == 2
    assert len(recuperador.buscar("datos personales", k=100)) == len(UNIDADES)


def test_bm25_sin_ruta_no_incluye_la_ruta_en_el_texto_indexado() -> None:
    # Si alguien busca literalmente por un término que solo aparece en la ruta ("Sección 2"),
    # la variante sin ruta no debería encontrar nada por ese camino.
    con_ruta = RecuperadorBM25(UNIDADES, con_ruta=True)
    sin_ruta = RecuperadorBM25(UNIDADES, con_ruta=False)

    assert con_ruta.buscar("Sección 2", k=1)[0].score > sin_ruta.buscar("Sección 2", k=1)[0].score


def _pregunta(id_: str, tipo: TipoPregunta, fuente: tuple[str, ...], pregunta: str) -> Pregunta:
    return Pregunta(
        id=id_,
        pregunta=pregunta,
        tipo=tipo,
        respuesta="una respuesta cualquiera, aquí no se evalúa la respuesta, solo la fuente",
        fuente=tuple(Identificador.parse(f) for f in fuente),
        estado="aceptada",
    )


def test_preguntas_evaluables_deja_fuera_lo_que_no_tiene_fuente_que_recuperar() -> None:
    eval_set = EvalSet(
        version="test",
        preguntas=(
            _pregunta(
                "q1",
                TipoPregunta.FACTUAL,
                ("rgpd:art-33.1",),
                "¿En qué plazo debe notificarse una violación de seguridad a la autoridad?",
            ),
            _pregunta(
                "q2",
                TipoPregunta.FUERA_DE_CORPUS,
                (),
                "¿Qué sanción impone la AEPD por publicidad no consentida en 2024?",
            ),
        ),
    )

    evaluables = preguntas_evaluables(eval_set)

    assert [p.id for p in evaluables] == ["q1"]


def test_evaluar_recall_cuenta_acierto_en_cruzada_solo_si_aparecen_todas_las_fuentes() -> None:
    eval_set = EvalSet(
        version="test",
        preguntas=(
            _pregunta(
                "cruzada-1",
                TipoPregunta.CRUZADA,
                ("rgpd:art-17.1", "lopdgdd:art-15.1"),
                "Qué necesita un menor de catorce años para pedir la supresión de sus datos",
            ),
        ),
    )
    recuperador = RecuperadorBM25(UNIDADES, con_ruta=True)

    resultado = evaluar_recall(recuperador, eval_set, k=len(UNIDADES))

    assert resultado.total == 1
    assert resultado.aciertos == 1
    assert resultado.recall == 1.0

    resultado_estrecho = evaluar_recall(recuperador, eval_set, k=1)
    assert resultado_estrecho.aciertos == 0
    assert resultado_estrecho.fallos == ("cruzada-1",)
