# Confirmar a mano los datos críticos que no se pudieron verificar

Type: task
Status: open

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
