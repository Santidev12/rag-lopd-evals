"""Tests del recuperador denso y de la persistencia del índice.

`_EmbebedorFijo` sustituye a DeepInfra por un diccionario: estos tests miden la lógica de
similitud coseno y de alineación de ids, no la llamada HTTP (esa vive en test_embeddings.py).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from rag_lopd.model import Granularidad, Identificador, UnidadIndexable
from rag_lopd.retrieval import indice_denso
from rag_lopd.retrieval.denso import RecuperadorDenso


class _EmbebedorFijo:
    """Devuelve el vector guardado para cada texto exacto. Falla fuerte si pides uno que no
    preparaste — mejor eso que un vector inventado que enmascare un test mal escrito."""

    def __init__(self, por_texto: dict[str, list[float]]) -> None:
        self._por_texto = por_texto

    def embeber(self, textos: list[str]) -> list[list[float]]:
        return [self._por_texto[t] for t in textos]


def _unidad(id_texto: str, texto: str, *, ruta: str = "RGPD · Artículo X") -> UnidadIndexable:
    return UnidadIndexable(
        id=Identificador.parse(id_texto),
        texto=texto,
        granularidad=Granularidad.APARTADO,
        ruta=ruta,
    )


def test_recuperador_denso_devuelve_el_mas_parecido_por_coseno_primero() -> None:
    unidades = [_unidad("rgpd:art-1.1", "uno"), _unidad("rgpd:art-2.1", "dos")]
    vectores = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    embebedor = _EmbebedorFijo({"una consulta": [0.0, 5.0]})  # no normalizado a propósito

    resultados = RecuperadorDenso(unidades, vectores, embebedor).buscar("una consulta", k=1)

    assert len(resultados) == 1
    assert str(resultados[0].id) == "rgpd:art-2.1"
    assert resultados[0].score == pytest.approx(1.0)  # coseno perfecto tras normalizar


def test_recuperador_denso_devuelve_como_mucho_k_resultados() -> None:
    unidades = [_unidad("rgpd:art-1.1", "uno"), _unidad("rgpd:art-2.1", "dos")]
    vectores = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    embebedor = _EmbebedorFijo({"x": [1.0, 1.0]})

    assert len(RecuperadorDenso(unidades, vectores, embebedor).buscar("x", k=1)) == 1
    assert len(RecuperadorDenso(unidades, vectores, embebedor).buscar("x", k=10)) == 2


def test_recuperador_denso_exige_unidades_y_vectores_alineados() -> None:
    unidades = [_unidad("rgpd:art-1.1", "uno")]
    vectores = np.zeros((2, 3), dtype=np.float32)

    with pytest.raises(ValueError, match="alineado"):
        RecuperadorDenso(unidades, vectores, _EmbebedorFijo({}))


def test_indice_denso_guarda_y_carga_alineado(tmp_path: Path) -> None:
    unidades = [
        _unidad("rgpd:art-1.1", "uno", ruta="RGPD · Artículo 1"),
        _unidad("rgpd:art-2.1", "dos", ruta="RGPD · Artículo 2"),
    ]
    embebedor = _EmbebedorFijo(
        {
            "RGPD · Artículo 1\n\nuno": [3.0, 4.0],
            "RGPD · Artículo 2\n\ndos": [0.0, 5.0],
        }
    )

    vectores = indice_denso.construir(unidades, embebedor, con_ruta=True)
    ruta = tmp_path / "indice.npz"
    indice_denso.guardar(ruta, unidades, vectores)
    unidades_cargadas, vectores_cargados = indice_denso.cargar(ruta, unidades)

    assert [str(u.id) for u in unidades_cargadas] == ["rgpd:art-1.1", "rgpd:art-2.1"]
    # `construir` normaliza a norma 1: es lo que permite que la búsqueda sea un producto punto.
    np.testing.assert_allclose(np.linalg.norm(vectores_cargados, axis=1), [1.0, 1.0], atol=1e-6)


def test_indice_denso_carga_falla_si_el_corpus_ya_no_tiene_esa_unidad(tmp_path: Path) -> None:
    unidades_original = [_unidad("rgpd:art-1.1", "uno", ruta="RGPD · Artículo 1")]
    embebedor = _EmbebedorFijo({"RGPD · Artículo 1\n\nuno": [1.0, 0.0]})
    vectores = indice_denso.construir(unidades_original, embebedor)
    ruta = tmp_path / "indice.npz"
    indice_denso.guardar(ruta, unidades_original, vectores)

    corpus_nuevo = [_unidad("rgpd:art-2.1", "dos", ruta="RGPD · Artículo 2")]

    with pytest.raises(ValueError, match="ya no están en el corpus"):
        indice_denso.cargar(ruta, corpus_nuevo)
