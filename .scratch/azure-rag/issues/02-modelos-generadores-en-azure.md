# Modelos generadores en Azure: opciones, cuota, coste y autenticación

Type: research
Status: open

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
