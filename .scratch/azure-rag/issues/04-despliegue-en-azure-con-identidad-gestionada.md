# Despliegue gratuito en Azure con identidad gestionada y Key Vault

Type: research
Status: resolved (27-oct-2026)

## Question

¿Dónde y cómo se despliega una API FastAPI y una UI Streamlit en Azure sin salirse del crédito y
dejándola apagable, con secretos en Key Vault y permisos mínimos?

- Opciones de cómputo: Azure Container Apps (¿escala a cero?, cuota gratuita mensual), App Service
  (¿nivel gratuito con Python y contenedores?), Container Instances. Cuál encaja y cuánto cuesta.
- Azure Key Vault: coste real a este volumen, y cómo lo lee una aplicación con identidad gestionada
  (referencias a secretos frente a SDK).
- **Identidad gestionada**: asignada por el sistema o por el usuario; qué roles RBAC mínimos hacen
  falta para leer secretos (Key Vault Secrets User), consultar Azure AI Search (Search Index Data
  Reader) y llamar al modelo (Cognitive Services OpenAI User o similar).
- Cómo se apaga y se vuelve a levantar: ¿qué se cobra con todo parado?
- Presupuestos y alertas: cómo se fija un límite de gasto real y no solo un aviso en una suscripción nueva.
- Construir y publicar la imagen: Azure Container Registry (coste), o alternativas gratuitas.

Entregable: un documento con tabla comparativa y recomendación, cada dato con su fuente y marcado
como **verificado** o **no verificado**.

## Answer

**Recomendación** (certeza media-alta en arquitectura, baja en costes): **Azure Container Apps, plan
Consumption**, dos apps (`api` y `ui`) y mínimo de 0 réplicas.

**Verificado** en el Markdown fuente de la documentación de Microsoft:
- Cuota gratuita de Container Apps: 180.000 vCPU-s, 360.000 GiB-s y 2 M de peticiones al mes por
  suscripción; con 0 réplicas no hay cargo de consumo.
- Roles con su id: Key Vault Secrets User, Search Index Data Reader, Cognitive Services OpenAI User y
  AcrPull. Propuesta: una identidad de usuario para la `api` con los tres primeros, cada uno en el ámbito
  de su recurso; la `ui` no necesita ninguno. Con identidad gestionada, Search y el modelo no necesitan
  secreto: el vault solo guarda claves de terceros (DeepSeek, y el embedder por API si se usa).
- Imágenes: Azure Container Registry no tiene nivel gratuito y su compilación en la nube está pausada
  para créditos gratuitos; se propone **construir en GitHub Actions y publicar en GHCR**.

**Riesgo principal (verificado):** el crédito de la cuenta gratuita **caduca a los 30 días**; para seguir
hay que pasar a pago por uso, y eso **elimina el límite de gasto**. Los presupuestos de Azure **solo
avisan** (se evalúan cada 24 h): no paran nada. Choca con "solo gratis y crédito, con alerta de gasto".
Además, una API con acceso externo permite que cualquiera gaste el crédito (opciones: acceso interno,
restricciones de IP o autenticación integrada).

**No verificado:** todos los precios, si una acción de presupuesto puede desactivar una revisión de
Container Apps, y los detalles de la cuenta gratuita.

**Informe completo:** rama `research/despliegue-azure-identidad` (de la que no se ha hecho PR), fichero `docs/research/despliegue-azure-identidad.md`.
Cada dato del informe va marcado como verificado o no verificado, y termina con la lista de lo que hay
que confirmar a mano.
