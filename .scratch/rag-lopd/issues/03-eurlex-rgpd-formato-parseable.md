# Formato parseable del RGPD en EUR-Lex

Type: research
Status: resolved

## Question

Determinar cuál es la vía más limpia para obtener el RGPD consolidado en español como texto
estructurado por artículo, y probarla:

- Comparar los formatos disponibles para CELEX `02016R0679-20160504`: HTML, PDF, Formex XML y
  Akoma Ntoso. Cuál conserva la numeración de artículos y apartados de forma explícita.
- Cómo se descarga sin navegador (URL directa, content negotiation en Cellar, o SPARQL).
- Cómo quedan separados los considerandos del articulado, y si merece la pena indexarlos.
- Si hay diferencias entre la versión original y la consolidada que afecten al parseo.

Salida: un informe en `docs/research/eurlex-rgpd.md` con la URL exacta recomendada y un
fragmento real del formato elegido.

## Answer

Verificado descargando de verdad. Informe completo: [`docs/research/eurlex-rgpd.md`](../../../docs/research/eurlex-rgpd.md).

- **`eur-lex.europa.eu` está detrás de un reto JS de AWS WAF**: cualquier cliente que no sea un navegador
  recibe `202` con `x-amzn-waf-action: challenge`. Es decir, la URL "obvia" de EUR-Lex **no sirve** para
  un pipeline automatizado. Descubrimiento importante, y material de README.
- **La vía buena es Cellar** (`publications.europa.eu`), sin WAF, con URL directa al **Formex XML consolidado**:
  `http://publications.europa.eu/resource/celex/02016R0679-20160504.SPA.fmx4.CONSLEG_02016R0679-20160504_0000030_SPA.fmx4.zip`
- Ese XML trae **99 `<ARTICLE IDENTIFIER="033">`**, apartados explícitos en `<PARAG>`/`<NO.PARAG>` y
  `<DIVISION>` anidados que dan la jerarquía Capítulo → Sección → Artículo como árbol real.
  **Mucho mejor estructurado que el BOE**, donde los apartados hay que sacarlos con regex.
- **Akoma Ntoso no existe** como descarga oficial (400 "Illegal accept header").
- **Los 173 considerandos solo están en el acto original** (`32016R0679`), no en el consolidado.
  Decisión pendiente en el ticket del modelo de documento: si se indexan o no.
- **Diferencia real original vs consolidado** encontrada diffando: art. 83(4)(c) dice "autoridad de control"
  en el original y "organismo de supervisión" en el consolidado tras la corrección de 2021. Es un caso
  perfecto para una pregunta `temporal` del eval set.
- **Licencia**: CC BY 4.0 (Decisión 2011/833/UE), con el disclaimer de "instrumento de documentación,
  no surte efecto jurídico" que hay que reproducir.

Incluye un script Python (solo librería estándar) probado end-to-end: extrae los 99 artículos.
