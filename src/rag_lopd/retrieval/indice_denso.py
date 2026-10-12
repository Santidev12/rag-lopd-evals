"""Persistencia del índice denso: los vectores ya calculados, para no volver a llamar a la API
en cada arranque.

Se guardan por separado de las unidades del corpus (solo `ids` + `vectores`) y se recomponen
contra `cargar_unidades` en el momento de usarlos. Si el corpus cambió desde que se construyó el
índice (nueva ingesta, un artículo que ya no existe), `cargar` falla en vez de servir resultados
silenciosamente desalineados — el mismo principio que el umbral de la ingesta de la LOPDGDD.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from rag_lopd.config import Settings
from rag_lopd.model import UnidadIndexable
from rag_lopd.retrieval.embeddings import Embebedor


def ruta_indice(settings: Settings, *, con_ruta: bool) -> Path:
    """Dónde vive el índice denso de cada variante. Un solo sitio para quien lo construye
    (`retrieval indexar`) y para quien lo consume (`retrieval evaluar`, `generacion evaluar`)."""
    sufijo = "con-ruta" if con_ruta else "sin-ruta"
    return settings.processed_dir / f"denso-{sufijo}.npz"


def construir(
    unidades: list[UnidadIndexable], embebedor: Embebedor, *, con_ruta: bool = True
) -> np.ndarray:
    """Embebe todas las unidades y normaliza los vectores a norma 1.

    Normalizar aquí, una sola vez al construir, es lo que permite que la búsqueda sea un
    producto punto en vez de tener que calcular la norma en cada consulta.
    """
    textos = [u.texto_para_embeber if con_ruta else u.texto for u in unidades]
    vectores = np.array(embebedor.embeber(textos), dtype=np.float32)
    normas = np.linalg.norm(vectores, axis=1, keepdims=True)
    return vectores / normas


def guardar(ruta: Path, unidades: list[UnidadIndexable], vectores: np.ndarray) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ids = np.array([str(u.id) for u in unidades])
    np.savez_compressed(ruta, ids=ids, vectores=vectores)


def cargar(ruta: Path, unidades: list[UnidadIndexable]) -> tuple[list[UnidadIndexable], np.ndarray]:
    """Las unidades y los vectores del índice guardado, en el mismo orden entre sí.

    `unidades` es el corpus actual (de `cargar_unidades`): sirve para traducir cada id guardado
    de vuelta a su `UnidadIndexable` completa, con el texto y la ruta al día.
    """
    datos = np.load(ruta)
    ids_guardados = [str(id_) for id_ in datos["ids"]]
    vectores = datos["vectores"]

    por_id = {str(u.id): u for u in unidades}
    faltantes = [id_ for id_ in ids_guardados if id_ not in por_id]
    if faltantes:
        raise ValueError(
            f"el índice denso en {ruta} tiene {len(faltantes)} unidad(es) que ya no están en "
            f"el corpus (por ejemplo {faltantes[0]!r}). Reconstrúyelo con "
            "'rag-lopd retrieval indexar'."
        )
    unidades_ordenadas = [por_id[id_] for id_ in ids_guardados]
    return unidades_ordenadas, vectores
