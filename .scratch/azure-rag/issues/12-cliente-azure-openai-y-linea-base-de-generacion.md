# Cliente de Azure OpenAI y línea base de generación (3 pasadas)

Type: task
Status: claimed
Blocked by: 06 (resuelto)

## Question

Implementar la decisión del ticket del generador y medirla:

- Un cliente de Azure OpenAI que cumpla el contrato `ModeloDeLenguaje` (`completar(sistema, usuario)`),
  con `gpt-4.1-mini` en **`Standard` regional de West Europe** (Data Zone tiene cuota 0), `temperature` 0 y JSON simple, sin tocar el prompt v2. Decidir
  dentro del ticket cómo se autentica en local (Entra ID con `DefaultAzureCredential` o clave en `.env`)
  sin dejar claves en el repositorio.
- Su tarifa explícita en `buscar_tarifa` (precio de `Standard` regional verificado, no adivinado).
- El **estado `BLOQUEADO`**: un bloqueo del filtro de contenido (el 400 o el `finish_reason` de filtro,
  formas exactas por verificar con una llamada real) se registra como `BLOQUEADO`, cuenta como callarse
  y se desglosa en el resumen. Con tests sin red, como el resto del proyecto.
- `generacion evaluar` con el modelo nuevo, **tres pasadas** con el recuperador denso local y k = 10, y el
  juez (`j1`) sobre cada una. Guardar todo en `data/runs/` como hoy.
- El tratamiento de la **cuota baja de TPM**: subirla temporalmente para las pasadas o medir la latencia
  sin estrangular, y dejar escrito cuál se hizo.
- La tabla antes/después: tasas con intervalo de Wilson, preguntas que cambian de estado entre Gemini y
  Azure, estabilidad entre las tres pasadas y latencia por tramo.

Skills: `/tdd`, `/codebase-design`. Resultado: código en el repo y la tabla medida, con la lectura
honesta del resultado.

## Antes de desplegar nada (precondiciones, del ticket de la cuenta)

1. **Confirmar los umbrales del presupuesto** (20 %, 40 % y 80 % de 25 €, más la previsión) y que los avisos
   llegan al correo. Es la única protección de gasto que no actúa sola.
2. **Vaciar o borrar el grupo de East US**, si sigue existiendo.
3. Desplegar con `Standard` regional en `westeurope`, una **capacidad baja** (≈ 20 en miles de TPM, unidad
   de memoria) y **verificar el precio** en la página de precios y en Cost Management tras la primera
   llamada. Cuota actual: 200.

## Progreso (1-nov-2026): el código está hecho; falta medir

Ticket aún **abierto**: el entorno del agente no llega a Azure, así que el cliente se probó con tests sin
red (respx y un token de mentira) y **no se ha ejecutado contra el servicio real**.

### Entregado (rama `azure-rag/mapa`)
- `generacion/azure_openai.py`: `AzureOpenAIModelo` como `ModeloDeLenguaje`. **Autenticación con Entra ID**
  (`DefaultAzureCredential`, sin ninguna clave: en local usa `az login`, desplegado usará la identidad
  gestionada, con el mismo código). El token se pide **en cada intento**, porque caduca. Tarifa
  **obligatoria y explícita**. `temperature` 0, JSON simple, prompt v2 intacto.
- **`Estado.BLOQUEADO`**: un 400 con `content_filter` (el prompt) o un `finish_reason` de filtro (la salida)
  se convierten en ese estado. Cuenta como callarse y el resumen lo desglosa (`Resumen.bloqueadas`). El
  informe estático lo distingue de un fallo del modelo. **Las formas exactas del error son las de la
  investigación, sin verificar:** si aparece un bloqueo real, hay que mirar el cuerpo del error.
- CLI: `--proveedor azure`, `--despliegue`, `--precio-entrada` / `--precio-salida` (obligatorios con Azure,
  y fallan **antes** de tocar el corpus) y `--pasadas N`. Nueva `generacion comparar`.
- `generacion comparar`: tasas con Wilson, preguntas que cambian de estado (`mejora`, `empeora`,
  `inestable`), estabilidad entre pasadas y latencia por tramo. Conclusión por defecto: «sin diferencia
  demostrable». No mide el contenido: eso lo hace el juez por pasada.
- Dependencia nueva: `azure-identity` 1.27.0.
- Pruebas: cliente, bloqueos, CLI y comparación. `ruff`, `mypy` y `pytest` en verde.

### Precondiciones antes de desplegar (del ticket de la cuenta)
1. Confirmar los **umbrales del presupuesto** (20 %, 40 %, 80 % de 25 €, más previsión) y que los avisos llegan.
2. Vaciar o borrar el **grupo de East US**, si sigue existiendo.

### Cómo ejecutarlo (lo hace Santiago; PowerShell; comandos de Azure *de memoria, sin verificar*)
1. **Recurso de Azure OpenAI** en West Europe (el nombre debe ser único; el dominio personalizado es
   necesario para Entra ID):
   `az cognitiveservices account create --name <recurso> --resource-group <grupo> --location westeurope --kind OpenAI --sku S0 --custom-domain <recurso>`
2. **Rol de datos** (ser propietario no basta):
   `$id = az cognitiveservices account show --name <recurso> --resource-group <grupo> --query id -o tsv`
   `az role assignment create --assignee "<tu correo>" --role "Cognitive Services OpenAI User" --scope $id`
3. **Despliegue** `Standard` regional con capacidad baja (en miles de TPM, de memoria):
   `az cognitiveservices account deployment create --name <recurso> --resource-group <grupo> --deployment-name gpt-4-1-mini --model-name gpt-4.1-mini --model-version 2025-04-14 --model-format OpenAI --sku-name Standard --sku-capacity 20`
4. **`.env`:** `AZURE_OPENAI_ENDPOINT=https://<recurso>.openai.azure.com` y
   `AZURE_OPENAI_DEPLOYMENT=gpt-4-1-mini`. Sin claves. Si el servicio rechaza la versión de la API, ajustar
   `AZURE_OPENAI_API_VERSION`.
5. **Precio:** leer el de `gpt-4.1-mini` en `Standard` regional (página de precios o calculadora de Azure).
   Para la prueba de humo vale provisionalmente el de Global (0,40 / 1,60 $ por millón), sabiendo que no
   es el definitivo; **antes de las tres pasadas hay que poner el real**.
6. **Prueba de humo:**
   `uv run rag-lopd generacion preguntar "¿En qué plazo debe notificarse una violación de seguridad?" --proveedor azure --precio-entrada <E> --precio-salida <S>`
7. **Subir la cuota temporalmente** para las pasadas (con 20 las tres tardarían ≈ 45 min, y los reintentos por
   límite de uso inflarían la latencia medida): repetir el paso 3 con `--sku-capacity 60`. Al terminar,
   volver a 20.
8. **Tres pasadas:**
   `uv run rag-lopd generacion evaluar --proveedor azure --precio-entrada <E> --precio-salida <S> --pasadas 3`
9. **Juez** sobre cada una de las tres: `uv run rag-lopd generacion juzgar data\runs\<pasada>.jsonl`
10. **Comparar** con la línea base de Gemini del 22-oct:
    `uv run rag-lopd generacion comparar data\runs\gemini-3.5-flash-lite-promptv2-k10-20261022-114306.jsonl data\runs\<azure-p1>.jsonl data\runs\<azure-p2>.jsonl data\runs\<azure-p3>.jsonl --salida data\comparacion-generacion.md`
11. Pegar las salidas (sin claves ni identificadores). Después se verifica el coste real en **Cost Management**
    y se cierra el ticket con la tabla.

### Bloqueo en el paso 1 (2-nov-2026)
`az cognitiveservices account create` en **westeurope** devolvió `RequestDisallowedByAzure`: "The selected
region is currently not accepting new customers" (https://aka.ms/locationineligible). **No es el nombre del
recurso.** Hay que elegir otra región europea. Pendiente: comprobar cuáles aceptan Azure OpenAI para esta
suscripción y su cuota de `gpt-4.1-mini` (ver paso 3 del ticket).

### Prueba de humo superada (2-nov-2026)
- Recurso `oai-rag-lopd-santi` en **Suecia Central** (West Europe rechazó la creación). Rol *Cognitive Services
  OpenAI User* asignado. Despliegue `gpt-4-1-mini` (`gpt-4.1-mini` 2025-04-14, Standard, capacidad 20) creado.
- `generacion preguntar --proveedor azure` respondió `responde`, con la cita `rgpd:art-33` y el plazo de 72 h.
  4.855 tokens de entrada y 127 de salida: **0,00215 $ con la tarifa provisional de Global**.
- **Pendiente antes de las tres pasadas:** la tarifa real de Standard en Suecia Central (se pasa con
  `--precio-entrada` / `--precio-salida`).

### Resultados: tres pasadas de Azure (2-nov-2026), juzgadas con el juez j1 y comparadas con Gemini (22-oct)

**Tasas** (todas con intervalo de Wilson; el "antes" es Gemini 3.5 Flash-Lite, prompt v2):

| Métrica | Gemini | Azure p1 | Azure p2 | Azure p3 |
| --- | --- | --- | --- | --- |
| Sobre-respuesta | 1/16 (6 %) | 2/16 (12,5 %) | 2/16 (12,5 %) | 2/16 (12,5 %) |
| Abstención indebida | 3/34 (8,8 %) | 0/34 | 1/34 | 0/34 |
| Exactitud (juez) | 27/34 (79,4 %) | 30/34 (88,2 %) | 29/34 (85,3 %) | 29/34 (85,3 %) |

Los intervalos se solapan en todas. **Sin diferencia demostrable.** La cita cubre la fuente cambia de base
(31 para Gemini, 33-34 para Azure) porque Azure contesta más preguntas.

**Cambios de estado (comportamiento):** e-021, e-024 y e-027 pasan de callar a contestar en las tres pasadas.
e-044 pasa de callar a contestar en las tres. e-047 es inestable (contesta, calla, contesta).

**Contenido (juez), inestable entre pasadas:** e-010 (incorrecta / correcta / parcial), e-044 (incorrecta /
parcial / incorrecta), e-026 (parcial / parcial / correcta), y e-014, e-024, e-032 aparecen en una sola pasada.
La comparación automática solo mide el comportamiento: el "1 de 50" del informe **no** mide la estabilidad
del contenido.

**Hallazgo de contenido, no de tasa:** en e-044 Azure afirma una cuantía mínima de 40.000 € que la norma no
fija (el RGPD solo fija máximos). Es un error de contenido grave y se cuenta en las tres pasadas, aunque con
n = 2 no se puede hablar de tasa.

**Latencia:** p50 ≈ 3,8–4,7 s frente a 1,4 s de Gemini; p95 ≈ 34 s, casi todo en la generación. No está
explicada (posible cola por la cuota o por reintentos; no verificado).

**Coste:** 0,14 $ por pasada con la tarifa de trabajo (East US × 1,10, **deducción, no verificada**).

**Pendiente:** bajar la capacidad del despliegue de 60 a 20; revisar a mano e-010, e-026 y e-044; decidir
cómo se reporta e-044 en el README (¿error de contenido o fallo del juez?).

### Revisión a mano de e-010, e-026 y e-044 (6-nov-2026)

Textos de las respuestas leídos en las tres pasadas; clasificación verificada en `lopdgdd:art-73` y `art-74`.

- **e-010 (factual): inconsistencia del modelo, no del juez.** La pasada 2 menciona bloquear los datos
  (correcta). Las pasadas 1 y 3 solo citan los arts. 16, 17 y 18 RGPD (incorrectas o parciales). La
  referencia (`lopdgdd:art-32.1`) es el bloqueo, y no está en el RGPD.
- **e-026 (cruzada): el juez acierta.** Las pasadas 1 y 2 dicen que no comunicar la brecha al afectado es
  "infracción leve que prescribe al año". Es **grave, dos años** (`lopdgdd:art-73.s`). La pasada 3 no lo dice.
- **e-044 (trampa): error real en las tres pasadas.** Azure afirma una multa mínima y la clasifica como leve.
  Dos errores: el RGPD no fija mínimos, y el incumplimiento del art. 33 es **grave** (`art-73.r`), no leve.
  La pasada 2 cita el art. 74 (leves) para algo que está en el art. 73. El juez la marcó "parcial", y
  debería ser incorrecta: la sobre-respuesta grave es **1/2 en las tres pasadas**, no 0/2 en la 2.

**Métricas afectadas:** ninguna tasa cambia de forma material. La sobre-respuesta grave pasa a 1/2 en la
pasada 2. El juez j1 subestima e-044 en la pasada 2. Corregirlo exige una rúbrica nueva (j2) y repetir el juicio;
no se hace ahora.

### Capacidad restaurada (6-nov-2026)
Despliegue `gpt-4-1-mini` en `oai-rag-lopd-santi`: `sku.capacity` = **20** (confirmado con
`deployment show --query sku`). La cuota de 60 se usó solo durante las pasadas. Cambio hecho desde el portal,
porque `deployment update` no existe con esos argumentos en la CLI 2.91.0.

### Tarifa real de Standard regional (7-nov-2026), leída de la página de precios

- `gpt-4.1-mini` (2025-04-14), fila **Regional**: entrada **$0,49**, salida **$1,94** por millón de tokens
  (caché de entrada: $0,13, no usada por el código).
- **Corrección:** la tarifa de trabajo anterior (0,484 / 1,936) estaba mal derivada. Usó la fila Data Zone
  (0,44 / 1,76) como si fuera el regional de East US. El "+10 %" no era un dato. La diferencia real es
  pequeña: unos 0,002 $ por pasada.
- **Pendiente:** confirmar que la región seleccionada en la página es **Sweden Central**, porque la tabla
  no lo indica.
- **Nota:** el código no descuenta tokens en caché, así que el coste calculado puede ser algo mayor que el real.
