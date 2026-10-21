"""Tests del juez: el modelo es un doble que devuelve un texto fijo. Lo que se prueba es la rúbrica
que llega al modelo, cómo se lee su salida y las cuentas, no a DeepSeek."""

from __future__ import annotations

import json

import pytest

from rag_lopd.eval.modelo import EvalSet, Pregunta, TipoPregunta
from rag_lopd.generacion.evaluacion import Observacion, Proporcion
from rag_lopd.generacion.juez import (
    SISTEMA,
    Acuerdo,
    Etiqueta,
    Juicio,
    Veredicto,
    calibrar,
    construir_usuario,
    juzgar,
    juzgar_pasada,
    leer_etiquetas,
    leer_juicios,
    resumir_juicios,
    texto_de_fuente,
)
from rag_lopd.generacion.modelo import Completado, Estado, Respuesta, Tarifa, Uso
from rag_lopd.model import Granularidad, Identificador, UnidadIndexable


def _unidad(id_texto: str, texto: str, *, hasta: str | None = None) -> UnidadIndexable:
    from datetime import date

    return UnidadIndexable(
        id=Identificador.parse(id_texto),
        texto=texto,
        granularidad=Granularidad.APARTADO,
        ruta="RGPD",
        vigente_hasta=date.fromisoformat(hasta) if hasta else None,
    )


def _pregunta(
    id_: str,
    tipo: TipoPregunta,
    *,
    respuesta: str = "72 horas",
    fuente: tuple[str, ...] = ("rgpd:art-33.1",),
    notas: str = "",
) -> Pregunta:
    sin_respuesta = tipo in {TipoPregunta.FUERA_DE_CORPUS, TipoPregunta.TRAMPA}
    return Pregunta(
        id=id_,
        pregunta="¿En qué plazo debe notificarse una violación de seguridad a la autoridad?",
        tipo=tipo,
        respuesta="Debe abstenerse: no hay tasa." if sin_respuesta else respuesta,
        fuente=() if sin_respuesta else tuple(Identificador.parse(f) for f in fuente),
        estado="aceptada",  # type: ignore[arg-type]
        notas=notas,
    )


class _Juez:
    nombre = "juez-doble"
    tarifa = Tarifa(entrada_usd_mtok=1.0, salida_usd_mtok=1.0)

    def __init__(self, *textos: str) -> None:
        self._textos = list(textos)
        self.sistemas: list[str] = []
        self.usuarios: list[str] = []

    def completar(self, sistema: str, usuario: str) -> Completado:
        self.sistemas.append(sistema)
        self.usuarios.append(usuario)
        texto = self._textos.pop(0) if len(self._textos) > 1 else self._textos[0]
        return Completado(texto=texto, uso=Uso(tokens_entrada=100, tokens_salida=10))


def _salida(veredicto: str, motivo: str = "porque sí") -> str:
    return json.dumps({"motivo": motivo, "veredicto": veredicto})


CORPUS = [_unidad("rgpd:art-33.1", "La notificación será en 72 horas.")]


# --- el mensaje que ve el juez ------------------------------------------------------------------


def test_caso_a_lleva_la_referencia_el_texto_de_la_norma_y_la_respuesta() -> None:
    pregunta = _pregunta("f-1", TipoPregunta.FACTUAL)

    usuario = construir_usuario(pregunta, texto_de_fuente(pregunta, CORPUS), "Son 72 horas")

    assert "CASO: A" in usuario
    assert "RESPUESTA DE REFERENCIA: 72 horas" in usuario
    assert "[rgpd:art-33.1] La notificación será en 72 horas." in usuario
    assert usuario.endswith("RESPUESTA DEL SISTEMA: Son 72 horas")


def test_caso_b_no_lleva_texto_de_norma_porque_no_hay_fuente() -> None:
    pregunta = _pregunta("tr-1", TipoPregunta.TRAMPA)

    usuario = construir_usuario(pregunta, texto_de_fuente(pregunta, CORPUS), "Una tasa de 10 €")

    assert "CASO: B" in usuario
    assert "TEXTO DE LA NORMA" not in usuario
    assert "RESPUESTA DE REFERENCIA: Debe abstenerse" in usuario


def test_las_notas_del_revisor_llegan_al_juez_solo_si_existen() -> None:
    con = _pregunta("f-1", TipoPregunta.FACTUAL, notas="El bloqueo es propio de la ley española.")
    sin = _pregunta("f-2", TipoPregunta.FACTUAL)

    assert "CRITERIO DEL REVISOR: El bloqueo" in construir_usuario(con, "", "x")
    assert "CRITERIO DEL REVISOR" not in construir_usuario(sin, "", "x")


def test_el_texto_de_la_fuente_cae_al_articulo_si_el_apartado_no_esta_partido() -> None:
    corpus = [_unidad("rgpd:art-33", "Artículo sin partir.")]  # el corpus no tiene el .1
    pregunta = _pregunta("f-1", TipoPregunta.FACTUAL, fuente=("rgpd:art-33.1",))

    assert "Artículo sin partir." in texto_de_fuente(pregunta, corpus)


def test_el_texto_de_la_fuente_es_solo_el_vigente_y_no_se_repite() -> None:
    corpus = [
        _unidad("rgpd:art-33.1", "antigua", hasta="2023-05-10"),
        _unidad("rgpd:art-33.1", "vigente"),
    ]
    pregunta = _pregunta("f-1", TipoPregunta.FACTUAL, fuente=("rgpd:art-33.1", "rgpd:art-33.1"))

    texto = texto_de_fuente(pregunta, corpus)

    assert "vigente" in texto
    assert "antigua" not in texto
    assert texto.count("[rgpd:art-33.1]") == 1


def test_la_rubrica_pide_razonar_antes_de_decidir_y_no_juzgar_las_citas() -> None:
    assert SISTEMA.index('"motivo"') < SISTEMA.index('"veredicto"')
    assert "No juzgues las citas" in SISTEMA


# --- leer lo que dice el juez -------------------------------------------------------------------


@pytest.mark.parametrize("veredicto", ["correcta", "parcial", "incorrecta"])
def test_juzgar_lee_los_tres_veredictos_y_el_motivo(veredicto: str) -> None:
    juez = _Juez(_salida(veredicto, "da el plazo"))

    juicio = juzgar(juez, _pregunta("f-1", TipoPregunta.FACTUAL), "72 h", CORPUS)

    assert juicio.veredicto is Veredicto(veredicto)
    assert juicio.motivo == "da el plazo"
    assert juicio.uso == Uso(tokens_entrada=100, tokens_salida=10)
    assert juez.sistemas == [SISTEMA]


def test_acepta_mayusculas_y_la_valla_de_codigo() -> None:
    juez = _Juez('```json\n{"motivo": "ok", "veredicto": " Correcta "}\n```')

    assert juzgar(juez, _pregunta("f-1", TipoPregunta.FACTUAL), "x", CORPUS).veredicto is (
        Veredicto.CORRECTA
    )


@pytest.mark.parametrize(
    "texto",
    ["no es json", "", '{"motivo": "x"}', '{"motivo": "x", "veredicto": "quizá"}'],
)
def test_lo_que_no_es_el_json_pedido_es_invalido_no_incorrecta(texto: str) -> None:
    juicio = juzgar(_Juez(texto), _pregunta("f-1", TipoPregunta.FACTUAL), "x", CORPUS)

    assert juicio.veredicto is Veredicto.INVALIDO


# --- la pasada ----------------------------------------------------------------------------------


def _obs(id_: str, tipo: TipoPregunta, estado: Estado, texto: str = "una respuesta") -> Observacion:
    sin_respuesta = tipo in {TipoPregunta.FUERA_DE_CORPUS, TipoPregunta.TRAMPA}
    return Observacion(
        pregunta_id=id_,
        tipo=tipo,
        fuente=() if sin_respuesta else (Identificador.parse("rgpd:art-33.1"),),
        contextos=(),
        respuesta=Respuesta(estado=estado, texto=texto if estado is Estado.RESPONDE else ""),
    )


def _eval_set(*preguntas: Pregunta) -> EvalSet:
    return EvalSet(version="test", preguntas=preguntas)


def test_solo_se_juzga_lo_que_el_sistema_contesto() -> None:
    observaciones = [
        _obs("f-1", TipoPregunta.FACTUAL, Estado.RESPONDE),
        _obs("f-2", TipoPregunta.FACTUAL, Estado.ABSTIENE),
    ]
    eval_set = _eval_set(
        _pregunta("f-1", TipoPregunta.FACTUAL), _pregunta("f-2", TipoPregunta.FACTUAL)
    )
    juez = _Juez(_salida("correcta"))

    juicios = juzgar_pasada(juez, observaciones, eval_set, CORPUS)

    assert set(juicios) == {"f-1"}
    assert len(juez.usuarios) == 1


def test_lo_ya_juzgado_no_se_vuelve_a_pagar_pero_un_juicio_invalido_si_se_repite() -> None:
    observaciones = [
        _obs("f-1", TipoPregunta.FACTUAL, Estado.RESPONDE),
        _obs("f-2", TipoPregunta.FACTUAL, Estado.RESPONDE),
    ]
    eval_set = _eval_set(
        _pregunta("f-1", TipoPregunta.FACTUAL), _pregunta("f-2", TipoPregunta.FACTUAL)
    )
    previos = {
        "f-1": Juicio(pregunta_id="f-1", tipo=TipoPregunta.FACTUAL, veredicto=Veredicto.PARCIAL),
        "f-2": Juicio(pregunta_id="f-2", tipo=TipoPregunta.FACTUAL, veredicto=Veredicto.INVALIDO),
    }
    juez = _Juez(_salida("correcta"))
    avisados: list[str] = []

    juicios = juzgar_pasada(
        juez, observaciones, eval_set, CORPUS, previos=previos,
        al_terminar=lambda j: avisados.append(j.pregunta_id),
    )  # fmt: skip

    assert avisados == ["f-2"]
    assert juicios["f-1"].veredicto is Veredicto.PARCIAL  # intacto
    assert juicios["f-2"].veredicto is Veredicto.CORRECTA  # repetido


def test_un_juicio_hecho_con_otro_tipo_de_pregunta_se_repite() -> None:
    """e-047 se juzgó como trampa (contra 'debe abstenerse') y luego se corrigió a factual: aquel
    veredicto es de otra pregunta y no puede reutilizarse."""
    observaciones = [_obs("f-1", TipoPregunta.FACTUAL, Estado.RESPONDE)]
    eval_set = _eval_set(_pregunta("f-1", TipoPregunta.FACTUAL))
    previos = {
        "f-1": Juicio(pregunta_id="f-1", tipo=TipoPregunta.TRAMPA, veredicto=Veredicto.INCORRECTA)
    }
    juez = _Juez(_salida("correcta"))

    juicios = juzgar_pasada(juez, observaciones, eval_set, CORPUS, previos=previos)

    assert len(juez.usuarios) == 1
    assert juicios["f-1"].veredicto is Veredicto.CORRECTA
    assert juicios["f-1"].tipo is TipoPregunta.FACTUAL


# --- las cuentas --------------------------------------------------------------------------------


def _juicio(id_: str, tipo: TipoPregunta, veredicto: Veredicto) -> Juicio:
    return Juicio(
        pregunta_id=id_,
        tipo=tipo,
        veredicto=veredicto,
        uso=Uso(tokens_entrada=100, tokens_salida=5),
    )


def test_la_exactitud_cuenta_callar_como_fallo_y_la_de_las_contestadas_no() -> None:
    f, c = TipoPregunta.FACTUAL, TipoPregunta.CRUZADA
    observaciones = [
        _obs("f-1", f, Estado.RESPONDE),
        _obs("f-2", f, Estado.RESPONDE),
        _obs("f-3", f, Estado.ABSTIENE),
        _obs("c-1", c, Estado.RESPONDE),
    ]
    juicios = {
        "f-1": _juicio("f-1", f, Veredicto.CORRECTA),
        "f-2": _juicio("f-2", f, Veredicto.INCORRECTA),
        "c-1": _juicio("c-1", c, Veredicto.PARCIAL),
    }

    resumen = resumir_juicios(observaciones, juicios)

    assert resumen.exactitud == Proporcion(casos=4, exitos=1)
    assert resumen.exactitud_de_las_contestadas == Proporcion(casos=3, exitos=1)
    assert (resumen.parciales, resumen.incorrectas) == (1, 1)
    assert resumen.exactitud_por_tipo[f] == Proporcion(casos=3, exitos=1)
    assert resumen.exactitud_por_tipo[c] == Proporcion(casos=1, exitos=0)
    assert TipoPregunta.TRAMPA not in resumen.exactitud_por_tipo
    assert resumen.uso == Uso(tokens_entrada=300, tokens_salida=15)


def test_la_sobre_respuesta_grave_son_las_que_afirman_algo_sin_base() -> None:
    t = TipoPregunta.TRAMPA
    observaciones = [
        _obs("t-1", t, Estado.RESPONDE),
        _obs("t-2", t, Estado.RESPONDE),
        _obs("t-3", t, Estado.ABSTIENE),
    ]
    juicios = {
        "t-1": _juicio("t-1", t, Veredicto.INCORRECTA),
        "t-2": _juicio("t-2", t, Veredicto.CORRECTA),
    }

    resumen = resumir_juicios(observaciones, juicios)

    assert resumen.sobre_respuesta_grave == Proporcion(casos=2, exitos=1)


def test_un_juicio_invalido_no_cuenta_como_correcto_y_se_avisa() -> None:
    f = TipoPregunta.FACTUAL
    resumen = resumir_juicios(
        [_obs("f-1", f, Estado.RESPONDE)], {"f-1": _juicio("f-1", f, Veredicto.INVALIDO)}
    )

    assert resumen.exactitud == Proporcion(casos=1, exitos=0)
    assert resumen.juicios_invalidos == 1


# --- calibración --------------------------------------------------------------------------------


def _calibracion(pares: list[tuple[Veredicto, Veredicto]]) -> Acuerdo:
    juicios = {
        f"p-{i}": _juicio(f"p-{i}", TipoPregunta.FACTUAL, juez) for i, (_, juez) in enumerate(pares)
    }
    etiquetas = [Etiqueta(pregunta_id=f"p-{i}", veredicto=e) for i, (e, _) in enumerate(pares)]
    return calibrar(juicios, etiquetas)


def test_acuerdo_total_da_kappa_uno() -> None:
    C, P, I = Veredicto.CORRECTA, Veredicto.PARCIAL, Veredicto.INCORRECTA  # noqa: E741
    acuerdo = _calibracion([(C, C), (C, C), (P, P), (I, I)])

    assert acuerdo.coinciden == 4
    assert acuerdo.kappa == pytest.approx(1.0)
    assert acuerdo.discrepancias == ()


def test_el_kappa_desenmascara_un_acuerdo_alto_que_es_solo_azar() -> None:
    C, I = Veredicto.CORRECTA, Veredicto.INCORRECTA  # noqa: E741
    # El juez dice "correcta" siempre; 9 de 10 etiquetas lo son: acuerdo bruto 90 %, kappa 0.
    acuerdo = _calibracion([(C, C)] * 9 + [(I, C)])

    assert acuerdo.bruto == Proporcion(casos=10, exitos=9)
    assert acuerdo.kappa == pytest.approx(0.0)


def test_el_acuerdo_binario_no_castiga_confundir_parcial_con_incorrecta() -> None:
    C, P, I = Veredicto.CORRECTA, Veredicto.PARCIAL, Veredicto.INCORRECTA  # noqa: E741
    acuerdo = _calibracion([(P, I), (C, C), (C, P)])

    assert acuerdo.coinciden == 1
    assert acuerdo.coinciden_en_correcta == 2
    assert [d.pregunta_id for d in acuerdo.discrepancias] == ["p-0", "p-2"]


def test_calibrar_solo_compara_lo_que_ambos_han_visto() -> None:
    juicios = {"a": _juicio("a", TipoPregunta.FACTUAL, Veredicto.CORRECTA)}
    etiquetas = [
        Etiqueta(pregunta_id="a", veredicto=Veredicto.CORRECTA),
        Etiqueta(pregunta_id="b", veredicto=Veredicto.CORRECTA),  # el juez no la vio
    ]

    assert calibrar(juicios, etiquetas).casos == 1


def test_los_ficheros_de_juicios_y_etiquetas_se_leen() -> None:
    juicio = _juicio("f-1", TipoPregunta.FACTUAL, Veredicto.CORRECTA)

    assert leer_juicios(juicio.model_dump_json() + "\n") == {"f-1": juicio}
    etiquetas = leer_etiquetas('{"pregunta_id": "f-1", "veredicto": "parcial", "nota": "x"}\n')
    assert etiquetas == [Etiqueta(pregunta_id="f-1", veredicto=Veredicto.PARCIAL, nota="x")]
