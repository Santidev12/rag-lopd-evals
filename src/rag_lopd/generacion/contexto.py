"""De unidades recuperadas a artículos enteros: el salto *small-to-big* del ADR 0001.

El buscador indexa y devuelve apartados; al modelo se le entrega el artículo completo. Aquí se
reconstruye ese artículo a partir de las unidades del corpus (`Articulo.titulo` no se guarda en el
JSONL aplanado, y la `ruta` ya lleva el encabezado).

Si entre las unidades hay redacciones antiguas (`vigente_hasta` con fecha), se separan de la
vigente: el texto vigente es el que manda y las antiguas quedan aparte, ordenadas por fecha.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from rag_lopd.generacion.modelo import Contexto, RedaccionAnterior
from rag_lopd.model import Identificador, UnidadIndexable
from rag_lopd.retrieval.modelo import Resultado

IndiceArticulos = dict[str, list[UnidadIndexable]]


def indexar_articulos(unidades: list[UnidadIndexable]) -> IndiceArticulos:
    """Agrupa las unidades por el artículo que las contiene, conservando el orden del corpus."""
    indice: IndiceArticulos = defaultdict(list)
    for unidad in unidades:
        indice[str(unidad.id.unidad_de_contexto)].append(unidad)
    return dict(indice)


def _unir(unidades: list[UnidadIndexable]) -> str:
    """Los apartados se marcan con su número para que el modelo pueda distinguirlos y citar con
    precisión; una unidad sin apartado (artículo que no se pudo partir) va tal cual."""
    return "\n".join(
        f"({u.id.apartado}) {u.texto}" if u.id.apartado is not None else u.texto for u in unidades
    )


def construir_contexto(unidades: list[UnidadIndexable]) -> Contexto:
    """Un artículo entero a partir de sus unidades: la redacción vigente y, si las hay, las
    anteriores. Un artículo sin ninguna unidad vigente no se puede presentar como contexto."""
    vigentes = [u for u in unidades if u.vigente]
    if not vigentes:
        raise ValueError(
            f"el artículo {unidades[0].id.unidad_de_contexto} no tiene redacción vigente"
        )

    versiones: dict[tuple[date | None, date], list[UnidadIndexable]] = defaultdict(list)
    for unidad in unidades:
        if unidad.vigente_hasta is not None:
            versiones[(unidad.vigente_desde, unidad.vigente_hasta)].append(unidad)
    anteriores = tuple(
        RedaccionAnterior(desde=desde, hasta=hasta, texto=_unir(grupo))
        for (desde, hasta), grupo in sorted(
            versiones.items(), key=lambda par: (par[0][0] or date.min, par[0][1])
        )
    )

    primera = vigentes[0]
    return Contexto(
        id=primera.id.unidad_de_contexto,
        ruta=primera.ruta,
        texto=_unir(vigentes),
        vigente_desde=max((u.vigente_desde for u in vigentes if u.vigente_desde), default=None),
        anteriores=anteriores,
    )


def contextos_para(resultados: list[Resultado], indice: IndiceArticulos) -> list[Contexto]:
    """Los artículos de los resultados, sin repetir y en el orden en que aparece cada uno por
    primera vez (el de mejor posición manda).

    Un resultado cuyo artículo no está en el índice se salta en vez de fallar: significaría que el
    índice denso y el corpus cargado no están alineados, y eso ya lo vigila `indice_denso.cargar`.
    """
    vistos: set[Identificador] = set()
    contextos: list[Contexto] = []
    for resultado in resultados:
        articulo = resultado.id.unidad_de_contexto
        if articulo in vistos or str(articulo) not in indice:
            continue
        vistos.add(articulo)
        contextos.append(construir_contexto(indice[str(articulo)]))
    return contextos
