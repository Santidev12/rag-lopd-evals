# Modelos generadores en Azure: opciones, cuota, coste y autenticación

Type: research
Status: resolved (27-oct-2026)

## Question

El generador pasa a un modelo alojado en Azure y se rehace la línea base de generación. ¿Qué opciones
hay realmente con el crédito de una suscripción nueva?

- Qué modelos se pueden desplegar hoy en Azure OpenAI / Azure AI Foundry, con qué cuotas por defecto en
  una suscripción nueva, y si hace falta solicitar acceso.
- Coste por millón de tokens de entrada y salida de los candidatos pequeños/baratos (el contexto de
  cada consulta son ≈ 5.600 tokens de entrada y ≈ 110 de salida). Estimar el coste de las 50 preguntas.
- ¿Es de **otra familia** que DeepSeek (el juez)? Si el generador fuera de la misma familia que el
  juez, se pierde la regla de que el juez no se favorezca a sí mismo.
- Salida JSON estructurada y `temperature`: ¿se puede pedir el mismo formato (`sin_respuesta`,
  `respuesta`, `citas`)? ¿hay modelos de razonamiento que no aceptan `temperature` 0?
- Autenticación: clave frente a Entra ID con identidad gestionada.
- Filtros de contenido nativos: qué se activa por defecto en el despliegue, y si se pueden ajustar.
- Si el crédito de la suscripción nueva caduca (p. ej. a los 30 días): cuánto dura y qué cubre.

Entregable: un documento con tabla de candidatos y cada dato con su fuente, marcado como **verificado**
o **no verificado**.

## Answer

**Ningún dato de Azure se pudo verificar en fuente primaria** (las páginas de Microsoft no eran
accesibles desde la sesión). Lo que sale es una dirección, no hechos:
- **Candidatos:** modelos OpenAI que Azure vende directamente (`gpt-4.1-mini`, `gpt-5-mini`,
  `gpt-5.4-mini`, `gpt-5.4-nano`). Son de **otra familia que DeepSeek** (el juez). Los DeepSeek de Foundry
  quedan **excluidos** por ser de su misma familia.
- `gpt-4.1-mini` no razona: es la primera opción por repetibilidad. Los `gpt-5*` probablemente no aceptan
  `temperature` 0 y añaden tokens de razonamiento, que habría que medir.
- Coste orientativo (precios sin verificar): ≈ 0,06–0,24 USD por pasada de 50 preguntas.
- Riesgo real: la **cuota por defecto en una suscripción nueva puede ser 0** en algunos modelos y regiones.
- Autenticación con Entra ID y `DefaultAzureCredential`, rol "Cognitive Services OpenAI User". El filtro
  de contenido por defecto filtra en severidad media y se puede ajustar.

**No verificado:** todos los precios y cuotas, si el crédito de 200 USD cubre Foundry/Azure OpenAI, el
soporte de salida JSON estricta y de `temperature`, las fechas de retirada y el acceso a los `gpt-5*`.

**Informe completo:** rama `research/modelos-generadores-azure` (de la que no se ha hecho PR), fichero `docs/research/modelos-generadores-azure.md`.
Cada dato del informe va marcado como verificado o no verificado, y termina con la lista de lo que hay
que confirmar a mano.
