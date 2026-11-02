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
