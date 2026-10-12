"""Carga las unidades indexables del corpus normalizado, para dárselas a cualquier motor.

Lee `*.unidades.jsonl` en `data/processed/`: son las unidades **vigentes**, ya aplanadas por
`rag_lopd.almacen.guardar`. Ningún motor de recuperación debería saber leer ese fichero por su
cuenta — todos comparten esta única puerta de entrada, así que el día que el formato cambie solo
hay un sitio que tocar.
"""

from __future__ import annotations

from pathlib import Path

from rag_lopd.almacen import cargar as cargar_norma
from rag_lopd.model import UnidadIndexable


def cargar_unidades(directorio: Path) -> list[UnidadIndexable]:
    """Todas las unidades de todas las normas ya ingeridas en `directorio`.

    Vacío (no un error) si aún no se ha ejecutado `rag-lopd ingest`: quien llame decide si eso
    es un problema.
    """
    unidades: list[UnidadIndexable] = []
    for ruta in sorted(directorio.glob("*.unidades.jsonl")):
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            if linea.strip():
                unidades.append(UnidadIndexable.model_validate_json(linea))
    return unidades


def cargar_unidades_con_historia(directorio: Path) -> list[UnidadIndexable]:
    """Las unidades de cada norma ya ingerida **incluyendo las redacciones antiguas**.

    El índice de recuperación solo lleva las vigentes (`cargar_unidades`); esto lee la fuente de
    verdad (`<slug>.json`) para que la generación pueda enseñar cómo decía antes un artículo
    modificado. Quien recupera no debe usar esto: una redacción derogada no debe poder salir como
    resultado de búsqueda.

    Las normas se descubren por sus `*.unidades.jsonl`, para que ambas funciones vean las mismas.
    """
    unidades: list[UnidadIndexable] = []
    for ruta in sorted(directorio.glob("*.unidades.jsonl")):
        slug = ruta.name.removesuffix(".unidades.jsonl")
        norma = cargar_norma(slug, directorio)
        unidades.extend(u for a in norma.articulos for u in a.unidades)
    return unidades
