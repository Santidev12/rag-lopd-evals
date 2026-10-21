# Baseline de retrieval: BM25 y la pregunta de la ruta jerárquica

Type: task
Status: resolved

## Question

Antes de tocar denso, RRF o reranker, el proyecto necesita un motor de referencia y un contrato
común para medir cualquier motor futuro contra el mismo eval set.

Alcance de este ticket, recortado a propósito de la niebla original (*Retrieval híbrido y sus
baselines*):

- El contrato `Recuperador` (`buscar(consulta, k) -> list[Resultado]`), para que denso e híbrido
  se puedan medir con el mismo harness sin cambiarlo.
- Un primer motor real: BM25 sobre las unidades indexables del corpus.
- La pregunta heredada del ticket 07 (*Estrategia de chunking*): **¿anteponer la ruta jerárquica
  al texto antes de indexar mejora el recall, o solo lo parece?** Se mide, no se opina.
- Un harness mínimo: recall@k contra las preguntas `factual` y `cruzada` del eval set (las únicas
  que tienen una fuente que recuperar).

Sigue en la niebla, para un ticket propio: recuperación densa, combinación híbrida (RRF) y
reranker — y correrlos todos contra el mismo harness que deja este ticket.

## Answer

**Resuelto el 26-sep-2026.**

Entregado:

- `rag_lopd.retrieval.modelo` — `Resultado` y el protocolo `Recuperador`. Es el contrato: cualquier
  motor que lo cumpla se mide igual, sin tocar el harness.
- `rag_lopd.retrieval.corpus.cargar_unidades` — lee las `*.unidades.jsonl` de `data/processed/`,
  la única puerta de entrada al corpus para cualquier motor.
- `rag_lopd.retrieval.bm25.RecuperadorBM25` — BM25 (`rank-bm25`) con un flag `con_ruta` que decide
  si se indexa `texto_para_embeber` (ruta + texto) o solo `texto`. Es la variable del experimento,
  no una decisión tomada de antemano.
- `rag_lopd.retrieval.evaluacion.evaluar_recall` — recall@k sobre las preguntas `factual` y
  `cruzada` aceptadas. En una `cruzada` solo cuenta acierto si aparecen **todas** sus fuentes: la
  mitad de las fuentes de una pregunta cruzada no la responde.
- `rag-lopd retrieval evaluar` — corre BM25 con y sin ruta jerárquica y enseña el recall@k de las
  dos variantes, con las preguntas falladas por id. `rag-lopd retrieval buscar "..."` para probar
  una consulta a mano.
- 5 tests contra unidades y preguntas de mentira (no contra el corpus real, para que sigan
  significando lo mismo si el corpus cambia). Ruff y mypy limpios; se añadió `rank-bm25` a las
  dependencias y una excepción de mypy para sus stubs, que no existen.

**La pregunta de la ruta jerárquica sigue sin número real**: el harness ya la mide
(`rag-lopd retrieval evaluar`), pero necesita el corpus ingerido de verdad en esta máquina para
dar un resultado que signifique algo — correr `rag-lopd ingest` y luego `rag-lopd retrieval
evaluar` es el primer paso de la siguiente sesión, no de esta.

Quedan en la niebla, ahora más concretas porque ya hay contrato y harness: recuperación densa
(BGE-M3, decidido en el ticket 04), combinación híbrida por RRF, y reranker sobre el top-10 —
las tres, medidas con el mismo `evaluar_recall` que ya existe.

## Números reales (29-sep-2026)

Corridos contra el corpus ingerido de verdad (728 unidades):

| Variante | Recall@10 (apartado) |
| --- | --- |
| Con ruta jerárquica | 37,0 % (10/27) |
| Sin ruta jerárquica | 37,0 % (10/27) |

**Misma cifra y las mismas 17 preguntas falladas, exactamente.** La ruta jerárquica no cambió ni
un solo resultado. Contesta la pregunta heredada del ticket 07: **no, anteponerla no ayuda al
recall con BM25** — y tiene una explicación mecánica, no es ruido: las preguntas del eval set
nunca usan vocabulario de capítulos o secciones ("RGPD", "Capítulo IV"), así que esos tokens
nunca casan con la consulta. Su única influencia es alargar un poco cada documento, y esa
normalización por longitud no basta para reordenar el top-10. Esto puede no valer para un motor
denso, donde la ruta sí podría aportar señal semántica aunque no haya coincidencia literal — se
vuelve a medir cuando exista ese motor.

**Diagnóstico de 3 de las 17 falladas** (e-001, e-002, e-004) reveló dos modos de fallo
distintos, no uno:

1. **Hueco léxico real** (e-001, e-002): la pregunta describe la situación en lenguaje corriente
   ("nos han accedido sin permiso a la base de datos", "cuánto tiempo tiene una empresa para
   contestar") y el artículo usa el término legal exacto ("violación de seguridad", "plazo de un
   mes"). BM25 no tiene forma de saber que son lo mismo. Es el caso de libro para embeddings
   densos.
2. **Fragmentación a nivel apartado** (e-004): la fuente esperada es `rgpd:art-30.5`, y BM25
   recuperó `rgpd:art-30.1` y `art-30.2` — el mismo artículo, otro apartado. Por el ADR 0001 el
   generador recibe el **artículo entero**, así que esto no es un fallo real del sistema, es un
   defecto de la métrica: contaba acierto solo si el apartado exacto aparecía.

Corregido en el propio harness, no eran dos hallazgos para dos tickets distintos: `evaluar_recall`
ahora acepta `nivel: "apartado" | "articulo"`. A nivel artículo, e-004 cuenta como acierto; e-001
y e-002 siguen sin contar (ni siquiera aparece ningún apartado de `rgpd:art-33` o `rgpd:art-12`
entre los recuperados), así que el hueco léxico es real y no un artefacto de la granularidad.
`rag-lopd retrieval evaluar` ahora imprime los dos niveles.

### Cifra final (29-sep-2026)

| | Recall@10 apartado | Recall@10 artículo |
| --- | --- | --- |
| BM25, con o sin ruta jerárquica (idéntico en las dos) | 37,0 % (10/27) | 48,1 % (13/27) |

La corrección de granularidad rescata exactamente 3 preguntas (e-004, e-006, e-013): el mismo
patrón que el diagnóstico había encontrado a mano. Quedan **14 de 27 preguntas factual/cruzada
donde BM25 no encuentra ni el artículo correcto**, más de la mitad. Ese 48,1 % es el techo real
del léxico puro sobre este corpus, no un número deprimido por un defecto de la métrica — la
métrica ya está arreglada y el número sigue siendo bajo.

**Conclusión: BM25 solo no basta.** Es la referencia correcta y se queda como parte del híbrido,
pero el proyecto necesita recuperación densa para cerrar ese hueco semántico antes de que la
política de abstención o el harness completo tengan un motor de recuperación digno de medirse.
