"""Carga las unidades indexables del corpus normalizado, para dárselas a cualquier motor.

Lee `*.unidades.jsonl` en `data/processed/`: son las unidades **vigentes**, ya aplanadas por
`rag_lopd.almacen.guardar`. Ningún motor de recuperación debería saber leer ese fichero por su
cuenta — todos comparten esta única puerta de entrada, así que el día que el formato cambie solo
hay un sitio que tocar.
"""

from __future__ import annotations

from pathlib import Path

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
