# Cuenta de Azure, presupuesto y alertas

Type: task
Status: resolved (31-oct-2026)
Blocked by: 01, 02, 04, 10

Nota: **crear la cuenta arranca la ventana de 30 días del crédito.** Se hace al empezar este ticket,
con las decisiones de presupuesto, generador y diseño del experimento ya cerradas.

## Question

Crear la suscripción de Azure y dejarla lista y **segura para gastar**, sin quemar el crédito antes de
tiempo. Bloqueado a propósito por la investigación: si el crédito de una suscripción nueva caduca a
los pocos días (a confirmar en los tickets de Azure AI Search, modelos y despliegue), no se crea hasta
saber qué hace falta aprovisionar y en qué orden.

Checklist (HITL: lo hace Santiago con una lista precisa, o con el agente si hay `az` autenticado):

- Crear la suscripción y un grupo de recursos para este proyecto, en la región que decida el ticket de
  presupuesto (**no Spain Central**, que no tiene los límites altos de AI Search).
- **Pasar a pago por uso** (la cuenta gratuita tiene cuota 0), lo que quita el límite de gasto y pide
  tarjeta. Decidido en el ticket de presupuesto (tope de 25 €). Las **alertas a 5, 10 y 20 €** se crean
  antes que cualquier recurso.
- Elegir la región (europea, no Spain Central) con la disponibilidad real de `gpt-4.1-mini` en Data Zone UE
  y comprobar el precio ahí.
- Al desplegar el modelo, fijar una **cuota baja de TPM** (≈ 20.000 como punto de partida) como tope
  automático.
- Anotar la regla de apagado: borrar el grupo de recursos al terminar cada fase.
- Fijar un **presupuesto con alertas** (y límite de gasto si la suscripción lo permite).
- Instalar y autenticar `az` en la máquina de Santiago.
- Tras la primera llamada al modelo, comprobar en Cost Management que el crédito la cubre, y mirar la
  **cuota real** de cada modelo candidato en la región elegida (puede ser 0).
- Anotar dónde queda cada dato que los tickets siguientes necesitan (nombre del servicio, región,
  endpoints), **sin pegar claves en ningún fichero versionado**.

La respuesta registra qué se hizo y los datos no secretos que dependen de ello.

## Progreso (31-oct-2026, ticket aún abierto)

Hecho por Santiago:
- **Alta de la cuenta: 31-oct-2026.** El crédito de 200 $ **vence el 30-nov-2026**. La ventana de trabajo es
  de 30 días desde hoy (el calendario orientativo de semanas se cuenta desde esa fecha).
- **Presupuesto creado** (umbrales exactos *sin confirmar*: debían ser 20 %, 40 % y 80 % de 25 €, más una
  previsión al 100 %).
- **Pasado a pago por uso** (límite de gasto quitado; el crédito restante sigue hasta el 30-nov).
- `az` **instalado** con `winget` (versión 2.91.0); la ventana de PowerShell no lo encontraba por no haber
  recargado el `PATH`. Falta `az login` y confirmar la suscripción.

Pendiente, y por qué no se cierra:
- **Región:** Santiago indicó **East US**, que contradice la decisión de **Data Zone UE** del ticket de
  presupuesto (en East US el procesamiento sería en EE. UU.). Sin decidir si es deliberado: la recomendación
  es comprobar primero regiones europeas y dejar East US como plan B documentado.
- **Modelo, precio y cuota (TPM):** lo único recibido fue "sin cargos para el modelo en East US en octubre",
  que se interpreta como sin gasto todavía, no como un precio. Falta el **nombre exacto del modelo**
  (`gpt-4.1-mini` frente a `gpt-4o-mini`), su **precio** y su **cuota real** en la región elegida.
- Nombre de la suscripción (`az account show --query name`), sin identificadores.

### Actualización (31-oct-2026): región cambiada a West Europe

Santiago ha creado "uno nuevo en **West Europe**" (región europea, que resuelve el conflicto con Data Zone
UE). **Sin confirmar qué se creó** (¿grupo de recursos, recurso de Azure OpenAI/Foundry?), si el de East US
sigue existiendo, ni la disponibilidad de `gpt-4.1-mini` con despliegue **Data Zone (UE)** en West Europe.
Siguen sin recibirse: nombre exacto del modelo, precio, cuota (TPM), umbrales del presupuesto y nombre de
la suscripción.

Confirmado por Santiago: lo creado en West Europe es el **grupo de recursos** (sin recursos de modelo todavía).
Siguen pendientes la disponibilidad de `gpt-4.1-mini` con Data Zone (UE) en West Europe, su cuota y precio,
el estado del grupo de East US, los umbrales del presupuesto y el nombre de la suscripción.

### Disponibilidad confirmada en West Europe (31-oct-2026, salida de `az cognitiveservices model list`)

- **Suscripción:** "Azure subscription 1 - santiago" (autenticado con `az`; funciona).
- **`gpt-4.1-mini`, versión `2025-04-14`, disponible en `westeurope`** con los tipos de despliegue `Standard`,
  `GlobalStandard`, **`DataZoneStandard`**, `DeveloperTier`, `GlobalProvisionedManaged`,
  `DataZoneProvisionedManaged`, `GlobalBatch` y `DataZoneBatch`. La salida trae la entrada duplicada con el
  mismo contenido.
- Que `DataZoneStandard` en `westeurope` sea la zona **UE** es de memoria y se confirma al desplegar (el
  portal indica la zona).
- Pendiente: **cuota** (TPM) de ese tipo de despliegue, **precio** en Data Zone UE, estado del grupo de East
  US y umbrales del presupuesto.

## Answer

Hecho por Santiago el 31-oct-2026; salidas leídas por el agente.

- **Cuenta:** alta el **31-oct-2026**; el crédito de 200 $ **vence el 30-nov-2026**. Suscripción
  "Azure subscription 1 - santiago", ya **en pago por uso** (límite de gasto quitado; el crédito restante
  sigue hasta el 30-nov). **Presupuesto creado**; los umbrales exactos **no están confirmados**.
- **Región: West Europe** (europea). Santiago había creado primero algo en East US y lo cambió; en West
  Europe existe un **grupo de recursos** (sin recursos de modelo). **Estado del grupo de East US: sin
  confirmar** (hay que vaciarlo o borrarlo).
- `az` **2.91.0** instalado y autenticado.
- **`gpt-4.1-mini`, versión `2025-04-14`, disponible en `westeurope`**, pero con esta **cuota** (`limit`,
  unidad sin mostrar; probablemente miles de TPM, de memoria):

| Tipo de despliegue | Cuota |
| --- | --- |
| **`DataZoneStandard`** | **0** |
| `Standard` (regional) | 200 |
| `GlobalStandard` | 200 |
| `GlobalBatch` / `DataZoneBatch` | 50.000 |

### Decisión: Standard regional en West Europe
Data Zone Standard tiene **cuota 0** en una suscripción nueva: no se puede desplegar. Se usa **`Standard`
regional en West Europe** (cuota 200, de sobra para la cuota baja de ≈ 20.000 TPM). Cumple la intención de
la decisión de Data Zone UE (el procesamiento se queda en Europa; que el regional lo mantenga **dentro de
la región** es de memoria). **Enmienda** a los tickets de presupuesto y del generador.

### Sin verificar / pendiente
- **Precio** de `gpt-4.1-mini` en `Standard` regional (se verifica al desplegar y en Cost Management).
- La **unidad** del límite de cuota, y que regional mantenga el procesamiento en la región.
- Si Data Zone se pudiera pedir con un aumento de cuota (descartado por calendario).
- Umbrales del presupuesto y estado del grupo de East US: se comprueban **antes de desplegar** (ticket del
  cliente de Azure OpenAI).

### Cómo releer la cuota (PowerShell 5.1; los paréntesis son necesarios)
```powershell
(az cognitiveservices usage list --location westeurope -o json | ConvertFrom-Json) | Where-Object { $_.name.value -like "*4.1-mini*" } | Select-Object currentValue, limit, @{n='nombre';e={$_.name.value}} | Format-Table -AutoSize
```
