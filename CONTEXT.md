# Lenguaje del proyecto

Glosario canónico. Si un término está aquí, se usa **este** y no sus sinónimos, en el código, en los
tests, en el eval set y en el README. Solo entran términos ya decididos: esto no es una lista de deseos.

Regla de idioma: el dominio jurídico va en español (norma, artículo, apartado), porque es como lo dice
la fuente. Los términos de recuperación van en inglés (recall, chunking, reranking), porque es como se
dicen en el campo y es como aparecerán en una entrevista.

## Dominio jurídico

**Norma**:
Un texto legal completo con identidad propia: el RGPD, la LOPDGDD. Es la unidad que se descarga.
_Evita_: ley, documento, fuente.

**Artículo**:
La división numerada de una norma. Es la **unidad de contexto**: lo que se le entrega al generador.
_Evita_: sección, cláusula.

**Apartado**:
La subdivisión numerada dentro de un artículo (33.1, 33.2). Es la **unidad indexable**: lo que se
convierte en vector. En el RGPD viene marcado explícitamente; en la LOPDGDD hay que extraerlo del texto.
_Evita_: párrafo, punto, inciso.

**Resolución**:
Una resolución sancionadora de la AEPD. Entra en el corpus en v1. Su división interna son los
fundamentos de derecho, no los artículos.
_Evita_: expediente, sanción.

**Remisión**:
Una referencia de un artículo a otro ("en los casos previstos en el apartado 1"). Puede ser interna a
la norma o entre normas.
_Evita_: referencia cruzada, link.

## Recuperación

**Unidad indexable**:
El apartado. Es lo que se embebe y lo que devuelve el buscador.
_Evita_: chunk, fragmento, pasaje, nodo.

**Unidad de contexto**:
El artículo completo al que pertenece la unidad indexable recuperada. Es lo que entra en el prompt.
Este desacople —recuperar fino, entregar grueso— se llama **small-to-big**.
_Evita_: ventana, contexto expandido.

**Identificador**:
La referencia estable de una unidad indexable, con forma `<norma>:<tipo>-<numero>[.<apartado>]`:
`rgpd:art-33.1`, `lopdgdd:da-1.2`, `aepd-ps-00117-2022:fd-3`. Es semántico, no posicional: sobrevive a
cualquier cambio de chunking. El ELI/CELEX oficial se guarda aparte, como metadato.
_Evita_: chunk_id, doc_id, clave.

**Granularidad**:
Si una unidad indexable es un apartado o un artículo entero. Vale `articulo` cuando la regex no pudo
partir el artículo. No es un defecto a esconder: es una variable que el eval set puede medir.
_Evita_: nivel, resolución, tamaño.

**Corpus v0**:
RGPD consolidado + LOPDGDD consolidada. Nada más. La frontera importa: es lo que hace que una pregunta
sea `fuera_de_corpus` y no otra cosa.

## Evaluación

**Eval set**:
El conjunto de 50 preguntas con su respuesta correcta y su fuente esperada, versionado en `eval/`.
_Evita_: test set, benchmark, dataset de pruebas.

**Fuente esperada**:
Los identificadores de las unidades indexables que **deberían** recuperarse para una pregunta. Vacío en
las preguntas sin respuesta en el corpus. Es lo que permite medir el retrieval por separado de la
generación.
_Evita_: ground truth, gold chunk, respuesta de referencia.

**Sobre-respuesta**:
Que el sistema responda a una pregunta cuya respuesta no está en el corpus. El fallo caro.
_Evita_: alucinación, falso positivo.

**Abstención indebida**:
Que el sistema se calle teniendo la respuesta en el contexto recuperado. El fallo espejo del anterior.
Se reporta **siempre junto** a la sobre-respuesta: por separado, cualquiera de los dos se maquilla solo.
_Evita_: falso negativo, exceso de prudencia.
