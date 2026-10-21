# Modelo de documento e identificadores estables

Type: grilling
Blocked by: 02, 03
Status: resolved

## Question

Fijar el modelo de datos interno al que se normalizan RGPD y LOPDGDD, y que tendrá que admitir
las resoluciones de la AEPD en v1 sin romperse:

- Qué es una unidad indexable y cómo se llama (¿artículo? ¿apartado? ¿fragmento?).
- Esquema del identificador estable (`rgpd:art-33.1`) y qué pasa con disposiciones adicionales,
  anexos y considerandos.
- Qué metadatos acompañan a cada unidad: jerarquía, fechas de vigencia, remisiones salientes.
- Cómo se representa que un artículo tiene varias versiones en el tiempo (las preguntas de tipo
  `temporal` del eval set dependen de esto).
- Dónde vive el corpus normalizado: ficheros JSONL en el repo, SQLite, o solo en el índice.

Salida: el vocabulario en `CONTEXT.md` y, si la decisión es difícil de revertir, un ADR.

## Progreso

**Decidido (13-sep-2026): small-to-big.** La unidad indexable es el **apartado**; la unidad de contexto
que se entrega al generador es el **artículo** completo. Se recupera fino y se entrega grueso.

Motivo: el artículo 83 del RGPD son ~1.400 tokens y diez ideas distintas — su vector sería una media
borrosa. El apartado da un vector preciso y una cita al nivel que el campo `fuente` del eval set ya
asumía; el artículo completo evita que el generador lea "en los casos previstos en el apartado anterior"
sin tener delante ese apartado.

Términos fijados en `CONTEXT.md`: norma, artículo, apartado, resolución, remisión, unidad indexable,
unidad de contexto, corpus v0, eval set, fuente esperada, sobre-respuesta, abstención indebida.

Pendiente en este ticket: cómo se extrae el apartado en la LOPDGDD (el BOE no lo marca), el esquema del
identificador estable, el versionado temporal y dónde vive el corpus normalizado.

## Answer

Resuelto el 13-sep-2026. Recogido en [ADR 0001](../../../docs/adr/0001-small-to-big-e-identificadores-semanticos.md)
y en el glosario de [`CONTEXT.md`](../../../CONTEXT.md).

1. **Small-to-big**: unidad indexable = apartado, unidad de contexto = artículo.
2. **Fallback con umbral**: si la regex no parte un artículo de la LOPDGDD, la unidad es el artículo
   entero con `granularidad: articulo`, y un test falla si el porcentaje de éxito baja del umbral.
3. **Identificador semántico propio** `<norma>:<tipo>-<numero>[.<apartado>]`, con el ELI/CELEX como
   metadato. Dos segmentos siempre, también para las resoluciones (`aepd-ps-00117-2022:fd-3`).
4. **Versiones**: la ingesta conserva todas con `vigente_desde`/`vigente_hasta`; en v0 solo se indexa
   la vigente.
5. **Dónde vive**: JSONL en `data/processed/` con un `manifest.json` de hashes y fechas de descarga.
   Fuera de git en v0; se publica como dataset cuando el eval set esté listo.
