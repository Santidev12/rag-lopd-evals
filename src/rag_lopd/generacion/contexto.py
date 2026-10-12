"""De unidades recuperadas a artículos enteros: el salto *small-to-big* del ADR 0001.

El buscador indexa y devuelve apartados; al modelo se le entrega el artículo completo. Aquí se
reconstruye ese artículo a partir de las unidades vigentes del corpus (la única fuente que tiene
`rag-lopd`: `Articulo.titulo` no se guarda en el JSONL aplanado, y la `ruta` ya lleva el
encabezado).
"""

from __future__ import annotations

from collections import defaultdict

from rag_lopd.generacion.modelo import Contexto
from rag_lopd.model import Identificador, UnidadIndexable
from rag_lopd.retrieval.modelo import Resultado

IndiceArticulos = dict[str, list[UnidadIndexable]]


def indexar_articulos(unidades: list[UnidadIndexable]) -> IndiceArticulos:
    """Agrupa las unidades por el artículo que las contiene, conservando el orden del corpus."""
    indice: IndiceArticulos = defaultdict(list)
    for unidad in unidades:
        indice[str(unidad.id.unidad_de_contexto)].append(unidad)
    return dict(indice)


def construir_contexto(unidades: list[UnidadIndexable]) -> Contexto:
    """Un artículo entero a partir de sus unidades. Los apartados se marcan con su número para
    que el modelo pueda distinguirlos y citar con precisión; una unidad sin apartado (artículo que
    no se pudo partir) va tal cual."""
    primera = unidades[0]
    trozos = [
        f"({u.id.apartado}) {u.texto}" if u.id.apartado is not None else u.texto for u in unidades
    ]
    return Contexto(
        id=primera.id.unidad_de_contexto,
        ruta=primera.ruta,
        texto="\n".join(trozos),
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
