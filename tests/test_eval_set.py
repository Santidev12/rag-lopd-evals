"""El eval set real del repo, no un ejemplo de laboratorio.

Los tests que necesitan el corpus se saltan solos si no está en disco (`data/` está en
.gitignore y se regenera con `rag-lopd ingest`), para que la suite siga corriendo en CI.
"""

from pathlib import Path

import pytest

from rag_lopd.eval.almacen import leer
from rag_lopd.eval.modelo import REPARTO_OBJETIVO
from rag_lopd.eval.validacion import (
    cargar_corpus,
    fuentes_inexistentes,
    identificadores_del_corpus,
)

RAIZ = Path(__file__).resolve().parents[1]
CANDIDATAS = RAIZ / "eval" / "candidatas-v0.jsonl"
CORPUS = RAIZ / "data" / "processed"

sin_corpus = pytest.mark.skipif(
    not (CORPUS / "rgpd.json").exists(),
    reason="el corpus se regenera con `rag-lopd ingest`; no está versionado",
)


@pytest.fixture(scope="module")
def eval_set():
    return leer(CANDIDATAS)


def test_el_fichero_de_candidatas_cumple_todas_las_reglas(eval_set) -> None:
    # Que el fichero se lea sin excepción ya significa que las 50 pasan las reglas del modelo.
    assert len(eval_set.preguntas) == 50


def test_el_reparto_por_tipo_es_el_objetivo(eval_set) -> None:
    assert eval_set.reparto() == REPARTO_OBJETIVO


def test_una_de_cada_cinco_preguntas_no_tiene_respuesta_en_el_corpus(eval_set) -> None:
    sin_respuesta = sum(1 for p in eval_set.preguntas if p.debe_abstenerse)

    assert sin_respuesta / len(eval_set.preguntas) >= 0.30, (
        "con pocas preguntas sin respuesta, la tasa de sobre-respuesta no tiene precisión"
    )


def test_ninguna_pregunta_repite_texto(eval_set) -> None:
    textos = [p.pregunta.strip().lower() for p in eval_set.preguntas]

    assert len(set(textos)) == len(textos)


@sin_corpus
def test_todas_las_fuentes_existen_en_el_corpus(eval_set) -> None:
    corpus = identificadores_del_corpus(cargar_corpus(CORPUS))

    assert fuentes_inexistentes(eval_set, corpus) == {}


#: Términos que la respuesta esperada afirma y que DEBEN aparecer en el texto de su fuente.
#: Es la defensa contra el fallo más peligroso al generar preguntas con un LLM: que la
#: respuesta suene impecable y el artículo citado no diga eso.
ANCLAS = {
    "e-001": "72 horas",
    "e-002": "plazo de un mes",
    "e-003": "catorce años",
    "e-004": "menos de 250 personas",
    "e-005": "4 %",
    "e-008": "prescribirán al año",
    "e-009": "superior a 300.000 euros",
    "e-010": "bloquear los datos",
    "e-012": "desconexión digital",
    "e-014": "13 años",
    "e-015": "2 %",
    "e-028": "dieciocho meses",
    "e-029": "(Anulado)",
    "e-030": "Fiscalía General del Estado",
    "e-031": "artículo 64.4",
}


@sin_corpus
@pytest.mark.parametrize(("identificador", "ancla"), sorted(ANCLAS.items()))
def test_la_respuesta_esperada_esta_anclada_en_el_texto_de_su_fuente(
    eval_set, identificador: str, ancla: str
) -> None:
    pregunta = next(p for p in eval_set.preguntas if p.id == identificador)
    unidades = {str(u.id): u for n in cargar_corpus(CORPUS) for u in n.unidades_vigentes()}
    textos = " ".join(unidades[str(f)].texto for f in pregunta.fuente)

    assert ancla in textos, f"{identificador}: la fuente citada no contiene {ancla!r}"
