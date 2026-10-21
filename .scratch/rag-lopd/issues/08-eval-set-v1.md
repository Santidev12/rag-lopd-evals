# Eval set v1: las 50 preguntas

Type: task
Status: resolved

## Question

Construir el eval set con el método híbrido acordado y dejarlo versionado en el repo:

- Generar preguntas candidatas desde el corpus normalizado con un LLM, guardando el prompt y la
  semilla para que el proceso sea reproducible.
- Santiago revisa y corrige **todas** las candidatas; las descartadas se registran (por qué se
  descartaron es material de README).
- Las preguntas `fuera_de_corpus` y `trampa` las escribe él a mano: son las que no se pueden generar
  desde dentro del corpus por definición.
- Reparto objetivo: 15 factual · 12 cruzada · 6 temporal · 10 fuera de corpus · 7 trampa.
- Esquema de fila y reglas de escritura: ver `reference/anatomia-eval-set.html`.

Criterio de hecho: `eval/preguntas-v1.jsonl` en el repo, con esquema validado por un test, y el
proceso documentado en `docs/eval-set.md`.

## Progreso (24-sep-2026): 50 candidatas listas para revisar

Entregado: módulo `rag_lopd.eval` (`modelo.py`, `almacen.py`, `validacion.py`, `cli.py`),
`eval/candidatas-v0.jsonl` con las 50, `docs/eval-set.md` con el método y
`docs/eval-candidatas.md` como tabla de revisión. 84 tests en verde; ruff y mypy limpios.

Reparto exacto al objetivo: 15 factual · 12 cruzada · 6 temporal · 10 fuera de corpus · 7 trampa.
24 fuentes distintas, **todas verificadas contra el corpus real**.

Las reglas viven en el modelo, no en un documento: nada de preguntas de sí o no; una
`fuera_de_corpus` no puede declarar fuente; una `cruzada` necesita **dos artículos distintos**
(dos apartados del mismo artículo no cruzan nada); ids únicos.

Dos defensas contra que el LLM generador se invente cosas:
1. `rag-lopd eval validar` comprueba que toda fuente declarada existe en el corpus.
2. Un test de **anclas de texto**: para 15 preguntas, un término literal de la respuesta esperada
   ("72 horas", "catorce años", "dieciocho meses", "(Anulado)") debe aparecer en el texto de la
   fuente citada. Es la defensa contra el fallo más peligroso al generar preguntas con un LLM:
   que la respuesta suene impecable y el artículo citado no diga eso.

Las `temporal` salen de diferencias reales del texto consolidado: doce → dieciocho meses de
investigación previa (2023), la previsión sobre partidos políticos anulada en 2019, y la remisión
del artículo 66.1 que pasó del 64.3 al 64.4.

**Pendiente y bloqueante**: la revisión humana. Las 50 están en estado `candidata`. Hasta que
Santiago las acepte o descarte una a una, ningún número calculado con ellas es publicable.

## Cierre (26-sep-2026)

Santiago revisó las 50 y las aceptó todas: `eval/candidatas-v0.jsonl` tiene las 50 en
`estado: aceptada`. El eval set v1 queda cerrado con el reparto exacto al objetivo y cero
descartes — si en el futuro se descarta alguna al usarla de verdad, el motivo va en su campo
`notas`, no se borra la fila.
