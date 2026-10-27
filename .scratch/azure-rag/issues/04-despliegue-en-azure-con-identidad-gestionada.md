# Despliegue gratuito en Azure con identidad gestionada y Key Vault

Type: research
Status: open

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
