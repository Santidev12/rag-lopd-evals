"""Persistencia del corpus normalizado.

Se escriben dos ficheros por norma, a propósito:

- `<slug>.json` — la norma entera, anidada. Es la **fuente de verdad**: legible, diffeable y
  suficiente para reconstruir todo lo demás.
- `<slug>.unidades.jsonl` — una unidad indexable por línea, ya aplanada. Es lo que consumirá el
  indexador, que solo necesita las unidades vigentes y no quiere cargar el árbol entero en memoria.

Duplicar así es barato (el RGPD son ~1 MB) y ahorra que cada consumidor tenga que recorrer el árbol.
"""

from __future__ import annotations

from pathlib import Path

from rag_lopd.model import Norma


def guardar(norma: Norma, directorio: Path) -> tuple[Path, Path]:
    directorio.mkdir(parents=True, exist_ok=True)

    ruta_norma = directorio / f"{norma.slug}.json"
    ruta_norma.write_text(norma.model_dump_json(indent=2), encoding="utf-8")

    ruta_unidades = directorio / f"{norma.slug}.unidades.jsonl"
    lineas = [u.model_dump_json() for u in norma.unidades_vigentes()]
    ruta_unidades.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    return ruta_norma, ruta_unidades


def cargar(slug: str, directorio: Path) -> Norma:
    return Norma.model_validate_json((directorio / f"{slug}.json").read_text(encoding="utf-8"))
