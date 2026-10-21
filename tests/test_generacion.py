"""Tests de la generación: contexto, política de abstención y métricas.

El modelo de lenguaje es un doble que devuelve un texto fijo: lo que se prueba es la política
(qué cuenta como responder, como abstenerse y como romper el formato), no a Gemini.
"""

from __future__ import annotations

from datetime import date

import pytest

from rag_lopd.eval.modelo import EvalSet, Pregunta, TipoPregunta
from rag_lopd.generacion.contexto import construir_contexto, contextos_para, indexar_articulos
from rag_lopd.generacion.evaluacion import (
    Observacion,
    Proporcion,
    evaluar_generacion,
    intervalo_wilson,
    percentil,
    realinear,
    resumir,
)
from rag_lopd.generacion.modelo import (
    Completado,
    Contexto,
    Estado,
    RedaccionAnterior,
    Respuesta,
    Tarifa,
    Uso,
)
from rag_lopd.generacion.prompt import PROMPT_POR_DEFECTO, PROMPTS, V1, V2, prompt_de
from rag_lopd.generacion.responder import responder
from rag_lopd.model import Granularidad, Identificador, UnidadIndexable
from rag_lopd.retrieval.modelo import Resultado


def _unidad(
    id_texto: str,
    texto: str,
    ruta: str = "RGPD · Artículo X",
    *,
    desde: date | None = None,
    hasta: date | None = None,
) -> UnidadIndexable:
    return UnidadIndexable(
        id=Identificador.parse(id_texto),
        texto=texto,
        granularidad=Granularidad.APARTADO,
        ruta=ruta,
        vigente_desde=desde,
        vigente_hasta=hasta,
    )


def _resultado(id_texto: str) -> Resultado:
    return Resultado(id=Identificador.parse(id_texto), score=0.5, texto="", ruta="")


class _Modelo:
    """Devuelve siempre el mismo texto y apunta qué se le pidió."""

    nombre = "doble"
    tarifa = Tarifa(entrada_usd_mtok=1.0, salida_usd_mtok=1.0)

    def __init__(self, texto: str, uso: Uso | None = None) -> None:
        self._texto = texto
        self._uso = uso or Uso(tokens_entrada=10, tokens_salida=5)
        self.sistemas: list[str] = []
        self.usuarios: list[str] = []

    def completar(self, sistema: str, usuario: str) -> Completado:
        self.sistemas.append(sistema)
        self.usuarios.append(usuario)
        return Completado(texto=self._texto, uso=self._uso)


CONTEXTOS = [
    Contexto(id=Identificador.parse("rgpd:art-33"), ruta="RGPD · Artículo 33", texto="plazo 72 h"),
    Contexto(id=Identificador.parse("rgpd:art-34"), ruta="RGPD · Artículo 34", texto="afectados"),
]


# --- contexto: small-to-big -------------------------------------------------------------------


def test_construir_contexto_reune_los_apartados_del_articulo_con_su_numero() -> None:
    unidades = [_unidad("rgpd:art-33.1", "uno"), _unidad("rgpd:art-33.2", "dos")]

    contexto = construir_contexto(unidades)

    assert str(contexto.id) == "rgpd:art-33"
    assert contexto.texto == "(1) uno\n(2) dos"


def test_un_articulo_sin_partir_va_tal_cual() -> None:
    contexto = construir_contexto([_unidad("lopdgdd:art-5", "texto entero")])

    assert contexto.texto == "texto entero"


def test_contextos_para_entrega_el_articulo_entero_sin_repetir_y_en_orden() -> None:
    corpus = [
        _unidad("rgpd:art-33.1", "a"),
        _unidad("rgpd:art-33.2", "b"),
        _unidad("rgpd:art-34.1", "c"),
    ]
    indice = indexar_articulos(corpus)
    # Se recuperan dos apartados del 33 y uno del 34: el 33 sale una vez, con TODOS sus apartados.
    resultados = [
        _resultado("rgpd:art-33.2"),
        _resultado("rgpd:art-34.1"),
        _resultado("rgpd:art-33.1"),
    ]

    contextos = contextos_para(resultados, indice)

    assert [str(c.id) for c in contextos] == ["rgpd:art-33", "rgpd:art-34"]
    assert "(1) a" in contextos[0].texto
    assert "(2) b" in contextos[0].texto


def test_contextos_para_salta_lo_que_no_esta_en_el_indice() -> None:
    assert contextos_para([_resultado("rgpd:art-99.1")], indexar_articulos([])) == []


def test_el_prompt_lleva_los_articulos_con_su_identificador_y_la_pregunta() -> None:
    usuario = V1.usuario("¿plazo?", CONTEXTOS)

    assert "[rgpd:art-33] RGPD · Artículo 33" in usuario
    assert usuario.endswith("PREGUNTA: ¿plazo?")


# --- contexto: vigencia y redacciones anteriores -------------------------------------------------

_ANTES = date(2018, 12, 7)
_CAMBIO = date(2023, 5, 10)


def _articulo_modificado() -> list[UnidadIndexable]:
    """Como el art. 67 de la LOPDGDD: la redacción antigua y la vigente conviven en el corpus, y
    la antigua puede aparecer antes en el orden de lectura."""
    return [
        _unidad("lopdgdd:art-67.1", "antes 1", desde=_ANTES, hasta=_CAMBIO),
        _unidad("lopdgdd:art-67.2", "doce meses", desde=_ANTES, hasta=_CAMBIO),
        _unidad("lopdgdd:art-67.1", "ahora 1", desde=_CAMBIO),
        _unidad("lopdgdd:art-67.2", "dieciocho meses", desde=_CAMBIO),
    ]


def test_el_contexto_separa_la_redaccion_vigente_de_las_anteriores() -> None:
    contexto = construir_contexto(_articulo_modificado())

    assert contexto.texto == "(1) ahora 1\n(2) dieciocho meses"  # nada de la derogada se cuela
    assert contexto.vigente_desde == _CAMBIO
    assert contexto.anteriores == (
        RedaccionAnterior(desde=_ANTES, hasta=_CAMBIO, texto="(1) antes 1\n(2) doce meses"),
    )


def test_las_redacciones_anteriores_salen_de_la_mas_antigua_a_la_mas_reciente() -> None:
    unidades = [
        _unidad("lopdgdd:art-2.1", "v2", desde=date(2020, 1, 1), hasta=date(2021, 1, 1)),
        _unidad("lopdgdd:art-2.1", "v1", desde=date(2018, 1, 1), hasta=date(2020, 1, 1)),
        _unidad("lopdgdd:art-2.1", "v3", desde=date(2021, 1, 1)),
    ]

    contexto = construir_contexto(unidades)

    assert [a.texto for a in contexto.anteriores] == ["(1) v1", "(1) v2"]


def test_un_articulo_sin_modificar_no_tiene_redacciones_anteriores() -> None:
    contexto = construir_contexto([_unidad("rgpd:art-33.1", "uno", desde=date(2016, 5, 4))])

    assert contexto.anteriores == ()
    assert contexto.vigente_desde == date(2016, 5, 4)


def test_un_articulo_sin_redaccion_vigente_no_se_puede_presentar() -> None:
    derogada = [_unidad("lopdgdd:art-9.1", "x", desde=_ANTES, hasta=_CAMBIO)]

    with pytest.raises(ValueError, match="no tiene redacción vigente"):
        construir_contexto(derogada)


def test_contextos_para_con_historia_entrega_un_solo_articulo() -> None:
    indice = indexar_articulos(_articulo_modificado())

    contextos = contextos_para([_resultado("lopdgdd:art-67.2")], indice)

    assert len(contextos) == 1
    assert len(contextos[0].anteriores) == 1


def test_v1_no_enseña_la_vigencia_ni_las_redacciones_anteriores() -> None:
    contexto = construir_contexto(_articulo_modificado())

    usuario = V1.usuario("¿cuánto duran?", [contexto])

    assert "dieciocho meses" in usuario
    assert "doce meses" not in usuario
    assert "Redacción" not in usuario


def test_v2_enseña_desde_cuando_rige_y_la_redaccion_anterior_con_su_periodo() -> None:
    contexto = construir_contexto(_articulo_modificado())

    usuario = V2.usuario("¿cuánto duran?", [contexto])

    assert "Redacción vigente desde 2023-05-10:\n(1) ahora 1\n(2) dieciocho meses" in usuario
    assert (
        "Redacción anterior, vigente desde 2018-12-07 hasta 2023-05-10:\n"
        "(1) antes 1\n(2) doce meses"
    ) in usuario
    # Lo vigente va antes que lo anterior: es lo que debe pesar por defecto.
    assert usuario.index("dieciocho meses") < usuario.index("doce meses")


def test_v2_sin_fecha_de_vigencia_no_inventa_una() -> None:
    contexto = Contexto(id=Identificador.parse("rgpd:art-33"), ruta="RGPD", texto="x")

    usuario = V2.usuario("q", [contexto])

    assert "Redacción vigente desde" not in usuario
    assert "[rgpd:art-33] RGPD\nx" in usuario


def test_solo_v2_explica_la_vigencia_en_las_instrucciones() -> None:
    assert "Redacción anterior" not in V1.sistema
    assert "Redacción anterior" in V2.sistema
    # v2 es v1 más una regla: lo demás no se toca, así la diferencia entre pasadas es solo esa.
    assert V2.sistema.startswith(V1.sistema.split("\nDevuelve únicamente")[0])


def test_prompt_de_resuelve_las_versiones_y_rechaza_las_desconocidas() -> None:
    assert prompt_de("v1") is V1
    assert set(PROMPTS) == {"v1", "v2"}
    with pytest.raises(ValueError, match="no hay prompt 'v9'"):
        prompt_de("v9")


# --- responder: la política --------------------------------------------------------------------


def test_responde_con_cita_valida() -> None:
    modelo = _Modelo('{"sin_respuesta": false, "respuesta": "72 horas", "citas": ["rgpd:art-33"]}')

    respuesta = responder(modelo, "plazo", CONTEXTOS)

    assert respuesta.estado is Estado.RESPONDE
    assert respuesta.texto == "72 horas"
    assert [str(c) for c in respuesta.citas] == ["rgpd:art-33"]
    assert respuesta.uso == Uso(tokens_entrada=10, tokens_salida=5)


def test_sin_respuesta_es_abstencion_aunque_traiga_texto_y_citas() -> None:
    modelo = _Modelo(
        '{"sin_respuesta": true, "respuesta": "creo que...", "citas": ["rgpd:art-33"]}'
    )

    respuesta = responder(modelo, "q", CONTEXTOS)

    assert respuesta.estado is Estado.ABSTIENE
    assert respuesta.se_abstiene
    assert respuesta.citas == ()


def test_una_cita_inventada_se_descarta_y_sin_ninguna_valida_cuenta_como_abstencion() -> None:
    modelo = _Modelo('{"sin_respuesta": false, "respuesta": "x", "citas": ["rgpd:art-99"]}')

    respuesta = responder(modelo, "q", CONTEXTOS)

    assert respuesta.estado is Estado.SIN_CITA_VALIDA
    assert respuesta.se_abstiene
    assert respuesta.citas == ()
    assert respuesta.citas_descartadas == ("rgpd:art-99",)


def test_las_citas_validas_se_conservan_y_las_inventadas_se_apartan() -> None:
    modelo = _Modelo(
        '{"sin_respuesta": false, "respuesta": "x", '
        '"citas": ["rgpd:art-33", "rgpd:art-99", "basura"]}'
    )

    respuesta = responder(modelo, "q", CONTEXTOS)

    assert respuesta.estado is Estado.RESPONDE
    assert [str(c) for c in respuesta.citas] == ["rgpd:art-33"]
    assert respuesta.citas_descartadas == ("rgpd:art-99", "basura")


def test_una_cita_a_un_apartado_se_reduce_a_su_articulo() -> None:
    modelo = _Modelo('{"sin_respuesta": false, "respuesta": "x", "citas": ["rgpd:art-33.1"]}')

    respuesta = responder(modelo, "q", CONTEXTOS)

    assert [str(c) for c in respuesta.citas] == ["rgpd:art-33"]


def test_una_cita_repetida_cuenta_una_vez() -> None:
    modelo = _Modelo(
        '{"sin_respuesta": false, "respuesta": "x", "citas": ["rgpd:art-33", "rgpd:art-33.1"]}'
    )

    assert len(responder(modelo, "q", CONTEXTOS).citas) == 1


@pytest.mark.parametrize(
    "texto",
    [
        "no es json",
        "",
        '{"respuesta": "falta sin_respuesta"}',
        '{"sin_respuesta": false, "respuesta": "", "citas": ["rgpd:art-33"]}',
    ],
)
def test_lo_que_no_es_el_json_pedido_es_salida_invalida_no_abstencion_ni_respuesta(
    texto: str,
) -> None:
    respuesta = responder(_Modelo(texto), "q", CONTEXTOS)

    assert respuesta.estado is Estado.SALIDA_INVALIDA
    assert respuesta.se_abstiene


def test_responder_usa_el_prompt_que_se_le_pide() -> None:
    modelo = _Modelo('{"sin_respuesta": true, "respuesta": "", "citas": []}')

    responder(modelo, "q", CONTEXTOS, V1)
    responder(modelo, "q", CONTEXTOS, V2)
    responder(modelo, "q", CONTEXTOS)

    assert modelo.sistemas == [V1.sistema, V2.sistema, PROMPT_POR_DEFECTO.sistema]
    assert PROMPT_POR_DEFECTO is V2


def test_acepta_el_json_envuelto_en_una_valla_de_codigo() -> None:
    texto = '```json\n{"sin_respuesta": true, "respuesta": "", "citas": []}\n```'

    assert responder(_Modelo(texto), "q", CONTEXTOS).estado is Estado.ABSTIENE


# --- métricas -----------------------------------------------------------------------------------


def _obs(
    id_: str,
    tipo: TipoPregunta,
    estado: Estado,
    *,
    fuente: tuple[str, ...] = (),
    contextos: tuple[str, ...] = (),
    citas: tuple[str, ...] = (),
) -> Observacion:
    return Observacion(
        pregunta_id=id_,
        tipo=tipo,
        fuente=tuple(Identificador.parse(f) for f in fuente),
        contextos=tuple(Identificador.parse(c) for c in contextos),
        respuesta=Respuesta(
            estado=estado,
            citas=tuple(Identificador.parse(c) for c in citas),
            uso=Uso(tokens_entrada=100, tokens_salida=10),
        ),
    )


def test_resumir_separa_sobre_respuesta_de_abstencion_indebida() -> None:
    observaciones = [
        # Sin respuesta en el corpus: una contesta (mal), una calla (bien).
        _obs("foc-1", TipoPregunta.FUERA_DE_CORPUS, Estado.RESPONDE, citas=("rgpd:art-1",)),
        _obs("tr-1", TipoPregunta.TRAMPA, Estado.ABSTIENE),
        # Con respuesta: una contesta (bien), una calla (mal).
        _obs(
            "f-1",
            TipoPregunta.FACTUAL,
            Estado.RESPONDE,
            fuente=("rgpd:art-33.1",),
            citas=("rgpd:art-33",),
        ),
        _obs("f-2", TipoPregunta.FACTUAL, Estado.ABSTIENE, fuente=("rgpd:art-34.1",)),
    ]

    resumen = resumir(observaciones)

    assert resumen.sobre_respuesta == Proporcion(casos=2, exitos=1)
    assert resumen.abstencion_indebida == Proporcion(casos=2, exitos=1)
    assert resumen.comportamiento_por_tipo[TipoPregunta.FACTUAL] == Proporcion(casos=2, exitos=1)
    assert resumen.comportamiento_por_tipo[TipoPregunta.TRAMPA] == Proporcion(casos=1, exitos=1)
    assert resumen.uso == Uso(tokens_entrada=400, tokens_salida=40)


def test_sin_cita_valida_y_salida_invalida_cuentan_como_callarse_en_las_metricas() -> None:
    observaciones = [
        _obs("tr-1", TipoPregunta.TRAMPA, Estado.SIN_CITA_VALIDA),
        _obs("tr-2", TipoPregunta.TRAMPA, Estado.SALIDA_INVALIDA),
    ]

    resumen = resumir(observaciones)

    assert resumen.sobre_respuesta == Proporcion(casos=2, exitos=0)
    assert resumen.salidas_invalidas == 1


def test_contexto_completo_separa_fallos_de_retrieval_de_fallos_de_generacion() -> None:
    observaciones = [
        # El artículo llegó al modelo y aun así calló: fallo de generación.
        _obs(
            "f-1",
            TipoPregunta.FACTUAL,
            Estado.ABSTIENE,
            fuente=("rgpd:art-33.1",),
            contextos=("rgpd:art-33",),
        ),
        # El artículo ni llegó: fallo de retrieval, ningún prompt lo arregla.
        _obs(
            "f-2",
            TipoPregunta.FACTUAL,
            Estado.ABSTIENE,
            fuente=("rgpd:art-34.1",),
            contextos=("rgpd:art-5",),
        ),
    ]

    assert resumir(observaciones).contexto_completo == Proporcion(casos=2, exitos=1)


def test_cita_cubre_fuente_exige_todos_los_articulos_en_una_cruzada() -> None:
    observaciones = [
        _obs(
            "c-1",
            TipoPregunta.CRUZADA,
            Estado.RESPONDE,
            fuente=("rgpd:art-12.3", "lopdgdd:art-32.1"),
            citas=("rgpd:art-12",),
        ),
        _obs(
            "c-2",
            TipoPregunta.CRUZADA,
            Estado.RESPONDE,
            fuente=("rgpd:art-12.3", "lopdgdd:art-32.1"),
            citas=("rgpd:art-12", "lopdgdd:art-32"),
        ),
    ]

    assert resumir(observaciones).cita_cubre_fuente == Proporcion(casos=2, exitos=1)


def test_intervalo_de_wilson() -> None:
    bajo, alto = intervalo_wilson(0, 17)
    assert bajo == 0.0
    assert 0.15 < alto < 0.2  # con 0 de 17 el techo no es 0: no se puede descartar un fallo raro

    bajo, alto = intervalo_wilson(5, 10)
    assert bajo < 0.5 < alto
    assert intervalo_wilson(0, 0) == (0.0, 1.0)


# --- la pasada entera ---------------------------------------------------------------------------


class _RecuperadorFijo:
    def __init__(self, resultados: list[Resultado]) -> None:
        self._resultados = resultados

    def buscar(self, consulta: str, *, k: int = 10) -> list[Resultado]:
        return self._resultados[:k]


def _pregunta(id_: str, tipo: TipoPregunta, texto: str, fuente: tuple[str, ...] = ()) -> Pregunta:
    return Pregunta(
        id=id_,
        pregunta=texto,
        tipo=tipo,
        respuesta="una respuesta cualquiera, aquí no se evalúa",
        fuente=tuple(Identificador.parse(f) for f in fuente),
        estado="aceptada",
    )


def test_evaluar_generacion_recorre_las_aceptadas_y_avisa_de_cada_una() -> None:
    corpus = [_unidad("rgpd:art-33.1", "72 horas")]
    eval_set = EvalSet(
        version="test",
        preguntas=(
            _pregunta(
                "f-1",
                TipoPregunta.FACTUAL,
                "En qué plazo debe notificarse una violación de seguridad",
                ("rgpd:art-33.1",),
            ),
            _pregunta(
                "foc-1", TipoPregunta.FUERA_DE_CORPUS, "Qué sanción impuso la AEPD a tal empresa"
            ),
        ),
    )
    modelo = _Modelo('{"sin_respuesta": false, "respuesta": "72 h", "citas": ["rgpd:art-33"]}')
    avisos: list[str] = []

    observaciones = evaluar_generacion(
        modelo,
        _RecuperadorFijo([_resultado("rgpd:art-33.1")]),
        indexar_articulos(corpus),
        eval_set,
        prompt=V2,
        al_terminar=lambda o: avisos.append(o.pregunta_id),
    )

    assert avisos == ["f-1", "foc-1"]
    assert [str(c) for c in observaciones[0].contextos] == ["rgpd:art-33"]
    # El modelo de mentira responde a todo: acierta la factual y sobre-responde la fuera de corpus.
    assert resumir(observaciones).sobre_respuesta == Proporcion(casos=1, exitos=1)
    assert len(modelo.usuarios) == 2
    assert set(modelo.sistemas) == {V2.sistema}


def test_evaluar_generacion_mide_la_latencia_de_cada_consulta() -> None:
    corpus = [_unidad("rgpd:art-33.1", "72 horas")]
    eval_set = EvalSet(
        version="test",
        preguntas=(
            _pregunta(
                "f-1",
                TipoPregunta.FACTUAL,
                "En qué plazo debe notificarse una violación de seguridad",
                ("rgpd:art-33.1",),
            ),
            _pregunta(
                "f-2",
                TipoPregunta.FACTUAL,
                "Quién debe notificar una violación de seguridad a la autoridad",
                ("rgpd:art-33.1",),
            ),
        ),
    )
    # Dos lecturas del reloj por pregunta: la primera tarda 1,5 s y la segunda 3 s.
    lecturas = iter([10.0, 11.5, 20.0, 23.0])

    observaciones = evaluar_generacion(
        _Modelo('{"sin_respuesta": true}'),
        _RecuperadorFijo([_resultado("rgpd:art-33.1")]),
        indexar_articulos(corpus),
        eval_set,
        reloj=lambda: next(lecturas),
    )

    assert [o.latencia_s for o in observaciones] == [1.5, 3.0]
    latencia = resumir(observaciones).latencia
    assert latencia is not None
    assert (latencia.consultas, latencia.p50_s) == (2, 2.25)


def test_una_pasada_guardada_sin_latencia_se_resume_sin_inventarla() -> None:
    sin_medir = _obs("f-1", TipoPregunta.FACTUAL, Estado.RESPONDE)

    assert sin_medir.latencia_s is None
    assert resumir([sin_medir]).latencia is None


def test_percentil_interpola_y_rechaza_lo_vacio() -> None:
    assert percentil([1.0, 2.0, 3.0, 4.0], 50) == 2.5
    assert percentil([1.0, 2.0, 3.0, 4.0], 95) == pytest.approx(3.85)
    assert percentil([7.0], 95) == 7.0
    with pytest.raises(ValueError):
        percentil([], 50)


# --- realinear con el eval set --------------------------------------------------------------------


def _eval_con(*preguntas: Pregunta) -> EvalSet:
    return EvalSet(version="test", preguntas=preguntas)


def _pregunta_factual(id_: str) -> Pregunta:
    return Pregunta(
        id=id_,
        pregunta="¿Cuánto cuesta presentar una reclamación ante la autoridad de control?",
        tipo=TipoPregunta.FACTUAL,
        respuesta="Nada: es gratuito para el interesado.",
        fuente=(Identificador.parse("rgpd:art-57.3"),),
        estado="aceptada",  # type: ignore[arg-type]
    )


def test_realinear_toma_tipo_y_fuente_del_eval_set_actual_y_no_toca_lo_que_hizo_el_modelo() -> None:
    vieja = _obs("e-1", TipoPregunta.TRAMPA, Estado.RESPONDE, contextos=("rgpd:art-57",))

    (nueva,) = realinear([vieja], _eval_con(_pregunta_factual("e-1")))

    assert nueva.tipo is TipoPregunta.FACTUAL
    assert nueva.fuente == (Identificador.parse("rgpd:art-57.3"),)
    assert not nueva.debe_abstenerse
    assert nueva.respuesta == vieja.respuesta
    assert nueva.contextos == vieja.contextos


def test_realinear_cambia_las_cifras_de_sobre_respuesta() -> None:
    observaciones = [
        _obs("e-1", TipoPregunta.TRAMPA, Estado.RESPONDE),
        _obs("e-2", TipoPregunta.FUERA_DE_CORPUS, Estado.ABSTIENE),
    ]
    antes = resumir(observaciones)
    despues = resumir(realinear(observaciones, _eval_con(_pregunta_factual("e-1"), _fuera("e-2"))))

    assert (antes.sobre_respuesta.exitos, antes.sobre_respuesta.casos) == (1, 2)
    assert (despues.sobre_respuesta.exitos, despues.sobre_respuesta.casos) == (0, 1)


def test_realinear_rechaza_una_pasada_con_preguntas_que_ya_no_existen() -> None:
    with pytest.raises(ValueError, match="e-9"):
        realinear([_obs("e-9", TipoPregunta.TRAMPA, Estado.ABSTIENE)], _eval_con())


def _fuera(id_: str) -> Pregunta:
    return Pregunta(
        id=id_,
        pregunta="¿Qué opina la jurisprudencia del Tribunal Supremo sobre este asunto concreto?",
        tipo=TipoPregunta.FUERA_DE_CORPUS,
        respuesta="Debe abstenerse: el corpus no contiene jurisprudencia.",
        estado="aceptada",  # type: ignore[arg-type]
    )
