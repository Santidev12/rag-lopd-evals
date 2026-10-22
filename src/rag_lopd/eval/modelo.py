"""El eval set como tipo, no como fichero suelto.

Este módulo es el corazón del proyecto. Un eval set que nadie valida se degrada solo: una fuente
que ya no existe, una pregunta que se cuela sin respuesta esperada, un reparto de tipos que se
desequilibra sin que nadie se entere. Aquí cada una de esas cosas es un error de validación.

Las reglas no son caprichos de estilo; cada una viene de un modo de fallo conocido:

- Una pregunta que se contesta con sí o no la acierta la mitad de las veces un sistema roto.
- Una pregunta `fuera_de_corpus` con fuente esperada es una contradicción: si tiene fuente,
  la respuesta está en el corpus.
- Una pregunta `cruzada` con una sola fuente no cruza nada, y era precisamente el tipo que
  tenía que doler.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator

from rag_lopd.model import Identificador


class TipoPregunta(StrEnum):
    """Los cinco tipos del eval set. El desglose por tipo es la mitad del valor de medir."""

    FACTUAL = "factual"
    """Se responde con un solo apartado. Es el suelo del sistema."""

    CRUZADA = "cruzada"
    """Exige reunir dos o más artículos. Donde casi todos los RAG se rompen."""

    TEMPORAL = "temporal"
    """Distingue entre versiones de una norma. Específica de un corpus normativo."""

    FUERA_DE_CORPUS = "fuera_de_corpus"
    """La respuesta no está. El sistema debe abstenerse. La métrica más valiosa."""

    TRAMPA = "trampa"
    """Parece respondible y usa el vocabulario del corpus, pero pide algo que no contiene."""


class Estado(StrEnum):
    """Dónde está una pregunta en la revisión humana."""

    CANDIDATA = "candidata"
    ACEPTADA = "aceptada"
    DESCARTADA = "descartada"


class Dificultad(StrEnum):
    FACIL = "facil"
    MEDIA = "media"
    DIFICIL = "dificil"


#: Los tipos cuya respuesta NO está en el corpus: el sistema debe abstenerse.
SIN_RESPUESTA = {TipoPregunta.FUERA_DE_CORPUS, TipoPregunta.TRAMPA}

#: Reparto objetivo de las 50 preguntas. El 20 % sin respuesta no es decorativo: con menos,
#: la tasa de sobre-respuesta se calcula sobre tan pocos casos que no dice nada.
REPARTO_OBJETIVO = {
    TipoPregunta.FACTUAL: 16,
    TipoPregunta.CRUZADA: 12,
    TipoPregunta.TEMPORAL: 6,
    TipoPregunta.FUERA_DE_CORPUS: 10,
    TipoPregunta.TRAMPA: 6,
}

_BINARIA = re.compile(
    r"^[¿\s]*(es|está|están|puede|pueden|puedo|tiene|tienen|hay|existe|existen|"
    r"se puede|se pueden|debe|deben|debería|deberían|sería|hace falta)\b",
    re.IGNORECASE,
)


class Pregunta(BaseModel):
    """Una fila del eval set."""

    model_config = ConfigDict(frozen=True)

    id: str
    pregunta: str
    tipo: TipoPregunta
    respuesta: str
    fuente: tuple[Identificador, ...] = ()
    dificultad: Dificultad = Dificultad.MEDIA
    estado: Estado = Estado.CANDIDATA
    notas: str = ""
    """El criterio de corrección en los casos limítrofes, y por qué se descartó si se descartó."""

    @model_validator(mode="after")
    def _reglas(self) -> Pregunta:
        if len(self.pregunta.strip()) < 30:
            raise ValueError(f"{self.id}: la pregunta es demasiado vaga ({self.pregunta!r})")
        if _BINARIA.match(self.pregunta.strip()):
            raise ValueError(
                f"{self.id}: se contesta con sí o no, así que la acierta media vez un sistema roto"
            )
        if not self.respuesta.strip():
            raise ValueError(f"{self.id}: sin respuesta esperada no se puede corregir nada")

        if self.tipo in SIN_RESPUESTA:
            if self.fuente:
                raise ValueError(
                    f"{self.id}: una pregunta {self.tipo.value} no puede tener fuente esperada; "
                    "si la tiene, la respuesta sí está en el corpus"
                )
        elif not self.fuente:
            raise ValueError(f"{self.id}: una pregunta {self.tipo.value} necesita fuente esperada")

        if self.tipo is TipoPregunta.CRUZADA and len(self._articulos()) < 2:
            raise ValueError(
                f"{self.id}: una pregunta cruzada debe apoyarse en dos artículos distintos, "
                f"y esta solo toca {len(self._articulos())}"
            )
        return self

    def _articulos(self) -> set[str]:
        return {str(f.unidad_de_contexto) for f in self.fuente}

    @property
    def debe_abstenerse(self) -> bool:
        return self.tipo in SIN_RESPUESTA


class EvalSet(BaseModel):
    """El conjunto de preguntas, con las invariantes que valen para el conjunto y no para una."""

    model_config = ConfigDict(frozen=True)

    version: str
    preguntas: tuple[Pregunta, ...]

    @model_validator(mode="after")
    def _ids_unicos(self) -> EvalSet:
        vistos = [p.id for p in self.preguntas]
        repetidos = {i for i in vistos if vistos.count(i) > 1}
        if repetidos:
            raise ValueError(f"ids repetidos: {sorted(repetidos)}")
        return self

    def aceptadas(self) -> tuple[Pregunta, ...]:
        return tuple(p for p in self.preguntas if p.estado is Estado.ACEPTADA)

    def reparto(self, *, solo_aceptadas: bool = False) -> dict[TipoPregunta, int]:
        fuente = self.aceptadas() if solo_aceptadas else self.preguntas
        return {tipo: sum(1 for p in fuente if p.tipo is tipo) for tipo in TipoPregunta}

    def desviacion_del_objetivo(self) -> dict[TipoPregunta, int]:
        """Cuántas preguntas faltan (positivo) o sobran (negativo) por tipo, entre las aceptadas."""
        actual = self.reparto(solo_aceptadas=True)
        return {tipo: objetivo - actual[tipo] for tipo, objetivo in REPARTO_OBJETIVO.items()}

    def fuentes(self) -> set[str]:
        return {str(f) for p in self.preguntas for f in p.fuente}
