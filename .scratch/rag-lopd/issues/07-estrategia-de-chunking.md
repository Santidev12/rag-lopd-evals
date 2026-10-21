# Estrategia de chunking sobre artículos

Type: prototype
Status: resolved

## Question

Ver sobre artículos reales cómo quedan tres estrategias antes de comprometerse con una:
un chunk por artículo · un chunk por apartado · troceo por tamaño con solapamiento.

Casos que deben mirarse con los ojos: un artículo largo (RGPD art. 6), uno con una tabla o una
enumeración densa (RGPD art. 83), uno muy corto que solo tiene sentido con su vecino, y uno con
remisión explícita a otro artículo.

La pregunta de fondo: ¿anteponer a cada chunk su ruta jerárquica ("RGPD · Capítulo IV · Artículo 33")
antes de embeber reproduce el efecto del contextual retrieval de Anthropic sin coste de LLM?

Salida: un prototipo desechable que imprime los chunks de cada variante, y la variante elegida.

## Answer

**Cerrado el 16-sep-2026 como absorbido por el ADR 0001, no por haberse trabajado.**

Cuando se escribió este ticket, "¿cómo troceamos?" era una pregunta abierta. Dejó de serlo al
resolver *Modelo de documento e identificadores estables*: el ADR 0001 fijó apartado como unidad
indexable y artículo como unidad de contexto, y la ingesta ya antepone la ruta jerárquica a cada
unidad. Mirar chunks impresos ya no decide nada.

Lo único que quedaba vivo —**si anteponer la ruta jerárquica mejora de verdad el recall, o solo
lo parece**— no se puede contestar mirando texto: hace falta medirlo con el eval set contra el
corpus indexado. Esa pregunta se traslada a la zona de niebla de *Retrieval híbrido y sus
baselines*, como una variante más que comparar.

Que un ticket muera porque una decisión anterior se lo comió es sano. Trabajarlo igual habría
sido gastar una sesión en producir una opinión que el eval set va a contradecir o confirmar
gratis dos tickets después.
