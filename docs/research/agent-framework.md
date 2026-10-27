# Microsoft Agent Framework (Python): estado, modelos, herramientas, memoria, trazas y hosting

Investigación del ticket `03-microsoft-agent-framework` del mapa `azure-rag` (rama `azure-rag/mapa`,
`.scratch/azure-rag/issues/03-microsoft-agent-framework.md`). Fecha de la lectura: **27 de octubre de 2026**.

## Cómo se ha leído (y qué significa cada marca)

`learn.microsoft.com`, `devblogs.microsoft.com`, `github.com` y `cdn.jsdelivr.net` **no resuelven** desde el entorno
(`getaddrinfo ENOTFOUND` / 403). Lo que sí llegó:

- **PyPI** (`pypi.org`, `WebFetch`): páginas de proyecto e historial de versiones. Fuente primaria para versiones y fechas.
- **El código fuente publicado**: `pip download` de las ruedas (`.whl`) desde PyPI y lectura de sus ficheros
  (docstrings, firmas, `METADATA`). Es el mismo código que está en `github.com/microsoft/agent-framework/tree/main/python`,
  así que cuenta como fuente primaria. Las citas tienen la forma `PyPI <paquete> <versión> › <ruta dentro de la rueda>`.
- **Una ejecución local de prueba** (sin red, sin claves) con un cliente de chat falso, para comprobar el bucle de
  herramientas, la memoria de sesión y las trazas por defecto. Se marca como **verificado (ejecutado)**.
- **`WebSearch`**: solo fragmentos. Todo lo que descansa solo en ellos va como **no verificado**.

Marcas: **verificado** = leído en fuente primaria o ejecutado aquí; **no verificado** = solo fragmento de búsqueda,
espejo de terceros o memoria.

Versiones leídas: `agent-framework` / `agent-framework-core` **1.23.0** (22-oct-2026), `agent-framework-openai` 1.17.0,
`agent-framework-foundry` 1.15.0, `agent-framework-orchestrations` 1.4.0, `agent-framework-azure-ai-search`
1.0.0b261015, `agent-framework-azure-cosmos` 1.0.0b261015, `agent-framework-redis` 1.0.0b261022,
`agent-framework-ag-ui` 1.7.0, `agent-framework-devui` 1.0.0b261022, `agent-framework-foundry-hosting` 1.0.0b261022.

---

## 1. Estado actual, SDK de Python y relación con Semantic Kernel y AutoGen

**Estado: estable (GA) desde 1.0.0, con una cadencia de releases casi semanal.**

- **Verificado.** `1.0.0` salió en PyPI el **2-abr-2026**; antes hubo `1.0.0b…` (betas, desde el 1-oct-2025) y
  `1.0.0rc1…rc6` (20-feb a 30-mar-2026). Después: 1.1.0 (21-abr), 1.2.0 (24-abr), 1.3.0 (8-may)… 1.20.0 (2-oct),
  1.21.0 (8-oct), 1.22.0 (15-oct), **1.23.0 (22-oct-2026)**. Son 23 minor en ~6,5 meses.
  Fuente: https://pypi.org/project/agent-framework/ (historial de versiones).
- **Verificado.** Clasificador de desarrollo de `agent-framework-core`: *Production/Stable*; Python `>=3.10`
  (3.10 marcado como *deprecated*; clasificadores 3.10 a 3.15); licencia MIT.
  Fuente: https://pypi.org/project/agent-framework-core/ . El proyecto usa Python 3.12, compatible.
- **Verificado. Matiz importante: "1.x" no significa que todo sea estable.** El metapaquete `agent-framework` 1.23.0 es
  solo `agent-framework-core[all]==1.23.0` y el extra `all` arrastra ~30 paquetes de integración, **muchos todavía en
  beta** (`1.0.0b2610…`): `azure-ai-search`, `azure-cosmos`, `redis`, `mem0`, `devui`, `foundry-hosting`, `a2a`,
  `durabletask`, `purview`... Solo algunos están en 1.x: `core` 1.23, `openai` ≥1.17, `foundry` ≥1.15,
  `orchestrations` ≥1.4, `ag-ui` ≥1.7, `declarative` ≥1.4.
  Fuente: `PyPI agent-framework-core 1.23.0 › METADATA` (líneas `Requires-Dist … extra == "all"`).
- **Verificado. Dentro del núcleo hay APIs marcadas explícitamente como experimentales**, con aviso
  "subject to change or removal … without notice": `SESSION_STORE` (`SessionStore`, `FileSessionStore`),
  `FILE_HISTORY` (`FileHistoryProvider`), `HARNESS`, `EVALS`, `VECTOR_STORES`, `FUNCTIONAL_WORKFLOWS`,
  `PROGRESSIVE_TOOLS`, `AGENT_HOOKS`, entre otras.
  Fuente: `PyPI agent-framework-core 1.23.0 › agent_framework/_feature_stage.py` (enum `ExperimentalFeature`) y
  decoradores `@experimental(...)` en `_sessions.py`.
- **Verificado. Hay deriva de API entre versiones.** Varios resultados de búsqueda y un ejemplo empaquetado
  (`agent_framework_ag_ui_examples/server/main.py` en `agent-framework-ag-ui` 1.7.0) usan
  `AzureOpenAIChatClient` / `AzureOpenAIResponsesClient` / `AzureOpenAIChatCompletionClient`; esos nombres **no
  existen** en `agent_framework.azure` ni `agent_framework.openai` de 1.23.0/1.17.0 (grep sin resultados en el código
  del núcleo y de `openai`). Hoy Azure OpenAI se alcanza con `OpenAIChatClient(azure_endpoint=…, credential=…)`
  (sección 2). Conclusión práctica: **fijar versiones exactas** (`==`) en `pyproject.toml` y no fiarse de tutoriales
  antiguos.
- **Verificado.** Instalación mínima razonable para este proyecto: `agent-framework-core` + `agent-framework-openai`
  (+ `azure-identity`), en vez de `agent-framework` (que instala todo el `all`).
  Fuente: https://pypi.org/project/agent-framework-core/ (README: "pip install agent-framework-core", integraciones
  opcionales).

**Relación con Semantic Kernel y AutoGen.**

- **Verificado.** PyPI de Semantic Kernel (**1.45.0, 6-oct-2026**) lleva un aviso "Semantic Kernel is now Microsoft Agent
  Framework!", que llama a MAF su *enterprise-ready successor*, indica que MAF está en 1.0 con APIs estables y
  compromiso de soporte a largo plazo, y enlaza a una guía de migración. **No** dice que SK esté deprecado ni da fecha de
  fin de soporte. Fuente: https://pypi.org/project/semantic-kernel/ .
- **Verificado (parcial).** `autogen-agentchat` en PyPI: última versión **0.7.5, 30-sep-2025**, sin ninguna mención a Agent
  Framework en la descripción. Fuente: https://pypi.org/project/autogen-agentchat/ . Una release un año sin movimiento es
  coherente con "modo mantenimiento", pero no lo prueba.
- **No verificado.** "AutoGen está en modo mantenimiento (desde oct-2025), sin features nuevas, MAF es su sucesor":
  solo en fragmentos de búsqueda de espejos de terceros (un fork en GitHub, Gitee) y blogs. Abrir:
  https://github.com/microsoft/autogen (aviso en el README) y
  https://learn.microsoft.com/agent-framework/migration-guide/from-autogen
- **No verificado.** Fecha oficial del anuncio GA: los fragmentos dicen 3-abr-2026 (blog oficial) y otros 2-abr; PyPI
  confirma la publicación de 1.0.0 el 2-abr (UTC). Abrir https://devblogs.microsoft.com/agent-framework/ (entrada del
  3-abr-2026).
- **No verificado.** Equivalencias SK → MAF (`ChatCompletionAgent` → `client.as_agent(...)`, `@kernel_function` →
  `@tool`): solo en un espejo de terceros (https://www.mintlify.com/microsoft/agent-framework/migration/from-semantic-kernel).
  Lo que sí está verificado en el código es que `@tool` existe (sección 3). Guía oficial a abrir:
  https://learn.microsoft.com/agent-framework/migration-guide/from-semantic-kernel
- **No verificado.** Que existan versiones de MAF para Go (fragmento de un resumen de terceros). Irrelevante aquí.

---

## 2. Proveedores de modelo y autenticación con Entra ID

**Proveedores disponibles (verificado, como paquetes).** El extra `all` de `agent-framework-core` 1.23.0 enumera
paquetes para: OpenAI y Azure OpenAI (`agent-framework-openai`), Microsoft Foundry (`agent-framework-foundry`),
Foundry Local, Anthropic, Amazon Bedrock, Gemini, Mistral, Ollama, GitHub Copilot, Claude, Copilot Studio.
Fuente: `PyPI agent-framework-core 1.23.0 › METADATA`. El README de `agent-framework-core` solo destaca OpenAI,
Microsoft Foundry y Anthropic (https://pypi.org/project/agent-framework-core/). **No he probado ninguno contra un
servicio real** (no hay claves ni suscripción en la sesión).

**Azure OpenAI (verificado en código; no probado contra el servicio).** Se usa la misma clase que OpenAI:

- `agent_framework.openai.OpenAIChatClient` (API *Responses*) y `OpenAIChatCompletionClient` (API *Chat Completions*)
  aceptan `azure_endpoint=…`, `credential=…` (credencial de Azure o *token provider*), `api_version`, `api_key`,
  `base_url`, `async_client`. Pasar `azure_endpoint` o `credential` es "una señal explícita de Azure".
  Fuente: `PyPI agent-framework-openai 1.17.0 › agent_framework_openai/_chat_client.py` (docstring de
  `RawOpenAIChatClient.__init__`, líneas ~660-780).
- Variables de entorno que lee para Azure: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_BASE_URL`, `AZURE_OPENAI_API_KEY`,
  `AZURE_OPENAI_CHAT_MODEL` (luego `AZURE_OPENAI_MODEL`), `AZURE_OPENAI_API_VERSION` (por defecto `"preview"` para
  Responses). Mismo fichero. El parámetro `model` es el nombre del **despliegue**.
- **Entra ID.** La docstring dice que `credential` es "the preferred Azure auth surface" y que los objetos credencial
  "require the optional `azure-identity` package". Internamente usa `get_bearer_token_provider` con el ámbito
  `https://cognitiveservices.azure.com/.default`. Fuente: `agent_framework_openai/_shared.py` (constante
  `AZURE_OPENAI_TOKEN_SCOPE`, función que llama a `azure.identity.get_bearer_token_provider`).
- **Verificado (ejecutado, sin red).** Con `azure-identity` 1.27.0 y `openai` 3.39.0 instalados, esto construye sin
  error y enruta a Azure (`AsyncAzureOpenAI`, `OTEL_PROVIDER_NAME == "azure.ai.openai"`):

  ```python
  from azure.identity import DefaultAzureCredential
  from agent_framework import Agent
  from agent_framework.openai import OpenAIChatClient
  client = OpenAIChatClient(model="<despliegue>", azure_endpoint="https://<recurso>.openai.azure.com",
                            credential=DefaultAzureCredential())
  agent = Agent(client=client, name="x", instructions="...")
  ```
  (No se hizo ninguna llamada de red: solo construcción.)
- **Verificado, con trampa.** `OpenAIChatClient` (Responses) tiene `STORES_BY_DEFAULT = True`
  (historial en el servicio) y `OpenAIChatCompletionClient` lo tiene a `False`. Afecta a la memoria (sección 4).
- **Microsoft Foundry.** `agent_framework.foundry.FoundryChatClient` / `FoundryAgent` usan
  `FOUNDRY_PROJECT_ENDPOINT` y `FOUNDRY_MODEL` y aceptan `credential` (verificado en `PyPI agent-framework-foundry
  1.15.0 › _chat_client.py`). Requiere un proyecto de Foundry; para el mapa no hace falta salvo que se quiera el tracing
  de Foundry (sección 5).
- **No verificado.** Rol RBAC necesario: los fragmentos del tutorial de Learn dicen "Cognitive Services OpenAI User" o
  "Cognitive Services OpenAI Contributor" sobre el recurso, y que la asignación tarda hasta ~5 min en aplicar. Abrir
  https://learn.microsoft.com/en-us/agent-framework/tutorials/agents/run-agent y
  https://learn.microsoft.com/azure/ai-services/openai/how-to/managed-identity
- **No verificado.** Qué modelos concretos (p. ej. no-OpenAI desplegados en Azure/Foundry) funcionan con la API
  *Responses* frente a *Chat Completions*. Eso decide qué cliente usar; depende del ticket del generador.

---

## 3. Herramientas y orquestación: qué patrón encaja con "buscar, abrir artículo, seguir remisión"

**Herramientas (verificado).**

- `@tool` (de `agent_framework`) convierte una función Python (sync o async) en `FunctionTool`: el esquema JSON sale de la
  firma con Pydantic; los parámetros se describen con `Annotated[tipo, "descripción"]` o `Field`; el nombre y la
  descripción salen de `__name__` y del docstring, o de `name=`/`description=`. También hay `schema=` (modelo Pydantic
  o dict JSON), `approval_mode` (`"never_require"` por defecto / `"always_require"`), `max_invocations`
  (por vida de la instancia de la herramienta), `max_invocation_exceptions` y `result_parser`.
  Fuente: `PyPI agent-framework-core 1.23.0 › agent_framework/_tools.py` (función `tool`, líneas ~1668-1850).
- También se aceptan funciones Python "desnudas" en `Agent(tools=...)` (el ejemplo de `RawAgent` pasa `tools=get_weather`
  sin decorar). Fuente: `_agents.py`, docstring de `RawAgent`. Para herramientas con nombre/descr. controladas
  (nuestras tres), conviene `@tool` explícito.
- Servidores MCP: `MCPStdioTool`, `MCPStreamableHTTPTool`, `MCPWebsocketTool` (extra `all` añade `mcp>=2.2.0,<3`).
  Fuente: `agent_framework/__init__.pyi` y `METADATA`. Un agente que consuma el BOE por MCP es posible, pero no es lo que pide
  el ticket.
- **Límites del bucle de herramientas (verificado)**, vía `FunctionInvocationConfiguration`:
  `max_iterations` (viajes al LLM; por defecto **40**), `max_function_calls` (total de llamadas a herramientas por petición;
  por defecto sin límite), `max_duration_seconds` (por defecto sin límite). Al alcanzarlos se desactivan las herramientas y se
  fuerza una respuesta de texto. Son límites "best effort": se comprueban **después** de cada lote de llamadas paralelas.
  Fuente: `_tools.py` líneas ~1871-1990 (`DEFAULT_MAX_ITERATIONS: Final[int] = 40`).
  Esto es justo el mando que hace falta para acotar coste y la sobre-navegación entre remisiones.
- **Verificado (ejecutado).** Un `Agent` con una herramienta `@tool` y un cliente falso ejecutó el ciclo
  modelo → herramienta → modelo y devolvió texto; la herramienta recibió los argumentos tipados (ver apéndice).

**Patrones de orquestación (verificado en existencia y nombres; no probados con modelo real).**

1. **Un agente con herramientas** (`Agent(client, instructions, tools=[…])`; `await agent.run(texto, session=…)`;
   streaming con `stream=True`). Fuente: `_agents.py`, docstring de `RawAgent`.
2. **Workflows**: grafos de ejecutores y aristas (`WorkflowBuilder`, `Executor`, `@handler`, `WorkflowContext`), con
   `max_iterations` por defecto 100, *checkpoints* y flujos funcionales (estos últimos, experimentales). Fuente:
   `_workflows/_workflow_builder.py`, `_feature_stage.py`.
3. **Varios agentes** en `agent-framework-orchestrations` 1.4.0: `SequentialBuilder`, `ConcurrentBuilder`,
   `HandoffBuilder`, `GroupChatBuilder`, `MagenticBuilder`. Fuente: `PyPI agent-framework-orchestrations 1.4.0 › METADATA`
   (campo `Summary`). Además, un agente puede exponerse como herramienta de otro (`agent.as_tool(...)`), visto en
   `_agents.py`.

**Cuál encaja (recomendación, no un hecho de la fuente).** "Buscar normativa → abrir un artículo → seguir una remisión"
es un bucle de decisión abierto (el número de saltos depende de la pregunta), no un grafo fijo. Encaja el **patrón 1: un solo
agente con tres funciones `@tool`** (`buscar_normativa`, `abrir_articulo`, `seguir_remision`), con
`max_function_calls` y `max_iterations` bajos. Los workflows y los varios agentes añaden complejidad que el
objetivo medible (cruzadas sin subir la sobre-respuesta) no justifica todavía; se reconsideran si el eval muestra que un
agente único no basta. Esa decisión es de medición, no de documentación.

---

## 4. Memoria: abstracciones y dónde se guarda

**Abstracciones (verificado, `PyPI agent-framework-core 1.23.0 › agent_framework/_sessions.py`).**

- `AgentSession`: contenedor ligero con `session_id`, `service_session_id` (id de conversación en el servicio, si lo hay)
  y un `state: dict` compartido con los proveedores. Se crea con `agent.create_session()`; se serializa con
  `to_dict()` / `AgentSession.from_dict(...)`. Los valores de `state` propios (clases personalizadas) deben registrarse con
  `register_state_type`.
- `ContextProvider` (`before_run` / `after_run`): inyecta mensajes, instrucciones o herramientas antes de cada llamada.
- `HistoryProvider(ContextProvider)`: carga y guarda el historial. Implementaciones: `InMemoryHistoryProvider`
  (en `session.state["messages"]`; es el que el agente añade automáticamente), `FileHistoryProvider` (JSONL/msgpack,
  **experimental**, texto plano sin cifrar ni bloqueo entre procesos), y en paquetes aparte `CosmosHistoryProvider`
  (`agent-framework-azure-cosmos`, beta), `RedisHistoryProvider` y `RedisContextProvider` (`agent-framework-redis`, beta).
- `SessionStore` / `FileSessionStore`: almacenes de instantáneas de sesión por id (ambos **experimentales**).
- Memoria a largo plazo / extras: `FoundryMemoryProvider` (`agent-framework-foundry`), integración `mem0`,
  `AzureAISearchContextProvider` (`agent-framework-azure-ai-search`, beta), y *compaction* de contexto
  (`SlidingWindowStrategy`, `SummarizationStrategy`, `TruncationStrategy`, `CompactionProvider`...) en el núcleo.
- Ver también `agent_framework/__init__.pyi` (lista de exportaciones) y los `METADATA` de cada paquete.

**Dónde se guarda por defecto (verificado, y ejecutado).**

- Con un cliente que **no** guarda en servidor, el agente añade solo un `InMemoryHistoryProvider` cuando se pasa
  `session=`: el historial vive **en el objeto `AgentSession`, en la memoria del proceso**. Fuente: `_agents.py` líneas
  ~1569-1580 y docstring de `create_session`. En la prueba local, el turno 2 de una sesión envió al modelo 5 mensajes
  (historial del turno 1 + el nuevo), y `session.state` contenía la clave `'in_memory'`.
- **Trampa con Azure OpenAI vía Responses.** `OpenAIChatClient` tiene `STORES_BY_DEFAULT = True`: el agente **no** añade el
  `InMemoryHistoryProvider` y el historial queda en el servicio (`service_session_id`), salvo que se fije `store=False`.
  Con `OpenAIChatCompletionClient` (`STORES_BY_DEFAULT = False`) el historial es local. Fuente: `_clients.py`
  (docstring de `STORES_BY_DEFAULT`), `_agents.py` y la prueba de construcción. Decisión a tomar: si la conversación debe
  vivir en nuestro proceso/almacén (control de qué se guarda; relevante para la política de trazas y RGPD) o en el servicio.
  **No he verificado** qué retención y qué garantías da Azure OpenAI al guardar respuestas con `store=True`: abrir
  https://learn.microsoft.com/azure/ai-services/openai/how-to/responses
- **Para un servicio multi-usuario**: una `AgentSession` por conversación, persistida fuera del proceso (por ejemplo
  `to_dict()` a un almacén propio, o `CosmosHistoryProvider`/`RedisHistoryProvider`, ambos beta). La docstring de
  `OpenAIChatClient` indica que un cliente puede compartirse entre llamadas concurrentes en el mismo event loop, pero que
  cada llamada debe usar su propio `Agent`/`AgentSession`/mensajes/opciones (verificado, `_chat_client.py`).
- **No verificado**: coste y nivel gratuito de Cosmos DB/Redis en Azure; no era objeto de este ticket.

---

## 5. Observabilidad: OpenTelemetry, trazas por defecto y destinos sin coste

**Soporte OpenTelemetry (verificado, `PyPI agent-framework-core 1.23.0 › agent_framework/observability.py`).**

- El núcleo depende solo de `opentelemetry-api`; **no instala exportadores** (el SDK de OTel se instala aparte; para
  Application Insights, `azure-monitor-opentelemetry`). La instrumentación está **activada por defecto**
  (`ENABLE_INSTRUMENTATION=true`), pero sin proveedores/exportadores configurados no sale nada.
- `configure_otel_providers(...)` crea proveedores y exportadores a partir de variables estándar
  (`OTEL_EXPORTER_OTLP_ENDPOINT`, `…_PROTOCOL` (`grpc` por defecto o `http/protobuf`), `…_HEADERS`, `…_TIMEOUT`),
  `ENABLE_CONSOLE_EXPORTERS`, o de `exporters=[…]` propios. "Llamarla una sola vez al arrancar." Como alternativa, se
  configuran los proveedores por otra vía (p. ej. Azure Monitor) y se llama a `enable_instrumentation()` /
  `enable_sensitive_telemetry()`.
- **Spans por defecto (verificado, ejecutado con exportador en memoria):** `invoke_agent <nombre>` (con
  `gen_ai.agent.name`), `chat <modelo>` (`gen_ai.operation.name=chat`) y `execute_tool <herramienta>`
  (`gen_ai.tool.name`), anidados por llamada; además métricas con prefijos `agent_framework` y `gen_ai` (duración y
  tokens). Los nombres de operación están en `OtelAttr` (`"chat"`, `"execute_tool"`, `"invoke_agent"`).
- **Contenido (verificado, docstring y ejecución).** Por defecto solo se emiten **metadatos** (conteo de tokens, nombres de
  operación, duraciones), **sin** contenido de mensajes. `ENABLE_SENSITIVE_DATA=true` (por defecto `False`) añade
  mensajes, argumentos y resultados de herramientas y mensajes de excepción; la propia documentación lo limita a
  desarrollo/pruebas. En la prueba, ningún atributo de span contenía mensajes ni argumentos con la configuración por defecto.
  **Esto da base técnica a la regla pendiente del mapa "qué guardan las trazas":** dejar el flag apagado en el servicio
  desplegado, y asumir que los textos de normativa que devuelven las herramientas contarían como contenido sensible
  si se activa.
- **Convenciones GenAI no estables (verificado).** El valor por defecto de `OTEL_SEMCONV_STABILITY_OPT_IN` selecciona
  `gen_ai_latest_experimental`; la docstring avisa de que "ni siquiera la línea base v1.36.0 es una versión estable" de las
  convenciones GenAI de OTel. Los nombres de atributos pueden cambiar entre versiones.

**Destinos sin coste (lo que se pudo establecer).**

- **Consola:** `ENABLE_CONSOLE_EXPORTERS=true` o `configure_otel_providers(enable_console_exporters=True)`. **Verificado**
  (docstring). Coste cero.
- **Colector OTLP local:** `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317` (gRPC) o 4318 (HTTP) hacia cualquier
  colector/visor local. **Verificado** en cuanto a la configuración; **no verificado** qué visor concreto (Jaeger, panel de
  .NET Aspire, SigNoz, etc.) conviene: no lo he probado. Además hay `vs_code_extension_port` para enviar a las extensiones
  AI Toolkit / Foundry de VS Code (verificado en docstring).
- **Application Insights:** dos caminos. (a) `azure-monitor-opentelemetry` + `configure_azure_monitor(...)` por tu cuenta y
  `enable_instrumentation()` — es lo que la docstring de `configure_otel_providers` describe; **verificado** como camino
  soportado, no probado contra un recurso real. (b) `await FoundryChatClient(...).configure_azure_monitor()`, que obtiene la
  cadena de conexión de Application Insights **del proyecto de Foundry** y requiere `azure-monitor-opentelemetry>=1.8.10,<2`
  (**verificado** en `PyPI agent-framework-foundry 1.15.0 › _chat_client.py`; exige un proyecto de Foundry con App Insights
  conectado). Para el caso de este mapa, el camino (a) evita depender de Foundry.
- **No verificado: el nivel gratuito.** Fragmentos de búsqueda (Microsoft Q&A y páginas de terceros) dicen que
  Application Insights/Log Analytics incluye 5 GB/mes de ingesta gratis por cuenta de facturación y que por encima
  cuesta ~2,3 USD/GB. No he podido leer la página oficial de precios: abrir https://azure.microsoft.com/pricing/details/monitor/
  y https://learn.microsoft.com/azure/azure-monitor/logs/cost-logs
- **No verificado: tracing de Foundry** como producto aparte (el portal de Foundry ve las trazas si se enrutan a App
  Insights del proyecto; solo está confirmado el método de integración de arriba, no lo que muestra el portal ni su coste).
- **No verificado:** que la propagación de contexto de traza no cruce conectores MCP *hosted* (fragmento de la página de
  Learn). Irrelevante si las herramientas son funciones locales.

---

## 6. Cómo se expone como servicio: ¿FastAPI?, ¿hosting integrado?

**Respuesta corta: no hay hosting obligatorio; un `Agent` es una corrutina, y FastAPI se integra sin fricción.**

- **Verificado.** El núcleo no depende de ningún framework web: `agent-framework-core` 1.23.0 declara solo `msgspec`,
  `typing-extensions`, `pydantic`, `python-dotenv`, `opentelemetry-api`, `pyyaml`, `regex` (`METADATA`). `agent.run(...)`
  es `async` y con `stream=True` devuelve un flujo asíncrono iterable con `get_final_response()` (docstring de `RawAgent`),
  que se puede envolver en un `StreamingResponse`/SSE de FastAPI. Es el camino de menor magia para el contrato propio de la
  API (respuesta, citas, estado, trazas) que pide el mapa.
- **Verificado (ejecutado).** Instalar `agent-framework-core` 1.23.0 con `pydantic` 2.14 (el proyecto exige `pydantic>=2.7`) no
  genera conflictos con el entorno aislado; no se probó junto a FastAPI/uvicorn del proyecto real.
- **Verificado, pero opcional.** `agent-framework-ag-ui` 1.7.0 (estable) ofrece
  `add_agent_framework_fastapi_endpoint(app, agent, path="/", …)` que monta un endpoint para un agente o workflow en
  una app FastAPI **con el protocolo AG-UI** (eventos SSE para interfaces de agente); trae `fastapi>=0.121,<0.142` y
  `uvicorn[standard]`. Sirve si la UI hablara AG-UI; para Streamlit + contrato propio, no es necesario y fija un tope de
  versión de FastAPI. Fuente: `PyPI agent-framework-ag-ui 1.7.0 › agent_framework_ag_ui/_endpoint.py` y `METADATA`.
- **Verificado, no apto para producción.** `agent-framework-devui` (beta) es "a sample app … **not** intended for production
  use" (README en `METADATA`): sirve para depurar un agente en local con una API compatible con OpenAI.
- **Verificado, depende de Foundry.** `agent-framework-foundry-hosting` (beta) ofrece `ResponsesHostServer` (API
  *Responses* de OpenAI sobre un agente o workflow) e `InvocationsHostServer`, basados en `azure-ai-agentserver-*`, para
  agentes alojados en Foundry. No hace falta para un FastAPI propio y arrastra más dependencias en beta.
  Fuente: `PyPI agent-framework-foundry-hosting 1.0.0b261022 › METADATA` y `_responses.py`.
- **Verificado, alternativas de hosting en Azure.** Existen `agent-framework-azurefunctions` (`AgentFunctionApp`) y
  `agent-framework-durabletask` (`DurableAIAgent…`), ambos beta (`agent_framework/azure/__init__.py`). El despliegue es
  asunto del ticket de despliegue.
- **No verificado.** Cualquier guía oficial de "hosting" en Learn (páginas de *hosting* / *deployment* de Agent Framework):
  abrir https://learn.microsoft.com/agent-framework/ y buscar "hosting".

**Puntos a tener en cuenta para un servicio FastAPI (verificados en código):** una sesión por conversación y no compartir
`Agent`/`AgentSession` entre peticiones concurrentes (sección 4); fijar `max_function_calls`/`max_duration_seconds`
(sección 3); llamar a `configure_otel_providers` una vez en el *lifespan* de la app (sección 5); y el `Agent` admite
`async with agent` / `open()`/`close()` para liberar recursos.

---

## Apéndice: prueba local ejecutada (reproducible, sin claves)

`agent-framework-core==1.23.0` + `opentelemetry-sdk` en un venv limpio, Python 3.13. Cliente falso
(`class Fake(FunctionInvocationLayer, ChatTelemetryLayer, BaseChatClient)` con `_inner_get_response`), una herramienta
`@tool abrir_articulo(norma, numero)`, dos turnos con la misma `AgentSession`, `configure_otel_providers(exporters=[mem])`.
Resultado: llamadas al modelo con 1, 3 y 5 mensajes (la herramienta se ejecutó y el segundo turno ve el historial);
`session.state` con la clave `'in_memory'`; spans `invoke_agent demo`, `chat`, `execute_tool abrir_articulo`; ningún atributo
con contenido de mensajes por defecto. El script no se ha incluido en el repositorio (solo este documento). Caveat: el
cliente falso no ejercita la red ni la API real de Azure OpenAI.

---

## Qué queda por confirmar a mano

1. Anuncio GA y notas de versión (¿fecha oficial 2 o 3 de abril de 2026?; ¿qué cambió en la serie 1.x?):
   https://devblogs.microsoft.com/agent-framework/ y https://github.com/microsoft/agent-framework/releases?q=tag%3Apython-1&expanded=true
2. Estado de AutoGen (¿modo mantenimiento? términos exactos) y de Semantic Kernel (¿fecha de fin de soporte?):
   https://github.com/microsoft/autogen , https://github.com/microsoft/semantic-kernel ,
   https://learn.microsoft.com/agent-framework/migration-guide/from-autogen y `/from-semantic-kernel`.
3. Azure OpenAI con Entra ID: rol exacto (`Cognitive Services OpenAI User`) y comportamiento real de
   `OpenAIChatClient(azure_endpoint=…, credential=…)` contra un recurso real, con API *Responses* y *Chat Completions*:
   https://learn.microsoft.com/en-us/agent-framework/tutorials/agents/run-agent
4. Retención y garantías de datos cuando se guarda el historial en el servicio (`store=True` en *Responses*), relevante para
   la política de RGPD: https://learn.microsoft.com/azure/ai-services/openai/how-to/responses
5. Nivel gratuito vigente de Application Insights / Log Analytics y su retención:
   https://azure.microsoft.com/pricing/details/monitor/ y https://learn.microsoft.com/azure/azure-monitor/logs/cost-logs
6. Qué visor local de OTLP usar sin coste (no probado): documentación de la página de observabilidad de Agent Framework
   https://learn.microsoft.com/agent-framework/agents/observability
7. Estabilidad de las APIs experimentales que se usarían (`SessionStore`, `FileHistoryProvider`) y de los paquetes beta de
   Cosmos/Redis/Azure AI Search: releases de https://github.com/microsoft/agent-framework (carpeta `python/`).
8. Guía oficial de hosting/despliegue de agentes de MAF (¿recomiendan algo para FastAPI en Container Apps?):
   https://learn.microsoft.com/agent-framework/ (sección de hosting).
9. Qué modelos del generador elegido admiten *Responses* vs *Chat Completions* y llamadas a herramientas con
   `OpenAIChatClient` (depende del ticket del generador).
