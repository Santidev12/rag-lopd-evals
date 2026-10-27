# Microsoft Agent Framework: qué es, qué ofrece y cómo se expone como servicio

Type: research
Status: open

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
