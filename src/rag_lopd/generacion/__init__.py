"""Generación: de unos artículos recuperados a una respuesta con cita, o a una abstención.

`modelo.py` fija los tipos y el contrato `ModeloDeLenguaje` (texto en, texto y tokens fuera): lo
único que cambia entre Gemini, Claude o DeepSeek. `contexto.py` reconstruye el artículo entero a
partir de las unidades recuperadas (small-to-big, ADR 0001). `prompt.py` y `responder.py` son la
política de abstención: instrucción + salida estructurada con vía `sin_respuesta` + cita
obligatoria y validada contra lo que de verdad se le dio al modelo. `gemini.py` es el primer
modelo. `evaluacion.py` mide sobre-respuesta y abstención indebida contra el eval set.
"""
