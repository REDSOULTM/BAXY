# Refinamiento del Bucle Agentic con Gemma 4 E4B-it sobre llama.cpp — Veredictos por Tensión

**TL;DR**
- **T1 (chaining) y T2 (thinking)** son los dos puntos donde más latencia y fiabilidad puedes ganar sin reescribir nada: (a) cambia el "auto-encadenado" implícito por un **mensaje de continuación estructurado tras la observación + retry forzado con `tool_choice="required"` sobre un subset de 1 herramienta**, y (b) sustituye el FR-CoT inyectado en el prompt por el **sampler nativo `--reasoning-budget` / `thinking_budget_tokens` de llama-server**, que cuenta tokens dentro del canal `<|channel|>thought` de Gemma 4 y los corta limpiamente sin que el formato pueda fugarse al canal de salida. Evidencia: Magnet (arXiv:2503.07826) demuestra +32.5 pp en multi-turn de BFCL-v3 sobre Qwen2.5-14B con LoRA + mDPO (Magnet-14B-mDPO = 68.01 overall); FunReason-MT (arXiv:2510.24645) lleva Qwen3-4B-Instruct-2507 de 15.75% → 56.50% multi-turn; `--reasoning-budget` con `--reasoning-budget-message` recuperó HumanEval de 78%→89% en Qwen3-9B según el merge oficial (commit acb7c790698fa28a0fbfc0468804926815b94de3).
- **T3 (layout de cache)**: el experimento de "core-set fijo de 15 tools" fracasó probablemente porque en Gemma 4 la **cache-reuse está rota por la arquitectura de Shared KV Cache** (Issue #21468 de llama.cpp), no por mal layout — independientemente del orden, cada turno re-procesa el prompt entero hasta que el PR #21749 (pos_min_thold=0 con `--swa-full`) esté en tu build. La aritmética del layout sigue siendo correcta (stable-first, variable-tail, usuario al final), pero el ROI hoy es pequeño hasta arreglar la caché; mide build b9090 contra master.
- **T4 (sampling)**: los defaults de Gemma (T=1.0 / top_p=0.95 / top_k=64) son los oficiales para *generación con thinking*, pero para **modos de acción con grammar activa** son innecesariamente altos. Recomendación: **T≈0.2, top_p=0.9, top_k=20, min_p=0.05 en modos fast_action/quick_action**; mantener defaults en deep/research/chat. **T5**: 3 249 líneas no es deuda crítica si están bien estructuradas; refactor a *phase pipeline* (no FSM completo) con golden-traces — ROI medio, no urgente; honesto: si el sistema va a estabilizarse, **no refactorices**.

---

## Key Findings

1. **Multi-turn FC en SLMs <10B es estructuralmente débil.** El paper "LLMs Get Lost in Multi-Turn Conversation" (arXiv:2505.06120, Laban et al., Microsoft Research/Salesforce, mayo 2025) midió la caída sobre 15 LLMs que van desde LLaMA-3.1-8B-Instruct hasta Gemini 2.5 Pro: *"a 25-point drop from single-turn performances of 90%"* (de 90% → 65%) en conversaciones underspecified. En BFCL-v3 multi-turn, fine-tunes especializados de 2024 quedan en el rango bajo (~10% según el reporte Magnet: *"some public models have only around 10% success rate"*; ToolACE-8B muestra single-digit en sus filas de multi-turn category en la tabla de BFCL).

2. **Existe un techo claro alcanzable hoy con fine-tuning ligero en 4B–8B**: xLAM-2-8b-fc-r alcanza **69.25%** BFCL-v3 multi-turn (APIGen-MT, arXiv:2504.03601); xLAM-2-3b-fc-r alcanza **56.00%**. FunReason-MT (arXiv:2510.24645) lleva Qwen3-4B-Instruct-2507 de **15.75% → 46.90% (SFT) → 56.50% (RL)** multi-turn en BFCL-v3. Magnet-14B-mDPO (arXiv:2503.07826) gana +32.5 pp en multi-turn sobre Qwen2.5-Coder-14B con LoRA (lr=1e-6) + mDPO, llegando a 68.01 BFCL-v3 overall.

3. **El bug específico de FR-CoT en Gemma E4B es estructural, no de prompt-engineering**. La model card oficial (huggingface.co/google/gemma-4-E4B-it y ai.google.dev/gemma/docs/core/prompt-formatting-gemma4) dice literal: *"Disabled Thinking Behavior: For all models except for the E2B and E4B variants, if thinking is disabled, the model will still generate the tags but with an empty thought block"*. Es decir, en E4B con thinking OFF **no hay canal de pensamiento**; cualquier "INTENT/TOOL/ARGS/GO" que pidas en el prompt sale por content, no por reasoning_content — esto explica la regresión 6/6→3/6 que mediste.

4. **llama.cpp ya tiene el sampler oficial que necesitas para T2**: `--reasoning-budget N` se convirtió en sampler real en el commit `acb7c790698fa28a0fbfc0468804926815b94de3`; `--reasoning-budget-message` inyecta un mensaje antes del end-of-thinking. Per-request `thinking_budget_tokens: N` funciona vía body (Discussion #21445). Evidencia de ROI: Qwen3-9B HumanEval con budget = 1000 + mensaje de transición recuperó de 78% (corte abrupto) a 89%, frente a 94% sin budget.

5. **Gemma 4 + cache-reuse está rota hoy** (Issue #21468). Root cause: Shared KV Cache (los últimos `num_kv_shared_layers` reusan K/V). PR #21749 ("server: ensure prompt caching for SWA models") arregla parte: *"In short, this makes inference faster for SWA models when using prompt caching"*. Esto invalida la conclusión "core-set fijo fue 2× peor": el layout no podía funcionar porque cada turno se re-prefilleaba completo.

6. **El sampling actual es subóptimo para grammar-tool-calling**. Greedy/baja-T es estándar industria para JSON estructurado y function-calling (machinelearningplus, amitray, letsdatascience, prompt-engineering guide); Gemma defaults son para chat. Per-mode sampling es la disciplina que ya implementas para `thinking_budget` — extiéndela a temperature/top_p.

7. **Evidencia sobre budget de CoT no es monótona**. El paper *"Brief Is Better: Non-Monotonic Chain-of-Thought Budget Effects in Function-Calling Language Agents"* (arXiv:2604.02155, Xuan Qi, IIIS Tsinghua, abr 2026) midió específicamente sobre Qwen2.5-1.5B-Instruct: *"brief reasoning (32 tokens) dramatically improves accuracy by +45% relative over direct answers (from 44.0% to 64.0%), while extended reasoning (256 tokens) degrades performance well below the no-CoT baseline, to 25.0% (McNemar p < 0.001)"*. El resultado es modelo-específico y la nota del paper aclara que *"the optimum is as brief as 8–16"* para algunas tareas. No traduces 1:1 a Gemma 4 E4B, pero refuerza la dirección: **budget corto + medir**, no FR-CoT inyectado.

---

## T1 — Chaining dependiente search → open/play/read

### Diagnóstico
Patrón mejor documentado de 2025 en SLMs. Tu síntoma — `filesystem.search` OK, segundo turno en prosa — es el modo de fallo *promise-without-action* caracterizado por Red Hat Developer (feb 2026): *"Smaller models often state what they are about to do instead of actually performing the action."* La causa raíz es el chat template: tras la observación, Gemma 4 vuelve al rol `model` con contexto natural de "responder al usuario", no de "decidir si quedan pasos". Los guards que tienes capturan el síntoma; el nudge ayuda en parte pero pelea contra el template.

### Opciones

| Opción | Tool-call reliability esperada | Latencia añadida | Riesgo regresión | Esfuerzo |
|---|---|---|---|---|
| A. **Pre-Act-lite: continuación estructurada `<observation>...<next_action?>` como mensaje `user` (no `tool`)**, con subset reducido a 2–3 herramientas plausibles | +20–30 pp (proyectado desde Pre-Act arXiv:2505.09970, que reporta *"70% improvement in Action Recall"* sobre ReAct en Llama-3.1-8B fine-tuneado) | +50–100 ms (segundo prefill pequeño) | Bajo (no toca el primer pass) | 1–2 días |
| B. **Forced-retry `tool_choice="required"` + subset-of-1** cuando el reply_validator detecta "promesa sin acción" en el segundo turno | +15–25 pp en chains de 2 pasos | +1 turno completo (~1.5–3 s) sólo en caso de fallo | Bajo | 0.5 día (ya tienes motor de forced-retry) |
| C. **Microagente de continuación**: trigger-injected "open_after_search" cuando el primer tool es `filesystem.search` y devuelve ≤3 hits — auto-elige el más probable y emite `office.open` programáticamente | ~100% en camino feliz | Reduce latencia (un turno menos) | Medio (auto-execute puede abrir archivo equivocado) | 1 día |
| D. **QLoRA sobre Gemma 4 E4B en 2k–5k trazas de chaining** (search→open, list→read, find→play) | Magnet: +18.5 pp multi-turn en 7B Qwen2.5-Coder; FunReason-MT lleva Qwen3-4B de 15.75 → 46.90 (SFT) → 56.50 (RL) multi-turn | Sin coste en inferencia | Alto (puede romper formato `<|tool_call|>` nativo de Gemma; re-entrenar chat template) | 2–4 semanas + dataset + smoke |
| E. **Cambiar modelo base a xLAM-2-3b-fc-r** (Llama-3.1-3B base, 56.00% BFCL-v3 multi-turn) o xLAM-2-8b-fc-r (69.25%, no cabe holgado en 6 GB Q4_K_M) | Salto cualitativo | Similar (3B) / peor (8B) | Cambio de modelo: chat template (Hermes-style), tool_call format y sampling de cero | 1 semana de re-medición |

### Veredicto para tu stack
**A + B en cascada; mantener E como plan B si tras eso sigues <80% en chains.** **No abrir QLoRA todavía**: ROI alto pero el cuello es el dataset (2k trazas multi-turn de calidad no se generan en una tarde), y rompes el chat template oficial. Patrón ganador, menor coste/riesgo:

1. Tras la observación de una herramienta "navegacional" (search, list, find, query), **inyecta un mensaje role=user** (no `tool`) con plantilla fija (no inyectes esto si el primer turno cerró explícitamente la solicitud).
2. Si el reply_validator detecta promesa-sin-acción **en este segundo turno**, **forced-retry con `tool_choice="required"` y subset reducido a 1 sola herramienta** (la inferida por el router del verbo original — *abrir/reproducir/leer*).
3. Microagente para search-1-hit: si `len(results)==1` → auto-execute `office.open` sin segundo turno de LLM. Mantener guard de honesty para no decir "abierto" si la app no confirmó.

**Fuentes**: Pre-Act (arXiv:2505.09970), Magnet (arXiv:2503.07826), FunReason-MT (arXiv:2510.24645), Tool-N1 (arXiv:2505.00024), llama.cpp Issue #20164 (looping en optional params), Red Hat Developer feb 2026, Augment Code prompting guide (*"Models will often call tools in incorrect ways... It is best to validate the input, and return a tool output that explains the error"*), BFCL v3 (gorilla.cs.berkeley.edu/blogs/13_bfcl_v3_multi_turn.html), llm-stats.com/benchmarks/bfcl-v3-multiturn.

### Snippet listo
```python
# agent.py — tras tool_result en modos fast_action/quick_action
NAV_TOOLS = {"filesystem.search", "filesystem.list", "music.find", "mail.query", "calendar.query"}

def maybe_inject_continuation(turn):
    if turn.first_tool not in NAV_TOOLS or turn.user_intent_terminal:
        return None
    candidate = infer_next_tool(turn.user_intent_verb, turn.tool_result)
    # Camino feliz: 1 hit y candidato claro → auto-execute sin LLM
    if candidate and len(turn.tool_result.hits) == 1:
        return AutoExecute(tool=candidate, args={"path": turn.tool_result.hits[0]})
    # Camino guiado: nuevo turn user con next-action explícito
    msgs = turn.messages + [{
        "role": "user",
        "content": (
            f"<observation>{summarize(turn.tool_result, max_hits=3)}</observation>\n"
            f"Next action? If the original request implied {turn.user_intent_verb}, "
            f"call the relevant tool NOW with the most relevant result. "
            f"If no clear candidate, reply exactly: ASK"
        )
    }]
    subset = [candidate] if candidate else turn.subset[:2]
    return ContinuationPass(msgs, subset=subset)

# Si tras este pass el reply_validator detecta "promise-without-action":
if reply_validator.is_promise_without_action(reply):
    return ForceToolPass(messages=msgs, tool_choice="required", tools=[candidate])
```

### Métrica obligatoria
- **Chain success rate** (% de turns donde la cadena de 2 pasos completa correctamente) sobre dataset de 50–100 prompts navegacionales reales.
- **p50/p90 latencia total** con vs sin continuación estructurada (esperado +50–100 ms p50).
- **False auto-execute rate** del microagente de 1-hit (debe ser <2%).

---

## T2 — Reducir coste de THINKING sin romper tool-call

### Diagnóstico
Coincide con dos hallazgos publicados:
- "Brief Is Better" (arXiv:2604.02155): el budget de CoT óptimo en agentes function-calling es **no monótono**; sobre Qwen2.5-1.5B-Instruct, *"brief reasoning (32 tokens) dramatically improves accuracy by +45% relative over direct answers (from 44.0% to 64.0%), while extended reasoning (256 tokens) degrades performance well below the no-CoT baseline, to 25.0% (McNemar p < 0.001)"*. El óptimo puede ser tan breve como 8–16 tokens en ciertas tareas.
- El bug de FR-CoT en E4B es estructural (ver Key Finding #3). Tu FR-CoT pelea contra el chat template.

### Opciones

| Opción | Tool-call rel. esperada (sobre 6/6) | Latencia thinking p90 | Riesgo regresión | Esfuerzo |
|---|---|---|---|---|
| A. **`--reasoning-budget 256` global + `--reasoning-budget-message`** (sampler nativo de llama.cpp) | 5–6/6 | ~1 s (cae de 4.3 s) | Bajo — budget bajo puede dañar tareas duras; usa override per-request | 1 día |
| B. **Per-mode `thinking_budget_tokens` vía body** (sin reload): quick=64, fast_info=128, deep=512, research=2048 + complexity_router → algunas peticiones a `enable_thinking=false` + `tool_choice="required"` + grammar | 6/6 en crisp (grammar fuerza el formato), 5–6/6 en ambiguos | quick=200–400 ms, fast_info=600 ms | Bajo-Medio | 2–3 días |
| C. Chain-of-Draft prompt (arXiv:2502.18600, *"as little as only 7.6% of the tokens"* — token reduction medido en Claude 3.5 Sonnet para tareas de sports understanding; en GSM8k CoD = 91% acc vs CoT ~95% con muchos menos tokens) | 4–5/6 — mismo riesgo de fuga en E4B | Reduce mucho CoT en otros modelos, no probado en function calling 4B | **Alto (mismo bug que FR-CoT)** | 0.5 día — esperable regresión |
| D. Disable thinking + GBNF grammar que fuerza JSON tool_call + `tool_choice="required"` en modos de acción crisp | 5–6/6 (cura el 2/6 con grammar) | Mínima | Bajo en crisp, Alto en ambiguous (pierde razonamiento que ayuda en casos como "pon algo de jazz") | 1 día |
| E. **A + B + D combinados con complexity_router**: fast-path (crisp → D) + slow-path (ambiguous → A con budget=128) | **6/6 en crisp + 5–6/6 en ambiguos** | crisp: ~300 ms; ambiguous: ~1.2 s | Bajo si el router es bueno (tu router holdout=0.881 ya es suficiente) | 3–5 días |

### Veredicto para tu stack
**E**: complexity_router + dos caminos diferenciados. Es lo que ya casi tienes, **apoyándote en el sampler nativo de llama.cpp** en vez del prompt-injection FR-CoT. Acciones concretas:

1. **Relaunch llama-server con `--reasoning-budget 256 --reasoning-budget-message "\n</thought>\nFinal answer:"`** como tope global (default seguro).
2. **Per-request override** vía `thinking_budget_tokens`:
   - `quick_action`: `chat_template_kwargs={"enable_thinking": false}` + grammar GBNF de tool_call + `tool_choice="required"` (cura el 2/6 OFF actual).
   - `fast_info`: `thinking_budget_tokens=96`.
   - `deep_action` / `vision_action`: `thinking_budget_tokens=512`.
   - `research`: `thinking_budget_tokens=2048` (tu valor actual).
3. **Borra el FR-CoT del system prompt**. Era ingenioso pero el prompt-injection es post-template; el modelo no sabe que esa estructura va al canal de pensamiento — sale por content y rompe el parser. Con el sampler, el corte ocurre dentro del canal real `<|channel|>thought`.

#### Por qué E4B se traga el formato como output
La model card oficial (huggingface.co/google/gemma-4-E4B-it) confirma: *"Trigger Thinking: Thinking is enabled by including the `<|think|>` token at the start of the system prompt. To disable thinking, remove the token. Standard Generation: When thinking is enabled, the model will output its internal reasoning followed by the final answer using this structure: `<|channel|>thought\n[Internal reasoning]<channel|>` Disabled Thinking Behavior: For all models except for the E2B and E4B variants, if thinking is disabled, the model will still generate the tags but with an empty thought block"*. Tu `--jinja` lo maneja correctamente sólo si activas thinking vía system (con `<|think|>`) y dejas que llama.cpp tope los tokens dentro del canal.

### Snippets listos

**Server launch (flags añadidos)**:
```
llama-server -m gemma-4-E4B-it-Q4_K_M.gguf --jinja --flash-attn on --swa-full \
  --cache-reuse 256 --keep -1 -c 16384 --parallel 1 \
  --reasoning-budget 256 \
  --reasoning-budget-message "\n</thought>\nFinal answer:"
```

**Per-request body por modo**:
```python
def request_for_mode(mode, messages, tools):
    base = {"model": "gemma4-e4b", "messages": messages, "tools": tools}
    if mode == "quick_action":
        return base | {
            "chat_template_kwargs": {"enable_thinking": False},
            "tool_choice": "required",
            "temperature": 0.2, "top_p": 0.9, "top_k": 20, "min_p": 0.05,
            "max_tokens": 160,
        }
    if mode == "fast_info":
        return base | {"thinking_budget_tokens": 96, "max_tokens": 220}
    if mode == "deep_action":
        return base | {"thinking_budget_tokens": 512, "max_tokens": 320}
    if mode == "research":
        return base | {"thinking_budget_tokens": 2048, "max_tokens": 800}
    return base
```

### Métrica obligatoria
- **% tool-call OK** en dataset de 6 crisp + 6 ambiguous (tu eval actual).
- **p50/p90 thinking tokens emitidos** por modo (length de `reasoning_content`).
- **Tasa de "format leak"**: % de respuestas donde aparece literal "INTENT:" o "TOOL:" en `content` (debe caer a 0 al quitar FR-CoT).

---

## T3 — Subset dinámico vs estabilidad de prefijo (KV cache)

### Diagnóstico — dos problemas independientes confundidos en tu experimento

**(a) Layout matemáticamente correcto (independiente del modelo).** Cache-reuse en llama.cpp es *longest-prefix match*: se reusa hasta el primer token divergente. Tu plantilla actual `[SYSTEM_RULES + TOOLS_DINÁMICAS(4–6) + HISTORY + USER]` muta la cabecera de TOOLS cada turno → fragmenta cache desde el byte que cambia. Layout óptimo:

```
[STABLE_HEADER (persona, rules, fechas, contexto general)]
[CORE_TOOLS (opcional, ver abajo)]
[VARIABLE_TOOLS_DINÁMICAS_DEL_ROUTER]
[HISTORY]
[USER]
```
Con esto, el prefill cacheado cubre `[STABLE_HEADER + CORE_TOOLS]`, y sólo se re-prefillea la cola variable + historia + user. Es lo que aprovecha `--cache-reuse 256`.

**(b) Por qué tu experimento "10× mejor en aislamiento, 2× peor end-to-end".** Dos causas combinadas:

- **Distractor cost**: meter 15 tools donde sólo se usan 4–6 degrada selección. Hammer (arXiv:2410.04587) demuestra que el "function masking" durante train es lo que estabiliza esto en modelos <10B; "Gaming Tool Preferences" (arXiv:2505.18135) muestra *"over 10 times more usage from GPT-4.1 and Qwen2.5-7B"* cuando se edita la descripción de una herramienta, evidenciando que las descripciones de tools no-usadas compiten con las relevantes.
- **Crucial: Gemma 4 + llama.cpp tiene cache-reuse rota.** Issue #21468: *"cache reuse is not supported for Gemma 4 models despite -fa enabled and --swa-full"*. Root cause = Shared KV Cache. PR #21749 ("server: ensure prompt caching for SWA models" por shipped-it) corrige: *"In short, this makes inference faster for SWA models when using prompt caching"*. Verifica si tu build b9090 lo incluye: `git log --grep "shipped-it"` o el SHA del PR. Si **no** lo incluye, el experimento del core-set no podía ganar — la cache se invalidaba turno-a-turno por la SWA, no por tu layout.

### Cálculo concreto para tu setup
Prompt típico estimado:
- system_rules (estable): ~400 tok
- 65 tools schema completo: ~7 800 tok (~120 tok/tool)
- 4–6 tools subset: ~600 tok
- historia comprimida: ~1 200 tok
- user: ~30 tok
- ventana: 16 384 tok

**Escenarios** (asumiendo cache-reuse funcional con PR #21749 aplicado):

| Layout | Stable cached prefix | Reprefill por turno | Distractor cost |
|---|---|---|---|
| Naïve (tools dinámicas adelante) | 0 tok | ~2 200 tok | 6 tools relevantes |
| **Stable-first + dynamic-tail** (recomendado) | ~400 tok | ~1 800 tok | 6 tools relevantes |
| Core-set 15 + tail dinámico | ~2 200 tok | ~1 200 tok | **15 distractors** |
| Core-set 8 + tail dinámico (sweet spot) | ~1 360 tok | ~1 440 tok | **8 distractors** |
| 65 tools fijo | ~8 200 tok | ~1 230 tok (sólo historia+user) | **65 distractors → desastre tool-call** |

A nivel prefill puro, core-set 8 minimiza re-prefill manteniendo distractores manejables. **Pero el ROI real depende totalmente de que cache-reuse funcione**. Hoy en Gemma 4 con build pre-PR-21749 no funciona, así que el experimento del usuario fue correctamente medido: el layout no ayuda si la cache no se reusa.

### Veredicto para tu stack
**Tres acciones en este orden:**

1. **Verifica que `--swa-full` + `--cache-reuse 256` realmente reusan**. Logs: busca `slot update_slots ... cache_hit = N` con N > 0; o `forcing full prompt re-processing due to lack of cache data`. Si ves esto último, **el PR #21749 no está en tu build**. Cherry-pick o sube a master.
2. Con la cache funcionando, **adopta layout stable-first + dynamic-tail SIN core-set**. Reduce fragmentación sin añadir distractors. Ganancia segura.
3. Sólo si quieres ir más allá: prueba **core-set de 6–8 herramientas verdaderamente always-relevant** (`clarify`, `cancel`, `read_back`, `set_timer`, `time_now`, `volume`, +1–2). Mide tool-call accuracy con vs sin core; espera **regresión ligera (−2–4 pp) compensada por +20–40 ms prefill ahorrado**. Tu medida de 2× peor probablemente fue por elegir 15 sin auditar relevancia.

### Snippet — layout (plantilla Jinja personalizada)
```jinja
{% if messages[0]['role'] == 'system' %}
<|turn|>system
{{ messages[0]['content'] }}{# STABLE: persona, rules, locale; ~400 tok #}

{% if core_tools %}<tools>
{% for t in core_tools %}{{ t | tojson }}
{% endfor %}</tools>{% endif %}

{% if variable_tools %}<tools>
{% for t in variable_tools %}{{ t | tojson }}
{% endfor %}</tools>{% endif %}
<|turn|>{% endif %}
{# History + last user turn #}
...
```

### Métrica obligatoria
- `cache_hit` en logs por turno (esperado: ~ stable_prefix_len tokens).
- p50/p90 prefill ms (esperado: 100–300 ms cuando hay hit, vs 800–900 ms hoy).
- Δ tool_call accuracy si se introduce core-set.

---

## T4 — Sampling para tool-calling

### Diagnóstico
Defaults de Gemma (T=1.0/top_p=0.95/top_k=64) son los recomendados por Google para *generación con thinking activo y chat general*, no para tool-calling con grammar. Evidencia industria (machinelearningplus, amitray "*Temperature 0 enables greedy decoding... ideal for factual tasks, classification, data extraction, and any scenario where consistency matters more than creativity*", letsdatascience): **temperature baja / greedy es estándar para JSON estructurado**. Sutileza: en reasoning models OpenAI bloquea T=0 porque colapsa cadenas internas. Para Gemma 4 con `<|think|>` activo, **el thinking sí se beneficia de variance, pero la emisión del tool_call sí debe ser cuasi-determinista**.

Como llama-server aplica un único `temperature` por request, no puedes separar fases — pero sí diferenciar **por modo**, que es lo que tu router ya decide.

### Recomendación numérica

| Modo | temperature | top_p | top_k | min_p | repeat_penalty | Justificación |
|---|---|---|---|---|---|---|
| `fast_action`, `quick_action` (grammar + thinking OFF) | **0.2** | 0.9 | 20 | 0.05 | 1.0 | grammar garantiza forma; baja-T mejora estabilidad de nombre y args |
| `fast_info` (thinking budget 96) | 0.6 | 0.95 | 40 | 0.05 | 1.05 | algo de variance para razonar breve |
| `deep_action`, `vision_action` (budget 512) | 0.7 | 0.95 | 50 | 0.0 | 1.05 | defaults moderados |
| `audio_mode`, `research` | 1.0 | 0.95 | 64 | 0.0 | 1.0 | defaults Gemma |
| `chat` libre | 1.0 | 0.95 | 64 | 0.0 | 1.0 | defaults Gemma |

**`repeat_penalty=1.05` en modos cortos**: previene el bucle documentado en llama.cpp Issue #20164 (*"the model gets stuck in broken loops"*) donde el modelo repite la misma tool-call con args vacíos.

### Riesgos y métricas
- **Lenguaje**: bajar T<0.5 en fases que generen texto al usuario empobrece la respuesta. Aplica solo a modos donde el output es un tool_call o un summary corto (max_tokens=160 ya capado).
- **Tool-call rate**: medir en dataset crisp pre/post — esperado ↑ 5–10 pp y ↓ varianza turn-a-turn.
- **NLG quality** del summary pass: subjective check sobre 30 respuestas; si suena "robótico", subir a T=0.4.

### Veredicto
**Sí, baja la temperatura solo en modos de acción.** Mejora gratis con riesgo controlado. No la apliques globalmente.

---

## T5 — Deuda arquitectónica de `agent.py` (3 249 líneas)

### Diagnóstico honesto
3 249 líneas concentradas no es "monstruoso". Continue.dev orchestrator y el agent loop de Aider están en rangos similares (~2 000–4 000 líneas en un módulo). El **riesgo real** no es el tamaño; es:

1. **Acoplamiento entre el loop, los guards y la recovery** — si cambias el orden de un guard, regresas otra ruta.
2. **Difícil de testear unitariamente** cuando el bug aparece en la 4ª iteración con ciertos guards activos.
3. **Onboarding**: dependencia mental implícita del orden de operaciones.

Patrones publicados:
- **LangGraph** modela el loop como grafo explícito con checkpoints + replay (langchain.com/blog/planning-agents). Útil pero introduces dependencia pesada y pierdes control fino sobre prefijo de prompt y sampler.
- **Phase pipeline / orquestador-política separados** (Orchestral, arXiv:2601.02577): cada fase es función pura `(state) → state`, policies intercambiables.
- **State machine explícito** (AppsTekCorp design patterns): útil con >5–6 estados; overkill para 3–4 estados reales.

### Opciones

| Opción | Reducción riesgo regresión | Esfuerzo | ROI |
|---|---|---|---|
| A. **No tocar; añadir golden-trace tests** (snapshot de turnos típicos + assert sobre el reply final) | Medio (capturas regresiones después) | 1 semana | **Alto** |
| B. **Phase pipeline incremental**: extrae cada fase (router→planner→pass1→guards→pass2→summary) a función con `TurnState` dataclass; agent.py queda como pipeline director de ~300 líneas + 5–6 fases de ~400 líneas | Alto (cada fase testeable) | 3–4 semanas | **Alto si vas a iterar más; medio si estable** |
| C. State machine completo (transitions library / statesman) | Alto-Medio | 4–6 semanas | Bajo (overkill para 3–4 estados) |
| D. Migrar a LangGraph | Alto en algunas dimensiones, regresiones en otras | 6–10 semanas | **Bajo** — perderías control sobre prefijo de prompt, sampler, jinja |
| E. **No tocar arquitectura, sí extraer dos cosas: (1) los 8 guards a módulo con interface `Guard.check(reply, ctx) → Optional[Action]` componibles; (2) la recovery a una máquina de errores pequeña** | Medio | 1 semana | **Alto** |

### Veredicto honesto
**A + E primero (2 semanas combinadas).** No reescribir. El refactor completo a phase-pipeline (B) tiene ROI **sólo si planeas añadir 2–3 modos nuevos o más herramientas en los próximos 3 meses**; si el sistema va a estabilizarse, **el ROI es bajo y la regresión de un refactor grande es real**. Has invertido medición en este código; tirarlo para tener un "shape" más limpio sin ganancia funcional es deuda inversa.

**Test de decisión**: si en las últimas 4 semanas has tocado >3 partes diferentes de `agent.py` por bugs cruzados → refactor B vale. Si los bugs estaban localizados → quédate con A+E.

---

## Detalles técnicos transversales

### Gemma 4 E4B + llama.cpp — gotchas específicas
- **`<|think|>` token va en el system prompt, no en el body**. Si tu jinja personalizado lo omite, *no hay thinking aunque envíes `enable_thinking=true`*. Verifica con `--verbose` que el prompt renderizado contiene `<|think|>`.
- **Shared KV Cache rompe cache-reuse hasta PR #21749** — verifica build b9090.
- **`tool_choice="required"` activa grammar_lazy=false**: la grammar de tool_call se aplica desde el principio del turn, forzando el formato. Combinado con `enable_thinking=false` te da el "cure del 2/6" en T2.
- **Issue #21384**: Gemma 4 puede serializar arrays con `{`/`}` en values como string. Valida la deserialización si tienes herramientas con args que contengan JSON inline.

### llama.cpp — flags relevantes 2025–2026
- `--reasoning-budget N` (PR #13771, sampler real en commit `acb7c790698fa28a0fbfc0468804926815b94de3`)
- `--reasoning-budget-message MSG` — mensaje inyectado antes del end-of-thinking
- Per-request `thinking_budget_tokens: N` en body (Discussion #21445)
- `tool_choice: "required"` — soportado; activa grammar no-lazy
- `chat_template_kwargs: {"enable_thinking": false}` — pasado a Jinja, controla `<|think|>` en el render

---

## Recommendations consolidadas (orden de ejecución)

1. **Esta semana (T2)**: relanzar llama-server con `--reasoning-budget 256 --reasoning-budget-message "\n</thought>\nFinal answer:"`. Borrar FR-CoT del system prompt. Implementar per-mode `thinking_budget_tokens`; en `quick_action`, `enable_thinking=false` + `tool_choice="required"` + grammar GBNF mínima de tool_call. **Aprobación**: tool-call OK ≥5/6 en crisp, ≥4/6 en ambiguous; thinking p90 ≤200 ms en quick.
2. **Semana 1–2 (T1)**: implementar continuación estructurada Pre-Act-lite (mensaje role=user con `<observation>` + "next action?") tras tool navegacional; añadir microagente de 1-hit auto-execute; mantener reply_validator + forced-retry como fallback. **Aprobación**: chain success rate ≥80% sobre dataset de 50 prompts navegacionales.
3. **Semana 2 (T3)**: verificar cache-reuse en logs (`cache_hit > 0`). Si está rota → cherry-pick PR #21749 o actualizar build. Reordenar el prompt a stable-first/variable-tail. **Aprobación**: prefill p50 ≤400 ms en turnos con cache hit. Mantener subset dinámico (no core-set) hasta validar caché funcional.
4. **Semana 2–3 (T4)**: sampling por modo (tabla arriba). Smoke comparativo de 30 turns por modo. **Aprobación**: tool-call accuracy ↑ ≥3 pp en quick_action; NLG quality subjective sin regresión.
5. **Semana 3–4 (T5)**: extraer guards a módulo componible, recovery a state machine pequeño. Añadir golden-trace tests. **No refactor grande** salvo que el roadmap añada modos.
6. **Diferido (T1 follow-up)**: si tras 1+2 el chain success rate sigue <80% en chains de 3+ pasos, evaluar QLoRA sobre 2k trazas siguiendo el recipe Magnet (LoRA, lr=1e-6) sobre Gemma E4B. ROI alto pero coste de dataset es real.

### Umbrales que cambian decisiones
- Si chain success rate post-(1+2) sigue <70% → considerar **xLAM-2-3b-fc-r** como modelo base alternativo (cabe en 6 GB Q4_K_M, 56% multi-turn BFCL-v3 vs ~15.75% del Qwen3-4B-Inst baseline; Gemma 4 E4B no tiene número multi-turn BFCL-v3 publicado, pero su pareja Gemma 3 4B no supera el 30% en evaluaciones independientes). Latencia similar.
- Si los tokens de thinking p90 post-(1) siguen >150 con budget 256 → bajar a 128. Si <50 → la tarea está en zona "always 32 baseline" (Brief-is-Better).
- Si la cache nunca da hit aún con PR #21749 → reportar issue al upstream con repro; mientras tanto, bajar `-c` a 8192 para reducir coste del prefill completo.
- Si tras T4 el tool-call no mejora con T=0.2 → probar T=0.0 (greedy puro) en quick_action; si tampoco, el problema no es sampling sino prompt/template.

## Caveats

- Algunos números BFCL v3 multi-turn (xLAM-2-8b-fc-r 69.25%, xLAM-2-3b-fc-r 56.00%, Qwen3-4B 15.75%, ToolACE-8B en filas de single-digit en multi-turn) provienen de papers de los propios fine-tuners y BFCL oficial; cifras agregadas en `llm-stats.com` pueden conflatar "overall BFCLv3" con "multi-turn-only" — el "66.9% Nemotron-Nano-9B-v2 multi-turn" en una fuente parece ser el overall score (per NVIDIA tech report arXiv:2508.14444). Verifica al consumir.
- El PR #21749 no está confirmado en build b9090 según las fuentes que tengo. **Acción obligatoria**: `git log --oneline | grep "shipped-it\|swa-full.*prompt caching"` o equivalente. Sin él, T3 es inerte.
- El paper "Brief Is Better" (arXiv:2604.02155) es preprint reciente; sus números (32 tok = +45% rel acc en Qwen2.5-1.5B) son model-específicos y NO trasladables 1:1 a Gemma 4 E4B. Sí refuerza la dirección estratégica: **budget corto + medir**.
- El número Chain-of-Draft de *"7.6% of the tokens"* aparece en el paper original (arXiv:2502.18600) como reducción agregada *"across various reasoning tasks"*; en GSM8k específicamente, CoD logra 91% acc vs CoT ~95% con mucho menos consumo de tokens, pero no se reporta el 92.4% de reducción en esa tarea concreta.
- Latencias proyectadas son estimaciones de orden de magnitud; mide siempre en tu hardware (RTX 4060 Ti 16GB target 6GB). En una 4060 Ti con Gemma 4 E4B Q4_K_M, espera ~40–60 tok/s ≈ 17–25 ms/tok → 256 tok ≈ 4.3–6.4 s en el peor caso, ~2 s en p50 con budget bajo.
- QLoRA sobre Gemma 4 E4B es viable pero la integración GGUF + adapters en llama.cpp requiere convertir el adapter a GGUF (PR de soporte en upstream); Unsloth ofrece notebook para Gemma 4. No es plug-and-play.
- "Cambiar a xLAM-2-3b-fc-r" se debe validar en tu pipeline porque NO es Gemma — chat template, formato de tool_call (Hermes-style vs `<|tool_call|>`) y respuesta al sampling cambian; no es "swap el GGUF". Reservar como plan B si la fiabilidad multi-turn sigue baja tras T1+T2.