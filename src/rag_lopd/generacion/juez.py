"""El juez: ¿el contenido de lo que respondió el sistema es correcto?

`evaluacion.py` mide comportamiento (contesta, calla, cita) pero no puede ver si una respuesta que
"responde" y cita dice algo equivocado: e-010 y e-026 lo demostraron en la primera pasada. Para eso
hace falta alguien que lea la respuesta y la compare con la esperada. Aquí ese alguien es otro
modelo de lenguaje, de otra familia que el generador para que no se favorezca a sí mismo.

Un juez es un instrumento de medida y hay que calibrarlo antes de fiarse de él. Por eso:

- Juzga **contra la respuesta de referencia** del eval set (verificada por una persona) y contra el
  texto de la norma en que se apoya, no contra su propio conocimiento del derecho.
- La salida lleva el `motivo` antes del `veredicto`: se pide razonar antes de decidir, y el motivo
  permite auditar a mano cada juicio.
- Un juicio que no se puede leer es `INVALIDO`, un estado propio: no se disfraza de incorrecta.
- `calibrar` compara los veredictos del juez con etiquetas manuales y da el acuerdo (bruto y
  corregido por azar) y cada discrepancia. Mientras no se haya hecho, las cifras del juez son
  provisionales.

Versionado como el prompt del generador (`VERSION`): cambiar la rúbrica mirando los resultados la
contaminaría.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from rag_lopd.eval.modelo import EvalSet, Pregunta, TipoPregunta
from rag_lopd.generacion.evaluacion import Observacion, Proporcion
from rag_lopd.generacion.modelo import ModeloDeLenguaje, Uso
from rag_lopd.model import UnidadIndexable

VERSION = "j1"

SISTEMA = """\
Eres un corrector estricto de un sistema de preguntas y respuestas sobre protección de datos en \
España (RGPD y LOPDGDD). Recibes la PREGUNTA, la RESPUESTA DE REFERENCIA (verificada por una \
persona), el TEXTO DE LA NORMA en el que se apoya la referencia (cuando existe) y la RESPUESTA DEL \
SISTEMA. Decides si la respuesta del sistema es correcta.

Hay dos casos y el mensaje te dice cuál es.

CASO A, la pregunta tiene respuesta en la norma:
- "correcta": contiene lo esencial de la referencia (cifras, plazos, condiciones, sujetos) y nada \
de lo que afirma contradice la referencia ni el texto de la norma. Usar otras palabras o dar más \
detalle correcto no importa.
- "parcial": acierta una parte esencial pero omite otra parte esencial de la referencia, o añade \
una afirmación secundaria que contradice la norma.
- "incorrecta": no contiene lo esencial de la referencia, lo contradice o responde a otra cosa.

CASO B, la pregunta no tiene respuesta en la norma (la referencia explica por qué) y el sistema \
debió abstenerse, pero contestó:
- "correcta": se limita a lo que la norma dice y deja claro que no regula lo preguntado.
- "parcial": mezcla algo correcto con una afirmación que la norma no sostiene.
- "incorrecta": afirma como si fuera norma algo que la referencia dice que el corpus no contiene.

Reglas:
- Juzga solo contra la referencia y el texto de la norma que se te dan, no con tu conocimiento.
- No premies la longitud ni castigues la brevedad: importa lo esencial.
- No juzgues las citas: se miden aparte.
- La referencia puede mencionar una redacción anterior de la norma que no aparece en el texto que \
se te da: acéptala como cierta. Si la respuesta menciona una redacción anterior claramente \
etiquetada como tal, no es un error salvo que la presente como la regla actual.

Devuelve únicamente un objeto JSON con estas claves, en este orden y ninguna más:
{"motivo": "<una frase concreta: qué elemento esencial acierta o falla>", \
"veredicto": "<correcta|parcial|incorrecta>"}"""


class Veredicto(StrEnum):
    CORRECTA = "correcta"
    PARCIAL = "parcial"
    INCORRECTA = "incorrecta"
    INVALIDO = "invalido"
    """El juez no devolvió el JSON pedido. Es un fallo del instrumento, no una decisión."""


class _Salida(BaseModel):
    """El JSON que se le pide al juez. Privado: lo que sale hacia fuera es `Juicio`."""

    motivo: str = ""
    veredicto: Veredicto

    @field_validator("veredicto", mode="before")
    @classmethod
    def _normalizar(cls, valor: object) -> object:
        return valor.strip().lower() if isinstance(valor, str) else valor


class Juicio(BaseModel):
    model_config = ConfigDict(frozen=True)

    pregunta_id: str
    tipo: TipoPregunta
    veredicto: Veredicto
    motivo: str = ""
    uso: Uso = Uso()


# --- construir el mensaje -----------------------------------------------------------------------


def texto_de_fuente(pregunta: Pregunta, unidades: list[UnidadIndexable]) -> str:
    """El texto vigente de las unidades que sustentan la referencia. Si una fuente apunta a un
    apartado que el corpus no tiene partido, se usa su artículo entero."""
    trozos: list[str] = []
    vistos: set[str] = set()
    for fuente in pregunta.fuente:
        coincidentes = [u for u in unidades if u.id == fuente]
        if not coincidentes:
            coincidentes = [
                u for u in unidades if u.id.unidad_de_contexto == fuente.unidad_de_contexto
            ]
        for unidad in coincidentes:
            if str(unidad.id) not in vistos and unidad.vigente:
                vistos.add(str(unidad.id))
                trozos.append(f"[{unidad.id}] {unidad.texto}")
    return "\n\n".join(trozos)


def construir_usuario(pregunta: Pregunta, norma: str, respuesta: str) -> str:
    if pregunta.debe_abstenerse:
        caso = "B (no hay respuesta en la norma; el sistema debió abstenerse y contestó)"
        bloque_norma = ""
    else:
        caso = "A (hay respuesta en la norma)"
        bloque_norma = f"TEXTO DE LA NORMA EN LA QUE SE APOYA LA REFERENCIA:\n{norma}\n\n"
    notas = f"CRITERIO DEL REVISOR: {pregunta.notas}\n\n" if pregunta.notas.strip() else ""
    return (
        f"CASO: {caso}\n\n"
        f"PREGUNTA: {pregunta.pregunta}\n\n"
        f"RESPUESTA DE REFERENCIA: {pregunta.respuesta}\n\n"
        f"{notas}{bloque_norma}"
        f"RESPUESTA DEL SISTEMA: {respuesta}"
    )


# --- juzgar -------------------------------------------------------------------------------------

_VALLA_CODIGO = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _leer_salida(texto: str) -> _Salida | None:
    encaje = _VALLA_CODIGO.match(texto)
    limpio = encaje.group(1) if encaje else texto.strip()
    try:
        return _Salida.model_validate_json(limpio)
    except ValidationError:
        return None


def juzgar(
    juez: ModeloDeLenguaje, pregunta: Pregunta, respuesta: str, unidades: list[UnidadIndexable]
) -> Juicio:
    completado = juez.completar(
        SISTEMA, construir_usuario(pregunta, texto_de_fuente(pregunta, unidades), respuesta)
    )
    salida = _leer_salida(completado.texto)
    if salida is None or salida.veredicto is Veredicto.INVALIDO:
        return Juicio(
            pregunta_id=pregunta.id,
            tipo=pregunta.tipo,
            veredicto=Veredicto.INVALIDO,
            motivo=completado.texto[:300],
            uso=completado.uso,
        )
    return Juicio(
        pregunta_id=pregunta.id,
        tipo=pregunta.tipo,
        veredicto=salida.veredicto,
        motivo=salida.motivo,
        uso=completado.uso,
    )


def juzgar_pasada(
    juez: ModeloDeLenguaje,
    observaciones: list[Observacion],
    eval_set: EvalSet,
    unidades: list[UnidadIndexable],
    *,
    previos: dict[str, Juicio] | None = None,
    al_terminar: Callable[[Juicio], None] | None = None,
) -> dict[str, Juicio]:
    """Juzga cada respuesta que el sistema dio (las abstenciones no tienen nada que juzgar).

    Lo ya juzgado en `previos` no se vuelve a pagar: se reutiliza. Se repite, en cambio, un juicio
    `INVALIDO` (es un fallo del instrumento, no un resultado) y uno hecho con otro tipo de
    pregunta del que tiene ahora: ese se juzgó contra otra referencia y otro caso de la rúbrica.
    Si cambia solo el texto de la referencia, el tipo no lo delata: borra el fichero de juicios.
    """
    preguntas = {p.id: p for p in eval_set.preguntas}
    juicios: dict[str, Juicio] = dict(previos or {})
    for observacion in observaciones:
        if not observacion.respuesta.responde:
            continue
        pregunta = preguntas[observacion.pregunta_id]
        previo = juicios.get(pregunta.id)
        if (
            previo is not None
            and previo.veredicto is not Veredicto.INVALIDO
            and previo.tipo is pregunta.tipo
        ):
            continue
        juicio = juzgar(juez, pregunta, observacion.respuesta.texto, unidades)
        juicios[observacion.pregunta_id] = juicio
        if al_terminar is not None:
            al_terminar(juicio)
    return juicios


# --- métricas -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class ResumenJuicios:
    exactitud: Proporcion
    """De todas las preguntas con respuesta, cuántas el sistema contestó **correctamente**. Callar
    cuenta como fallo: es lo que ve quien pregunta."""

    exactitud_de_las_contestadas: Proporcion
    """De las con respuesta que el sistema sí contestó, cuántas correctas. Mide el contenido con
    independencia de cuánto se calla."""

    parciales: int
    incorrectas: int
    """Ambas sobre las con respuesta que se contestaron."""

    exactitud_por_tipo: dict[TipoPregunta, Proporcion]
    """Como `exactitud`, por tipo, solo para los tipos con respuesta."""

    sobre_respuesta_grave: Proporcion
    """De las sin respuesta que el sistema contestó, cuántas afirman algo que la norma no
    sostiene (`incorrecta`). Es la sobre-respuesta que sí hace daño."""

    juicios_invalidos: int
    uso: Uso


def resumir_juicios(observaciones: list[Observacion], juicios: dict[str, Juicio]) -> ResumenJuicios:
    con_respuesta = [o for o in observaciones if not o.debe_abstenerse]
    contestadas = [o for o in con_respuesta if o.respuesta.responde]
    sobre = [o for o in observaciones if o.debe_abstenerse and o.respuesta.responde]

    def veredicto(o: Observacion) -> Veredicto | None:
        juicio = juicios.get(o.pregunta_id)
        return juicio.veredicto if juicio else None

    def correcta(o: Observacion) -> bool:
        return o.respuesta.responde and veredicto(o) is Veredicto.CORRECTA

    por_tipo: dict[TipoPregunta, Proporcion] = {}
    for tipo in TipoPregunta:
        del_tipo = [o for o in con_respuesta if o.tipo is tipo]
        if del_tipo:
            por_tipo[tipo] = Proporcion(
                casos=len(del_tipo), exitos=sum(1 for o in del_tipo if correcta(o))
            )

    uso = Uso()
    for juicio in juicios.values():
        uso = uso + juicio.uso

    return ResumenJuicios(
        exactitud=Proporcion(
            casos=len(con_respuesta), exitos=sum(correcta(o) for o in con_respuesta)
        ),
        exactitud_de_las_contestadas=Proporcion(
            casos=len(contestadas), exitos=sum(correcta(o) for o in contestadas)
        ),
        parciales=sum(1 for o in contestadas if veredicto(o) is Veredicto.PARCIAL),
        incorrectas=sum(1 for o in contestadas if veredicto(o) is Veredicto.INCORRECTA),
        exactitud_por_tipo=por_tipo,
        sobre_respuesta_grave=Proporcion(
            casos=len(sobre), exitos=sum(1 for o in sobre if veredicto(o) is Veredicto.INCORRECTA)
        ),
        juicios_invalidos=sum(1 for j in juicios.values() if j.veredicto is Veredicto.INVALIDO),
        uso=uso,
    )


# --- calibración: ¿se puede uno fiar del juez? --------------------------------------------------


class Etiqueta(BaseModel):
    """Lo que dice una revisión manual de una respuesta. Es la vara de medir del juez, así que
    lleva la respuesta copiada: el fichero se entiende sin la pasada que lo originó."""

    model_config = ConfigDict(frozen=True)

    pregunta_id: str
    veredicto: Veredicto
    respuesta: str = ""
    nota: str = ""


@dataclass(frozen=True)
class Discrepancia:
    pregunta_id: str
    etiqueta: Veredicto
    juez: Veredicto
    motivo_del_juez: str


@dataclass(frozen=True)
class Acuerdo:
    casos: int
    coinciden: int
    coinciden_en_correcta: int
    """Acuerdo en la única distinción que alimenta la cifra de exactitud: correcta frente a no."""

    kappa: float
    """Cohen: el acuerdo por encima del que habría por azar. Con muchas "correcta" el acuerdo bruto
    engaña, y el kappa no."""

    matriz: dict[tuple[Veredicto, Veredicto], int]
    """(etiqueta, juez) -> cuántas veces."""

    discrepancias: tuple[Discrepancia, ...]

    @property
    def bruto(self) -> Proporcion:
        return Proporcion(casos=self.casos, exitos=self.coinciden)

    @property
    def binario(self) -> Proporcion:
        return Proporcion(casos=self.casos, exitos=self.coinciden_en_correcta)


def _kappa(pares: list[tuple[Veredicto, Veredicto]]) -> float:
    n = len(pares)
    if n == 0:
        return 0.0
    observado = sum(1 for a, b in pares if a is b) / n
    etiquetas = Counter(a for a, _ in pares)
    jueces = Counter(b for _, b in pares)
    azar = sum(etiquetas[v] * jueces[v] for v in Veredicto) / (n * n)
    return 1.0 if azar == 1.0 else (observado - azar) / (1 - azar)


def calibrar(juicios: dict[str, Juicio], etiquetas: list[Etiqueta]) -> Acuerdo:
    """Compara al juez con las etiquetas, solo en lo que ambos han visto."""
    pares: list[tuple[Veredicto, Veredicto]] = []
    discrepancias: list[Discrepancia] = []
    for etiqueta in etiquetas:
        juicio = juicios.get(etiqueta.pregunta_id)
        if juicio is None:
            continue
        pares.append((etiqueta.veredicto, juicio.veredicto))
        if etiqueta.veredicto is not juicio.veredicto:
            discrepancias.append(
                Discrepancia(
                    pregunta_id=etiqueta.pregunta_id,
                    etiqueta=etiqueta.veredicto,
                    juez=juicio.veredicto,
                    motivo_del_juez=juicio.motivo,
                )
            )
    matriz = dict(Counter(pares))
    return Acuerdo(
        casos=len(pares),
        coinciden=sum(1 for a, b in pares if a is b),
        coinciden_en_correcta=sum(
            1 for a, b in pares if (a is Veredicto.CORRECTA) == (b is Veredicto.CORRECTA)
        ),
        kappa=_kappa(pares),
        matriz=matriz,
        discrepancias=tuple(discrepancias),
    )


def leer_juicios(texto: str) -> dict[str, Juicio]:
    juicios = [Juicio.model_validate_json(x) for x in texto.splitlines() if x.strip()]
    return {j.pregunta_id: j for j in juicios}


def leer_etiquetas(texto: str) -> list[Etiqueta]:
    return [Etiqueta.model_validate(json.loads(x)) for x in texto.splitlines() if x.strip()]
