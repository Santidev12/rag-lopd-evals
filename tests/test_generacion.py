"""Tests de la generación: contexto, política de abstención y métricas.

El modelo de lenguaje es un doble que devuelve un texto fijo: lo que se prueba es la política
(qué cuenta como responder, como abstenerse y como romper el formato), no a Gemini.
"""

from __future__ import annotations

import pytest

from rag_lopd.eval.modelo import EvalSet, Pregunta, TipoPregunta
from rag_lopd.generacion.contexto import construir_contexto, contextos_para, indexar_articulos
from rag_lopd.generacion.evaluacion import (
    Observacion,
    Proporcion,
    evaluar_generacion,
    intervalo_wilson,
    resumir,
)
from rag_lopd.generacion.modelo import Completado, Contexto, Estado, Respuesta, Tarifa, Uso
from rag_lopd.generacion.prompt import construir_usuario
from rag_lopd.generacion.responder import responder
from rag_lopd.model import Granularidad, Identificador, UnidadIndexable
from rag_lopd.retrieval.modelo import Resultado


def _unidad(id_texto: str, texto: str, ruta: str = "RGPD · Artículo X") -> UnidadIndexable:
    return UnidadIndexable(
        id=Identificador.parse(id_texto),
        texto=texto,
        granularidad=Granularidad.APARTADO,
        ruta=ruta,
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
        self.usuarios: list[str] = []

    def completar(self, sistema: str, usuario: str) -> Completado:
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
    usuario = construir_usuario("¿plazo?", CONTEXTOS)

    assert "[rgpd:art-33] RGPD · Artículo 33" in usuario
    assert usuario.endswith("PREGUNTA: ¿plazo?")


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
        al_terminar=lambda o: avisos.append(o.pregunta_id),
    )

    assert avisos == ["f-1", "foc-1"]
    assert [str(c) for c in observaciones[0].contextos] == ["rgpd:art-33"]
    # El modelo de mentira responde a todo: acierta la factual y sobre-responde la fuera de corpus.
    assert resumir(observaciones).sobre_respuesta == Proporcion(casos=1, exitos=1)
    assert len(modelo.usuarios) == 2
