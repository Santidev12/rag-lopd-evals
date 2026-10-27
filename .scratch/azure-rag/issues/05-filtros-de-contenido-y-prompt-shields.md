# Filtros de contenido y defensa ante prompt injection en Azure

Type: research
Status: open

## Question

¿Qué ofrece Azure para el horizonte de Responsible AI y qué es medible con un set adversarial?

- Filtros de contenido de Azure OpenAI / Foundry: categorías, niveles, qué viene activado por defecto,
  qué devuelve el servicio al bloquear (código de error, campo de la respuesta) y cómo se registra.
- **Azure AI Content Safety** y **Prompt Shields**: qué detectan (ataques directos de usuario, ataques
  indirectos en documentos), cómo se llama a la API y cuál es el nivel gratuito y su cuota.
- Cómo se evalúa un filtro de verdad: ¿hay métricas o conjuntos de referencia públicos de prompt
  injection que sirvan de modelo para un set de unas 10 preguntas de ataque propias?
- Cómo interactúan con una política de **abstención**: ¿un bloqueo del filtro cuenta como abstención
  o es otro estado? (hoy: `responde`, `abstiene`, `sin_cita_valida`, `salida_invalida`).
- Qué datos guardan los registros y las trazas de estos servicios (el texto de las preguntas puede
  contener datos personales).

Entregable: un documento con lo anterior, cada dato con su fuente y marcado como **verificado** o
**no verificado**.
