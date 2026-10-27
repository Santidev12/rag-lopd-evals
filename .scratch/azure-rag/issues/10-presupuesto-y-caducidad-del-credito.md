# Presupuesto: el crédito caduca a los 30 días y el límite de gasto desaparece al pasar a pago

Type: grilling
Status: open
Blocked by: 11

## Question

La investigación de despliegue encontró algo que contradice una decisión de partida. Se acordó "solo
niveles gratuitos y el crédito de una suscripción nueva, con alerta de gasto", pero:

- El crédito de la cuenta gratuita **caduca a los 30 días**.
- Para seguir hay que pasar a pago por uso, y eso **elimina el límite de gasto** (el único tope duro).
- Los presupuestos de Azure solo **avisan** (se evalúan cada 24 h): no paran nada.
- El mapa pide un demo "desplegado pero apagable" y una verificación final, que pueden caer fuera de los
  primeros 30 días.

Decidir, con los datos que traiga el ticket de confirmación a mano:

- ¿Se hace todo el trabajo de Azure **dentro de la ventana de 30 días**, con el límite de gasto activo, y
  se planifica el orden para que quepa (retrieval, generador, despliegue, agente)?
- ¿O se acepta pasar a pago por uso con un presupuesto de aviso y una disciplina explícita de apagado
  (borrar el grupo de recursos al terminar cada sesión)?
- ¿Qué se recorta del alcance si no cabe en la ventana?
- Con la API expuesta, ¿cómo se evita que alguien gaste el crédito (acceso interno, restricciones de IP,
  autenticación)?

Entrevista con `/grilling`. Resultado: la decisión de presupuesto y el calendario de la ventana, que
consumirá el ticket de la cuenta de Azure.
