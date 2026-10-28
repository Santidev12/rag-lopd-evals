# Generador en Azure: qué modelo y cómo se rehace la línea base

Type: grilling
Status: resolved (28-oct-2026)
Blocked by: 02, 11, 10

## Question

Con las opciones reales que traiga la investigación (cuota, coste, familia, formato de salida):

- ¿Qué modelo de Azure se elige, y por qué ese frente a los demás candidatos?
- **Protocolo de la línea base nueva**: mismo prompt v2, mismas 50 preguntas, mismo juez y rúbrica `j1`,
  temperatura/razonamiento fijados. Qué se puede igualar y qué no (un modelo de razonamiento cambia el
  coste y la latencia).
- ¿Cómo se cuenta una respuesta **bloqueada por el filtro de contenido**? El ticket de filtros propone un
  estado nuevo `BLOQUEADO` (hoy acabaría como `SALIDA_INVALIDA`): decidir si se adopta y cómo entra en
  las tasas de sobre-respuesta y abstención indebida.
- Confirmado el 27-oct-2026: **solo `gpt-4.1-mini` acepta `temperature` 0** (los `gpt-5*` no), y los
  cuatro candidatos admiten JSON estricto. Precios de entrada/salida por millón: 0,40/1,60 (`gpt-4.1-mini`),
  0,25/2,00, 0,75/4,50 y 0,20/1,25. Los `gpt-5*` añaden tokens de razonamiento.
- Esto estrecha mucho la elección: para repetir pasadas, `gpt-4.1-mini` es el candidato natural. Queda
  decidir si se acepta o si el trabajo de reproducibilidad justifica otro, y el despliegue (Global
  Standard frente a Data Zone UE, ≈ 10 % más).
- **Ya decidido en el ticket de presupuesto:** el modelo se despliega en **Data Zone UE** y con una cuota
  baja de TPM. Falta verificar el precio de `gpt-4.1-mini` en Data Zone y su disponibilidad en la región.
- ¿Cuántas pasadas? Con una sola, la latencia ya demostró variar de 1,4 s a 21,2 s entre días.
- Cómo se presenta el "antes" (Gemini) y el "después" sin que parezca que uno es mejor por azar con n
  pequeño.

Entrevista con `/grilling`. Resultado: la decisión y el protocolo escritos, que consumirá el ticket de
implementación del cliente (todavía en la niebla).

## Answer

Decidido con Santiago el 28-oct-2026.

### Decisiones
- **Modelo: `gpt-4.1-mini`**, desplegado en **Data Zone UE** y con cuota baja de TPM (ticket de
  presupuesto). Razones: es el **único de los cuatro candidatos que acepta `temperature` 0** (pasadas
  repetibles), **no razona** (coste y latencia se comparan limpio con Gemini) y es de otra familia que el
  juez (DeepSeek). Descartados `gpt-5-mini`, `gpt-5.4-mini` y `gpt-5.4-nano`: razonamiento, sin
  `temperature` 0 y tokens de razonamiento que habría que medir; de los dos últimos, además, no está
  confirmado si piden registro de acceso.
- **Protocolo: cambia solo el modelo.** Mismo prompt v2 sin tocar, mismas 50 preguntas, `temperature` 0,
  **JSON simple sin esquema** (el equivalente al `responseMimeType` de Gemini; la salida estructurada
  estricta queda como variante posterior solo si la línea base muestra fallos de formato), mismo juez
  (DeepSeek-V4-Flash-0731) y misma rúbrica `j1` sin retocar.
- **Misma recuperación que el "antes"** *(consecuencia del principio de una sola variable, la añado yo)*:
  la línea base de generación usa el **recuperador denso local actual** con k = 10, para que solo cambie
  el generador. El efecto de Azure AI Search se mide aparte en su propio ticket, y el pipeline completo
  nuevo se reporta como una tercera columna al final.
- **Tres pasadas.** ≈ 0,12 $ cada una más el juez. Permiten ver qué preguntas son estables y reportar la
  latencia con 150 consultas.
- **Respuesta bloqueada por el filtro: estado nuevo `BLOQUEADO`**, que **cuenta como callarse** (entra
  en la abstención indebida o en lo correcto según el tipo de pregunta, igual que cualquier abstención)
  y se **desglosa**: el resumen dice cuántas abstenciones fueron por el filtro. Así las tasas titulares
  siguen siendo comparables con Gemini. El juez no las juzga (no hay respuesta que juzgar).

### Cómo se presenta el "antes y después"
Siguiendo el principio de honestidad con los números de las Notes del mapa *(derivado, no una decisión
nueva)*: tasas con intervalo de Wilson, la lista de preguntas que **cambian de estado** entre Gemini y
Azure (no solo el porcentaje), y la conclusión por defecto es "sin diferencia demostrable" cuando los
intervalos se solapan, que con n = 50 será lo habitual. El "antes" es Gemini 3.5 Flash-Lite, prompt v2,
22-oct-2026.

### Riesgos a tratar al implementar
- **La cuota baja de TPM ralentiza las pasadas.** Cada consulta usa ≈ 5.700 tokens: con 20.000 TPM caben
  ≈ 3 consultas por minuto, y una pasada de 50 tardaría ≈ 15 minutos, con reintentos por 429 que
  **inflarían la latencia medida** *(cálculo propio, sin verificar cómo cuenta Azure la cuota)*. Hay que
  subir la cuota temporalmente para las pasadas, o medir la latencia sin estrangular.
- **Sin verificar:** el precio de `gpt-4.1-mini` en Data Zone UE y su disponibilidad en la región elegida.
  Se comprueban al crear la cuenta.
