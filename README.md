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
| Corpus v0 | RGPD + LOPDGDD | Resoluciones de la AEPD: su `robots.txt` prohíbe la descarga masiva, entran en v1 con muestreo acotado |
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
la evaluación no mide el fallo que más importa.

### 4. Qué le falla y cuánto cuesta

| | |
| --- | --- |
| Coste medio por consulta | — € |
| Latencia p50 / p95 | — |
| Modos de fallo conocidos | — |

---

## Reproducirlo

```bash
uv sync                 # crea el entorno e instala todo
cp .env.example .env    # y rellena las claves que vayas a usar
uv run rag-lopd info    # comprueba que la configuración se lee bien
```

Desarrollo:

```bash
uv run pytest                  # tests
uv run ruff check . --fix      # lint
uv run ruff format .           # formato
uv run mypy                    # tipos
```

## Licencia

Código bajo [MIT](LICENSE). El RGPD proviene de EUR-Lex (CC BY 4.0, Decisión 2011/833/UE) y es un
instrumento de documentación sin efecto jurídico; la LOPDGDD proviene del BOE. Origen de los datos
citado en cada documento del corpus.
