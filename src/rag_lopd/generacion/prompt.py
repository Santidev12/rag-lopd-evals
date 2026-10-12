"""El prompt: la política de abstención escrita en lenguaje natural.

Versionado a propósito. El prompt es una variable del experimento tanto como el modelo: si se
retoca mirando los resultados del eval set, los números dejan de ser honestos (se estaría
ajustando el prompt a las 50 preguntas). Cada versión se publica tal cual con sus cifras y las
anteriores siguen disponibles para reproducirlas; cualquier cambio es una versión nueva con su
motivo anotado en el ticket correspondiente.

- **v1**: la política base. Al modelo solo se le da la redacción vigente de cada artículo.
- **v2**: v1 + vigencia. Cada artículo dice desde cuándo rige su redacción actual y, si se ha
  modificado, lleva también las redacciones anteriores con su periodo. Nació de un diagnóstico
  (ticket 13): las preguntas temporales fallaban porque la información no llegaba al modelo, no
  porque la política fuera mala. Las seis temporales dejan de ser una medida limpia de v2.

Las reglas son genéricas a propósito: describen lo que el corpus es y no es (RGPD + LOPDGDD, no
resoluciones ni casos concretos), no las preguntas del eval set.
"""

from __future__ import annotations

from dataclasses import dataclass

from rag_lopd.generacion.modelo import Contexto

_BASE = """\
Eres un asistente jurídico que responde preguntas sobre protección de datos en España. Tu única \
fuente es el CONTEXTO que se te da: artículos del RGPD (Reglamento (UE) 2016/679) y de la LOPDGDD \
(Ley Orgánica 3/2018), con su identificador entre corchetes.

Reglas:
1. Responde solo con lo que dice el contexto. No uses conocimiento propio ni de otras normas, \
resoluciones o casos concretos.
2. Si el contexto no contiene lo que se pregunta, marca "sin_respuesta": true. Que los artículos \
traten el mismo tema o usen las mismas palabras no basta: tienen que responder de verdad a lo \
preguntado. Ante la duda entre inventar un dato y abstenerte, abstente.
3. Si la pregunta exige reunir varios artículos, usa todos los necesarios y cítalos todos.
4. Cada respuesta se apoya en artículos concretos: en "citas" pon los identificadores exactos de \
los artículos del contexto que usas (por ejemplo "rgpd:art-33"), sin inventar ninguno.
5. Responde en español, de forma concisa y precisa.
"""

_VIGENCIA = """\
6. Cada artículo indica desde cuándo rige su redacción actual ("Redacción vigente desde ..."). \
Algunos incluyen además una o más "Redacción anterior", con el periodo en que estuvo vigente. \
Responde con la redacción vigente, salvo que la pregunta se refiera a una etapa anterior o a \
cómo ha cambiado la norma: entonces usa la redacción anterior que corresponda e indica a qué \
periodo se refiere. Nunca presentes una redacción anterior como la regla actual. Las únicas \
fechas que puedes dar son las que figuran en el contexto.
"""

_FORMATO = """
Devuelve únicamente un objeto JSON con estas claves y ninguna más:
{"sin_respuesta": <true|false>, "respuesta": "<texto, vacío si sin_respuesta>", \
"citas": ["<identificador>", ...]}"""


@dataclass(frozen=True)
class Prompt:
    version: str
    sistema: str
    con_vigencia: bool
    """Si el contexto lleva la fecha de vigencia y las redacciones anteriores."""

    def usuario(self, pregunta: str, contextos: list[Contexto]) -> str:
        """El mensaje de usuario: los artículos recuperados y, después, la pregunta."""
        if contextos:
            bloque = "\n\n".join(self._formatear(c) for c in contextos)
        else:
            bloque = "(no se recuperó ningún artículo)"
        return f"CONTEXTO:\n\n{bloque}\n\nPREGUNTA: {pregunta}"

    def _formatear(self, contexto: Contexto) -> str:
        cabecera = f"[{contexto.id}] {contexto.ruta}"
        if not self.con_vigencia:
            return f"{cabecera}\n{contexto.texto}"

        partes = [cabecera]
        if contexto.vigente_desde is not None:
            partes.append(f"Redacción vigente desde {contexto.vigente_desde.isoformat()}:")
        partes.append(contexto.texto)
        for anterior in contexto.anteriores:
            desde = f"desde {anterior.desde.isoformat()} " if anterior.desde else ""
            partes.append(f"Redacción anterior, vigente {desde}hasta {anterior.hasta.isoformat()}:")
            partes.append(anterior.texto)
        return "\n".join(partes)


V1 = Prompt(version="v1", sistema=_BASE + _FORMATO, con_vigencia=False)
V2 = Prompt(version="v2", sistema=_BASE + _VIGENCIA + _FORMATO, con_vigencia=True)

PROMPTS: dict[str, Prompt] = {p.version: p for p in (V1, V2)}

PROMPT_POR_DEFECTO = V2
"""v2 desde el 13-oct-2026: medido con una pasada completa, arregla las temporales sin cambiar el
estado de ninguna otra pregunta (ticket 13). v1 sigue disponible con `--prompt v1`."""


def prompt_de(version: str) -> Prompt:
    try:
        return PROMPTS[version]
    except KeyError:
        raise ValueError(
            f"no hay prompt {version!r}; disponibles: {', '.join(sorted(PROMPTS))}"
        ) from None
