# 0001. Small-to-big e identificadores semánticos

Fecha: 2026-09-13 · Estado: aceptada

## Contexto

El corpus son normas jurídicas con jerarquía propia (norma → capítulo → sección → artículo → apartado).
Dos hechos de las fuentes, verificados en `docs/research/`:

- El **RGPD** (Formex XML vía Cellar) marca los apartados explícitamente con `<PARAG>`/`<NO.PARAG>`.
- La **LOPDGDD** (API del BOE) devuelve `<p>` planos: el "1." y el "a)" son texto suelto dentro del
  párrafo. No hay estructura semántica que extraer, solo texto que parsear.

Además, el eval set mide el retrieval por separado de la generación, y eso exige un campo `fuente` con
identificadores de lo que *debería* recuperarse. Si esos identificadores cambian al cambiar el chunking,
el eval set muere con ellos.

## Decisión

**1. Small-to-big.** La unidad indexable es el **apartado**; la unidad de contexto que se entrega al
generador es el **artículo** completo. Se recupera fino y se entrega grueso.

**2. Fallback con umbral medido.** Cuando un artículo de la LOPDGDD no se deja partir por regex, la
unidad indexable es el artículo entero, marcado con `granularidad: articulo`. Un test falla si el
porcentaje de artículos partidos con éxito baja de un umbral. El flag permite medir después, con el eval
set, si las unidades sin partir se recuperan peor.

**3. Identificador semántico propio, ELI como metadato.** Forma:
`<norma>:<tipo>-<numero>[.<apartado>]` — `rgpd:art-33.1`, `lopdgdd:da-1.2`,
`aepd-ps-00117-2022:fd-3`. El ELI/CELEX oficial se guarda como metadato.

**4. Versiones.** La ingesta conserva todas las versiones históricas de cada unidad, con
`vigente_desde`/`vigente_hasta`. En v0 **solo se indexa la vigente**.

## Alternativas descartadas

- **Indexar el artículo entero.** El artículo 83 del RGPD son ~1.400 tokens y diez ideas distintas: su
  vector sería una media borrosa de todas ellas.
- **Indexar y devolver solo el apartado.** Máxima precisión, pero "en los casos previstos en el apartado
  anterior" es incomprensible fuera de su artículo, y el texto legal está lleno de remisiones así.
- **Granularidad asimétrica por norma** (RGPD por apartado, LOPDGDD por artículo). Más simple, pero
  renuncia a la precisión en medio corpus y deja el `fuente` del eval set con dos niveles distintos
  según la norma.
- **Trocear por tamaño cuando falle la regex.** Granularidad uniforme, pero los cortes caen a mitad de
  frase y el identificador deja de ser semántico — justo lo que se quiere evitar.
- **ELI como identificador primario.** Rigor máximo, pero son URIs largas que ensucian el eval set y los
  logs, y ni la LOPDGDD del BOE ni las resoluciones de la AEPD tienen ELI a nivel de apartado: habría
  que inventarlo igualmente para medio corpus.

## Consecuencias

- El campo `fuente` del eval set apunta a apartados y sobrevive a cualquier cambio de chunking.
- El corpus queda **deliberadamente heterogéneo** en granularidad, y eso es un dato medible, no un
  defecto que esconder. Va al README.
- El índice guarda el apartado; el pipeline necesita un paso extra de expansión al artículo antes de
  construir el prompt. Es código adicional que hay que probar.
- Las resoluciones de la AEPD encajan en v1 sin tocar el esquema: cambia el tipo de división
  (`fd` en vez de `art`), no el modelo.
