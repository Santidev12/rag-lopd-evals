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

    @property
    def debe_abstenerse(self) -> bool:
        return self.tipo in SIN_RESPUESTA

    @property
    def fuente_articulos(self) -> set[str]:
        return {str(f.unidad_de_contexto) for f in self.fuente}


def evaluar_generacion(
    modelo: ModeloDeLenguaje,
    recuperador: Recuperador,
    indice: IndiceArticulos,
    eval_set: EvalSet,
    *,
    k: int = 10,
    prompt: Prompt = PROMPT_POR_DEFECTO,
    al_terminar: Callable[[Observacion], None] | None = None,
) -> list[Observacion]:
    """Recupera, genera y registra, para las preguntas aceptadas, de una en una.

    `al_terminar` se llama con cada observación en cuanto está lista: quien lo pasa puede guardarla
    al momento, de modo que una caída a mitad de pasada no tire a la basura las respuestas ya
    pagadas.
    """
    observaciones: list[Observacion] = []
    for pregunta in eval_set.aceptadas():
        contextos = contextos_para(recuperador.buscar(pregunta.pregunta, k=k), indice)
        observacion = Observacion(
            pregunta_id=pregunta.id,
            tipo=pregunta.tipo,
            fuente=pregunta.fuente,
            contextos=tuple(c.id for c in contextos),
            respuesta=responder(modelo, pregunta.pregunta, contextos, prompt),
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
    )
