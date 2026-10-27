# Filtros de contenido y defensa ante prompt injection en Azure

Type: research
Status: resolved (27-oct-2026)

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

## Answer

**Verificado** en la especificación OpenAPI oficial y en el código del SDK:
- Prompt Shields (`POST /text:shieldPrompt`) recibe `userPrompt` y `documents[]` y devuelve solo
  `attackDetected` (sí/no), sin puntuación ni categoría. **La API no bloquea: decide la aplicación.**
- Cuatro categorías de contenido (Hate, SelfHarm, Sexual, Violence). El SDK `azure-ai-contentsafety`
  1.1.0b1 (beta) añade Prompt Shields y admite Entra ID.

**Propuestas del informe** (del subagente, no de una fuente):
- Un bloqueo del filtro no encaja en los 4 estados actuales (acabaría como `SALIDA_INVALIDA`): estado
  nuevo `BLOQUEADO`, sin contarlo como abstención ni como sobre-respuesta.
- Medir **ASR** (tasa de éxito del ataque) y **falsos positivos** sobre las 50 preguntas normales. Con
  n = 10, un 0/10 tiene un intervalo de Wilson de 0 % a 28 %: no demuestra seguridad.
- **No guardar el texto de las preguntas en las trazas.**

**No verificado:** la cuota gratuita (F0), el comportamiento por defecto del filtro (el ataque en
documento viene desactivado), la forma exacta del error al bloquear, la retención de datos, y que
Prompt Shields funcione bien en **español** (Microsoft dice que se entrena sobre todo con inglés: el set
debe estar en español con alguna variante en inglés).

**Informe completo:** rama `research/content-safety-prompt-shields` (de la que no se ha hecho PR), fichero `docs/research/content-safety-prompt-shields.md`.
Cada dato del informe va marcado como verificado o no verificado, y termina con la lista de lo que hay
que confirmar a mano.
