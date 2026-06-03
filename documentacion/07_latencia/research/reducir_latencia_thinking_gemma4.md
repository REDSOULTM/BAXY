# Reduciendo Latencia de THINKING en Asistente de Voz Local (Gemma E4B-Q4 + llama.cpp b9090)

## TL;DR

- **El mayor ROI inmediato (días, no semanas) es combinar (1) un router barato de intent que mande los comandos triviales a una ruta "tool-call directo SIN thinking" y (2) reemplazar el thinking libre por una plantilla *structured brief CoT* tipo FR-CoT (≤32 tokens, formato `INTENT: / TOOL: / ARGS: / GO`).** Hay evidencia directa publicada en BFCL v3 de que esa plantilla mejora drásticamente la fiabilidad (Qwen2.5-1.5B: 44.0% sin CoT → 64.0% con brief CoT@32, +45% relativo; Qwen2.5-7B: efecto similar y amplificado) y elimina la alucinación de función a 0.0%, mientras corta el thinking >5×.
- **Enmascarar latencia con TTS en paralelo (speculative tool-call + filler audio) es el único truco que regala ~1–2 s percibidos sin tocar el modelo.** Track A emite "Abriendo Steam…" mientras Track B corre el thinking + tool en silencio. Es el patrón estándar Vapi / Stream / Sierra y aplica directo a tu pipeline tier-Alexa.
- **NO esperes ganancias de speculative decoding en este stack.** N-gram (`--spec-type ngram-mod` / `ngram-simple`) ha dado regresión neta del 3–12% en benchmarks recientes sobre RTX 3090 / 5060 Ti / Qwen3 / Gemma 4, salvo en repeticiones triviales. Para 6 GB VRAM no hay drafter externo viable. KV cache q8_0 sin draft model es seguro pero acelera ~0–2% en decode.

---

## Key Findings

1. **El thinking estructurado y breve es estrictamente mejor que el thinking libre para tool-calling en modelos chicos.** El paper de Xuan Qi (IIIS, Tsinghua University), "Brief Is Better: Non-Monotonic Chain-of-Thought Budget Effects in Function-Calling Language Agents" (arXiv:2604.02155v1, 2 abril 2026) mide en BFCL v3 Multiple con Qwen2.5-1.5B-Instruct: 44.0% sin CoT → **64.0% con brief CoT @32 tokens** → 25.0% con CoT @256 tokens (McNemar p<0.001 entre brief y largo). Sección 8.2 reporta no-monotonicidad confirmada y amplificada en Qwen2.5-7B. El abstract afirma textualmente: "FR-CoT [el template estructurado `Function: X / Key args: …`] reduces function hallucination to 0.0% — providing a structural reliability guarantee without budget tuning." Para tu modelo de 4B esto es la evidencia más relevante disponible en 2026.

2. **Chain-of-Draft "libre" (5 palabras/paso, sin estructura) NO es seguro para modelos pequeños.** El paper original de Xu et al. (Zoom AI, arXiv 2502.18600) sólo testeó GPT-4o y Claude 3.5 Sonnet (CoT 95.4-95.8% → CoD 91.1-91.4%, ~80% menos tokens). La afirmación "CoD underperforms on models <3B" es extensamente citada en blogs y reviews (AWS, Medium) pero los números específicos de degradación sobre Qwen2.5-1.5B/3B y Llama-3.2-3B en algunas tablas circulan en literatura secundaria, no en el cuerpo principal del paper de Xu et al. Tomado conservadoramente: **no copies CoD libre — usa el template estructurado FR-CoT**.

3. **`thinking_budget_tokens` / `--reasoning-budget` en llama.cpp es un corte duro con sufijo cosmético.** La implementación (commit `acb7c790698fa28a0fbfc0468804926815b94de3`, "common/parser: handle reasoning budget", PR #20297) inyecta `--reasoning-budget-message` exactamente en el token N: deja al modelo cero tokens para concluir → funcionalmente equivalente a truncar. El issue #20632 lo documenta: "The current --reasoning-budget-message implementation injects a wrap-up message at exactly token N, leaving the model zero tokens to actually act on it." Verdict: usable como red de seguridad p99 pero no como mecanismo principal de control; el prompt debe inducir brevedad, no esperar que el sampler corte.

4. **Speculative decoding sin draft model (n-gram) no es viable para tu carga.** Benchmarks reproducibles publicados:
   - thc1006 (HackMD/HuggingFace, post PR #19493): 19 configuraciones sobre Qwen3.6-35B-A3B + RTX 3090, **"None of the spec-decode modes — ngram-cache, ngram-mod (incluso con la receta n=24/min=48/max=64), o classic --model-draft con Qwen3.5-0.8B — achieves net speedup over baseline. Mean decode drops 3–12%."**
   - defilan en DEV.to sobre RTX 5060 Ti + Qwen3-32B: ngram-simple 20.4 → 20.6 tok/s (dentro del ruido). El "5x speedup" sólo aparece al repetir el MISMO prompt 10 veces. Conclusión textual: "With diverse prompts, there's nothing useful to cache."
   - Para voz con prompts diversos NO ayuda y puede empeorar. Sólo el fragmento estructurado del FR-CoT (`INTENT: / TOOL: / ARGS:`) podría disparar n-gram hits, pero no compensa la regresión global.

5. **El router adaptativo tiene evidencia sólida.** Yang et al., "Ares: Adaptive Reasoning Effort Selection for Efficient LLM Agents" (arXiv:2603.07915, 9 marzo 2026) reporta textualmente: "Ares reduces reasoning token usage by up to 52.7% compared to fixed high-effort reasoning, while introducing minimal degradation in task success rates," evaluado sobre TAU-Bench (tool use), BrowseComp-Plus y WebArena con gpt-oss-20b como backbone y un router fine-tuneado (Qwen3-1.7B). Es la mejor evidencia disponible de que rutear thinking por complejidad reduce >50% el costo de reasoning con caída despreciable.

6. **Speculative / parallel tool-call enmascara latencia de forma probada.** Lawrence Jones (incident.io, "Break chatbot speed limits with speculative tool calls", 2024-2025): describe lanzar tool calls ANTES de que el LLM oficialmente lo pida, basándose en intent del input. GetStream.io ("How Do You Prevent Voice Gaps with Speculative Tool Calling?") describe el patrón Two-Track: Track A = filler conversacional inmediato a TTS, Track B = ejecución del tool en background, "While TTS reads the filler (buying 1.5-2 seconds), the tool executes." Sierra describe el mismo principio bajo "Time to First Audio" como métrica clave.

---

## Punto 1 — Reducir tokens de thinking sin perder fiabilidad de tool-call (ALTA PRIORIDAD)

### (a) Diagnóstico
Tu medición (23% de turnos >100 tok, p90=268 tok, max 841 tok @ 62 tok/s = hasta 13.5 s de puro thinking) es consistente con el patrón "overthinking" documentado en Qwen2.5 / Gemma small por Qi (2026). La causa típica es prompts ambiguos + system sin estructura → el modelo deriva en monólogo. El paper de Xu et al. ("Chain of Draft", 2502.18600) advierte ya en su §4 que la efectividad de CoD depende fuertemente del tamaño del modelo y de que el modelo haya visto datos similares en entrenamiento; aplicable por extensión al E4B en Q4. Conclusión: NO uses CoD libre; usa template estructurado.

### (b) Opciones

| Técnica | Tokens thinking esperados | % tool-call correcto (evidencia) | VRAM | Riesgo | Veredicto |
|---|---|---|---|---|---|
| **Status quo (CoT libre + budget 256/1024/2048)** | mediana 23, p90 268, max 841 | 6/6 medido por usuario | 0 | outliers rompen 4-5 s | baseline |
| **FR-CoT / Structured brief CoT** (template `INTENT: / TOOL: / ARGS: / GO`, ≤32 tok) | 8–32 tok | Qwen2.5-1.5B BFCL: 44.0% → 64.0% (+45% rel); alucinación 3.0% → 0.0% (arXiv 2604.02155, Qi 2026) | 0 | bajo: prompt-only | **VIABLE — primera apuesta** |
| **CoD libre (5 palabras/paso, sin campos fijos)** | ~20–60 tok | sin evidencia directa para Gemma E4B; degradación documentada en modelos pequeños en literatura secundaria | 0 | alto en modelos 3-4B | **NO recomendado** |
| **Sketch-of-Thought** (Aytes et al., arXiv 2503.05179) | −76% tokens en Qwen2.5-7B | −0.74% accuracy en 7B, no medido en tool-calling ni en 4B | 0 | medio: no validado en tu escala/tarea | esperar evidencia |
| **Budget muy agresivo (`thinking_budget_tokens` 64/128)** | corte duro a 64–128 | en HumanEval Qwen3-9B: 94% (full) → 78% (budget mal sintonizado, reportado por mantenedor en commit acb7c79) | 0 | alto: corta a media frase | sólo como red de seguridad p99 |
| **Fine-tune QLoRA en 1-2k ejemplos brief-CoT con tool calls** | ~20–30 tok | esperable +10-20 pts vs prompt-only | 0 inference; ~16 GB train | medio: tiempo de ingeniería | **viable a 2-4 semanas si FR-CoT no basta** |

### (c) Plantilla concreta — Structured Brief CoT para Gemma E4B

```text
SYSTEM (al final del system prompt, junto a la declaración de tools):

When the user asks you to act on the system, reason BRIEFLY using EXACTLY
this 4-line format inside the thought channel, then emit the tool call.
Never deliberate beyond these 4 lines.

INTENT: <one of: open_app | search | media_control | system_setting | clarify_needed>
TOOL:   <exact function name from the tool list, or "none">
ARGS:   <comma-separated key=value, or "—">
GO

If INTENT=clarify_needed, output a one-sentence question to the user and do
NOT call any tool.
```

Por qué funciona, en línea con el hallazgo central de Qi (2026): cuatro campos cortos forzados → la entropía del modelo se concentra en `TOOL` y `ARGS` (lo importante) y se aborta el divague. Es la versión "Function-Routing CoT" del paper trasladada al template Gemma. Espera mediana <20 tok, p95 <50 tok.

### (d) Veredicto
**VIABLE y de mayor ROI inmediato.** Aplica sin tocar binarios. Combinado con el Punto 4 (gating por intent) elimina la mayoría de outliers >268 tok. Empieza por aquí.

---

## Punto 4 — Detección temprana de cuándo NO hace falta thinking (ALTA PRIORIDAD)

### (a) Diagnóstico
"Abre Steam" no necesita ningún thinking — el tool es obvio. Pero el problema medido por el usuario fue: reasoning OFF → 2/6 fiabilidad. La pregunta es: *¿se puede gatear el thinking SIN reintroducir esa caída?* La respuesta en la literatura es sí, vía router de complejidad/intent con fallback. Ares (Yang et al. 2026) lo demuestra con −52.7% tokens y leve mejora en TAU-Bench, aunque con un router LLM (Qwen3-1.7B) que en tu hardware sería caro. Para 6 GB VRAM la versión liviana es embeddings.

### (b) Opciones de routing

| Arquitectura | Latencia router | Cobertura "crisp" | Riesgo de mis-route | VRAM | Veredicto |
|---|---|---|---|---|---|
| **Reglas + verbos imperativos** ("abre/cierra/sube/pausa/reproduce" + n-grams de apps conocidas) | <0.5 ms | 60-80% del tráfico Alexa-tier | medio: depende del léxico | 0 | **VIABLE como capa 0** |
| **Embeddings + cosine kNN** (Suki AI / Voiceflow pattern, `e5-small` ~80 MB CPU) | ~1-3 ms | >90% con 50-100 ejemplos/intent | bajo si umbral cosine bien calibrado | ~0 VRAM (CPU) | **VIABLE — capa 1** |
| **Adaptive-classifier/llm-router (HuggingFace, Apache 2.0)** | ~5-10 ms | similar AutoThink | bajo | ~0 | viable, más pesado |
| **LLM mini (FunctionGemma 270M)** | ~50-100 ms | alto | bajo | +0.3 GB | poco ROI vs embeddings en tu VRAM |
| **Self-routing por perplejidad** (CAR, Lu et al. 2025; SynapseRoute, Zhang et al. 2025) | 0 extra | medio | requiere fine-tune | 0 | demasiado complejo para 6 GB |

### (c) Pipeline propuesto (tres capas, fail-safe)

```python
# Router pre-LLM de 3 capas
def route_thinking(user_text: str, asr_confidence: float) -> dict:
    # Capa 0: reglas léxicas — comandos crisp
    if matches_imperative_app_command(user_text) and asr_confidence > 0.85:
        # ej. "abre steam", "pausa spotify", "sube volumen 20"
        return {"mode": "tool_only", "thinking_budget": 0, "template": "DIRECT"}

    # Capa 1: embedding kNN sobre ~200 ejemplos etiquetados
    intent, score = embed_knn_classify(user_text)
    if score > 0.78 and intent in CRISP_INTENTS:
        return {"mode": "tool_only", "thinking_budget": 0, "template": "DIRECT"}
    if score > 0.78 and intent in AMBIGUOUS_INTENTS:
        return {"mode": "brief_cot", "thinking_budget": 128, "template": "FR_COT"}

    # Capa 2: fallback con thinking estructurado
    return {"mode": "brief_cot", "thinking_budget": 256, "template": "FR_COT"}
```

Para `tool_only` mode, el system prompt cambia a:
```text
The user request is unambiguous. Emit the tool call DIRECTLY without any
reasoning. Do not write a thought block. Output ONLY the <|tool_call|> JSON.
```
En el body del request: `"thinking_budget_tokens": 0`. En Gemma E4B con `--jinja --chat-template-kwargs '{"enable_thinking":false}'` se desactiva el thinking en la práctica (confirmado en discussion #21338 para text-only).

⚠️ **Mitigación del fallo 2/6** (el caso donde Gemma E4B sin reasoning "prometía en texto" sin llamar tool):
1. **Few-shot positivo en system prompt** con 3-4 ejemplos `usuario → <|tool_call|>` SIN texto natural intermedio. Esto re-condiciona la cabeza de salida hacia el tool token.
2. **Grammar / GBNF constraint** sobre la salida en modo direct: forzar que la primera línea sea `<|tool_call|>{` literal. En llama.cpp esto se hace vía `--grammar-file` o el campo `"grammar"` en el body del POST.

### (d) Veredicto
**VIABLE y de muy alto ROI.** Reduce el % de turnos con thinking a probablemente <40% (vs 100% actual) y preserva fiabilidad porque los casos ambiguos siguen con FR-CoT + budget conservador. Implementación: 2-3 días.

---

## Punto 2 — Speculative / draft decoding

### (a) Diagnóstico
Tu generación va a 62 tok/s. Para 268-841 tok eso es 4.3-13.5 s. Doblar la velocidad sería ideal, pero los benchmarks recientes en hardware comparable son desalentadores.

### (b) Opciones

| Variante | Speedup medido | VRAM extra | Aplica a E4B-Q4 6 GB | Veredicto |
|---|---|---|---|---|
| **`--spec-type ngram-simple`** | RTX 5060 Ti / Qwen3-32B: 20.4 → 20.6 tok/s (ruido); 5x sólo en prompt idéntico repetido (defilan, DEV.to) | 0 | sí | **NO viable para voz** (prompts diversos) |
| **`--spec-type ngram-mod` (recomendada para MoE)** | Qwen3.6-A3B / RTX 3090: −3 a −12% mean; bimodal 59-67 tok/s en código/reasoning incluso con 100% acceptance (thc1006, HackMD) | 0 | sí | **NO** |
| **`--spec-type ngram-cache` con persistencia** | similar (regresión 3-12%) | 0 | sí | **NO** |
| **Draft model externo (mismo tokenizer)** | requiere drafter compatible | +0.3-0.5 GB | borderline en 6 GB | quizá probar, no garantizado |
| **Draft MTP (Multi-Token Prediction Gemma)** | Qwen3.6-27B / RTX 3090: 38.86 → 65 tok/s (×1.71, DataCamp); pero Gemma 3n MTP no carga en mainline llama.cpp (issue conocido) | +VRAM no medido | NO según investigación previa | descartado por usuario |
| **Lookahead Reasoning** (Fu et al., arXiv 2506.19830) | hasta 2.1× combinado con SD | requiere 2do modelo + cambios runtime | NO en llama.cpp aún | esperar |

Flag concreto para confirmar en tu hardware exacto (recomendación oficial del doc llama.cpp):
```bash
llama-server -m gemma-4-E4B-it-Q4_K_M.gguf \
  --jinja --flash-attn on --swa-full \
  --spec-type ngram-mod \
  --spec-ngram-mod-n-match 24 \
  --spec-ngram-mod-n-min 48 --spec-ngram-mod-n-max 64 \
  -c 16384 --parallel 1 --keep -1 --cache-reuse 256
```
Mide con `llama-bench` o tu pipeline real con n≥30 turnos antes/después. Abandona si la mediana no sube ≥10%.

### (c) Veredicto
**NO viable como apuesta principal para 6 GB / E4B-Q4 / voz.** Ngram-mod *podría* ayudar al fragmento estructurado del FR-CoT (`INTENT: / TOOL: / ARGS:` son casi-deterministas). Si pruebas, hazlo SÓLO con A/B sobre tu carga real.

---

## Punto 3 — Paralelizar thinking con TTS

### (a) Diagnóstico
La latencia percibida ≠ la latencia computacional. El estándar voice-agent (Vapi, Sierra, Stream, Twilio ConversationRelay, Cresta, LiveKit, Deepgram, Cloudflare Agents SDK) usa "request-start message" o "speculative tool call" para emitir audio mientras el LLM piensa.

### (b) Patrón: Two-Track Speculative Tool Call

```
t=0     user termina de hablar → ASR final
t=0     Track A: emite a TTS un confirm corto basado en intent del router barato
           "Ok, abriendo Steam…"   (≈800-1200 ms de audio)
t=0     Track B: llama-server con FR-CoT, thinking_budget según router
           (típicamente 1-3 s)
t≈1.0s  Track A termina audio
t=?     Track B retorna tool_call → ejecuta → emite resultado por TTS
```

| Patrón | Reducción percibida | Riesgo | Aplica |
|---|---|---|---|
| **Confirm filler genérico** ("dame un segundo", Vapi request-start) | enmascara 0.8-1.5 s del thinking | bajo | siempre |
| **Confirm filler intent-aware** ("Abriendo Steam…") | enmascara 1.0-1.8 s | medio: si router se equivoca, filler suena raro | con router del Punto 4 |
| **Pre-ejecutar tool read-only** durante thinking (PASTE / Stream eager execution) | toda la latencia del thinking | nulo si tool es idempotente | calendar, weather, abrir app |
| **Pre-ejecutar tool write** | toda | ALTO: efectos colaterales | NO, salvo idempotencia explícita |

Cita clave de Stream: "Good candidates for eager execution include weather lookups, stock prices, account balances, and calendar queries. Avoid eager execution for anything that changes state, like transfers, purchases, message sending, or deletions."

### (c) Veredicto
**VIABLE y de altísimo ROI percibido.** No baja la latencia computacional pero sí la percibida 1-2 s. Complementaria al Punto 1 y 4. Implementación: 3-5 días de plomería TTS + orquestador.

---

## Punto 5 — `thinking_budget_tokens` / `--reasoning-budget`: cómo funciona en serio

### (a) Mecánica real (verificada)
- Es un **sampler logit-processor** (commit `acb7c790698fa28a0fbfc0468804926815b94de3`, PR #20297) que cuenta tokens dentro del bloque thinking. Al llegar a N inyecta `--reasoning-budget-message` y el end-of-thinking delimiter del template.
- **Issue #20632** documenta que la inyección ocurre exactamente en token N, "leaving the model zero tokens to actually act on it. This is functionally equivalent to truncation with a cosmetic suffix." Propone Option A (offset) y Option B (split budget), sin merge a fecha del informe.
- En el body de `/v1/chat/completions`, el campo es `"thinking_budget_tokens": N` (no `reasoning_budget`). Confirmado en discussion #21445: "You're looking for thinking_budget_tokens. You can include this in the request body."
- Con `--jinja` y el template Gemma 4 oficial, el budget interactúa con la apertura del canal de pensamiento; el sampler cierra en N.
- **Gemma 4 quirk:** discussion #21338 muestra que en Gemma 4 26B-A4B, `--reasoning-budget 0` solo NO apaga thinking; lo apaga `--chat-template-kwargs '{"enable_thinking":false}'`. Para E4B esto debe verificarse en tu build exacto. Adicionalmente, "Solo Thinking ON está roto en Gemma 4 — dispara el flood de `<unused49>`. En el mismo hardware y build, Qwen 3.5-35B-A3B Thinking ON/OFF funciona. Esto confirma que el issue es específico del template/parser de Gemma 4." Validar antes de confiar.

### (b) Configuración recomendada
| Modo (set por router) | `thinking_budget_tokens` (body) | `--reasoning-budget-message` |
|---|---|---|
| direct/tool_only | 0 (+ `enable_thinking:false` via chat-template-kwargs) | n/a |
| quick_action | 64–96 | `"Decidido. Llamando tool."` |
| deep_action / vision | 256–384 | `"Resumen breve y llamo tool."` |
| research | 1024 | idem |

### (c) Veredicto
**VIABLE como tope p99 sólo si el prompt YA induce respuesta breve.** El budget NO arregla un prompt malo: si el modelo no había planeado terminar, cortarlo a 96 puede dejar argumentos inválidos (HumanEval Qwen3-9B cayó 94% → 78% con budget mal sintonizado, según el maintainer). Úsalo siempre con FR-CoT.

---

## Punto 6 — Decoding tricks que aceleran sin tocar fiabilidad

### (a) Sampling
- **Greedy (`temperature=0`, `top_k=1`)** para tool-calling: seguro y elimina overhead de sampler chain. No acelera mucho (el cuello es matmul) pero da reproducibilidad.
- **Cadena minimal:** `--samplers "top_k;temperature"` reduce CPU work del sampler (penalties, DRY, top_n_sigma son innecesarias para tool-calling determinista).

### (b) KV cache quantization
- **`--cache-type-k q8_0 --cache-type-v q8_0`** corta ~50% memoria KV con impacto mínimo. En tu E4B-Q4 16k ctx libera ~0.5-1 GB.
- ⚠️ **Issue #10552**: Q8 KV cache + draft model causa −16% en algunos setups (Qwen2.5-Coder-32B con drafter 0.5B en RTX 3090: 79.97 → 66.60 tok/s python). Sin draft model (tu caso), el riesgo es nulo.
- En decode puro la mejora es 0–2% (la KV cache q8 ahorra memoria, no compute). Útil principalmente para meter `-c` mayor o `--cache-reuse` más generoso.

### (c) Batch / parallel
- Ya tienes `--parallel 1` (correcto para voz monoslot).
- `--batch-size` y `--ubatch-size`: en decode (bs=1) no afectan; en prefill sí, pero prefill ya está controlado.

### (d) Flash-attn y SWA
- Ya activados (`--flash-attn on --swa-full`). Confirmado óptimo para Gemma con SWA híbrida.

### (e) Tabla de impacto en E4B-Q4 / 6 GB / decode

| Cambio | Δ tok/s decode | Δ calidad tool-call | VRAM | Veredicto |
|---|---|---|---|---|
| `--cache-type-k q8_0 -ctv q8_0` | +0–2% | ≈0 | −~0.5 GB | sí (sin draft) |
| Greedy + samplers minimal | +1–3% | =0 (determinista) | 0 | sí |
| `--mlock` | 0% en VRAM-only | 0 | 0 | irrelevante |
| Quant más agresiva del modelo (Q3_K_S) | +5–10% | RIESGO real, degrada Gemma E4B | −1 GB | NO recomendado |
| Compilar con CUDA Graphs si build no lo trae | +3–8% reportado | 0 | 0 | sí, si aplica |

### (f) Veredicto
**VIABLE como afinación menor, ~5% acumulado.** No es la apuesta principal.

---

## Configuración final propuesta (lista para pegar)

### llama-server
```bash
llama-server.exe ^
  -m gemma-4-E4B-it-Q4_K_M.gguf ^
  -c 16384 --parallel 1 --keep -1 ^
  --jinja --flash-attn on --swa-full ^
  --cache-reuse 256 ^
  --cache-type-k q8_0 --cache-type-v q8_0 ^
  --reasoning-budget-message "Decidido. Llamando tool." ^
  --samplers "top_k;temperature" ^
  --host 127.0.0.1 --port 8080 --metrics
```

### Body por modo (Python)
```python
ROUTES = {
    "tool_only": {
        "thinking_budget_tokens": 0,
        "chat_template_kwargs": {"enable_thinking": False},
        "temperature": 0.0, "top_k": 1,
        "max_tokens": 128,
        "grammar": GRAMMAR_FORCE_TOOL_CALL,  # GBNF que fuerza <|tool_call|>{...}
    },
    "quick_action": {
        "thinking_budget_tokens": 96,
        "temperature": 0.0, "top_k": 1,
        "max_tokens": 256,
    },
    "deep_action": {
        "thinking_budget_tokens": 384,
        "temperature": 0.2, "top_k": 20,
        "max_tokens": 768,
    },
    "research": {
        "thinking_budget_tokens": 1024,
        "temperature": 0.3, "top_k": 40,
        "max_tokens": 2048,
    },
}

def call_llm(user_text, asr_conf, history):
    route = router.classify(user_text, asr_conf)   # ver Punto 4
    body = {
        "messages": build_messages(user_text, history, template=route["template"]),
        "tools": TOOL_SCHEMA,
        **ROUTES[route["mode"]],
    }
    return requests.post(LLM_URL, json=body, stream=True)
```

### System prompt (fragmento clave)
```text
You are a voice assistant. Your output is spoken aloud or executed as a tool call.

When you need to call a tool, reason briefly in this EXACT 4-line format inside
the thought channel:

INTENT: <open_app|search|media_control|system_setting|clarify>
TOOL:   <function_name | none>
ARGS:   <k=v, k=v | —>
GO

Then emit the <|tool_call|> immediately. Never write more than 4 lines of thought.
If you cannot decide, INTENT=clarify and ask one short question.
```

---

## Recommendations (orden de implementación)

1. **Semana 1 — Mayor ROI**:
   - Implementar el system prompt FR-CoT (Punto 1). Medir distribución de tokens generados en n≥100 turnos reales antes de continuar.
   - **Benchmark de éxito:** mediana baja de 23 → ~15, p90 baja de 268 → ~80. Si se cumple, ya estás cerca del presupuesto sin tocar más.
2. **Semana 1-2**:
   - Implementar router de 3 capas (Punto 4): reglas + embeddings + fallback.
   - **Targeta:** ≥70% del tráfico real en modo `tool_only` con `thinking_budget_tokens=0`.
3. **Semana 2-3**:
   - Implementar two-track confirm filler + TTS paralelo (Punto 3).
   - **Métrica clave:** mouth-to-ear time-to-first-audio <800 ms para comandos crisp.
4. **Semana 3**:
   - Aplicar flags de afinación (Punto 6) y configurar `--reasoning-budget-message` (Punto 5).
   - A/B test con n-gram speculative SÓLO si tienes tiempo de medir; si no aporta ≥10% en mediana real, descarta.
5. **Backlog**:
   - Si FR-CoT no llega al objetivo, fine-tune QLoRA en 1-2k ejemplos `(query, brief_thought, tool_call)` propios. Esperable: +10-15 pts de fiabilidad sobre prompt-only.

### Benchmarks que deberían cambiar la estrategia
- Si tras Punto 1+4 la mediana E2E sigue >2 s y el p90 >5 s en comandos crisp → invierte en QLoRA.
- Si el ASR confidence empuja muchas frases a "ambiguous" injustamente → el cuello es VAD/STT, no el LLM.
- Si tu carga real tiene muchos turnos largos genuinos (research, multi-step) → el budget alto no debería tocarse; el problema es de UX, no de latencia.

---

## Caveats

- **Gemma 4 vs Gemma 3n confusion en el stack:** el usuario menciona "Gemma 4 / Gemma 3n E4B". Son arquitecturas distintas — Gemma 3n usa MatFormer + Per-Layer Embeddings; Gemma 4 es la familia oficial con thinking nativo y token `<|think|>`. El template Jinja y el formato de tool calling difieren. Si el GGUF Q4_K_M es Gemma 3n, los campos `enable_thinking` y `<|tool_call|>` pueden NO funcionar igual que en Gemma 4 oficial — verifica con un `curl` de prueba antes de asumir el comportamiento.
- **`thinking_budget_tokens` en Gemma E4B no está universalmente probado:** discussion #21338 muestra bugs intermitentes (flood de `<unused49>`) con Gemma 4 26B. Validar en el build b9090+ del usuario antes de depender de ello en producción.
- **N-gram speculative en MoE vs dense:** los benchmarks negativos citados son sobre Qwen3.6-A3B (MoE). En Gemma E4B (dense + per-layer-embeddings) el comportamiento puede diferir. Vale un A/B propio antes de descartar definitivamente.
- **Las cifras de "Brief Is Better" (Qi 2026, arXiv 2604.02155) son sobre Qwen2.5-1.5B/7B y Phi-3-mini.** Gemma E4B no fue testeado directamente. La extrapolación es razonable (FR-CoT es prompt-only y agnóstico al modelo) pero no probada empíricamente en tu modelo exacto.
- **Llama-3.2-3B y otros números de degradación CoD en sub-3B:** circulan en literatura secundaria pero el paper Xu et al. (arXiv 2502.18600) en su cuerpo principal sólo testeó GPT-4o y Claude 3.5 Sonnet. Toma con cautela cualquier cifra específica atribuida a Llama-3.2-3B sobre CoD; la conclusión cualitativa ("CoD libre no es seguro para modelos pequeños") sigue válida pero los números exactos en blogs requieren cross-check con el PDF.
- **`--cache-reuse 256` + system prompt cambiante por modo:** si el router cambia template con frecuencia, parte del prefix-cache se invalida. Mantén un system prompt único con secciones condicionales activadas por un flag en el primer user turn si quieres preservar el reúso. Esto NO es prefix-cache pinning (ya descartado por el usuario), sino simple oportunismo del flag `--cache-reuse`.
- **Speculative tool calling con efectos colaterales:** sólo aplicar a tools idempotentes/read-only. Para `send_message` o `delete_file` la pre-ejecución es inaceptable; el filler debe ser un confirm sin compromiso ("entendido, dame un segundo") y la ejecución debe esperar a la respuesta firme del LLM.
- **Fuentes con fecha 2026 verificadas:** los papers Qi 2026 (Brief Is Better), Yang et al. 2026 (Ares), y los benchmarks de speculative decoding (thc1006, defilan) son todos posteriores a marzo 2026 y publicados en plataformas verificables (arXiv, HackMD, HuggingFace, DEV.to). Las referencias de llama.cpp (commit acb7c79, PR #20297, issue #20632, discussion #21338, #21445) son del repo oficial ggml-org/llama.cpp y verificables.