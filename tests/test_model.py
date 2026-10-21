import json
from datetime import date

import pytest
from pydantic import ValidationError

from rag_lopd.model import (
    Articulo,
    Granularidad,
    Identificador,
    Norma,
    TipoDivision,
    UnidadIndexable,
)

# --- Identificador ---------------------------------------------------------


@pytest.mark.parametrize(
    "texto",
    [
        "rgpd:art-33.1",
        "rgpd:art-33",
        "lopdgdd:da-1.2",
        "lopdgdd:art-6bis",
        "rgpd:cons-171",
        "aepd-ps-00117-2022:fd-3",
        "rgpd:art-83.3a",
    ],
)
def test_ida_y_vuelta_de_los_identificadores_reales(texto: str) -> None:
    assert str(Identificador.parse(texto)) == texto


@pytest.mark.parametrize(
    "texto",
    [
        "RGPD:art-33.1",  # mayúsculas
        "rgpd:articulo-33",  # tipo desconocido
        "rgpd:art-",  # sin número
        "art-33.1",  # sin norma
        "rgpd:art-33.1.2",  # dos niveles de apartado
        "",
    ],
)
def test_los_identificadores_mal_formados_no_se_construyen(texto: str) -> None:
    with pytest.raises(ValidationError):
        Identificador.parse(texto)


def test_la_unidad_de_contexto_es_el_articulo_sin_apartado() -> None:
    apartado = Identificador.parse("rgpd:art-33.1")

    assert str(apartado.unidad_de_contexto) == "rgpd:art-33"
    assert apartado.unidad_de_contexto.tipo is TipoDivision.ARTICULO
    # Un artículo es su propia unidad de contexto: el salto es idempotente.
    assert apartado.unidad_de_contexto.unidad_de_contexto == apartado.unidad_de_contexto


def test_el_identificador_se_serializa_como_cadena_no_como_objeto() -> None:
    unidad = UnidadIndexable(
        id="rgpd:art-33.1",
        texto="En caso de violación de la seguridad de los datos personales...",
        granularidad=Granularidad.APARTADO,
        ruta="RGPD · Capítulo IV · Sección 2 · Artículo 33",
    )

    volcado = json.loads(unidad.model_dump_json())

    assert volcado["id"] == "rgpd:art-33.1"


def test_los_identificadores_son_inmutables_y_comparables() -> None:
    uno = Identificador.parse("rgpd:art-33.1")
    otro = Identificador.parse("rgpd:art-33.1")

    assert uno == otro
    assert len({uno, otro}) == 1, "deben poder usarse como clave de un dict o de un set"
    with pytest.raises(ValidationError):
        uno.numero = "34"  # type: ignore[misc]


# --- Invariantes del artículo ---------------------------------------------


def _unidad(id_: str, granularidad: Granularidad = Granularidad.APARTADO) -> UnidadIndexable:
    return UnidadIndexable(id=id_, texto="texto", granularidad=granularidad, ruta="ruta")


def test_un_articulo_no_admite_unidades_de_otro_articulo() -> None:
    with pytest.raises(ValidationError, match="no pertenece al artículo"):
        Articulo(
            id="rgpd:art-33",
            titulo="Notificación de una violación de la seguridad",
            ruta="RGPD · Artículo 33",
            texto="...",
            unidades=(_unidad("rgpd:art-33.1"), _unidad("rgpd:art-34.1")),
        )


def test_el_id_de_un_articulo_no_puede_llevar_apartado() -> None:
    with pytest.raises(ValidationError, match="no puede tener apartado"):
        Articulo(id="rgpd:art-33.1", titulo="t", ruta="r", texto="...", unidades=())


# --- Vigencia y granularidad ----------------------------------------------


def test_solo_se_indexan_las_unidades_vigentes() -> None:
    vieja = UnidadIndexable(
        id="rgpd:art-83.4",
        texto="...autoridad de control...",
        granularidad=Granularidad.APARTADO,
        ruta="RGPD · Artículo 83",
        vigente_hasta=date(2021, 5, 4),
    )
    nueva = _unidad("rgpd:art-83.4")
    norma = Norma(
        slug="rgpd",
        titulo="Reglamento General de Protección de Datos",
        identificador_oficial="02016R0679-20160504",
        articulos=(
            Articulo(id="rgpd:art-83", titulo="t", ruta="r", texto="...", unidades=(vieja, nueva)),
        ),
    )

    assert norma.unidades_vigentes() == [nueva]
    assert vieja.vigente is False


def test_la_proporcion_partida_delata_una_regex_rota() -> None:
    articulos = (
        Articulo(
            id="lopdgdd:art-7",
            titulo="t",
            ruta="r",
            texto="...",
            unidades=(_unidad("lopdgdd:art-7.1"), _unidad("lopdgdd:art-7.2")),
        ),
        Articulo(
            id="lopdgdd:art-8",
            titulo="t",
            ruta="r",
            texto="...",
            unidades=(_unidad("lopdgdd:art-8", Granularidad.ARTICULO),),
        ),
    )
    norma = Norma(
        slug="lopdgdd", titulo="t", identificador_oficial="BOE-A-2018-16673", articulos=articulos
    )

    assert norma.proporcion_partida_en_apartados() == pytest.approx(2 / 3)


def test_el_texto_que_se_embebe_lleva_la_ruta_delante() -> None:
    unidad = _unidad("rgpd:art-33.1")

    assert unidad.texto_para_embeber.startswith("ruta")
    assert unidad.texto.strip() in unidad.texto_para_embeber
