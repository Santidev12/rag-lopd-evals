# Azure AI Search: índice con vectores BGE-M3, recuperador y recall medido

Type: task
Status: claimed
Blocked by: 06, 07

## Question

Implementar la migración y medirla según el diseño del experimento:

- Un `RecuperadorAzureSearch` que cumpla el contrato `Recuperador` (el mismo que BM25 y el denso local),
  con la consulta embebida por BGE-M3 vía DeepInfra como hasta ahora.
- Un comando para crear el índice y subir las 728 unidades con sus vectores y metadatos (identificador
  semántico, norma, ruta, granularidad), idempotente y sin claves en el repositorio.
- `retrieval evaluar` ampliado con los motores nuevos, guardando las cifras con `--guardar` como hoy.
- La tabla antes/después y la lectura honesta del resultado (incluidas las preguntas que cambian de
  estado), con tests sin red (cliente mockeado) como el resto del proyecto.

Skills: `/tdd`, `/codebase-design`. Resultado: código en el repo, tabla medida y la decisión de qué
retriever queda como el de v1.

## Entrada: el diseño aprobado en el ticket del experimento

- **Cinco configuraciones:** local denso (A), Azure vectorial HNSW (B), Azure vectorial exacto (C), BM25
  solo en Azure (D) y Azure híbrido (E), con RRF `k` = 60 y peso del vector por defecto. Sin ranker
  semántico ni variantes de peso.
- **Control de cordura:** C debe reproducir A (25/28 en @10, artículo) antes de interpretar nada.
- **Guardar** cada configuración con el ranking top-20 por pregunta, y versionar una copia pequeña.
- **Regla de mejora** y **decisión de v1** exactamente como en el ticket del experimento; la tabla final
  incluye la lista de preguntas que cambian de estado.
- Un índice por configuración de texto o vectorial cabe en el nivel Free (3 índices, 50 MB): contarlos al
  diseñar el esquema para no pasarse de 3.

## Progreso (7-nov-2026): código hecho; falta el servicio y medir

Ticket aún **abierto**: el agente no llega a Azure, así que el código está probado con un cliente falso y **no
se ha ejecutado contra un servicio real**.

### Entregado (rama `azure-rag/mapa`)
- `retrieval/azure_search.py`: `RecuperadorAzureSearch` con los cuatro modos (`vectorial`, `vectorial-exacto`,
  `bm25`, `hibrido`), que cumple el contrato `Recuperador`. Un solo índice (`rag-lopd-v0`) y un solo campo
  vectorial: la búsqueda exacta es el mismo campo con `exhaustive=True`.
- **Decisiones que el ticket pedía fijar antes de medir:**
  - Analizador: `es.microsoft` (lematiza). `es.lucene` queda sin probar.
  - Clave del documento: `rgpd:art-33.1` → `rgpd--art-33_1` (Azure no admite `:` ni `.`). El identificador
    original va en un campo recuperable; la traducción es reversible.
  - Vectores: se suben los del denso local (`denso-sin-ruta.npz`), sin volver a embeber.
- CLI: `retrieval indexar-azure` (crea o actualiza el índice y sube los documentos) y
  `retrieval evaluar --motor azure-...`.
- Autenticación: clave de administración en `.env` si está; si no, Entra ID.
- Pruebas: 17 tests con cliente falso (claves, esquema, documentos, forma de cada consulta, traducción de
  resultados). `ruff`, `mypy` y `pytest` en verde.

### Pendiente (lo ejecuta Santiago)
1. **Crear el servicio** en el nivel Free (sin coste), en `swedencentral`, con el grupo `rg-rag-lopd`. El nombre es
   global en Azure: `az search service create --name <servicio> --resource-group rg-rag-lopd --sku free --location swedencentral`
   *(de memoria, sin verificar)*.
2. **Clave de administración** → `.env` (`AZURE_SEARCH_ENDPOINT`, `AZURE_SEARCH_API_KEY`). **No pegarla en el chat.**
3. **Indexar:** `uv run rag-lopd retrieval indexar-azure`. Aquí se verá si alguna clave del corpus real no cabe en
   la traducción (la función lo rechaza con error).
4. **Medir** las cuatro configuraciones con `--guardar`, y la comparación con el local.

### Riesgos conocidos
- Ni el nivel Free ni la cuota del índice vectorial están confirmados en fuente primaria (ver el informe de
  investigación). Si el índice no cabe, el indexado falla con un error claro, no en silencio.

### Servicio creado (7-nov-2026)
- `rg-rag-lopd-search`, SKU **free**, **Sweden Central**, grupo `rg-rag-lopd`, endpoint
  `https://rg-rag-lopd-search.search.windows.net`. Estado `Succeeded`.
- Dato del propio servicio: `semanticSearch: free`. Es el plan gratuito del ranker semántico (1.000 consultas al
  mes). El experimento sigue sin usarlo, por decisión del ticket de presupuesto, pero queda confirmado que existe.
- Pendiente: clave de administración en `.env` y `indexar-azure`.
- **Indexado (7-nov-2026):** `indexar-azure` subió **728 documentos** con vectores de **1024 dimensiones** al índice
  `rag-lopd-v0`, sin errores. Pendiente: medir las cuatro configuraciones y el control de cordura.
