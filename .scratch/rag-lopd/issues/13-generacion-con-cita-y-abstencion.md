# Generación con cita y política de abstención

Type: task
Status: v2 medido y adoptado por defecto; abiertos el juez de contenido y un segundo modelo

## Question

El ticket 12 midió que el score de recuperación no separa las preguntas con respuesta de las que
no la tienen (AUC 0,83) y dejó la decisión: la política tiene que mirar el contenido, y eso solo
se mide con un generador en el bucle — instrucción de responder solo con el contexto, salida
estructurada con vía de abstención y cita obligatoria como control.

Alcance:

- Un contrato `ModeloDeLenguaje` (texto en, texto y tokens fuera), igual que `Recuperador`, para
  medir varios modelos con el mismo prompt y el mismo validador.
- El primer modelo: Gemini (la clave ya existe; ver decisión de abajo).
- La política: prompt versionado + JSON `{sin_respuesta, respuesta, citas}` + validación de las
  citas contra los artículos que de verdad se le dieron al modelo.
- Una pasada sobre las 50 preguntas aceptadas que mida **sobre-respuesta** y **abstención
  indebida** (con intervalo de confianza), guardando cada observación para no repetir llamadas.

Fuera de alcance, para el ticket del harness: si el *contenido* de una respuesta es correcto
(exige un juez), y la comparación entre varios modelos en el README.

## Answer

**Código entregado el 07-oct-2026; primera pasada real el 12-oct-2026** (Gemini 3.5 Flash-Lite,
prompt v1, k = 10, 50 preguntas, `data/runs/gemini-3.5-flash-lite-promptv1-k10-20261012-212811.jsonl`).

### Decisión: modelo generador

Gemini 3.5 Flash-Lite por defecto ($0,30 / $2,50 por millón de tokens, de la página oficial de
precios de Google). Con ~5.000 tokens de entrada y ~300 de salida por consulta son ~0,002 $ por
consulta y ~0,11 $ por pasada de 50 preguntas: el coste no es el factor que decide (incluso
Sonnet 5.5 serían ~0,65 $ por pasada); lo que decide es cuánto sobre-responde cada modelo, y eso
se mide, no se supone. Por eso el contrato `ModeloDeLenguaje`: Claude Haiku 4.5 y DeepSeek-V4-Flash
(DeepInfra) son los comparables previstos y cada uno es un fichero nuevo con su tarifa. La
calidad en español jurídico de ninguno está verificada.

### Entregado

- `generacion/modelo.py` — `ModeloDeLenguaje`, `Contexto`, `Respuesta` con cuatro `Estado`
  (`responde`, `abstiene`, `sin_cita_valida`, `salida_invalida`), `Uso` y `Tarifa`.
- `generacion/contexto.py` — reconstruye el **artículo entero** a partir de las unidades
  recuperadas (small-to-big, ADR 0001), sin repetir artículos y en orden de recuperación.
- `generacion/prompt.py` — la política en lenguaje natural, versionada (`VERSION = "v1"`).
- `generacion/responder.py` — ejecuta la política: `sin_respuesta` explícito; si responde, cada
  cita se valida contra el contexto entregado (las inventadas se descartan y se registran; sin
  ninguna válida, cuenta como abstención); si no hay JSON, `salida_invalida` (no se disfraza).
- `generacion/gemini.py` — cliente REST de `generateContent` con reintentos (429/5xx, respeta
  `Retry-After`) y coste real: los tokens de razonamiento se cuentan como salida (total − entrada).
- `generacion/evaluacion.py` — `Observacion` (guardable), `resumir` con IC de Wilson al 95 %.
  Además de las dos métricas centrales separa **contexto completo** (¿llegó el artículo al
  modelo?) de **cita cubre fuente**, para distinguir fallos de retrieval de fallos de generación.
- `rag-lopd generacion preguntar | evaluar | resumir`. `evaluar` guarda cada observación en
  `data/runs/` según termina; `resumir` recalcula las cifras de un fichero guardado sin llamar a
  nadie.
- 36 tests nuevos sin red, ruff y mypy limpios.
- `indice_denso.ruta_indice` sustituye al helper privado de `retrieval/cli.py`: un solo sitio
  para quien construye el índice y quien lo consume.

### Decisiones y salvedades

- **`generateContent`, no la Interactions API.** Google marca la segunda como recomendada para
  proyectos nuevos y `generateContent` como *legacy* pero plenamente soportada, sin fecha de
  retirada. Para una llamada sin estado el contrato de `generateContent` está más fijado; si se
  retira, el cambio queda dentro de `gemini.py`.
- **El esquema del JSON va en el prompt, no en `responseSchema`**, y lo valida pydantic: no
  depende del subconjunto de JSON Schema que acepte cada versión de la API ni de que otros
  modelos lo soporten igual.
- **El prompt v1 no se retoca mirando los resultados.** Ajustarlo a las 50 preguntas las
  contaminaría. La primera pasada se publica tal cual con su versión; los cambios posteriores son
  `v2`, `v3`... y quedan registrados con el motivo.
- **Las `temporal` pueden inflar la abstención indebida.** El corpus indexado solo lleva las
  unidades vigentes; si una pregunta temporal pide el texto de una versión antigua, el sistema
  no puede contestarla desde el índice y callar sería lo correcto. Se mira en los resultados
  antes de dar la cifra por buena.
- **k = 10 unidades pueden ser muchos artículos en el contexto.** Más ruido puede dificultar
  abstenerse; el coste real de tokens saldrá de la primera pasada, no de la estimación.

### Primera pasada: cifras

| Métrica | Valor (IC 95 % de Wilson) |
| --- | --- |
| Sobre-respuesta (sin respuesta y contesta) | 2/17 = 11,8 % (3 %–34 %) |
| Abstención indebida (con respuesta y calla) | 5/33 = 15,2 % (7 %–31 %) |
| Contexto completo (todos los artículos fuente llegaron al modelo) | 30/33 = 90,9 % (76 %–97 %) |
| Cita cubre la fuente | 24/28 = 85,7 % (69 %–94 %) |
| Salida inválida | 0/50 |
| Tokens | 240.854 entrada · 5.174 salida · 0,0852 $ en total |

Por tipo: factual 15/15 responde, cruzada 9/12, temporal 4/6, fuera de corpus 10/10 se abstiene,
trampa 5/7 se abstiene. Coste real: **≈ 0,0017 $ por consulta** (~4.800 tokens de entrada y ~100
de salida; la estimación de salida de ~300 era alta).

**Frente al umbral de score del ticket 12:** la política mirando el contenido iguala al mejor
punto de esa tabla en sobre-respuesta (~12 %, el umbral 0,60 daba 2/17) pero bajando la
abstención indebida del 36 % al 15 %. Los IC son anchos (n = 17 y n = 33): la diferencia de
abstención indebida es clara; la de sobre-respuesta con otros modelos no se puede afirmar todavía.

*Nota del 16-oct-2026.* Estas cifras son con el eval set de entonces. e-047 estaba mal etiquetada
como trampa (el RGPD, art. 57.3, sí responde: es gratuito) y se reconvirtió en factual. Recalculadas
con `resumir` sobre la misma pasada: sobre-respuesta 1/16 = 6,2 %, abstención indebida 5/34 =
14,7 %, contexto completo 31/34, cita cubre la fuente 25/29. Detalle en el
[ticket 14](14-el-juez.md). La mejora de sobre-respuesta es una corrección de etiqueta, no del
sistema.

### Diagnóstico a mano de los 11 casos problemáticos

**Abstención indebida (5):**

- **e-021, e-024: abstención correcta dado el contexto.** Son dos de las tres preguntas que el
  retrieval no engancha (ticket 11): el artículo fuente nunca llegó al modelo. Callar es lo que
  debe hacer; el fallo es de recuperación, no de generación. Por eso se mide el contexto completo
  aparte: 30/33 llegan, y de las 3 que no llegan, 2 se callan y 1 (e-026) responde mal.
- **e-028, e-032 (temporales): fallo estructural del contexto, no del modelo.** Confirmado en los
  datos: `data/processed/*.unidades.jsonl` no contiene ni una sola unidad con `vigente_hasta`
  (0 de 389 y 0 de 339), así que la redacción anterior del art. 67.2 (doce meses) no existe en el
  índice; y `vigente_desde` (2021-06-16 para el art. 2.5, 2023-05-10 para el 67.2) es un campo de
  la unidad que `generacion/prompt.py` no pasa al modelo. Para e-028 la mitad "cuánto duraban
  antes" es incontestable desde el índice; para e-032 la fecha estaba disponible y no se le dio.
- **e-027 (cruzada): fallo real de generación.** Ambos artículos fuente (lopdgdd:art-67 y
  art-78) estaban en el contexto y el modelo se abstuvo. Es la pregunta marcada como
  "deliberadamente rebuscada" en el eval set. Un caso aislado, no se puede generalizar.

**Sobre-respuesta (2):** e-046 y e-047, dos trampas que el modelo contestó. Son preguntas de
formulación tentativa donde el contexto contiene algo plausible y parcialmente defendible; el
score de recuperación tampoco las separaba (e-046 tenía 0,650, de los más altos). Sin juez no se
puede decir cuánto de lo contestado es erróneo.

**Cita que no cubre la fuente (4):** e-010, e-018, e-025, e-026. En e-018 y e-025 el contenido es
correcto y la cita incompleta (cita un artículo de los esperados, no todos); en e-010 y e-026 hay
errores de contenido que las métricas actuales **no pueden ver**: ambas cuentan como "responde".

### Lo que esta pasada NO mide

- **Si el contenido de una respuesta es correcto.** e-010 y e-026 lo demuestran: una respuesta que
  "responde" y cita puede estar mal. Necesita un juez (ticket del harness).
- **Un solo modelo, un solo prompt.** Con n = 17 y n = 33 los IC son anchos; la tabla comparativa
  del README exige al menos un segundo modelo.
- Las temporales mezclan dos problemas distintos (versión histórica ausente / fecha no entregada)
  que hay que separar antes de dar su cifra como límite del modelo.

### Prompt v2: vigencia y redacciones anteriores (código 12-oct-2026, medido y adoptado 13-oct-2026)

Motivo: las dos temporales que fallaban (e-028, e-032) fallaban porque la información no llegaba
al modelo, no por la política. La fuente de verdad (`data/processed/<norma>.json`) sí conserva las
redacciones antiguas (53 unidades en 15 artículos de la LOPDGDD; el RGPD no tiene ninguna), solo
que el índice y el contexto trabajaban con las vigentes.

- **La recuperación no cambia.** Sigue indexando solo lo vigente: una redacción derogada no puede
  salir como resultado de búsqueda. Las anteriores se añaden **después**, al armar el contexto
  del artículo recuperado (`retrieval.corpus.cargar_unidades_con_historia`).
- `Contexto` separa `texto` (siempre la vigente), `vigente_desde` y `anteriores` (ordenadas de
  más antigua a más reciente). Nunca se mezclan.
- v2 = v1 + una regla (la 6) + formato del contexto: "Redacción vigente desde AAAA-MM-DD" y, si
  existe, "Redacción anterior, vigente desde ... hasta ...". La regla pide responder con lo
  vigente salvo que la pregunta sea sobre una etapa anterior o sobre el cambio, indicar el
  periodo y no dar más fechas que las del contexto. Las reglas 1–5 y el formato JSON no se tocan.
- **v1 sigue reproducible**: `--prompt v1` (el valor por defecto hasta que v2 se mida) genera
  byte a byte el mismo sistema que la primera pasada, y su mensaje de usuario es idéntico aunque
  se cargue la historia (comprobado sobre todos los artículos del corpus).
- Coste esperado: 15 de ~240 artículos llevan texto extra; ~150 caracteres de media por artículo.

#### Resultado de v2 (Gemini 3.5 Flash-Lite, k = 10, `data/runs/...promptv2-k10-20261013-001311.jsonl`)

| Métrica | v1 | v2 |
| --- | --- | --- |
| Sobre-respuesta | 2/17 = 11,8 % (3 %–34 %) | 2/17 = 11,8 % (3 %–34 %) |
| Abstención indebida | 5/33 = 15,2 % (7 %–31 %) | 3/33 = 9,1 % (3 %–24 %) |
| Contexto completo | 30/33 | 30/33 |
| Cita cubre la fuente | 24/28 = 85,7 % | 26/30 = 86,7 % (70 %–95 %) |
| Temporal | 4/6 | 6/6 (IC 61 %–100 %) |
| Tokens de entrada por consulta | ~4.800 | ~5.600 |
| Coste por consulta | ≈ 0,0017 $ | ≈ 0,0020 $ (0,0976 $ la pasada) |

*Nota del 16-oct-2026.* Con e-047 corregida (ver arriba y el [ticket 14](14-el-juez.md)), v2 da
sobre-respuesta 1/16 = 6,2 % (1 %–28 %), abstención indebida 3/34 = 8,8 % (3 %–23 %), contexto
completo 31/34 y cita cubre la fuente 27/31 = 87,1 %; v1, 1/16 y 5/34 = 14,7 %. La tabla de arriba
queda como se midió. Contenido según el juez ([ticket 14](14-el-juez.md)): v1 26/34 = 76,5 %, v2
27/34 = 79,4 %; la diferencia está dentro del ruido y v2 sí arregla las dos temporales.

Comparación pregunta a pregunta (mismos contextos en las 50, comprobado):

- **Cambian de estado exactamente dos: e-028 y e-032, de abstiene a responde.** Las otras 48
  conservan su estado, incluidas las dos sobre-respuestas (e-046, e-047) y las tres abstenciones
  que siguen (e-021, e-024, e-027).
- **Las dos respuestas nuevas son correctas frente a la esperada.** e-028: "dieciocho meses;
  antes, entre el 7-dic-2018 y el 10-may-2023, doce meses". e-032: el tratamiento del Ministerio
  Fiscal y de la Oficina Fiscal, desde el 16-jun-2021, citando el art. 2.
- **31 de las 50 preguntas tienen un artículo con redacciones anteriores en el contexto** y
  ninguna otra cambia de estado: el riesgo de regresión de estado no se materializó.
- **Una filtración de redacción antigua en una pregunta no temporal: e-020** (cruzada) añade
  "(o doce meses según la redacción anterior vigente desde ... hasta ...)". Está bien etiquetada
  y no es incorrecta, pero nadie preguntó por ella: la regla 6 no basta para que se calle lo que
  no se pide. No se retoca el prompt por una sola observación (v3, si acaso, con más evidencia).
- Las citas de e-007, e-011 y e-023 pierden una cita sobrante (de 2-4 a 1-3): menos ruido.
- e-015 trae dos citas mal formadas (`rgpd:art-83-4`) que el validador descarta; la cita buena
  (`rgpd:art-83`) se mantiene. Sin relación con la historia; se vigila.
- 22 respuestas cambian de redacción con el mismo contexto: ruido de la instrucción nueva. Que
  una respuesta cambie de texto no es mejora ni empeoramiento: sin juez no se puede medir.

Salvedades al publicar:

- **La bajada de abstención indebida (15,2 % → 9,1 %) es exactamente las dos temporales para las
  que se diseñó v2.** No es evidencia de que v2 generalice; sí lo es de que no empeora el resto.
- **Coste: +17 % de tokens de entrada, no los ~150 caracteres por artículo estimados.** Esa media
  era sobre todos los artículos; las preguntas recuperan artículos con historia mucho más de lo
  que les toca por azar (31 de 50), y esos son de los más largos (procedimiento y sanciones).
- Un modelo, un prompt, n pequeño: los IC se solapan por completo.

Salvedades de diseño que ya estaban escritas antes de medir:

- **Las seis temporales ya no son una medida limpia de v2**: v2 se diseñó mirando e-028 y e-032.
  Lo que sí es limpio es el resto (44 preguntas): v2 no debe empeorarlas.
- **Riesgo de regresión**: un contexto con dos redacciones puede hacer que el modelo conteste con
  la antigua una pregunta no temporal sobre esos 15 artículos. Se mira a mano en la pasada.
- **Preguntas sin respuesta que tocan artículos con historia**: más texto y fechas podrían
  empujar a sobre-responder. Es la métrica que más importa y se compara con v1 caso a caso.

## Pendiente

1. ~~Primera pasada.~~ Hecho (arriba).
2. ~~Diagnóstico a mano.~~ Hecho (arriba).
3. ~~Medir v2~~ Hecho: no empeora nada, arregla las dos temporales; **v2 es el valor por defecto**.
4. Siguiente: harness con juez, segundo modelo para la tabla del README, latencia p50/p95.
5. El prompt v1 sigue intacto; v2 es la única versión nueva y queda registrada arriba.
