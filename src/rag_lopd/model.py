"""El modelo de datos del corpus.

Aquí vive, en forma de tipos, la decisión del ADR 0001: se indexa el **apartado** (unidad
indexable) y se le entrega al generador el **artículo** completo (unidad de contexto).

El objetivo de este módulo es que una violación de esa decisión sea un error de validación,
no un bug silencioso que aparezca tres semanas después en los números del eval set.
"""

from __future__ import annotations

import re
from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, model_serializer, model_validator


class TipoDivision(StrEnum):
    """Las divisiones que puede tener una norma.

    Las resoluciones de la AEPD (v1) usan FUNDAMENTO en lugar de ARTICULO.
    """

    ARTICULO = "art"
    DISPOSICION_ADICIONAL = "da"
    DISPOSICION_TRANSITORIA = "dt"
    DISPOSICION_DEROGATORIA = "dd"
    DISPOSICION_FINAL = "df"
    ANEXO = "anexo"
    CONSIDERANDO = "cons"
    FUNDAMENTO = "fd"


class Granularidad(StrEnum):
    """A qué nivel se pudo partir el texto.

    `ARTICULO` no es un error: es lo que pasa cuando la LOPDGDD no se deja partir por regex
    (el BOE no marca los apartados). Se guarda para poder medir después si esas unidades se
    recuperan peor que las partidas.
    """

    APARTADO = "apartado"
    ARTICULO = "articulo"


_PATRON_ID = re.compile(
    r"^(?P<norma>[a-z0-9][a-z0-9-]*)"
    r":(?P<tipo>art|da|dt|dd|df|anexo|cons|fd)"
    r"-(?P<numero>\d+(?:bis|ter|quater)?)"
    r"(?:\.(?P<apartado>\d+[a-z]?))?$"
)


class Identificador(BaseModel):
    """La referencia estable de una unidad del corpus: `rgpd:art-33.1`.

    Es **semántico, no posicional**: no depende de en qué chunk cayó el texto, así que
    sobrevive a cualquier cambio de la estrategia de troceo. Si fuese un índice de chunk,
    el día que cambiásemos el chunking el eval set entero dejaría de valer.

    Se comporta como una cadena allí donde importa: acepta un `str` al validar y se serializa
    de vuelta a `str`, de modo que en el JSONL del corpus y en el eval set se lee
    `"rgpd:art-33.1"` y no un objeto anidado.
    """

    model_config = ConfigDict(frozen=True)

    norma: str
    tipo: TipoDivision
    numero: str
    apartado: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _aceptar_cadena(cls, valor: Any) -> Any:
        if not isinstance(valor, str):
            return valor
        encaje = _PATRON_ID.match(valor)
        if encaje is None:
            raise ValueError(
                f"identificador mal formado: {valor!r}. "
                "Se espera <norma>:<tipo>-<numero>[.<apartado>], por ejemplo 'rgpd:art-33.1'."
            )
        return encaje.groupdict()

    def __str__(self) -> str:
        base = f"{self.norma}:{self.tipo.value}-{self.numero}"
        return f"{base}.{self.apartado}" if self.apartado is not None else base

    @model_serializer
    def _serializar(self) -> str:
        return str(self)

    @property
    def unidad_de_contexto(self) -> Identificador:
        """El identificador del artículo que contiene este apartado.

        Es el salto *small-to-big* del ADR 0001, escrito una sola vez y en un solo sitio.
        """
        return Identificador(norma=self.norma, tipo=self.tipo, numero=self.numero)

    @classmethod
    def parse(cls, texto: str) -> Identificador:
        return cls.model_validate(texto)


class UnidadIndexable(BaseModel):
    """Lo que se convierte en un vector y lo que el buscador devuelve.

    Normalmente un apartado; un artículo entero cuando no se pudo partir.
    """

    model_config = ConfigDict(frozen=True)

    id: Identificador
    texto: str
    granularidad: Granularidad
    ruta: str
    """Ruta jerárquica legible: 'RGPD · Capítulo IV · Sección 2 · Artículo 33'."""

    vigente_desde: date | None = None
    vigente_hasta: date | None = None
    """`None` significa vigente. La ingesta conserva las versiones antiguas; el índice solo lleva
    las vigentes, pero el eval set necesita las antiguas para las preguntas de tipo `temporal`."""

    eli: str | None = None
    """Identificador oficial europeo, cuando la fuente lo da. Metadato, nunca la clave primaria."""

    @property
    def vigente(self) -> bool:
        return self.vigente_hasta is None

    @property
    def texto_para_embeber(self) -> str:
        """El texto con su ruta jerárquica delante.

        Reproduce el efecto del *contextual retrieval* de Anthropic sin coste de LLM: el contexto
        que allí se genera con un modelo, aquí ya lo conocemos por la estructura del documento.
        """
        return f"{self.ruta}\n\n{self.texto}"


class Articulo(BaseModel):
    """La unidad de contexto: lo que entra en el prompt cuando se recupera una de sus unidades."""

    model_config = ConfigDict(frozen=True)

    id: Identificador
    titulo: str
    ruta: str
    texto: str
    unidades: tuple[UnidadIndexable, ...]

    @model_validator(mode="after")
    def _las_unidades_pertenecen_a_este_articulo(self) -> Articulo:
        if self.id.apartado is not None:
            raise ValueError(f"un artículo no puede tener apartado en su id: {self.id}")
        for unidad in self.unidades:
            if unidad.id.unidad_de_contexto != self.id:
                raise ValueError(
                    f"la unidad {unidad.id} no pertenece al artículo {self.id}: "
                    "su unidad de contexto es "
                    f"{unidad.id.unidad_de_contexto}"
                )
        return self


class Norma(BaseModel):
    """Un texto legal completo: el RGPD, la LOPDGDD."""

    model_config = ConfigDict(frozen=True)

    slug: str
    """El prefijo que aparece en los identificadores: 'rgpd', 'lopdgdd'."""

    titulo: str
    identificador_oficial: str
    """CELEX para EUR-Lex ('02016R0679-20160504'), identificador BOE para el BOE."""

    eli: str | None = None
    fecha_consolidacion: date | None = None
    articulos: tuple[Articulo, ...] = ()

    def unidades_vigentes(self) -> list[UnidadIndexable]:
        """Lo único que se indexa en la v0."""
        return [u for a in self.articulos for u in a.unidades if u.vigente]

    def proporcion_partida_en_apartados(self) -> float:
        """Qué fracción de las unidades **vigentes** se pudo partir en apartados.

        Es la métrica que vigila el test de umbral: si la regex de la LOPDGDD se rompe al cambiar
        la fuente, esto baja y el test falla antes de que nadie mire los números del eval set.
        """
        unidades = self.unidades_vigentes()
        if not unidades:
            return 0.0
        partidas = sum(1 for u in unidades if u.granularidad is Granularidad.APARTADO)
        return partidas / len(unidades)
