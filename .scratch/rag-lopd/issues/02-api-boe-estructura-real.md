# Estructura real de la API del BOE

Type: research
Status: resolved

## Question

Verificar contra el servidor en vivo cómo se obtiene y cómo viene estructurada la LOPDGDD
(`BOE-A-2018-16673`) desde la API de legislación consolidada:

- Qué devuelve exactamente `/legislacion-consolidada/id/{id}/texto/indice` y qué forma tienen
  los identificadores de bloque (`a1`, `da1`, …).
- Qué devuelve `/texto/bloque/{id}`: etiquetas, versiones (`fecha_vigencia`), y cómo se
  representan apartados y letras dentro de un artículo.
- Qué contiene `/analisis` y si sirve para construir el grafo de remisiones entre normas.
- Si acepta `Accept: application/json`, si hay límites de tasa y si requiere cabeceras.

Salida: un informe en `docs/research/api-boe.md` con ejemplos reales de respuesta recortados.

## Answer

Verificado en vivo contra la API. Informe completo: [`docs/research/api-boe.md`](../../../docs/research/api-boe.md).

- **Los ids de bloque NO son derivables del número de artículo.** Van `a1`…`a9` y luego reciclan:
  el artículo 10 es `a1-2`, el 20 es `a2-2`. Hay que resolverlos siempre pidiendo `/texto/indice`
  (169 bloques en la LOPDGDD) y nunca construirlos a mano. Es la trampa principal de esta fuente.
- **Dentro de un artículo no hay estructura semántica**: todo es `<p class="articulo|parrafo|parrafo_2">`
  y el número de apartado o la letra van como texto plano dentro del párrafo. Los apartados solo se
  extraen con regex sobre el texto.
- **Las versiones históricas vienen todas juntas**: cada `<bloque>` trae sus
  `<version fecha_publicacion=... fecha_vigencia=...>`. No existe parámetro de fecha (`?fecha=` da 400),
  hay que filtrar en el cliente. Esto habilita las preguntas de tipo `temporal` del eval set.
- **`/analisis` sí da grafo de remisiones** estructurado (`anteriores`/`posteriores` con códigos:
  DEROGA=210, MODIFICA=270, AÑADE=407).
- **Formatos**: solo `/legislacion-consolidada`, `/metadatos`, `/analisis` y `/texto/indice` aceptan JSON.
  `/texto/bloque/{id}` es **XML únicamente**.
- Sin autenticación, sin rate limit observado (ráfaga de 8 peticiones sin throttling), y el `robots.txt`
  del BOE no menciona `/datosabiertos/api/`. Vía limpia y sin restricciones.

Incluye un script Python (requests + xml.etree) ejecutado contra la API real.
