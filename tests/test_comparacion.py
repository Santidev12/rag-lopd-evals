"""Tests de la comparación antes/después: qué cambia de estado, qué es estable entre pasadas y qué
se concluye (por defecto, nada)."""

from __future__ import annotations

import pytest

from rag_lopd.eval.modelo import TipoPregunta
from rag_lopd.generacion.comparacion import Pasada, comparar, formatear, intervalos_se_solapan
from rag_lopd.generacion.evaluacion import Observacion, Proporcion
from rag_lopd.generacion.modelo import Estado, Respuesta, Uso
from rag_lopd.model import Identificador

F, FOC = TipoPregunta.FACTUAL, TipoPregunta.FUERA_DE_CORPUS


def _obs(
    id_: str, tipo: TipoPregunta, estado: Estado, latencia: float | None = None
) -> Observacion:
    articulo = Identificador.parse("rgpd:art-33")
    con_respuesta = tipo not in {FOC, TipoPregunta.TRAMPA}
    return Observacion(
        pregunta_id=id_,
        tipo=tipo,
        fuente=(Identificador.parse("rgpd:art-33.1"),) if con_respuesta else (),
        contextos=(articulo,),
        respuesta=Respuesta(
            estado=estado,
            citas=(articulo,) if estado is Estado.RESPONDE else (),
            uso=Uso(tokens_entrada=100, tokens_salida=10),
        ),
        latencia_s=latencia,
    )


def _pasada(nombre: str, estados: dict[str, Estado], latencia: float | None = None) -> Pasada:
    tipos = {"e-1": F, "e-2": F, "e-3": FOC, "e-4": FOC}
    return Pasada(
        nombre=nombre,
        observaciones=[_obs(i, tipos[i], e, latencia) for i, e in estados.items()],
    )


ANTES = _pasada(
    "gemini",
    {
        "e-1": Estado.RESPONDE,  # bien
        "e-2": Estado.ABSTIENE,  # abstención indebida
        "e-3": Estado.ABSTIENE,  # bien
        "e-4": Estado.RESPONDE,  # sobre-respuesta
    },
)


def test_una_pregunta_que_mejora_en_todas_las_pasadas_nuevas_se_marca_como_mejora() -> None:
    p1 = _pasada(
        "azure-1",
        {
            "e-1": Estado.RESPONDE,
            "e-2": Estado.RESPONDE,
            "e-3": Estado.ABSTIENE,
            "e-4": Estado.RESPONDE,
        },
    )
    p2 = _pasada(
        "azure-2",
        {
            "e-1": Estado.RESPONDE,
            "e-2": Estado.RESPONDE,
            "e-3": Estado.ABSTIENE,
            "e-4": Estado.RESPONDE,
        },
    )

    comparacion = comparar(ANTES, [p1, p2])

    cambios = {c.pregunta_id: c.clasificacion for c in comparacion.cambios}
    assert cambios == {"e-2": "mejora"}


def test_una_pregunta_que_empeora_se_marca_como_empeora() -> None:
    p1 = _pasada(
        "azure-1",
        {
            "e-1": Estado.ABSTIENE,
            "e-2": Estado.ABSTIENE,
            "e-3": Estado.ABSTIENE,
            "e-4": Estado.RESPONDE,
        },
    )

    comparacion = comparar(ANTES, [p1])

    assert {c.pregunta_id: c.clasificacion for c in comparacion.cambios} == {"e-1": "empeora"}


def test_si_las_pasadas_nuevas_no_coinciden_entre_si_la_pregunta_es_inestable() -> None:
    p1 = _pasada(
        "azure-1",
        {
            "e-1": Estado.RESPONDE,
            "e-2": Estado.RESPONDE,
            "e-3": Estado.ABSTIENE,
            "e-4": Estado.RESPONDE,
        },
    )
    p2 = _pasada(
        "azure-2",
        {
            "e-1": Estado.RESPONDE,
            "e-2": Estado.ABSTIENE,
            "e-3": Estado.ABSTIENE,
            "e-4": Estado.RESPONDE,
        },
    )

    comparacion = comparar(ANTES, [p1, p2])

    assert {c.pregunta_id: c.clasificacion for c in comparacion.cambios} == {"e-2": "inestable"}
    assert comparacion.inestables_entre_pasadas == 1


def test_un_bloqueo_cuenta_como_callarse_en_la_comparacion() -> None:
    p1 = _pasada(
        "azure-1",
        {
            "e-1": Estado.RESPONDE,
            "e-2": Estado.BLOQUEADO,
            "e-3": Estado.BLOQUEADO,
            "e-4": Estado.RESPONDE,
        },
    )

    comparacion = comparar(ANTES, [p1])

    assert comparacion.resumenes["azure-1"].bloqueadas == 2
    assert comparacion.cambios == ()  # e-2 sigue siendo abstención indebida y e-3 callar bien


def test_con_pocas_preguntas_los_intervalos_se_solapan_y_no_se_concluye_diferencia() -> None:
    p1 = _pasada(
        "azure-1",
        {
            "e-1": Estado.RESPONDE,
            "e-2": Estado.RESPONDE,
            "e-3": Estado.ABSTIENE,
            "e-4": Estado.ABSTIENE,
        },
    )

    comparacion = comparar(ANTES, [p1])

    assert any("sin diferencia demostrable" in c for c in comparacion.conclusiones)


def test_con_muchos_casos_y_efecto_enorme_si_se_dice_que_hay_diferencia() -> None:
    def trampas(estado: Estado) -> Pasada:
        return Pasada(
            nombre=estado.value,
            observaciones=[_obs(f"t-{i}", TipoPregunta.TRAMPA, estado) for i in range(60)],
        )

    comparacion = comparar(trampas(Estado.RESPONDE), [trampas(Estado.ABSTIENE)])

    assert any(
        "sobre-respuesta" in c and "diferencia" in c and "sin diferencia" not in c
        for c in comparacion.conclusiones
    )


def test_los_intervalos_de_wilson_se_solapan_o_no() -> None:
    assert intervalos_se_solapan(Proporcion(casos=16, exitos=1), Proporcion(casos=16, exitos=3))
    assert not intervalos_se_solapan(
        Proporcion(casos=60, exitos=60), Proporcion(casos=60, exitos=0)
    )


def test_las_pasadas_tienen_que_cubrir_las_mismas_preguntas() -> None:
    incompleta = _pasada("azure-1", {"e-1": Estado.RESPONDE, "e-2": Estado.RESPONDE})

    with pytest.raises(ValueError, match="mismas preguntas"):
        comparar(ANTES, [incompleta])


def test_sin_pasadas_nuevas_no_hay_nada_que_comparar() -> None:
    with pytest.raises(ValueError, match="al menos una"):
        comparar(ANTES, [])


def test_el_texto_enseña_las_tasas_los_cambios_y_la_latencia() -> None:
    antes = _pasada(
        "gemini",
        {
            "e-1": Estado.RESPONDE,
            "e-2": Estado.ABSTIENE,
            "e-3": Estado.ABSTIENE,
            "e-4": Estado.RESPONDE,
        },
        latencia=2.0,
    )
    p1 = _pasada(
        "azure-1",
        {
            "e-1": Estado.RESPONDE,
            "e-2": Estado.RESPONDE,
            "e-3": Estado.ABSTIENE,
            "e-4": Estado.RESPONDE,
        },
        latencia=1.0,
    )

    texto = formatear(comparar(antes, [p1]))

    assert "gemini" in texto and "azure-1" in texto
    assert "Sobre-respuesta" in texto and "Abstención indebida" in texto
    assert "e-2" in texto and "mejora" in texto
    assert "2,0 s" in texto or "2.00 s" in texto
    assert "sin diferencia demostrable" in texto
