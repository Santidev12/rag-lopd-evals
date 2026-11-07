"""Tests del recuperador de Azure AI Search con un cliente falso: nada sale a la red.

Lo que se prueba es la traducción (claves, esquema, documentos) y la forma de cada consulta según el
modo. Que el servicio real devuelva lo mismo se mide con la prueba de humo del ticket, no aquí.
"""

from __future__ import annotations

import numpy as np
import pytest

from rag_lopd.config import Settings
from rag_lopd.model import Granularidad, Identificador, UnidadIndexable
from rag_lopd.retrieval.azure_search import (
    CAMPO_VECTORIAL,
    DIMENSIONES,
    MODOS,
    PERFIL_VECTORIAL,
    RecuperadorAzureSearch,
    clave_de,
    definir_indice,
    documentos,
)


class _Embebedor:
    def __init__(self, vector: list[float]) -> None:
        self._vector = vector

    def embeber(self, textos: list[str]) -> list[list[float]]:
        return [self._vector for _ in textos]


class _Cliente:
    """Anota cada llamada y devuelve filas tal como las da Azure: un dict con `@search.score`."""

    def __init__(self, filas: list[dict[str, object]] | None = None) -> None:
        self.llamadas: list[dict[str, object]] = []
        self._filas = filas or []

    def search(self, **kwargs: object) -> list[dict[str, object]]:
        self.llamadas.append(kwargs)
        return self._filas


def _unidad(id_: str, texto: str) -> UnidadIndexable:
    return UnidadIndexable(
        id=Identificador.parse(id_),
        texto=texto,
        granularidad=Granularidad.APARTADO,
        ruta="RGPD · Artículo 33",
    )


# --- claves -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("identificador", "clave"),
    [
        ("rgpd:art-33.1", "rgpd--art-33_1"),
        ("lopdgdd:da-1.2", "lopdgdd--da-1_2"),
        ("aepd-ps-00117-2022:fd-3", "aepd-ps-00117-2022--fd-3"),
    ],
)
def test_la_clave_de_azure_es_valida_y_reversible(identificador: str, clave: str) -> None:
    assert clave_de(identificador) == clave
    assert clave.replace("--", ":").replace("_", ".") == identificador


def test_un_identificador_que_rompe_la_traduccion_se_rechaza_en_vez_de_colisionar() -> None:
    with pytest.raises(ValueError, match="traducción"):
        clave_de("rgpd:art_33")


# --- esquema ------------------------------------------------------------------------------------


def test_el_indice_tiene_un_campo_vectorial_de_1024_dimensiones_con_perfil_hnsw() -> None:
    indice = definir_indice("rag-lopd-v0")

    campo = next(f for f in indice.fields if f.name == CAMPO_VECTORIAL)
    assert campo.vector_search_dimensions == DIMENSIONES == 1024
    assert campo.vector_search_profile_name == PERFIL_VECTORIAL
    assert any(p.name == PERFIL_VECTORIAL for p in indice.vector_search.profiles)


def test_el_texto_usa_el_analizador_de_espanol() -> None:
    indice = definir_indice("rag-lopd-v0")

    for nombre in ("texto", "ruta"):
        campo = next(f for f in indice.fields if f.name == nombre)
        assert campo.analyzer_name == "es.microsoft"


def test_la_clave_del_documento_es_el_campo_clave() -> None:
    indice = definir_indice("rag-lopd-v0")

    clave = next(f for f in indice.fields if f.name == "clave")
    assert clave.key is True


# --- documentos ---------------------------------------------------------------------------------


def test_los_documentos_llevan_clave_identificador_y_vector() -> None:
    unidades = [_unidad("rgpd:art-33.1", "72 horas")]
    vectores = np.array([[1.0, 0.0] + [0.0] * (DIMENSIONES - 2)], dtype=np.float32)

    (doc,) = documentos(unidades, vectores)

    assert doc["clave"] == "rgpd--art-33_1"
    assert doc["identificador"] == "rgpd:art-33.1"
    assert doc["texto"] == "72 horas"
    assert len(doc[CAMPO_VECTORIAL]) == DIMENSIONES


def test_un_vector_desalineado_con_las_unidades_no_se_sube() -> None:
    with pytest.raises(ValueError, match="no está alineado"):
        documentos([_unidad("rgpd:art-33.1", "x")], np.zeros((2, DIMENSIONES), dtype=np.float32))


# --- modos de consulta --------------------------------------------------------------------------


def _vector_de_prueba() -> list[float]:
    return [0.6, 0.8] + [0.0] * (DIMENSIONES - 2)


def test_el_modo_vectorial_busca_por_vector_aproximado_y_sin_texto() -> None:
    cliente = _Cliente()
    recuperador = RecuperadorAzureSearch(cliente, _Embebedor(_vector_de_prueba()), modo="vectorial")

    recuperador.buscar("consulta", k=5)

    (llamada,) = cliente.llamadas
    assert llamada["search_text"] is None
    (vq,) = llamada["vector_queries"]  # type: ignore[misc]
    assert vq.k_nearest_neighbors == 5
    assert vq.fields == CAMPO_VECTORIAL
    assert vq.exhaustive is False


def test_el_modo_vectorial_exacto_pide_busqueda_exhaustiva() -> None:
    cliente = _Cliente()
    recuperador = RecuperadorAzureSearch(
        cliente, _Embebedor(_vector_de_prueba()), modo="vectorial-exacto"
    )

    recuperador.buscar("consulta")

    (vq,) = cliente.llamadas[0]["vector_queries"]  # type: ignore[misc]
    assert vq.exhaustive is True


def test_el_modo_bm25_busca_solo_texto_y_no_calcula_embedding() -> None:
    cliente = _Cliente()

    class _Prohibido:
        def embeber(self, textos: list[str]) -> list[list[float]]:
            raise AssertionError("BM25 no debe embeber la consulta")

    recuperador = RecuperadorAzureSearch(cliente, _Prohibido(), modo="bm25")
    recuperador.buscar("plazo de notificación")

    llamada = cliente.llamadas[0]
    assert llamada["search_text"] == "plazo de notificación"
    assert llamada["vector_queries"] is None
    assert llamada["search_fields"] == ["texto", "ruta"]


def test_el_modo_hibrido_manda_texto_y_vector_en_la_misma_llamada() -> None:
    cliente = _Cliente()
    recuperador = RecuperadorAzureSearch(cliente, _Embebedor(_vector_de_prueba()), modo="hibrido")

    recuperador.buscar("plazo de notificación", k=10)

    llamada = cliente.llamadas[0]
    assert llamada["search_text"] == "plazo de notificación"
    assert len(llamada["vector_queries"]) == 1  # type: ignore[arg-type]
    assert llamada["top"] == 10


def test_los_resultados_se_traducen_al_contrato_con_su_identificador_original() -> None:
    filas = [
        {"identificador": "rgpd:art-33.1", "@search.score": 0.91, "texto": "72 horas", "ruta": "R"},
    ]
    recuperador = RecuperadorAzureSearch(
        _Cliente(filas), _Embebedor(_vector_de_prueba()), modo="vectorial"
    )

    (resultado,) = recuperador.buscar("x")

    assert resultado.id == Identificador.parse("rgpd:art-33.1")
    assert resultado.score == pytest.approx(0.91)
    assert resultado.texto == "72 horas"


def test_un_modo_desconocido_falla_al_construir() -> None:
    with pytest.raises(ValueError, match="modo desconocido"):
        RecuperadorAzureSearch(_Cliente(), _Embebedor([1.0]), modo="rrf")  # type: ignore[arg-type]


def test_los_cuatro_modos_del_experimento_estan_declarados() -> None:
    assert set(MODOS) == {"vectorial", "vectorial-exacto", "bm25", "hibrido"}


def test_sin_endpoint_no_se_puede_crear_el_cliente() -> None:
    from rag_lopd.retrieval.azure_search import cliente_de_busqueda

    with pytest.raises(ValueError, match="AZURE_SEARCH_ENDPOINT"):
        cliente_de_busqueda(Settings(_env_file=None))  # type: ignore[call-arg]
