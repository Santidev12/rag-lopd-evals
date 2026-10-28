# Diseño del experimento de retrieval antes/después

Type: grilling
Status: open
Blocked by: 01, 11, 10

## Question

Con n = 28 preguntas evaluables y el recall@10 actual en 89,3 % (3 fallos, estructurales), ¿qué
experimento puede decir algo y cuál solo produciría ruido?

- **Configuraciones a comparar**: línea base local (denso con NumPy), Azure vectorial, Azure híbrido
  (BM25 + vectorial con RRF, con `k` fijo en 60). El **ranker semántico queda fuera** (decidido en el
  ticket de presupuesto: exige Basic y supera el tope; AI Search se usa en Free). ¿Se prueba el **peso del vector** (< 1 favorece el texto)
  como única palanca ajustable? ¿Y BM25 solo en Azure como control?
- **Qué se mide**: recall@5/10/20 a nivel artículo (el que predice si el generador tiene el texto) y a
  nivel apartado; qué preguntas cambian de estado, no solo el porcentaje.
- **Criterio de "mejora"**: con 28 preguntas, ¿cuántas tienen que cambiar para que no sea ruido? Fijar de
  antemano qué diferencia cuenta, para no interpretar los datos después.
- **Qué se hace con un resultado nulo.** Las 3 preguntas que fallan piden artículos transversales sin
  vocabulario propio: lo esperable es que el híbrido no las arregle. ¿Cómo se cuenta eso?
- **Reproducibilidad**: qué se guarda para poder rehacer la tabla sin volver a pagar.

Entrevista con `/grilling`. Resultado: el diseño escrito, que consumirá el ticket de implementación.
