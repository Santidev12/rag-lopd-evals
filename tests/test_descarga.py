import json
from pathlib import Path

import httpx
import pytest
import respx

from rag_lopd.descarga import Descargador

URL = "https://example.org/norma.zip"
CONTENIDO = b"contenido de prueba"


@respx.mock
def test_descarga_una_vez_y_luego_usa_la_cache(tmp_path: Path) -> None:
    ruta = respx.get(URL).mock(return_value=httpx.Response(200, content=CONTENIDO))
    descargador = Descargador(tmp_path)

    primera = descargador.obtener(URL, "norma.zip")
    segunda = descargador.obtener(URL, "norma.zip")

    assert primera == segunda == tmp_path / "norma.zip"
    assert primera.read_bytes() == CONTENIDO
    assert ruta.call_count == 1, "la segunda llamada no debe tocar la red"


@respx.mock
def test_forzar_vuelve_a_descargar(tmp_path: Path) -> None:
    ruta = respx.get(URL).mock(return_value=httpx.Response(200, content=CONTENIDO))
    descargador = Descargador(tmp_path)

    descargador.obtener(URL, "norma.zip")
    descargador.obtener(URL, "norma.zip", forzar=True)

    assert ruta.call_count == 2


@respx.mock
def test_el_manifiesto_deja_constancia_de_la_procedencia(tmp_path: Path) -> None:
    respx.get(URL).mock(return_value=httpx.Response(200, content=CONTENIDO))
    descargador = Descargador(tmp_path)

    descargador.obtener(URL, "norma.zip")
    entrada = json.loads(descargador.ruta_manifiesto.read_text(encoding="utf-8"))["norma.zip"]

    assert entrada["url"] == URL
    assert entrada["bytes"] == len(CONTENIDO)
    assert len(entrada["sha256"]) == 64
    assert entrada["descargado_en"].endswith("+00:00"), "la fecha va en UTC, no en hora local"


@respx.mock
def test_un_error_http_no_deja_un_fichero_a_medias(tmp_path: Path) -> None:
    respx.get(URL).mock(return_value=httpx.Response(404))
    descargador = Descargador(tmp_path)

    with pytest.raises(httpx.HTTPStatusError):
        descargador.obtener(URL, "norma.zip")

    assert not (tmp_path / "norma.zip").exists()
    assert descargador.leer_manifiesto() == {}


@respx.mock
def test_se_identifica_con_un_user_agent_propio(tmp_path: Path) -> None:
    ruta = respx.get(URL).mock(return_value=httpx.Response(200, content=CONTENIDO))

    Descargador(tmp_path, user_agent="rag-lopd-evals/9.9").obtener(URL, "norma.zip")

    assert ruta.calls[0].request.headers["user-agent"] == "rag-lopd-evals/9.9"
