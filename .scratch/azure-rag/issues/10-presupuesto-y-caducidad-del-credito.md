# Presupuesto: sin cuota de modelos no hay Azure OpenAI gratis, y pagar quita el límite de gasto

Type: grilling
Status: claimed

## Question

La decisión de partida ("solo niveles gratuitos y el crédito de una suscripción nueva, con alerta de
gasto") **ya no se sostiene**. Lo confirmado el 27-oct-2026 (ver el ticket de datos críticos):

- Con la cuenta gratuita, **todos los modelos de Azure OpenAI / Foundry tienen cuota 0**. Para usarlos
  hay que pasar a **pago por uso**, y eso **quita el límite de gasto** (el único tope duro). El crédito
  restante sigue disponible hasta completar los 30 días.
- Los presupuestos y alertas de Azure **solo avisan** (se evalúan cada 24 h): no paran nada.
- El ranker semántico exige AI Search **Basic o superior**, no el nivel Free (≈ 73,73 USD/mes según
  terceros, sin verificar; si se factura por horas es otra cuenta distinta).

Lo que ayuda a acotar el riesgo, con las cifras que hay:
- Una pasada de 50 preguntas cuesta ≈ **0,06–0,24 $** según el modelo (≈ 280.000 tokens de entrada y
  5.500 de salida; sin contar tokens de razonamiento de los `gpt-5*`).
- AI Search Free (50 MB, 3 índices) cubre el corpus y **no cuesta nada**; Container Apps con mínimo de 0
  réplicas y la cuota gratuita tampoco debería costar; Key Vault es despreciable.
- Lo que sí puede dispararse es **la API expuesta a un tercero** que gaste tokens a tu cuenta.

Decidir:

- ¿Se **acepta el pago por uso** con alertas desde el primer día y una disciplina explícita de apagado
  (borrar el grupo de recursos al terminar), o se **revierte** la decisión de pasar el generador a Azure
  y se mantiene Gemini?
- Si se acepta: ¿qué **tope** se fija, y qué **mecanismos de contención** se aplican? Ideas a verificar:
  desplegar el modelo con una cuota de TPM baja (limita el gasto por minuto), API sin acceso externo o
  con autenticación, y una alerta de presupuesto con importe bajo.
- ¿Se paga un **Basic puntual** de AI Search para probar el ranker semántico, o queda fuera del
  experimento? (Lo decide también el ticket del diseño del experimento.)
- ¿En qué **región** se despliega (no Spain Central), y se usa Data Zone UE por el RGPD (≈ 10 % más)?

Entrevista con `/grilling`. Resultado: la decisión de presupuesto, el tope, los mecanismos de contención
y la región, que consumirá el ticket de la cuenta de Azure.
