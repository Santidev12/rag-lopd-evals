# Embeddings en español y viabilidad en HF Spaces gratis

Type: research
Status: resolved

## Question

Decidir con datos si los embeddings se auto-alojan o se llaman por API, teniendo en cuenta que
el demo va en un Space gratuito de CPU (2 vCPU / 16 GB) y el presupuesto es de 10 €/mes:

- Posición real de los candidatos en el subconjunto español/multilingüe del leaderboard MTEB
  (BGE-M3, multilingual-e5-large, jina-embeddings-v3, Qwen3-Embedding, y los de API).
- Tamaño en disco y en RAM de BGE-M3, y latencia estimada de embeber una consulta en CPU sin GPU.
  ¿Aguanta un Space gratuito o hay que precalcular el índice y llamar a una API solo para la query?
- Coste real de indexar ~1.500 chunks y de servir consultas con cada opción de API.
- Si `voyage-law-2` (especializado en legal) merece la pena frente a un multilingüe generalista
  para texto legal **en español**, o si su ventaja es solo en inglés.

Salida: un informe en `docs/research/embeddings.md` con una recomendación y el coste asociado.

## Answer

Informe completo: [`docs/research/embeddings.md`](../../../docs/research/embeddings.md).

**Recomendación**: arquitectura asimétrica. **Indexar en local con BGE-M3** (gratis, buen español,
1.500 chunks son minutos en el portátil) y **en producción llamar al mismo checkpoint de BGE-M3 por API**
(DeepInfra lo sirve a 0,01 $/millón de tokens) solo para embeber la consulta. El Space gratuito no
ejecuta el modelo: solo hace una llamada de red y el retrieval sobre el índice ya calculado.
Coste real: céntimos al mes. El presupuesto de 10 €/mes no es la restricción; la restricción es la CPU.

**Condición innegociable**: el modelo de indexación y el de consulta tienen que ser el **mismo checkpoint**,
o los vectores viven en espacios distintos y el retrieval devuelve basura.

**Lo que NO se pudo verificar y por eso genera un ticket nuevo**: no existe ningún benchmark público de
latencia de BGE-M3 en CPU pura para una consulta. La única señal cuantitativa encontrada (un cross-encoder
de tamaño comparable, ~2,57 s por par en CPU) sugiere riesgo alto de pasarse de los 2 s. Hay que medirlo,
no estimarlo → ver *Latencia real de embeddings y reranking en CPU*.

Otros hallazgos:
- **`voyage-law-2` descartado**: no hay evidencia de que su ventaja en dominio legal se sostenga fuera del
  inglés. Su ecosistema y sus benchmarks son angloparlantes.
- **Plan B sin dependencias externas**: `multilingual-e5-small` o `paraphrase-multilingual-MiniLM-L12-v2`
  (~118M) para indexar Y consultar dentro del Space, aceptando varios puntos menos de recall.
- **Reranker**: BGE-reranker-v2-m3 (568M) probablemente no cabe en el presupuesto de latencia en CPU.
  Candidato realista: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (~117M, entrenado con español).
