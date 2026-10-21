"""Tests del parser de la LOPDGDD contra un recorte real de la API del BOE.

El fixture conserva, en el orden del documento, los bloques que prueban cada trampa de esta
fuente: un artículo con dos versiones (el 2), uno con párrafo de continuación sin marcador
(el 7), uno cuyo id no se deriva del número (el 10 es `a1-2`), uno con jerarquía de tres
niveles y numeración "bis" (el 53 bis), y una disposición adicional situada detrás del
TÍTULO X, que es el caso que delata si la pila de encabezados no se vacía.
"""

from datetime import date
from pathlib import Path

import pytest

from rag_lopd.fuentes import lopdgdd
from rag_lopd.model import Granularidad, Norma, TipoDivision

FIXTURE = Path(__file__).parent / "fixtures" / "lopdgdd-recorte.xml"
HOY = date(2026, 9, 13)


@pytest.fixture(scope="module")
def norma() -> Norma:
    return lopdgdd.parsear(FIXTURE.read_bytes(), hoy=HOY)


def _articulo(norma: Norma, identificador: str):
    return next(a for a in norma.articulos if str(a.id) == identificador)


def test_el_numero_del_articulo_sale_del_titulo_y_no_del_id(norma: Norma) -> None:
    # El bloque del artículo 10 tiene id="a1-2": el BOE recicla los sufijos.
    # Construir el id a partir del número daría "a10", que es otro artículo distinto.
    articulo = _articulo(norma, "lopdgdd:art-10")

    assert articulo.titulo.startswith("Tratamiento de datos de naturaleza penal")
    assert [str(u.id) for u in articulo.unidades] == [
        "lopdgdd:art-10.1",
        "lopdgdd:art-10.2",
        "lopdgdd:art-10.3",
    ]


def test_un_parrafo_sin_marcador_continua_el_apartado_anterior(norma: Norma) -> None:
    articulo = _articulo(norma, "lopdgdd:art-7")
    primero = articulo.unidades[0]

    assert len(articulo.unidades) == 2
    assert "mayor de catorce años" in primero.texto
    assert "Se exceptúan los supuestos" in primero.texto, "el párrafo huérfano es parte del 7.1"
    assert not primero.texto.startswith("1."), "el marcador no forma parte del texto"


def test_la_ruta_se_reconstruye_con_una_pila_de_encabezados(norma: Norma) -> None:
    assert _articulo(norma, "lopdgdd:art-7").ruta == "LOPDGDD · TÍTULO II · Artículo 7"
    assert (
        _articulo(norma, "lopdgdd:art-53bis").ruta
        == "LOPDGDD · TÍTULO VII · CAPÍTULO I · Sección 2 · Artículo 53 bis"
    )


def test_una_disposicion_no_hereda_el_ultimo_titulo(norma: Norma) -> None:
    # En el documento, la disposición adicional vigésima primera va detrás del TÍTULO X.
    # Si la pila no se vacía, acaba con una ruta que no es la suya.
    disposicion = _articulo(norma, "lopdgdd:da-21")

    assert disposicion.ruta == "LOPDGDD · Disposición adicional vigésima primera"
    assert "TÍTULO" not in disposicion.ruta
    assert disposicion.id.tipo is TipoDivision.DISPOSICION_ADICIONAL


def test_el_ordinal_escrito_con_letra_se_resuelve_por_el_sufijo_del_id(norma: Norma) -> None:
    # "vigésima primera" = 21, y el bloque tiene id="da-21". Esta correspondencia es la
    # suposición sobre la que descansa la numeración de todas las disposiciones.
    disposicion = _articulo(norma, "lopdgdd:da-21")

    assert disposicion.titulo == "Educación digital."


def test_un_articulo_sin_apartados_numerados_cae_al_fallback(norma: Norma) -> None:
    articulo = _articulo(norma, "lopdgdd:art-53bis")

    assert len(articulo.unidades) == 1
    assert articulo.unidades[0].granularidad is Granularidad.ARTICULO
    assert str(articulo.unidades[0].id) == "lopdgdd:art-53bis"


def test_las_versiones_historicas_se_conservan_pero_no_son_vigentes(norma: Norma) -> None:
    # El artículo 2 se modificó en 2021: antes tenía 4 apartados y ahora tiene 5.
    # Es material directo para una pregunta de tipo `temporal` del eval set.
    articulo = _articulo(norma, "lopdgdd:art-2")
    vigentes = [u for u in articulo.unidades if u.vigente]
    antiguas = [u for u in articulo.unidades if not u.vigente]

    assert len(antiguas) == 4
    assert len(vigentes) == 5
    assert all(u.vigente_hasta == date(2021, 6, 16) for u in antiguas)
    assert all(u.vigente_desde == date(2021, 6, 16) for u in vigentes)


def test_una_version_futura_todavia_no_cuenta() -> None:
    # Con la fecha puesta antes de la reforma de 2021, la versión vigente es la antigua.
    norma = lopdgdd.parsear(FIXTURE.read_bytes(), hoy=date(2020, 1, 1))
    articulo = _articulo(norma, "lopdgdd:art-2")

    assert len([u for u in articulo.unidades if u.vigente]) == 4


def test_los_metadatos_vienen_del_propio_boe(norma: Norma) -> None:
    assert norma.identificador_oficial == "BOE-A-2018-16673"
    assert norma.eli == "https://www.boe.es/eli/es/lo/2018/12/05/3"


def test_el_recorte_se_mantiene_por_encima_del_umbral(norma: Norma) -> None:
    assert norma.proporcion_partida_en_apartados() >= lopdgdd.UMBRAL_PARTIDO


def test_la_url_apunta_a_la_legislacion_consolidada() -> None:
    url = lopdgdd.url_norma("https://www.boe.es/datosabiertos/api", "BOE-A-2018-16673")

    assert url.endswith("/legislacion-consolidada/id/BOE-A-2018-16673")
    assert lopdgdd.ACEPTA == "application/xml", "el BOE responde 400 ante el Accept por defecto"
