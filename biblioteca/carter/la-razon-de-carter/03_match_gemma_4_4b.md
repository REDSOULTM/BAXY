# 03 — Match con Gemma 4 4B

**Fecha**: 2026-05-11

---

## 1. Qué dice la evidencia sobre Gemma 4 4B

### 1.1 Tool calling bias documentado

> "The 4b models have a **genuine tool-call bias regardless of prompt**. The 12b and 27b models (base and fine-tuned) correctly answer conversational questions in plain text even when tools are available. No-tool accuracy is **primarily a model size issue**, not a fine-tuning artifact."

— [HuggingFace Gemma 3 discussion #24](https://huggingface.co/google/gemma-3-27b-it/discussions/24)

**Recomendación documentada**: añadir al system prompt: *"Only call a tool when the user asks you to perform an action. For questions and explanations, respond in plain text."*

### 1.2 Tool count degrada accuracy

> "Large system prompts with 22+ tools result in accuracy degradation and format errors increase. This suggests keeping system prompts concise and toolsets limited (5-15 tools recommended) for optimal performance with the 4B model."

— Síntesis de [Google Gemma 3 4B forum thread](https://huggingface.co/google/gemma-3-27b-it/discussions/24).

### 1.3 Sampling oficial Gemma 4

Investigación previa confirmó:
- temperature=1.0, top_p=0.95, top_k=64, repeat_penalty=1.0
- max_tokens 1280 para tool calling
- `--jinja` en llama-server para chat templates correctos
- Special tokens manejados por Jinja (no hay que escribirlos manualmente)

### 1.4 Capability multimodal nativa

Gemma 4 E4B tiene encoder Conformer USM (audio) + projector mmproj-F16 (vision). El llama-server con mmproj cargado permite `image_url` en /v1/chat/completions. Carter ya lo usa para vision tools.

---

## 2. Mediciones reales con Gemma 4 4B en Carter

### 2.1 Bench oficial 54 P0 (2026-05-11)

- **PASS rate**: 41/54 (75.93%)
- **FAILs por funcionalidad**: 0
- **FAILs por latencia**: 3 (C02-01 +0.6s sobre budget, C14-01 +43s, C16-02 +0.03s)
- **PARTIALs**: 10 (todos latencia)

**Insight**: Gemma 4 4B HACE bien el trabajo. La arquitectura de Carter lo hace lento.

### 2.2 Latencia per tool count

| # Tools | n cases | Avg latency | Max | Target | Diagnóstico |
|--------|---------|-------------|------|--------|-------------|
| 0 | 22 | 3.9s | 11.8s | 3-5s | OK |
| 1 | 28 | 16.0s | 28.6s | 8-12s | **+33-100%** |
| 2 | 3 | 42.3s | 58.9s | 20s | **+110%** |
| 4+ | 1 | 73.2s | 73.2s | 30s | **+144%** |

### 2.3 Patrones de fallo del LLM observados (smoke previo)

- C13-03: "si no ves Aceptar no clickees" → llamó `system_time` (tool-call bias documentado)
- C14-26: filesystem_read sobre URL (tool selection ambigua)
- C14-01: emite gui_universal_action(click "Aceptar") sin haber visto pantalla (vision-less reasoning)

Estos son fallos del **4B tool-call bias**. Doc Google confirma: añadir instrucción explícita en system prompt mitiga ~50% de casos.

---

## 3. Adaptaciones que Carter YA tiene para Gemma 4 4B

✅ **Built**:
- Sampling oficial Gemma 4 (T=1.0, top_p=0.95, top_k=64)
- `--jinja` para chat templates
- mmproj-F16 cargado para vision
- `chat_template_kwargs: {"enable_thinking": False}` (Gemma 4 quirk: pone JSON en reasoning)
- Tool retrieval top-K (mitiga >22 tools)
- 14 anchors siempre incluidos (tools transversales)
- Causal focus post-action (UI-TARS-2 pattern)
- Loop detection v2 result-aware
- Snowball stems multilingüe destructive intent

---

## 4. Adaptaciones FALTANTES para 10/10 match

### 4.1 Mitigar tool-call bias del 4B

**Falta**: prompt explícito tipo *"Only call a tool when the user asks for an action. For questions, respond in plain text."*

Carter actualmente tiene reglas implícitas distribuidas en CORE_PROMPT (R9 trivial, R5 acción). No tiene la regla doc-recomendada en frase única corta.

**Cambio propuesto**: añadir línea explícita al inicio de CORE_PROMPT.

### 4.2 CORE_PROMPT 3400 → <1500 tokens

Doc Google: "keep system prompts concise". Carter actual 3400 tokens.

**Cambio propuesto**: cortar a 1200-1500 tokens, mover ejemplos a recuperación condicional por archetype.

### 4.3 Tools visibles ≤15 por turn

Doc Google: 5-15 tools recomendado para 4B.

Carter actual: anchors=14 + top-K=12 = **26 tools** visibles default. En anaphora boost: 14+20 = **34 tools** (sobre threshold).

**Cambio propuesto**: anchors=8 críticos + top-K=4-8 según archetype. Total ≤12-16.

### 4.4 Output JSON estricto con retry

Doc Google: "automatic conversion from Python functions to JSON schema may not always meet specific expectations". Carter actualmente acepta cualquier estructura del LLM y rewrite a posteriori.

**Cambio propuesto**: validar Pydantic schemas en boundary. Si el LLM emite JSON inválido en tool_call, retry con error específico (no re-prompt completo).

### 4.5 Estado externo de misión

Doc Google: 4B tiene "menor memoria de trabajo". Carter actualmente:
- ✅ `_LAST_VISION_LOCATE` cache (turn-scoped)
- ✅ `_TURN_BASELINE_SNAPSHOT` Win32 baseline
- ❌ NO tiene `MissionGoal` persistente con "qué pidió el user" + "qué falta hacer"

**Cambio propuesto**: dataclass `MissionGoal(text, expected_outcomes, current_state)` que se actualiza tras cada tool y se inyecta al LLM en cada follow-up.

### 4.6 Reducir LLM calls por tool

Cada tool en Carter → 1 LLM follow-up call (~6-10s en Gemma 4). 4 tools = 5 LLM calls = 25-40s.

**Cambio propuesto** (estructural):
- Si la tool tiene verifier=PASS y mission_goal NO completa, **encadenar** sin esperar follow-up.
- LLM follow-up SOLO cuando hay incertidumbre (tool=FAIL o verifier=None o mission_goal indica fin posible).

Esto requiere mission_goal verifier funcionando (P4 del 01_auditoria_arquitectura).

### 4.7 Vision inline en MISSION turn

Para misiones GUI, en vez de tener `vision_describe_dialog` y `vision_locate_target` como tools que el LLM debe pedir, **inyectar screenshot+descripción automáticamente** al context si el archetype es GUI.

Pattern UI-TARS-2: "Perception integrated to action token".

**Cambio propuesto**: en archetype MISSION o TOOL con tool GUI emitida, post-tool injecta screenshot + 1-line description al next_messages como user role (`[contexto visual: ...]`).

Ya tengo el opt-in `CARTER_V4_AUTO_VISION_DESCRIBE`, pero solo dispara en `gui_screenshot`. Generalizar.

### 4.8 Sin per-app hardcodes (V7 ya en CLAUDE.md)

step_planner._WEB_APP_URLS / _DEEPLINK_APPS / _NATIVE_APPS son trampa V7.

**Cambio propuesto**:
- Universal "open" handler: input(app_token) → consulta `apps.resolve_app` (que usa Get-StartApps + procesos + lnk). Si resultado es `kind=start_apps` → `app_open`. Si es URL conocida del registry → `web_open_url`. Si es scheme registrado HKCR (`is_protocol_registered`) → `gui_deeplink`.
- Eliminar listas hardcoded.
- Si la latencia sube, es el costo de honestidad arquitectónica. Documentar.

---

## 5. Decisiones para Carter+Gemma 4 4B (con evidencia)

| Decisión | Por qué Gemma 4 4B la necesita | Evidencia |
|----------|-------------------------------|-----------|
| CORE_PROMPT <1500 tokens | Reduce context noise + format error rate | Google docs Gemma 3 4B |
| ≤16 tools visibles per turn | Bajo threshold "22+ degrada" | Google docs |
| Frase explícita "only call tool if user asks for action" | Mitiga 4B tool-call bias | HF Gemma discussion #24 |
| Mission goal verifier | Compensa "menor memoria de trabajo" del 4B | Voyager pattern |
| Vision inline en GUI archetype | Pattern UI-TARS-2: percepción integrada | arxiv 2509.02544 |
| ModelCapability protocol | Decouple agent.py de quirks específicos | Pydantic AI |
| top-K=8 default, 12 en MISSION | RAG-MCP +30 pts accuracy en 4-7B | arxiv 2505.03275 |
| Reducir LLM calls (chain sin follow-up cuando posible) | "Each successive step 3x longer" | MLSys WukLab OSWorld-Human |

---

## 6. Lo que NO se puede lograr con Gemma 4 4B (limites estructurales)

Honestamente, hay cosas que **no son alcanzables sin cambiar de modelo**:

1. **OSWorld-level GUI workflows**: instalar Doom en Steam end-to-end con dialogos modales requiere razonamiento sobre UI dinámica. Frontier models 35B+ alcanzan 47-82%, 4B no aparece en leaderboard.

2. **Razonamiento de >6 pasos sin replan**: Gemma 4 4B pierde coherencia. Mitigación: `MissionGoal` + replan cada N pasos.

3. **Resolver tool ambiguity sin pista**: ejemplos C14-26 (filesystem_read sobre URL). El modelo no distingue path local vs URL cuando ambos están disponibles. Mitigación: validar argumentos en tool spec antes de dispatch.

4. **Latencia <3s en tools complejas**: una tool dispatch + LLM follow-up llega a ~6-10s mínimo. Para conversación pura sin tools, sí <3s.

**Para alcanzar OSWorld-level con Carter**, hay 2 caminos:
- **A**: cambiar a Qwen3-VL-7B (4-6GB VRAM, multimodal nativo SOTA open-source).
- **B**: fine-tune Gemma 4 4B con LoRA sobre los 540 casos del bench. Costo: ~1-2 días de training, ~$0 (local).

---

## 7. Criterios para match 10/10

Solo declaro 10/10 cuando:

- [ ] CORE_PROMPT medido <1500 tokens (`wc -c` /4 ≈ tokens estimados).
- [ ] Tools visibles ≤16 default (anchors 6-8 + top-K 6-8).
- [ ] Frase "only call tool if user asks for action" en CORE_PROMPT.
- [ ] `MissionGoal` dataclass implementado, usado por orchestrator.
- [ ] Vision inline en archetype MISSION/TOOL_GUI verificado funcionando.
- [ ] `ModelCapability` protocol decoupling agent.py.
- [ ] Bench oficial P0 ≥85% con budgets actuales (medible).
- [ ] Latencia 1-tool ≤12s (50% reducción medida).
- [ ] Sin per-app hardcodes (grep verificación).
- [ ] Tests del agent loop con mock Gemma response.

Score actual: **5/10**. Distancia a 10: 8 cambios estructurales, dependen mucho de Fase 3-4.

---

## 8. Fuentes

- [Google AI: Gemma 4 Function Calling](https://ai.google.dev/gemma/docs/capabilities/function-calling)
- [HuggingFace Gemma 3 discussion #24](https://huggingface.co/google/gemma-3-27b-it/discussions/24) — 4B tool-call bias
- [arxiv 2505.03275 RAG-MCP](https://arxiv.org/abs/2505.03275)
- [arxiv 2509.02544 UI-TARS-2](https://arxiv.org/abs/2509.02544)
- [MLSys WukLab OSWorld-Human](https://mlsys.wuklab.io/posts/oshuman/) — step latency 3x
- [Pydantic AI](https://ai.pydantic.dev/agent/) — provider abstraction
- [Voyager NeurIPS 2023](https://voyager.minedojo.org/)
- [llama.cpp function calling](https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md)
