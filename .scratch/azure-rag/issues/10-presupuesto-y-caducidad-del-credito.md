# Presupuesto: sin cuota de modelos no hay Azure OpenAI gratis, y pagar quita el límite de gasto

Type: grilling
Status: resolved (28-oct-2026)

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

## Answer

Decidido con Santiago el 28-oct-2026. **Se acepta el pago por uso en Azure, con tope y contención.**

### Decisiones
- **Tope de bolsillo: 25 € para todo el proyecto en Azure.** Azure no lo hace cumplir (sin límite de
  gasto): lo garantizan las contenciones de abajo y la atención.
- **Se acepta el pago por uso** (hace falta tarjeta) y el generador **se queda en Azure**; no se revierte a
  Gemini. El crédito de 200 $ sigue disponible hasta completar los 30 días desde el alta, así que el
  trabajo se concentra en esa ventana y el grupo de recursos se **borra al terminar cada fase**.
- **Contención del gasto:**
  - **Alertas de presupuesto a 5, 10 y 20 €.** Solo avisan y se evalúan cada 24 h.
  - **Cuota baja de TPM** en el despliegue del modelo (gratis): es el único tope automático. Orden de
    magnitud *(cálculo propio, sin verificar la relación exacta cuota-TPM)*: con 20.000 TPM y
    `gpt-4.1-mini`, como máximo ≈ 0,5 $ por hora de uso continuo.
  - **La API sin acceso externo, o autenticada**, para que un tercero no gaste tokens a tu cuenta. Cuál de
    las dos se decide en el ticket de despliegue.
  - *No adoptada:* tarjeta virtual con límite bajo, que sería el único tope duro fuera de Azure. El
    riesgo residual es un error propio entre dos alertas.
- **Ranker semántico: fuera del experimento principal.** Exige AI Search Basic (≈ 73,74 $/mes, tercero,
  sin verificar), casi el triple del tope. Queda como ampliación opcional al final, solo si sobra
  presupuesto y se confirma si Basic se factura por horas. **AI Search se usa en el nivel Free.**
- **Datos: Data Zone UE** para el modelo (≈ 10 % más; el precio de `gpt-4.1-mini` en Data Zone y su
  disponibilidad en la región elegida **no están verificados**). Coherente con un proyecto de protección
  de datos: el procesamiento se queda en la UE.
- **Región de AI Search y Container Apps:** una región europea con los límites altos, **no Spain
  Central**; la concreta se fija en el ticket de la cuenta con la disponibilidad real.

### Cifras de apoyo (precios confirmados el 27-oct-2026)
Una pasada de 50 preguntas (≈ 280.000 tokens de entrada, 5.500 de salida): `gpt-4.1-mini` ≈ 0,12 $,
`gpt-5-mini` ≈ 0,08 $, `gpt-5.4-nano` ≈ 0,06 $ y `gpt-5.4-mini` ≈ 0,24 $ (+ ≈ 10 % en Data Zone), sin
contar los tokens de razonamiento de los `gpt-5*`. Lo esperable queda muy por debajo del tope.
