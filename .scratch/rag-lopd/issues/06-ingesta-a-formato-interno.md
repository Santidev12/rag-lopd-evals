# Ingesta a formato interno

Type: task
Blocked by: 05
Status: resolved

## Question

Escribir el código de ingesta: descargar RGPD y LOPDGDD de sus fuentes, parsearlos y
normalizarlos al modelo fijado, con identificadores estables y metadatos.

Criterio de hecho: un comando reproducible deja el corpus normalizado en disco, con tests que
comprueban que artículos conocidos (RGPD art. 33.1, LOPDGDD art. 7) salen con el identificador
y el texto correctos. El resultado es cacheable: no se vuelve a descargar en cada ejecución.

## Progreso (13-sep-2026)

Primera rodaja hecha: **`src/rag_lopd/model.py`** — el ADR 0001 escrito en forma de tipos.
`Identificador` (parsea y serializa como cadena, con `unidad_de_contexto` como único sitio donde vive
el salto small-to-big), `UnidadIndexable`, `Articulo` (con la invariante de que sus unidades le
pertenecen), `Norma` (con `unidades_vigentes()` y `proporcion_partida_en_apartados()`).
25 tests en `tests/test_model.py`. Verificado en contenedor: ruff check, ruff format, mypy y pytest
en verde. De paso se corrigió el lint de `config.py`, que habría puesto la CI en rojo.

Siguiente: el descargador (httpx + caché en `data/raw/` con `manifest.json`) y los dos parsers,
empezando por el del RGPD, que es el fácil porque el Formex marca los apartados.

## Progreso (13-sep-2026, segunda tanda): el RGPD ya entra

- **`descarga.py`** — `Descargador` con caché en disco y `manifest.json` que anota url, fecha UTC,
  sha256 y tamaño de cada fichero. Sin esto, los números del README no se pueden defender: no sabrías
  sobre qué texto los mediste.
- **`fuentes/rgpd.py`** — parser del Formex XML. Reconstruye la jerarquía desde los `<DIVISION>`
  anidados, saca los apartados de `<PARAG IDENTIFIER="033.001">`, traduce las comillas de
  `<QUOT.START CODE="00AB">` y separa los items de lista para que no queden pegados.
- **`almacen.py`** — escribe `rgpd.json` (norma anidada, fuente de verdad) y `rgpd.unidades.jsonl`
  (una unidad vigente por línea, lo que consumirá el indexador).
- **`cli.py`** — `rag-lopd ingest rgpd`.

**Resultado real contra la red**: 99 artículos, 389 unidades, **95,6 % partidas en apartados**.
Segunda ejecución en 0,3 s gracias a la caché.

**Hallazgo**: 17 de los 99 artículos del RGPD no tienen apartados (el 4, "Definiciones", es una lista
de términos). El fallback a `granularidad: articulo` del ADR 0001, diseñado pensando en el BOE, hacía
falta ya en la fuente "fácil".

42 tests en verde; ruff, ruff format y mypy limpios. El test end-to-end del parser corre **sin red**
contra `tests/fixtures/rgpd-recorte.xml`, un recorte del fichero oficial con los artículos 4, 33 y 83.

**Pendiente de este ticket**: el parser de la LOPDGDD desde la API del BOE, que es el difícil —
ids de bloque no derivables (art. 10 = `a1-2`) y apartados solo extraíbles por regex. Ahí es donde
entra el test de umbral sobre `proporcion_partida_en_apartados()`.

## Answer

Resuelto el 13-sep-2026. `rag-lopd ingest` descarga y normaliza las dos normas del corpus v0.

| Norma | Preceptos | Unidades vigentes | Partidas en apartados |
| --- | --- | --- | --- |
| RGPD | 99 | 389 | 95,6 % |
| LOPDGDD | 144 | 339 | 82,9 % |

Módulos: `descarga.py` (caché + `manifest.json` con url, fecha UTC y sha256),
`fuentes/rgpd.py`, `fuentes/lopdgdd.py`, `almacen.py`, `cli.py`.

Las cuatro trampas del BOE, verificadas contra el servidor y resueltas en el código:
1. La API responde **400 si no mandas un `Accept` explícito** (`*/*` no le vale). El descargador
   acepta ahora un parámetro `acepta`.
2. **Los ids de bloque no son derivables**: el artículo 10 es `a1-2`. El número se lee del
   atributo `titulo`, nunca del `id`.
3. **No hay estructura dentro del artículo**: los apartados salen con regex, y un párrafo sin
   marcador continúa el apartado anterior (artículo 7).
4. **La jerarquía es plana**: los TÍTULO/CAPÍTULO/Sección son bloques hermanos en orden de
   documento. Se reconstruye con una pila, que hay que **vaciar** al llegar a las disposiciones
   adicionales — van detrás del TÍTULO X y heredarían una ruta falsa.

Extras: las versiones históricas se conservan con `vigente_desde`/`vigente_hasta` (el artículo 2
tenía 4 apartados antes de 2021 y tiene 5 después — material listo para una pregunta `temporal`),
y hay un umbral `UMBRAL_PARTIDO = 0.75` que hace fallar la ingesta si la regex se rompe.

53 tests sin red + 2 marcados `red` que sí salen a internet (`uv run pytest -m red`), excluidos
por defecto para que la suite corra rápido y sin conexión. ruff y mypy limpios.
