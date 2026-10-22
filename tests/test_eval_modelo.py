"""Las reglas del eval set, sin corpus ni red.

Cada regla existe por un modo de fallo concreto, y cada test nombra cuál.
"""

import pytest
from pydantic import ValidationError

from rag_lopd.eval.modelo import REPARTO_OBJETIVO, Estado, EvalSet, Pregunta, TipoPregunta

BASE = dict(
    id="e-001",
    pregunta="¿En qué plazo debe notificarse una brecha a la autoridad de control?",
    tipo=TipoPregunta.FACTUAL,
    respuesta="72 horas desde que se tiene constancia.",
    fuente=("rgpd:art-33.1",),
)


def test_una_pregunta_bien_formada_se_construye() -> None:
    pregunta = Pregunta(**BASE)

    assert str(pregunta.fuente[0]) == "rgpd:art-33.1"
    assert pregunta.estado is Estado.CANDIDATA
    assert pregunta.debe_abstenerse is False


def test_se_rechaza_una_pregunta_de_si_o_no() -> None:
    # Un sistema roto acierta la mitad de estas por puro azar: no miden nada.
    with pytest.raises(ValidationError, match="sí o no"):
        Pregunta(**BASE | {"pregunta": "¿Es obligatorio notificar una brecha a la autoridad?"})


def test_se_rechaza_una_pregunta_vaga() -> None:
    with pytest.raises(ValidationError, match="demasiado vaga"):
        Pregunta(**BASE | {"pregunta": "¿Qué dice el RGPD?"})


def test_una_pregunta_sin_respuesta_en_el_corpus_no_puede_tener_fuente() -> None:
    # Si tiene fuente esperada, la respuesta sí está en el corpus: es una contradicción.
    with pytest.raises(ValidationError, match="no puede tener fuente"):
        Pregunta(**BASE | {"tipo": TipoPregunta.FUERA_DE_CORPUS})


def test_una_pregunta_respondible_necesita_fuente() -> None:
    # Sin fuente no se puede medir el retrieval por separado de la generación.
    with pytest.raises(ValidationError, match="necesita fuente"):
        Pregunta(**BASE | {"fuente": ()})


def test_una_cruzada_con_un_solo_articulo_no_cruza_nada() -> None:
    with pytest.raises(ValidationError, match="dos artículos distintos"):
        Pregunta(**BASE | {"tipo": TipoPregunta.CRUZADA, "fuente": ("rgpd:art-33.1",)})


def test_dos_apartados_del_mismo_articulo_no_hacen_una_cruzada() -> None:
    # 83.4 y 83.5 son apartados hermanos: recuperarlos no exige cruzar documentos.
    with pytest.raises(ValidationError, match="dos artículos distintos"):
        Pregunta(
            **BASE | {"tipo": TipoPregunta.CRUZADA, "fuente": ("rgpd:art-83.4", "rgpd:art-83.5")}
        )


def test_una_cruzada_entre_dos_normas_es_valida() -> None:
    pregunta = Pregunta(
        **BASE
        | {
            "pregunta": "¿Qué edad de consentimiento aplica España frente a la del reglamento?",
            "tipo": TipoPregunta.CRUZADA,
            "fuente": ("rgpd:art-8.1", "lopdgdd:art-7.1"),
        }
    )

    assert len(pregunta.fuente) == 2


def test_no_se_admiten_ids_repetidos() -> None:
    with pytest.raises(ValidationError, match="ids repetidos"):
        EvalSet(version="v", preguntas=(Pregunta(**BASE), Pregunta(**BASE)))


def test_el_reparto_objetivo_suma_cincuenta() -> None:
    # Si alguien toca el reparto, que sea a propósito y no por descuido.
    assert sum(REPARTO_OBJETIVO.values()) == 50
    assert REPARTO_OBJETIVO[TipoPregunta.FUERA_DE_CORPUS] == 10, "el 20 % sin respuesta es el suelo"


def test_la_desviacion_cuenta_lo_que_falta_por_aceptar() -> None:
    eval_set = EvalSet(version="v", preguntas=(Pregunta(**BASE | {"estado": Estado.ACEPTADA}),))

    assert eval_set.desviacion_del_objetivo()[TipoPregunta.FACTUAL] == 15
