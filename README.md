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
| Recuperación | Denso (BGE-M3), 89,3 % recall@10 a nivel artículo | BM25 solo: se queda en 48,1 %, no cierra el hueco entre lenguaje corriente y término legal |
| Generación | Gemini 3.5 Flash-Lite (prompt v2), salida JSON con vía `sin_respuesta` y cita validada contra el contexto entregado | Abstenerse por umbral de score: la similitud no separa lo respondible de lo no respondible (AUC 0,83) |

Las decisiones con su evidencia están en [`docs/research/`](docs/research/).

### 3. Cómo sé que funciona

| Métrica | Valor |
| --- | --- |
| Recall@5 / @10 / @20 del artículo correcto (denso, 28 preguntas) | 78,6 % (22/28) / 89,3 % (25/28) / 92,9 % (26/28) |
| Exactitud de respuesta (preguntas respondibles, IC 95 %) | 79,4 % (27/34, IC 95 %: 63 %–90 %); 87,1 % de las que contesta (27/31) |
| Cita cubre el artículo fuente | 87,1 % (27/31, IC 95 %: 71 %–95 %) |
| **Tasa de sobre-respuesta** (responde sin tener la respuesta) | 6,2 % (1/16, IC 95 %: 1 %–28 %) |
| **Tasa de abstención indebida** (calla teniendo la respuesta) | 8,8 % (3/34, IC 95 %: 3 %–23 %) |

El eval set (50 preguntas con respuesta correcta y fuente esperada) está versionado en
[`eval/`](eval/). Incluye preguntas sin respuesta en el corpus y preguntas trampa: sin ellas,
la evaluación no mide el fallo que más importa. Reparto: 16 factual · 12 cruzada · 6 temporal ·
10 fuera de corpus · 6 trampa.

Cómo se construyó, y cómo se defiende de que un LLM se invente las respuestas, en
[`docs/eval-set.md`](docs/eval-set.md). **Estado actual: las 50 preguntas están revisadas y
aceptadas.** Los números de generación son de una sola pasada (un modelo, prompt v2).

**Una pregunta se corrigió a posteriori.** e-047 (¿qué tasa debe abonar un ciudadano para reclamar
ante la AEPD?) estaba etiquetada como trampa ("el corpus no prevé ninguna tasa"), pero el RGPD,
art. 57.3, dice que es gratuito: el sistema contestaba bien y la referencia era la equivocada. Se
descubrió porque el juez la marcó como discrepancia, y se reconvirtió en pregunta factual el
16-oct-2026. Con la corrección la sobre-respuesta baja de 2/17 a 1/16, y eso **no es una mejora
del sistema**: es una etiqueta mal puesta que dejó de contar en su contra. La que queda (e-046,
"¿qué formato concreto debe tener el registro?") cita el art. 30 sin inventar ningún formato, y una
revisión manual la da por correcta.

La exactitud la mide un juez automático (DeepSeek-V4-Flash, otra familia que el generador, contra
la respuesta de referencia). Antes de fiarse se comparó con una revisión manual de las 32 respuestas
contestadas: coincide en 31 (kappa 0,84). Salvedades: esa revisión la hizo una IA salvo las 7
respuestas dudosas, que cerró una persona, y el kappa se apoya en solo 3 respuestas no correctas, así
que es una estimación inestable. El juez tiene un sesgo conocido: trata como esencial todo lo que
añade la referencia aunque la pregunta no lo pida (caso e-019), por lo que es algo más estricto que
un revisor humano.

Con el prompt v1 la abstención indebida era del 14,7 % (5/34) y la exactitud del 76,5 % (26/34). La
diferencia en abstención son dos preguntas temporales, para las que se diseñó v2; la de exactitud es
de una sola respuesta, dentro del ruido. No es una mejora que se pueda extrapolar.

```bash
uv run rag-lopd eval validar   # reglas del eval set + todas las fuentes existen en el corpus
uv run rag-lopd eval stats     # reparto por tipo y avance de la revisión
uv run rag-lopd eval tabla     # exporta docs/eval-candidatas.md para revisar
```

### 4. Qué le falla y cuánto cuesta

| | |
| --- | --- |
| Coste medio por consulta | ≈ 0,0020 $ (Gemini 3.5 Flash-Lite, ~5.600 tokens de entrada) |
| Latencia p50 / p95 (extremo a extremo) | 21,2 s / 41,8 s (50 consultas, una sola pasada, con Gemini 3.5 Flash-Lite; incluye embeber la consulta, buscar, generar y los reintentos) |
| Modos de fallo conocidos | Las preguntas cruzadas son lo débil: 6/12 correctas. Tres se callan (en dos el artículo transversal que hace falta no llega a recuperarse; la tercera es un fallo de generación) y tres salen parciales (una por recuperación, una por no aplicar la regla al caso concreto y una, discutible, por omitir un dato que la referencia incluye y la pregunta no pide). Además, una factual (e-010) cita el art. 19 del RGPD habiendo recibido el artículo correcto de la LOPDGDD. |

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
hueco: **89,3 % de recall@10** a nivel artículo (25/28; era 88,9 % sobre 27 antes de que e-047 pasara a
factual: es el mismo sistema con una pregunta más, que acierta), igual con o sin ruta jerárquica
delante del texto (tampoco ayuda aquí — segunda vez que se mide y segunda vez que no aporta).
Con el top-5 baja a 78,6 % y con el top-20 sube a 92,9 %. Quedan 3 de 28 preguntas sin el
artículo correcto en el top-10 (e-021, e-024, e-026), y dos de ellas siguen fuera en el top-20:

```bash
uv run rag-lopd retrieval indexar               # construye el índice denso (una vez, de pago)
uv run rag-lopd retrieval evaluar --motor bm25   # o --motor denso
uv run rag-lopd retrieval evaluar --motor denso --k 5 --k 10 --k 20 --guardar data/recall.json   # recall@5/@10/@20 de una vez
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
uv run rag-lopd generacion evaluar           # las 50 preguntas; llama a Gemini (céntimos); mide la latencia p50/p95
uv run rag-lopd generacion evaluar --prompt v1   # reproduce la primera pasada
uv run rag-lopd generacion juzgar data/runs/<pasada>.jsonl   # juez (DeepSeek en DeepInfra): ¿es correcto el contenido?
uv run rag-lopd informe data/runs/<pasada>.jsonl --juicios data/runs/<pasada>.juez-<...>.jsonl --recall data/recall.json   # el demo: un HTML estático en docs/informe.html
uv run rag-lopd generacion calibrar <juicios>.jsonl eval/etiquetas-v2-preliminares.jsonl eval/etiquetas-v2-santiago.jsonl
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
