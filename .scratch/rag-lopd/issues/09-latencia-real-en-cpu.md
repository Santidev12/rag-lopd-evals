# Latencia real de embeddings y reranking en CPU

Type: task
Status: resolved

## Question

Medir, no estimar. No existe benchmark público de BGE-M3 en CPU pura, y de ese número depende si el
demo puede embeber la consulta dentro del Space gratuito o tiene que llamar a una API.

A medir, en 2 vCPU sin GPU y con arranque en frío incluido:

- Tiempo de carga del modelo BGE-M3 y RAM que ocupa residente.
- Latencia p50/p95 de embeber una consulta corta en español (50 ejecuciones).
- Lo mismo para `multilingual-e5-small` y `paraphrase-multilingual-MiniLM-L12-v2`.
- Lo mismo para el reranker `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` sobre 20 candidatos.
- Latencia de la llamada a la API de DeepInfra con BGE-M3, desde Europa.

Criterio de hecho: una tabla de números reales en `docs/research/latencia-cpu.md` y la decisión tomada
sobre dónde corre cada modelo. Si ningún modelo local baja de 2 s, la arquitectura asimétrica deja de
ser una preferencia y pasa a ser obligatoria.

## Answer

Medido en 2 vCPU / 7 GB con torch CPU. Informe: [`docs/research/latencia-cpu.md`](../../../docs/research/latencia-cpu.md).

- **BGE-M3: 159 ms p50 / 170 ms p95** por consulta, 1,6 GB de RAM, 5,2 s de carga en frío. Cabe de sobra
  en un Space gratuito. El miedo de `embeddings.md` era infundado.
- **La API es peor**: el round trip a DeepInfra cuesta 673 ms–1 s solo de red, sin contar inferencia.
  4,2 veces peor que el peor caso local. **Arquitectura asimétrica descartada.**
- **MiniLM descartado**: ventana de 128 tokens, trunca los artículos. Sus buenos números medían menos texto.
- **Reranking**: 199 ms (top-5) · 413 ms (top-10) · 784 ms (top-20), y 1.353 ms con top-20 de fragmentos
  largos. Se implementa detrás de un flag sobre el top-10 y decide el eval set si compensa.
- Plan B si el Space va ahogado: `multilingual-e5-small` (17 ms, ventana 512), cambio de una línea.

Sin verificar: el ruido de vecindario de la vCPU compartida de Spaces bajo carga ajena.
