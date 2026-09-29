"""Recuperador BM25: la referencia contra la que se mide todo lo demás.

Es el baseline correcto para un corpus normativo antes que cualquier embedding: los términos son
precisos (nombres de artículos, plazos, excepciones) y BM25 puntúa la coincidencia léxica exacta
mejor de lo que la aproxima un embedding genérico en español. Si el híbrido (denso + RRF +
reranker, todavía en la niebla) no le gana a esto con margen, no vale la complejidad de
mantenerlo.
"""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from rag_lopd.model import UnidadIndexable
from rag_lopd.retrieval.modelo import Resultado

_TOKEN = re.compile(r"[a-záéíóúñü0-9]+", re.IGNORECASE)


def _tokenizar(texto: str) -> list[str]:
    return _TOKEN.findall(texto.lower())


class RecuperadorBM25:
    """BM25 sobre las unidades indexables del corpus.

    `con_ruta` decide si el texto que se indexa lleva delante su ruta jerárquica
    ("RGPD · Capítulo IV · Artículo 33") o no. Es la pregunta que dejó pendiente el ticket 07
    (*Estrategia de chunking*): si anteponerla ayuda al recall o solo lo parece. Aquí no se opina,
    se deja elegible por quien construye el índice, y `retrieval evaluar` la mide con las dos
    variantes.
    """

    def __init__(self, unidades: list[UnidadIndexable], *, con_ruta: bool = True) -> None:
        if not unidades:
            raise ValueError("no se puede indexar una lista vacía de unidades")
        self._unidades = unidades
        self.con_ruta = con_ruta
        textos = [u.texto_para_embeber if con_ruta else u.texto for u in unidades]
        self._bm25 = BM25Okapi([_tokenizar(t) for t in textos])

    def buscar(self, consulta: str, *, k: int = 10) -> list[Resultado]:
        puntuaciones = self._bm25.get_scores(_tokenizar(consulta))
        orden = sorted(range(len(self._unidades)), key=lambda i: puntuaciones[i], reverse=True)
        return [
            Resultado(
                id=self._unidades[i].id,
                score=float(puntuaciones[i]),
                texto=self._unidades[i].texto,
                ruta=self._unidades[i].ruta,
            )
            for i in orden[:k]
        ]
