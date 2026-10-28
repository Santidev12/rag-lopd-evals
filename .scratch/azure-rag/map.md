# Mapa: RAG de protección de datos sobre Azure, con agente, servicio y seguridad

Label: `wayfinder:map`

## Destination

El repositorio `rag-lopd-evals` pasa a v1 sobre Azure y **cada cambio se mide contra lo ya publicado**:

1. **Retrieval:** Azure AI Search con los vectores BGE-M3 propios, denso e híbrido, con recall@5/10/20
   medido frente a la línea base actual (89,3 % @10 a nivel artículo).
2. **Generación:** un modelo alojado en Azure, con línea base nueva medida frente a Gemini
   (sobre-respuesta 6,2 %, abstención indebida 8,8 %).
3. **Servicio:** API FastAPI y UI Streamlit desplegadas en Azure, apagables.
4. **Agente:** Microsoft Agent Framework con herramientas (buscar, abrir artículo, seguir remisión),
   memoria de conversación y trazas, evaluado en las cruzadas (6/12) y en un mini eval multi-turno.
5. **Seguridad y Responsible AI:** Key Vault con identidad gestionada y permisos mínimos, filtros de
   contenido y defensa ante prompt injection medidos con un set adversarial, y la política de
   abstención documentada.
6. **Salida pública:** el informe estático y el README se actualizan con todos los antes/después.

El mapa termina cuando el informe público enseña esas comparaciones y la demo desplegada se ha
verificado una vez y queda apagable.

## Notes

**Dominio**: el mismo que el mapa anterior (RGPD + LOPDGDD, corpus v0). Vocabulario en `CONTEXT.md`.
Mapa anterior: `../rag-lopd/map.md` (destino alcanzado el 22-oct-2026, informe publicado en GitHub
Pages). Este mapa **revisa con números nuevos** lo que aquel dejó fuera de alcance en v0: el híbrido y
el reranker, y los agentes multi-paso con navegación por remisiones.

**Este mapa lleva la ejecución dentro.** Sobrescribe el "plan, don't do" por defecto de wayfinder:
Santiago quiere programar y aprender estas habilidades, no recibir un plan. Los tickets `task`
producen código real. Se trabaja en pareja y el porqué de cada decisión se explica sobre el código.

**Decisiones de partida** (tomadas al trazar el mapa, el 27-oct-2026):
- **Presupuesto:** solo niveles gratuitos y el crédito de una suscripción nueva, con alerta de gasto.
  Lo de pago se crea, se mide y se borra en la misma sesión. Sustituye al tope de 10 €/mes anterior.
  **Revisada el 28-oct-2026:** la cuenta gratuita no da cuota de modelos. Se acepta el pago por uso con
  tope de 25 € y contención (ver el ticket de presupuesto).
- **Alcance:** entran los cuatro horizontes (Azure AI Search, FastAPI + UI, seguridad y Responsible AI,
  agente). El agente va el último y depende de lo medido antes.
- **Demo:** desplegada pero apagable. El informe estático sigue siendo el artefacto público permanente.
- **Embeddings:** se mantiene BGE-M3 con vectores propios en Azure AI Search. Solo cambia el motor, así
  el recall antes/después es comparable.
- **Generador:** pasa a un modelo alojado en Azure y se rehace la línea base. Las cifras de Gemini pasan
  a ser el "antes". El juez (DeepSeek) se mantiene: sigue siendo de otra familia que el generador.
- **Interfaz:** Streamlit, no React.
- **Memoria del agente:** sí, pero medida, con un mini eval multi-turno (8-10 preguntas de seguimiento).
- **Seguridad y Responsible AI:** Key Vault + identidad gestionada + mínimos privilegios; filtros de
  contenido y prompt injection con set adversarial medido; política de abstención documentada
  (incluida una regla sobre qué guardan las trazas).

**Cómo se trabaja aquí**:
- Python. Su nivel: lee bien y ha hecho scripts, pero duda con idioms, tipado, entornos y estructura de
  proyecto: explicar esas convenciones al vuelo, sin condescendencia y sin pararse.
- Todo en español; los términos técnicos en inglés cuando ese es el término real del campo.
- Honestidad con los números: nada se publica que no venga de una ejecución real; con n pequeño, siempre
  con intervalo de confianza, y un resultado nulo ("el híbrido no ayuda") es un resultado válido.
- Limitación del entorno de la sesión: no llega a `learn.microsoft.com` ni a `github.com` por
  `WebFetch`; `WebSearch` sí, pero devuelve fragmentos. Los tickets de investigación marcan como
  **no verificado** todo lo que no hayan podido leer en la fuente primaria.

**Skills a consultar**: `/tdd` para el código nuevo, `/prototype` para la UI y el comportamiento del
agente, `/research` para hechos externos, `/domain-modeling` para `CONTEXT.md` y los ADR,
`/codebase-design` al fijar los límites de los módulos.

**Referencias del proyecto**: `../rag-lopd/map.md`, `README.md`, `docs/eval-set.md`,
`docs/adr/0001-small-to-big-e-identificadores-semanticos.md`, `docs/informe.html`.

## Decisions so far

<!-- una línea por ticket cerrado -->

- [Azure AI Search: nivel gratuito, vectores propios y búsqueda híbrida](issues/01-azure-ai-search-nivel-gratuito-vectores-e-hibrido.md) —
  verificado en el SDK oficial 12.0.0: vectores propios sin vectorizador (encaja con mantener BGE-M3),
  híbrido en una llamada con peso ajustable, y `exhaustive=True` para medir lo que pierde HNSW. Sin
  verificar: límites del nivel Free, cuota vectorial y si el ranker semántico está en Free.
- [Modelos generadores en Azure](issues/02-modelos-generadores-en-azure.md) — candidatos OpenAI
  (`gpt-4.1-mini` el más repetible; `gpt-5*` con razonamiento), de otra familia que el juez; DeepSeek de
  Foundry excluido. **Todo precio y cuota sin verificar**; riesgo de cuota 0 en suscripción nueva.
- [Microsoft Agent Framework](issues/03-microsoft-agent-framework.md) — GA 1.0 (abr-2026), pero con
  deriva de API y paquetes beta: instalar solo `core` + `openai` + `azure-identity` con versiones
  fijadas. Un agente con tres herramientas; memoria con `store=False`; trazas OpenTelemetry solo con
  metadatos por defecto; FastAPI sin fricción. Sin probar contra Azure real.
- [Despliegue en Azure con identidad gestionada](issues/04-despliegue-en-azure-con-identidad-gestionada.md) —
  Container Apps (consumo, 0 réplicas mínimas), identidad con tres roles por recurso, imágenes desde
  GitHub Actions a GHCR. **Riesgo:** el crédito caduca a los 30 días y pasar a pago elimina el límite de
  gasto; los presupuestos solo avisan.
- [Filtros de contenido y prompt injection](issues/05-filtros-de-contenido-y-prompt-shields.md) — Prompt
  Shields solo devuelve `attackDetected` y no bloquea (verificado en la spec). Set adversarial en español
  con variante en inglés, midiendo ASR y falsos positivos; con n = 10, 0/10 = IC 0–28 %. Propuesta de
  estado `BLOQUEADO` y de no guardar el texto de las preguntas en las trazas.
- [Confirmar a mano los datos críticos](issues/11-confirmar-a-mano-los-datos-criticos.md) — **la cuenta
  gratuita da cuota 0 en todos los modelos de Azure OpenAI**: usarlos obliga a pasar a pago por uso y eso
  quita el límite de gasto. En AI Search Free (50 MB, 3 índices) no hay ranker semántico (exige Basic) ni
  ascenso de nivel; `k` de RRF fijo en 60. Solo `gpt-4.1-mini` acepta `temperature` 0. Región: no Spain
  Central.
- [Presupuesto: sin cuota de modelos no hay Azure OpenAI gratis](issues/10-presupuesto-y-caducidad-del-credito.md) —
  se acepta el pago por uso con **tope de 25 €**, alertas a 5/10/20 €, cuota baja de TPM y API sin acceso
  externo o autenticada; la tarjeta con límite no se adopta. AI Search en Free (**sin ranker semántico**),
  modelo en **Data Zone UE**, región europea no Spain Central, y el grupo de recursos se borra al
  terminar cada fase.
- [Generador en Azure: qué modelo y cómo se rehace la línea base](issues/09-generador-en-azure-y-linea-base.md) —
  **`gpt-4.1-mini`** en Data Zone UE (el único con `temperature` 0 y sin razonamiento). Cambia solo el
  modelo: mismo prompt v2, JSON simple, mismo juez `j1` y mismo recuperador local. **Tres pasadas**. Un
  bloqueo del filtro es el estado nuevo `BLOQUEADO`: cuenta como callarse y se desglosa. Conclusión por
  defecto: "sin diferencia demostrable" si los intervalos se solapan.

## Not yet specified

<!-- niebla: en alcance, pero aún no se puede formular como ticket -->

- **API FastAPI y UI Streamlit.** El contrato de la API (¿qué devuelve: respuesta, citas, estado,
  trazas?) y qué ve alguien en los primeros diez segundos. Depende de qué retriever y generador queden.
- **Despliegue, Key Vault e identidad gestionada.** Con Container Apps como punto de partida: roles,
  imágenes en GHCR, cómo se apaga, y si la API va sin acceso externo o con autenticación (ya decidido que una de las
  dos). Depende de tener la cuenta.
- **Diseño del agente.** Un agente con tres herramientas (buscar, abrir artículo, seguir remisión),
  memoria y trazas. Falta fijar qué cambia respecto al RAG simple y cómo se mide en las cruzadas;
  depende de lo que mida el retrieval nuevo y de qué cliente de modelo quede.
- **Evals nuevos.** El mini eval multi-turno y el set adversarial (≈ 10 ataques en español, con alguna
  variante en inglés, datos ficticios): qué casos, quién los escribe, cómo se corrigen. A mano, no con
  un LLM.
- **Política de abstención documentada** y la regla de qué guardan las trazas (no guardar el texto de
  las preguntas). El estado `BLOQUEADO` ya está decidido (ticket del generador); falta escribir la política.
- **Informe y README v1:** cómo se enseñan los antes/después y qué se retira o se matiza de lo publicado.

## Out of scope

<!-- fuera del destino; se cierra y no vuelve salvo que se redibuje el destino -->

- **React** como interfaz: se eligió Streamlit; un frontend completo no es el objetivo.
- **Embeddings de Azure OpenAI** como variante de la migración: cambiaría motor y embeddings a la vez.
- **Demo pública permanente**: exigiría límites de uso y control de acceso para no gastar el crédito.
- **Corpus de la AEPD y EDPB (v1 del mapa anterior)**: otro esfuerzo.
- **Fine-tuning, LoRA o entrenamiento de modelos.**
