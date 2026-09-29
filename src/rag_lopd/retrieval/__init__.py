"""Recuperación: el contrato común y los motores que lo cumplen.

`modelo.py` fija qué entra y qué sale de cualquier recuperador. `corpus.py` carga las unidades
indexables desde `data/processed/`. `bm25.py` es el primer motor —la referencia contra la que se
mide todo lo demás—. `evaluacion.py` mide cualquier motor contra el eval set.
"""
