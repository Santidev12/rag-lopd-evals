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
| Embeddings | — | — |
| Recuperación | — | — |
| Generación | — | — |

Las decisiones con su evidencia están en [`docs/research/`](docs/research/).

### 3. Cómo sé que funciona

| Métrica | Valor |
| --- | --- |
| Recall@5 / Recall@20 | — |
| Exactitud de respuesta (preguntas respondibles, IC 95 %) | — |
| Cita el artículo correcto | — |
| **Tasa de sobre-respuesta** (responde sin tener la respuesta) | — |
| **Tasa de abstención indebida** (calla teniendo la respuesta) | — |

El eval set (50 preguntas con respuesta correcta y fuente esperada) está versionado en
[`eval/`](eval/). Incluye preguntas sin respuesta en el corpus y preguntas trampa: sin ellas,
la evaluación no mide el fallo que más importa. Reparto: 15 factual · 12 cruzada · 6 temporal ·
10 fuera de corpus · 7 trampa.

Cómo se construyó, y cómo se defiende de que un LLM se invente las respuestas, en
[`docs/eval-set.md`](docs/eval-set.md). **Estado actual: las 50 preguntas están revisadas y
aceptadas.** Los números siguen sin ser publicables hasta que exista un harness de recuperación +
generación que las conteste de verdad.

```bash
uv run rag-lopd eval validar   # reglas del eval set + todas las fuentes existen en el corpus
uv run rag-lopd eval stats     # reparto por tipo y avance de la revisión
uv run rag-lopd eval tabla     # exporta docs/eval-candidatas.md para revisar
```

### 4. Qué le falla y cuánto cuesta

| | |
| --- | --- |
| Coste medio por consulta | — € |
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

Hay un primer motor de recuperación, BM25, con el contrato (`Recuperador`) que usará también el
denso y el híbrido más adelante:

```bash
uv run rag-lopd retrieval evaluar     # recall@k con y sin ruta jerárquica delante del texto
uv run rag-lopd retrieval buscar "..." # prueba una consulta a mano
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
