# rag-lopd-evals

**RAG sobre normativa española de protección de datos, con un set de evaluación de 50 preguntas.**

> 🚧 En construcción. Las cifras marcadas como `—` se rellenan cuando el harness de evaluación las
> produzca. Este README no publica ningún número que no venga de una ejecución real.

---

### 1. Qué problema resuelve y para quién

Responder preguntas concretas sobre el RGPD y la LOPDGDD citando el artículo exacto, y **callarse
cuando la respuesta no está en el corpus**. Pensado para quien tiene que aplicar la norma sin ser
abogado: responsables de pymes, gestorías y equipos de producto.

La parte difícil no es responder. Es saber cuándo no se puede.

### 2. Arquitectura, y qué se descartó

| Decisión | Elegido | Descartado, y por qué |
| --- | --- | --- |
| Fuente del RGPD | Formex XML vía Cellar | `eur-lex.europa.eu` responde con un reto JS de AWS WAF a cualquier cliente que no sea un navegador |
| Fuente de la LOPDGDD | API de legislación consolidada del BOE | Scrapear el HTML: la API da bloques y versiones ya estructurados |
| Corpus v0 | RGPD + LOPDGDD, 728 unidades indexables | Resoluciones de la AEPD: su `robots.txt` prohíbe la descarga masiva, entran en v1 con muestreo acotado |
| Unidad indexable | El apartado; al generador se le entrega el artículo entero (*small-to-big*) | El artículo como chunk: el art. 83 del RGPD son ~1.400 tokens y diez ideas, su vector sería una media borrosa. Ver [ADR 0001](docs/adr/0001-small-to-big-e-identificadores-semanticos.md) |
| Identificadores | Semánticos propios (`rgpd:art-33.1`), con el ELI oficial como metadato | Índices de chunk: se rompen al cambiar el troceo y se llevan por delante el eval set |
| Framework | Ninguno | LangChain / LlamaIndex esconden justo lo que hay que medir |
| Embeddings | BGE-M3 vía DeepInfra | `voyage-law-2`: sin evidencia de soporte en español |
| Recuperación | Denso (BGE-M3), 88,9 % recall@10 a nivel artículo | BM25 solo: se queda en 48,1 %, no cierra el hueco entre lenguaje corriente y término legal |
| Generación | Gemini 3.5 Flash-Lite (prompt v2), salida JSON con vía `sin_respuesta` y cita validada contra el contexto entregado | Abstenerse por umbral de score: la similitud no separa lo respondible de lo no respondible (AUC 0,83) |

Las decisiones con su evidencia están en [`docs/research/`](docs/research/).

### 3. Cómo sé que funciona

| Métrica | Valor |
| --- | --- |
| Recall@5 / Recall@20 | — |
| Exactitud de respuesta (preguntas respondibles, IC 95 %) | — |
| Cita cubre el artículo fuente | 86,7 % (26/30, IC 95 %: 70 %–95 %) |
| **Tasa de sobre-respuesta** (responde sin tener la respuesta) | 11,8 % (2/17, IC 95 %: 3 %–34 %) |
| **Tasa de abstención indebida** (calla teniendo la respuesta) | 9,1 % (3/33, IC 95 %: 3 %–24 %) |

El eval set (50 preguntas con respuesta correcta y fuente esperada) está versionado en
[`eval/`](eval/). Incluye preguntas sin respuesta en el corpus y preguntas trampa: sin ellas,
la evaluación no mide el fallo que más importa. Reparto: 15 factual · 12 cruzada · 6 temporal ·
10 fuera de corpus · 7 trampa.

Cómo se construyó, y cómo se defiende de que un LLM se invente las respuestas, en
[`docs/eval-set.md`](docs/eval-set.md). **Estado actual: las 50 preguntas están revisadas y
aceptadas.** Los números de generación son de una sola pasada (un modelo, prompt v2) y miden comportamiento
(contestar / callar / citar), no si el contenido es correcto: eso necesita el harness con juez.
Con el prompt v1 la abstención indebida era del 15,2 % (5/33): las dos de diferencia son preguntas
temporales, para las que se diseñó v2 (ver el ticket del proyecto), así que no es una mejora que
se pueda extrapolar.

```bash
uv run rag-lopd eval validar   # reglas del eval set + todas las fuentes existen en el corpus
uv run rag-lopd eval stats     # reparto por tipo y avance de la revisión
uv run rag-lopd eval tabla     # exporta docs/eval-candidatas.md para revisar
```

### 4. Qué le falla y cuánto cuesta

| | |
| --- | --- |
| Coste medio por consulta | ≈ 0,0020 $ (Gemini 3.5 Flash-Lite, ~5.600 tokens de entrada) |
| Latencia p50 / p95 | — |
| Modos de fallo conocidos | — |

---

## Reproducirlo

```bash
uv sync                    # crea el entorno e instala todo
cp .env.example .env       # y rellena las claves que vayas a usar
uv run rag-lopd info       # comprueba que la configuración se lee bien
uv run rag-lopd ingest     # descarga y normaliza RGPD + LOPDGDD
```

La ingesta deja el corpus en `data/processed/` y anota en `data/raw/manifest.json` de dónde salió
cada fichero, cuándo y con qué sha256. Salida actual:

| Norma | Preceptos | Unidades | Partidas en apartados |
| --- | --- | --- | --- |
| RGPD (Formex, Cellar) | 99 | 389 | 95,6 % |
| LOPDGDD (API del BOE) | 144 | 339 | 82,9 % |

La diferencia no es un defecto del parser: el Formex europeo marca los apartados con etiquetas,
mientras que el BOE los deja como texto plano dentro de un `<p>` y hay que sacarlos con una regex.
58 de los 144 preceptos de la LOPDGDD no tienen apartados numerados en absoluto. Las unidades que
no se pudieron partir quedan marcadas con `granularidad: articulo`, y el eval set dirá si se
recuperan peor. Si esa proporción baja del 75 %, la ingesta falla en vez de seguir en silencio.

Hay dos motores de recuperación detrás del mismo contrato (`Recuperador`): BM25 (léxico) y denso
(BGE-M3 vía DeepInfra, `rag-lopd retrieval indexar` construye el índice una vez y cuesta
céntimos). BM25 solo llega al 48,1 % de recall@10 a nivel artículo — se queda corto justo en las
preguntas que usan lenguaje corriente en vez del término legal exacto. Denso cierra casi todo ese
hueco: **88,9 % de recall@10** a nivel artículo, con o sin ruta jerárquica delante del texto
(tampoco ayuda aquí — segunda vez que se mide y segunda vez que no aporta). Quedan 3 de 27
preguntas sin el artículo correcto en el top-10, pendientes de diagnóstico:

```bash
uv run rag-lopd retrieval indexar               # construye el índice denso (una vez, de pago)
uv run rag-lopd retrieval evaluar --motor bm25   # o --motor denso
uv run rag-lopd retrieval buscar "..." --motor denso
```

La generación recibe los artículos recuperados (el artículo entero, no el apartado) y devuelve
una respuesta con cita o se abstiene. Que el score de recuperación no basta para decidir cuándo
callarse está medido (AUC 0,83: callar al 88 % de lo que no tiene respuesta silencia al 36 % de lo
que sí la tiene), así que la política mira el contenido: el modelo puede declarar `sin_respuesta`,
y toda respuesta debe citar artículos que de verdad estaban en el contexto o cuenta como
abstención. `generacion evaluar` mide sobre-respuesta y abstención indebida y guarda cada
observación para recalcular sin volver a pagar:

```bash
uv run rag-lopd generacion preguntar "..."   # recupera, genera y enseña cita y coste
uv run rag-lopd generacion evaluar           # las 50 preguntas; llama a Gemini (céntimos)
uv run rag-lopd generacion evaluar --prompt v1   # reproduce la primera pasada
uv run rag-lopd generacion resumir data/runs/<pasada>.jsonl
```

Desarrollo:

```bash
uv run pytest                  # tests (sin red)
uv run pytest -m red           # tests que sí salen a internet, contra las fuentes reales
uv run ruff check . --fix      # lint
uv run ruff format .           # formato
uv run mypy                    # tipos
```

## Licencia

Código bajo [MIT](LICENSE). El RGPD proviene de EUR-Lex (CC BY 4.0, Decisión 2011/833/UE) y es un
instrumento de documentación sin efecto jurídico; la LOPDGDD proviene del BOE. Origen de los datos
citado en cada documento del corpus.
