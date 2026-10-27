# Azure AI Search: nivel gratuito, vectores propios y búsqueda híbrida

Type: research
Status: open

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
