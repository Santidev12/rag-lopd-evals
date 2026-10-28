# Cliente de Azure OpenAI y línea base de generación (3 pasadas)

Type: task
Status: open
Blocked by: 06

## Question

Implementar la decisión del ticket del generador y medirla:

- Un cliente de Azure OpenAI que cumpla el contrato `ModeloDeLenguaje` (`completar(sistema, usuario)`),
  con `gpt-4.1-mini` en Data Zone UE, `temperature` 0 y JSON simple, sin tocar el prompt v2. Decidir
  dentro del ticket cómo se autentica en local (Entra ID con `DefaultAzureCredential` o clave en `.env`)
  sin dejar claves en el repositorio.
- Su tarifa explícita en `buscar_tarifa` (precio de Data Zone UE verificado en la cuenta, no adivinado).
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
