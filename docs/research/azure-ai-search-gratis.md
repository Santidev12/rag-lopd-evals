# Azure AI Search en el nivel gratuito: vectores propios e híbrido

Ticket: `.scratch/azure-rag/issues/01-azure-ai-search-nivel-gratuito-vectores-e-hibrido.md`
Fecha de la investigación: 27 de octubre de 2026.

## Cómo leer este documento

Cada dato lleva su fuente y una marca:

- **verificado**: lo leí yo en una fuente primaria (aquí, el paquete oficial `azure-search-documents` 12.0.0 descargado de PyPI: README, CHANGELOG, muestras y docstrings del código).
- **no verificado**: solo lo vi en un fragmento o resumen devuelto por `WebSearch`, o es una inferencia mía. Un humano debe comprobarlo en la página oficial indicada.

Limitación del entorno: `learn.microsoft.com`, `docs.azure.cn`, `azure.microsoft.com`, `github.com`, `cdn.jsdelivr.net` y `mintlify.com` no resuelven por DNS desde `WebFetch` (error `ENOTFOUND`). Solo pude leer PyPI y los ficheros del paquete. Por eso **todas las cifras de límites, cuotas y precios quedan sin verificar**: la página que las define (`search-limits-quotas-capacity`) no se pudo abrir. No he rellenado ningún hueco con lo que "debería ser".

Aviso sobre `WebSearch`: devuelve un resumen redactado sobre fragmentos, no la página. Tómalo como una pista para saber dónde mirar, no como una cita.

## Resumen ejecutivo

1. **Dos de las premisas del ticket aparecen contradichas o matizadas** en los fragmentos (no verificado): el ranker semántico en Free y la imposibilidad de ascender de nivel (secciones 2 y 6).
2. La parte del SDK, la forma de subir vectores propios, la consulta con vector externo, el híbrido con pesos y los analizadores `es.microsoft` / `es.lucene` **sí están verificados** por el código del SDK.
3. Lo que decide si cabe el índice (almacenamiento Free y cuota vectorial Free) **no está verificado**. La cuenta bruta de los vectores sale ~3 MB (sección 1), pero falta la cuota real.

---

## 1. Límites del nivel Free y si caben 728 × 1024

| Dato | Estado | Fuente |
|---|---|---|
| Un único servicio Free por suscripción | no verificado | https://learn.microsoft.com/azure/search/search-sku-tier |
| Máximo de 3 índices en Free | no verificado (el fragmento de búsqueda lo atribuye a la tabla oficial; no lo abrí) | https://learn.microsoft.com/en-us/azure/search/search-limits-quotas-capacity |
| Almacenamiento Free: 50 MB por servicio | no verificado (solo en espejos y agregadores de terceros, no en Microsoft) | https://learn.microsoft.com/en-us/azure/search/search-limits-quotas-capacity |
| Free: recursos compartidos con otros suscriptores, no se puede escalar ni ejecutar cargas relevantes | no verificado | https://learn.microsoft.com/azure/search/search-sku-tier |
| Cuota de índice vectorial en Free (MB) | **no encontrada** en ninguna fuente | https://learn.microsoft.com/en-us/azure/search/vector-search-index-size |
| La cuota vectorial se aplica al servicio, se cuenta por partición y depende de la fecha de creación y la región | no verificado | https://learn.microsoft.com/en-us/azure/search/vector-search-index-size |
| Los campos HNSW consumen cuota vectorial (viven en memoria); los campos con kNN exhaustivo no la consumen | no verificado | https://learn.microsoft.com/en-us/azure/search/vector-search-index-size |
| El servicio expone la cuota y el uso reales (en bytes) vía la API Service Statistics | no verificado | https://learn.microsoft.com/rest/api/searchservice/get-service-statistics |
| Cuota y límites de consulta en Free (consultas por segundo, tamaño de petición, tamaño de documento) | **no encontrados** | https://learn.microsoft.com/en-us/azure/search/search-limits-quotas-capacity |

Cálculo propio (no es un dato de Microsoft): 728 vectores × 1024 dimensiones × 4 bytes (float32) = 2 981 888 bytes, unos 2,84 MiB de vectores en bruto. Eso deja holgura frente a 50 MB **si** ese fuera el tope, pero el tamaño real del índice añade el grafo HNSW, el texto de las 728 unidades y los campos de metadatos, y no sé cuánto suman. Conclusión: **probablemente cabe, pero no está demostrado**. La comprobación más barata es crear el índice y leer la cuota y el uso reales con Service Statistics, o abrir la página de límites.

Dato adicional (verificado): el SDK admite `exhaustive=True` en una consulta vectorial, descrito como "Useful for scenarios where exact matches are critical, such as determining ground truth values". Sirve para medir el recall de HNSW frente a la búsqueda exacta. Fuente: docstring de `VectorQuery` en `azure/search/documents/models/_models.py` del paquete https://pypi.org/project/azure-search-documents/12.0.0/.

## 2. Qué NO tiene Free (y dos premisas que hay que revisar)

| Dato | Estado | Fuente |
|---|---|---|
| Sin cifrado con claves gestionadas por el cliente en servicios Free | **verificado** (docstring: "Encryption with customer-managed keys is not available for free search services") | paquete `azure-search-documents` 12.0.0, `indexes/models/_models.py` |
| Sin identidad gestionada para acceso saliente de indexadores, sin firewall de IP, sin private endpoints entrantes, sin zonas de disponibilidad | no verificado | https://learn.microsoft.com/azure/search/search-sku-tier |
| Indexadores con más restricciones en Free; el enriquecimiento con IA corre pero no se recomienda | no verificado | https://learn.microsoft.com/azure/search/search-sku-tier |
| **Ranker semántico**: la tabla de niveles lo da como no disponible en Free | no verificado | https://learn.microsoft.com/azure/search/search-sku-tier |
| **Ranker semántico, premisa dudosa**: otros fragmentos dicen que el ranker semántico es gratis hasta 1 000 consultas al mes en el plan gratuito, y que para activarlo hay que usar un nivel facturable (Basic o superior). Los dos fragmentos se contradicen | no verificado | https://learn.microsoft.com/azure/search/semantic-search-overview y https://learn.microsoft.com/azure/search/semantic-how-to-enable-disable |
| **Ascenso de nivel, premisa dudosa**: Free no se puede cambiar de nivel en el sitio. Un fragmento lo apoya (el cambio de nivel en vista previa de abril de 2025 cubría Basic, S1, S2 y S3, y excluía Free). La vía es crear otro servicio y copiar el índice | no verificado | https://mc.merill.net/message/AZ485989 y https://learn.microsoft.com/en-ie/answers/questions/1435162/azure-ai-search-changing-pricing-tiers |

Conclusión para el proyecto: la premisa "el semántico no está en Free" es probable pero **no confirmada**, y el matiz del cupo de 1 000 consultas al mes necesita una lectura humana. Si es cierto que hay ranker semántico gratuito, cambia el mapa: el reranker (que el mapa trata como "revisar con números nuevos") podría medirse sin pagar. Abrir: https://learn.microsoft.com/azure/search/semantic-search-overview (sección de disponibilidad y precios) y la fila "Semantic ranker" de https://learn.microsoft.com/azure/search/search-sku-tier.

## 3. Subir vectores propios y consultarlos con un vector externo

Todo lo de esta sección es **verificado** a partir de `samples/sample_query_vector.py` (y su README) del paquete https://pypi.org/project/azure-search-documents/12.0.0/ (sdist `azure_search_documents-12.0.0.tar.gz`).

- Campo vectorial: `SearchField(name=..., type=SearchFieldDataType.Collection(SearchFieldDataType.SINGLE), searchable=True, vector_search_dimensions=N, vector_search_profile_name="...")`. Para BGE-M3, `N = 1024`.
- `vector_search_dimensions` se documenta solo como "The dimensionality of the vector field". El **máximo permitido de dimensiones no está en el SDK**: no verificado, hay que mirarlo en la página de límites.
- Configuración del índice: `VectorSearch(algorithms=[HnswAlgorithmConfiguration(name=...), ExhaustiveKnnAlgorithmConfiguration(name=...)], profiles=[VectorSearchProfile(name=..., algorithm_configuration_name=...)])`. Un perfil apunta a **un** algoritmo; para comparar HNSW y exhaustivo hacen falta dos perfiles y, por tanto, dos campos vectoriales (o dos índices). Que dos campos vectoriales con el mismo contenido caben en Free es un dato no verificado (duplican la cuota).
- Parámetros de HNSW (`HnswParameters`): `m`, `ef_construction`, `ef_search` y `metric` con valores `cosine`, `euclidean`, `dotProduct`, `hamming`. El SDK no da valores por defecto en el docstring. BGE-M3 se suele usar con coseno; elegir métrica es una decisión del proyecto, no un dato de Azure.
- Subida: `SearchClient.upload_documents(documents=[...])`, con cada documento como diccionario que incluye el vector como lista de floats.
- Consulta con un vector calculado fuera: `VectorizedQuery(vector=<list[float]>, k_nearest_neighbors=K, fields="<campo vectorial>")` pasado en `search_client.search(vector_queries=[...], select=[...], top=...)`. No hace falta vectorizador en el servicio.
- Filtros: `filter=...` junto a la consulta vectorial; `vector_filter_mode` admite `preFilter` (por defecto en índices nuevos), `postFilter` y `strictPostFilter`.
- Versión de API por defecto del SDK 12.0.0: `2026-04-01` (`azure/search/documents/_configuration.py`).

## 4. Búsqueda híbrida (BM25 + vectorial con RRF)

| Dato | Estado | Fuente |
|---|---|---|
| Una consulta híbrida se hace pasando `search_text="..."` **y** `vector_queries=[VectorizedQuery(...)]` en la misma llamada a `search()` | **verificado** | `samples/sample_query_vector.py`, función `simple_hybrid_search` |
| `VectorQuery.weight`: peso relativo respecto a otras consultas vectoriales y a la consulta de texto en la misma petición; por defecto 1.0; debe ser positivo y mayor que cero. Cuanto mayor, más arriba quedan los documentos que casaron con esa consulta | **verificado** | docstring de `VectorQuery`, `models/_models.py` |
| `VectorQuery.k_nearest_neighbors` (parámetro `k`): vecinos devueltos como mejores resultados; `top` limita el total de la respuesta | **verificado** | docstring de `VectorQuery` y `SearchRequest` |
| El servicio combina las listas con "fusion/combination method such as RRF" y se puede ver el desglose de subpuntuaciones previo a la fusión con `debug="vector"` (modo `QueryDebugMode.VECTOR`: "Allows the user to further explore their hybrid and vector query results") | **verificado** | docstring de `VectorsDebugInfo` y `QueryDebugMode`, `models/_models.py` y `_enums.py` |
| `skip` no puede superar 100 000 | **verificado** | docstring de `SearchRequest.skip` |
| Constante `k` de RRF (se cita 60 de memoria) | **no verificado**; los fragmentos no la confirman. No asumir 60 | https://learn.microsoft.com/azure/search/hybrid-search-ranking |
| Parámetros `hybridSearch.maxTextRecallSize` (por defecto 1 000, máximo 10 000) y `countAndFacetMode` para fijar cuántos resultados BM25 entran en RRF | no verificado; además los fragmentos dicen que estaban en vista previa. **No aparecen en el SDK 12.0.0** (busqué `max_text_recall`, `maxTextRecall` y `hybridSearch` y no hay coincidencias), así que con el SDK estable podrían no ser accesibles sin una versión beta o la API REST | https://learn.microsoft.com/azure/search/hybrid-search-how-to-query |

Qué se puede ajustar según lo verificado: `k_nearest_neighbors`, `weight` del vector (el texto no tiene un peso propio en este modelo de datos, solo el peso relativo de la consulta vectorial), `top`, `exhaustive` y `oversampling` (este último solo con compresión vectorial, que no se usará). Para ajustar el número de candidatos BM25 hay que confirmar si existe en la API estable (fila de arriba).

## 5. Analizador de texto para español

- `es.microsoft` y `es.lucene` existen como valores del enum de analizadores: `ES_MICROSOFT = "es.microsoft"` y `ES_LUCENE = "es.lucene"` en `azure/search/documents/indexes/models/_enums.py`. **Verificado**.
- Diferencia (no verificado, de la documentación general): los analizadores de Microsoft hacen lematización y son de dos a tres veces más lentos de indexar que los de Lucene; los de Lucene usan stemming ligero basado en reglas y son más rápidos. Para español, la documentación no confirma explícitamente lo mismo; es una inferencia. Fuente: https://learn.microsoft.com/azure/search/index-add-language-analyzers
- Recomendación operativa (no verificada como consejo oficial): el servicio ofrece la API Analyze (`SearchIndexClient.analyze_text`, hay una muestra `sample_index_analyze_text.py` en el paquete, verificado que existe) para ver los tokens de cada analizador con texto del corpus real antes de elegir. Con 728 unidades el coste de indexado es irrelevante; lo que importa es medir recall con cada uno.
- Se declara en el campo de texto con la propiedad `analyzer_name` de `SearchableField`. Que esa propiedad sea la que se aplica tanto al indexar como al consultar es un dato no verificado.

## 6. SDK de Python `azure-search-documents`

| Dato | Estado | Fuente |
|---|---|---|
| Última versión estable: **12.0.0**, publicada el 2026-04-01 según el CHANGELOG (Production/Stable) | **verificado** | https://pypi.org/pypi/azure-search-documents/json y CHANGELOG del paquete |
| Python requerido: `>=3.9` en los metadatos (el README dice "3.8 or later": contradicción interna del paquete; manda el metadato) | **verificado** | metadatos `Requires-Python` del wheel |
| Dependencias: `isodate>=0.6.1`, `azure-core>=1.37.0`, `typing-extensions>=4.6.0` | **verificado** | `METADATA` del wheel |
| Versiones previas: 11.6.0 estable (2025-10-10), 11.5.3 (2025-06-25); betas 11.7.0b1 y 11.7.0b2 | **verificado** | CHANGELOG del paquete |
| 12.0.0 trae cambios incompatibles solo para quien usara betas (los de la API estable 11.6.0 no se ven afectados salvo `serialize()`/`deserialize()` eliminados: usar `as_dict()`) | **verificado** | CHANGELOG, sección 12.0.0 "Breaking Changes" |
| Clientes: `SearchClient` (buscar y subir), `SearchIndexClient` (índices), `SearchIndexerClient` (indexadores) | **verificado** | README del paquete |
| Autenticación por clave: `SearchClient(endpoint, index_name, AzureKeyCredential(key))`. Hay claves de administración (lectura-escritura) y de consulta (solo lectura); para consultas desde una app cliente usar la de consulta | **verificado** | README, "Authenticate the client" |
| Autenticación con Entra ID: `DefaultAzureCredential()` como credencial del mismo cliente (paquete `azure-identity`). El README nombra el rol "Search Index Data Reader" para lectura. Para subir documentos hará falta otro rol de escritura, **no nombrado en el README**: no verificado | **verificado** (lectura) / no verificado (escritura) | README, "Create a client using Microsoft Entra ID authentication" |
| Que Entra ID / RBAC funcione en el nivel Free | **no verificado** (la tabla de niveles que vi en fragmentos no lo lista como ausente, pero no es una confirmación) | https://learn.microsoft.com/azure/search/search-security-rbac |

Para este proyecto, `pyproject.toml` debería fijar `azure-search-documents>=12,<13`. Eso es una recomendación, no un hecho de Azure.

## 7. Precio del primer nivel de pago (solo para decidir)

El primer nivel facturable es **Basic**. Todo lo siguiente es **no verificado** porque la página de precios oficial no se pudo abrir:

- Fuentes de terceros dan unos 73,73 USD por unidad de búsqueda y mes (Basic, 15 GB por partición). Otra da 76 USD de base. Dividir entre ~730 h da ~0,10 USD/h; es cálculo mío, no un precio publicado.
- Hay un conflicto sobre cuántas unidades admite Basic (3 según la tabla de límites, 9 según otra fuente).
- Un fragmento dice que la página de precios podría listar el producto con otro nombre (Foundry IQ) desde mediados de 2026.
- Hay un modelo "serverless" en vista previa con otras unidades; no se compara con el dedicado.

Fuente oficial a abrir: https://azure.microsoft.com/en-us/pricing/details/search/ (y la calculadora, o la hoja "Select Pricing Tier" del portal, que muestra el precio en tu región y moneda).

Compatible con la decisión del mapa: crear un servicio Basic temporal, medir (por ejemplo el semántico, si de verdad no está en Free) y borrarlo en la misma sesión. Si Free no asciende de nivel (sección 2), el servicio de pago sería uno **nuevo**, con el índice reimportado desde los vectores locales; con 728 unidades eso es trivial.

---

## Qué queda por confirmar a mano

Abrir en un navegador con acceso:

1. **Tabla de límites por nivel (columna Free)**: almacenamiento (¿50 MB?), nº de índices (¿3?), indexadores, cuota de índice vectorial, consultas por segundo y tamaños de petición/documento, y el máximo de dimensiones de un campo vectorial. https://learn.microsoft.com/en-us/azure/search/search-limits-quotas-capacity
2. **Cuota vectorial real**: sección de cuotas por nivel y fecha de creación del servicio. https://learn.microsoft.com/en-us/azure/search/vector-search-index-size. Después de crear el servicio, leer cuota y uso reales con https://learn.microsoft.com/rest/api/searchservice/get-service-statistics
3. **Ranker semántico en Free**: ¿no está, o hay 1 000 consultas gratis al mes? https://learn.microsoft.com/azure/search/semantic-search-overview y https://learn.microsoft.com/azure/search/search-sku-tier
4. **Ascenso desde Free**: confirmar que no se puede cambiar de nivel. https://learn.microsoft.com/azure/search/search-sku-tier (y la página "Change your service tier" si existe)
5. **RRF**: constante `k` y si hay un peso para el texto. https://learn.microsoft.com/azure/search/hybrid-search-ranking
6. **Candidatos BM25 (`maxTextRecallSize`)**: ¿disponible en la API estable / en el SDK 12.0.0? https://learn.microsoft.com/azure/search/hybrid-search-how-to-query
7. **Analizadores**: qué hace `es.microsoft` frente a `es.lucene` en español. https://learn.microsoft.com/azure/search/index-add-language-analyzers
8. **Entra ID en Free** y el rol de escritura necesario (Search Index Data Contributor, nombre no verificado). https://learn.microsoft.com/azure/search/search-security-rbac
9. **Precio de Basic** en tu región y moneda. https://azure.microsoft.com/en-us/pricing/details/search/
10. **Valores por defecto de HNSW** (`m`, `efConstruction`, `efSearch`) y de la métrica. https://learn.microsoft.com/azure/search/vector-search-ranking (nombre de página no verificado)
