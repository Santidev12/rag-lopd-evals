# Recuperación densa vía DeepInfra

Type: task
Status: resolved

## Question

El ticket 10 dejó una cifra real: BM25 no encuentra ni el artículo correcto en 14 de 27
preguntas factual/cruzada (48,1 % recall@10 a nivel artículo). Hace falta un segundo motor que
capture el hueco semántico que BM25 no puede: preguntas en lenguaje corriente contra artículos
en lenguaje legal, sin solapamiento de términos.

Alcance de este ticket:

- Un `Embebedor` que hable con DeepInfra (BGE-M3, decidido en el ticket 04) y un
  `RecuperadorDenso` que cumpla el contrato `Recuperador` ya existente, para que
  `evaluar_recall` lo mida sin cambios.
- Persistencia del índice (vectores + ids) en disco: construirlo es un paso aparte, lento y de
  pago, no algo que se repita en cada consulta.
- `rag-lopd retrieval indexar` para construirlo, y `--motor denso` en `evaluar`/`buscar`.

**Desviación deliberada del ticket 04**: aquel dejó decidido indexar en local con BGE-M3 (gratis)
y usar la API de DeepInfra solo para la consulta. Este ticket indexa también por la API. Motivo:
728 unidades a los precios de DeepInfra (0,01 $/millón de tokens) cuestan unos pocos céntimos
**una sola vez**, y evita meter `sentence-transformers` + `torch` (varios GB) como dependencia
solo para un paso que se corre una vez. Si el corpus crece mucho (AEPD en v1) o el coste deja de
ser trivial, mover el indexado a local es un cambio dentro de `embeddings.py` — nada fuera de
ese fichero sabe de dónde salen los vectores.

## Answer

**Resuelto el 29-sep-2026.**

Entregado:

- `rag_lopd.retrieval.embeddings.EmbebedorDeepInfra` — llama al endpoint compatible con OpenAI
  de DeepInfra (`https://api.deepinfra.com/v1/openai/embeddings`, modelo `BAAI/bge-m3`),
  troceando en lotes de 32 y reordenando por el `index` de la respuesta (la API no promete
  devolver `data` en el mismo orden que `input`).
- `rag_lopd.retrieval.indice_denso` — `construir` (embebe y normaliza a norma 1),
  `guardar`/`cargar` en `.npz`. `cargar` falla fuerte si el índice guardado tiene una unidad que
  ya no existe en el corpus actual, en vez de servir un resultado desalineado en silencio.
- `rag_lopd.retrieval.denso.RecuperadorDenso` — similitud coseno como producto punto (los
  vectores ya vienen normalizados), mismo contrato `Recuperador` que BM25.
- `rag-lopd retrieval indexar [--con-ruta/--sin-ruta]` construye y guarda el índice.
  `retrieval evaluar --motor denso` y `retrieval buscar --motor denso` lo usan. Se puede
  construir e indexar con y sin ruta jerárquica por separado — la pregunta del ticket 07 se
  vuelve a medir aquí, esta vez con un motor que sí podría captar la ruta como señal semántica
  aunque no haya coincidencia literal de palabras.
- 12 tests nuevos (`test_embeddings.py`, `test_denso.py`), todos contra dobles de prueba
  (respx para la llamada HTTP, un `Embebedor` falso para la lógica de coseno): nada sale a
  internet ni gasta un céntimo al correr la suite normal. Ruff y mypy limpios; se añadió `numpy`
  como dependencia explícita (antes solo llegaba transitivamente vía `rank-bm25`).

**Pendiente y con coste real, no automatizado desde aquí**: construir el índice de verdad
(`rag-lopd retrieval indexar` con y sin ruta) y correr `retrieval evaluar --motor denso` contra
el corpus ingerido, para tener la cifra real de recall denso y compararla con el 48,1 % de BM25.
Con las dos cifras delante se decide si el híbrido (RRF) aporta algo o si denso solo ya alcanza.

## Números reales (30-sep-2026)

Corridos contra el corpus ingerido de verdad (728 unidades, `BAAI/bge-m3` vía DeepInfra):

| Variante | Recall@10 apartado | Recall@10 artículo |
| --- | --- | --- |
| Con ruta jerárquica | 81,5 % (22/27) | 88,9 % (24/27) |
| Sin ruta jerárquica | 85,2 % (23/27) | 88,9 % (24/27) |

Salto enorme sobre BM25 (48,1 % → 88,9 % a nivel artículo): confirma el diagnóstico del ticket
10 — el hueco era semántico (lenguaje corriente vs. término legal), y es justo lo que un modelo
de embeddings está hecho para cerrar.

**La ruta jerárquica tampoco ayuda claramente aquí**: mismo recall a nivel artículo con o sin
ella, y sin ruta incluso saca una pregunta más a nivel apartado (23 vs 22). Segunda vez que se
mide y segunda vez que no aporta — con BM25 la explicación era léxica (los tokens de la ruta
nunca casan con la consulta); aquí la explicación más probable es que BGE-M3 ya captura el
contexto semántico del apartado por sí solo, y anteponer "RGPD · Capítulo IV · Artículo 33"
añade vocabulario administrativo que no aparece en ninguna consulta real, diluyendo un poco la
señal en vez de reforzarla. Se deja `sin-ruta` como variante por defecto para lo que siga
construyéndose sobre denso: no pierde nada y es más barata de indexar (menos tokens).

Solo quedan 3 de 27 preguntas sin el artículo correcto en el top-10: **e-021, e-024** (fallan en
las dos variantes) y **e-025** (con ruta) / **e-026** (sin ruta). Sin diagnosticarlas a mano
todavía no se sabe si son otro hueco semántico real o algo más simple (p. ej. una pregunta
`cruzada` donde falta una sola fuente de varias).

**Conclusión provisional**: con un solo motor en el 88,9 %, el híbrido (RRF) ya no es la apuesta
obvia que parecía cuando solo existía BM25 al 48,1 % — el margen de mejora que le queda es, como
mucho, 3 preguntas. Antes de construirlo tiene más sentido diagnosticar esas 3 a mano (mismo
patrón que en el ticket 10): si BM25 tampoco las encuentra, el híbrido no va a rescatarlas y el
esfuerzo rinde más en la política de abstención o en generación.

## Diagnóstico de las 4 falladas (01-oct-2026)

e-021, e-024 y e-026 comparten el mismo patrón, uno distinto del hueco léxico que resolvía denso:

- **e-021** — "plazo para atender supresión y qué hacer con los datos suprimidos". Fuente
  esperada: `rgpd:art-12.3` (el plazo de un mes, común a *todos* los derechos, no solo
  supresión) + `lopdgdd:art-32.1` (bloqueo de datos tras la supresión). Denso devuelve sobre
  todo variantes de `rgpd:art-17` (el derecho de supresión en sí) — el artículo obvio por tema,
  pero no el que de verdad trae la cifra del plazo. Ninguna de las dos fuentes esperadas aparece
  en el top-10.
- **e-024** — "garantías de videovigilancia y base de licitud". `lopdgdd:art-22.1` sí aparece
  (6º lugar), pero `rgpd:art-6.1` (las seis bases de licitud del RGPD, en general) no. El texto
  del art. 6.1 es una lista abstracta de bases legales sin ninguna palabra de "videovigilancia":
  no hay con qué emparejarlo semánticamente.
- **e-026** — "cuándo comunicar la brecha y en qué tramo de sanción cae no hacerlo". Encuentra
  `rgpd:art-34` (notificación a los afectados) pero no `rgpd:art-83.4` (el tramo de sanción) — el
  mismo patrón que e-024: el artículo de sanciones es una lista de importes y categorías que no
  menciona "brecha" ni "notificación" en ningún sitio.
- **e-025** (ya no falla sin ruta, se incluye para comparar) — incluso aquí `rgpd:art-83.4`
  aparece último, en la posición 10 de 10: el mismo artículo genérico, al límite del corte.

**El patrón real**: no es un hueco léxico ni semántico en el sentido habitual — es que estas tres
preguntas `cruzada` emparejan un artículo específico y temático (fácil de encontrar, porque su
texto comparte vocabulario con la pregunta) con un artículo **transversal y genérico** (plazos,
bases de licitud, tramos sancionadores) cuyo texto es una lista abstracta que se aplica a decenas
de situaciones distintas y por eso no se parece, en vocabulario, a ninguna pregunta concreta.
Ningún motor de similitud —léxico o semántico— tiene mucho con qué engancharlo, porque el
artículo genérico simplemente no contiene las palabras del escenario. Es el espejo del hallazgo
del ticket 10 (hueco léxico cerrado por significado), pero aquí el significado tampoco basta:
hace falta saber que el art. 17 remite al 12.3, o que cualquier infracción tiene su tramo en el
83.4 — es conocimiento de la *estructura* de la norma, no de su contenido.

**Consecuencia para el híbrido**: BM25 no va a encontrar estos artículos genéricos mejor que
denso — si acaso peor, porque tampoco comparten términos literales con la pregunta. El RRF no
es la herramienta para este problema. Lo que sí lo sería (fuera de alcance aquí, candidato a su
propio ticket si hace falta): seguir referencias cruzadas explícitas dentro del propio artículo
recuperado (si el texto de un artículo dice "sin perjuicio de lo dispuesto en el artículo 12",
añadir ese artículo al contexto) — no es retrieval por similitud, es navegación por la estructura
del corpus que ya tenemos modelada.

## Decisión (01-oct-2026)

Con la causa ya entendida y no una incógnita, Santiago decide no perseguir el híbrido ni la
navegación por referencias cruzadas ahora: **88,9 % recall@10 a nivel artículo queda como la
cifra de retrieval de v0**. El margen que queda es pequeño, tiene una causa estructural conocida
(no de ranking) y el proyecto rinde más moviéndose a la pieza que todavía no existe: la política
de abstención y la generación con cita, que son las que de verdad distinguen este proyecto. La
navegación por referencias cruzadas queda anotada en el mapa como mejora futura, no como fog
activo.
