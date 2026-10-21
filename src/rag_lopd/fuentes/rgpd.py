"""Ingesta del RGPD desde el Formex XML consolidado de Cellar.

Por qué Cellar y no eur-lex.europa.eu: EUR-Lex responde con un reto JS de AWS WAF a cualquier
cliente que no sea un navegador. Cellar sirve el mismo contenido sin ese obstáculo, y además en
Formex XML, que marca los apartados explícitamente en lugar de dejarlos en el texto.
Ver `docs/research/eurlex-rgpd.md`.

Forma del documento (verificada sobre el fichero real):

    <ARTICLE IDENTIFIER="033">
      <TI.ART>Artículo 33</TI.ART>
      <STI.ART>Notificación de una violación de la seguridad...</STI.ART>
      <PARAG IDENTIFIER="033.001"><NO.PARAG>1.</NO.PARAG><ALINEA>...</ALINEA></PARAG>

y la jerarquía de capítulos y secciones cuelga de elementos <DIVISION> anidados.
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile
from datetime import date
from pathlib import Path

from rag_lopd.descarga import Descargador
from rag_lopd.model import (
    Articulo,
    Granularidad,
    Identificador,
    Norma,
    TipoDivision,
    UnidadIndexable,
)

SLUG = "rgpd"
ELI = "http://data.europa.eu/eli/reg/2016/679/oj"

_NOMBRE_ZIP = "rgpd-formex.zip"
_SEPARADOR_RUTA = " · "

# Etiquetas tras las cuales el texto plano necesita un salto de línea o un espacio para no
# quedar pegado: <NO.P>a)</NO.P><TXT>describir...</TXT> saldría como "a)describir...".
_BLOQUE = {"P", "ITEM", "DLIST.ITEM", "ALINEA", "TXT", "DEFINITION", "TI", "STI"}
_MARCADOR = {"NO.P", "PREFIX", "NO.PARAG", "TERM"}


def url_formex(cellar_base: str, celex: str) -> str:
    """URL de descarga directa del Formex consolidado, sin negociación de contenido."""
    return f"{cellar_base}/{celex}.SPA.fmx4.CONSLEG_{celex}_0000030_SPA.fmx4.zip"


def descargar(descargador: Descargador, cellar_base: str, celex: str) -> Path:
    return descargador.obtener(url_formex(cellar_base, celex), _NOMBRE_ZIP)


def extraer_xml(ruta_zip: Path) -> bytes:
    """Saca el XML del acto del zip, descartando el `.doc.xml` (que son solo metadatos)."""
    with zipfile.ZipFile(io.BytesIO(ruta_zip.read_bytes())) as z:
        candidatos = [n for n in z.namelist() if n.endswith(".xml") and not n.endswith(".doc.xml")]
        if len(candidatos) != 1:
            raise ValueError(
                f"esperaba exactamente un XML del acto en {ruta_zip.name}, encontré {candidatos}"
            )
        return z.read(candidatos[0])


def parsear(xml: bytes) -> Norma:
    """Convierte el Formex XML en una `Norma` con sus artículos y apartados."""
    raiz = ET.fromstring(xml)
    padres = {hijo: padre for padre in raiz.iter() for hijo in padre}

    inicio = _fecha(raiz.find(".//INFO.CONSLEG"), "START.DATE")

    articulos = [_articulo(elemento, padres, inicio) for elemento in raiz.findall(".//ARTICLE")]
    return Norma(
        slug=SLUG,
        titulo="Reglamento (UE) 2016/679 (Reglamento General de Protección de Datos)",
        identificador_oficial=_texto(raiz.find(".//INFO.CONSLEG"), atributo="CONSLEG.REF"),
        eli=ELI,
        fecha_consolidacion=_fecha(raiz.find(".//INFO.CONSLEG"), "CONSLEG.DATE"),
        articulos=tuple(articulos),
    )


def ingerir(descargador: Descargador, cellar_base: str, celex: str) -> Norma:
    """Descarga (si hace falta) y parsea. Es el único punto de entrada que necesita la CLI."""
    return parsear(extraer_xml(descargar(descargador, cellar_base, celex)))


# --- interiores ------------------------------------------------------------


def _articulo(
    elemento: ET.Element, padres: dict[ET.Element, ET.Element], inicio: date | None
) -> Articulo:
    numero = str(int(elemento.get("IDENTIFIER", "0")))
    id_articulo = Identificador(norma=SLUG, tipo=TipoDivision.ARTICULO, numero=numero)
    titulo = _texto(elemento.find("STI.ART"))
    ruta = _ruta(elemento, padres, _texto(elemento.find("TI.ART")))
    texto = _texto(elemento, excluir={"TI.ART", "STI.ART"})

    apartados = elemento.findall("PARAG")
    if apartados:
        unidades = tuple(
            UnidadIndexable(
                id=Identificador(
                    norma=SLUG,
                    tipo=TipoDivision.ARTICULO,
                    numero=numero,
                    apartado=str(int(_numero_apartado(p, indice))),
                ),
                texto=_texto(p, excluir={"NO.PARAG"}),
                granularidad=Granularidad.APARTADO,
                ruta=ruta,
                vigente_desde=inicio,
                eli=ELI,
            )
            for indice, p in enumerate(apartados, start=1)
        )
    else:
        # 17 de los 99 artículos del RGPD no tienen apartados (el 4, "Definiciones", es uno).
        # No es un fallo del parser: es el fallback del ADR 0001 y queda marcado como tal.
        unidades = (
            UnidadIndexable(
                id=id_articulo,
                texto=texto,
                granularidad=Granularidad.ARTICULO,
                ruta=ruta,
                vigente_desde=inicio,
                eli=ELI,
            ),
        )

    return Articulo(id=id_articulo, titulo=titulo, ruta=ruta, texto=texto, unidades=unidades)


def _numero_apartado(parag: ET.Element, indice: int) -> str:
    """El IDENTIFIER es '033.001'; si faltase, se cae al orden de aparición."""
    identificador = parag.get("IDENTIFIER", "")
    if "." in identificador:
        return identificador.split(".")[-1]
    return str(indice)


def _ruta(elemento: ET.Element, padres: dict[ET.Element, ET.Element], titulo_articulo: str) -> str:
    """'RGPD · CAPÍTULO IV · Sección 2 · Artículo 33'.

    Esta cadena se antepone al texto antes de embeber: reproduce el efecto del contextual
    retrieval de Anthropic sin coste de LLM, porque el contexto ya lo conocemos por la estructura.
    """
    tramos: list[str] = []
    actual = padres.get(elemento)
    while actual is not None:
        if actual.tag == "DIVISION":
            encabezado = _texto(actual.find("./TITLE/TI"))
            if encabezado:
                tramos.append(encabezado)
        actual = padres.get(actual)
    return _SEPARADOR_RUTA.join(["RGPD", *reversed(tramos), titulo_articulo])


def _fecha(elemento: ET.Element | None, atributo: str) -> date | None:
    crudo = elemento.get(atributo) if elemento is not None else None
    if not crudo or crudo.startswith("9999"):
        return None
    return date(int(crudo[0:4]), int(crudo[4:6]), int(crudo[6:8]))


def _texto(
    elemento: ET.Element | None,
    *,
    excluir: set[str] | None = None,
    atributo: str | None = None,
) -> str:
    """Aplana un subárbol Formex a texto legible.

    Traduce QUOT.START/QUOT.END a las comillas reales que representan (su atributo CODE es el
    punto Unicode en hexadecimal), respeta los saltos entre bloques y normaliza los espacios
    duros que la Oficina de Publicaciones usa en los títulos ('CAPÍTULO\\xa0IV').
    """
    if elemento is None:
        return ""
    if atributo is not None:
        return elemento.get(atributo, "")

    excluir = excluir or set()
    trozos: list[str] = []

    def visitar(nodo: ET.Element) -> None:
        if nodo.tag in {"QUOT.START", "QUOT.END"}:
            codigo = nodo.get("CODE")
            if codigo:
                trozos.append(chr(int(codigo, 16)))
            return
        if nodo.text:
            trozos.append(nodo.text)
        for hijo in nodo:
            if hijo.tag not in excluir:
                visitar(hijo)
            if hijo.tail:
                trozos.append(hijo.tail)
        if nodo.tag in _BLOQUE:
            trozos.append("\n")
        elif nodo.tag in _MARCADOR:
            trozos.append(" ")

    visitar(elemento)
    return _normalizar("".join(trozos))


def _normalizar(texto: str) -> str:
    """Colapsa espacios y líneas vacías.

    `str.split()` sin argumentos ya trata como espacio los separadores Unicode raros que usa la
    Oficina de Publicaciones (el espacio duro de "CAPÍTULO\xa0IV", entre otros), así que no hace
    falta sustituirlos a mano.
    """
    lineas = [" ".join(linea.split()) for linea in texto.split("\n")]
    return "\n".join(linea for linea in lineas if linea).strip()
