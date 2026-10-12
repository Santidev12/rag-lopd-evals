"""El prompt: la política de abstención escrita en lenguaje natural.

Versionado a propósito (`VERSION`). El prompt es una variable del experimento tanto como el
modelo: si se retoca mirando los resultados del eval set, los números dejan de ser honestos (se
estaría ajustando el prompt a las 50 preguntas). La primera medición se publica tal cual con la
versión que la produjo; cualquier cambio posterior es una versión nueva y queda registrado.

Las reglas son genéricas a propósito: describen lo que el corpus es y no es (RGPD + LOPDGDD, no
resoluciones ni casos concretos), no las preguntas del eval set.
"""

from __future__ import annotations

from rag_lopd.generacion.modelo import Contexto

VERSION = "v1"

SISTEMA = """\
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

Devuelve únicamente un objeto JSON con estas claves y ninguna más:
{"sin_respuesta": <true|false>, "respuesta": "<texto, vacío si sin_respuesta>", \
"citas": ["<identificador>", ...]}"""


def _formatear_contexto(contexto: Contexto) -> str:
    return f"[{contexto.id}] {contexto.ruta}\n{contexto.texto}"


def construir_usuario(pregunta: str, contextos: list[Contexto]) -> str:
    """El mensaje de usuario: los artículos recuperados y, después, la pregunta."""
    if contextos:
        bloque = "\n\n".join(_formatear_contexto(c) for c in contextos)
    else:
        bloque = "(no se recuperó ningún artículo)"
    return f"CONTEXTO:\n\n{bloque}\n\nPREGUNTA: {pregunta}"
