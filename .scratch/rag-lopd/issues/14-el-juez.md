# El juez: ¿es correcto el contenido de la respuesta?

Type: task
Status: cerrado (16-oct-2026): pasadas v1 y v2 juzgadas con el eval set corregido, juez calibrado; quedan decisiones menores de Santiago (abajo)

## Question

Las métricas del ticket 13 miden comportamiento (contestar, callar, citar) pero no pueden ver si una
respuesta que "responde" y cita dice algo equivocado: e-010 y e-026 lo demostraron. Sin una medida
de corrección, la fila "Exactitud de respuesta" del README no se puede rellenar y las cifras de
generación no son publicables.

Alcance: un juez que lea cada respuesta contra la de referencia del eval set y la clasifique, un
modo de comprobar si el juez es fiable, y las métricas de exactitud con intervalo de confianza.

## Answer

### Decisiones

- **El juez es DeepSeek-V4-Flash vía DeepInfra, fijado a la versión `-0731`** (0,06 / 0,18 $ por
  millón de tokens, de la página del modelo en DeepInfra, 13-oct-2026). Otra familia que el
  generador (Gemini) para que no se favorezca a sí mismo, y la clave ya existe (embeddings). El
  alias sin fecha (`DeepSeek-V4-Flash`, 0,09 $ de entrada) se descarta: apunta a lo que DeepInfra
  decida y un juez que cambia sin avisar invalida la comparación entre pasadas. Haiku 4.5
  (más fiable, pero exige otra clave) y Gemini (sesgo de autopreferencia) quedaron como
  alternativas si este no calibra bien.
- **Juzga contra la referencia, no contra su conocimiento del derecho.** Recibe la pregunta, la
  respuesta de referencia (revisada por una persona), las notas del revisor si las hay, el texto
  vigente de las unidades de la fuente y la respuesta del sistema.
- **Tres niveles: `correcta`, `parcial`, `incorrecta`** (más `invalido` cuando el juez no devuelve
  el JSON pedido, que es un fallo del instrumento y no se disfraza). Dos casos en la misma
  rúbrica: A (hay respuesta en la norma) y B (no la hay y el sistema contestó: ¿afirmó algo sin
  base?).
- **El `motivo` va antes del `veredicto` en el JSON**: se le pide razonar antes de decidir, y
  permite auditar cada juicio a mano.
- **No juzga las citas** (se miden aparte) y **solo juzga lo que el sistema contestó**: no hay
  nada que juzgar en una abstención.
- **Rúbrica versionada (`j1`)** como el prompt del generador: no se retoca mirando resultados.
- **No se manda `response_format` ni parámetros de razonamiento** a DeepInfra: no están
  verificados para este modelo y un parámetro no soportado tumba toda la pasada con un 400. El
  JSON lo pide el prompt y lo valida pydantic. Si el modelo razona de forma incrustada
  (`<think>`), se quita; los tokens de razonamiento, si los hay, ya vienen en `completion_tokens`.
- Los reintentos ante 429/5xx se extrajeron de `gemini.py` a `generacion/reintentos.py` y los
  usan los dos clientes.

### Entregado

- `generacion/deepinfra.py` — `DeepInfraModelo`, otra implementación de `ModeloDeLenguaje`
  (con tarifas fijadas por versión).
- `generacion/juez.py` — rúbrica, `juzgar`, `juzgar_pasada` (reanudable: lo ya juzgado no se
  paga otra vez; un `invalido` sí se repite), `resumir_juicios` y `calibrar`.
- `rag-lopd generacion juzgar <pasada.jsonl>` — guarda los juicios junto a la pasada
  (`<pasada>.juez-<modelo>-j1.jsonl`), imprime las cifras y lista cada no-correcta con el motivo.
- `rag-lopd generacion calibrar <juicios.jsonl> <etiquetas.jsonl>...` — acuerdo exacto, acuerdo
  correcta/no-correcta, kappa de Cohen, matriz y cada discrepancia. No llama a nadie. Acepta varios
  ficheros de etiquetas y los últimos pisan a los primeros por pregunta.
- `eval/etiquetas-v2-preliminares.jsonl` — 32 etiquetas manuales de las respuestas contestadas
  de la pasada v2 (ver más abajo).
- 36 tests nuevos sin red (90 en total), ruff y mypy limpios. Tras corregir e-047, 6 más (96):
  - `evaluacion.realinear`: una observación guardada lleva copiados el tipo y la fuente de la
    pregunta *del día de la pasada*; `resumir` y `juzgar` los reponen ahora con los del eval set
    actual (opción `--eval-set`) y dicen qué preguntas cambiaron. Sin esto, corregir una pregunta
    obligaba a repetir una pasada de pago por algo que no cambia lo que el modelo contestó.
  - `juzgar_pasada` repite un juicio hecho con otro tipo de pregunta del que tiene ahora (e-047 se
    juzgó como trampa). Si cambia solo el texto de la referencia no lo detecta: hay que borrar el
    fichero de juicios.

### Métricas

- **Exactitud** (la de la fila del README): de las 33 preguntas con respuesta, cuántas se
  contestaron **correctamente**. Callar cuenta como fallo: es lo que vive quien pregunta.
- **Exactitud de las contestadas**: lo mismo sin contar lo que se calla; mide el contenido.
- Parciales e incorrectas por separado, y exactitud por tipo.
- **Sobre-respuesta grave**: de las sin respuesta que se contestaron, cuántas afirman algo que la
  norma no sostiene.

### Calibración: cómo se sabrá si el juez sirve

Un juez es un instrumento y se calibra antes de fiarse. Antes de ver ningún veredicto del juez se
etiquetaron a mano las 32 respuestas contestadas de la pasada v2 (28 correctas, 3 parciales, 1
incorrecta). **Las etiquetas las ha puesto Claude, no una persona**: son una referencia
preliminar y las discrepancias, junto a las siete etiquetas dudosas (e-001, e-016, e-019, e-023,
e-026, e-046, e-047, marcadas como "borderline" o discutibles en su nota), las tiene que cerrar
Santiago. El resultado de `calibrar` solo vale lo que valgan esas etiquetas.

Con 28 de 32 en "correcta", el acuerdo bruto engaña (un juez que dijera siempre "correcta"
acertaría el 87,5 %): por eso se reporta el kappa y el acuerdo en las cuatro no-correctas.

### Hallazgo sobre el eval set: e-047 (decidido el 16-oct-2026)

**e-047** (¿qué tasa debe abonar un ciudadano para reclamar ante la AEPD?) espera abstención
("el corpus no prevé ninguna tasa"), pero el RGPD, art. 57.3, dice que el desempeño de las
funciones de la autoridad de control, "incluida la presentación de reclamaciones, será gratuito
para el interesado": el sistema contestó citando eso y es fiel a la norma. Si se confirma, la
referencia debería cambiar o la pregunta dejar de ser una trampa. Cambiar el eval set es decisión
suya y obliga a re-medir la sobre-respuesta (hoy 2/17).

**Decisión de Santiago: reconvertir e-047 en pregunta `factual`.** Referencia nueva: «Ninguna: el
desempeño de las funciones de la autoridad de control, entre ellas atender la reclamación, es
gratuito para el interesado», fuente `rgpd:art-57.3`. La nota de la pregunta documenta la
corrección y que el 57.4 permite una tasa razonable en solicitudes manifiestamente infundadas o
excesivas (no se exige mencionarlo).

Dos precisiones a lo que escribí arriba: (1) la frase «incluida la presentación de reclamaciones»
**no es literal del 57.3** (el texto dice «el desempeño de las funciones de cada autoridad de
control será gratuito para el interesado y, en su caso, para el delegado de protección de
datos»): la añadió el modelo, y es una paráfrasis defendible, no una cita; (2) la pregunta sigue
cumpliendo las reglas del eval set (`eval validar`: 50 preguntas, 25 fuentes existentes).

Efecto, recalculado con `resumir` sobre las mismas pasadas guardadas (sin repetir ninguna llamada):

| | Antes (e-047 trampa) | Ahora (e-047 factual) |
| --- | --- | --- |
| Reparto | 15 · 12 · 6 · 10 · 7 | 16 · 12 · 6 · 10 · 6 |
| Sobre-respuesta v2 | 2/17 = 11,8 % (3 %–34 %) | 1/16 = 6,2 % (1 %–28 %) |
| Abstención indebida v2 | 3/33 = 9,1 % (3 %–24 %) | 3/34 = 8,8 % (3 %–23 %) |
| Abstención indebida v1 | 5/33 = 15,2 % | 5/34 = 14,7 % |
| Contexto completo (ambas) | 30/33 | 31/34 = 91,2 % |
| Cita cubre la fuente v2 / v1 | 26/30 / 24/28 | 27/31 = 87,1 % / 25/29 = 86,2 % |

**La bajada de sobre-respuesta no es una mejora del sistema**: es una etiqueta errónea que deja de
contar en su contra, y el README lo dice así. La sobre-respuesta que queda es e-046 (el sistema
cita el art. 30, «por escrito, también electrónico», sin inventar formato), que Santiago da por
correcta: la sobre-respuesta grave de v2 pasa a ser 0/1 con el juicio actual. La constante
`REPARTO_OBJETIVO` (15/7) no se ha tocado: `eval stats` muestra la desviación -1/+1 a propósito.

### Primera pasada juzgada: la pasada v2 (`...promptv2-k10-20261013-001311.jsonl`)

*(Con el eval set anterior a corregir e-047: 33 respondibles, 17 sin respuesta. Se recalcula, ver
«Pendiente».)*

| Métrica | Valor (IC 95 % de Wilson) |
| --- | --- |
| **Exactitud** (de las 33 con respuesta, contestadas correctamente) | 26/33 = 78,8 % (62 %–89 %) |
| Exactitud de las contestadas (el contenido) | 26/30 = 86,7 % (70 %–95 %) |
| Parciales / incorrectas (de las contestadas) | 3 / 1 |
| Por tipo: factual / cruzada / temporal | 14/15 · 6/12 · 6/6 |
| Sobre-respuesta grave | 1/2 (9 %–91 %) |
| Coste del juez | 35.120 tokens de entrada, 1.902 de salida ≈ 0,0025 $ |

Las 6 temporales siguen siendo la medida contaminada de v2 (ticket 13).

### Calibración del juez contra mis etiquetas preliminares (32 respuestas, antes de cerrar nada)

- **Acuerdo exacto 29/32 = 90,6 % (76 %–97 %); kappa de Cohen 0,63**; el acuerdo en
  correcta/no correcta es igual, 29/32.
- **Las 25 etiquetas no marcadas como dudosas: 25/25 de acuerdo**, incluida la única incorrecta
  (e-010). Las tres discrepancias están **todas** entre las siete que yo había marcado como
  borderline antes de ver el juez.
- Las 3 discrepancias:
  - **e-019** (yo: correcta; juez: parcial). La referencia incluye "prescribe a los tres años" y
    el juez la trata como esencial; la pregunta solo pide la multa y la clasificación. Es la
    referencia la que pide más de lo que pregunta la pregunta. En e-001 y e-016 el juez sí
    dejó pasar la omisión de un dato secundario: no es incoherencia gratuita, pero es
    sensibilidad a lo que la referencia pone, no a lo que la pregunta exige.
  - **e-046** (yo: parcial; juez: correcta). El juez acepta que la respuesta se limita a lo que
    dice el art. 30 y no afirma ningún formato concreto. Concedo que es defendible: la respuesta
    contiene lo mismo que la propia referencia afirma ("exige forma escrita, incluida la
    electrónica") menos la aclaración de que no hay formato concreto.
  - **e-047** (yo: correcta; juez: incorrecta). El juez dice "contradice la referencia", y es
    verdad: la referencia espera abstención. **El juez no se equivoca: reproduce una referencia
    que el art. 57.3 del RGPD contradice.** En el caso B el juez no recibe texto de la norma (no
    hay fuente) y solo puede fiarse de la referencia. Consecuencia: la "sobre-respuesta grave"
    (1/2) es tan buena como las referencias de las preguntas sin respuesta, y una de las dos
    está en duda.

Lectura honesta: con estas etiquetas el juez es bastante bueno en lo claro (25/25) y falla, o no
falla, en los bordes, que son justo donde la rúbrica y la referencia son ambiguas. **El kappa de
0,63 se apoya en cuatro no-correctas: es una estimación inestable** (un solo caso que cambie lo
mueve mucho). Y las etiquetas las puso Claude: si Santiago cierra los siete casos dudosos de otra
manera, las cifras cambian.

### Cierre de la calibración: veredictos de Santiago (16-oct-2026)

Fichero `eval/etiquetas-v2-santiago.jsonl`, aparte; `eval/etiquetas-v2-preliminares.jsonl` no se ha
tocado. Para las 24 no dudosas siguen valiendo las preliminares.

| Pregunta | Yo (preliminar) | Juez | Santiago | Cómo se cerró |
| --- | --- | --- | --- | --- |
| e-001 | correcta | correcta | correcta | Sin objeción a mi etiqueta (no se le preguntó: juez y yo coincidíamos) |
| e-016 | correcta | correcta | correcta | Ídem |
| e-019 | correcta | parcial | **correcta** | Responde a lo preguntado; la prescripción la pide la referencia, no la pregunta |
| e-023 | parcial | parcial | **parcial** | Acierta la norma y omite la conclusión para el caso |
| e-026 | parcial | parcial | parcial | Sin objeción a mi etiqueta |
| e-046 | parcial | correcta | **correcta** | Se limita a lo que dice el art. 30, no inventa formato |
| e-047 | correcta | incorrecta | correcta (*) | (*) Consecuencia de reconvertir la pregunta; la etiqueta la puse yo, pendiente de que la confirme |

Con tres de las siete (e-001, e-016, e-026) no hubo veredicto propio sino ausencia de objeción:
cuentan como cerradas pero no como una segunda opinión independiente.

**Recálculo provisional.** El juicio de e-047 es de la referencia vieja y no vale, así que se deja
fuera hasta re-juzgarla: **31 respuestas, acuerdo exacto 30/31 = 96,8 % (84 %–99 %), kappa 0,84**
(con solo las preliminares, esos mismos 31 casos daban 29/31 = 93,5 %, kappa 0,72). Queda una
discrepancia: **e-019** (Santiago: correcta; juez: parcial).

Cómo leerlo, sin inflarlo:

- **Solo 6 de las 31 etiquetas son de una persona** (y 3 de ellas por no objeción). Las otras 25 son
  mías. El acuerdo es acuerdo con un híbrido, y la revisión humana se concentró justo en los casos
  límite: está bien para encontrar errores del juez, pero el resto del acuerdo no es evidencia
  independiente.
- **El kappa se apoya en tres no-correctas** (e-010 incorrecta; e-023 y e-026 parciales). Sigue
  siendo una estimación inestable: un caso cambia mucho el valor.
- **e-019 es un sesgo del juez, y se anota sin tocar la rúbrica `j1`:** trata como esencial todo lo
  que añade la referencia, aunque la pregunta no lo pida. Santiago juzga por lo que se pregunta.
  Consecuencia: la exactitud del juez es algo más estricta que la de un revisor humano. Opciones
  abiertas, ninguna aplicada: dejarlo declarado, o recortar la referencia de e-019 a lo que pide la
  pregunta (corrección de eval set, como e-047, y se documentaría igual).

### Diagnóstico de las 4 respuestas no correctas (con el juez)

| Pregunta | Qué pasó | De quién es |
| --- | --- | --- |
| e-010 (incorrecta) | El artículo fuente (lopdgdd:art-32, bloqueo) estaba en el contexto; el modelo contestó con el art. 19 del RGPD (comunicar a destinatarios) | Generación: eligió el artículo equivocado |
| e-019 (parcial) | Contexto y citas completos; omite la prescripción a 3 años | Generación, o referencia que pide de más (discutible) |
| e-023 (parcial) | Contexto y citas completos; expone la regla y las excepciones sin aplicarlas a una clínica con datos de salud | Generación: no razona sobre el caso |
| e-026 (parcial) | **El art. 83 del RGPD no estaba en el contexto**; dio la clasificación de la LOPDGDD (leve) en vez del tramo del 83.4 | Retrieval (una de las 3 preguntas de contexto incompleto, ticket 11) |

Patrón: **la debilidad está en las cruzadas** (6/12 = 50 %): 3 se callan (e-021, e-024, e-027) y
3 contestan a medias. Las factuales (14/15) y las temporales (6/6) están sanas.

### Resultado final (16-oct-2026, eval set corregido, juez `j1`)

| | v1 | v2 (por defecto) |
| --- | --- | --- |
| **Exactitud** (de las 34 con respuesta) | 26/34 = 76,5 % (60 %–88 %) | **27/34 = 79,4 % (63 %–90 %)** |
| Exactitud de las contestadas | 26/29 = 89,7 % (74 %–96 %) | 27/31 = 87,1 % (71 %–95 %) |
| Parciales / incorrectas | 2 / 1 | 3 / 1 |
| Factual / cruzada / temporal | 14/16 · 8/12 · 4/6 | 15/16 · 6/12 · 6/6 |
| Sobre-respuesta grave | 0/1 (0 %–79 %) | 0/1 (0 %–79 %) |
| Coste del juez | 33.427 / 1.757 tokens ≈ 0,0023 $ | 35.278 / 1.894 tokens ≈ 0,0025 $ |

**Calibración final** (32 respuestas de v2; etiquetas preliminares de Claude con las 7 dudosas
cerradas por Santiago): acuerdo exacto **31/32 = 96,9 % (84 %–99 %), kappa 0,84**. e-047, ya con la
referencia corregida, la juzga correcta y coincide. Una sola discrepancia: **e-019** (Santiago:
correcta; juez: parcial). El acuerdo no cayó, así que no hace falta probar Haiku 4.5 como juez.

**v1 contra v2 en contenido, pregunta a pregunta.** De las 32 respuestas juzgadas en v2, 27 tienen
el mismo veredicto en las dos pasadas; cambian cinco:

- **Mejoran 3:** e-028 y e-032 (las dos temporales para las que se hizo v2: v1 callaba y v2 contesta
  y el juez las da por correctas) y e-014 (v1 parcial por omitir el margen de 13 años; v2 correcta).
- **Empeoran 2:** e-019 (v1 incluía la prescripción a tres años; v2 la omite) y e-023 (v1 correcta,
  v2 parcial).
- **Neto +1 (26 → 27), dentro del ruido** (los IC se solapan casi por completo). Lo que v2 sí hace
  es contestar bien las dos temporales que v1 no podía. No se puede decir que mejore el resto ni
  que lo empeore.
- Las dos "regresiones" son discutibles. e-019: Santiago da por correcta la respuesta de v2 (la
  prescripción no se preguntaba); contado así, v2 sería 28/34. e-023: el motivo del juez en v1
  admite la misma omisión que en v2 ("no menciona ... que la exención no aplica a la clínica") y
  aun así la dio por correcta: **el veredicto de v1 parece indulgente**, y con el criterio de
  Santiago (parcial) v1 sería 25/34. Los juicios de v1 no tienen revisión manual: el 26/34 de v1
  es menos fiable que el 27/34 de v2.

Patrón que se confirma en las dos pasadas: **la debilidad está en las cruzadas** (6/12 en v2, 8/12
en v1; las 3 abstenciones son las mismas) y las factuales y temporales están sanas.

### Pendiente

1. ~~Re-juzgar e-047, juzgar v1 y calibrar con las etiquetas de Santiago.~~ Hecho (arriba).
2. **Confirmar la etiqueta de e-047** (correcta), que puse yo al reconvertir la pregunta.
3. **e-019:** declarar el sesgo del juez (ya está en el README) o recortar la referencia a lo que
   pide la pregunta (corrección de eval set, a documentar como la de e-047).
4. **Riesgo abierto del eval set:** las referencias «debe abstenerse» de las 15 preguntas sin
   respuesta que el sistema calló no las revisa nadie automáticamente: si una estuviera mal como
   e-047, el sistema habría acertado callando por error y no se vería. Una revisión de esas 15
   contra el corpus lo descartaría.
5. Si se quiere un número de v1 en el que fiarse, revisar a mano sus 29 respuestas contestadas
   (hoy solo están revisadas las de v2).
6. Cualquier cambio de rúbrica será `j2` con su motivo; hoy no hay evidencia para tocarla.
