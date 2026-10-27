# Confirmar a mano los datos críticos que no se pudieron verificar

Type: task
Status: resolved (27-oct-2026)

## Question

Las cinco investigaciones se hicieron sin acceso a `learn.microsoft.com` ni a `azure.microsoft.com`, y
dejaron una lista de datos **no verificados**. Casi todos pueden esperar al momento de usarlos, pero
**cuatro decisiones del mapa dependen de unos pocos**. Este ticket es solo esa lista corta: abrir cada
página en un navegador y apuntar lo que dice, con la fecha.

Es HITL: lo hace Santiago, y el agente anota los valores en la respuesta. No hace falta tener cuenta de
Azure para ninguno.

**Para el experimento de retrieval** (ticket del diseño del experimento):
1. Límites del nivel **Free** de AI Search: almacenamiento, nº de índices, cuota del índice vectorial,
   dimensiones máximas. https://learn.microsoft.com/en-us/azure/search/search-limits-quotas-capacity y
   https://learn.microsoft.com/en-us/azure/search/vector-search-index-size
2. ¿Está el **ranker semántico** en Free, o hay 1.000 consultas gratis al mes (los fragmentos se
   contradicen)? https://learn.microsoft.com/azure/search/semantic-search-overview y
   https://learn.microsoft.com/azure/search/search-sku-tier
3. ¿Puede un servicio Free ascender de nivel? (misma página de niveles).
4. Constante `k` de RRF y si hay peso para el texto: https://learn.microsoft.com/azure/search/hybrid-search-ranking

**Para el generador** (ticket del generador en Azure):
5. **Precios** de `gpt-4.1-mini`, `gpt-5-mini`, `gpt-5.4-mini` y `gpt-5.4-nano`:
   https://azure.microsoft.com/pricing/details/azure-openai/
6. ¿Exigen registro de acceso los `gpt-5*` en una suscripción nueva?
   https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/openai/limited-access
7. Salida JSON estricta y `temperature` en los modelos de razonamiento:
   https://learn.microsoft.com/azure/ai-foundry/openai/how-to/structured-outputs y `.../how-to/reasoning`

**Para el presupuesto** (ticket del presupuesto y la caducidad del crédito):
8. **Crédito de la cuenta gratuita:** importe, 30 días, qué pasa con el límite de gasto al mejorar la
   cuenta, y si cubre Azure OpenAI / Foundry: https://azure.microsoft.com/free/ y
   https://azure.microsoft.com/pricing/purchase-options/azure-account
9. Precio de **Container Apps** fuera de la cuota gratuita y de **Key Vault**:
   https://azure.microsoft.com/pricing/details/container-apps/ y
   https://azure.microsoft.com/pricing/details/key-vault/

**Lo que NO se puede confirmar sin cuenta** (se mira dentro del ticket de la cuenta de Azure): la cuota
real de cada modelo en la región elegida, si el filtro de contenido por defecto bloquea alguna de las 50
preguntas, y el arranque en frío de la UI.

La respuesta recoge cada valor con su fecha y la URL, y marca si contradice lo que dijo la investigación.

## Answer

Valores leídos por Santiago en las páginas oficiales el **27-oct-2026**. Lo marcado *(sin verificar)* no
se pudo leer o es deducción.

### Lo que contradice a la investigación
- **La cuenta gratuita no sirve para los modelos.** Con la oferta Free Trial, todos los modelos de Azure
  OpenAI / Foundry tienen **cuota 0 TPM**. Hay que pasar a pago por uso para desbloquearla, y eso
  **quita el límite de gasto**. El crédito que quede sigue disponible hasta completar los 30 días.
  (Documentación antigua decía 1K TPM; los casos recientes coinciden en 0.)
- **El ranker semántico no está en el nivel Free del servicio.** No se contradecían las fuentes: su "plan
  gratuito" (tope de 1.000 consultas/mes) existe, pero el servicio tiene que ser **Basic o superior**.

### Bloque C. Dinero
- **Crédito:** 200 $ para gastar en los 30 días desde el alta. **Límite de gasto** activo por defecto e
  igual al crédito; no se puede cambiar el importe, solo quitarlo.
- **Al terminar:** a los 30 días o al agotar el crédito, lo que llegue antes, hay que pasar a pago por
  uso (quitando el límite). Si no, la cuenta y los productos se desactivan.
- **Exclusiones:** el crédito no cubre productos de terceros ni de Azure Marketplace.
- **Container Apps:** cuota gratuita confirmada (180.000 vCPU-s, 360.000 GiB-s, 2 M de peticiones al
  mes por suscripción). Precio por encima de la cuota *(sin verificar: la página lo carga con
  JavaScript)*: ≈ 0,000024 $/vCPU-s activo y 0,40 $ por millón de peticiones.
- **Key Vault Standard:** ≈ 0,03 $ por 10.000 operaciones *(sin verificar)*; despreciable a este volumen.

### Bloque B. Modelos (Global Standard, USD por millón de tokens, entrada / salida)
| Modelo | Entrada | Salida |
| --- | --- | --- |
| `gpt-4.1-mini` | 0,40 | 1,60 |
| `gpt-5-mini` | 0,25 | 2,00 |
| `gpt-5.4-mini` | 0,75 | 4,50 |
| `gpt-5.4-nano` | 0,20 | 1,25 |

- **Región y RGPD:** en Data Zone (UE), `gpt-5.4-mini` sale a 0,825–0,90 $ de entrada y 4,95–5,40 $ de
  salida (≈ 10 % más).
- **Acceso:** `gpt-5-mini` no requiere registro; `gpt-5.4` completo es de acceso limitado;
  `gpt-5.4-mini` y `gpt-5.4-nano` *(sin confirmar: comprobar en el catálogo de Foundry al desplegar)*.
- **Salida JSON estricta:** los cuatro la admiten.
- **`temperature`:** los `gpt-5*` **no** la admiten (solo el valor por defecto, 1; tampoco `top_p`,
  `logprobs` ni `max_tokens`). **`gpt-4.1-mini` es el único de los cuatro que acepta `temperature` 0.**

### Bloque A. Azure AI Search (documentación actualizada el 17-ago-2026)
- **Free:** 50 MB de almacenamiento sin posibilidad de escalar, 3 índices, 4096 dimensiones por campo
  vectorial. La tabla no da tamaño de índice vectorial para Free (solo desde Basic: 5 GB).
- **Región:** Spain Central **no** tiene los límites altos: usar otra región europea.
- **Ascenso:** un servicio Free no puede pasar a pago; hay que crear otro. Solo se cambia entre Basic y
  Standard, y solo hacia arriba.
- **RRF:** `k` es una constante fija de 60, **no configurable**. Se puede dar **peso a las consultas
  vectoriales** desde la API 2024-05-01-preview; no hay parámetro de peso para el texto (favorecer el
  texto sería bajar el peso del vector por debajo de 1: *deducción, sin verificar*).

### Lo que no se pudo confirmar sin cuenta
La cuota real por modelo y región, si el filtro por defecto bloquea alguna de las 50 preguntas, y el
arranque en frío de la UI. Se miran en el ticket de la cuenta de Azure.
