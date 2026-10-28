# Azure AI Search: índice con vectores BGE-M3, recuperador y recall medido

Type: task
Status: open
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
