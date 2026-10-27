# Cuenta de Azure con límite de gasto y alerta

Type: task
Status: open
Blocked by: 01, 02, 04

## Question

Crear la suscripción de Azure y dejarla lista y **segura para gastar**, sin quemar el crédito antes de
tiempo. Bloqueado a propósito por la investigación: si el crédito de una suscripción nueva caduca a
los pocos días (a confirmar en los tickets de Azure AI Search, modelos y despliegue), no se crea hasta
saber qué hace falta aprovisionar y en qué orden.

Checklist (HITL: lo hace Santiago con una lista precisa, o con el agente si hay `az` autenticado):

- Crear la suscripción y un grupo de recursos para este proyecto (región decidida con las
  investigaciones: disponibilidad del modelo y del nivel gratuito de AI Search).
- Fijar un **presupuesto con alertas** (y límite de gasto si la suscripción lo permite).
- Instalar y autenticar `az` en la máquina de Santiago.
- Anotar dónde queda cada dato que los tickets siguientes necesitan (nombre del servicio, región,
  endpoints), **sin pegar claves en ningún fichero versionado**.

La respuesta registra qué se hizo y los datos no secretos que dependen de ello.
