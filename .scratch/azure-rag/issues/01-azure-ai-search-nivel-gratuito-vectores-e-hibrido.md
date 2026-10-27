# Azure AI Search: nivel gratuito, vectores propios y búsqueda híbrida

Type: research
Status: resolved (27-oct-2026)

## Question

¿Se puede migrar el índice denso (728 unidades, vectores de 1024 dimensiones de BGE-M3) a Azure AI
Search **sin salir del nivel gratuito**, y qué se puede medir ahí? Datos a traer, con fuente primaria:

- Límites del nivel Free: nº de índices, almacenamiento total, tamaño máximo del índice vectorial,
  cuota y límites de consulta. ¿Caben 728 vectores de 1024 dimensiones con sus campos de texto?
- Qué NO tiene el nivel Free (se sabe que el ranker semántico no está y que no se puede ascender a un
  nivel de pago): confirmarlo y listar cualquier otra restricción que afecte a un experimento.
- Cómo se suben **vectores propios** (campo `Collection(Edm.Single)`, dimensiones, perfil HNSW vs
  búsqueda exhaustiva) y cómo se consulta con un vector calculado fuera del servicio.
- Cómo funciona la **búsqueda híbrida**: BM25 sobre campos de texto + vectorial fusionados con RRF.
  Qué parámetros se pueden ajustar (pesos, k, nº de candidatos) y qué analizador de texto conviene para
  español (`es.microsoft` / `es.lucene`).
- SDK de Python (`azure-search-documents`): versión estable, autenticación por clave y por Entra ID.
- Precio del primer nivel de pago, por si hiciera falta una sesión puntual (para decidirlo, no usarlo).

Entregable: un documento con lo anterior, cada dato con su fuente y marcado como **verificado** (leído
en la fuente primaria) o **no verificado** (solo en un fragmento de búsqueda).

## Answer

**Verificado** (leyendo el paquete oficial `azure-search-documents` 12.0.0, publicado en PyPI el 1-abr-2026):
- Los **vectores propios** se suben como campo `Collection(SINGLE)` con `vector_search_dimensions`, con
  perfil HNSW o búsqueda exhaustiva, y se consultan con `VectorizedQuery` sin vectorizador del servicio.
  Encaja con mantener BGE-M3 calculado fuera de Azure.
- `exhaustive=True` permite medir cuánto recall se pierde por aproximar con HNSW frente a la búsqueda exacta.
- El **híbrido** es `search_text` + `vector_queries` en la misma llamada, con `k`, peso del vector (1.0 por
  defecto) y `debug="vector"` para ver las subpuntuaciones antes de fusionar con RRF.
- Los analizadores `es.microsoft` y `es.lucene` existen. Autenticación por clave y por Entra ID.
- Los vectores en bruto ocupan ≈ 2,84 MiB (728 × 1024 × 4 B): probablemente caben en el nivel gratuito.

**No verificado:** los límites del nivel Free (50 MB y 3 índices solo aparecen en fragmentos), la cuota
del índice vectorial, si el **ranker semántico** está en Free (los fragmentos se contradicen: uno dice que
no, otro que hay 1.000 consultas gratis al mes), si un servicio Free puede ascender de nivel, la constante
`k` de RRF, y el precio de Basic (≈ 73,73 USD/mes según terceros).

**Informe completo:** rama `research/azure-ai-search-gratis` (de la que no se ha hecho PR), fichero `docs/research/azure-ai-search-gratis.md`.
Cada dato del informe va marcado como verificado o no verificado, y termina con la lista de lo que hay
que confirmar a mano.
