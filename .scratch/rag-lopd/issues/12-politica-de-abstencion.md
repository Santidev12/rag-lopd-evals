# Política de abstención

Type: task
Status: en curso

## Question

Es la decisión central del proyecto (ver `map.md`, Destination): el sistema tiene que saber
callarse cuando la respuesta no está en el corpus, y el eval set está construido justo para medir
eso — `fuera_de_corpus` y `trampa` (`SIN_RESPUESTA` en `eval.modelo`, propiedad
`Pregunta.debe_abstenerse`) son el 34 % de las 50 preguntas, no un añadido decorativo.

La niebla original ofrecía tres mecanismos sin decidir entre ellos: umbral sobre el score de
recuperación, clasificador de suficiencia de contexto, o instrucción en el prompt. Elegir a ciegas
sería opinar, no medir. Antes de construir nada, hace falta saber **si el score de recuperación
denso por sí solo ya separa las preguntas con respuesta de las que no la tienen** — si separa
bien, un umbral simple basta y las otras dos opciones son complejidad que no hace falta; si no
separa, hace falta algo que mire el *contenido* recuperado, no solo su score (clasificador o
instrucción en el prompt que compare la pregunta contra el contexto).

Alcance de este primer paso:

- Un diagnóstico que corra el motor denso (ya elegido, ticket 11) contra las 50 preguntas
  aceptadas —no solo las 27 factual/cruzada que mide `evaluar_recall`— y registre el score del
  mejor resultado (y la media del top-k) para cada una.
- Agrupar por `debe_abstenerse` (`fuera_de_corpus` + `trampa` vs. el resto) y mirar si hay
  separación visible. Con 50 preguntas no hace falta estadística sofisticada: una tabla ordenada
  por score ya dice si hay un hueco o si están mezcladas.
- Con ese número real delante, se decide el mecanismo — eso es la segunda mitad de este ticket,
  no se adelanta aquí.

## Answer

**Primera mitad resuelta el 05-oct-2026: el score de recuperación por sí solo NO separa.**

Entregado: `retrieval/abstencion.py`, `rag-lopd retrieval puntuaciones` y 4 tests. Corrido contra
el corpus real (denso, sin ruta, k=10) sobre las 50 preguntas aceptadas: 33 con respuesta
(factual, cruzada, temporal) y 17 sin ella (`fuera_de_corpus` + `trampa`).

| Umbral sobre top1 (calla si score < t) | Sin respuesta que calla | Con respuesta que calla (abstención indebida) |
| --- | --- | --- |
| 0,45 | 1/17 (6 %) | 0/33 (0 %) |
| 0,50 | 5/17 (29 %) | 2/33 (6 %) |
| 0,55 | 11/17 (65 %) | 6/33 (18 %) |
| 0,60 | 15/17 (88 %) | 12/33 (36 %) |
| 0,65 | 16/17 (94 %) | 20/33 (61 %) |

AUC del top1 como discriminador: 0,834 (la media del top-10 es peor: 0,789). Hay solape en todo
el rango útil: las con-respuesta bajan hasta 0,478 (e-029) y las sin-respuesta suben hasta 0,650
(e-046). Para callar el 88 % de lo que no tiene respuesta hay que silenciar también a 1 de cada
3 preguntas que sí la tienen — inaceptable para un sistema cuyo valor es responder bien cuando
puede.

Dos observaciones que explican el solape, no solo lo constatan:

- **Las `trampa` puntúan alto por construcción**: están escritas con el vocabulario del corpus
  (e-046: 0,650, e-045: 0,624, por encima de 14 preguntas respondibles). Un score de similitud
  mide "se parece a algo del corpus", no "el corpus contiene lo que se pregunta"; ese es
  exactamente el hueco que la trampa explota.
- **Parte de las con-respuesta de score bajo son fallos de retrieval ya diagnosticados**
  (e-024: 0,504, e-026: 0,498): el sistema no encontró el artículo y el score lo refleja, pero
  el *score no sabe distinguir* "no está en el corpus" de "está y no lo encontré".

**Decisión**: un umbral de score no puede ser la política. La señal tiene que mirar el
*contenido* recuperado frente a la pregunta, y eso solo se puede medir con un generador en el
bucle: instrucción de responder solo con el contexto dado, salida estructurada con una vía
explícita de abstención (`sin_respuesta`) y la cita obligatoria como control (una respuesta sin
cita válida cuenta como abstención). El score queda como señal auxiliar barata que se puede
añadir después si los números lo justifican.

**Segunda mitad, pendiente**: construirlo y medir sobre-respuesta y abstención indebida con el
mismo eval set. Eso exige el ticket de generación y formato de cita (en la niebla del mapa), que
pasa a ser el siguiente.
