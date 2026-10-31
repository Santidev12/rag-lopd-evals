# Cuenta de Azure, presupuesto y alertas

Type: task
Status: claimed
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
