"""Recuperador sobre Azure AI Search: vectores propios (BGE-M3) y búsqueda léxica o híbrida.

Cumple el contrato `Recuperador`, así que se mide con el mismo harness que BM25 y el denso local.
Los vectores **no** se recalculan en Azure: se suben los del índice local (`denso-sin-ruta.npz`),
para que la única diferencia entre configuraciones sea el motor de búsqueda y no el modelo de
embeddings.

Cuatro modos, que son las configuraciones del experimento (ticket del diseño):

- `vectorial`: búsqueda aproximada HNSW sobre el campo vectorial.
- `vectorial-exacto`: el mismo campo con `exhaustive=True`. Es el control de cordura: debe
  reproducir al local, y lo que difiera frente a `vectorial` es lo que cuesta aproximar.
- `bm25`: solo texto, con el analizador de español de Azure. Separa lo que aporta el texto.
- `hibrido`: texto y vector en la misma llamada. Azure los fusiona con RRF (`k` fijo, no
  configurable).

Dos decisiones fijadas antes de medir:
- Analizador: `es.microsoft` (lematiza). `es.lucene` queda como alternativa, sin probar.
- Clave del documento: Azure solo admite letras, dígitos, guiones bajos, guiones y signos `=`. Un
  id como `rgpd:art-33.1` no cabe, así que la clave es `rgpd--art-33_1` y el identificador original
  se guarda aparte, en un campo recuperable. La traducción es reversible y no cambia el eval set.
"""

from __future__ import annotations

import re
from typing import Any, Literal

import numpy as np
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchIndex,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)
from azure.search.documents.models import VectorizedQuery, VectorQuery

from rag_lopd.config import Settings
from rag_lopd.model import Identificador, UnidadIndexable
from rag_lopd.retrieval.embeddings import Embebedor
from rag_lopd.retrieval.modelo import Resultado

Modo = Literal["vectorial", "vectorial-exacto", "bm25", "hibrido"]
MODOS: tuple[Modo, ...] = ("vectorial", "vectorial-exacto", "bm25", "hibrido")

DIMENSIONES = 1024
"""BGE-M3 devuelve vectores de 1024 dimensiones."""

ANALIZADOR = "es.microsoft"
CAMPO_VECTORIAL = "embedding"
PERFIL_VECTORIAL = "perfil-hnsw"
ALGORITMO_VECTORIAL = "hnsw"
CAMPOS_TEXTO = ["texto", "ruta"]
CAMPOS_RESULTADO = ["identificador", "ruta", "texto"]

_CLAVE_VALIDA = re.compile(r"^[A-Za-z0-9_\-=]+$")


def clave_de(identificador: str) -> str:
    """La clave de Azure para un identificador semántico, reversible y válida (`[A-Za-z0-9_\\-=]+`).

    `:` pasa a `--` y `.` a `_`. Los identificadores del corpus no contienen `--` ni `_`, así que la
    traducción es inyectiva; un identificador que la rompa se rechaza en vez de colisionar en
    silencio."""
    if "--" in identificador or "_" in identificador:
        raise ValueError(f"identificador {identificador!r} no admite la traducción de clave")
    clave = identificador.replace(":", "--").replace(".", "_")
    if not _CLAVE_VALIDA.match(clave):
        raise ValueError(f"la clave {clave!r} no es válida en Azure AI Search")
    return clave


def definir_indice(nombre: str) -> SearchIndex:
    """El esquema del índice: texto con analizador de español, un campo vectorial HNSW y el
    identificador."""
    return SearchIndex(
        name=nombre,
        fields=[
            SimpleField(name="clave", type="Edm.String", key=True, filterable=True),
            SimpleField(
                name="identificador",
                type="Edm.String",
                filterable=True,
                retrievable=True,
            ),
            SearchableField(name="ruta", analyzer_name=ANALIZADOR, retrievable=True),
            SearchableField(name="texto", analyzer_name=ANALIZADOR, retrievable=True),
            SearchField(
                name=CAMPO_VECTORIAL,
                type="Collection(Edm.Single)",
                searchable=True,
                vector_search_dimensions=DIMENSIONES,
                vector_search_profile_name=PERFIL_VECTORIAL,
            ),
        ],
        vector_search=VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name=ALGORITMO_VECTORIAL)],
            profiles=[
                VectorSearchProfile(
                    name=PERFIL_VECTORIAL, algorithm_configuration_name=ALGORITMO_VECTORIAL
                )
            ],
        ),
    )


def documentos(unidades: list[UnidadIndexable], vectores: np.ndarray) -> list[dict[str, Any]]:
    """Los documentos a subir: una fila por unidad, con su vector ya normalizado."""
    if len(unidades) != vectores.shape[0]:
        raise ValueError(
            f"{len(unidades)} unidades pero {vectores.shape[0]} vectores: "
            "el índice no está alineado."
        )
    return [
        {
            "clave": clave_de(str(u.id)),
            "identificador": str(u.id),
            "ruta": u.ruta,
            "texto": u.texto,
            CAMPO_VECTORIAL: vector.tolist(),
        }
        for u, vector in zip(unidades, vectores, strict=True)
    ]


def credencial_de(settings: Settings) -> AzureKeyCredential | DefaultAzureCredential:
    """Clave si está en `.env` (lo más simple para empezar); si no, Entra ID con el rol de datos."""
    if settings.azure_search_api_key:
        return AzureKeyCredential(settings.azure_search_api_key)
    return DefaultAzureCredential()


def cliente_de_indices(settings: Settings) -> SearchIndexClient:
    _exigir_endpoint(settings)
    endpoint = settings.azure_search_endpoint
    assert endpoint is not None  # garantizado por _exigir_endpoint
    return SearchIndexClient(endpoint=endpoint, credential=credencial_de(settings))


def cliente_de_busqueda(settings: Settings) -> SearchClient:
    _exigir_endpoint(settings)
    endpoint = settings.azure_search_endpoint
    assert endpoint is not None  # garantizado por _exigir_endpoint
    return SearchClient(
        endpoint=endpoint,
        index_name=settings.azure_search_index,
        credential=credencial_de(settings),
    )


def _exigir_endpoint(settings: Settings) -> None:
    if not settings.azure_search_endpoint:
        raise ValueError(
            "falta AZURE_SEARCH_ENDPOINT en .env (p. ej. https://<servicio>.search.windows.net)."
        )


class RecuperadorAzureSearch:
    """Cumple `Recuperador`. El `cliente` se inyecta: en producción es un `SearchClient` real, y en
    los tests un doble que no sale a la red."""

    def __init__(
        self,
        cliente: SearchClient,
        embebedor: Embebedor,
        *,
        modo: Modo,
    ) -> None:
        if modo not in MODOS:
            raise ValueError(f"modo desconocido: {modo!r}. Usa uno de {', '.join(MODOS)}.")
        self._cliente = cliente
        self._embebedor = embebedor
        self._modo = modo

    @property
    def modo(self) -> Modo:
        return self._modo

    def buscar(self, consulta: str, *, k: int = 10) -> list[Resultado]:
        solo_texto = self._modo == "bm25"
        pedir_vector = not solo_texto

        consultas_vectoriales: list[VectorQuery] | None = None
        if pedir_vector:
            vector = np.array(self._embebedor.embeber([consulta])[0], dtype=np.float32)
            vector = vector / np.linalg.norm(vector)
            consultas_vectoriales = [
                VectorizedQuery(
                    vector=vector.tolist(),
                    k_nearest_neighbors=k,
                    fields=CAMPO_VECTORIAL,
                    exhaustive=self._modo == "vectorial-exacto",
                )
            ]

        resultados = self._cliente.search(
            search_text=consulta if self._modo in ("bm25", "hibrido") else None,
            search_fields=CAMPOS_TEXTO if self._modo in ("bm25", "hibrido") else None,
            vector_queries=consultas_vectoriales,
            select=CAMPOS_RESULTADO,
            top=k,
        )
        return [
            Resultado(
                id=Identificador.parse(r["identificador"]),
                score=float(r["@search.score"]),
                texto=r["texto"],
                ruta=r["ruta"],
            )
            for r in resultados
        ]
