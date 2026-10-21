"""Ingesta de la LOPDGDD desde la API de legislación consolidada del BOE.

Esta es la fuente difícil, y conviene saber por qué antes de leer el código. Tres trampas,
las tres verificadas contra el servidor real y documentadas en `docs/research/api-boe.md`:

1. **Los ids de bloque no se pueden construir.** El artículo 10 es `a1-2` y el 20 es `a2-2`:
   el BOE recicla los sufijos. Hay que leer el número del atributo `titulo`, nunca del `id`.
2. **Dentro del artículo no hay estructura.** Todo son `<p class="parrafo">` y el "1." del
   apartado es texto plano al principio de la cadena. Los apartados salen con una regex, y
   58 de los 144 preceptos no tienen apartados numerados en absoluto.
3. **La jerarquía es plana.** Los `TÍTULO`/`CAPÍTULO`/`Sección` son bloques hermanos que
   aparecen en el orden del documento, no padres. Se reconstruye llevando una pila mientras
   se recorre. Ojo: las disposiciones adicionales van *después* del TÍTULO X, así que
   heredarían una ruta falsa si no se vacía la pila al llegar a ellas.

Y una cuarta, en el transporte: la API responde 400 si no le mandas una cabecera Accept
explícita. El `*/*` por defecto de httpx no le vale.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
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

SLUG = "lopdgdd"
ACEPTA = "application/xml"

UMBRAL_PARTIDO = 0.75
"""Fracción mínima de unidades vigentes que deben salir partidas en apartados.

Hoy el parser saca 0,83. Si el BOE cambia el formato o la regex se rompe, esto cae y la ingesta
falla en vez de dejar un corpus silenciosamente peor. El valor no es caprichoso: es el resultado
medido menos un margen, y se sube cuando se mejora el parser."""

_NOMBRE = "lopdgdd.xml"
_SEPARADOR_RUTA = " · "

_ARTICULO = re.compile(r"^Artículo\s+(\d+(?:\s+bis|\s+ter|\s+quater)?)$")
_DISPOSICION = re.compile(r"^Disposición\s+(adicional|transitoria|derogatoria|final)\b")
_APARTADO = re.compile(r"^(\d+)\.\s+")
_RANGO_ENCABEZADO = {"TÍTULO": 0, "CAPÍTULO": 1, "SECCIÓN": 2}

_TIPO_POR_DISPOSICION = {
    "adicional": TipoDivision.DISPOSICION_ADICIONAL,
    "transitoria": TipoDivision.DISPOSICION_TRANSITORIA,
    "derogatoria": TipoDivision.DISPOSICION_DEROGATORIA,
    "final": TipoDivision.DISPOSICION_FINAL,
}


def url_norma(api_base: str, identificador: str) -> str:
    return f"{api_base}/legislacion-consolidada/id/{identificador}"


def descargar(descargador: Descargador, api_base: str, identificador: str) -> Path:
    """Una sola petición trae la norma entera (~410 KB), no 169 peticiones por bloque."""
    return descargador.obtener(url_norma(api_base, identificador), _NOMBRE, acepta=ACEPTA)


def parsear(xml: bytes, *, hoy: date | None = None) -> Norma:
    hoy = hoy or date.today()
    raiz = ET.fromstring(xml)

    articulos: list[Articulo] = []
    encabezados: list[str] = []

    for bloque in raiz.findall(".//bloque"):
        tipo_bloque = bloque.get("tipo")
        titulo = (bloque.get("titulo") or "").strip()

        if tipo_bloque == "encabezado":
            _apilar(encabezados, titulo)
            continue
        if tipo_bloque != "precepto":
            continue  # preámbulo y firma no son unidades recuperables

        identificador = _identificador(bloque)
        if identificador is None:
            continue
        if identificador.tipo is not TipoDivision.ARTICULO:
            # Las disposiciones van detrás del último TÍTULO: si no vaciamos la pila,
            # heredarían una ruta que no es suya.
            encabezados.clear()

        articulos.append(_precepto(bloque, identificador, titulo, encabezados, hoy))

    return Norma(
        slug=SLUG,
        titulo=(
            "Ley Orgánica 3/2018, de Protección de Datos Personales "
            "y garantía de los derechos digitales"
        ),
        identificador_oficial=_identificador_oficial(raiz),
        eli=_eli(raiz),
        fecha_consolidacion=None,
        articulos=tuple(articulos),
    )


def ingerir(
    descargador: Descargador, api_base: str, identificador: str, *, hoy: date | None = None
) -> Norma:
    return parsear(descargar(descargador, api_base, identificador).read_bytes(), hoy=hoy)


# --- interiores ------------------------------------------------------------


def _apilar(encabezados: list[str], titulo: str) -> None:
    """Mantiene la pila TÍTULO → CAPÍTULO → Sección según el rango del encabezado."""
    palabra = titulo.split()[0].upper() if titulo else ""
    rango = _RANGO_ENCABEZADO.get(palabra)
    if rango is None:
        return
    del encabezados[rango:]
    encabezados.append(titulo)


def _identificador(bloque: ET.Element) -> Identificador | None:
    titulo = (bloque.get("titulo") or "").strip()

    encaje = _ARTICULO.match(titulo)
    if encaje is not None:
        return Identificador(
            norma=SLUG,
            tipo=TipoDivision.ARTICULO,
            numero=encaje.group(1).replace(" ", ""),
        )

    encaje = _DISPOSICION.match(titulo)
    if encaje is not None:
        # El ordinal va escrito con letra ("vigésima primera"), pero el sufijo del id sí es
        # secuencial dentro de cada tipo: da=1, da-2=2, ..., da-21=vigésima primera.
        sufijo = (bloque.get("id") or "").split("-")
        return Identificador(
            norma=SLUG,
            tipo=_TIPO_POR_DISPOSICION[encaje.group(1)],
            numero=sufijo[1] if len(sufijo) > 1 else "1",
        )

    return None


def _precepto(
    bloque: ET.Element,
    identificador: Identificador,
    titulo_bloque: str,
    encabezados: list[str],
    hoy: date,
) -> Articulo:
    versiones = _versiones_ordenadas(bloque, hoy)
    ruta = _SEPARADOR_RUTA.join(["LOPDGDD", *encabezados, titulo_bloque])

    unidades: list[UnidadIndexable] = []
    texto_vigente = ""
    titulo = titulo_bloque

    for version, desde, hasta in versiones:
        parrafos = [_texto(p) for p in version.findall("p")]
        rubrica = parrafos[0] if parrafos and _es_rubrica(version) else ""
        cuerpo = parrafos[1:] if rubrica else parrafos
        texto = "\n".join(t for t in cuerpo if t)

        if hasta is None:
            texto_vigente = texto
            titulo = _rubrica_limpia(rubrica, titulo_bloque) or titulo_bloque

        unidades.extend(_unidades(identificador, cuerpo, texto, ruta, desde, hasta))

    return Articulo(
        id=identificador,
        titulo=titulo,
        ruta=ruta,
        texto=texto_vigente,
        unidades=tuple(unidades),
    )


def _unidades(
    identificador: Identificador,
    parrafos: list[str],
    texto_completo: str,
    ruta: str,
    desde: date,
    hasta: date | None,
) -> list[UnidadIndexable]:
    """Agrupa los párrafos en apartados numerados.

    Un párrafo sin marcador continúa el apartado anterior: en el artículo 7, "Se exceptúan los
    supuestos..." pertenece al apartado 1 aunque no lleve número.
    """
    grupos: list[tuple[str, list[str]]] = []
    for parrafo in parrafos:
        if not parrafo:
            continue
        encaje = _APARTADO.match(parrafo)
        if encaje is not None:
            grupos.append((encaje.group(1), [parrafo[encaje.end() :]]))
        elif grupos:
            grupos[-1][1].append(parrafo)
        # Un párrafo antes del primer apartado numerado se queda solo en el texto del
        # artículo: meterlo dentro del apartado 1 cambiaría lo que dice la norma.

    if not grupos:
        return [
            UnidadIndexable(
                id=identificador,
                texto=texto_completo,
                granularidad=Granularidad.ARTICULO,
                ruta=ruta,
                vigente_desde=desde,
                vigente_hasta=hasta,
            )
        ]

    return [
        UnidadIndexable(
            id=Identificador(
                norma=identificador.norma,
                tipo=identificador.tipo,
                numero=identificador.numero,
                apartado=numero,
            ),
            texto="\n".join(lineas).strip(),
            granularidad=Granularidad.APARTADO,
            ruta=ruta,
            vigente_desde=desde,
            vigente_hasta=hasta,
        )
        for numero, lineas in grupos
    ]


def _versiones_ordenadas(
    bloque: ET.Element, hoy: date
) -> list[tuple[ET.Element, date, date | None]]:
    """Devuelve (version, vigente_desde, vigente_hasta) en orden cronológico.

    La API entrega todas las versiones históricas juntas y no acepta filtrar por fecha
    (`?fecha=` responde 400), así que el recorte se hace aquí.
    """
    versiones = sorted(
        bloque.findall("version"), key=lambda v: v.get("fecha_vigencia") or "00000000"
    )
    aplicables = [v for v in versiones if _fecha(v.get("fecha_vigencia")) <= hoy] or versiones[:1]

    salida: list[tuple[ET.Element, date, date | None]] = []
    for indice, version in enumerate(aplicables):
        desde = _fecha(version.get("fecha_vigencia"))
        siguiente = aplicables[indice + 1] if indice + 1 < len(aplicables) else None
        hasta = _fecha(siguiente.get("fecha_vigencia")) if siguiente is not None else None
        salida.append((version, desde, hasta))
    return salida


def _es_rubrica(version: ET.Element) -> bool:
    primero = version.find("p")
    return primero is not None and primero.get("class") in {"articulo", "sangrado_articulo"}


def _rubrica_limpia(rubrica: str, titulo_bloque: str) -> str:
    """De 'Artículo 7. Consentimiento de los menores de edad.' saca la parte con contenido."""
    return rubrica.removeprefix(titulo_bloque).lstrip(". ").strip()


def _identificador_oficial(raiz: ET.Element) -> str:
    nodo = raiz.find(".//identificador")
    return _texto(nodo) if nodo is not None else "BOE-A-2018-16673"


def _eli(raiz: ET.Element) -> str | None:
    nodo = raiz.find(".//url_eli")
    texto = _texto(nodo) if nodo is not None else ""
    return texto or None


def _fecha(crudo: str | None) -> date:
    if not crudo or len(crudo) != 8:
        return date.min
    return date(int(crudo[0:4]), int(crudo[4:6]), int(crudo[6:8]))


def _texto(nodo: ET.Element | None) -> str:
    if nodo is None:
        return ""
    return " ".join("".join(nodo.itertext()).split())
