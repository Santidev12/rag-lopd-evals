"""Compara la línea base (el «antes») con una o varias pasadas nuevas (el «después»).

La regla de lectura se fijó antes de ver ningún dato (ticket del generador en Azure):

- Las tasas llevan **intervalo de Wilson**, nunca un porcentaje suelto.
- Se enseñan las **preguntas que cambian de estado**, no solo el porcentaje: con n = 50, que una
  tasa se mueva dos puntos es una pregunta.
- La conclusión por defecto es **«sin diferencia demostrable»**. Solo se afirma una diferencia
  cuando los intervalos de las dos pasadas son disjuntos, que con tan pocas preguntas es raro.

Qué cuenta como «acierto de comportamiento»: callar si no hay respuesta en el corpus y contestar si
la hay (lo mismo que `resumir` en su desglose por tipo). El contenido de lo contestado lo mide el
juez, pasada por pasada, con `juzgar`: esta comparación no lo mezcla.

Para saber si una diferencia es del modelo hay que **tener las tres pasadas nuevas**: una pregunta
que cambia en una pasada y no en otra es ruido, no una diferencia, y se marca como `inestable`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from rag_lopd.eval.modelo import TipoPregunta
from rag_lopd.generacion.evaluacion import Observacion, Proporcion, Resumen, resumir
from rag_lopd.generacion.modelo import Estado


@dataclass(frozen=True)
class Pasada:
    nombre: str
    observaciones: list[Observacion]


@dataclass(frozen=True)
class CambioDePregunta:
    pregunta_id: str
    tipo: TipoPregunta
    antes: Estado
    despues: tuple[Estado, ...]
    """Un estado por cada pasada nueva, en el orden en que se pasaron."""

    clasificacion: str
    """`mejora` o `empeora` (el acierto de comportamiento cambia igual en todas las pasadas
    nuevas), o `inestable` (las pasadas nuevas no coinciden entre sí)."""


@dataclass(frozen=True)
class Comparacion:
    antes: Pasada
    despues: tuple[Pasada, ...]
    resumenes: dict[str, Resumen]
    cambios: tuple[CambioDePregunta, ...]
    inestables_entre_pasadas: int
    """Preguntas en las que las pasadas nuevas difieren **en el estado** entre sí (aunque el acierto
    sea el mismo). Mide el ruido del propio modelo nuevo."""

    conclusiones: tuple[str, ...]


def intervalos_se_solapan(a: Proporcion, b: Proporcion) -> bool:
    """¿Se solapan los intervalos de Wilson de dos proporciones? Es una prueba **conservadora**:
    que se solapen no demuestra que no haya diferencia, solo que con este n no se puede afirmar."""
    bajo_a, alto_a = a.intervalo
    bajo_b, alto_b = b.intervalo
    return max(bajo_a, bajo_b) <= min(alto_a, alto_b)


def _acierta(observacion: Observacion) -> bool:
    return observacion.respuesta.se_abstiene == observacion.debe_abstenerse


def comparar(antes: Pasada, despues: list[Pasada]) -> Comparacion:
    if not despues:
        raise ValueError("hace falta al menos una pasada nueva que comparar con el antes.")
    nombres = [antes.nombre, *(p.nombre for p in despues)]
    if len(set(nombres)) != len(nombres):
        raise ValueError(f"los nombres de las pasadas deben ser distintos: {nombres}")

    por_pasada = {p.nombre: {o.pregunta_id: o for o in p.observaciones} for p in [antes, *despues]}
    ids_antes = set(por_pasada[antes.nombre])
    for p in despues:
        if set(por_pasada[p.nombre]) != ids_antes:
            diferencia = sorted(ids_antes ^ set(por_pasada[p.nombre]))
            raise ValueError(
                f"las pasadas no cubren las mismas preguntas ({p.nombre}): difieren {diferencia}"
            )

    cambios: list[CambioDePregunta] = []
    inestables = 0
    for pregunta_id in sorted(ids_antes):
        base = por_pasada[antes.nombre][pregunta_id]
        nuevas = [por_pasada[p.nombre][pregunta_id] for p in despues]
        if len({o.respuesta.estado for o in nuevas}) > 1:
            inestables += 1
        aciertos = {_acierta(o) for o in nuevas}
        if len(aciertos) > 1:
            clasificacion = "inestable"
        else:
            (nuevo,) = aciertos
            if nuevo == _acierta(base):
                continue
            clasificacion = "mejora" if nuevo else "empeora"
        cambios.append(
            CambioDePregunta(
                pregunta_id=pregunta_id,
                tipo=base.tipo,
                antes=base.respuesta.estado,
                despues=tuple(o.respuesta.estado for o in nuevas),
                clasificacion=clasificacion,
            )
        )

    resumenes = {p.nombre: resumir(p.observaciones) for p in [antes, *despues]}
    return Comparacion(
        antes=antes,
        despues=tuple(despues),
        resumenes=resumenes,
        cambios=tuple(cambios),
        inestables_entre_pasadas=inestables,
        conclusiones=_conclusiones(antes, despues, resumenes),
    )


def _conclusiones(
    antes: Pasada, despues: list[Pasada], resumenes: dict[str, Resumen]
) -> tuple[str, ...]:
    metricas: tuple[tuple[str, Callable[[Resumen], Proporcion]], ...] = (
        ("sobre-respuesta", lambda r: r.sobre_respuesta),
        ("abstención indebida", lambda r: r.abstencion_indebida),
    )
    texto: list[str] = []
    for nombre, tasa in metricas:
        base = tasa(resumenes[antes.nombre])
        distintas = [
            p.nombre for p in despues if not intervalos_se_solapan(base, tasa(resumenes[p.nombre]))
        ]
        if distintas:
            texto.append(
                f"{nombre}: hay diferencia entre el antes y {', '.join(distintas)} "
                "(los intervalos de Wilson no se solapan)."
            )
        else:
            texto.append(
                f"{nombre}: sin diferencia demostrable (los intervalos de Wilson del antes y de "
                "todas las pasadas nuevas se solapan)."
            )
    texto.append(
        "Que los intervalos se solapen no prueba que no haya diferencia: con tan pocas preguntas "
        "no se puede distinguir un efecto pequeño del azar."
    )
    return tuple(texto)


def formatear(comparacion: Comparacion) -> str:
    """El informe de la comparación en Markdown: pegable en un README o en un ticket."""
    pasadas = [comparacion.antes, *comparacion.despues]
    columnas = [p.nombre for p in pasadas]

    def fila(titulo: str, celda: Callable[[Resumen], str]) -> str:
        return (
            "| " + " | ".join([titulo, *(celda(comparacion.resumenes[n]) for n in columnas)]) + " |"
        )

    def latencia(resumen: Resumen, tramo: str) -> str:
        valor = {
            "total": resumen.latencia,
            "recuperar": resumen.latencia_recuperacion,
            "generar": resumen.latencia_generacion,
        }[tramo]
        return str(valor) if valor is not None else "sin medir"

    lineas = [
        f"Antes: {comparacion.antes.nombre} ({len(comparacion.antes.observaciones)} preguntas)",
        f"Después: {len(comparacion.despues)} pasada(s): "
        + ", ".join(p.nombre for p in comparacion.despues),
        "",
        "| Métrica | " + " | ".join(columnas) + " |",
        "| --- | " + " | ".join("---" for _ in columnas) + " |",
        fila("Sobre-respuesta (menos es mejor)", lambda r: str(r.sobre_respuesta)),
        fila("Abstención indebida (menos es mejor)", lambda r: str(r.abstencion_indebida)),
        fila("Cita cubre la fuente", lambda r: str(r.cita_cubre_fuente)),
        fila("Bloqueadas por el filtro", lambda r: str(r.bloqueadas)),
        fila("Latencia de extremo a extremo", lambda r: latencia(r, "total")),
        fila("  recuperar", lambda r: latencia(r, "recuperar")),
        fila("  generar", lambda r: latencia(r, "generar")),
        "",
    ]
    if comparacion.cambios:
        lineas.append("Preguntas que cambian de estado respecto al antes:")
        for c in comparacion.cambios:
            despues = ", ".join(e.value for e in c.despues)
            lineas.append(
                f"- {c.pregunta_id} ({c.tipo.value}): {c.antes.value} -> {despues} "
                f"[{c.clasificacion}]"
            )
    else:
        lineas.append("Ninguna pregunta cambia de estado respecto al antes.")
    if len(comparacion.despues) > 1:
        lineas.append(
            f"\nEstabilidad entre las pasadas nuevas: {comparacion.inestables_entre_pasadas} de "
            f"{len(comparacion.antes.observaciones)} preguntas cambian de estado entre una pasada "
            "y otra."
        )
    lineas.append("")
    lineas.extend(comparacion.conclusiones)
    return "\n".join(lineas) + "\n"
