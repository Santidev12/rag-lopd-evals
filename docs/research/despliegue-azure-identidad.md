# Despliegue gratuito en Azure con identidad gestionada y Key Vault

> Investigación del ticket 04 del mapa `azure-rag` (27-oct-2026). Pregunta: ¿dónde y cómo se despliega una API FastAPI y una UI Streamlit en Azure sin salirse del crédito, apagable, con secretos en Key Vault y permisos mínimos?

## Cómo leer este documento (método y límites)

- **verificado**: leído por mí, hoy, en el texto fuente de la documentación oficial de Microsoft. Esa documentación se publica desde el repositorio `MicrosoftDocs`; leí los ficheros Markdown "raw" (la misma fuente que renderiza learn.microsoft.com), con su `ms.date` indicado. Cada dato lleva dos enlaces: el fichero leído y la URL de Learn que un humano puede abrir.
- **no verificado**: solo en un fragmento de búsqueda, en una pregunta de Microsoft Q&A, en un blog de terceros o de memoria. No lo uses para decidir sin abrir la URL indicada.
- **Límites del entorno**: learn.microsoft.com, azure.microsoft.com y github.com no son accesibles. Sí lo era `raw.githubusercontent.com` para los repos `MicrosoftDocs/azure-docs`, `azure-management-docs`, `azure-compute-docs` y `Azure/azure-sdk-for-python`. **No pude leer** los repos que alojan las páginas de Key Vault (rbac-guide, límites), de Azure AI Search (tiers, RBAC) ni de Azure OpenAI/Foundry (RBAC). Tampoco ninguna página de precios (azure.microsoft.com): **ningún precio de este documento está verificado salvo las cuotas gratuitas de Container Apps**.
- Abreviaturas de fuentes (prefijo `raw` = `https://raw.githubusercontent.com/MicrosoftDocs/`):
  - [CA-BILL] `raw`azure-docs/main/articles/container-apps/billing.md — Learn: https://learn.microsoft.com/azure/container-apps/billing (ms.date 09-dic-2025)
  - [CA-SCALE] `.../container-apps/scale-app.md` — https://learn.microsoft.com/azure/container-apps/scale-app (19-may-2026)
  - [CA-REV] `.../container-apps/revisions.md` y `revisions-manage.md` — https://learn.microsoft.com/azure/container-apps/revisions-manage
  - [CA-MI] `.../container-apps/managed-identity.md` — https://learn.microsoft.com/azure/container-apps/managed-identity
  - [CA-SEC] `.../container-apps/manage-secrets.md` — https://learn.microsoft.com/azure/container-apps/manage-secrets
  - [CA-PULL] `.../container-apps/managed-identity-image-pull.md` — https://learn.microsoft.com/azure/container-apps/managed-identity-image-pull
  - [CA-CONT] `.../container-apps/containers.md` — https://learn.microsoft.com/azure/container-apps/containers
  - [CA-ING] `.../container-apps/ingress-overview.md` — https://learn.microsoft.com/azure/container-apps/ingress-overview
  - [CA-ENV] `.../container-apps/environment.md` y `log-options.md` — https://learn.microsoft.com/azure/container-apps/log-options
  - [CA-STICKY] `.../container-apps/sticky-sessions.md` — https://learn.microsoft.com/azure/container-apps/sticky-sessions
  - [APPSVC] `.../app-service/overview-hosting-plans.md` — https://learn.microsoft.com/azure/app-service/overview-hosting-plans (24-ago-2026)
  - [ACI-OV] `raw`azure-compute-docs/main/articles/container-instances/container-instances-overview.md y `container-instances-faq.yml` — https://learn.microsoft.com/azure/container-instances/container-instances-faq
  - [ACR-SKU] `raw`azure-management-docs/main/articles/container-registry/container-registry-skus.md — https://learn.microsoft.com/azure/container-registry/container-registry-skus
  - [ACR-TASKS] `.../container-registry/container-registry-tasks-overview.md` — https://learn.microsoft.com/azure/container-registry/container-registry-tasks-overview
  - [RBAC-SEC] `raw`azure-docs/main/articles/role-based-access-control/built-in-roles/security.md — https://learn.microsoft.com/azure/role-based-access-control/built-in-roles/security (01-jul-2026)
  - [RBAC-AI] `.../built-in-roles/ai-machine-learning.md` — https://learn.microsoft.com/azure/role-based-access-control/built-in-roles/ai-machine-learning
  - [RBAC-CONT] `.../built-in-roles/containers.md` — https://learn.microsoft.com/azure/role-based-access-control/built-in-roles/containers
  - [SPEND] `.../cost-management-billing/manage/spending-limit.md` — https://learn.microsoft.com/azure/cost-management-billing/manage/spending-limit (29-abr-2026)
  - [FREE] `.../cost-management-billing/manage/avoid-charges-free-account.md` — https://learn.microsoft.com/azure/cost-management-billing/manage/avoid-charges-free-account (03-mar-2026)
  - [BUDGET] `.../cost-management-billing/costs/tutorial-acm-create-budgets.md` — https://learn.microsoft.com/azure/cost-management-billing/costs/tutorial-acm-create-budgets
  - [BUDGET-AUTO] `.../cost-management-billing/manage/cost-management-budget-scenario.md` — https://learn.microsoft.com/azure/cost-management-billing/manage/cost-management-budget-scenario
  - [SDK-KV] `raw`Azure/azure-sdk-for-python/main/sdk/keyvault/azure-keyvault-secrets/README.md
  - [SDK-SEARCH] `raw`Azure/azure-sdk-for-python/main/sdk/search/azure-search-documents/README.md

## Resumen y recomendación

**Recomendación (certeza media-alta en la arquitectura, baja en los costes en euros):**

1. **Cómputo: Azure Container Apps, plan Consumption** (entorno "workload profiles", el predeterminado), con **dos apps**: `api` (FastAPI) y `ui` (Streamlit), mínimo de réplicas **0** (valor predeterminado). Es la única opción comparada que a la vez escala a cero sin coste de cómputo, admite contenedores y WebSockets (Streamlit los necesita) y tiene una cuota gratuita mensual documentada.
2. **Identidad**: una identidad **asignada por el usuario** para la `api` con exactamente tres roles, cada uno en el ámbito del recurso concreto (no del grupo de recursos): Key Vault Secrets User (Key Vault), Search Index Data Reader (servicio de búsqueda), Cognitive Services OpenAI User (recurso del modelo, **si el modelo es de Azure OpenAI**). La `ui` **no necesita ningún rol** si solo llama a la API. Si se tira de un registro privado, una segunda identidad de usuario solo con AcrPull.
3. **Secretos**: Key Vault con modelo de permisos RBAC; la app los consume como **referencias de secreto de Container Apps** (sin código) para las claves de terceros que sigan existiendo (DeepSeek como juez, el embedder de consulta si es una API externa). Para Search y el modelo no hay secretos: se usa `DefaultAzureCredential` con la identidad.
4. **Imagen**: construir fuera de Azure (GitHub Actions o local) y publicar en un registro **público y gratuito** (p. ej. GHCR) si la imagen no contiene nada privado; ACR Basic solo como plan B y borrándolo al acabar. `az acr build` (ACR Tasks) está documentado como **pausado para créditos gratuitos**.
5. **Apagado**: (a) mínimo 0 réplicas = no hay cargo de cómputo; (b) para cortar el acceso, desactivar la revisión o deshabilitar ingress; (c) para coste cero real, borrar el grupo de recursos y recrearlo con IaC/CLI.
6. **Límite de gasto real**: el único tope duro documentado es el **spending limit** de la cuenta gratuita (= el crédito, no editable, desactiva los recursos al agotarse). Los **presupuestos no paran nada** y se evalúan cada 24 h. Atención: el crédito de la cuenta gratuita dura **30 días** y, para seguir, hay que pasar a pago por uso, lo que **elimina** el spending limit. Ver §6.

**Mayor riesgo**: tras 30 días la suscripción se desactiva o pierdes el tope duro. Si la demo tiene que seguir "desplegada pero apagable" más de un mes, el tope pasa a ser un presupuesto con automatización (no verificado que funcione con Container Apps) o simplemente borrar el grupo de recursos.

## Tabla comparativa de opciones de cómputo

| | **Container Apps (Consumption)** | **App Service (Free F1)** | **App Service (Basic+)** | **Container Instances (ACI)** |
|---|---|---|---|---|
| Escala a cero | **Sí**, mínimo 0 por defecto; sin cargo de consumo con 0 réplicas — **verificado** [CA-BILL][CA-SCALE] | No aplica: el plan Free no se factura, pero comparte VM y recibe cuota de CPU — **verificado** [APPSVC] | No: el plan cobra mientras exista — **verificado** (el plan "carries a charge", salvo Free) [APPSVC] | No escala a cero; se detiene el grupo — **verificado** [ACI-OV] |
| Cuota gratuita | 180.000 vCPU-s, 360.000 GiB-s y 2 M peticiones HTTP por mes y suscripción — **verificado** [CA-BILL] | El plan Free no cobra — **verificado** [APPSVC]; cuotas exactas (minutos de CPU/día) — **no verificado** | Ninguna | Ninguna documentada en lo que leí — **no verificado** |
| Contenedores | Cualquier registro público o privado — **verificado** [CA-CONT] | Contenedores en Free: **no verificado**; un artículo de 2019 dice que no (itmedia, ver abajo). El texto actual de [APPSVC] no lo aclara | Sí (no leído en detalle) — **no verificado** | Sí, Linux y Windows — **verificado** [ACI-OV] |
| WebSockets (Streamlit) | Sí ("Support for WebSocket and gRPC") — **verificado** [CA-ING] | No leído — **no verificado** | No leído — **no verificado** | HTTP directo en IP del grupo; no leído — **no verificado** |
| Identidad gestionada | Sistema o usuario — **verificado** [CA-MI] | Soportada en general — **no verificado** en esta página | idem | Sí — **verificado** [ACI-OV] |
| Referencias a Key Vault | Nativas (`keyvaultref`) — **verificado** [CA-SEC] | Existen en App Service — **no verificado** | idem | No; hay que usar SDK — **no verificado** |
| Cobro con todo parado | 0 réplicas = 0 de consumo; las peticiones externas siguen contando para el cupo HTTP — **verificado** [CA-BILL] | Free: 0 | Plan sigue cobrando salvo que se borre/pare según SKU — **no verificado** | Medidores paran al detener el grupo entero — **verificado** [ACI-OV/FAQ] |
| Encaja | **Sí, primera opción** | Dudoso (contenedor + límites de CPU) | Cobra siempre: gasta crédito sin necesidad | Sin cuota gratuita, sin HTTPS/ingress gestionado propio: peor encaje |

Fuente del dato "Free de App Service no soporta contenedores en 2019": https://atmarkit.itmedia.co.jp/ait/spv/1905/20/news008.html — fragmento de búsqueda, antiguo, **no verificado**; hay que contrastarlo en https://learn.microsoft.com/azure/app-service/overview-hosting-plans y en la página de límites de App Service.

## 1. Opciones de cómputo

**Container Apps**

- Dos tipos de plan, Consumption y Dedicated; ambos escalan a cero y "pagas por lo que usas" — **verificado** [https://learn.microsoft.com/azure/container-apps/plans].
- Cuota gratuita mensual por suscripción y mes natural: primeros 180.000 vCPU-segundos, 360.000 GiB-segundos y 2 millones de peticiones HTTP; el uso gratuito no aparece en la factura — **verificado** [CA-BILL].
- Con 0 réplicas no hay cargo de consumo. Las peticiones que llegan desde fuera del entorno siguen contando; las sondas de salud no — **verificado** [CA-BILL].
- Con mínimo de réplicas > 0 existe una tarifa **idle** reducida cuando la réplica no procesa peticiones, usa < 0,01 vCPU y recibe < 1.000 B/s; fuera de eso se cobra la tarifa activa — **verificado** [CA-BILL]. Los importes de ambas tarifas: **no verificado** (https://azure.microsoft.com/pricing/details/container-apps/).
- Mínimo de réplicas por defecto 0, máximo por defecto 10 — **verificado** [CA-SCALE]. Aviso documentado: si no hay ingress ni regla de escalado y el mínimo es 0, la app escala a cero y no puede volver a arrancar — **verificado** [CA-SCALE]. Nuestras apps tienen ingress HTTP, así que despiertan con la primera petición (el arranque en frío de la primera petición no está medido: **no verificado**).
- Streamlit usa WebSockets y mantiene estado en el proceso: la afinidad de sesión (cookies) solo está disponible en modo de revisión única con ingress HTTP, y la doc recomienda no activarla si no hace falta — **verificado** [CA-STICKY]. Con máximo de 1 réplica en la UI el problema desaparece; recomendación mía (no es un dato de la doc).
- Estimación aritmética propia (no es un dato de Microsoft): 180.000 vCPU-s equivalen a 50 vCPU-horas al mes. Una app de 0,5 vCPU encendida 24/7 consumiría ~1,3 M vCPU-s al mes, muy por encima del cupo; con escala a cero y uso de demo (unas decenas de horas) cabe dentro. Hay que fijar los vCPU/GiB reales de cada contenedor antes de calcular.
- Las apps comparten un entorno; en el entorno "workload profiles" por defecto no hay coste de entorno si solo se usa el perfil Consumption: la doc dice que se cobra una tarifa de gestión de plan Dedicated solo si hay perfiles dedicados, y que ciertas funciones (endpoints privados, mantenimiento planificado) llevan "Dedicated Plan Management" aunque uses Consumption — **verificado** [CA-BILL]. No usar endpoints privados.
- Cuotas: dependen de la antigüedad y tipo de suscripción, y se consultan con `az containerapp env list-usages` — **verificado** [https://learn.microsoft.com/azure/container-apps/quotas]. Los valores concretos para una suscripción nueva: **no verificado**.

**App Service**

- Niveles: Free, Shared, Basic, Standard, Premium… Free y Shared comparten VM con otros clientes, tienen cuota de CPU por app y no escalan horizontalmente; salvo Free, todos los planes cobran por el cómputo — **verificado** [APPSVC].
- Que Free admita Linux y contenedores personalizados hoy, y su cuota exacta de CPU: **no verificado**. URL a abrir: https://learn.microsoft.com/azure/app-service/overview-hosting-plans y la sección "Azure App Service limits" de https://learn.microsoft.com/azure/azure-resource-manager/management/azure-subscription-service-limits.
- Una Streamlit exige WebSockets y un proceso que no se duerma por cuota de CPU; con CPU compartida es frágil. Descartado como primera opción por criterio propio.

**Container Instances**

- Linux y Windows, identidad gestionada y pull de imagen con identidad desde ACR — **verificado** [ACI-OV].
- Los medidores se detienen cuando **todo** el grupo de contenedores está parado; mientras un contenedor corra, se mantienen los recursos — **verificado** [ACI-FAQ]. El grupo se factura desde que empieza el pull de la imagen hasta que se detiene — **verificado** [ACI-FAQ].
- No hay escala a cero automática ni cuota gratuita en lo leído. Si el grupo se reinicia, puede cambiar su IP — **verificado** [ACI-OV]. Para HTTPS propio habría que añadir un front (Application Gateway). Peor encaje.

## 2. Azure Key Vault: coste y lectura desde la aplicación

**Coste**

- Precio por operación: la página oficial muestra "$-/10.000 transacciones" en su caché (importes ocultos). Una cifra de **0,03 $ por 10.000 operaciones** (nivel Standard, secretos) aparece en respuestas de Microsoft Q&A y en un blog de un competidor (Infisical) — **no verificado**. Hay que abrir https://azure.microsoft.com/pricing/details/key-vault/ para confirmar. A este volumen (un puñado de lecturas al arrancar) saldría en céntimos; la cuenta es mía, no un dato oficial.
- Qué cuenta como operación: según el FAQ de precios, crear/actualizar, obtener y listar — **no verificado** (fragmento). Una respuesta de Q&A afirma que cada secreto resuelto por Container Apps cuenta como transacción — **no verificado**: https://learn.microsoft.com/en-us/answers/questions/5859110/clarification-on-azure-container-apps-and-key-vaul
- Cuota gratuita de Key Vault: **no verificado**; en lo que vi no hay.

**Cómo lo lee la aplicación**

| | Referencia de secreto de Container Apps | SDK (`azure-keyvault-secrets` + `DefaultAzureCredential`) |
|---|---|---|
| Qué hace | El secreto se declara con `keyvaultref:<URI>,identityref:<identidad>`; Container Apps lo recupera y lo expone como secreto/variable de entorno — **verificado** [CA-SEC] | La app llama a `SecretClient(vault_url, DefaultAzureCredential())` — **verificado** [SDK-KV] |
| Rol necesario | Key Vault Secrets User para la identidad — **verificado** [CA-SEC][RBAC-SEC] | Idem — **verificado** |
| Rotación | Si el URI no lleva versión, toma la última y se refresca "en 30 minutos"; las revisiones activas que lo usen como variable de entorno se reinician automáticamente — **verificado** [CA-SEC] | La app decide cuándo releer |
| Código | Ninguno: la app lee `os.environ` | Dependencia `azure-identity` + `azure-keyvault-secrets` |
| Pruebas locales | Igual que cualquier variable de entorno (más simple) | `DefaultAzureCredential` encadena `az login` en local — **verificado** en [SDK-KV] (usa `DefaultAzureCredential`); el orden de la cadena no lo leí |
| Limitaciones | Con la creación (`create`) hay que usar identidad de usuario: la de sistema no existe hasta que se crea la app — **verificado** [CA-SEC]. Tras modificar secretos hay que reiniciar las revisiones activas — **verificado** [CA-REV] | — |

**Recomendación**: referencias de secreto para claves de terceros (menos código, rotación gestionada). Reservar el SDK para lo que no se pueda tener como variable de entorno. Con identidad gestionada, Search y el modelo no necesitan clave, así que **el Key Vault solo guarda las claves de proveedores externos** (juez DeepSeek y, si lo hay, el embedder de consulta por API). Conviene decir esto en el informe: es honesto con lo que el Key Vault protege de verdad.

El modelo de permisos del Key Vault debe ser RBAC: el rol Key Vault Secrets User "solo funciona en key vaults que usan el modelo de permisos Azure RBAC" — **verificado** [RBAC-SEC]. La página `key-vault/general/rbac-guide` no la pude leer: **no verificado** si el modelo RBAC es el predeterminado en los vaults nuevos (abrir https://learn.microsoft.com/azure/key-vault/general/rbac-guide).

## 3. Identidad gestionada y roles RBAC mínimos

**Sistema o usuario**

- Sistema: ligada a la app y se borra con ella; una por app. Usuario: recurso independiente, reutilizable, sobrevive a la app — **verificado** [CA-MI].
- La doc dice que sistema es mejor para cargas contenidas en un recurso con identidad independiente; usuario, para recursos múltiples que comparten identidad o necesitan **preautorización** — **verificado** [CA-MI]. Para el pull de imagen desde ACR, "cuando sea posible, usa identidad de usuario" — **verificado** [CA-PULL].
- Argumento práctico (propio): con identidad de usuario, los roles se asignan **antes** de crear la app, evitando el huevo-y-gallina de la identidad de sistema (que no existe hasta que la app existe; documentado para Key Vault en `create`, [CA-SEC]) y sobreviven a recrear la app tras "apagar y borrar".

**Roles (nombres y descripciones leídos en la lista oficial de roles integrados; cada uno asignado en el ámbito del recurso)**

| Para qué | Rol | Qué permite exactamente | Id del rol | Marca |
|---|---|---|---|---|
| Leer secretos de Key Vault | **Key Vault Secrets User** | `getSecret` y `readMetadata` de secretos; solo vaults con modelo RBAC | `4633458b-17de-408a-b874-0445c86b69e6` | **verificado** [RBAC-SEC] |
| Consultar índices de Azure AI Search | **Search Index Data Reader** | Solo `indexes/documents/read` (leer documentos o términos sugeridos) | `1407120a-92aa-4202-b7e9-c0e197c71c8f` | **verificado** [RBAC-AI] |
| Llamar a un modelo de Azure OpenAI | **Cognitive Services OpenAI User** | Lectura de ficheros/modelos/despliegues y crear completions, chat y embeddings (`.../deployments/chat/completions/action`, `.../embeddings/action`, etc.) | `5e0bd9bd-7b93-4f28-af87-19fc36ad61bd` | **verificado** [RBAC-AI] |
| Descargar la imagen de ACR (solo si hay ACR) | **AcrPull** | "Pull artifacts from a container registry" | `7f951dda-4ed3-4680-a7ca-43fe172d538d` | **verificado** [RBAC-CONT] |

Observaciones:

- El ticket decía "Cognitive Services OpenAI User o similar". Lo verificado es que ese rol existe y cubre chat completions. Si el ticket 02 elige un modelo que **no** es de Azure OpenAI (p. ej. modelos de Foundry de otro proveedor), el rol puede cambiar: en la lista de hoy existe **Foundry User** (`53ca6127-db72-4b80-b1b0-d745d6d5456d`) con `dataActions: Microsoft.CognitiveServices/*` y `accounts/listkeys/action` — **verificado** [RBAC-AI], es decir, **mucho más ancho** que OpenAI User y concede listar claves. Para mínimo privilegio, preferir OpenAI User siempre que el modelo lo permita. Qué rol exige cada tipo de despliegue de Foundry: **no verificado** (URL: https://learn.microsoft.com/azure/ai-foundry/concepts/rbac-azure-ai-foundry y https://learn.microsoft.com/azure/ai-services/openai/how-to/role-based-access-control, que no pude leer).
- Los roles de datos de Search (Reader/Contributor) son distintos de los de gestión (Search Service Contributor, que **no** da acceso a los datos). Que los roles de datos funcionen en el nivel **Free** de Search: un fragmento de la doc de Learn indica que RBAC es aplicable a "any tier, including free" — **no verificado** (fragmento): https://learn.microsoft.com/azure/search/search-security-enable-roles. Desactivar las claves de API (`disableLocalAuth`) también se menciona en ese fragmento; su efecto en Free **no verificado**.
- Los ejemplos del SDK de Search confirman que con `DefaultAzureCredential` el cliente se autentica con identidad gestionada y que el usuario "must be assigned the Search Index Data Reader role" — **verificado** [SDK-SEARCH]. Ojo: la indexación (BGE-M3 → índice) necesita **Search Index Data Contributor** (`8ebe5a00-799e-43f5-93ac-243d3dce84a7`, id leído en [RBAC-AI]) y gestionar el índice **Search Service Contributor**; esos roles son **de la persona que indexa, no de la API desplegada**.
- Propagación de las asignaciones de rol: puede tardar; no leí la cifra — **no verificado**.
- Asignaciones por identidad (propuesta, mínimo privilegio): `api` → 3 roles; `ui` → ninguno; identidad de pull → AcrPull solo si hay ACR.

## 4. Apagar y volver a levantar: qué se cobra con todo parado

| Recurso | Parado / sin uso | Marca |
|---|---|---|
| Container Apps (Consumption) con mínimo 0 | Sin cargo de consumo; sí cuentan las peticiones HTTP externas (cupo gratuito de 2 M) | **verificado** [CA-BILL] |
| Container Apps, revisión desactivada | "Deactivation stops all running replicas"; las revisiones inactivas no se cobran (límite de 100 en el historial) | **verificado** [CA-REV] |
| Container Apps, ingress deshabilitado | Cierra el acceso; no hay una "parada" como tal en lo leído | **verificado** que existe ingress interno/externo [CA-ING]; efecto en cobro: no leído |
| Entorno de Container Apps | En workload profiles con solo Consumption, no hay cargo propio por el entorno; en el entorno "Consumption only (legacy)" tampoco | **verificado** [CA-ENV][CA-BILL] |
| Log Analytics (destino de logs por defecto) | La ingesta y retención de logs puede costar aparte; el ingesta gratuita por GB: **no verificado**. La doc permite elegir "Don't save logs" o Azure Monitor | **verificado** que Log Analytics es el destino por defecto y que existe "Don't save logs" [https://learn.microsoft.com/azure/container-apps/log-options]; importes **no verificado** |
| Key Vault | Cobro por operación; cuota fija mensual del vault estándar: no vi ninguna, pero **no verificado** | **no verificado** |
| Azure AI Search Free | Un único servicio gratuito por suscripción; sin SLA; 50 MB y 3 índices según una página espejo | **no verificado** (fragmentos): https://learn.microsoft.com/azure/search/search-sku-tier |
| Modelo alojado | Depende del tipo de despliegue (estándar por tokens frente a provisionado): ticket 02 | **no verificado** |
| ACR (si se usa) | Cuota diaria fija mientras exista el registro, y el almacenamiento extra por GB y día | **verificado** que el cobro es por SKU y que el almacenamiento extra va aparte [ACR-SKU]; importes **no verificado** |

**Procedimiento propuesto de apagado** (comandos que cité de la doc enlazada, no los ejecuté):

1. Parada suave: mínimo de réplicas 0 (ya es el valor predeterminado): `az containerapp update --min-replicas 0` (parámetro `--min-replicas` documentado en [CA-SCALE]).
2. Parada dura de una revisión: `az containerapp revision deactivate` (para volver, `... activate`) — **verificado** [CA-REV].
3. Coste cero: borrar el grupo de recursos y recrearlo desde un script. Que "borrar el grupo de recursos" elimina todo lo que contiene es conocimiento general de Azure, **no verificado** aquí; en la práctica hay que validar que el soft-delete de Key Vault (nombre reservado durante la retención) no bloquee recrear el vault con el mismo nombre — **no verificado**, abrir https://learn.microsoft.com/azure/key-vault/general/soft-delete-overview.

## 5. Presupuestos y alertas: ¿límite real o solo aviso?

- **Los presupuestos solo avisan**: "Resources aren't affected, and your consumption isn't stopped" — **verificado** [BUDGET].
- Latencia: los datos de coste tardan "typically 8-24 hours" y los presupuestos se evalúan **cada 24 h**; el aviso por correo suele salir en la hora siguiente a la evaluación — **verificado** [BUDGET]. Un presupuesto no sirve como freno inmediato.
- Una suscripción nueva puede tardar hasta **48 h** en permitir crear presupuestos u otras funciones de Cost Management — **verificado** [BUDGET].
- Los presupuestos pueden invocar un **grupo de acciones** (ámbito suscripción o grupo de recursos) que ejecuta automatizaciones (Azure Functions, webhooks, Logic Apps, Automation) — **verificado** [BUDGET]. La guía oficial de automatización ([BUDGET-AUTO]) explica cómo **parar máquinas virtuales** con un runbook disparado por un umbral; **no hay receta oficial para Container Apps** en lo que leí. Parar una Container App desde la automatización (desactivar revisión) sería factible con la CLI/REST pero **no verificado**, y llega con retraso de al menos un día.
- **Límite duro: spending limit de la suscripción**. Lo tienen activado por defecto los clientes nuevos de cuenta gratuita y de suscripciones con crédito multi-mes. Es igual al crédito (en cuenta gratuita, 200 USD), **no se puede cambiar a otra cantidad** y no existe límite personalizado — **verificado** [SPEND].
  - Al agotarse, "the services that you deployed are disabled for the rest of that billing period": recursos retirados de producción, VMs paradas y desasignadas, almacenamiento en solo lectura — **verificado** [SPEND]. Si es cuenta gratuita y se llega al límite, se puede pasar a pago por uso para re-habilitar — **verificado** [SPEND].
  - No cubre todo: servicios de terceros del Marketplace, soporte, etc. se facturan aparte — **verificado** [SPEND]. No contratar nada del Marketplace.
  - No está disponible en suscripciones de pago por uso ni con planes de compromiso — **verificado** [SPEND].
- **El crédito de la cuenta gratuita caduca a los 30 días**: "Your subscription and services are disabled when your credit runs out or expires at the end of 30 days. To continue using Azure services, you must upgrade" — **verificado** [FREE]. Tras mejorar la cuenta, sigues con servicios gratuitos 12 meses y pagas solo por exceso — **verificado** [FREE]. Y la propia [SPEND] indica que pasar a pago por uso **elimina el spending limit**.
  - Consecuencia: durante los primeros 30 días hay tope duro de crédito; después, o se borra todo, o se mejora la cuenta y se pierde el tope, quedando solo presupuesto + automatización + disciplina. **Esto choca con "demo desplegada pero apagable" y debe decidirse antes de empezar** (ver ticket 06).
- Cuota exacta de crédito (200 USD/30 días en la UI actual de tu región/moneda) y qué servicios son "gratis 12 meses": **no verificado** más allá de lo que citan [FREE] y [SPEND]; abrir https://azure.microsoft.com/pricing/purchase-options/azure-account y su FAQ.

**Recomendación de límites** (certeza media):

1. Mantener la cuenta gratuita sin mejorarla mientras dure el trabajo (tope duro = crédito).
2. Crear un presupuesto de suscripción (importe bajo, p. ej. 5 USD, mensual) con alertas al 50/80/100 % por correo y grupo de acciones. Esperar a que Cost Management esté disponible (hasta 48 h).
3. Lo que cuesta de verdad (ACR, modelo de pago, Log Analytics) se crea, se mide y se borra en la misma sesión, como dice el mapa.
4. Antes del día 30: borrar el grupo de recursos o decidir conscientemente la mejora de cuenta.

## 6. Construir y publicar la imagen: ACR y alternativas

- **ACR** tiene tres SKU (Basic, Standard, Premium); cada una incluye una cantidad de almacenamiento y el extra se cobra por GB — **verificado** [ACR-SKU]. Importes: la página de Learn en idioma lt-lt cita para Basic **10 GB incluidos y 0,167 $/día** (≈ 5 $/mes por cálculo propio) y 0,003 $/GB/día de almacenamiento extra — **no verificado** (fragmento de búsqueda; las páginas de azure.microsoft.com muestran los importes en blanco): https://azure.microsoft.com/pricing/details/container-registry/. **No hay nivel gratuito de ACR en lo leído**: consume crédito aunque el registro esté inactivo (por cálculo propio, ~5 $ de 200 $).
- **ACR Tasks / `az acr build`**: la propia doc advierte: "Azure Container Registry task runs are temporarily paused from Azure free credits" — **verificado** [ACR-TASKS]. Es decir, con crédito gratuito puede que `az acr build` no funcione; construir fuera.
- **Pull con identidad gestionada**: Container Apps puede tirar de ACR con identidad de sistema o de usuario (preferible de usuario) y rol **AcrPull**; el registro debe aceptar tokens de audiencia ARM (`az acr config authentication-as-arm`) — **verificado** [CA-PULL][CA-CONT].
- **Registro público**: Container Apps acepta "containers from any public or private container registry" — **verificado** [CA-CONT]. Aviso oficial: Docker Hub limita las descargas y, al alcanzar el límite, los contenedores no arrancan; la doc recomienda un registro con límites suficientes — **verificado** [CA-CONT]. Los límites de GHCR: **no verificado** (https://docs.github.com/packages/working-with-a-github-packages-registry/working-with-the-container-registry).
- **Recomendación**: construir en GitHub Actions (o local) y publicar en **GHCR público** (coste 0; ninguna credencial en la app) mientras la imagen no contenga nada privado (ni `.env`, ni claves; el corpus del proyecto es legislación pública). Si se prefiere privado: ACR Basic con identidad de usuario + AcrPull, creado y borrado en la misma sesión. Certeza media: la gratuidad y los límites de GHCR no están verificados.

## Preguntas abiertas para otros tickets

- Ticket 02 (modelo): el rol RBAC y el coste "parado" dependen del tipo de despliegue.
- Ticket 05/06: filtros de contenido y spending limit, 30 días de crédito.
- La API debe autenticar a quien la llama: con ingress externo cualquiera podría gastar crédito. Opciones documentadas: ingress **interno** para la API [CA-ING], restricciones de IP (`allow`/`deny`; sin reglas se permite todo) [https://learn.microsoft.com/azure/container-apps/ip-restrictions], o autenticación integrada ("Easy Auth") con Entra ID u otros proveedores [https://learn.microsoft.com/azure/container-apps/authentication]. La UI es el único punto público; el set adversarial y la demo "apagable" se apoyan en esto. Todo **verificado** como funcionalidad; su adecuación para una demo abierta, no.

## Qué queda por confirmar a mano

1. **Todos los precios**: Container Apps tarifas activa/idle y por petición (https://azure.microsoft.com/pricing/details/container-apps/), Key Vault por 10.000 operaciones (https://azure.microsoft.com/pricing/details/key-vault/), ACR Basic (https://azure.microsoft.com/pricing/details/container-registry/), Log Analytics ingesta (https://azure.microsoft.com/pricing/details/monitor/).
2. **Azure AI Search Free**: límites (50 MB / 3 índices), RBAC y `disableLocalAuth` permitidos en Free, un servicio gratuito por suscripción, posible borrado por inactividad (https://learn.microsoft.com/azure/search/search-sku-tier y `.../search-limits-quotas-capacity`, `.../search-security-enable-roles`).
3. **Rol correcto para el modelo elegido** (OpenAI User frente a Foundry User) cuando haya decisión en el ticket 02 (https://learn.microsoft.com/azure/ai-services/openai/how-to/role-based-access-control).
4. **Key Vault**: RBAC como modelo por defecto, soft-delete al recrear, cuota gratuita, retraso de propagación de roles (https://learn.microsoft.com/azure/key-vault/general/rbac-guide).
5. **App Service Free**: si admite hoy contenedores Linux y sus cuotas (https://learn.microsoft.com/azure/app-service/overview-hosting-plans).
6. **Crédito de la cuenta gratuita**: importe, 30 días, qué pasa con el spending limit al mejorar la cuenta (https://azure.microsoft.com/pricing/purchase-options/azure-account).
7. **Automatización de presupuesto para Container Apps** (¿se puede desactivar una revisión desde un grupo de acciones?).
8. **Arranque en frío** real de Streamlit/FastAPI desde 0 réplicas (medirlo en el despliegue).
9. **Límites de GHCR** y que una imagen pública no exponga nada.
10. Que `az acr build` siga pausado para créditos gratuitos (https://learn.microsoft.com/azure/container-registry/container-registry-tasks-overview).
