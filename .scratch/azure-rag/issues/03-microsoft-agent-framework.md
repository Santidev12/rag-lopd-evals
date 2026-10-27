# Microsoft Agent Framework: qué es, qué ofrece y cómo se expone como servicio

Type: research
Status: resolved (27-oct-2026)

## Question

Antes de diseñar el agente hay que saber qué ofrece el framework y en qué estado está:

- Estado actual (versión estable o preview), SDK de Python y relación con Semantic Kernel y AutoGen.
- Qué proveedores de modelo soporta (Azure OpenAI, OpenAI, otros) y cómo se autentica con Entra ID.
- Cómo se definen **herramientas** (funciones Python), qué patrones de **orquestación** ofrece (un agente
  con herramientas, flujos/workflows, varios agentes) y cuál encaja con "buscar, abrir artículo, seguir
  remisión".
- **Memoria**: qué abstracciones tiene (historial de conversación, hilos, almacenes) y dónde se guarda.
- **Observabilidad**: soporte de OpenTelemetry, qué trazas emite por defecto y adónde pueden ir sin
  coste (Application Insights, exportador a consola/OTLP local, tracing de Foundry).
- Cómo se **expone como servicio** (¿hosting propio con FastAPI?, ¿algún hosting integrado?) y si se
  integra con FastAPI sin pelearse.

Entregable: un documento con lo anterior, cada dato con su fuente, marcado como **verificado** o
**no verificado**. Incluye los números de versión y las fechas de lo leído: es software joven.

## Answer

**Verificado** leyendo el código publicado en PyPI y ejecutando una prueba local con un cliente falso
(sin probar contra un recurso real de Azure):
- Agent Framework es **GA desde 1.0.0** (abr-2026); `agent-framework-core` 1.23.0 es de 22-oct-2026, con
  releases casi semanales. "1.x" no es todo estable: el metapaquete arrastra ≈ 30 paquetes, muchos en
  beta, y la API deriva (`AzureOpenAIChatClient` ya no existe). Recomendación: instalar solo `core` +
  `openai` + `azure-identity` y **fijar versiones exactas**.
- Herramientas con `@tool` (esquema desde la firma) y bucle acotado por `max_iterations`,
  `max_function_calls` y `max_duration_seconds`. Recomendación: **un solo agente con tres herramientas**
  (buscar, abrir artículo, seguir remisión), sin workflows ni multi-agente de entrada.
- **Memoria:** `AgentSession` + `HistoryProvider`; por defecto vive en el proceso. **Trampa:** el cliente
  de Responses guarda el historial en el servicio salvo `store=False`.
- **Trazas:** OpenTelemetry (`invoke_agent`, `chat`, `execute_tool`); por defecto solo metadatos, sin
  contenido, hasta activar `ENABLE_SENSITIVE_DATA`. Respalda la regla de qué guardan las trazas.
- **FastAPI** no da fricción: `agent.run` es async y admite streaming.

**No verificado:** la guía oficial de hosting, el nivel gratuito de Application Insights, la retención de
datos con `store=True`, y la estabilidad futura de las APIs experimentales.

**Informe completo:** rama `research/agent-framework` (de la que no se ha hecho PR), fichero `docs/research/agent-framework.md`.
Cada dato del informe va marcado como verificado o no verificado, y termina con la lista de lo que hay
que confirmar a mano.
