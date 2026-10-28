# Diseño del experimento de retrieval antes/después

Type: grilling
Status: resolved (28-oct-2026)
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

## Answer

Decidido con Santiago el 28-oct-2026, **antes de ver ningún dato de Azure**.

### Configuraciones (5), sobre las mismas 28 preguntas factuales y cruzadas
| | Configuración | Para qué |
| --- | --- | --- |
| A | **Local denso** (BGE-M3, NumPy, sin ruta jerárquica) | Línea base: el 89,3 % @10 publicado |
| B | **Azure vectorial** (HNSW) | El efecto de migrar el índice |
| C | **Azure vectorial exacto** (`exhaustive=True`) | Control de cordura y lo que cuesta aproximar con HNSW |
| D | **BM25 solo en Azure** | Separar lo que aporta el texto de lo que aporta el vector, y control del híbrido |
| E | **Azure híbrido** (BM25 + vectorial, RRF) | El horizonte pedido |

Fuera, por decisión: el **ranker semántico** (exige Basic; ticket de presupuesto) y las **variantes de peso
del vector** (el híbrido se prueba una sola vez, con `k` de RRF fijo en 60 y el peso por defecto). El
analizador de español (`es.microsoft` o `es.lucene`) se elige en la implementación **antes de medir** y no
se cambia mirando resultados.

### Qué se mide
- **Recall@5, @10 y @20**, a nivel **artículo** (el que predice si el generador tiene el texto) y a nivel
  apartado. **Titular: recall@10 a nivel artículo**, el que ya publica el README.
- Siempre la **lista de preguntas que cambian de estado** entre configuraciones, no solo el porcentaje.

### Regla de "mejora", fijada de antemano
- **Mejora consistente:** al menos **+2 preguntas netas en @10** (artículo) **y sin pérdida neta en @5 ni
  en @20**, frente a la línea base A.
- **Empeora:** lo simétrico. **Todo lo demás: "sin diferencia demostrable".**
- **El informe declara que con n = 28 la significación estadística no es alcanzable en @10.** La línea
  base falla 3 preguntas en @10: aunque Azure las arreglara las tres sin romper ninguna, la prueba exacta
  por pares daría p ≈ 0,25. En @5 (6 fallos) el mejor caso posible es p ≈ 0,03.
- Margen de mejora de la línea base a nivel artículo: @5 = 6 preguntas (e-021, e-023, e-024, e-025,
  e-026, e-047), @10 = 3 (e-021, e-024, e-026), @20 = 2 (e-021, e-024).

### Qué retriever queda para v1
**Azure híbrido salvo que empeore** (por la regla de arriba, frente a A). Si el híbrido empeora y el
vectorial no, el vectorial. Si ambos empeoran, se documenta y se decide entonces. La migración es un
objetivo del proyecto: el informe dirá "migré; la calidad no mejora" y no "mejoré" si el resultado es nulo.

### Lo que añado yo (derivado, no decidido)
- **Control de cordura:** C debe **reproducir a A** (mismas 25/28 en @10 a nivel artículo). Una diferencia
  de más de una pregunta en cualquier k indica un fallo de la migración (normalización, métrica,
  vectores) que se arregla **antes** de interpretar nada.
- **Reproducibilidad:** cada configuración se guarda con `--guardar` e incluye el **ranking top-20 de cada
  pregunta** (identificadores), no solo aciertos y fallos, para rehacer la tabla sin pagar de nuevo. Una
  copia pequeña se versiona en el repo.

### Lo esperable (no un resultado)
Las tres preguntas estructurales (e-021, e-024, e-026) piden artículos transversales sin vocabulario
propio y es probable que sigan fallando en todas las configuraciones. Se reportará lo que salga.
