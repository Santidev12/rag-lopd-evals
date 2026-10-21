import json
from pathlib import Path

from rag_lopd.almacen import cargar, guardar
from rag_lopd.fuentes import rgpd
from rag_lopd.model import Norma

FIXTURE = Path(__file__).parent / "fixtures" / "rgpd-recorte.xml"


def test_ida_y_vuelta_por_disco_conserva_la_norma(tmp_path: Path) -> None:
    original = rgpd.parsear(FIXTURE.read_bytes())

    guardar(original, tmp_path)
    recuperada: Norma = cargar("rgpd", tmp_path)

    assert recuperada == original


def test_el_jsonl_lleva_una_unidad_vigente_por_linea(tmp_path: Path) -> None:
    norma = rgpd.parsear(FIXTURE.read_bytes())

    _, ruta_unidades = guardar(norma, tmp_path)
    lineas = ruta_unidades.read_text(encoding="utf-8").strip().split("\n")

    assert len(lineas) == len(norma.unidades_vigentes())
    identificadores = [json.loads(linea)["id"] for linea in lineas]
    assert "rgpd:art-33.1" in identificadores
    assert identificadores == [str(u.id) for u in norma.unidades_vigentes()]
