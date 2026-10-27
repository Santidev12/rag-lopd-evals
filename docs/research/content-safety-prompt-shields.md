# Filtros de contenido y defensa ante prompt injection en Azure

Investigación del ticket `05-filtros-de-contenido-y-prompt-shields` del mapa `.scratch/azure-rag/`.
Fecha de trabajo: 27 de octubre de 2026.

## Cómo leer las marcas

- **verificado**: lo leí en una fuente primaria (la especificación OpenAPI oficial de Azure, el README
  oficial del SDK, el README del propio proyecto de un benchmark, o el código del repo).
- **no verificado**: solo lo vi en un fragmento de resultados de búsqueda (incluidos fragmentos *de* páginas de
  learn.microsoft.com, que no pude abrir) o de memoria. Se da la URL exacta que un humano debe abrir.

Limitación del entorno: `learn.microsoft.com`, `azure.microsoft.com`, `techcommunity.microsoft.com`, `arxiv.org`,
`huggingface.co` y `genai.owasp.org` no resuelven (DNS). `github.com` y `api.github.com` tampoco, pero
`raw.githubusercontent.com` **sí** resuelve para repos públicos y allí está la especificación OpenAPI de
Content Safety (fuente primaria de la API). Las páginas de documentación de Microsoft (`MicrosoftDocs/azure-ai-docs`)
devuelven 404 en raw, así que no hay manera de leer las páginas de concepto en este entorno. Nota: la herramienta de
lectura resume el contenido con un modelo pequeño; lo marcado como verificado son datos que el resumen citó
literalmente del fichero fuente, pero conviene un vistazo humano a las cifras críticas.

---

## 1. Filtros de contenido de Azure OpenAI / Foundry

### 1.1 Categorías

- Cuatro categorías de daño: Hate, SelfHarm, Sexual, Violence. **verificado**
  (`TextCategory` en la spec de Content Safety:
  https://raw.githubusercontent.com/Azure/azure-rest-api-specs/main/specification/cognitiveservices/data-plane/ContentSafety/stable/2024-09-01/contentsafety.json ;
  README del SDK: https://raw.githubusercontent.com/Azure/azure-sdk-for-python/main/sdk/contentsafety/azure-ai-contentsafety/README.md).
  Esto describe el servicio Content Safety; que el filtro de Azure OpenAI use las mismas cuatro categorías
  lo dice la documentación de Microsoft (ver 1.2), **no verificado**.
- Además de las cuatro, el filtro de Azure OpenAI/Foundry incluye clasificadores de "prompt attack"
  (ataque de usuario y ataque en documento) y de material protegido (texto y código). **no verificado**
  (fragmento de búsqueda de https://learn.microsoft.com/en-us/azure/foundry-classic/openai/how-to/content-filters).

### 1.2 Niveles y valores por defecto

- Escala de severidad del servicio Content Safety: por defecto 4 niveles (0, 2, 4, 6); con
  `outputType = EightSeverityLevels`, 8 niveles (0 a 7). **verificado** (spec 2024-09-01, campo `outputType`).
- Umbral por defecto del filtro de Azure OpenAI: severidad **media** en las cuatro categorías, para
  prompt y para completion (se filtra medium y high; low y safe pasan). **no verificado**
  (fragmento de búsqueda de https://learn.microsoft.com/en-us/azure/foundry-classic/openai/how-to/content-filters).
- Detección de ataque de usuario (jailbreak/direct) **activada por defecto**; detección de ataque en
  documento (indirect) **desactivada por defecto** y hay que activarla. **no verificado**
  (fragmento de búsqueda de https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/content-filter-prompt-shields).
  Una guía de terceros dice lo contrario para el indirect; no es fuente fiable. Abrir la página y confirmar,
  porque cambia directamente qué se mide.
- Hay informes (preguntas en Microsoft Q&A de 2026) de que en algunos despliegues de modelos nuevos el filtro por
  defecto no se evaluaba. **no verificado**, anecdótico:
  https://learn.microsoft.com/en-us/answers/questions/5972501/azure-openai-gpt-5-6-terra-content-filter-not-eval .
  Implicación para el proyecto: no asumir que "el filtro está puesto"; comprobarlo con una petición de prueba
  y mirar si la respuesta trae `content_filter_results`.

### 1.3 Qué devuelve el servicio al bloquear

- Prompt bloqueado: HTTP **400** con `error.code = "content_filter"`; en `innererror` aparece
  `ResponsibleAIPolicyViolation` y un objeto `content_filter_result` con flags `filtered`/`detected`
  (p. ej. en `jailbreak`). **no verificado** (fragmentos de búsqueda de la documentación y de issues públicos
  de terceros, p. ej. https://github.com/cline/cline/issues/8860). Ojo: no todo 400 es del filtro
  (contexto demasiado largo, parámetro no soportado), así que el código debe comprobarse, no asumir.
- Salida bloqueada: la respuesta puede ser HTTP 200 con `finish_reason = "content_filter"` y contenido
  omitido o incompleto; en streaming el flujo termina con ese `finish_reason`. **no verificado**
  (fragmento de https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/content-streaming).
- Facturación: un 400 por prompt filtrado se cobra solo por la evaluación del prompt. **no verificado**
  (mismo fragmento de content-streaming).
- Falsos positivos: hay muchos informes públicos de peticiones normales marcadas como jailbreak (por ejemplo
  texto de documentos pegado en el prompt). **no verificado**, de terceros. Relevante para un RAG: los artículos
  recuperados van dentro del prompt y podrían disparar el filtro; hay que medir también falsos positivos con
  las 50 preguntas normales del eval set.
- Para el Content Safety directo (no Azure OpenAI): la forma del error es el estándar de Azure:
  `{ "error": { "code", "message", "target", "details", "innererror" } }` y cabecera `x-ms-error-code`.
  **verificado** (`Azure.Core.Foundations.ErrorResponse` en la spec 2024-09-01).

### 1.4 Cómo se registra

- No pude confirmar qué registra el servicio ni dónde se ven las anotaciones del filtro (diagnostic settings,
  trazas de Foundry). **no verificado**. Ver sección 5. Páginas a abrir:
  https://learn.microsoft.com/en-us/azure/foundry-classic/openai/how-to/content-filters y
  https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/content-filter-prompt-shields .

---

## 2. Azure AI Content Safety y Prompt Shields

### 2.1 Qué detectan

- Prompt Shields analiza el prompt del usuario (ataques directos, "user prompt attacks": intentos de saltarse
  las instrucciones de sistema o el entrenamiento de seguridad) y documentos (ataques indirectos: instrucciones
  ocultas en documentos, correos o páginas web que intentan secuestrar la sesión). **no verificado** como
  descripción conceptual (fragmento de https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/jailbreak-detection).
  Lo que sí está **verificado** en la spec de la API: la operación se describe como "A synchronous API for shielding
  prompt from direct and indirect injection attacks"; `userPrompt` "may contain direct injection attacks";
  `documents` "may contain direct or indirect injection attacks".
- Es una clasificación binaria: devuelve si hay ataque o no, sin categoría ni puntuación. **verificado** en la spec
  (el único campo de resultado es `attackDetected: boolean`, tanto para el prompt como para cada documento;
  no hay score, ni texto analizado en la respuesta).
- La API en sí no bloquea nada: devuelve el veredicto y la aplicación decide. **no verificado** (fragmento de
  la documentación de Microsoft). Esto es lo que importa para el diseño de estados (sección 4).
- Idiomas: Microsoft indica que los modelos de ataque de usuario y de documento se entrenan y evalúan
  principalmente con contenido en inglés y el rendimiento puede variar en otros idiomas; la detección de idioma
  es automática. **no verificado** (fragmento de https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/jailbreak-detection
  y de https://learn.microsoft.com/en-us/azure/ai-services/content-safety/language-support). **Para este proyecto es el
  punto crítico: las preguntas son en español, así que el set adversarial debe estar en español** (y conviene
  incluir alguna variante en inglés para contrastar).

### 2.2 Cómo se llama a la API

- `POST {endpoint}/contentsafety/text:shieldPrompt?api-version=2024-09-01`. **verificado** el path `/text:shieldPrompt`
  y la existencia de la versión estable `2024-09-01` (spec; el prefijo `/contentsafety` y el parámetro
  `api-version` no los vi literalmente en la spec, vienen del fragmento de búsqueda de
  https://learn.microsoft.com/en-us/rest/api/contentsafety/text-operations/shield-prompt?view=rest-contentsafety-2024-09-01 ,
  **no verificado**).
- Cuerpo de la petición: `{"userPrompt": "...", "documents": ["...", "..."]}`; ambos campos opcionales, sin
  `maxLength` ni límite de elementos declarado en la spec. **verificado**.
- Respuesta: `{"userPromptAnalysis": {"attackDetected": bool}, "documentsAnalysis": [{"attackDetected": bool}, ...]}`.
  **verificado**. La spec no documenta explícitamente cómo se asocia cada entrada de `documentsAnalysis`
  con cada documento enviado (presumiblemente por orden: **no verificado**).
- Versiones de la API: la spec define `2023-04-30-preview`, `2023-10-01`, `2023-10-15-preview`, `2024-02-15-preview`,
  `2024-09-01` (estable), `2026-07-01-preview` y `2026-09-01-preview` (la global por defecto del readme).
  **verificado**
  (https://raw.githubusercontent.com/Azure/azure-rest-api-specs/main/specification/cognitiveservices/data-plane/ContentSafety/readme.md).
  La `2026-09-01-preview` mantiene `text:shieldPrompt` con el mismo esquema y añade operaciones como
  `content:unifiedModerate`, `text:detectProtectedMaterial` y `provenance:detect`. **verificado**
  (spec preview/2026-09-01-preview). Una versión preview puede cambiar: fijar `2024-09-01` salvo motivo.
- Límites de entrada: 10.000 caracteres por prompt; hasta 5 documentos con 10.000 caracteres en total.
  **no verificado** (fragmento que cita la página de límites de servicio vía un espejo de GitHub). Distinto
  de `text:analyze`, cuyo límite sí está **verificado**: `text` con `maxLength` 10000 (spec).
- Text analyze (categorías de daño): `POST /text:analyze` con `text`, `categories`, `blocklistNames`,
  `haltOnBlocklistHit`, `outputType`; respuesta `categoriesAnalysis[{category, severity}]` y `blocklistsMatch`.
  **verificado** (spec 2024-09-01). Hay blocklists propias (máx. 100 elementos por petición en la preview
  2026-09-01). **verificado**.
- SDK de Python: `azure-ai-contentsafety`; la versión 1.1.0b1 (2026-09-14) añade "support for prompt shielding and
  protected-material detection". **verificado**
  (https://raw.githubusercontent.com/Azure/azure-sdk-for-python/main/sdk/contentsafety/azure-ai-contentsafety/CHANGELOG.md).
  El README del SDK admite clave (`AzureKeyCredential`) o Microsoft Entra ID (`DefaultAzureCredential`, rol
  "Cognitive Services User", requiere subdominio personalizado). **verificado**. Coherente con el ticket de
  identidad gestionada: preferir Entra ID antes que claves, y no poner claves en el repo.

### 2.3 Nivel gratuito y cuota

- Existen niveles F0 (gratuito) y S0 (estándar). **no verificado** (fragmento de la página de overview).
- Cuota gratuita F0: 5.000 registros de texto al mes (Prompt Shields entra en esa cuota de texto) y 5.000
  imágenes; sin cobro por exceso (se detiene). **no verificado** (fragmento de la página de precios oficial).
- Un registro de texto = 1.000 caracteres; un prompt largo consume varios. **no verificado**.
- Límite de ritmo: F0 5 peticiones/segundo en Prompt Shields, S0 1000 por 10 segundos. **no verificado**
  (fragmento de la overview).
- Precio S0 visto en un blog de terceros: 0,375 USD por 1.000 registros de texto. **no verificado**, de terceros,
  no usar.
- Para un set de ~10 ataques más ~50 preguntas normales, 60 llamadas por pasada caben de sobra si la cuota
  es la indicada, pero hay que **confirmar la cuota actual en la página de precios antes de apoyarse en ella**:
  https://azure.microsoft.com/en-us/pricing/details/cognitive-services/content-safety/

---

## 3. Cómo se evalúa un filtro de verdad (modelo para ~10 preguntas propias)

### 3.1 Benchmarks y datasets públicos (de referencia, no para reutilizar tal cual)

- **BIPIA** (Microsoft): primer benchmark de inyección indirecta; 5 tareas (Email QA, Web QA, Summarization,
  Table QA, Code QA), 25 LLM evaluados; métrica principal **ASR** (attack success rate) calculada con un LLM
  evaluador. **verificado** (README: https://raw.githubusercontent.com/microsoft/BIPIA/main/README.md). El README no
  da el número de muestras.
- **AgentDojo** (ETH Zurich/Invariant Labs, NeurIPS 2024 Datasets & Benchmarks): entorno dinámico para evaluar
  ataques y defensas de prompt injection en agentes; se configura modelo + defensa + ataque. **verificado**
  (README: https://raw.githubusercontent.com/ethz-spylab/agentdojo/main/README.md). El README no define las métricas;
  en el paper se mide utilidad y tasa de éxito del ataque, **no verificado** (de memoria; paper
  https://arxiv.org/abs/2406.13352). Útil cuando llegue el ticket del agente.
- **PINT** (Lakera): 4.314 entradas, 3.016 en inglés y 1.298 en otros 24 idiomas (incluido español);
  mezcla de datos públicos y propietarios, así que no es descargable entero (el repo solo trae un dataset de
  ejemplo); métrica "PINT score" en %. Sus datasets propios usan campos `text`, `category`, `label` y se puede
  enchufar cualquier detector como función `str -> bool`. **verificado**
  (https://raw.githubusercontent.com/lakeraai/pint-benchmark/main/README.md). El formato `text/category/label` es una
  buena plantilla para el set propio.
- **LLMail-Inject** (Microsoft y otros): 208.095 ataques únicos de 839 participantes contra un asistente de correo;
  paper arXiv:2506.09956; datos en `microsoft/llmail-inject-challenge` (Hugging Face). **no verificado**
  (fragmentos de búsqueda; abrir https://arxiv.org/abs/2506.09956). Mayoritariamente inglés y orientado a correo.
- **deepset/prompt-injections** (Hugging Face): no pude abrirlo; no doy cifras. **no verificado**.
  URL: https://huggingface.co/datasets/deepset/prompt-injections
- **OWASP LLM01 Prompt Injection**: taxonomía directa/indirecta y mitigaciones. **no verificado** (no resolvió):
  https://genai.owasp.org/llmrisk/llm01-prompt-injection/

### 3.2 Qué métricas copiar (recomendación de diseño, no un hecho externo)

Con n ≈ 10 no hay potencia estadística; el mapa ya exige intervalo de confianza con n pequeño. Propuesta:

1. **ASR** (attack success rate): fracción de ataques que logran su objetivo. Es la métrica de BIPIA y la natural.
   Con 10 ataques, 0/10 tiene un intervalo de Wilson al 95 % de aproximadamente 0 a 28 %: un 0 % observado
   no demuestra seguridad. (Cálculo propio de la fórmula de Wilson, no de una fuente.)
2. **Tasa de falsos positivos** del filtro: las 50 preguntas normales del eval set pasadas por el mismo filtro. Un
   filtro que bloquea preguntas jurídicas legítimas (hay informes de falsos positivos en RAG, ver 1.3) es un
   coste real. Esto es el equivalente exacto de la "abstención indebida" ya medida.
3. Medir **por capa**: Prompt Shields solo, filtro del modelo solo, política de abstención propia sola, y
   combinadas. Igual que los controles de `responder.py`, que ya se miden por separado.
4. Cada ataque lleva etiqueta de objetivo comprobable sin juez LLM cuando sea posible (p. ej. "la respuesta
   contiene la cadena canario X", "revela el prompt de sistema", "cita un artículo que no está en el contexto").
5. Cubrir al menos: instrucción directa de ignorar reglas; extracción del prompt de sistema; juego de rol
   (jailbreak); inyección **indirecta** dentro de un artículo recuperado (ataque en el contexto, no en la
   pregunta); petición de exfiltrar datos personales de otro usuario; petición de asesoría ilegal/daño; ataque
   codificado u ofuscado; ataque en inglés contra un sistema en español; pregunta legítima con vocabulario
   alarmante (control de falsos positivos); mezcla de pregunta legítima con instrucción incrustada.
   Se escriben a mano (decisión ya fijada en el mapa).
6. Para el ataque indirecto hay que probar `documents` en Prompt Shields y la detección de "document attack" del
   filtro del modelo (desactivada por defecto, ver 1.2): si no se activa, se está midiendo la ausencia de defensa.
7. **No poner datos personales reales** en las preguntas de ataque; usar nombres y DNI claramente ficticios.
   El set se versiona en git y se envía a un servicio externo.

---

## 4. Interacción con la política de abstención

Estado actual verificado en el repo: `Estado` tiene `RESPONDE`, `ABSTIENE` (el modelo declara `sin_respuesta`),
`SIN_CITA_VALIDA` (respondió sin citar un artículo del contexto) y `SALIDA_INVALIDA` (no devolvió el JSON).
**verificado** (`src/rag_lopd/generacion/modelo.py` y `src/rag_lopd/generacion/responder.py`). El docstring ya afirma
que "distinguir las tres formas de no responder importa". Eso encaja con lo siguiente.

- Un bloqueo del filtro **no es** ninguna de las cuatro. En `responder()` el modelo ni siquiera llega a devolver
  texto cuando hay un 400 `content_filter` (entrada) y, con `finish_reason = "content_filter"`, el texto puede
  venir vacío o truncado (ver 1.3, **no verificado**); si hoy se pasara ese texto por `_Salida.model_validate_json`
  acabaría como `SALIDA_INVALIDA`, que es el estado equivocado: es un fallo de formato, no una decisión de
  seguridad. **Recomendación (mía, no una fuente):** añadir un estado propio, p. ej. `BLOQUEADO`, con el
  origen del bloqueo (`entrada` / `salida` / `prompt_shields`) y la categoría si existe, y **no contarlo ni
  como abstención ni como sobre-respuesta**.
- Razones para no fundir bloqueo y abstención:
  - Distinta causa y distinto arreglo: la abstención se corrige con prompt o recuperación; el bloqueo, con
    configuración del filtro.
  - Un bloqueo ante una pregunta **legítima** es un falso positivo del filtro, no una abstención indebida del
    modelo; mezclarlos contamina la "abstención indebida 8,8 %" publicada y rompe la comparabilidad antes/después.
  - Un bloqueo ante un ataque es un **acierto** y, si se contara como abstención, parecería un fallo de cobertura.
- Dónde situar Prompt Shields: como control previo a `completar` (antes de gastar la llamada al modelo) y,
  para ataques indirectos, sobre los textos de los artículos recuperados enviados como `documents`. La API solo
  devuelve el veredicto (ver 2.1), así que la política de qué hacer con un `attackDetected = true` es decisión
  del proyecto.
- Si el filtro del modelo bloquea dentro de la propia llamada, el cliente de generación en Azure tiene que
  traducir el 400 `content_filter` y el `finish_reason` a ese estado en lugar de lanzar una excepción genérica;
  hay que comprobar el comportamiento real con el SDK (el formato exacto del error en el cliente de Python:
  **no verificado**).
- Aviso: hay informes de que el filtro de jailbreak marca texto legítimo pegado en el prompt (ver 1.3). En un RAG
  eso significa que un artículo de ley recuperado podría provocar un bloqueo; vale la pena registrar el motivo
  para poder distinguirlo en la evaluación.

---

## 5. Qué datos guardan los registros y las trazas

Es la sección con menos verificación; **todo lo siguiente es no verificado** salvo lo indicado.

- Content Safety (`text:analyze`, `text:shieldPrompt`): no encontré ninguna declaración oficial de retención.
  Un catálogo de terceros dice "no se almacenan los datos", pero la frase parece copiada de Translator y no es
  fiable. La spec de la API no incluye el texto analizado en la respuesta (**verificado**, ver 2.2), lo cual
  reduce el eco de datos personales en las respuestas, pero no dice nada sobre almacenamiento en el servicio.
  Abrir: https://learn.microsoft.com/en-us/azure/ai-services/content-safety/overview (sección de cifrado y privacidad)
  y la página "Data, privacy, and security" de Azure AI services.
- Azure OpenAI / Foundry: el monitoreo de abuso puede almacenar prompts y completions y someterlos a revisión
  humana solo cuando la revisión automática no alcanza el umbral de confianza. Se repite a menudo la cifra de
  30 días, pero un hilo de Microsoft Q&A indica que esa frase se retiró alrededor del 18-nov-2024 y la
  documentación actual no daría un número fijo de días. Existe "Modified Abuse Monitoring" que elimina el
  almacenamiento y la revisión humana, pero con acceso restringido (programa de acceso limitado).
  Fuentes (Q&A, no documentación): https://learn.microsoft.com/en-us/answers/a/12983467 .
  Abrir la página oficial de datos, privacidad y seguridad de Azure OpenAI/Foundry y leer la retención vigente.
- Registros propios: lo que el proyecto decida guardar en trazas (y en el agente, en Foundry/Application
  Insights) es responsabilidad suya. Lo que sí es un hecho del repo: el texto de la pregunta puede contener datos
  personales y se envía a Azure; el mapa ya prevé "una regla sobre qué guardan las trazas". Recomendación (mía):
  registrar identificadores, estado, categoría de bloqueo y tokens, **no** el texto de la pregunta, o guardarlo
  solo con un campo explícito y caducidad. Para el set adversarial no aplica si es 100 % ficticio.
- RGPD: para tratar datos personales de usuarios reales con un encargado (Azure) habría que revisar el
  contrato de tratamiento y la región de proceso. Fuera del alcance de este ticket y **no verificado** aquí.

---

## Qué queda por confirmar a mano

1. Cuota gratuita actual de Content Safety (5.000 registros de texto/mes F0, sin cobro por exceso, 1 registro =
   1.000 caracteres) y límite de ritmo (5 RPS F0): https://azure.microsoft.com/en-us/pricing/details/cognitive-services/content-safety/
   y https://learn.microsoft.com/en-us/azure/ai-services/content-safety/overview
2. Límites de entrada de Prompt Shields (10.000 caracteres; 5 documentos / 10.000 en total):
   https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/jailbreak-detection y la página de
   límites de servicio de Content Safety.
3. Valores por defecto del filtro de Azure OpenAI/Foundry (umbral medio en las 4 categorías; ataque de usuario
   activado, ataque en documento desactivado) en el modelo concreto que se elija:
   https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/content-filter-prompt-shields y
   https://learn.microsoft.com/en-us/azure/foundry-classic/openai/how-to/content-filters . Comprobarlo además con
   una petición real (hay informes de despliegues nuevos sin filtro efectivo).
4. Formato exacto del error 400 y de `content_filter_results` / `finish_reason` en la versión de API y SDK que se use:
   https://learn.microsoft.com/en-us/azure/foundry-classic/openai/concepts/content-filter (y capturarlo en una prueba).
5. Soporte de idiomas de Prompt Shields para español (Microsoft dice "principalmente inglés"):
   https://learn.microsoft.com/en-us/azure/ai-services/content-safety/language-support
6. Retención y registro de datos: Content Safety, Prompt Shields y monitoreo de abuso de Azure OpenAI, y si procede
   solicitar Modified Abuse Monitoring: página "Data, privacy, and security" de Azure OpenAI/Foundry en learn.microsoft.com.
7. Prefijo `/contentsafety` y `api-version=2024-09-01` en la URL de `shieldPrompt`, y la correspondencia por orden
   de `documentsAnalysis` con `documents`: https://learn.microsoft.com/en-us/rest/api/contentsafety/text-operations/shield-prompt?view=rest-contentsafety-2024-09-01
8. Datasets de referencia: LLMail-Inject (https://arxiv.org/abs/2506.09956), deepset/prompt-injections
   (https://huggingface.co/datasets/deepset/prompt-injections), métricas de AgentDojo (https://arxiv.org/abs/2406.13352)
   y OWASP LLM01 (https://genai.owasp.org/llmrisk/llm01-prompt-injection/).
9. Si el SDK de Python con Prompt Shields (`azure-ai-contentsafety` 1.1.0b1) es suficientemente estable, o si
   conviene llamar por REST; y si la spec preview `2026-09-01-preview` es la que se quiere usar.
