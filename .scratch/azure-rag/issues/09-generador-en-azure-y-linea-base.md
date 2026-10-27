# Generador en Azure: qué modelo y cómo se rehace la línea base

Type: grilling
Status: open
Blocked by: 02

## Question

Con las opciones reales que traiga la investigación (cuota, coste, familia, formato de salida):

- ¿Qué modelo de Azure se elige, y por qué ese frente a los demás candidatos?
- **Protocolo de la línea base nueva**: mismo prompt v2, mismas 50 preguntas, mismo juez y rúbrica `j1`,
  temperatura/razonamiento fijados. Qué se puede igualar y qué no (un modelo de razonamiento cambia el
  coste y la latencia).
- ¿Cómo se cuenta una respuesta **bloqueada por el filtro de contenido** frente a una abstención?
- ¿Cuántas pasadas? Con una sola, la latencia ya demostró variar de 1,4 s a 21,2 s entre días.
- Cómo se presenta el "antes" (Gemini) y el "después" sin que parezca que uno es mejor por azar con n
  pequeño.

Entrevista con `/grilling`. Resultado: la decisión y el protocolo escritos, que consumirá el ticket de
implementación del cliente (todavía en la niebla).
