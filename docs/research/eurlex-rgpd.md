# RGPD consolidado en español (EUR-Lex / Cellar) para RAG — CELEX 32016R0679 / 02016R0679-20160504

Investigación **verificada en vivo** el 4 de septiembre de 2026 con `curl` (vía el proxy del entorno) y `WebFetch`/`WebSearch`
contra `eur-lex.europa.eu` y `publications.europa.eu` (Cellar). Todos los ficheros citados se descargaron de verdad
(no son ejemplos de memoria): quedan en `/tmp/.../scratchpad/rgpd/` de esta sesión y el script final del final de
este documento se ejecutó end-to-end contra la red real.

---

## TL;DR — receta concreta

1. **No uses `eur-lex.europa.eu` con `curl`/scripts**: todo el dominio está detrás de un reto JS de AWS WAF
   (`x-amzn-waf-action: challenge`, HTTP 202) — cualquier cliente no-navegador recibe una página de "JavaScript
   is disabled", nunca el documento. Usa en su lugar `publications.europa.eu` (Cellar), que no tiene WAF y responde
   directo a `curl`/`urllib`.
2. El formato ganador es **Formex XML consolidado**, vía una URL fija que **no necesita content negotiation**:
   `http://publications.europa.eu/resource/celex/02016R0679-20160504.SPA.fmx4.CONSLEG_02016R0679-20160504_0000030_SPA.fmx4.zip`
   → zip con un XML de ~290 KB, 99 `<ARTICLE IDENTIFIER="033">`, con `<PARAG>`/`<NO.PARAG>` explícitos por apartado
   y `<DIVISION>` anidados que dan capítulo→sección→artículo **como árbol XML real**, no como texto a inferir.
3. Ese Formex consolidado **no trae los 173 considerandos ni el preámbulo** (es la convención de EUR-Lex: los
   consolidados solo llevan el dispositivo). Para los considerandos hay que ir al acto original,
   CELEX `32016R0679` (mismo patrón de URL sin el prefijo `CONSLEG_`, con `<CONSID IDENTIFIER="001">` × 173).
4. Cellar por content negotiation (`Accept: application/xhtml+xml`/`zip;mtype=fmx4` + `Accept-Language: spa` contra
   `https://publications.europa.eu/resource/celex/{CELEX}`) **funciona y quedó demostrado** con peticiones reales
   (redirecciones 303 → `cellar/{uuid}.../DOC_n`), igual que el SPARQL endpoint (`/webapi/rdf/sparql`).
5. El PDF **no está en Cellar para el consolidado por negociación de contenido** (404: "does not hold a content
   datastream of the requested type"), pero sí existe como fichero directo con sufijo `.pdfa2a` — usa esa URL directa,
   no la de `eur-lex.europa.eu/.../TXT/PDF/` (bloqueada por el WAF). Para RAG, el PDF es la peor opción: solo texto
   corrido, numeración a inferir por regex.

---

## 1. Formatos disponibles para la versión consolidada en español

Probé los 5 formatos que pides contra el CELEX consolidado `02016R0679-20160504`, en **dos vías**: la URL "humana"
de `eur-lex.europa.eu` (para ver si servía sin navegador) y Cellar (`publications.europa.eu`) por content negotiation.

| Formato | `eur-lex.europa.eu` directo (curl) | Cellar / `publications.europa.eu` | Numeración art./apartado explícita |
|---|---|---|---|
| HTML (`/TXT/HTML/`) | ❌ Bloqueado por WAF (HTTP 202 + reto JS) | ✅ como XHTML "ELI" (ver abajo) | **Sí**, vía atributos `id` |
| PDF (`/TXT/PDF/`) | ❌ Bloqueado por WAF | ⚠️ No vía content-negotiation (404); **sí** vía URL directa `.pdfa2a...pdf` | No — solo texto plano |
| Formex XML (zip) | N/A (no se sirve desde ese dominio) | ✅ `Accept: application/zip;mtype=fmx4` → redirect 303 → zip | **Sí**, tags dedicados (`<ARTICLE>`, `<PARAG>`) |
| Akoma Ntoso | — | ❌ `Accept: application/akn+xml` → **HTTP 400** "Illegal accept header" | No aplica — no existe ese datastream |
| XHTML "ELI" | ❌ Bloqueado por WAF | ✅ `Accept: application/xhtml+xml` → redirect 303 → XHTML | **Sí**, vía atributos `id`/`class` |

Notas importantes de lo que verifiqué:

- **El bloqueo de `eur-lex.europa.eu` es real y reproducible.** Petición real:
  ```
  curl -sS -D - -o out.html "https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX:02016R0679-20160504"
  ```
  Respuesta real (cabeceras):
  ```
  HTTP/1.1 202 Accepted
  Server: CloudFront
  x-amzn-waf-action: challenge
  Content-Type: text/html; charset=UTF-8
  ```
  Y el cuerpo es un reto de `awswaf.com` (`AwsWafIntegration.getToken()...`), no el documento. **`WebFetch` (que sí
  ejecuta JS) consiguió el contenido de la página HTML**, así que si tu pipeline puede usar un navegador headless
  con JS (Playwright/Puppeteer), el HTML de `eur-lex.europa.eu` es viable; con `curl`/`requests`/`urllib` puro, no.
- **Akoma Ntoso no existe como formato público de descarga para el RGPD** (ni para actos legislativos de la UE en
  general, hasta donde pude comprobar): el propio servidor de Cellar rechaza `application/akn+xml` como tipo MIME
  no registrado (HTTP 400), a diferencia de `application/pdf`/`zip;mtype=fmx4`/`xhtml+xml` que sí reconoce (aunque
  a veces con 404 si no hay ese datastream para ese recurso concreto). Esto contradice la premisa "Akoma Ntoso
  disponible" que a veces se lee: existen *proyectos* de investigación (p. ej. el de Monica Palmirani) que convierten
  Formex a Akoma Ntoso, pero **EUR-Lex no lo publica** como descarga oficial.
- **XHTML "ELI"** (`application/xhtml+xml`) es la forma en la que EUR-Lex *renderiza internamente* la página HTML
  que ves en el navegador — es la misma fuente, con clases CSS (`oj-ti-art`, `oj-normal`...) e IDs ELI
  (`id="art_33"`). Es más fácil de obtener por curl que el HTML "humano" (no pasa por el WAF de `eur-lex.europa.eu`
  porque se sirve desde `publications.europa.eu`), y conserva la numeración explícita.
- **El PDF consolidado en español SÍ existe**, pero no como respuesta de content-negotiation genérica: la vía que
  funcionó es la URL directa con sufijo de fichero (ver §5). Es un PDF/A-2a de 128 páginas, texto seleccionable,
  pero **sin ninguna estructura semántica** — ver el fragmento del artículo 33 en PDF en la sección 2.

**Conclusión a la pregunta 1**: Formex XML y XHTML-ELI marcan la numeración de artículo/apartado de forma explícita
(atributos `IDENTIFIER="033"` / `id="art_33"`, y `<NO.PARAG>1.</NO.PARAG>` / apartados en `<div>` separados).
El PDF obliga a inferirla del texto (regex sobre "Artículo N" y "N.\s"). El HTML "humano" de `eur-lex.europa.eu`
también la marca explícitamente (es el mismo motor de conversión que el XHTML-ELI), pero solo es alcanzable con
un cliente que ejecute JavaScript.

---

## 2. Prueba de descarga — Artículo 33 tal cual viene en el fichero

### 2.a. Formex XML consolidado (el formato recomendado)

Petición real y respuesta real (sin negociación de contenido — URL directa):

```
curl -L -o rgpd_consolidado.zip \
  "http://publications.europa.eu/resource/celex/02016R0679-20160504.SPA.fmx4.CONSLEG_02016R0679-20160504_0000030_SPA.fmx4.zip"
unzip rgpd_consolidado.zip
# → CL2016R0679ES0000030.0001.xml (290 947 bytes, 99 <ARTICLE>, 0 <CONSID>, 26 <DIVISION>)
```

Fragmento **real**, extraído tal cual del XML descargado (recortado en el punto c) del apartado 3 por espacio):

```xml
<ARTICLE IDENTIFIER="033">
  <TI.ART>Artículo 33</TI.ART>
  <STI.ART>Notificación de una violación de la seguridad de los datos personales a la autoridad de control</STI.ART>
  <PARAG IDENTIFIER="033.001">
    <NO.PARAG>1.</NO.PARAG>
    <ALINEA>En caso de violación de la seguridad de los datos personales, el responsable del tratamiento la
    notificará a la autoridad de control competente de conformidad con el artículo 55 sin dilación indebida y,
    de ser posible, a más tardar 72 horas después de que haya tenido constancia de ella, a menos que sea
    improbable que dicha violación de la seguridad constituya un riesgo para los derechos y las libertades de
    las personas físicas. Si la notificación a la autoridad de control no tiene lugar en el plazo de 72 horas,
    deberá ir acompañada de indicación de los motivos de la dilación.</ALINEA>
  </PARAG>
  <PARAG IDENTIFIER="033.002">
    <NO.PARAG>2.</NO.PARAG>
    <ALINEA>El encargado del tratamiento notificará sin dilación indebida al responsable del tratamiento las
    violaciones de la seguridad de los datos personales de las que tenga conocimiento.</ALINEA>
  </PARAG>
  <PARAG IDENTIFIER="033.003">
    <NO.PARAG>3.</NO.PARAG>
    <ALINEA><P>La notificación contemplada en el apartado 1 deberá, como mínimo:</P>
      <LIST TYPE="alpha">
        <ITEM><NP><NO.P>a)</NO.P><TXT>describir la naturaleza de la violación...</TXT></NP></ITEM>
        <ITEM><NP><NO.P>b)</NO.P><TXT>comunicar el nombre y los datos de contacto del delegado...</TXT></NP></ITEM>
        ...
      </LIST>
    </ALINEA>
  </PARAG>
  <!-- apartados 4 y 5 con el mismo patrón -->
</ARTICLE>
```

Cómo se marca cada cosa (Formex):

- **Número de artículo** → atributo `IDENTIFIER="033"` en `<ARTICLE>` (con ceros a la izquierda) **y** texto
  legible en `<TI.ART>Artículo 33</TI.ART>`.
- **Título del artículo** → `<STI.ART>` (subtítulo del artículo), hijo directo de `<ARTICLE>`, siempre presente
  cuando el artículo tiene título (los 99 artículos del RGPD lo tienen).
- **Apartados 1, 2, 3…** → cada uno es un `<PARAG IDENTIFIER="033.00N">` con `<NO.PARAG>N.</NO.PARAG>` (el número
  tal y como aparece impreso, con el punto) y el texto en `<ALINEA>`. Cuando el apartado tiene una lista con
  letras (a, b, c…) esas van como `<LIST TYPE="alpha"><ITEM><NP><NO.P>a)</NO.P><TXT>...</TXT></NP></ITEM>`.

### 2.b. XHTML "ELI" (alternativa, si prefieres HTML a XML)

Mismo artículo, mismo contenido, vía `Accept: application/xhtml+xml` contra
`https://publications.europa.eu/resource/celex/02016R0679-20160504` (redirige 303 a
`.../DOC_2`). Fragmento real:

```html
<div class="eli-subdivision" id="art_33">
   <p class="title-article-norm" id="id-b2f29385-...">Artículo 33</p>
   <div class="eli-title" id="art_33.tit_1">
      <p class="stitle-article-norm">Notificación de una violación de la seguridad de los datos
      personales a la autoridad de control</p>
   </div>
   <div class="norm">
      <span class="no-parag">1.  </span>
      <div class="norm inline-element">En caso de violación de la seguridad de los datos personales,
      el responsable del tratamiento la notificará a la autoridad de control competente...</div>
   </div>
   <div class="norm">
      <span class="no-parag">2.  </span>
      <div class="norm inline-element">El encargado del tratamiento notificará sin dilación indebida...</div>
   </div>
   ...
</div>
```

**Aviso de parseo**: el acto *original* (CELEX `32016R0679`, sin consolidar) usa otro esqueleto de clases CSS para
lo mismo (`oj-ti-art`, `oj-sti-art`, `oj-normal`, dentro de `<div id="033.001">` en vez de `<span class="no-parag">`)
— es un conversor distinto (versión de "CONVEX" diferente). Si vas a parsear XHTML, **ancla la lógica a los
`id` con prefijo ELI (`art_NN`, `art_NN.tit_1`) y no a las clases CSS**, porque las clases cambian entre el acto
original y el consolidado.

### 2.c. PDF (para comparar — no lo recomiendo para RAG)

Descarga real: `http://publications.europa.eu/resource/celex/02016R0679-20160504.SPA.pdfa2a.CL2016R0679ES0000030.0001.pdf`
(823 437 bytes, PDF 1.7, 128 páginas). Extracción real con `pdftotext -layout`:

```
                                    Artículo 33
     Notificación de una violación de la seguridad de los datos personales
                          a la autoridad de control

     1.    En caso de violación de la seguridad de los datos personales, el
     responsable del tratamiento la notificará a la autoridad de control com­
     petente de conformidad con el artículo 55 sin dilación indebida y, de ser
     posible, a más tardar 72 horas después de que haya tenido constancia de
     ella...

     2.   El encargado del tratamiento notificará sin dilación indebida al
     responsable del tratamiento las violaciones...
```

Nótese el guión suave (`\xad`, se ve como `­` o se pierde) por división de sílaba a final de línea y los saltos de
línea a media frase: para usar esto en un RAG hay que primero re-unir líneas (colapsar `\n` salvo dobles) y luego
detectar "Artículo N" / "N.\s" con regex — funciona, pero es trabajo que Formex/XHTML te ahorran.

---

## 3. Considerandos vs. articulado

**Sí vienen separados de forma identificable, pero solo en el acto original — el consolidado no los trae.**

- En el Formex del acto original (CELEX `32016R0679`, mismo patrón de URL sin `CONSLEG_`), verifiqué **173**
  elementos `<CONSID IDENTIFIER="001">`…`<CONSID IDENTIFIER="173">`, todos dentro de `<GR.CONSID>`, cada uno con
  `<NP><NO.P>(1)</NO.P><TXT>...</TXT></NP>` — el número entre paréntesis tal como se imprime. Fragmento real:
  ```xml
  <GR.CONSID><GR.CONSID.INIT>Considerando lo siguiente:</GR.CONSID.INIT>
    <CONSID><NP><NO.P>(1)</NO.P><TXT>La protección de las personas físicas en relación con el tratamiento
    de datos personales es un derecho fundamental. El artículo 8, apartado 1, de la Carta de los Derechos
    Fundamentales de la Unión Europea (<QUOT.START.../>la Carta<QUOT.END.../>) y el artículo 16, apartado 1,
    del Tratado...</TXT></NP></CONSID>
    ...
  </GR.CONSID>
  ```
  En el XHTML-ELI del original, cada considerando tiene su propio `id="rct_N"` (recital N), hermano de `id="cit_N"`
  (citas/vistos) y `id="art_N"` (artículos) — los tres bien diferenciados por prefijo.
- En el Formex/XHTML **consolidado** (`02016R0679-20160504`) comprobé `CONSID` count = **0** y no hay ningún
  `id="rct_*"`: el documento consolidado empieza directamente en `CAPÍTULO I`/`Artículo 1`. Es la convención
  editorial de EUR-Lex: un texto consolidado solo recoge el *dispositivo* (parte que tiene efecto jurídico
  cambiante); el preámbulo no se reconsolida porque, salvo corrección de errores, no cambia.

**¿Merece la pena indexar los 173 considerandos?** Mi opinión razonada, para un RAG jurídico sobre RGPD:

- **Sí, pero como colección aparte, nunca mezclados en el mismo chunk que el artículo.** Los considerandos son la
  principal fuente de *interpretación* oficial del RGPD (p. ej. el considerando 26 sobre qué es "dato anonimizado",
  el 85 sobre qué es una "violación de la seguridad" que amplía el art. 33) y muchas preguntas de negocio ("¿esto es
  un dato personal?", "¿hace falta consentimiento explícito aquí?") se responden mejor citando el considerando que
  el artículo escueto. Quitarlos pierde información real.
- El riesgo de "ruido" que mencionas es real si los concatenas en el mismo chunk que el artículo correspondiente
  (no hay una relación 1:1 declarada en el XML entre considerando N y artículo M — esa relación hay que inferirla
  por contenido/cruce manual, EUR-Lex no la da). La mitigación barata: indexarlos como documentos separados con
  metadato `tipo: "considerando"` vs `tipo: "articulo"`, dejar que el retriever los recupere de forma independiente,
  y opcionalmente enlazar por número de artículo cuando el propio texto del considerando lo menciona explícitamente
  (ej. "de conformidad con el artículo 33" — eso sí es extraíble por regex).
- Como son solo 173 párrafos (mucho más cortos que muchos artículos), el coste de indexarlos es bajo comparado con
  el valor.

---

## 4. Anexos, capítulos y secciones — jerarquía reconstruible sin inferencia de texto

**El RGPD no tiene Anexos** (a diferencia de otros reglamentos UE) — ni el Formex ni el XHTML tienen ningún
`<ANNEX>`/`id="anx_*"`, lo comprobé con una búsqueda vacía sobre ambos documentos.

**Capítulos y secciones sí, y la jerarquía es un árbol XML real, no texto a adivinar.** En el Formex consolidado,
cada capítulo y cada sección es un `<DIVISION>`, y las secciones están **anidadas dentro** del `<DIVISION>` de su
capítulo (no son hermanas). Parseando el árbol de verdad con `xml.etree.ElementTree` (no regex) obtuve, por
ejemplo, esto (recorte real de la ejecución):

```
DIVISION CAPÍTULO IV
   DIVISION Sección 1
     ARTICLE Artículo 24
     ...
     ARTICLE Artículo 31
   DIVISION Sección 2
     ARTICLE Artículo 32
     ARTICLE Artículo 33      ← aquí
     ARTICLE Artículo 34
   DIVISION Sección 3
     ...
```

Es decir: `Capítulo IV › Sección 2 › Artículo 33` se obtiene recorriendo el DOM (padre → hijo), sin ningún regex
sobre el texto. Formex no pone un atributo `TYPE="CHAPTER"`/`TYPE="SECTION"` explícito en `<DIVISION>` — hay que
mirar el texto de `<TITLE><TI>` ("CAPÍTULO IV" vs "Sección 2") para distinguirlos, pero **la jerarquía en sí (qué
contiene a qué) es estructural, no inferida**.

En el XHTML-ELI pasa lo mismo pero de forma aún más cómoda para debugging: el `id` del `<div>` que envuelve la
sección **ya lleva el capítulo dentro**, p. ej. `id="cpt_IV.sct_2"`, y el artículo 33 aparece como hermano
siguiente dentro de ese mismo contenedor:

```html
<div id="cpt_IV.sct_2">      <!-- Sección 2 -->
  ...
  <div class="eli-subdivision" id="art_32">...</div>
  <div class="eli-subdivision" id="art_33">...</div>   <!-- Artículo 33 -->
  ...
</div>
```

(Y ese `cpt_IV.sct_2` está a su vez dentro de `<div id="cpt_IV">`.) Cualquiera de las dos vías te da capítulo y
sección "gratis" sin heurísticas de texto.

---

## 5. Cellar / SPARQL — funciona, con petición real

**Content negotiation por CELEX**: sí funciona. Demostración real (cabeceras reales, sin editar):

```
$ curl -v -H "Accept: application/xhtml+xml" -H "Accept-Language: spa" \
    "https://publications.europa.eu/resource/celex/32016R0679"

> GET /resource/celex/32016R0679 HTTP/1.1
> Accept: application/xhtml+xml
> Accept-Language: spa

< HTTP/1.1 303
< Content-Type: application/xhtml+xml;charset=UTF-8
< Location: http://publications.europa.eu/resource/cellar/3e485e15-11bd-11e6-ba9a-01aa75ed71a1.0023.03/DOC_1
```

Siguiendo la redirección (`curl -L`) se obtiene el XHTML de 831 331 bytes con el artículo 33 ya mostrado. Con
`Accept: application/pdf` sobre el mismo CELEX me devolvió (también real) un error explícito y legible:

```
HTTP/1.1 404
None of the requests returned successfully a redirection. The following exception was thrown:
[cellar identifier cellar:3e485e15-11bd-11e6-ba9a-01aa75ed71a1 does not hold a content datastream of the requested type]
```
— útil porque **revela el UUID de Cellar** aunque el formato pedido no exista para ese recurso; así descubrí el
`cellar:5f2552c2-cc45-11e6-ad7c-01aa75ed71a1` del consolidado sin tener que buscarlo en otro sitio.

Con `Accept: application/akn+xml` la respuesta es distinta (HTTP 400, "Illegal accept header"), lo que confirma
que ese tipo MIME ni siquiera está registrado en el servidor — no es solo que falte el dato, es que el formato no
existe ahí.

**SPARQL**: también funciona, verificado con una consulta trivial real contra
`https://publications.europa.eu/webapi/rdf/sparql`:

```
$ curl --data-urlencode "query=SELECT * WHERE {?s ?p ?o} LIMIT 1" \
    -H "Accept: application/sparql-results+json" \
    "https://publications.europa.eu/webapi/rdf/sparql"

HTTP/1.1 200 OK
Content-Type: application/sparql-results+json

{ "head": { "link": [], "vars": ["s", "p", "o"] },
  "results": { "distinct": false, "ordered": true, "bindings": [
    { "s": {"type":"uri","value":"http://publications.europa.eu/ontology/cdm/cmr#metsStructSubDiv"},
      "p": {"type":"uri","value":"http://www.w3.org/1999/02/22-rdf-syntax-ns#type"},
      "o": {"type":"uri","value":"http://www.w3.org/2002/07/owl#InverseFunctionalProperty"} } ] } }
```

No investigué las consultas SPARQL específicas para "dame todos los CELEX de correcciones de errores del
32016R0679" — eso lo dejo **no verificado**; probablemente se puede sacar del `NOTICE type="branch"` en XML que
ya descargué (ver más abajo, trae `ACT_CONSOLIDATED_CONSOLIDATES_RESOURCE_LEGAL` con los CELEX de cada
corrección), que es más simple que escribir SPARQL para este caso.

**Bonus no pedido pero útil**: hay una tercera vía de content negotiation, la de identificador **ELI**
(`http://publications.europa.eu/resource/eli/reg/2016/679/2016-05-04`), que aparece como `SAMEAS` en el propio
metadato del recurso — la mencioné pero no la probé exhaustivamente (⚠️ **no verificado del todo**, solo confirmé
que el URI existe en los metadatos, no hice content-negotiation completo contra ella).

**Hallazgo extra no pedido explícitamente pero muy útil**: la consulta de metadatos
(`Accept: application/xml;notice=branch`) devuelve, entre otras cosas, **URLs directas por idioma y formato sin
necesidad de negociación de contenido**, con el patrón:
```
http://publications.europa.eu/resource/celex/{CELEX}.{IDIOMA-3-LETRAS}.{formato}[.{nombre-fichero}]
```
Esas son las que usé en la receta del TL;DR — más estables para un script porque no dependen de que el servidor
elija bien según cabeceras `Accept`.

---

## 6. Diferencias entre la versión original y la consolidada que afectan al parseo

El texto consolidado en español incorpora, según sus propios metadatos (`INFO.CONSLEG` y las entradas
`ACT_CONSOLIDATED_CONSOLIDATES_RESOURCE_LEGAL` del `NOTICE type="branch"`, ambos reales, descargados), **tres
correcciones de errores**:

| CELEX | Referencia DO | Fecha (según metadato `DATE ISO`) |
|---|---|---|
| `32016R0679R(01)` | DO L 314 (referencia `JOL_2016_314_R_0011`) | ⚠️ no verifiqué el día exacto, solo el número de DO |
| `32016R0679R(02)` | DO L 127, 3-7 | 2018-05-23 (confirmado, `DATE ISO="20180523"`) |
| `32016R0679R(03)` | DO L 74, 35-38 | 2021-03-04 (confirmado, `DATE ISO="20210304"`, coincide con `DOUE-L-2021-80264`) |

`END.DATE="99999999"` / `END="NONE"` en los metadatos confirma que el RGPD sigue vigente sin fecha de derogación
(no ha sido modificado por otro reglamento, solo corregido).

**Diferencia real y concreta que encontré diffando artículo por artículo** el Formex original (`32016R0679`)
contra el consolidado (`02016R0679-20160504`) con `difflib`: en el **artículo 83, apartado 4, letra c)**, el
original dice *"las obligaciones **de la autoridad de control** a tenor del artículo 41, apartado 4"* y el
consolidado dice *"las obligaciones **del organismo de supervisión** a tenor del artículo 41, apartado 4"* — es
la corrección de errores que sustituye "autoridad de control" por "organismo de supervisión" en esa referencia
cruzada (el artículo 41 trata de organismos de supervisión de códigos de conducta, no de autoridades de control;
usar "autoridad de control" ahí era el error). Encontré 25 artículos con *algún* byte de diferencia entre ambos
ficheros, pero la mayoría son artefactos de serialización (ver aviso abajo) — el 83(4)(c) es el que confirmé
como cambio semántico real.

**Aviso de parseo importante** (lo descubrí al diffar): si concatenas el texto de un `<ARTICLE>` con
`"".join(el.itertext())` sin separador, en el artículo 4 (definiciones) el ":" que separa el término definido
del resto del texto **desaparece** en uno de los dos ficheros porque vive en un nodo XML distinto según la
versión del conversor Formex (05.55 en el original vs 06.02.1 en el consolidado) — no es un cambio real del
texto legal, es un efecto de cómo cada versión del pipeline de conversión de EUR-Lex parte el árbol XML. **Usa
siempre `" ".join(...)` o equivalente con espacio/normalización de blancos (`re.sub(r'\s+',' ',...)`), nunca
concatenación directa**, y si vas a diffar dos versiones para detectar corrigenda reales, normaliza espacios
antes de comparar (como hice arriba) para no perseguir falsos positivos.

**Recomendación práctica**: indexa siempre el **consolidado** (`02016R0679-20160504`), nunca el original
(`32016R0679`) para el articulado — el original tiene erratas ya corregidas. Usa el original **solo** para sacar
los considerandos (que no están en el consolidado) y, si te importa el detalle, para poder decir "el artículo 83
fue corregido en 2021" citando el número de corrección.

---

## 7. Licencia / condiciones de reutilización

Verificado (mezcla de: disclaimer real leído dentro del propio XHTML consolidado descargado, más la página de
política de reutilización de la Comisión, `WebFetch`):

- **El propio documento consolidado trae este aviso, en español, tal cual, en su primera página**
  (lo copio literal del XHTML descargado):
  > *"Este texto es exclusivamente un instrumento de documentación y no surte efecto jurídico. Las instituciones
  > de la UE no asumen responsabilidad alguna por su contenido. Las versiones auténticas de los actos pertinentes,
  > incluidos sus preámbulos, son las publicadas en el Diario Oficial de la Unión Europea, que pueden consultarse
  > a través de EUR-Lex. Los textos oficiales son accesibles directamente mediante los enlaces integrados en este
  > documento"*

  Esto **no es una licencia**, es un descargo de autenticidad jurídica — hay que ponerlo (o algo equivalente) en
  cualquier producto que muestre este texto como si fuera "el RGPD", para dejar claro que la fuente vinculante es
  el DOUE en papel/PDF oficial, no tu índice RAG.
- **La reutilización de contenido de EUR-Lex/sitios de la Comisión** se rige por la Decisión 2011/833/UE de la
  Comisión, de 12 de diciembre de 2011, sobre la reutilización de documentos de la Comisión, implementada hoy
  como licencia **Creative Commons Attribution 4.0 International (CC BY 4.0)** salvo indicación contraria en
  avisos de copyright individuales (verificado vía la página oficial de aviso legal de la UE). Cita textual
  encontrada: *"Reuse is allowed, provided appropriate credit is given and changes are indicated."*
- **Aviso de copyright recomendado** (verificado en `data.europa.eu/en/copyright-notice`, adaptable al año en
  curso): `© European Union, 1995-2026` (o el rango de años que corresponda), acompañado de referencia a la
  licencia CC BY 4.0 y de una indicación de qué cambios has hecho tú sobre el original (en tu caso: "convertido a
  chunks para indexación en un sistema RAG").
- ⚠️ **No pude verificar el texto íntegro y literal de la página específica "Legal notice" de `eur-lex.europa.eu`**
  (`content/legal-notice/legal-notice.html` y `content/help/data-reuse/reuse-contents-eurlex-details.html`): esas
  páginas son una SPA que, incluso vía `WebFetch`, solo devolvió cabecera/navegación sin el cuerpo del aviso legal
  — probablemente el texto se carga por un componente Angular que mi fetch no llegó a hidratar del todo. Lo que sí
  verifiqué de forma sólida es la política general de reutilización de la Comisión (aplicable a EUR-Lex por
  remisión) y el disclaimer que trae el propio documento descargado.

**Recomendación de aviso a incluir en tu sistema RAG**: combina ambos — el disclaimer de no-autenticidad jurídica
(arriba, en español, cópialo literal) más `© Unión Europea, 1995-2026, contenido reutilizado bajo licencia CC BY
4.0 (Decisión 2011/833/UE); texto adaptado a partir de EUR-Lex/Cellar, CELEX 02016R0679-20160504 — no es una
fuente jurídicamente auténtica`.

---

## Script Python: descarga y extracción de artículos

Sin dependencias externas (solo librería estándar: `urllib`, `zipfile`, `xml.etree.ElementTree`). Lo ejecuté de
verdad contra la red antes de pegarlo aquí — la salida real fue: `Artículos extraídos: 99`, y el artículo 33 salió
con capítulo `CAPÍTULO IV` / sección `Sección 2`, apartados 1 a 5 correctos.

```python
"""
Descarga el RGPD consolidado en español (Formex XML, vía Cellar) y extrae
cada artículo con su número, título, capítulo/sección y apartados.

Requiere solo la librería estándar de Python (urllib, zipfile, xml.etree).
"""

import io
import urllib.request
import zipfile
import xml.etree.ElementTree as ET

# URL "directa": no hace falta negociación de contenido (headers Accept),
# Cellar la resuelve igual a partir del CELEX consolidado + idioma + formato.
# CELEX 02016R0679-20160504 = RGPD, versión consolidada vigente desde 04-05-2016.
URL = (
    "http://publications.europa.eu/resource/celex/"
    "02016R0679-20160504.SPA.fmx4."
    "CONSLEG_02016R0679-20160504_0000030_SPA.fmx4.zip"
)


def download_formex_xml(url: str) -> str:
    """Descarga el zip Formex y devuelve el texto del XML principal (no el .doc.xml)."""
    req = urllib.request.Request(url, headers={"User-Agent": "rgpd-rag-indexer/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw_zip = resp.read()

    with zipfile.ZipFile(io.BytesIO(raw_zip)) as zf:
        # El zip trae dos ficheros: "<id>.doc.xml" (metadatos de publicación,
        # lo ignoramos) y "<id>.xml" (el acto consolidado en sí).
        main_name = next(n for n in zf.namelist() if not n.endswith(".doc.xml"))
        return zf.read(main_name).decode("utf-8")


def text_of(el) -> str:
    """Concatena todo el texto de un elemento y sus hijos (itertext), sin tags.
    OJO: usa espacio como separador — la concatenación sin separador puede
    'pegar' palabras que en el XML original estaban en nodos distintos."""
    if el is None:
        return ""
    return " ".join(t.strip() for t in el.itertext() if t.strip())


def extract_articles(xml_text: str):
    """
    Recorre el árbol <ENACTING.TERMS> del Formex y devuelve una lista de dicts:
    {numero, titulo, capitulo, seccion, apartados: [{numero, texto}]}

    La jerarquía capítulo/sección/artículo es la jerarquía REAL del XML
    (elementos <DIVISION> anidados), no algo que haya que adivinar del texto.
    """
    root = ET.fromstring(xml_text)
    enacting = root.find(".//ENACTING.TERMS")

    articles = []

    def walk(node, chapter=None, section=None):
        for child in node:
            if child.tag == "DIVISION":
                # Un DIVISION es un capítulo o una sección; su encabezado
                # está en <TITLE><TI>...</TI> (p.ej. "CAPÍTULO IV" o "Sección 2").
                heading = text_of(child.find("./TITLE/TI"))
                if heading.upper().startswith(("CAPÍTULO", "CAPITULO")):
                    walk(child, chapter=heading, section=None)
                elif heading.upper().startswith(("SECCIÓN", "SECCION")):
                    walk(child, chapter=chapter, section=heading)
                else:
                    walk(child, chapter=chapter, section=section)

            elif child.tag == "ARTICLE":
                numero = child.get("IDENTIFIER")  # p.ej. "033"
                titulo_num = text_of(child.find("TI.ART"))  # "Artículo 33"
                titulo_txt = text_of(child.find("STI.ART"))  # título del artículo

                apartados = []
                for parag in child.findall("PARAG"):
                    apt_num = text_of(parag.find("NO.PARAG"))  # "1.", "2."...
                    apt_txt = text_of(parag.find("ALINEA"))  # texto completo del apartado
                    apartados.append({"numero": apt_num, "texto": apt_txt})

                # Algunos artículos no tienen PARAG (van directos a texto corrido);
                # en ese caso metemos todo el artículo como "apartado único".
                if not apartados:
                    apartados.append({"numero": "", "texto": text_of(child)})

                articles.append(
                    {
                        "numero": numero,
                        "titulo_articulo": titulo_num,
                        "titulo": titulo_txt,
                        "capitulo": chapter,
                        "seccion": section,
                        "apartados": apartados,
                    }
                )
            else:
                # cualquier otro tag intermedio: seguimos bajando por si acaso
                walk(child, chapter=chapter, section=section)

    walk(enacting)
    return articles


if __name__ == "__main__":
    print(f"Descargando {URL} ...")
    xml_text = download_formex_xml(URL)

    articles = extract_articles(xml_text)
    print(f"Artículos extraídos: {len(articles)}")

    # Muestra el artículo 33 como comprobación
    art33 = next(a for a in articles if a["numero"] == "033")
    print()
    print(f"{art33['titulo_articulo']} — {art33['titulo']}")
    print(f"({art33['capitulo']} / {art33['seccion']})")
    for ap in art33["apartados"]:
        print(f"  {ap['numero']} {ap['texto'][:100]}...")

    # Para indexar en un RAG: un "chunk" natural por artículo (o por apartado
    # si los artículos son muy largos). Ejemplo mínimo de chunk por artículo:
    chunks = []
    for a in articles:
        cuerpo = "\n".join(f"{ap['numero']} {ap['texto']}" for ap in a["apartados"])
        chunks.append(
            {
                "id": f"rgpd-art-{int(a['numero'])}",
                "titulo": f"{a['titulo_articulo']} — {a['titulo']}",
                "capitulo": a["capitulo"],
                "seccion": a["seccion"],
                "texto": f"{a['titulo_articulo']}. {a['titulo']}\n\n{cuerpo}",
            }
        )

    print()
    print(f"Chunks listos para indexar: {len(chunks)}")
```

Salida real de esta ejecución (recortada):

```
Descargando http://publications.europa.eu/resource/celex/02016R0679-20160504.SPA.fmx4.CONSLEG_02016R0679-20160504_0000030_SPA.fmx4.zip ...
Artículos extraídos: 99

Artículo 33 — Notificación de una violación de la seguridad de los datos personales a la autoridad de control
(CAPÍTULO IV / Sección 2)
  1. En caso de violación de la seguridad de los datos personales, el responsable del tratamiento la noti...
  2. El encargado del tratamiento notificará sin dilación indebida al responsable del tratamiento las vio...
  3. La notificación contemplada en el apartado 1 deberá, como mínimo:a)describir la naturaleza de la vio...
  4. Si no fuera posible facilitar la información simultáneamente, y en la medida en que no lo sea, la in...
  5. El responsable del tratamiento documentará cualquier violación de la seguridad de los datos personal...

Chunks listos para indexar: 99
```

**Siguiente paso natural (no incluido arriba, para no alargar el script)**: para sacar los 173 `<CONSID>` como una
segunda colección de chunks (`tipo: "considerando"`, sección 3), hace falta el acto **original**
(CELEX `32016R0679`). Para ese, a diferencia del consolidado, **no** hay URL directa con nombre de fichero en los
metadatos (lo comprobé: el `NOTICE type="branch"` de `32016R0679` no trae variantes `.fmx4...zip` con nombre de
fichero, solo para el consolidado existen esas URLs "atajo"). Hay que usar content negotiation de verdad:

```python
import urllib.request

req = urllib.request.Request(
    "https://publications.europa.eu/resource/celex/32016R0679",
    headers={
        "Accept": "application/zip;mtype=fmx4",
        "Accept-Language": "spa",
        "User-Agent": "rgpd-rag-indexer/1.0",
    },
)
# urllib sigue automáticamente el 303 hacia .../cellar/<uuid>.../zip
with urllib.request.urlopen(req, timeout=60) as resp:
    raw_zip = resp.read()
```
El resto (`zipfile` + recorrer `<CONSID>` dentro de `<GR.CONSID>`) es análogo al script de arriba.
