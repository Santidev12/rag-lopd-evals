# Mapa: RAG evaluado sobre protección de datos española

Label: `wayfinder:map`

## Destination

Un repositorio público de GitHub con: un RAG sobre RGPD + LOPDGDD (y resoluciones de la AEPD en v1),
un eval set de 50 preguntas versionado en el repo, los números de la evaluación medidos y publicados
con su intervalo de confianza, un demo desplegado y accesible por URL, y un README que en la primera
pantalla responde: qué problema resuelve y para quién · qué arquitectura y qué se descartó · los
números · qué falla y cuánto cuesta por consulta.

El mapa termina cuando ese enlace está en el CV y en LinkedIn de Santiago.

## Notes

**Dominio**: recuperación sobre normativa española de protección de datos. El vocabulario del dominio
(norma, artículo, apartado, disposición, resolución, fundamento de derecho, remisión) se fija en
`CONTEXT.md` según se vaya usando.

**Este mapa lleva la ejecución dentro.** Sobrescribe el "plan, don't do" por defecto de wayfinder:
Santiago quiere programar, no recibir un plan. Los tickets de tipo `task` producen código real,
no decisiones sobre código.

**Cómo se trabaja aquí**:
- Se programa en pareja: nada de lecciones, deberes ni material de curso. El porqué de cada decisión
  se explica sobre el código en el momento de escribirlo.
- Python. Su nivel: lee bien y ha hecho scripts, pero duda con idioms, tipado, entornos y estructura
  de proyecto — hay que explicar esas convenciones al vuelo, sin condescendencia y sin pararse.
- Presupuesto de infraestructura: hasta 10 €/mes.
- Todo en español; los términos técnicos en inglés cuando ese es el término real del campo.

**Skills a consultar**: `/tdd` para el harness de evaluación, `/prototype` para las decisiones de
"cómo debería comportarse", `/research` para hechos externos, `/domain-modeling` para `CONTEXT.md`
y los ADR, `/codebase-design` al fijar los límites de los módulos.

**Referencias del proyecto**: `../../../RESOURCES.md` (fuentes verificadas el 3-sep-2026) y
`../../../reference/` (chuletas de métricas y de anatomía del eval set).

## Decisions so far

<!-- una línea por ticket cerrado -->

- [Estructura real de la API del BOE](issues/02-api-boe-estructura-real.md) — vía limpia y sin
  restricciones, pero los ids de bloque no son derivables del número de artículo (art. 10 = `a1-2`):
  hay que resolverlos siempre por el índice. Los apartados solo salen con regex; las versiones
  históricas vienen todas en el mismo bloque.
- [Formato parseable del RGPD en EUR-Lex](issues/03-eurlex-rgpd-formato-parseable.md) — `eur-lex.europa.eu`
  bloquea a los clientes que no son navegador (AWS WAF); se descarga por Cellar en Formex XML, que trae
  artículos, apartados y jerarquía como árbol real. Los 173 considerandos solo están en el acto original.
- [Embeddings en español y viabilidad en HF Spaces gratis](issues/04-embeddings-es-y-viabilidad-hf-spaces.md) —
  indexar en local con BGE-M3 y llamar al mismo checkpoint por API para la consulta; `voyage-law-2`
  descartado por falta de evidencia en español. La latencia en CPU no está verificada en ninguna fuente:
  se mide en un ticket propio.

- [Esqueleto del repo y tooling de Python](issues/01-esqueleto-del-repo.md) — uv + layout `src/` +
  pydantic-settings + typer + ruff + mypy + CI; tests en verde y primer commit en `main`.

- [Latencia real de embeddings y reranking en CPU](issues/09-latencia-real-en-cpu.md) — BGE-M3 se
  auto-aloja en el Space (159 ms p50); la API es 4 veces más lenta solo de red. Reranking detrás de un
  flag sobre el top-10 (~413 ms), lo decide el eval set.

- [Modelo de documento e identificadores estables](issues/05-modelo-de-documento-e-identificadores.md) —
  small-to-big (indexar apartado, entregar artículo), identificador semántico propio con ELI como
  metadato, fallback medido cuando la regex no parte un artículo. Ver ADR 0001.

- [Ingesta a formato interno](issues/06-ingesta-a-formato-interno.md) — `rag-lopd ingest` trae
  RGPD (99 preceptos, 389 unidades, 95,6 % partidas) y LOPDGDD (144, 339, 82,9 %) con caché y
  manifiesto de procedencia. Las versiones históricas se conservan; umbral que falla si la regex
  del BOE se rompe.

- [Estrategia de chunking sobre artículos](issues/07-estrategia-de-chunking.md) — cerrado sin
  trabajar: absorbido por el ADR 0001. Su residuo (¿ayuda la ruta jerárquica?) pasa a medirse en
  la fase de retrieval.

- [Eval set v1: las 50 preguntas](issues/08-eval-set-v1.md) — 50 candidatas con el reparto
  objetivo y las 24 fuentes verificadas contra el corpus; reglas en el modelo y anclas de texto
  como defensa contra respuestas inventadas. Santiago las revisó y aceptó las 50: cero descartes.

- [Baseline de retrieval: BM25 y la ruta jerárquica](issues/10-baseline-bm25-y-ruta-jerarquica.md) —
  el contrato `Recuperador` común a cualquier motor, BM25 como referencia, y `evaluar_recall` con
  dos niveles (apartado/artículo, este último nacido de un fallo real diagnosticado a mano).
  Cifra final: 48,1 % recall@10 a nivel artículo, la ruta jerárquica no cambia nada. Conclusión:
  BM25 solo no basta — hace falta denso.

- [Recuperación densa vía DeepInfra](issues/11-recuperacion-densa-deepinfra.md) — `RecuperadorDenso`
  (coseno sobre un índice de embeddings) y `rag-lopd retrieval indexar` para construirlo.
  Desviación deliberada del ticket 04: se indexa también por la API de DeepInfra (céntimos, una
  vez) en vez de con BGE-M3 en local, para no meter torch como dependencia todavía. Cifra final:
  **88,9 % recall@10 a nivel artículo** (frente al 48,1 % de BM25), sin ruta jerárquica. Las 3
  preguntas que quedan (e-021, e-024, e-026) comparten una causa estructural: piden un artículo
  transversal y genérico (plazos, bases de licitud, sanciones) sin vocabulario propio — ni BM25
  ni denso pueden engancharlo. Santiago decide no perseguir el híbrido: 88,9 % queda como la
  cifra de v0, y el proyecto pasa a abstención y generación.

## Not yet specified

- **Harness de evaluación.** El juez de contenido está construido, calibrado y aplicado a v1 y v2
  ([ticket 14](issues/14-el-juez.md), cerrado el 16-oct-2026). Exactitud v2 27/34 = 79,4 % (63 %–90 %)
  y v1 26/34 = 76,5 %: dentro del ruido; v2 sí arregla las dos temporales. El juez coincide en 31/32
  (kappa 0,84) con las etiquetas, de las que solo las 7 dudosas son de una persona. Sesgo conocido:
  e-019 (penaliza lo que la referencia añade a la pregunta). e-047 se corrigió en el eval set (era una
  referencia errónea). Lo débil son las cruzadas (6/12). Pendiente: unir todo en un informe
  reproducible (recall@5/@20, generación, juez, latencia) y, si se quiere, un segundo modelo.
- **Política de abstención y generación** ([ticket 12](issues/12-politica-de-abstencion.md) medido,
  [ticket 13](issues/13-generacion-con-cita-y-abstencion.md) medido con prompt v1 y v2). El score de
  recuperación no separa (AUC 0,83), así que la política mira el contenido. Gemini 3.5 Flash-Lite,
  prompt v2 (por defecto): sobre-respuesta 6,2 % (1/16; era 2/17 antes de corregir e-047, que era una
  etiqueta errónea) y abstención indebida 8,8 % (3/34). v1 daba 14,7 % (5/34): las dos abstenciones de más eran temporales por un hueco del contexto (índice solo
  vigente, vigencia sin entregar) y v2 las arregla sin cambiar el estado de ninguna otra pregunta.
  Quedan 3 abstenciones: 2 correctas por retrieval (e-021, e-024) y 1 fallo real de generación
  (e-027). Abierto: un segundo modelo.
- **Instrumentación de coste y latencia.** El coste ya sale de la ejecución: ≈ 0,0020 $ por
  consulta con Gemini 3.5 Flash-Lite y prompt v2 (tokens reales × tarifa). Latencia de extremo a extremo medida el 21-oct-2026: p50 21,2 s · p95 41,8 s (50 consultas, una pasada). Es alta y sin desglosar: falta saber cuánto es embeber, buscar y generar.
- **Forma del demo.** Qué ve un reclutador en los primeros diez segundos. Chat, informe de evaluación,
  o las dos cosas.
- **Despliegue.** HF Spaces + Qdrant es la apuesta, pero falta confirmar el flujo de indexación y los
  secretos.
- **Ampliación a v1**: resoluciones de la AEPD y directrices del EDPB, con el muestreo acotado que
  exige su robots.txt.

## Out of scope

- **Híbrido (RRF) y reranker.** Descartados para v0 (ticket 11, 01-oct-2026): denso solo + 88,9 %
  recall@10 a nivel artículo; las 3 preguntas que quedan fallan por una causa estructural
  (artículos transversales sin vocabulario propio) que ni el RRF ni un reranker atacan. Si en v1
  (con AEPD) el corpus crece y el retrieval se degrada, revisar esta decisión con números nuevos.
- **Navegación por referencias cruzadas explícitas** (seguir "sin perjuicio del artículo N" dentro
  del texto recuperado). Es lo único que de verdad atacaría las 3 preguntas que quedan, pero es
  una pieza nueva (detección de referencias + expansión de contexto), no una variante de lo que ya
  existe. Candidata a v1 si la política de abstención o la generación lo piden.
- Fine-tuning, LoRA o cualquier entrenamiento de modelos. Esto es AI Engineering, no ML Engineering.
- Agentes multi-paso. Un RAG bien medido señala más que un agente sin medir.
- LangChain / LlamaIndex en la v0: esconden justo lo que hay que aprender a medir.
- Convenios colectivos, AI Act, LSSI y jurisprudencia en el corpus. Fijan la frontera que hace
  posibles las preguntas `fuera_de_corpus`.
- Integrar esto en Complai. Si acaba encajando, será otro esfuerzo.
- Autenticación, multiusuario o persistencia de conversaciones en el demo.
