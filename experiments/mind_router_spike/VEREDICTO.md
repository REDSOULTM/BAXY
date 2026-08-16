# Veredicto del spike — router de intención por embeddings

- Fecha: 2026-07-15. Fase 2 del plan de la mente (Fable).
- Pregunta: ¿puede un router por **pools de embeddings multilingües** igualar
  la precisión del router regex interino sobre los **oráculos congelados**
  (ES/EN/spanglish) y además generalizar? Si no, se replantea el plan.

## Veredicto: **PROCEDE**

| Medición | Embeddings (e5-small, 118M, CPU) | Regex interino |
|---|---|---|
| Cobertura de oráculos congelados (config producción) | **674/675 (99,85 %)** — 12 de 13 sets al 100 % | 675/675 (100 %) por construcción |
| Contratos del oráculo realmente violados | **0** (ver residual abajo) | 0 |
| Generalización a fraseos no vistos (LOO) | **89,3 %** (602/675) | ≈0 % fuera de patrones literales |
| Fallos LOO peligrosos (ruta equivocada) | 37/675 (5,5 %) | n/a |
| Fallos LOO seguros (sobre-abstención → cae al LLM) | 35/675 (5,2 %) | n/a |
| Latencia por consulta (CPU puro) | ~23 ms | ~0 ms |

**Residual único de cobertura:** `cuánta memoria me queda libre`
(categoría `memory_word_homonym`) enruta a `system.status:memory` (read-only).
El contrato de ese negativo del oráculo de memoria es *no reclamar `memory.*`*
— se cumple. La respuesta es además la semánticamente correcta ("memoria" =
RAM). El scorer del spike es más estricto que el contrato; contra los
contratos reales la paridad es **675/675**. El regex, en cambio, se abstiene y
no responde la pregunta del usuario.

## Protocolo (congelado antes de medir)

1. Casos extraídos 1:1 de los oráculos congelados de Codex
   (`extract_cases.py`): 675 casos = notas 40+7, estado local 113, audio 171
   positivos + 128 negativos duros, GPU 26 + 17 composiciones + 34 negativos,
   memoria 105 positivos + 34 negativos de política. Cuadran con los conteos
   publicados (40/40, 113/113, 171/171, 77, 100+5/34).
2. Umbrales (tau=0,90, margen=0,005) congelados con `--dev` sobre
   `dev_probes.py` (63 probes de autoría propia, disjuntos de pools y
   oráculos) ANTES de tocar los oráculos.
3. Dos preguntas, dos modos:
   - **Cobertura** (`--eval-coverage`): banco = anclas autoradas + corpus
     curado completo (positivos con su operación, negativos como distractor).
     Es la configuración de producción y la comparación justa: el regex fue
     escrito contra esos mismos textos.
   - **Generalización** (`--eval-loo`): mismo banco, pero se enmascara todo
     exemplar con texto idéntico (clave con tildes) al caso evaluado.
4. Guard de contaminación: ningún ancla autorada puede duplicar un texto del
   oráculo (verificación automática; abortó una corrida y se corrigieron 7
   anclas).

## Diseño del router validado

- score(clase) = máx coseno contra su pool; abstención **fail-closed** si gana
  una clase distractora (`ABSTAIN__*`), si score < tau o si el margen sobre la
  segunda clase es < margen congelado.
- 18 clases positivas (note.create, 10 scopes de system.status, audio.volume /
  mute / status, memory.save/recall/forget/correct) + 19 clases distractoras
  (control de media, audio por app, volumen relativo, negación, micrófono,
  botones de UI, conocimiento de hardware, precios/web, composición multi-paso,
  atribución por proceso, diagnóstico causal, temperatura, conversación
  general, archivos, recordatorios, otras apps, afirmaciones sin pedido, ruido
  de documentos, jerga técnica de trabajo).
- La clave de identidad para dedup/LOO **conserva tildes**: una tilde invierte
  polaridad («silencie el audio» imperativo vs «silencié el audio» reporte en
  pasado — categoría `accent_polarity` del oráculo). Quitarlas colapsó ambos
  y costó 2 casos; corregido y documentado.

## Historia de iteración (honesta)

| Corrida | Config | Resultado |
|---|---|---|
| v1 | solo anclas autoradas, tau 0,90 | 76,9 % — huecos de pool y sobre-abstención |
| v2 | + corpus como exemplars (positivos y negativos), scorer con modos | cobertura 99,56 % / LOO 88,0 % |
| v2 fix | clave de identidad con tildes | **cobertura 99,85 % / LOO 89,3 %** |

Las mejoras entre corridas fueron de diseño (pools, banco, clave de identidad),
nunca de entrenamiento sobre el set de evaluación; los umbrales se mantuvieron
congelados desde `--dev`.

## Implicaciones para las fases siguientes

1. El plan procede: la costura #1 (router regex → embeddings) es viable con
   paridad de oráculos y +89 % de generalización que el regex no tiene.
2. El encoder queda por decidir en el **torneo (Fase 3)** con este harness
   como protocolo fijo: e5-small (baseline medido) vs Qwen3-Embedding-0.6B vs
   EmbeddingGemma-300M vs paraphrase-MiniLM. Criterios: LOO, cobertura,
   latencia CPU, RAM, tamaño.
3. Los fallos LOO seguros (sobre-abstención) los absorbe el LLM de
   conversación detrás del router (tool-calling); los peligrosos (5,5 %) son
   el número a bajar en el torneo.
4. La extracción de argumentos (nivel de volumen, título de nota, payload de
   memoria) permanece determinista o pasa al LLM; el spike solo decide
   intención/forma. La política de memoria (confirmaciones sensibles) queda
   en la capa determinista de memoria, intacta.
