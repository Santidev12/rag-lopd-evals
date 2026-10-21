# Latencia real de embeddings y reranking en CPU

Medido el 13 de septiembre de 2026. **Números propios, no estimaciones**: no existe ningún benchmark
público de BGE-M3 en CPU pura, y de este dato depende si el demo puede embeber la consulta dentro del
Space gratuito o tiene que llamar a una API externa.

## TL;DR

**BGE-M3 corre dentro de un Space gratuito sin problema: 159 ms por consulta.** La arquitectura
asimétrica que recomendaba `embeddings.md` (indexar en local, embeber la consulta por API) **queda
descartada**: la llamada de red sola cuesta entre 670 ms y 1 s, de cuatro a seis veces más que ejecutar
el modelo en local, además de añadir una clave, un proveedor y un modo de fallo. Se auto-aloja.

## Entorno de medición

| | |
| --- | --- |
| CPU | 2 vCPU (`torch.set_num_threads(2)`, `OMP_NUM_THREADS=2`) |
| RAM | 7 GB |
| PyTorch | 2.14.0+cpu, sin CUDA |
| Consulta | pregunta real en español, 22 palabras |
| Fragmento | artículo 33 del RGPD con su ruta jerárquica delante, ~400 tokens |
| Método | 3 ejecuciones de calentamiento, luego 30 medidas; p50 y p95 |

Un Space gratuito declara 2 vCPU / 16 GB, así que la CPU es equivalente y la RAM sobra. La diferencia
que queda sin medir es el **ruido de vecindario**: en Spaces la vCPU es compartida y puede ir más
lenta bajo carga ajena. Trátese esto como el mejor caso realista, no como una garantía.

## Bi-encoders (embeber la consulta)

| Modelo | Dim | Ventana | RAM | Carga en frío | Consulta p50 | Consulta p95 | Indexar 1.500 chunks |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `BAAI/bge-m3` | 1024 | 8192 | 1,6 GB | 5,2 s | **159,1 ms** | 169,8 ms | 18,3 min |
| `intfloat/multilingual-e5-small` | 384 | 512 | 448 MB | ~2 s | **17,1 ms** | 18,3 ms | 2,4 min |
| `paraphrase-multilingual-MiniLM-L12-v2` | 384 | **128** | 691 MB | ~2 s | 17,5 ms | 19,1 ms | 0,6 min |

**MiniLM queda descartado**: su ventana por defecto es de 128 tokens. Un artículo del RGPD se trunca
a la primera frase, así que sus 17 ms y sus 0,6 minutos de indexación son rápidos porque están midiendo
menos texto. Es una trampa clásica de los benchmarks de embeddings.

BGE-M3 es 9 veces más lento que e5-small y sigue siendo **irrelevante** frente al resto de la consulta:
la generación con un LLM cuesta entre 1 y 3 segundos. 159 ms es ruido dentro de ese presupuesto.

La indexación (18 min a 2 vCPU) se hace **una vez y en local**, no en el Space. En un portátil moderno
con más núcleos baja a unos pocos minutos.

## Cross-encoder (reranking)

`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, 502 MB, carga en 10,6 s la primera vez.

| Candidatos | p50 |
| --- | --- |
| 5 | 199 ms |
| 10 | 413 ms |
| 20 | 784 ms |

El coste crece **lineal con el número de candidatos y con la longitud de cada uno**: con fragmentos de
~400 tokens en lugar de los ~200 de esta tabla, el top-20 sube a 1.353 ms. Reordenar el top-10 es
asumible; el top-20 con artículos largos, no, si se quiere mantener la respuesta por debajo de los
dos segundos.

## La opción de API, medida

Round trip completo al endpoint de DeepInfra, sin contar la inferencia:

```
total=1,018 s   (handshake TLS 0,544 s)
total=0,937 s   (handshake TLS 0,491 s)
total=0,673 s   (handshake TLS 0,222 s)
```

El contenedor de medición no está necesariamente en Europa, así que esto es un **suelo**, no una medida
de lo que vería el Space. Aun así: el mejor caso de la API (673 ms) es 4,2 veces peor que el peor caso
de BGE-M3 en local (170 ms). Reutilizando la conexión TLS mejoraría, pero no hasta acercarse.

## Decisión

- **Embeddings: `BAAI/bge-m3` auto-alojado**, con `max_seq_length` limitado a 512 (su valor por defecto,
  8192, no aporta nada con chunks de artículo y multiplica el coste).
- **Indexación en local**, una vez, y el índice se sube al Space.
- **Sin API de embeddings**: cero coste, cero claves, cero dependencia externa y menos latencia.
- **Reranking: opcional y sobre el top-10.** Se implementa detrás de un flag y se decide con el eval
  set si el recall que aporta compensa los ~400 ms. Es exactamente el tipo de cosa que el eval set
  existe para responder.
- **Plan B si el Space va ahogado**: `multilingual-e5-small` (17 ms, 448 MB, ventana de 512). Pierde
  calidad pero es un cambio de una línea, porque indexación y consulta usan el mismo checkpoint.

## Lo que esto cambia respecto a `embeddings.md`

Aquel informe recomendaba arquitectura asimétrica **por precaución**, ante la ausencia de datos. Con los
datos delante, la precaución era innecesaria y el remedio era peor que la enfermedad. Queda como ejemplo
de por qué este proyecto mide en lugar de estimar.
