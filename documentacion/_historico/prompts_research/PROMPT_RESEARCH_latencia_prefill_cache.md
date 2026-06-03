# Prompt de investigación — Latencia de prefill / prefix-cache en Gemma 4 + llama.cpp

Copiá esto a claude.ai (con research/web). Es un problema ÚNICO y específico:
la latencia por turno de nuestro asistente de voz local. Incluyo TODA la
arquitectura real y las mediciones (extraídas del código y los logs del propio
llama-server). Quiero un informe técnico ACCIONABLE con código/flags listos para
implementar y MEDIR. Distinguí lo confirmado de lo hipotético; citá fuentes
oficiales (llama.cpp PRs/issues, papers) recientes.

---

## 0. Stack exacto (verificado en código)

- **Modelo**: Gemma 4 **E4B-it Q4_K_M** (~4.6 GB), GGUF. Familia Gemma 4 (recién
  salida; arquitectura tipo Gemma con **Sliding Window Attention**, n_swa=512).
  Target: laptop, GPU 6 GB o sin GPU dedicada.
- **Runtime**: **llama.cpp `llama-server`** build **b9090+**, un solo slot.
  Flags reales: `--jinja --ctx-checkpoints 1 --flash-attn on --keep -1
  --cache-reuse 256 --swa-full -ngl 99 -c 16384 --parallel 1`.
- **Restricción de UX**: asistente de VOZ, presupuesto de latencia tier-Alexa:
  4-5 s tope por turno, 8 s = catastrófico. 100% local, OSS, sin cloud.
- Ya se bajó de 16-22s → 3-7s antes (Q4_K_M + --swa-full + --cache-reuse +
  system prompt "lean"). Buscamos exprimir MÁS sin cambiar de modelo ni degradar
  el tool-calling.

## 1. Diagnóstico MEDIDO (logs de llama-server, 1494 turnos reales)

- **El cuello es el PREFILL, no la generación.**
  - Generación: mediana **21 tokens @ 62 tok/s = 386 ms** (está bien).
  - Prefill: se **reprocesan ~3906 tokens por turno** (mediana) a ~4400 tok/s =
    **~888 ms**; p90 = **11241 tokens (~2.5 s)**; peor caso 16197 tok.
  - Total por turno: mediana **2054 ms**; picos de **10-46 s** en turnos con
    prompt enorme (historial largo).
- **El prompt total es grande: mediana 7875 tokens.** Crece con el historial
  (cada turno suma user + respuesta + tool_results).
- **`--cache-reuse` SÍ funciona parcialmente**: reusa mediana ~6144 tokens del
  prefijo, pero cada turno reprocesa la "cola" variable de ~3900 tokens.

## 2. CAUSA RAÍZ identificada (el trade-off que sabotea el cache)

El sistema NO pasa los 65 tools al LLM cada turno. Un **router semántico** elige
un SUBCONJUNTO de tools por turno (4-6 tools) según la query. Para ahorrar
prompt, el **system prompt se FILTRA a ese subset**:
- `build_system_prompt(selected_tool_names)`: CORE + solo las reglas de uso de
  los tools del subset.
- `_tool_schemas_hint(selected_tool_names)`: el markdown "Tool Schemas EXACT"
  solo de esos tools.
- Además los tools van TAMBIÉN como `tools=[...]` de la API OpenAI-compat (que
  llama.cpp inserta en el prompt vía la plantilla `--jinja`).

**Medición del prompt (chars):**
- system prompt con subset [whatsapp, contacts] = 6071 chars
- system prompt con subset [office, filesystem]  = 5597 chars
- system prompt FULL (los 65 tools)              = 42383 chars
- **Prefijo común estable entre dos subsets distintos: solo 3659 chars (~900 tok).
  Después DIVERGEN** porque las reglas/schemas de tools cambian con el subset.

**Consecuencia**: como el subset cambia con cada query, el system prompt cambia
turno a turno, y el prefix-cache solo puede reusar ~900 tokens antes de toparse
con la parte variable → reprocesa miles de tokens. En el log se ve crudo:
`memory_seq_rm [4, end)` (reusó 4 tokens, reprocesó ~4800). Es un trade-off
TAMAÑO-de-prompt vs CACHE-HIT que parece no haberse medido en conjunto:
filtrar al subset achica el prompt pero lo vuelve inestable y mata el cache.

## 3. Lo que necesito investigado (con código/flags y fuentes)

1. **Estrategia de ordenamiento del prompt para maximizar prefix-cache**: ¿conviene
   un PREFIJO ESTABLE (system core + TODOS los tool-schemas, o un set fijo común)
   y dejar lo VARIABLE (subset hints, historial, user msg) al FINAL? ¿Cuál es el
   layout óptimo para `--cache-reuse` de llama.cpp dado que el historial crece por
   la cola? Trade-off concreto: prompt full estable de ~42K chars (¿cabe en 16K
   ctx? ~10-12K tokens) con cache casi perfecto, VS prompt chico inestable de ~6K
   con cache pobre. ¿Cuál gana en latencia NETA? Dame el cálculo y cómo medirlo.

2. **`--cache-reuse` / prefix-cache en llama.cpp con SWA (Gemma)**: ¿cómo funciona
   exactamente el matching de prefijo, y qué lo invalida? ¿`--swa-full` +
   `--cache-reuse 256` es la config óptima para reuso máximo en Gemma 4, o hay
   flags/PRs nuevos (b9090+) que mejoran esto? ¿`--ctx-checkpoints` ayuda? ¿El
   crecimiento del historial por la cola se puede mitigar con prompt-cache slots
   o context-shift sin reprocesar?

3. **Speculative decoding** en llama.cpp para este caso: ¿un draft model chico
   (ej. una Gemma más pequeña) aceleraría la GENERACIÓN? Pero ojo: medimos que la
   generación ya es barata (386 ms, 21 tok). ¿Vale la pena, o el ROI está SOLO en
   el prefill? Sé honesto si no aplica.

4. **Grammar/GBNF-constrained decoding para tool-calls**: ¿acelera el primer token
   y/o mejora fiabilidad del tool-calling en modelos chicos? ¿Interactúa bien con
   `--jinja` y `tool_choice`?

5. **Reducir el reprocesado del historial**: el prompt crece ~3900 tok/turno por
   acumulación de user+respuesta+tool_results. ¿Mejores prácticas para compactar/
   resumir el historial SIN romper el prefijo cacheado ni perder contexto? (Ya
   hay compactación que stripa tool messages; ¿hay algo mejor para latencia?)

6. **¿Cambiar de runtime daría un salto grande?** Preferimos quedarnos en
   llama.cpp (GGUF, 6GB, local). Pero si vLLM/SGLang/TGI con **prefix-caching
   automático (RadixAttention)** diera un salto de latencia GRANDE corriendo
   Gemma 4 E4B en 6GB, decílo con números. Si no aplica a 6GB, descartalo
   explícitamente.

## 4. Formato del informe

Para cada punto: diagnóstico, opciones con tabla comparativa (criterios
medibles: ms de prefill, cache-hit %, VRAM, riesgo de romper tool-calling),
fuentes oficiales/PRs/papers recientes, y un veredicto VIABLE para ESTE stack
(Gemma 4 E4B-Q4, llama.cpp b9090+, 16K ctx, 6GB, voz tier-Alexa, router con
subset dinámico de tools). Snippets de código Python y/o flags de llama-server
listos para pegar. Priorizá el punto 1 (layout del prompt para cache) y el 2
(exprimir cache-reuse) — son los de mayor ROI según la medición.
