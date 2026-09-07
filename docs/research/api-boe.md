# API de Legislación Consolidada del BOE — LOPDGDD (BOE-A-2018-16673)

Investigación **verificada en vivo** contra `https://www.boe.es/datosabiertos/api/legislacion-consolidada/`
el 4 de septiembre de 2026, con `curl` (a través del proxy del entorno) y contraste con la documentación
oficial (`api.php` vía WebFetch + PDF `APIconsolidada.pdf` de fecha "Madrid, 2 de septiembre de 2025",
descargado y extraído con `pdftotext`).

---

## TL;DR — receta concreta

1. **Siempre** manda `Accept: application/xml` (o `application/json` solo en `metadatos`, `analisis` y
   `texto/indice` — el resto de endpoints es **XML únicamente**); sin `Accept`, la API responde `400`.
2. Pide primero el índice: `GET /id/BOE-A-2018-16673/texto/indice` → lista de bloques `{id, titulo, fecha_actualizacion, url}`.
   Los `id` **no son `a{número de artículo}`**: van `a1..a9` y luego se reciclan como `a1-2`, `a1-3`... (art. 10, 11...),
   así que hay que resolver el id a través del índice, nunca construirlo a mano.
3. Para el texto de un artículo: `GET /id/BOE-A-2018-16673/texto/bloque/{id}` (p. ej. `a7` para el art. 7) — devuelve
   **todas** las versiones históricas del bloque en un solo XML; no existe parámetro de fecha para pedir una versión
   concreta (`?fecha=...` → `400 Parámetros no soportados`), hay que elegir la versión en el cliente comparando
   `fecha_vigencia`/`fecha_publicacion`.
4. Metadatos (`rango`, `fechas`, `url_eli`) en `/metadatos`; grafo de remisiones (DEROGA/MODIFICA/AÑADE, anteriores
   y posteriores) en `/analisis`. Para el documento entero (metadatos + análisis + ELI + texto) en un solo XML:
   `GET /id/{id}` sin sufijo (solo XML).
5. No hay autenticación, API key ni límites de tasa documentados ni observados (8 peticiones seguidas → sin throttling);
   `robots.txt` no menciona `/datosabiertos/api/` en absoluto (ni `Allow` ni `Disallow`), así que no está bloqueado.

---

## 1. `/texto/indice` — qué devuelve y forma de los ids

**Petición real:**
```
curl -H "Accept: application/json" \
  "https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-2018-16673/texto/indice"
```

Devuelve `status` + `data` con un array de `bloque`, cada uno con `id`, `titulo`, `fecha_actualizacion`
(última fecha en que ese bloque concreto cambió, `AAAAMMDD`) y `url` directa al bloque. El índice
**siempre refleja la versión vigente más reciente** (no se puede pedir el índice de una fecha pasada).

Fragmento real (JSON, tal cual llega, sin editar):
```json
{
    "status": { "code": "200", "text": "ok" },
    "data": [
        { "bloque": [
            { "id": "pr", "titulo": "[preambulo]", "fecha_actualizacion": "20181206", "url": ".../texto/bloque/pr" },
            { "id": "ti", "titulo": "TÍTULO I", "fecha_actualizacion": "20181206", "url": ".../texto/bloque/ti" },
            { "id": "a1", "titulo": "Artículo 1", "fecha_actualizacion": "20181206", "url": ".../texto/bloque/a1" },
            { "id": "a2", "titulo": "Artículo 2", "fecha_actualizacion": "20210527", "url": ".../texto/bloque/a2" },
            { "id": "a3", "titulo": "Artículo 3", "fecha_actualizacion": "20181206", ... },
            ...
        ]}
    ]
}
```

El total del documento son **169 bloques** (confirmado contando `<bloque id="...">` en `/texto` completo).

### Primeros 15 bloques reales (id | título)

| id | título |
|---|---|
| `pr` | `[preambulo]` |
| `ti` | TÍTULO I |
| `a1` | Artículo 1 |
| `a2` | Artículo 2 |
| `a3` | Artículo 3 |
| `ti-2` | TÍTULO II |
| `a4` | Artículo 4 |
| `a5` | Artículo 5 |
| `a6` | Artículo 6 |
| `a7` | Artículo 7 |
| `a8` | Artículo 8 |
| `a9` | Artículo 9 |
| `a1-2` | Artículo 10 |
| `ti-3` | TÍTULO III |
| `ci` | CAPÍTULO I |

### Forma exacta de los identificadores de bloque (trampa importante)

Verificado con el índice completo de esta norma:

- **Artículos**: prefijo `a` + un contador que **se reinicia cada vez que aparece un título/capítulo/sección nuevo**,
  y cuando ese contador local vuelve a pasar por `1..9` se desambigua con un sufijo `-2`, `-3`, `-4`... Por eso:
  - Artículo 10 → `a1-2` (no `a10`)
  - Artículo 11 → `a1-3`
  - Artículo 19 → `a1-11`
  - Artículo 20 → `a2-2`
  - Artículo 53 bis → `a5-12` (los "bis" no rompen la secuencia, se insertan con su propio id)
  - Artículo 79 → `a7-11`, Artículo 80 → `a8-2`, etc.
  - **Conclusión práctica: nunca construyas `a{n}` a partir del número de artículo. Resuelve siempre `titulo` → `id` vía el índice.**
- **Títulos**: `ti`, `ti-2`, `ti-3`, `ti-4`, `tv` (Título V, no `ti-5`), `tv-2`, `tv-3`, `tv-4`, `ti-5` (Título IX, reutiliza el prefijo `ti`), `tx` (Título X). No hay un patrón numérico limpio — hay que leer `titulo` para saber a qué título romano corresponde cada id.
- **Capítulos**: `ci`, `ci-2`, `ci-3`... (prefijo `ci` para todos, con sufijo incremental global, no por título).
- **Secciones**: `s1`, `s2`, `s3`, `s1-2`, `s2-2`... (el título "Sección 1"/"Sección 2" se repite dentro de cada capítulo; el id sí es único).
- **Preámbulo**: `pr`, título literal `[preambulo]` (con corchetes, tal cual).
- **Firma**: `fi`, título literal `[firma]`.
- **Disposiciones adicionales**: `da`, `da-2`, `da-3`... `da-23` (23 disposiciones adicionales en la LOPDGDD).
- **Disposiciones transitorias**: `dt`, `dt-2`... `dt-6`.
- **Disposición derogatoria**: `dd` (única, sin sufijo).
- **Disposiciones finales**: `df`, `df-2`... `df-16`.

No aparece prefijo `pr` con número (sería el caso si hubiera varios preámbulos, no es el caso aquí) ni tipos
adicionales en esta norma; la documentación menciona también `an` (anexo) en otro ejemplo (Real Decreto-ley
distinto), que la LOPDGDD no usa.

---

## 2. `/texto/bloque/{id}` para el Artículo 7 (consentimiento de menores)

**Petición real:**
```
curl -H "Accept: application/xml" \
  "https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-2018-16673/texto/bloque/a7"
```

**Respuesta real completa:**
```xml
<?xml version="1.0" encoding="utf-8"?>
<response>
  <status>
    <code>200</code>
    <text>ok</text>
  </status>
  <data>
    <bloque id="a7" tipo="precepto" titulo="Artículo 7">
      <version id_norma="BOE-A-2018-16673" fecha_publicacion="20181206" fecha_vigencia="20181207">
        <p class="articulo">Artículo 7. Consentimiento de los menores de edad.</p>
        <p class="parrafo">1. El tratamiento de los datos personales de un menor de edad únicamente podrá fundarse en su consentimiento cuando sea mayor de catorce años.</p>
        <p class="parrafo">Se exceptúan los supuestos en que la ley exija la asistencia de los titulares de la patria potestad o tutela para la celebración del acto o negocio jurídico en cuyo contexto se recaba el consentimiento para el tratamiento.</p>
        <p class="parrafo">2. El tratamiento de los datos de los menores de catorce años, fundado en el consentimiento, solo será lícito si consta el del titular de la patria potestad o tutela, con el alcance que determinen los titulares de la patria potestad o tutela.</p>
      </version>
    </bloque>
  </data>
</response>
```

### ¿Cómo se marcan apartados y letras? — respuesta corta: **no hay marcado semántico, es todo `<p>`**

No existen etiquetas `<apartado>`, `<numero>` ni `<letra>`. Todo el contenido de un bloque es una secuencia
plana de `<p class="...">`, y el número de apartado (`1.`, `2.`...) o la letra (`a)`, `b)`...) forman parte
del **texto plano** dentro del párrafo, no de un atributo. Las clases de `<p>` observadas en toda la LOPDGDD
(conteo real sobre el documento completo, 169 bloques):

| clase | apariciones | uso |
|---|---|---|
| `parrafo` | 734 | párrafo normal / apartado numerado en el nivel base |
| `parrafo_2` | 94 | párrafo con sangría adicional (p.ej. primera letra de una lista, o apartado que sigue a una lista de letras) |
| `articulo` | 159 | cabecera "Artículo N. Título del artículo." (una por versión de cada precepto) |
| `sangrado` | 40 | texto con sangría (listas, continuaciones) |
| `sangrado_2` | 14 | segundo nivel de sangría |
| `sangrado_articulo` | 12 | sangrado específico dentro de un artículo |
| `nota_pie` | 17 | nota a pie de modificación, dentro de un `<blockquote>` |
| `refPost` | 18 | enlace `<a class="refPost">` a la norma modificadora, dentro de la nota |
| `titulo_num` / `titulo_tit` | 10 / 10 | número y texto de un TÍTULO |
| `capitulo_num` / `capitulo_tit` | 9 / 9 | número y texto de un CAPÍTULO |
| `seccion` | 5 | encabezado de sección |
| `centro_redonda` | 8 | texto centrado (encabezado real, "FELIPE VI", "PREÁMBULO"...) |
| `firma_rey` / `firma_ministro` | 1 / 1 | bloque de firma final |
| `siempreSeVe` | 1 | nota que se muestra aunque el bloque esté caducado |

**Consecuencia práctica para parsear apartados/letras**: hay que usar heurísticas de texto sobre el contenido
de cada `<p>` (regex tipo `^\d+\.` para apartados, `^[a-z]\)` para letras), no hay forma de extraerlos
estructuralmente del XML. El artículo 2 (ver más abajo) ilustra bien el patrón: las letras `a)`, `b)`, `c)`
van en `<p class="parrafo_2">` (la primera) y `<p class="parrafo">` (las siguientes) — el uso de `parrafo` vs
`parrafo_2` no es 100% consistente entre "es una letra" y "es un apartado", así que **no os fiéis de la clase
CSS para distinguir apartado de letra**, solo para saber que es un párrafo con cierta sangría visual.

Ejemplo real (Artículo 2, primera versión, con letras a/b/c):
```xml
<p class="parrafo">2. Esta ley orgánica no será de aplicación:</p>
<p class="parrafo_2">a) A los tratamientos excluidos del ámbito de aplicación del Reglamento general de protección de datos por su artículo 2.2, sin perjuicio de lo dispuesto en los apartados 3 y 4 de este artículo.</p>
<p class="parrafo">b) A los tratamientos de datos de personas fallecidas, sin perjuicio de lo establecido en el artículo 3.</p>
<p class="parrafo">c) A los tratamientos sometidos a la normativa sobre protección de materias clasificadas.</p>
```

**No hay tablas ni imágenes en la LOPDGDD** (0 `<table>`, 0 `<img>` en las 169 bloques), aunque el esquema de
la API sí las contempla en general (`<table>` estándar HTML, `<img>` PNG en base64) — si generalizáis el
parser a otras normas, contemplad esos dos casos aunque aquí no aparezcan.

---

## 3. Versiones por fecha

**Sí hay versiones por bloque, pero NO hay parámetro para pedir una versión concreta.**

- Cada `<bloque>` contiene uno o más `<version id_norma="..." fecha_publicacion="AAAAMMDD" fecha_vigencia="AAAAMMDD">`.
  `id_norma` es el identificador BOE de la norma **que introdujo esa versión** (puede ser la propia LOPDGDD en su
  publicación original, o una ley posterior que la modificó); `fecha_publicacion` es la fecha de publicación de esa
  norma modificadora; `fecha_vigencia` es la fecha en que esa versión concreta del bloque entró en vigor.
- El endpoint `/texto/bloque/{id}` **siempre devuelve todas las versiones históricas del bloque**, en orden
  cronológico ascendente (la más antigua primero). No hay paginación ni filtro.
- **Probado en vivo**: `.../texto/bloque/a2?fecha=20190101` → `400 Parámetros no soportados`. Confirmado también
  en la documentación oficial: el único parámetro documentado para `texto/bloque` es `{id_bloque}` en la ruta;
  no hay querystring soportado.
- Para reconstruir "el texto vigente en la fecha X" hay que: pedir el bloque completo, y quedarse en el cliente
  con la última `<version>` cuya `fecha_vigencia <= X` (o `fecha_publicacion` si `fecha_vigencia` está vacía).

**Ejemplo real con dos versiones** (Artículo 2, modificado por la Ley Orgánica 7/2021):
```xml
<bloque id="a2" tipo="precepto" titulo="Artículo 2">
  <version id_norma="BOE-A-2018-16673" fecha_publicacion="20181206" fecha_vigencia="20181207">
    ... (apartados 1 a 4, texto original) ...
  </version>
  <version id_norma="BOE-A-2021-8806" fecha_publicacion="20210527" fecha_vigencia="20210616">
    ... (apartados 1 a 4 iguales, + apartado 5 nuevo) ...
    <blockquote>
      <p class="nota_pie">Se añade el apartado 5 por la disposición final 4.1 de la Ley Orgánica 7/2021, de 26 de mayo. <a class="refPost">Ref. BOE-A-2021-8806#df-4</a></p>
    </blockquote>
  </version>
</bloque>
```
Nótese que la nota de cambio (`nota_pie` + `refPost`) va **dentro** de la versión que introdujo el cambio, en
un `<blockquote>` separado del contenido normativo.

Sobre 169 bloques de la LOPDGDD, **15 tienen más de una versión** (verificado contando `<version` por bloque
en `/texto` completo): `a2`, `a2-5` (art. 24), `a2-6` (art. 25), `a4-6` (art. 44), `a4-10` (art. 48), `a5-2`
(art. 50), `a6-6` a `a6-9` (arts. 64-67), y otros — coincide con lo que dice `/analisis` sobre qué artículos
han sido modificados por leyes posteriores.

### Vía alternativa para fechas de consolidación: `metadata-eli`

`GET /id/{id}/metadata-eli` (solo XML) no da versiones por artículo, pero sí la **lista completa de fechas de
consolidación de la norma entera** vía `eli:consolidated_by` / `eli:version_date`. Verificado en vivo para
esta norma: `2018-12-06` (original), `2019-06-25`, `2020-12-30`, `2021-05-27`, `2023-02-21`, `2023-05-09`,
`2025-12-27`. Útil para saber "en qué fechas cambió algo en la norma", pero para el detalle artículo por
artículo hay que ir a `texto/bloque/{id}`.

---

## 4. `/analisis` — grafo de remisiones

**Sí, sirve directamente para construir un grafo de remisiones** (anteriores/posteriores con tipo de relación
y código numérico). Contiene tres nodos: `materias` (vocabulario controlado de materias), `notas` (info
adicional, vacío en este caso) y `referencias` (con `anteriores` y `posteriores`).

**Petición real:**
```
curl -H "Accept: application/xml" \
  "https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-2018-16673/analisis"
```

Fragmento real — normas anteriores (a las que la LOPDGDD afecta):
```xml
<anteriores>
  <anterior>
    <id_norma>BOE-A-2018-10751</id_norma>
    <relacion codigo="210">DEROGA</relacion>
    <texto>el Real Decreto-ley 5/2018, de 27 de julio</texto>
  </anterior>
  <anterior>
    <id_norma>BOE-A-1999-23750</id_norma>
    <relacion codigo="210">DEROGA</relacion>
    <texto>con las excepciones indicadas, la Ley Orgánica 15/1999</texto>
  </anterior>
  <anterior>
    <id_norma>BOE-A-2015-11719</id_norma>
    <relacion codigo="270">MODIFICA</relacion>
    <texto>el art. 14 de la Ley del Estatuto Básico del Empleado Público...</texto>
  </anterior>
  ...
  <anterior>
    <id_norma>DOUE-L-2016-80807</id_norma>
    <relacion codigo="440">DE CONFORMIDAD con</relacion>
    <texto>el Reglamento (UE) 2016/679, de 27 de abril de 2016</texto>
  </anterior>
</anteriores>
```

Fragmento real — normas posteriores (que modifican la LOPDGDD, la parte más útil para "qué versión está
vigente hoy"):
```xml
<posteriores>
  <posterior>
    <id_norma>BOE-A-2025-26698</id_norma>
    <relacion codigo="270">SE MODIFICA</relacion>
    <texto>el art. 23, por Ley 10/2025, de 26 de diciembre</texto>
  </posterior>
  <posterior>
    <id_norma>BOE-A-2023-11022</id_norma>
    <relacion codigo="270">SE MODIFICA</relacion>
    <texto>los arts. 48.2, 50, 64 a 67, 75, 77 y SE AÑADE el art. 53 bis y la disposición adicional 23, por Ley 11/2023, de 8 de mayo</texto>
  </posterior>
  <posterior>
    <id_norma>BOE-A-2021-8806</id_norma>
    <relacion codigo="270">SE MODIFICA</relacion>
    <texto>los arts. 2, 44.3 y la disposición adicional 15, por Ley Orgánica 7/2021, de 26 de mayo</texto>
  </posterior>
  <posterior>
    <id_norma>BOE-A-2019-9548</id_norma>
    <relacion codigo="470">SE DECLARA</relacion>
    <texto>en el Recurso 1405/2019, la inconstitucionalidad y nulidad de lo indicado de la disposición final 3.2, por Sentencia 76/2019, de 22 de mayo</texto>
  </posterior>
</posteriores>
```

Notas para construir el grafo:
- El texto de `<texto>` es **lenguaje natural libre** con referencias a artículos concretos (p.ej. "los arts.
  48.2, 50, 64 a 67..."); si necesitáis saber *qué artículos concretos* cambiaron, hay que parsear ese texto
  con regex/NLP — no viene estructurado por artículo, solo a nivel de norma completa.
  Sí es una señal fiable, en cambio, de **qué normas** están relacionadas y con qué tipo de relación
  (`relacion@codigo` + `relacion`), eso es 100% estructurado.
- Los códigos de relación vistos aquí: `210` = DEROGA / SE DEROGA, `270` = MODIFICA / SE MODIFICA, `407` =
  AÑADE / SE AÑADE, `440` = DE CONFORMIDAD con / SE DICTA DE CONFORMIDAD, `470` = SE DECLARA (inconstitucional,
  por sentencia del TC). Es un vocabulario controlado pero **no está documentado con la lista completa de
  códigos** en el PDF ni en `api.php`; hay que ir descubriéndolos empíricamente norma a norma. *(No verificado
  en vivo: si existe un catálogo público completo de estos códigos en otro endpoint del BOE.)*
- `<materias>` da 33 materias con código + texto (vocabulario controlado del BOE), útil para clasificación
  temática, no para el grafo de remisiones.

---

## 5. `/metadatos` — campos

**Petición real:**
```
curl -H "Accept: application/xml" \
  "https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-2018-16673/metadatos"
```

**Respuesta real completa:**
```xml
<?xml version="1.0" encoding="utf-8"?>
<response>
  <status><code>200</code><text>ok</text></status>
  <data>
    <metadatos>
      <fecha_actualizacion>20260720T102442Z</fecha_actualizacion>
      <identificador>BOE-A-2018-16673</identificador>
      <ambito codigo="1">Estatal</ambito>
      <departamento codigo="7723">Jefatura del Estado</departamento>
      <rango codigo="1290">Ley Orgánica</rango>
      <fecha_disposicion>20181205</fecha_disposicion>
      <numero_oficial>3/2018</numero_oficial>
      <titulo>Ley Orgánica 3/2018, de 5 de diciembre, de Protección de Datos Personales y garantía de los derechos digitales.</titulo>
      <diario>Boletín Oficial del Estado</diario>
      <fecha_publicacion>20181206</fecha_publicacion>
      <diario_numero>294</diario_numero>
      <fecha_vigencia>20181207</fecha_vigencia>
      <estatus_derogacion>N</estatus_derogacion>
      <estatus_anulacion>N</estatus_anulacion>
      <vigencia_agotada>N</vigencia_agotada>
      <estado_consolidacion codigo="3">Finalizado</estado_consolidacion>
      <url_eli>https://www.boe.es/eli/es/lo/2018/12/05/3</url_eli>
      <url_html_consolidada>https://www.boe.es/buscar/act.php?id=BOE-A-2018-16673</url_html_consolidada>
    </metadatos>
  </data>
</response>
```

Según la documentación (tabla completa del PDF), el esquema total soporta además, cuando aplican:
`fecha_derogacion` y `fecha_anulacion` (solo si `estatus_derogacion`/`estatus_anulacion` = `S`; aquí ambos
son `N` así que no aparecen). `rango@codigo` para esta norma es `1290` ("Ley Orgánica"); `departamento@codigo`
`7723` = Jefatura del Estado. `estado_consolidacion@codigo` `3` = "Finalizado" (la codificación exacta de
qué significa cada código de estado de consolidación tampoco viene documentada más allá de este ejemplo —
*no verificado si existe un `4` u otros estados y qué significan*).

---

## 6. Formatos, cabeceras, límites y robots.txt

- **`Accept` obligatorio** en todas las peticiones. Sin cabecera `Accept` → `400 No soportado ningún mime type de la cabecera Accept.` (verificado en vivo).
- **Soporte real de JSON, por endpoint** (verificado en vivo + confirmado por el PDF, sección 2.2):
  | Endpoint | XML | JSON |
  |---|---|---|
  | `/legislacion-consolidada` (lista/búsqueda) | sí | sí |
  | `/id/{id}` (documento completo) | sí | no (solo XML) |
  | `/id/{id}/metadatos` | sí | sí |
  | `/id/{id}/analisis` | sí | sí |
  | `/id/{id}/metadata-eli` | sí | no (solo XML) |
  | `/id/{id}/texto` (completo) | sí | no (solo XML) |
  | `/id/{id}/texto/indice` | sí | sí |
  | `/id/{id}/texto/bloque/{id_bloque}` | sí | **no** — `Accept: application/json` da siempre `400`, exista o no el bloque (verificado con `a7` real y con `a999`/`zzz` inexistentes: mismo error en los tres casos) |
- **Solo `GET`**: el PDF indica explícitamente que `POST`/`PUT`/etc. devuelven `403`. *(No reprobado en vivo
  en esta sesión, pero es literal de la documentación oficial.)*
- **Sin autenticación, sin API key, sin cabeceras especiales requeridas.** Un `User-Agent` vacío (`curl -A ""`)
  funcionó igual que uno normal — no hay bloqueo por User-Agent detectado.
- **Sin límites de tasa documentados ni observados**: 8 peticiones consecutivas al mismo endpoint devolvieron
  `200` sin backoff ni cabeceras `X-RateLimit-*`/`Retry-After`. *(Esto no descarta throttling agresivo bajo
  carga sostenida o por IP — solo se probó un burst pequeño; para uso intensivo real, sed prudentes y
  espaciad peticiones aunque no haya límite visible.)*
- **CORS abierto**: `Access-Control-Allow-Origin: *` en todas las respuestas — se puede llamar directamente
  desde el navegador.
- **`robots.txt`** (`https://www.boe.es/robots.txt`, 487 KB, con cientos de reglas específicas por
  documento): **no contiene ninguna mención a `/datosabiertos/` ni a `/api/`**, ni en `Disallow` ni en
  `Allow` — no está bloqueado por robots.txt. Las reglas del fichero se centran en rutas de buscador
  (`/buscar/...`), diario oficial en otros idiomas, y documentos concretos con enlaces rotos.
- **Errores HTTP observados y su formato** (siempre XML con `Content-Type: application/xml` incluso cuando el
  código es de error, salvo el caso ya descrito del 400 por Accept):
  - `400 Identificador no válido o parámetros incorrectos` (id con formato inválido)
  - `400 No soportado ningún mime type de la cabecera Accept` (falta `Accept` o formato no soportado por ese endpoint)
  - `400 Parámetros no soportados` (querystring no reconocido, p.ej. `?fecha=`)
  - `404 La información solicitada no existe` (norma o bloque inexistente, con `Accept` válido)
  - `500 Server error - Code: 109` (verificado en vivo al mandar un `query` de búsqueda como string simple en
    vez del JSON estructurado que exige el endpoint de lista — el parámetro `query` **debe** ser un objeto
    JSON con la forma `{"query":{"query_string":{"query":"..."},"range":{}},"sort":[]}`, no texto libre; documentado
    en el PDF sección 2.1)

---

## 7. Trampas al parsear

1. **Los ids de bloque no son deducibles del número de artículo/apartado** (ver punto 1) — siempre resolver
   vía `/texto/indice`, nunca construir `a{n}`.
2. **`/texto/bloque/{id}` no soporta JSON, nunca**, ni con bloques válidos ni inválidos — si vuestro cliente
   HTTP por defecto manda `Accept: application/json`, vais a recibir un `400` engañoso que parece un error de
   bloque inexistente pero en realidad es solo el `Accept` incorrecto. Comprobadlo explícitamente: un bloque
   inexistente con `Accept: application/xml` da `404` limpio; el mismo bloque con `Accept: application/json`
   da `400` "mime type" — **el código HTTP no distingue "bloque no existe" de "formato no soportado" cuando usáis JSON en ese endpoint.**
3. **No hay apartados/letras como nodos estructurados** — todo es `<p class="...">` con el número/letra como
   texto plano al principio del párrafo. Cualquier extracción de "apartado 2, letra b)" necesita regex sobre
   el texto (`^\d+\.` / `^[a-z]\)`), y la clase CSS (`parrafo` vs `parrafo_2`) no es un indicador fiable de
   "es una letra" — indica sangría visual, no jerarquía semántica.
4. **Todo un bloque devuelve todas sus versiones históricas siempre** — nunca una sola. Si solo queréis "el
   texto vigente hoy", quedaos con la **última** `<version>` del XML (la lista viene en orden cronológico
   ascendente, la más reciente es la última hija).
5. **No hay parámetro de fecha en ningún endpoint de texto** — ni en `bloque` ni en `indice` ni en `texto`
   completo. Si necesitáis "cómo estaba la ley el 1 de enero de 2020", tenéis que descargar todas las
   versiones de cada bloque y filtrar en vuestro código por `fecha_vigencia`.
6. **Nada de entidades HTML, tablas ni imágenes en esta norma concreta** (0 ocurrencias verificadas), pero el
   esquema general de la API sí las contempla para otras normas (`<table>` HTML estándar, `<img>` PNG en
   base64 dentro de `<version>`) — un parser genérico debe soportarlas aunque la LOPDGDD no las use.
7. **Las notas de modificación (`nota_pie` + `<a class="refPost">`) van dentro de un `<blockquote>` al final
   de la versión que introdujo el cambio**, no como un nodo separado ni en el nodo `<analisis>` — si queréis
   mostrar "por qué cambió este artículo" a nivel de párrafo (no solo a nivel de norma completa como en
   `/analisis`), hay que leer estos `<blockquote>` dentro de cada `<version>`.
8. **El endpoint de búsqueda de normas (`/legislacion-consolidada?query=...`) exige un `query` en formato JSON
   estructurado**, no una cadena de texto libre; mandar `?query=proteccion` sin la estructura `{"query":{"query_string":{"query":"proteccion"}}}` correcta produce un `500 Server error - Code: 109` en vez de un `400`
   claro — el mensaje de error no ayuda a diagnosticar el problema real.
9. **`/id/{id}/texto` y `/id/{id}` (documento completo) son XML únicamente** — pedirlos con
   `Accept: application/json` falla igual que con `texto/bloque`.

---

## Fuentes verificadas en vivo

- `https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-2018-16673/texto/indice` (XML y JSON, 200)
- `https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-2018-16673/texto/bloque/a7` (XML, 200)
- `https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-2018-16673/texto/bloque/a2` (XML, 200, 2 versiones)
- `https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-2018-16673/texto` (XML, 200, 169 bloques)
- `https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-2018-16673/metadatos` (XML, 200)
- `https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-2018-16673/analisis` (XML, 200)
- `https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-2018-16673/metadata-eli` (XML, 200)
- `https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-2018-99999/texto/indice` (404, id inexistente)
- `https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-2018-16673/texto/bloque/a999` y `/zzz` (400 con Accept JSON, 404 con Accept XML)
- `https://www.boe.es/datosabiertos/api/legislacion-consolidada?query=proteccion` (500, formato de query incorrecto)
- `https://www.boe.es/robots.txt` (200, sin reglas para `/datosabiertos/`)
- `https://www.boe.es/datosabiertos/documentos/APIconsolidada.pdf` (descargado y extraído con `pdftotext -layout`; fechado "Madrid, 2 de septiembre de 2025")
- `https://www.boe.es/datosabiertos/api/api.php` (vía WebFetch, resumen coincide con el PDF)

### No verificado en vivo (marcado explícitamente)

- Que `POST`/`PUT` devuelvan `403` — es literal de la documentación, no se reprodujo en esta sesión.
- Comportamiento bajo carga sostenida real (miles de peticiones) — solo se probó un burst de 8 peticiones.
- Catálogo completo de códigos de `relacion@codigo` en `/analisis` (solo se vieron los que aparecen en esta norma: 210, 270, 407, 440, 470) — no se encontró un endpoint o documento con la lista cerrada completa.
- Significado completo de todos los códigos de `estado_consolidacion@codigo` (solo se vio el `3` = "Finalizado" en esta norma).
- Si existe algún mecanismo no documentado de fecha/versión distinto de `?fecha=` (solo se probó ese nombre de parámetro).

---

## Código Python de ejemplo (requests + xml.etree)

Pensado para alguien que sabe programar pero no es experto en Python: usa solo `requests` (hay que instalarlo,
`pip install requests`) y el módulo estándar `xml.etree.ElementTree` (viene con Python, no hay que instalar nada).

```python
"""
Descarga el índice y un bloque (artículo) concreto de una norma consolidada del BOE.
Uso: python boe_lopdgdd.py
"""
import xml.etree.ElementTree as ET
import requests

BASE = "https://www.boe.es/datosabiertos/api/legislacion-consolidada"
NORMA_ID = "BOE-A-2018-16673"  # LOPDGDD

# --- 1. Pedir el índice en JSON (json/xml están soportados aquí; XML NO lo está en /texto/bloque) ---
resp = requests.get(
    f"{BASE}/id/{NORMA_ID}/texto/indice",
    headers={"Accept": "application/json"},  # sin esta cabecera, la API responde 400
    timeout=15,
)
resp.raise_for_status()  # lanza una excepción si el código HTTP no es 2xx
indice = resp.json()

bloques = indice["data"][0]["bloque"]  # data es una lista con un único dict que contiene la lista "bloque"
print(f"La norma tiene {len(bloques)} bloques.")

# --- 2. Buscar el id de bloque del "Artículo 7" a partir del título (nunca lo construyáis a mano) ---
id_bloque = None
for b in bloques:
    if b["titulo"] == "Artículo 7":
        id_bloque = b["id"]
        break

if id_bloque is None:
    raise RuntimeError("No se encontró el Artículo 7 en el índice")

print(f"Id de bloque del Artículo 7: {id_bloque}")  # imprime "a7"

# --- 3. Pedir el bloque en XML (este endpoint SOLO admite XML, JSON da 400) ---
resp = requests.get(
    f"{BASE}/id/{NORMA_ID}/texto/bloque/{id_bloque}",
    headers={"Accept": "application/xml"},
    timeout=15,
)
resp.raise_for_status()

# ElementTree.fromstring recibe texto/bytes XML y devuelve el elemento raíz del árbol
raiz = ET.fromstring(resp.content)

# La respuesta tiene la forma: <response><status>...</status><data><bloque>...</bloque></data></response>
bloque_el = raiz.find("data/bloque")

# Un bloque puede tener varias <version> (una por cada vez que se modificó el artículo).
# Nos quedamos con la ÚLTIMA, que es la vigente hoy.
versiones = bloque_el.findall("version")
print(f"El bloque {id_bloque} tiene {len(versiones)} version(es) histórica(s).")

version_vigente = versiones[-1]  # la API las devuelve en orden cronológico ascendente

# El contenido son párrafos <p class="..."> con el texto como texto plano.
# .itertext() recoge todo el texto de un elemento y sus hijos (útil si hubiera <a> o <ins> dentro de un <p>).
for p in version_vigente.findall("p"):
    clase = p.get("class")  # atributo "class", p.ej. "articulo", "parrafo", "parrafo_2"
    texto = "".join(p.itertext()).strip()
    print(f"[{clase}] {texto}")

# Nota: si el bloque tuviera <blockquote> (notas de modificación) hay que iterarlo aparte,
# blockquote no es un <p> y findall("p") no lo recoge:
for nota in version_vigente.findall("blockquote/p"):
    print(f"[nota] {''.join(nota.itertext()).strip()}")
```

Salida esperable (resumida) para el Artículo 7:
```
La norma tiene 169 bloques.
Id de bloque del Artículo 7: a7
El bloque a7 tiene 1 version(es) histórica(s).
[articulo] Artículo 7. Consentimiento de los menores de edad.
[parrafo] 1. El tratamiento de los datos personales de un menor de edad únicamente podrá fundarse en su consentimiento cuando sea mayor de catorce años.
[parrafo] Se exceptúan los supuestos en que la ley exija la asistencia de los titulares de la patria potestad o tutela...
[parrafo] 2. El tratamiento de los datos de los menores de catorce años, fundado en el consentimiento, solo será lícito si consta el del titular de la patria potestad o tutela...
```

**Notas para quien no domina Python:**
- `resp.raise_for_status()` convierte un código HTTP de error (400, 404, 500...) en una excepción de Python,
  para no tener que comprobar `resp.status_code == 200` a mano en cada llamada.
- `resp.json()` solo funciona si el `Content-Type` de la respuesta es JSON (lo es, porque pedimos
  `Accept: application/json` y ese endpoint lo soporta); para XML no existe un `.xml()` equivalente, por eso
  se usa `ET.fromstring(resp.content)`.
- `ET.fromstring` espera **bytes** (`resp.content`) o texto **sin** declaración de encoding al principio;
  usar `resp.content` (bytes crudos) en vez de `resp.text` evita problemas de encoding con la declaración
  `<?xml version="1.0" encoding="utf-8"?>` del propio XML.
- Los `find()`/`findall()` de `ElementTree` usan una sintaxis tipo XPath simplificada: `"data/bloque"` significa
  "el hijo `bloque` del hijo `data` del elemento raíz".
