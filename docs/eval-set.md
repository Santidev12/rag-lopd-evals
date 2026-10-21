# Cómo se construyó el eval set

El eval set es el proyecto. Este documento explica cómo se hizo, para que cualquiera pueda juzgar
si los números que publica el README significan algo.

## El método: híbrido y documentado

Las 50 preguntas **no** se escribieron a mano una por una, ni se generaron y se dieron por buenas.
El proceso tiene tres pasos y el segundo es innegociable:

1. **Generación de candidatas.** Un LLM (Claude Opus) lee el corpus normalizado —el mismo
   `data/processed/*.json` que produce `rag-lopd ingest`, no el texto original— y propone preguntas
   con su respuesta esperada y su fuente.
2. **Revisión humana de todas.** Cada candidata se acepta o se descarta a mano. Las descartadas se
   conservan en el fichero con su motivo: por qué una pregunta no sirve dice tanto del sistema como
   las que sí sirven.
3. **Validación automática**, en cada ejecución de los tests.

Los tipos que **no se pueden generar desde dentro del corpus** —`fuera_de_corpus` y `trampa`— se
escriben aparte: por definición preguntan por algo que el corpus no contiene, así que leerlo no
ayuda a inventarlas. Salen de conocer el dominio y la frontera que se fijó en el corpus v0.

## El reparto, y por qué ese

El objetivo de diseño era 15 factuales y 7 trampas. Quedó en 16 y 6 al corregir e-047 (ver
«Correcciones», más abajo), y el objetivo del código se actualizó a ese reparto.

| Tipo | Nº | Razón |
| --- | --- | --- |
| `factual` | 16 | El suelo. Si falla, el retrieval o el chunking están rotos, sin misterio. |
| `cruzada` | 12 | Exige reunir dos artículos. Es donde casi todos los RAG se rompen. |
| `temporal` | 6 | Distinguir versiones de una norma. Justifica haber elegido un corpus normativo. |
| `fuera_de_corpus` | 10 | Un 20 % del set. Con menos, la tasa de sobre-respuesta se calcula sobre tan pocos casos que no dice nada. |
| `trampa` | 6 | Preguntas que *parecen* respondibles. Demuestran que se pensó como adversario, no como demostrador. |

## Las reglas, y el fallo que evita cada una

Están en `src/rag_lopd/eval/modelo.py` y se comprueban al construir cada pregunta:

- **Nada de sí o no.** Un sistema roto acierta la mitad de esas por azar.
- **Mínimo 30 caracteres.** Una pregunta vaga no distingue un sistema bueno de uno malo.
- **Una pregunta sin respuesta en el corpus no puede tener fuente esperada.** Si la tiene, la
  respuesta sí está, y el tipo está mal puesto.
- **Una pregunta respondible necesita fuente.** Sin ella no se puede medir el retrieval por
  separado de la generación, que es el diagnóstico más útil que da este proyecto.
- **Una `cruzada` necesita dos artículos distintos.** Dos apartados del mismo artículo no cruzan
  nada: el 83.4 y el 83.5 se recuperan juntos sin esfuerzo.
- **Ids únicos** en el conjunto.

## Las dos validaciones contra el corpus real

1. **Toda fuente declarada existe.** Una fuente inventada o mal tecleada haría que el recall de esa
   pregunta fuese 0 para siempre, y el sistema parecería peor de lo que es sin que nadie supiera
   por qué. `rag-lopd eval validar` lo comprueba, y hay un test que lo repite.
2. **Anclas de texto.** Para 15 de las preguntas, un test comprueba que un término literal de la
   respuesta esperada (`"72 horas"`, `"catorce años"`, `"dieciocho meses"`, `"(Anulado)"`) aparece
   de verdad en el texto de la fuente citada. Es la defensa contra el fallo más peligroso de generar
   preguntas con un LLM: **que la respuesta suene impecable y el artículo citado no diga eso.**

## De dónde salen las preguntas `temporal`

De diferencias reales entre versiones del texto consolidado, no inventadas:

- Las actuaciones previas de investigación de la AEPD pasaron de **doce a dieciocho meses** en mayo
  de 2023 (`lopdgdd:art-67.2`).
- La previsión que amparaba a los partidos políticos para recopilar opiniones políticas fue
  **anulada**: desde junio de 2019 el texto vigente es literalmente «(Anulado)» (`lopdgdd:df-3.1`).
- El artículo 66.1 remitía al **64.3** y hoy remite al **64.4** (`lopdgdd:art-66.1`). Un cambio de
  una sola cifra: si el sistema recupera la versión vieja, la respuesta es incorrecta y suena
  perfectamente convincente.

Estas existen porque la ingesta **conserva las versiones históricas** con `vigente_desde` y
`vigente_hasta`, aunque solo se indexen las vigentes.

## Comandos

```bash
uv run rag-lopd eval validar   # reglas + todas las fuentes existen en el corpus
uv run rag-lopd eval stats     # reparto por tipo y avance de la revisión
uv run rag-lopd eval tabla     # exporta docs/eval-candidatas.md para revisar cómodamente
```

## Correcciones tras la revisión

Un eval set revisado también se equivoca, y las correcciones se anotan aquí con su motivo en vez
de hacerlas en silencio.

- **e-047, 16-oct-2026: de `trampa` a `factual`.** La pregunta (¿qué tasa debe abonar un ciudadano
  para reclamar ante la AEPD?) esperaba abstención, pero el RGPD, art. 57.3, dice que el
  desempeño de las funciones de la autoridad de control es gratuito para el interesado. El sistema
  contestaba bien y la referencia era la errónea. La detectó el juez de contenido (ticket 14), al
  marcar como incorrecta una respuesta que la norma sostiene. Referencia nueva: «Ninguna: es
  gratuito» (`rgpd:art-57.3`); el art. 57.4 permite una tasa razonable solo para solicitudes
  manifiestamente infundadas o excesivas, y no se exige mencionarlo. Efecto en las cifras: la
  sobre-respuesta pasa de 2/17 a 1/16. Es una corrección de una etiqueta, no una mejora del
  sistema, y por eso el README lo dice.

Lo que esta corrección no cubre: las trampas y fuera-de-corpus que el sistema calló no las ve el
juez (no hay respuesta que juzgar), así que una referencia mal puesta del mismo estilo pasaría
desapercibida. Es un riesgo conocido de las 15 preguntas sin respuesta donde el sistema se abstuvo.

## Estado

`eval/candidatas-v0.jsonl` — 50 preguntas, todas en estado `aceptada` (revisadas una a una),
25 fuentes distintas, todas verificadas contra el corpus.
