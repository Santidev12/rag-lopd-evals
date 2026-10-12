"""El corpus con historia: las redacciones antiguas son para la generación, no para el índice."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from rag_lopd.almacen import guardar
from rag_lopd.model import Articulo, Granularidad, Identificador, Norma, UnidadIndexable
from rag_lopd.retrieval.corpus import cargar_unidades, cargar_unidades_con_historia


def _unidad(id_texto: str, texto: str, *, hasta: date | None = None) -> UnidadIndexable:
    return UnidadIndexable(
        id=Identificador.parse(id_texto),
        texto=texto,
        granularidad=Granularidad.APARTADO,
        ruta="LOPDGDD · Artículo 67",
        vigente_desde=date(2018, 12, 7),
        vigente_hasta=hasta,
    )


def _norma_con_un_articulo_modificado() -> Norma:
    unidades = (
        _unidad("lopdgdd:art-67.2", "doce meses", hasta=date(2023, 5, 10)),
        _unidad("lopdgdd:art-67.2", "dieciocho meses"),
    )
    articulo = Articulo(
        id=Identificador.parse("lopdgdd:art-67"),
        titulo="Actuaciones previas",
        ruta="LOPDGDD · Artículo 67",
        texto="",
        unidades=unidades,
    )
    return Norma(
        slug="lopdgdd", titulo="LOPDGDD", identificador_oficial="BOE", articulos=(articulo,)
    )


def test_el_indice_solo_ve_lo_vigente_y_la_generacion_ve_tambien_lo_derogado(
    tmp_path: Path,
) -> None:
    guardar(_norma_con_un_articulo_modificado(), tmp_path)

    assert [u.texto for u in cargar_unidades(tmp_path)] == ["dieciocho meses"]
    assert [u.texto for u in cargar_unidades_con_historia(tmp_path)] == [
        "doce meses",
        "dieciocho meses",
    ]


def test_sin_corpus_ingerido_no_hay_unidades_con_historia(tmp_path: Path) -> None:
    assert cargar_unidades_con_historia(tmp_path) == []
