"""Recuperación: el contrato común y los motores que lo cumplen.

`modelo.py` fija qué entra y qué sale de cualquier recuperador. `corpus.py` carga las unidades
indexables desde `data/processed/`. `bm25.py` y `denso.py` (con `embeddings.py` e
`indice_denso.py`) son los dos motores. `evaluacion.py` mide recall contra el eval set.
`abstencion.py` mide algo distinto: si el score de recuperación por sí solo separa las preguntas
con respuesta de las que no la tienen — el diagnóstico detrás de la política de abstención.
"""
