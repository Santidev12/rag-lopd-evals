# Embeddings para RAG jurídico en español: auto-alojar vs. API

> Investigación de mercado, septiembre de 2026. Contexto: corpus ~1.500 chunks de texto legal en español, demo en un Hugging Face Space gratuito (CPU Basic: 2 vCPU, 16 GB RAM, sin GPU), presupuesto 10 €/mes, índice precalculable en local.

## TL;DR

No auto-alojes el modelo de embeddings dentro del Space gratuito: no encontramos ningún benchmark real de BGE‑M3 corriendo en CPU pura que garantice <2 s por consulta, y el riesgo de cold-start (Space que "duerme" + carga de un modelo de ~560M parámetros en cada arranque) es alto. **Indexa en local con BGE‑M3** (gratis, buena calidad multilingüe/español, corpus de 1.500 chunks se procesa en minutos en tu portátil) y **en producción llama a BGE‑M3 vía la API de DeepInfra** (mismo checkpoint, mismo espacio vectorial, **0,01 $/millón de tokens**) para embeber solo la consulta — coste real: **céntimos al mes**, muy por debajo de los 10 €. Alternativa 100% sin dependencias externas si prefieres no llamar a ninguna API: usa **multilingual-e5-small** o **paraphrase-multilingual-MiniLM-L12-v2** (~118M parámetros) para indexar Y consultar con el mismo modelo pequeño dentro del propio Space, aceptando una pérdida de calidad de recuperación notable (varios puntos en benchmarks multilingües) a cambio de latencia baja y cero coste externo. Evita `voyage-law-2` para este proyecto: no hay evidencia de que su ventaja legal se sostenga en español, cuesta más y su capa gratuita (50M tokens) es irrelevante frente a esa falta de evidencia. Un reranker cross-encoder completo (BGE-reranker-v2-m3, 568M) en CPU parece demasiado lento para el presupuesto de latencia del demo; si quieres reranking, usa la versión mMiniLM (~117M, entrenada en mMARCO con español) o sáltate el reranking en la demo.

**Recomendación concreta:**
- **Indexación (offline, en tu máquina):** BGE‑M3 vía `FlagEmbedding` o `sentence-transformers`, gratis, una sola vez. Sube el índice (FAISS/Chroma + metadatos) al Space.
- **Consulta (producción, dentro del Space gratuito):** llamada HTTP a BGE‑M3 en DeepInfra (0,01 $/M tokens) — el Space solo hace la llamada de red y el retrieval sobre el índice local, no ejecuta el modelo de embeddings.
- **Reranking (opcional):** `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` en CPU, o desactivado en el demo.
- **Coste mensual estimado:** < 1 € en la práctica para el volumen de un demo (ver §5). Presupuesto de 10 €/mes queda con margen amplio incluso si el tráfico crece 10-50×.

Todo lo que sigue detalla la evidencia, lo que pudimos verificar de fuentes primarias y lo que quedó como estimación o sin verificar.

---

## Nota metodológica importante

El leaderboard de MTEB (https://huggingface.co/spaces/mteb/leaderboard) es una Space de Gradio con la tabla renderizada por JavaScript. **Lo intentamos leer con fetch directo y confirmamos que el HTML estático no contiene datos de la tabla** (solo metadatos y un mensaje de carga "Fetching metadata from the HF Docker repository..."). No pudimos extraer de ahí números de ranking en vivo. Recurrimos a fuentes secundarias.

De esas fuentes secundarias, hay que distinguir dos niveles de confianza:

- **Primarias/fiables**: blogs y model cards oficiales (Qwen, BAAI/HuggingFace, Voyage AI, OpenAI, Cohere, DeepInfra), páginas de pricing oficiales, un paper académico (MMTEB, arXiv 2502.13595).
- **Secundarias de baja confianza**: numerosos sitios "roundup" de 2026 (tokenmix.ai, pecollective.com, costbench.com, embeddingcost.com, premai.io, checkthat.ai, codesota.com, tensoria.fr, presenc.ai, localaimaster.com, app.ailog.fr, etc.) que tienen toda la pinta de contenido generado en masa para SEO. Sus tablas mezclan a veces "MTEB score" global (inglés) con "MTEB multilingual" sin aclararlo, y los números difieren entre sí para el mismo modelo. **Los usamos solo para tener una foto direccional del mercado, nunca como cifra exacta verificada**, y lo marcamos explícitamente cada vez.

---

## 1. MTEB en español / multilingüe

**No pudimos leer la tabla interactiva del leaderboard** (confirmado arriba). Con fuentes secundarias:

- **Qwen3‑Embedding** (fuente primaria: [blog oficial de Qwen](https://qwenlm.github.io/blog/qwen3-embedding/) y [GitHub](https://github.com/QwenLM/Qwen3-Embedding)): la variante de 8B parámetros **lideraba el MTEB multilingual leaderboard a fecha 5 de junio de 2025, con score 70,58**. Familia Apache-2.0, con variantes 0.6B / 4B / 8B y embeddings "Matryoshka" (dimensión reducible). No encontramos desglose específico por español en la fuente oficial.
- **multilingual-e5-large-instruct** (fuente primaria/académica: paper **MMTEB**, arXiv 2502.13595): en la tabla de MTEB(Multilingual) de ese paper, **multilingual-e5-large-instruct (560M parámetros) lidera con score medio 63,2**, por delante de modelos basados en LLM mucho más grandes (GritLM-7B: 60,9; e5-mistral-7b-instruct: 60,3). El paper señala explícitamente que el mejor modelo público disponible tiene "solo" 560M parámetros. Este benchmark **no evalúa BGE-M3 ni jina-embeddings-v3** (no estaban en su conjunto de comparación), y **no reporta un desglose específico para español** (solo "Europe"/multilingüe agregado).
- **BGE‑M3** (BAAI): no es el modelo que más puntúa en el MTEB "global" (orientado a inglés), pero su propuesta de valor —documentada en su propio model card— es explícitamente **multilingüe (100+ idiomas), multi-funcional (denso + sparse + ColBERT) y multi-granular (hasta 8192 tokens)**. Es el modelo open-weight más citado en 2025-2026 como referencia de calidad multilingüe/cross-lingüe, incluido español, aunque no localizamos una cifra MTEB-español aislada y verificada.
- **jina-embeddings-v3**: 570M parámetros, adaptadores LoRA por tarea, buen contexto largo (8192). Aparece consistentemente en el grupo de cabeza en los roundups de baja confianza, sin cifra española verificada.
- **text-embedding-3-small/large** (OpenAI): generalistas, multilingües "razonables" pero no especializados; en los roundups de baja confianza aparecen en la banda media-alta (large ~64-65 en MTEB global agregado, según esas fuentes, no verificado independientemente).
- **Cohere embed-v4**: fuerte soporte multilingüe (100+ idiomas) según su propia documentación, gama alta de precio.
- **voyage-3 / voyage-3-large**: generalista fuerte según Voyage AI, especialmente en benchmarks de recuperación en inglés.
- **voyage-law-2**: ver §4 — específico de dominio legal, evidencia de multilingüismo débil/nula.

**Conclusión honesta del punto 1:** no existen, en lo que pudimos verificar, cifras MTEB desglosadas por español para la mayoría de estos modelos. La señal más sólida y verificable con fuente primaria es que (a) Qwen3-Embedding-8B lideraba el ranking multilingüe global a mediados de 2025, y (b) un modelo relativamente pequeño (560M, multilingual-e5-large-instruct) puede superar a LLMs de 7B en tareas multilingües según el paper académico MMTEB. Para BGE-M3 específicamente en español, la evidencia es reputacional/consenso de comunidad, no una cifra numérica que hayamos podido citar con fuente primaria.

---

## 2. Viabilidad de BGE-M3 en CPU

**Tamaño en disco/RAM** (fuente: herramienta automatizada de HuggingFace en la discusión [BAAI/bge-m3#64](https://huggingface.co/BAAI/bge-m3/discussions/64), y la página del modelo en Ollama):
- Precisión fp16/bf16: ~1,06 GB total de inferencia (la capa más grande pesa 504 MB), con ~20% de overhead adicional esperado sobre la capa más grande.
- Cuantizado int4: ~271 MB.
- Build cuantizada de Ollama: 1,2 GB en disco.
- **No encontramos una cifra de RAM residente real medida (RSS) al cargar el modelo con `sentence-transformers` o `FlagEmbedding`**; por experiencia general con modelos PyTorch de este tamaño, la carga vía Python + PyTorch suele consumir **2-3× el tamaño del checkpoint en RAM** (pesos + buffers + overhead del framework) — **esto es una estimación nuestra, no una medición encontrada**, así que probablemente 2-3,5 GB de RAM real. Con 16 GB disponibles en el Space, esto no es un problema de RAM en sí, pero compite con el resto de la app (Gradio, índice vectorial, LLM de generación si también corre ahí).

**Latencia de embeber una consulta corta en 2 vCPU sin GPU:** **no encontramos ningún benchmark publicado que mida directamente esto** pese a varias búsquedas específicas (HF discussions, GitHub issues, blogs técnicos, Reddit). Lo más cercano que hallamos:
- Un commit de HuggingFace ([mmbert-embed-32k-2d-matryoshka](https://huggingface.co/llm-semantic-router/mmbert-embed-32k-2d-matryoshka/commit/9ea9d54c2c570235de6b036731f5741de312ddb2)) compara BGE-M3 vs Qwen3-0.6B vs mmBERT-Embed, pero **la tabla es en GPU (AMD MI300X)**: BGE-M3 tarda 31,1 ms a 2K tokens y batch=1 — dato irrelevante para CPU, lo incluimos solo para mostrar el orden de magnitud relativo entre modelos en igualdad de hardware.
- Un artículo (Medium, Xiwei Zhou) mide un cross-encoder BGE (arquitectura hermana de tamaño similar, ~568M parámetros, basada en XLM-RoBERTa-large) reordenando ~100 candidatos en CPU: **257 segundos totales (~2,57 s por par)**, frente a 3,4 s en GPU T4 (~180× más rápido en GPU). El hardware CPU exacto no se especifica, lo que limita su fiabilidad, pero da una señal de orden de magnitud: un forward pass de un transformer de ~560M parámetros en CPU compartida puede costar del orden de segundos, no de milisegundos.
- Como referencia relativa (no medida en CPU): un artículo de agregador de baja confianza afirma que un reranker de este tamaño en CPU (Ryzen 7 7800X3D dedicado, no compartido/gratuito) rinde "~1/30 de un H100" y recomienda su uso solo para <100 consultas/día — cifra no verificada de forma independiente pero coherente con la idea de que CPU es 1-2 órdenes de magnitud más lento.

**Tiempo de arranque en frío:** no encontramos documentación oficial de Hugging Face con la duración exacta de sueño/despertar de un Space CPU Basic gratuito (un intento de fetch a la doc específica devolvió 404). Es conocimiento de comunidad (foros de HF) que los Spaces gratuitos se duermen tras inactividad y que el redeploy implica reconstruir el contenedor y recargar cualquier modelo en memoria desde cero, lo que para un modelo de ~1-2 GB puede añadir **varios segundos a más de un minuto** a la primera petición tras dormir — **esto es una estimación basada en comportamiento general de contenedores Docker en Spaces, no una medición específica para BGE-M3 que hayamos podido citar**.

**Conclusión del punto 2:** con la evidencia disponible, **no podemos afirmar con datos duros que BGE-M3 cumpla <2 s por consulta en el Space gratuito**. La única señal cuantitativa real que encontramos (el cross-encoder de tamaño comparable, 2,57 s/par en CPU no especificada) apunta más bien a un riesgo alto de exceder ese presupuesto de latencia, especialmente en el vCPU compartido y "best-effort" de un Space gratuito, sumado al riesgo de cold-start. Por eso recomendamos no auto-alojar BGE-M3 para la ruta de consulta en el Space, y sí usarlo únicamente para indexar en local (donde la latencia no importa).

---

## 3. Alternativa asimétrica: indexar en local, consultar por API

**Sí es compatible, con una condición estricta que confirmamos como crítica:** el vector de la consulta y los vectores del índice deben vivir en el **mismo espacio vectorial** — es decir, deben venir del **mismo modelo y, idealmente, el mismo checkpoint exacto**. Embeber el índice con BGE-M3 y la consulta con, por ejemplo, `text-embedding-3-small` de OpenAI produce vectores de dimensiones y semántica distintas: la similitud coseno entre ambos no tiene ningún significado y el retrieval sería básicamente ruido. Esto no es una opinión nuestra sino la razón estructural de cómo funcionan los embeddings bi-encoder: cada modelo aprende su propio espacio.

La forma correcta de hacer "indexar pesado en local, consultar barato en producción" es: **usar como "API barata" un proveedor que sirva el mismo checkpoint open-weight que usaste en local.** Verificamos una opción concreta y muy barata:

- **DeepInfra sirve BGE-M3** como endpoint de embeddings a **0,010 $ por millón de tokens** ([deepinfra.com/BAAI/bge-m3/api](https://deepinfra.com/BAAI/bge-m3/api)), sin capa gratuita explícita pero con un coste tan bajo que es irrelevante para el volumen de un demo (ver §5). Es el mismo BAAI/bge-m3 que puedes correr en local con `FlagEmbedding`/`sentence-transformers`, por lo que los vectores son compatibles.
- Existen otras plataformas de inferencia (OpenRouter lista `baai/bge-m3` como proveedor agregador) que también podrían servir el mismo checkpoint; no verificamos su precio en detalle porque DeepInfra ya cumple sobradamente el presupuesto.
- La HF Inference API (serverless) también puede servir modelos de HuggingFace bajo capa gratuita con límites de rate, pero no confirmamos su disponibilidad ni límites actuales para BGE-M3 específicamente con una fuente fiable — **no verificado**, tratarlo como opción secundaria a explorar, no como base de la recomendación.

**Conclusión del punto 3:** la arquitectura asimétrica (índice pesado en local + consulta barata en producción) es viable y recomendable siempre que "barata" signifique "el mismo modelo servido por un tercero", no "un modelo distinto más barato". BGE-M3 en local para indexar + BGE-M3 en DeepInfra para consultar es la combinación que mejor cumple esa condición al coste más bajo que encontramos.

---

## 4. ¿Merece la pena voyage-law-2 en español?

**No encontramos evidencia de que la ventaja de dominio legal de voyage-law-2 se sostenga en español.** Lo que sí verificamos:

- El [blog de lanzamiento de voyage-law-2](https://blog.voyageai.com/2024/04/15/domain-specific-embeddings-and-retrieval-legal-edition-voyage-law-2/) y el caso de uso con Harvey ([blog.voyageai.com/2024/07/31/...](https://blog.voyageai.com/2024/07/31/harvey-partners-with-voyage-to-build-custom-legal-embeddings/)) están orientados a legal tech angloparlante (contratos y jurisprudencia en inglés, cliente Harvey es una legaltech en inglés). No encontramos declaración explícita del mix de idiomas de entrenamiento, pero todo el contexto de producto apunta a inglés como idioma dominante.
- El único benchmark de embeddings legales en idioma no inglés que localizamos (**Noxtua Voyage Embed Benchmarking Report**, evaluando textos legales alemanes/UE) **no evalúa voyage-law-2 directamente**: evalúa un modelo propio de Noxtua *fine-tuneado* sobre `voyage-multilingual-2` (el modelo multilingüe genérico de Voyage, no el especializado en derecho) con datos legales alemanes, logrando +25,3% sobre `text-embedding-3-large` en ese dominio. Esto demuestra que el fine-tuning legal *sobre una base multilingüe* funciona bien en alemán, pero **no dice nada sobre si voyage-law-2 (entrenado presumiblemente sobre corpus legal predominantemente en inglés) generaliza a español**. El propio informe declara que no cubre español ni otras lenguas romances.
- No encontramos ningún benchmark público que compare voyage-law-2 contra alternativas generales (BGE-M3, multilingual-e5, voyage-multilingual-2) específicamente en tareas de recuperación legal en español.

**Conclusión del punto 4:** para este proyecto (normativa española), **no hay evidencia que justifique pagar la prima de voyage-law-2** (0,12 $/M, igual que el resto de modelos de dominio de Voyage) frente a un modelo multilingüe general. Si en el futuro se quisiera exprimir calidad de dominio legal en español, el patrón que sí tiene evidencia de funcionar es fine-tunear un modelo *multilingüe* (p. ej. BGE-M3 o voyage-multilingual-2) sobre corpus legal en español, no adoptar un modelo entrenado sobre todo en legal inglés.

---

## 5. Coste real: indexar ~1.500 chunks (~750.000 tokens) + consulta en producción

Tokens de indexación: **750.000** (dado). Asumimos ~30-50 tokens por consulta para el coste de query.

| Opción | Precio indexación (750k tok) | Capa gratuita relevante | Coste indexar tras gratis | Coste por 1.000 consultas (~40 tok c/u = 40k tok) |
|---|---|---|---|---|
| **BGE-M3 local** (auto-alojado offline) | 0 € (cómputo propio) | — | 0 € | N/A (no aplica, se hace local) |
| **BGE-M3 vía DeepInfra** | 0,0075 $ | ninguna declarada, pero precio ya trivial | 0,0075 $ | 0,0004 $ |
| **OpenAI text-embedding-3-small** | 0,015 $ (0,0075 $ con Batch API, -50%) | sin capa gratuita permanente | 0,015 $ | 0,0008 $ |
| **OpenAI text-embedding-3-large** | 0,0975 $ | sin capa gratuita permanente | 0,0975 $ | 0,0052 $ |
| **Cohere embed-v4** | ~0,09 $ (a 0,12 $/M según [embeddingcost.com](https://embeddingcost.com/cohere); un agregador distinto cita 0,10 $/M — **cifras inconsistentes entre fuentes secundarias, no verificado con precisión**) | Trial key: 100 llamadas/min sin tope de tokens, pero **no apto para producción** según Cohere | ~0,09 $ | ~0,005 $ |
| **Voyage voyage-3** | 0,045 $ | **200 millones de tokens gratis** (cubre indexación entera) | **0 €** dentro de la capa gratuita | 0 € dentro de capa gratuita |
| **Voyage voyage-law-2** | 0,09 $ | **50 millones de tokens gratis** (cubre indexación entera) | **0 €** dentro de la capa gratuita | 0 € dentro de capa gratuita (pero ver §4: no recomendado) |
| **Jina embeddings v3** | precio por token no publicado con claridad en la página oficial consultada; solo "tokens gratis" al registrarse y rate limit de 100k TPM en la key gratuita | tokens gratis al registro (cantidad no especificada con precisión) | **no verificado** | no verificado |

**Conclusión del punto 5:** a la escala de este proyecto (1.500 chunks, un demo con tráfico bajo), **el coste de cualquier API de embeddings es prácticamente irrelevante frente al presupuesto de 10 €/mes** — hablamos de céntimos para indexar y fracciones de céntimo por cada mil consultas. Incluso sin ninguna capa gratuita, tendrías que hacer **cientos de miles de consultas al mes** para acercarte a 10 €. La decisión real no la determina el coste de la API sino la viabilidad técnica en CPU (§2) y la compatibilidad de espacio vectorial (§3).

---

## 6. Modelos pequeños multilingües viables en CPU (~100-300M parámetros)

- **multilingual-e5-small** (intfloat, [model card](https://huggingface.co/intfloat/multilingual-e5-small)): **0,1B parámetros** (118M), 12 capas, embeddings de 384 dimensiones. Datos de calidad verificados en la propia model card (benchmark **Mr. TyDi**, MRR@10): e5-small **64,4** vs e5-base **65,9** vs e5-large **70,5**. Es decir, **frente a e5-large hay una caída de ~6 puntos de MRR@10** al pasar al modelo pequeño — una diferencia de calidad real y no trivial, aunque el modelo pequeño sigue siendo funcional. No encontramos cifra específica en español dentro de esta fuente (Mr. TyDi cubre otros idiomas: árabe, telugu, tailandés, etc., no español).
- **paraphrase-multilingual-MiniLM-L12-v2**: mencionado como alternativa habitual en la literatura de la comunidad para CPU (~118M parámetros, 384-dim, basado en la familia MiniLM/mMARCO), pero **no encontramos en esta investigación una cifra MTEB o de retrieval verificada y específica** que lo compare numéricamente contra BGE-M3 — lo dejamos como candidato razonable por reputación de comunidad, no como dato verificado.
- No pudimos obtener una comparación numérica directa "e5-small/MiniLM vs BGE-M3 en español" — no existe (que hayamos encontrado) un benchmark que aísle esa comparación en español específicamente. La comparación Mr. TyDi (e5-small vs e5-large) es la única cifra dura que localizamos sobre el coste de calidad de ir a un modelo pequeño, y es de la misma familia (e5), no cruzada con BGE-M3.

**Conclusión del punto 6:** sí, `multilingual-e5-small` es una opción real para correr indexación y consulta dentro del propio Space gratuito sin depender de ninguna API, con un coste de calidad medible (~6 puntos de MRR@10 menos que su hermano "large" en el único benchmark que verificamos) y, presumiblemente, bastante por debajo de BGE-M3 en calidad de recuperación (no cuantificado con fuente fiable). Su tamaño (5× menor que BGE-M3) sí hace mucho más plausible que cargue rápido y responda con baja latencia en 2 vCPU, aunque tampoco encontramos una medición de latencia real en CPU para este modelo concreto — es una inferencia razonable a partir de su tamaño, no un benchmark verificado.

---

## 7. Reranker en CPU: ¿viable un cross-encoder sobre 20 candidatos en 2 vCPU?

- **BGE-reranker-v2-m3** (568M parámetros, cross-encoder XLM-RoBERTa-large): el único dato cuantitativo real que encontramos en CPU (Medium, Xiwei Zhou) fue **257 s para ~100 pares en CPU** (~2,57 s/par), sin especificar el hardware exacto — dato con reservas por falta de detalle de hardware, pero es la única medición real disponible. Extrapolado (de forma aproximada, no lineal garantizado por batching) a 20 candidatos, estaríamos hablando de **varios segundos a decenas de segundos**, lo cual **incumple claramente el objetivo de <2 s del demo**. Un artículo adicional (baja confianza) sitúa el CPU en "~1/30 del rendimiento de un H100" y recomienda su uso solo para <100 consultas/día en CPU dedicada — coherente con la idea de que no es apto para latencia interactiva en un vCPU compartido y gratuito.
- **Alternativa CPU-viable**: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` ([model card](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1)), ~117M parámetros (mismo orden de tamaño que MiniLM/e5-small, 5× más pequeño que bge-reranker-v2-m3), entrenado sobre **mMARCO** (versión multilingüe de MS MARCO que incluye español, 14 idiomas). No encontramos una medición de latencia CPU real para este modelo específico tampoco, pero su tameño (comparable a los modelos bi-encoder pequeños de §6, que sí tienen indicios razonables de ser rápidos en CPU) hace mucho más plausible que 20 pares se procesen en el orden de cientos de milisegundos a ~1-2 s en 2 vCPU — **esto es una estimación razonada por analogía de tamaño de modelo, no una medición verificada**.

**Conclusión del punto 7:** el reranker "grande" (bge-reranker-v2-m3) probablemente **no es viable** en el Space gratuito dentro del presupuesto de latencia del demo, según la única evidencia cuantitativa real disponible. Si se quiere reranking, la opción con mejor relación tamaño/cobertura de español es la variante mMiniLM (mMARCO), aunque sin verificación de latencia propia; alternativamente, omitir el reranking en la demo y dejarlo como mejora futura (posiblemente vía API, fuera del Space) es razonable dado el presupuesto de tiempo tan ajustado.

---

## Resumen de qué está verificado vs. qué es estimación

**Verificado con fuente primaria/oficial:**
- Precios de OpenAI, Voyage AI, Cohere (parcialmente, ver nota), DeepInfra para BGE-M3.
- Capas gratuitas de Voyage (200M / 50M tokens según modelo).
- Especificaciones del Space CPU Basic gratuito (2 vCPU, 16 GB RAM, disco no persistente).
- Tamaño de BGE-M3 en fp16/int4 (herramienta automatizada de HF).
- Ranking multilingüe de Qwen3-Embedding-8B (blog oficial Qwen, snapshot de junio 2025).
- Resultado de multilingual-e5-large-instruct en MTEB(Multilingual) (paper académico MMTEB).
- Que el leaderboard de MTEB es JS y no se pudo leer directamente.
- Que voyage-law-2 está orientado a legal angloparlante y que el único benchmark legal no inglés encontrado evalúa un modelo distinto (voyage-multilingual-2 fine-tuneado), no voyage-law-2.
- Parámetros y benchmark Mr. TyDi de multilingual-e5-small.
- Existencia y entrenamiento (mMARCO, multilingüe) de `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`.

**Estimación / no verificado (marcado explícitamente en el texto):**
- Latencia real de BGE-M3 embebiendo una consulta en 2 vCPU (no localizado ningún benchmark directo).
- Consumo de RAM real (RSS) de BGE-M3 cargado con sentence-transformers/FlagEmbedding (estimado por regla general 2-3× el tamaño del checkpoint).
- Tiempo exacto de cold-start de un Space gratuito tras dormir (duración de sueño no confirmada con doc oficial; tiempo de recarga del modelo, estimado por comportamiento general de contenedores).
- Precio exacto de Cohere embed-v4 pay-as-you-go (fuentes secundarias discrepan entre 0,10 y 0,12 $/M).
- Precio exacto de Jina embeddings v3/v4 (no publicado con claridad en la página consultada).
- Latencia CPU del reranker mMiniLM y de multilingual-e5-small/paraphrase-multilingual-MiniLM (estimación por analogía de tamaño de modelo, sin medición directa encontrada).
- Cifras MTEB desglosadas por español para la mayoría de modelos (no localizadas; el leaderboard interactivo no fue legible).

---

## Fuentes

**Primarias / oficiales:**
- [MTEB Leaderboard](https://huggingface.co/spaces/mteb/leaderboard) (confirmado no legible vía fetch, JS-rendered)
- [BAAI/bge-m3 — Hugging Face](https://huggingface.co/BAAI/bge-m3)
- [BAAI/bge-m3 discusión #64 — memoria del modelo](https://huggingface.co/BAAI/bge-m3/discussions/64)
- [BAAI/bge-m3 discusión #23 — comparaciones multilingües](https://huggingface.co/BAAI/bge-m3/discussions/23)
- [bge-m3 en Ollama](https://ollama.com/library/bge-m3)
- [Qwen3 Embedding — blog oficial](https://qwenlm.github.io/blog/qwen3-embedding/)
- [Qwen3-Embedding — GitHub](https://github.com/QwenLM/Qwen3-Embedding)
- [MMTEB: Massive Multilingual Text Embedding Benchmark — arXiv 2502.13595](https://arxiv.org/html/2502.13595v4)
- [intfloat/multilingual-e5-small — Hugging Face](https://huggingface.co/intfloat/multilingual-e5-small)
- [cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 — Hugging Face](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1)
- [Voyage AI — Pricing](https://docs.voyageai.com/docs/pricing)
- [voyage-law-2 — blog de lanzamiento](https://blog.voyageai.com/2024/04/15/domain-specific-embeddings-and-retrieval-legal-edition-voyage-law-2/)
- [Harvey + Voyage legal embeddings](https://blog.voyageai.com/2024/07/31/harvey-partners-with-voyage-to-build-custom-legal-embeddings/)
- [Noxtua Voyage Embed Benchmarking Report](https://www.noxtua.com/news/further-publications/noxtua-voyage-embed-benchmarking-report)
- [OpenAI — new embedding models and API updates](https://openai.com/index/new-embedding-models-and-api-updates/)
- [Comunidad OpenAI — discrepancia de precios de embeddings](https://community.openai.com/t/pricing-discrepancy-for-embedding-models-between-pricing-page-and-model-docs/1346972)
- [DeepInfra — BAAI/bge-m3 API](https://deepinfra.com/BAAI/bge-m3/api)
- [Hugging Face — Spaces Overview](https://huggingface.co/docs/hub/en/spaces-overview)
- [Jina AI — Embeddings API](https://jina.ai/embeddings/)

**Secundarias usadas con reservas explícitas:**
- [embeddingcost.com/cohere](https://embeddingcost.com/cohere)
- Medium, Xiwei Zhou — [Speed Showdown: Reranker performance on CPU/GPU/TPU](https://medium.com/@xiweizhou/speed-showdown-reranker-1f7987400077)
- [localaimaster.com — Reranking & Cross-Encoders for RAG](https://localaimaster.com/blog/reranking-cross-encoders-guide)
- Commit de comparación de latencia (GPU) — [mmbert-embed-32k-2d-matryoshka](https://huggingface.co/llm-semantic-router/mmbert-embed-32k-2d-matryoshka/commit/9ea9d54c2c570235de6b036731f5741de312ddb2)
- [premai.io — Best Embedding Models for RAG 2026](https://www.premai.io/blog/best-embedding-models-for-rag-2026-ranked-by-mteb-score-cost-and-self-hosting/) (tabla usada solo como referencia direccional, cifras no verificadas de forma independiente)
