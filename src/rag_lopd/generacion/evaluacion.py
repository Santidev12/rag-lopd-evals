"""Mide la política de abstención contra el eval set: sobre-respuesta y abstención indebida.

Las dos métricas que el README promete en negrita, y las dos al revés de lo que parece:

- **Sobre-respuesta**: de las preguntas que NO tienen respuesta en el corpus (`fuera_de_corpus` y
  `trampa`), cuántas contesta el sistema en vez de callarse. Es el fallo grave.
- **Abstención indebida**: de las que SÍ la tienen, cuántas calla. Es el precio de ser prudente.

Cada pregunta produce una `Observacion` que se puede guardar y volver a resumir sin repetir la
llamada al modelo (que cuesta dinero): `resumir` solo mira lo guardado.

Esto no mide si el contenido de una respuesta es correcto (eso exige un juez y es el ticket del
harness completo): mide si el sistema responde cuando debe y si lo que cita cubre la fuente
esperada.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from rag_lopd.eval.modelo import SIN_RESPUESTA, EvalSet, TipoPregunta
from rag_lopd.generacion.contexto import IndiceArticulos, contextos_para
from rag_lopd.generacion.modelo import Estado, ModeloDeLenguaje, Respuesta, Uso
from rag_lopd.generacion.prompt import PROMPT_POR_DEFECTO, Prompt
from rag_lopd.generacion.responder import responder
from rag_lopd.model import Identificador
from rag_lopd.retrieval.modelo import Recuperador


class Observacion(BaseModel):
    """Lo que pasó con una pregunta: qué se le dio al modelo y qué hizo con ello.

    Lleva copiado lo que `resumir` necesita de la pregunta (tipo y fuente) para que un fichero de
    observaciones guardado se pueda resumir solo, sin volver a cargar el eval set.
    """

    model_config = ConfigDict(frozen=True)

    pregunta_id: str
    tipo: TipoPregunta
    fuente: tuple[Identificador, ...]
    contextos: tuple[Identificador, ...]
    """Los artículos que se le dieron al modelo, en orden de recuperación."""

    respuesta: Respuesta

    latencia_s: float | None = None
    """Segundos de la consulta de extremo a extremo (recuperar + generar). `None` en las pasadas
    guardadas antes de que se midiera."""

    latencia_recuperacion_s: float | None = None
    """Parte de `latencia_s` que se va en recuperar: embeber la consulta por la API, buscar y
    armar los artículos. `None` si la pasada es anterior al desglose."""

    latencia_generacion_s: float | None = None
    """Parte de `latencia_s` que se va en el modelo generador, con sus reintentos. `None` si la
    pasada es anterior al desglose."""

    @property
    def debe_abstenerse(self) -> bool:
        return self.tipo in SIN_RESPUESTA

    @property
    def fuente_articulos(self) -> set[str]:
        return {str(f.unidad_de_contexto) for f in self.fuente}


def realinear(observaciones: list[Observacion], eval_set: EvalSet) -> list[Observacion]:
    """Pone en cada observación el tipo y la fuente que la pregunta tiene HOY en el eval set.

    Una observación guarda lo que el modelo hizo (contexto, respuesta, coste), que no cambia, pero
    también una copia del tipo y la fuente de la pregunta de ese día. Si después se corrige la
    pregunta (una referencia errónea, un tipo mal puesto), esa copia queda vieja y las cifras
    saldrían contra un eval set que ya no existe. Realinear evita repetir la pasada, y pagarla,
    por un cambio que no afecta a lo que el modelo contestó.
    """
    por_id = {p.id: p for p in eval_set.preguntas}
    desconocidas = sorted(o.pregunta_id for o in observaciones if o.pregunta_id not in por_id)
    if desconocidas:
        raise ValueError(f"preguntas de la pasada que no están en el eval set: {desconocidas}")
    return [
        o.model_copy(
            update={"tipo": por_id[o.pregunta_id].tipo, "fuente": por_id[o.pregunta_id].fuente}
        )
        for o in observaciones
    ]


def evaluar_generacion(
    modelo: ModeloDeLenguaje,
    recuperador: Recuperador,
    indice: IndiceArticulos,
    eval_set: EvalSet,
    *,
    k: int = 10,
    prompt: Prompt = PROMPT_POR_DEFECTO,
    al_terminar: Callable[[Observacion], None] | None = None,
    reloj: Callable[[], float] = time.perf_counter,
) -> list[Observacion]:
    """Recupera, genera y registra, para las preguntas aceptadas, de una en una.

    `al_terminar` se llama con cada observación en cuanto está lista: quien lo pasa puede guardarla
    al momento, de modo que una caída a mitad de pasada no tire a la basura las respuestas ya
    pagadas. `reloj` mide la latencia de cada consulta (embeber, buscar y generar, con sus
    reintentos); se puede inyectar para probarlo sin esperar.
    """
    observaciones: list[Observacion] = []
    for pregunta in eval_set.aceptadas():
        inicio = reloj()
        contextos = contextos_para(recuperador.buscar(pregunta.pregunta, k=k), indice)
        tras_recuperar = reloj()
        respuesta = responder(modelo, pregunta.pregunta, contextos, prompt)
        fin = reloj()
        observacion = Observacion(
            pregunta_id=pregunta.id,
            tipo=pregunta.tipo,
            fuente=pregunta.fuente,
            contextos=tuple(c.id for c in contextos),
            respuesta=respuesta,
            latencia_s=fin - inicio,
            latencia_recuperacion_s=tras_recuperar - inicio,
            latencia_generacion_s=fin - tras_recuperar,
        )
        observaciones.append(observacion)
        if al_terminar is not None:
            al_terminar(observacion)
    return observaciones


def intervalo_wilson(exitos: int, total: int, *, z: float = 1.96) -> tuple[float, float]:
    """Intervalo de confianza del 95 % para una proporción. Wilson y no el normal de libro de
    texto: con 17 o 33 casos y proporciones cerca de 0 o 1, el normal se sale de [0, 1]."""
    if total == 0:
        return (0.0, 1.0)
    p = exitos / total
    denominador = 1 + z**2 / total
    centro = (p + z**2 / (2 * total)) / denominador
    margen = z * math.sqrt(p * (1 - p) / total + z**2 / (4 * total**2)) / denominador
    return (max(0.0, centro - margen), min(1.0, centro + margen))


def percentil(valores: list[float], p: float) -> float:
    """Percentil `p` (0-100) con interpolación lineal entre los dos valores vecinos, igual que el
    método por defecto de numpy. Con pocos datos, el p95 es casi el máximo: se reporta junto al
    número de consultas para que se sepa."""
    if not valores:
        raise ValueError("no hay valores de los que sacar un percentil")
    ordenados = sorted(valores)
    posicion = (len(ordenados) - 1) * p / 100
    bajo = math.floor(posicion)
    alto = min(bajo + 1, len(ordenados) - 1)
    return ordenados[bajo] + (ordenados[alto] - ordenados[bajo]) * (posicion - bajo)


@dataclass(frozen=True)
class Latencia:
    consultas: int
    p50_s: float
    p95_s: float

    def __str__(self) -> str:
        return f"p50 {self.p50_s:.2f} s · p95 {self.p95_s:.2f} s ({self.consultas} consultas)"


@dataclass(frozen=True)
class Proporcion:
    casos: int
    exitos: int

    @property
    def valor(self) -> float:
        return self.exitos / self.casos if self.casos else 0.0

    @property
    def intervalo(self) -> tuple[float, float]:
        return intervalo_wilson(self.exitos, self.casos)

    def __str__(self) -> str:
        bajo, alto = self.intervalo
        return f"{self.exitos}/{self.casos} = {self.valor:.1%} (IC 95 %: {bajo:.0%} a {alto:.0%})"


@dataclass(frozen=True)
class Resumen:
    sobre_respuesta: Proporcion
    """Sin respuesta en el corpus, y el sistema contesta. Menos es mejor."""

    abstencion_indebida: Proporcion
    """Con respuesta en el corpus, y el sistema calla. Menos es mejor."""

    contexto_completo: Proporcion
    """De las respondibles, cuántas recibieron en el contexto todos los artículos de su fuente.
    Separa los fallos de retrieval de los de generación: si el artículo no llegó, ningún prompt
    lo arregla."""

    cita_cubre_fuente: Proporcion
    """De las respondibles que el sistema contestó, cuántas citan todos los artículos de su
    fuente esperada."""

    comportamiento_por_tipo: dict[TipoPregunta, Proporcion]
    """Por tipo, en cuántas hizo lo correcto: callar si no hay respuesta, contestar si la hay."""

    salidas_invalidas: int
    """Veces que el modelo no devolvió el JSON pedido. Si no es cero, hay un problema de formato
    que contamina las demás cifras."""

    uso: Uso

    latencia: Latencia | None = None
    """De extremo a extremo, solo con las observaciones que la midieron. `None` si ninguna."""

    latencia_recuperacion: Latencia | None = None
    latencia_generacion: Latencia | None = None
    """El desglose de `latencia`, solo con las observaciones que lo midieron."""


def resumir(observaciones: list[Observacion]) -> Resumen:
    sin_respuesta = [o for o in observaciones if o.debe_abstenerse]
    con_respuesta = [o for o in observaciones if not o.debe_abstenerse]
    contestadas = [o for o in con_respuesta if o.respuesta.responde]

    por_tipo: dict[TipoPregunta, Proporcion] = {}
    for tipo in TipoPregunta:
        del_tipo = [o for o in observaciones if o.tipo is tipo]
        bien = sum(1 for o in del_tipo if o.respuesta.se_abstiene == o.debe_abstenerse)
        por_tipo[tipo] = Proporcion(casos=len(del_tipo), exitos=bien)

    uso = Uso()
    for o in observaciones:
        uso = uso + o.respuesta.uso

    def latencia_de(tiempos: list[float]) -> Latencia | None:
        if not tiempos:
            return None
        return Latencia(
            consultas=len(tiempos), p50_s=percentil(tiempos, 50), p95_s=percentil(tiempos, 95)
        )

    return Resumen(
        sobre_respuesta=Proporcion(
            casos=len(sin_respuesta),
            exitos=sum(1 for o in sin_respuesta if o.respuesta.responde),
        ),
        abstencion_indebida=Proporcion(
            casos=len(con_respuesta),
            exitos=sum(1 for o in con_respuesta if o.respuesta.se_abstiene),
        ),
        contexto_completo=Proporcion(
            casos=len(con_respuesta),
            exitos=sum(
                1 for o in con_respuesta if o.fuente_articulos <= {str(c) for c in o.contextos}
            ),
        ),
        cita_cubre_fuente=Proporcion(
            casos=len(contestadas),
            exitos=sum(
                1 for o in contestadas if o.fuente_articulos <= {str(c) for c in o.respuesta.citas}
            ),
        ),
        comportamiento_por_tipo=por_tipo,
        salidas_invalidas=sum(
            1 for o in observaciones if o.respuesta.estado is Estado.SALIDA_INVALIDA
        ),
        uso=uso,
        latencia=latencia_de([o.latencia_s for o in observaciones if o.latencia_s is not None]),
        latencia_recuperacion=latencia_de(
            [
                o.latencia_recuperacion_s
                for o in observaciones
                if o.latencia_recuperacion_s is not None
            ]
        ),
        latencia_generacion=latencia_de(
            [o.latencia_generacion_s for o in observaciones if o.latencia_generacion_s is not None]
        ),
    )
