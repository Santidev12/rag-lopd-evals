"""Tests del parser del RGPD contra un recorte real del Formex de Cellar.

El fixture `rgpd-recorte.xml` se construyó desde el fichero oficial conservando los artículos 4,
33 y 83 con las DIVISION que los envuelven. Los tests corren sin red: el parser no debe depender
de estar conectado, y una descarga en cada ejecución haría los tests lentos y frágiles.
"""

from pathlib import Path

import pytest

from rag_lopd.fuentes import rgpd
from rag_lopd.model import Granularidad, Norma

FIXTURE = Path(__file__).parent / "fixtures" / "rgpd-recorte.xml"


@pytest.fixture(scope="module")
def norma() -> Norma:
    return rgpd.parsear(FIXTURE.read_bytes())


def test_la_url_de_cellar_evita_eur_lex(norma: Norma) -> None:
    url = rgpd.url_formex("http://publications.europa.eu/resource/celex", "02016R0679-20160504")

    assert "eur-lex" not in url, "eur-lex bloquea a los clientes que no son navegador"
    assert url.endswith("CONSLEG_02016R0679-20160504_0000030_SPA.fmx4.zip")


def test_los_apartados_se_identifican_por_articulo_y_numero(norma: Norma) -> None:
    articulo = next(a for a in norma.articulos if str(a.id) == "rgpd:art-33")

    assert [str(u.id) for u in articulo.unidades] == [
        "rgpd:art-33.1",
        "rgpd:art-33.2",
        "rgpd:art-33.3",
        "rgpd:art-33.4",
        "rgpd:art-33.5",
    ]
    assert all(u.granularidad is Granularidad.APARTADO for u in articulo.unidades)


def test_un_articulo_sin_apartados_cae_al_fallback_del_adr(norma: Norma) -> None:
    # El artículo 4 son las definiciones: una lista de términos, sin apartados numerados.
    # 17 de los 99 artículos del RGPD están en este caso.
    articulo = next(a for a in norma.articulos if str(a.id) == "rgpd:art-4")

    assert len(articulo.unidades) == 1
    assert articulo.unidades[0].granularidad is Granularidad.ARTICULO
    assert str(articulo.unidades[0].id) == "rgpd:art-4"


def test_la_ruta_reconstruye_la_jerarquia(norma: Norma) -> None:
    articulo = next(a for a in norma.articulos if str(a.id) == "rgpd:art-33")

    assert articulo.ruta == "RGPD · CAPÍTULO IV · Sección 2 · Artículo 33"
    assert "\xa0" not in articulo.ruta, "los espacios duros de la Oficina de Publicaciones molestan"
    assert articulo.unidades[0].texto_para_embeber.startswith(articulo.ruta)


def test_el_texto_del_apartado_conserva_lo_que_importa(norma: Norma) -> None:
    articulo = next(a for a in norma.articulos if str(a.id) == "rgpd:art-33")
    primero = articulo.unidades[0]

    assert "72 horas" in primero.texto
    assert not primero.texto.startswith("1."), "el marcador del apartado no es parte del texto"
    assert "Notificación de una violación" not in primero.texto, "el título no se duplica dentro"


def test_las_listas_con_letras_no_quedan_pegadas(norma: Norma) -> None:
    articulo = next(a for a in norma.articulos if str(a.id) == "rgpd:art-33")
    tercero = articulo.unidades[2]

    assert "\na) describir la naturaleza" in tercero.texto
    assert "a)describir" not in tercero.texto


def test_las_comillas_del_formex_se_traducen(norma: Norma) -> None:
    # En Formex las comillas españolas son <QUOT.START CODE="00AB"/> ... <QUOT.END CODE="00BB"/>.
    articulo = next(a for a in norma.articulos if str(a.id) == "rgpd:art-4")

    assert "«datos personales»" in articulo.texto


def test_los_metadatos_de_la_norma_vienen_del_propio_fichero(norma: Norma) -> None:
    assert norma.slug == "rgpd"
    assert norma.identificador_oficial == "2016R0679"
    assert norma.eli == "http://data.europa.eu/eli/reg/2016/679/oj"
    assert norma.fecha_consolidacion is not None
    assert all(u.vigente for u in norma.unidades_vigentes())
