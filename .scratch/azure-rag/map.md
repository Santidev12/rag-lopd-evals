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

## Not yet specified

<!-- niebla: en alcance, pero aún no se puede formular como ticket -->

- **Generación en Azure, tras elegir modelo.** Implementar el cliente (como `ModeloDeLenguaje`),
  rehacer la pasada de las 50 preguntas y comparar con Gemini. Depende del ticket del generador.
- **API FastAPI y UI Streamlit.** El contrato de la API (¿qué devuelve: respuesta, citas, estado,
  trazas?) y qué ve alguien en los primeros diez segundos. Depende de qué retriever y generador queden.
- **Despliegue, Key Vault e identidad gestionada.** Dónde corre el servicio, qué roles recibe su
  identidad, cómo se apaga. Depende de la investigación de despliegue y de tener la cuenta.
- **Diseño del agente.** Herramientas, orquestación, memoria de conversación y trazas. Depende de
  la investigación de Agent Framework y de lo que mida el retrieval nuevo.
- **Evals nuevos.** El mini eval multi-turno de la memoria y el set adversarial de prompt injection:
  qué casos, quién los escribe, cómo se corrigen. Se escriben a mano, no se generan con un LLM.
- **Política de abstención documentada** y la regla de qué guardan las trazas.
- **Informe y README v1:** cómo se enseñan los antes/después y qué se retira o se matiza de lo publicado.

## Out of scope

<!-- fuera del destino; se cierra y no vuelve salvo que se redibuje el destino -->

- **React** como interfaz: se eligió Streamlit; un frontend completo no es el objetivo.
- **Embeddings de Azure OpenAI** como variante de la migración: cambiaría motor y embeddings a la vez.
- **Demo pública permanente**: exigiría límites de uso y control de acceso para no gastar el crédito.
- **Corpus de la AEPD y EDPB (v1 del mapa anterior)**: otro esfuerzo.
- **Fine-tuning, LoRA o entrenamiento de modelos.**
