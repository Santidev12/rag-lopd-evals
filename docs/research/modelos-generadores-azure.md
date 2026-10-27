# Modelos generadores en Azure: opciones, cuota, coste y autenticación

> Investigación del ticket `02-modelos-generadores-en-azure` del mapa `azure-rag` (27-oct-2026). Contexto: el generador actual es Gemini 3.5 Flash-Lite (≈ 5.600 tokens de entrada y ≈ 110 de salida por consulta, JSON con `sin_respuesta`, `respuesta`, `citas`, temperatura 0, ≈ 0,0020 $ por consulta según el README). El juez es DeepSeek-V4-Flash. Se quiere pasar el generador a Azure usando solo el crédito de una suscripción nueva.

## Cómo leer este documento (limitación importante)

En la sesión donde se escribió, `learn.microsoft.com`, `azure.microsoft.com`, `github.com`, `openai.com` y `prices.azure.com` **no resuelven** por `WebFetch` (error DNS). Se probó también `raw.githubusercontent.com` (resuelve, pero el repo `MicrosoftDocs/azure-ai-docs` devuelve 404 en todas las rutas probadas) y `api.github.com` (429). **No se pudo leer ninguna página oficial de Microsoft.**

Todo lo de abajo viene de `WebSearch`, que devuelve resúmenes de fragmentos de las páginas oficiales (y de agregadores de terceros). Por eso:

- **verificado** = leído en la fuente primaria. **Ningún dato de precio, cuota o política de este documento alcanza esa marca.** Lo único "verificado" son los datos del propio repositorio (README, mapa) y los cálculos aritméticos.
- **no verificado** = visto solo en un fragmento de búsqueda (aunque el fragmento sea de una página de Microsoft) o dado por un tercero. Se indica la URL que un humano debe abrir.

Los precios y las cuotas cambian: **no usar ninguna cifra de aquí sin abrir la URL indicada.**

## Tabla de candidatos

Precios en USD por millón de tokens, deployment Global Standard (el más barato). Todos **no verificados**; URL oficial a abrir: <https://azure.microsoft.com/pricing/details/azure-openai/> (los snippets de búsqueda de esa página muestran "$-" porque el precio lo pinta JavaScript).

| Candidato | Familia (¿≠ DeepSeek?) | Entrada $/M | Salida $/M | Cuota por defecto citada (Global Standard) | Razonamiento / `temperature` | Fuente de la cifra |
|---|---|---|---|---|---|---|
| `gpt-4.1-mini` | OpenAI (sí, distinta) | 0,40 | 1,60 | 200 RPM / 200.000 TPM, "Tier 0" | No razona; `temperature` se acepta (no verificado en doc oficial) | Precio: agregador azurespeed.com, finout.io, cloudzero.com. Cuota: snippet de la página de cuotas de Microsoft |
| `gpt-5-mini` | OpenAI (sí) | 0,25 | 2,00 | 500 RPM / 500.000 TPM, "Tier 0" | **Razonamiento**: tokens de razonamiento se facturan como salida; `temperature` fijo (ver §4) | Precio: finout.io y cloudzero.com (agregadores). Cuota: snippet de Microsoft |
| `gpt-5.4-mini` (versión 2026-03-17) | OpenAI (sí) | 0,75 | 4,50 | 1.000 RPM / 1.000.000 TPM (tier no indicado) | Familia razonamiento (no verificado) | Precio: blog de Microsoft Tech Community (snippet). Cuota: snippet de la página japonesa de cuotas |
| `gpt-5.4-nano` (versión 2026-03-17) | OpenAI (sí) | 0,20 | 1,25 | 5.000 RPM / 5.000.000 TPM | Familia razonamiento (no verificado) | Precio: blog de Microsoft Tech Community (snippet). Cuota: snippet de la página japonesa de cuotas |
| Llama, Mistral, Phi, Grok (modelos "Foundry Models") | Meta / Mistral / Microsoft / xAI (sí, distintas) | **sin leer** | **sin leer** | **sin leer** | Depende del modelo | Solo se confirmó que existen entradas de precio para Phi-4, Llama 4 Maverick, Llama 3.3 70B y varios Grok; ningún número leído |
| Modelos DeepSeek de Foundry | **DeepSeek (misma familia que el juez)** | — | — | — | — | **Descartados por la regla de familia distinta** |

Notas de la tabla:

- Los modelos de partners (Llama, Mistral, etc.) pueden exigir suscripción a Azure Marketplace y entonces **se facturan fuera del crédito** (ver §7). Por eso los candidatos principales son los de OpenAI, que Microsoft "vende directamente".
- La cuota publicada es un valor por defecto; la real en una suscripción concreta puede ser distinta (ver §1).

## 1. Qué modelos se pueden desplegar, cuotas por defecto y si hace falta solicitar acceso

- **Catálogo.** Microsoft separa "Foundry Models sold by Azure" (facturados con la suscripción, soporte de Microsoft; sin suscripción a Marketplace) de "Foundry Models from partners and community" (Llama, Mistral, Cohere, etc.; requieren Marketplace). **No verificado** (snippet). URLs a abrir: <https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure> y <https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-from-partners>.
- **Modelos pequeños OpenAI vigentes.** Un snippet de la tabla de regiones de Microsoft lista `gpt-5.4-mini` y `gpt-5.4-nano` (versión 2026-03-17) en Global Standard en varias regiones; Data Zone US sí, Data Zone EU "en despliegue" (según el blog) y sin ETA en un hilo de Q&A de hace ~187 días. **No verificado.** URL: <https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure-region-availability>.
- **Cuotas por defecto** (snippets de la página de cuotas): `gpt-4.1-mini` Global Standard 200 RPM / 200.000 TPM; `gpt-5-mini` 500 RPM / 500.000 TPM (ambos "Tier 0"); `gpt-5.4-mini` 1.000 RPM / 1.000.000 TPM; `gpt-5.4-nano` 5.000 RPM / 5.000.000 TPM. **No verificado.** Esos TPM sobran para este uso: 50 preguntas × ≈ 5.700 tokens = ≈ 285.000 tokens en total (cálculo propio, a partir del README). Aun así, con 200.000 TPM de `gpt-4.1-mini` una pasada lanzada en paralelo sin freno podría rozar el límite por minuto; con una pasada secuencial no. URL: <https://learn.microsoft.com/en-us/azure/foundry/openai/quotas-limits>.
- **Cuota real distinta de la publicada.** Un hilo de Microsoft Q&A (mayo 2026) cuenta que `gpt-5.4-mini` aparecía con 0/0 TPM en Canada Central. **No verificado.** Hay que mirar el panel de cuotas de la suscripción nueva en la región elegida antes de planificar. URL del hilo: <https://learn.microsoft.com/en-us/answers/questions/5868707/availability-timeline-for-gpt-5-4-mini-gpt-5-4-nan> (relacionado) y la página de cuotas anterior.
- **Cuotas por suscripción.** Las cuotas se definen por región, suscripción y modelo/tipo de despliegue; una versión nueva de la página menciona gestión de cuota a nivel de suscripción desde el 7-may-2026. **No verificado.** URL: <https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/quota>.
- **¿Hace falta solicitar acceso?** Un snippet de la página de Agent Service (antigua, ~250 días) marca la familia `gpt-5`, `gpt-5-mini`, `gpt-5-nano`, `gpt-5-chat` con "Registration is required" y no marca `gpt-4.1*`. La página de Limited Access dice que no hace falta formulario salvo para modelos de acceso limitado o para pedir guardrails modificados. **No verificado y posiblemente desfasado**: puede que ya no se exija registro para `gpt-5-mini`, y no hay dato sobre `gpt-5.4-*`. URLs: <https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/openai/limited-access> y la página de modelos de arriba.
- **Retirada.** Un espejo de la tabla de retiradas da `gpt-5.4-mini`/`nano` como GA desde el 17-mar-2026 con retirada el 17-mar-2027. Para `gpt-4.1-mini` y `gpt-5-mini` no se encontró fecha de retirada. **No verificado.** Importa porque la línea base debe poder repetirse: conviene fijar versión de modelo y anotar la fecha. URL: <https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-retirements>.

## 2. Coste por millón de tokens y estimación de las 50 preguntas

Datos de partida **verificados** (README del repo): ≈ 5.600 tokens de entrada y ≈ 110 de salida por consulta; Gemini 3.5 Flash-Lite ≈ 0,0020 $ por consulta.

Cálculo aritmético propio sobre los precios **no verificados** de la tabla. Totales para 50 preguntas = 280.000 tokens de entrada + 5.500 de salida (visibles):

| Modelo | Por consulta | 50 preguntas | Comentario |
|---|---|---|---|
| `gpt-4.1-mini` (0,40 / 1,60) | ≈ 0,0024 $ | ≈ 0,121 $ | Sin tokens de razonamiento, la cifra es fiable en estructura |
| `gpt-5-mini` (0,25 / 2,00) | ≈ 0,0016 $ + razonamiento | ≈ 0,081 $ + razonamiento | Cada 500 tokens de razonamiento por consulta añaden ≈ 0,05 $ por pasada (supuesto, no medido) |
| `gpt-5.4-mini` (0,75 / 4,50) | ≈ 0,0047 $ + razonamiento | ≈ 0,235 $ + razonamiento | |
| `gpt-5.4-nano` (0,20 / 1,25) | ≈ 0,0013 $ + razonamiento | ≈ 0,063 $ + razonamiento | |

Conclusión (robusta ante el error de precios): incluso con precios el doble de lo citado y 10 pasadas completas, el gasto queda en pocos dólares, muy por debajo de un crédito de 200 $ (ver §7). Lo que **no** se puede estimar sin medir es el volumen de tokens de razonamiento de los modelos `gpt-5*`; hay que medirlo en la primera pasada. Si el crédito se gasta en otra cosa (Azure AI Search de pago, etc.), el generador no es el factor limitante.

URLs oficiales para confirmar precios: <https://azure.microsoft.com/pricing/details/azure-openai/> y el blog <https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/introducing-openai%E2%80%99s-gpt-5-4-mini-and-gpt-5-4-nano-for-low-latency-ai/4500569>. Una segunda comprobación independiente: la API de precios de Azure `https://prices.azure.com/api/retail/prices` (no accesible desde esta sesión).

## 3. ¿Otra familia que DeepSeek?

- Los modelos de OpenAI (`gpt-4.1-mini`, `gpt-5-mini`, `gpt-5.4-*`) son de otra familia que DeepSeek-V4-Flash: se conserva la regla de que el juez no se favorece a sí mismo. Es una inferencia de la procedencia de los modelos, no una afirmación leída en una doc de Azure. **No verificado** en documentación, pero sin ambigüedad en la práctica.
- Llama (Meta), Mistral, Phi (Microsoft) y Grok (xAI) también son de otra familia.
- **Excluir los modelos DeepSeek de Foundry** como generador: misma familia que el juez. Un snippet de Microsoft agrupa "Microsoft AI, DeepSeek y Grok" entre los modelos vendidos por Azure, así que existen y es fácil elegirlos por error. **No verificado.**
- Matiz que el ticket no menciona: OpenAI y DeepSeek son distintas, pero conviene dejar anotado en el informe que el juez y el generador siguen siendo de proveedores distintos, y que Gemini (el "antes") tampoco compartía familia con el juez.

## 4. Salida JSON estructurada y `temperature`

- **Structured outputs (`response_format` con `json_schema` y `strict: true`)** existe en Azure OpenAI; el artículo de Microsoft lo describe y el modo JSON antiguo solo garantiza JSON válido, no el esquema. **No verificado** (snippet). **No se encontró la lista de modelos compatibles** con `gpt-4.1-mini`, `gpt-5-mini` ni `gpt-5.4-*`. Un blog de Azure de 2024 solo cita `gpt-4o-2024-08-06` y `gpt-4o-mini-2024-07-18`; un hilo de Q&A de oct-2024 decía que `gpt-4o-mini` aún no lo soportaba, y está desfasado. URL a abrir: <https://learn.microsoft.com/azure/ai-foundry/openai/how-to/structured-outputs>.
- **Modelos de razonamiento y `temperature`.** Un hilo de Microsoft Q&A (respuesta de comunidad) lista `temperature`, `top_p`, `presence_penalty`, `frequency_penalty`, `logprobs`, `logit_bias` y `max_tokens` como no aceptados por los modelos de razonamiento (se usa `max_completion_tokens` y `reasoning_effort`). Hilos de foros de OpenAI informan de error 400 "only the default (1) value is supported" con `gpt-5*`. Un issue del SDK de Vercel indica que en `gpt-5.1` la temperatura se puede controlar con esfuerzo de razonamiento "none". **No verificado** y fuentes secundarias. Consecuencia probable, **a confirmar con una llamada real**: con `gpt-5-mini` y quizá `gpt-5.4-*` no se puede pedir `temperature` 0, así que la línea base no sería determinista como la de Gemini; `gpt-4.1-mini` (no razonador) sí debería aceptar `temperature` 0 (no verificado). Para repetibilidad, `gpt-4.1-mini` es el candidato más natural; si se usa un modelo de razonamiento, hay que repetir pasadas y reportar variación. URLs: <https://learn.microsoft.com/azure/ai-foundry/openai/how-to/reasoning> y la referencia de API <https://learn.microsoft.com/en-us/azure/ai-foundry/openai/latest>.
- **Valores de `reasoning_effort`.** La referencia citada solo lista `low`, `medium`, `high`; no se confirmó `minimal`/`none` para estos modelos. **No verificado.** Un `reasoning_effort` bajo reduciría coste y latencia.
- Un hilo de terceros sugiere llamar a los modelos de razonamiento con la API Responses (`responses.parse`) en lugar de `chat.completions`. **No verificado**; fuente de baja confianza.

## 5. Autenticación: clave frente a Entra ID con identidad gestionada

- Microsoft recomienda identidades gestionadas frente a claves para Azure OpenAI. El patrón: asignar el rol **Cognitive Services OpenAI User** sobre el recurso, y en Python usar `DefaultAzureCredential` con un `bearer token provider` para el ámbito `https://cognitiveservices.azure.com/.default`, pasado al cliente `AzureOpenAI` como `azure_ad_token_provider`. Un cambio de rol puede tardar hasta ~5 minutos en surtir efecto. **No verificado** (snippets de Microsoft Learn en versiones localizadas). URLs: <https://learn.microsoft.com/azure/developer/ai/keyless-connections> y <https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/managed-identity>.
- Desactivar la autenticación por clave con `disableLocalAuth: true` en la cuenta de Cognitive Services: dato de una guía de terceros (KodeKloud), **no confirmado en Microsoft**; hay que verificar el nombre de la propiedad y la versión de API. Una guía menciona que el portal de Studio puede dejar de funcionar al deshabilitar las claves; **no verificado**.
- Para el desarrollo local en el portátil, lo normal es `az login` + `DefaultAzureCredential` (sin clave). La identidad gestionada solo existe cuando el servicio corre en Azure (relevante para el ticket 04). Esto es conocimiento general, **no verificado** en una fuente de esta investigación.

## 6. Filtros de contenido nativos

- Configuración por defecto: filtra en severidad **media** (bloquea media y alta, deja pasar baja y segura) las cuatro categorías de daño (odio, sexual, violencia, autolesión) en prompt y respuesta. Según los snippets, las políticas de seguridad por defecto cubren además contenido protegido y ataques de inyección de prompt de usuario; la detección de jailbreak es aparte y está desactivada por defecto. **No verificado** (snippets). URL: <https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/default-safety-policies>.
- Ajuste: todos los clientes pueden modificar umbrales (bajo, medio, alto) creando una configuración de filtro a nivel de recurso y asociándola a uno o varios despliegues. Quitar los filtros del todo o pasar a modo "solo anotar" requiere aprobación (clientes gestionados). **No verificado.** URL: <https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/content-filters>.
- **No se pudo confirmar** el nombre exacto de la política por defecto (se buscó `Microsoft.DefaultV2`, sin resultado). Para este corpus (texto jurídico del RGPD y la LOPDGDD, que menciona violencia, datos sensibles, etc.) hay que medir si el filtro por defecto bloquea alguna de las 50 preguntas: una respuesta bloqueada contaría como abstención o error. Eso lo cubre el ticket 05.

## 7. Crédito de la suscripción nueva

- La cuenta gratuita de Azure da **200 $ de crédito utilizable en 30 días**; se puede usar en servicios fuera de la lista gratuita o por encima de las cantidades gratuitas; no hay cargo salvo que se pase a pago por uso; en el alta se hace una retención temporal de 1 $. **No verificado** (snippet de la página oficial). URL: <https://azure.microsoft.com/free/> (y la página de la oferta de cuenta gratuita).
- **Si el crédito cubre Azure OpenAI/Foundry:** ninguna fuente oficial lo confirmó en los resultados. Un agregador (pricepertoken.com) dice que sí, que se aplica al uso de modelos y que después se factura por token; un blog promocional lo afirma también y no es fiable. **No verificado.**
- **Modelos de Marketplace (partners):** se facturan a través de Azure Marketplace; un hilo de Q&A (ene-2026) cuenta que modelos Claude en Foundry se cobraron fuera del crédito de Founders Hub; otra respuesta de Q&A (jun-2025) decía que Llama y Mistral sí entraban en créditos de startup. **Contradictorio y no verificado.** Regla prudente: usar solo modelos "sold by Azure" y comprobar en Cost Management que el consumo descuenta del crédito.
- **Qué pasa al caducar:** al pasar los 30 días (o agotar el crédito) los servicios de pago se desactivan salvo que se pase a pago por uso. Esto es lo habitual en la oferta, pero **no se leyó en la fuente**; si la cuenta pasa a pago por uso, el gasto sale de la tarjeta. Importante para el mapa: **los 30 días corren desde el alta**, así que conviene crear la suscripción justo antes de empezar el ticket de generación y tener la alerta de gasto (ticket 06) activa.
- Ojo con el reparto del crédito: el mismo crédito de 200 $ lo comparte todo el mapa (Azure AI Search de pago, despliegue, etc.). Las 50 preguntas con cualquier candidato cuestan céntimos (§2), así que el generador no debería agotarlo.

## Recomendación provisional (sujeta a lo que falte por confirmar)

1. **`gpt-4.1-mini`** como primera opción: no razona (gasto predecible), debería aceptar `temperature` 0 y structured outputs, es de otra familia que el juez y su coste es de céntimos por pasada. Riesgos: su cuota por defecto (200.000 TPM) y que no conocemos su fecha de retirada.
2. **`gpt-5-mini` o `gpt-5.4-nano`** como segunda opción para comparar un modelo de razonamiento barato; asumir que no admiten `temperature` 0 y medir los tokens de razonamiento.
3. Evitar DeepSeek en Foundry y los modelos de Marketplace mientras el crédito no esté confirmado para ellos.

## Qué queda por confirmar a mano

1. **Precios reales** de `gpt-4.1-mini`, `gpt-5-mini`, `gpt-5.4-mini`, `gpt-5.4-nano` (y Phi/Llama/Mistral si interesan) en <https://azure.microsoft.com/pricing/details/azure-openai/> (o la calculadora de precios de Azure).
2. **Cuota real** en la suscripción nueva y la región elegida (panel de Cuotas de Foundry), y si aparece 0 TPM. Referencia: <https://learn.microsoft.com/en-us/azure/foundry/openai/quotas-limits>.
3. **Registro de acceso** para `gpt-5-mini` y `gpt-5.4-*` en una suscripción nueva (<https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/openai/limited-access>).
4. **Que el crédito de 200 $ cubre Foundry/Azure OpenAI**, y si cubre modelos de Marketplace: mirar la página de la cuenta gratuita y comprobar en Cost Management tras la primera llamada.
5. **Qué ocurre al caducar el crédito** (30 días): confirmar en las FAQ de <https://azure.microsoft.com/free/> y activar la alerta de gasto antes de desplegar.
6. **Modelos que admiten structured outputs** (lista oficial) y si `strict: true` funciona con `gpt-4.1-mini` y con `gpt-5*`: <https://learn.microsoft.com/azure/ai-foundry/openai/how-to/structured-outputs>. Probar con una llamada real.
7. **`temperature` en modelos de razonamiento** (`gpt-5-mini`, `gpt-5.4-*`) y valores válidos de `reasoning_effort`: <https://learn.microsoft.com/azure/ai-foundry/openai/how-to/reasoning>, y comprobar con una llamada real.
8. **Fechas de retirada** de `gpt-4.1-mini` y `gpt-5-mini` y disponibilidad regional (<https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-retirements>).
9. **Filtro de contenido por defecto**: nombre de la política y si bloquea alguna de las 50 preguntas.
10. **Propiedad `disableLocalAuth`** y el rol exacto de Entra ID en la doc de Microsoft.
