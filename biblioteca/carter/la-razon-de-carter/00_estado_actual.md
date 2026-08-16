# 00 — Estado Actual de Carter v4

**Fecha**: 2026-05-11
**Branch**: `feat/gemma4-integration`
**Modelo activo**: Gemma 4 E4B-it-Q6_K (~7.1 GB VRAM, llama-server :8080)
**Adapter**: `LlamaCppAdapter` (OpenAI-compat)
**Hardware**: Windows 11 26200, RTX 4060 Ti 16GB

---

## 1. Tamaño del sistema (medido)

```
Carter_v4/src/carter_v4/
├── 56 archivos .py
├── 15,251 LOC totales
├── 351 funciones y clases
├── 61 tools registradas (@tool decorator)
└── 16 archivos de tests (1,717 LOC)
```

Top-10 archivos por LOC:

| # | Archivo | LOC |
|---|---------|----|
| 1 | `agent.py` | **1,397** |
| 2 | `tools/apps.py` | 1,224 |
| 3 | `tools/gui.py` | 1,150 |
| 4 | `tools/gui_universal.py` | 754 |
| 5 | `tools/files.py` | 676 |
| 6 | `adapters/llamacpp.py` | 498 |
| 7 | `tools/composite_dispatcher.py` | 496 |
| 8 | `step_planner.py` | 481 |
| 9 | `tools/vision_tools.py` | 393 |
| 10 | `verifier_orchestrator.py` | 390 |

**Nota crítica**: el header de `agent.py` declara como objetivo `<400 LoC`. La realidad es **1,397 LoC (+250% drift)**.

---

## 2. Tests baseline (medido el 2026-05-11)

```
pytest tests/ -q
140 passed, 4 failed, 3 warnings in 34.30s
```

Fallos:
- `test_rewrite_triggers_for_short_action_claim` — assert string con tilde no matchea reply sin tilde.
- `test_rewrite_triggers_for_physical_action_es` — idem encoding.
- `test_rewrite_triggers_for_physical_action_en` — idem.
- `test_rewrite_does_not_trigger_for_long_concept_explanation` — assert obsoleto contra rewriter actualizado.

**Diagnóstico**: 4 tests son de mantenimiento (strings hardcoded contra texto que cambió). Cero regresiones funcionales reales. Test discipline insuficiente: nadie corrió `pytest` al hacer los rewrites de `verify.py`.

---

## 3. Bench smoke previo (sesión nocturna)

Resultados acumulados del 2026-05-11 (sesión de fixes anterior, 60 cases):

| Categoría | Casos probados | Replied (no exception) |
|-----------|---------------|------------------------|
| C01 conv | 3/3 | 100% |
| C02 ident | 2/2 | 100% |
| C06 routing | 3/3 | 100% |
| C07 apps | 2/2 | 100% |
| C08 web | 1/1 | 100% |
| C09 Steam | 4/4 | 100% |
| C11 terminal | 2/2 | 100% |
| C12 safety | 5/5 | 100% |
| C13 GUI | 5/5 | 100% |
| C14 misiones | 24/24 | 100% |
| C16 multilingual | 4/4 | 100% |
| C17 follow-up | 2/2 | 100% |
| C18 regresiones | 3/3 | 100% |
| **TOTAL** | **60/60** | **100% replied** |

**Importante**: "replied" ≠ "PASS lógico". Algunos casos respondieron correctamente con `NEEDS_USER` (honest) que el bench oficial puede contar como FAIL si esperaba acción. Falta correr el bench oficial con criterios de audit.

---

## 4. Arquitectura actual (alto nivel)

### Flujo de `run_turn(user_text)` — medido

```
1. user_text.strip()
2. pending_action check (confirm/cancel)
3. detect_mission(user_text)            [mission_detector.py]
4. plan_mission(llm.chat)               [planner.py — LLM call EXTRA]
5. build_system_message(...)            [prompt.py]
6. plan_turn(user_text)                 [step_planner.py — detect_archetype]
7. Pre-LLM short_circuit (canned reply) [step_planner.py]
8. Pre-LLM forced_tool_call             [step_planner.py — VIOLA V7]
9. tool_retrieval.select(top-K)         [tool_retrieval.py — RAG-MCP]
10. select_profile(archetype)           [turn_profile.py O models/gemma4.py — DUPLICADO]
11. llm.chat(system, messages, tools)   [adapter]
12. [Si tool_calls]:
    a. _execute_tool_calls(...)         [agent.py:636]
       - safety.evaluate_tool_call
       - tools.dispatch
       - verify.verify
       - _compute_post_action_steps     [POST_DEEPLINK_AUTO_STEPS injection]
       - loop_state.record + detect_stuck
    b. _chain_more_tools(...)           [agent.py:887]
       - depth<=8, budget<=120s
       - hasta que no haya tool_calls
13. [Si no tool_calls]:
    - looks_like_action_claim heuristics
    - retry-with-nudge
    - strip_planning_leakage
    - fix_carter_vocative
    - rewrite_claim_to_unverified
    - no_action_footer
14. _finalize_turn(...)                 [verifier_orchestrator outcome]
15. _append_history + return TurnResult
```

**Observación**: hay **3 routers de decisión** ejecutándose en serie antes de la primera LLM call:
- `detect_mission(user_text)` → boolean is_mission
- `plan_mission(user_text, llm.chat)` → Plan con steps (UN LLM CALL extra)
- `plan_turn(user_text)` → TurnPlan con archetype + forced_tool_call

Y **3 funciones `select_profile`**:
- `turn_profile.select_profile(archetype, is_destructive_intent)` → TurnProfile (qwen3 default)
- `models/gemma4.select_profile(user_text, multi_step)` → GemmaTurnProfile (override Gemma)
- `profiles.select_profile(profiles, vram_gb)` → Profile (hardware tier)

---

## 5. Fortalezas (alineadas a SOTA documentada)

1. **Verifier estructural por-tool** (`verify.py` 367 LOC). Patrón Voyager: self-verification via código, no LLM-as-judge. Confirmado por [Voyager NeurIPS 2023](https://voyager.minedojo.org/).
2. **Tool retrieval top-K con embedder** (`tool_retrieval.py`). Patrón RAG-MCP. Confirmado por [arxiv 2505.03275](https://arxiv.org/abs/2505.03275): accuracy 13.62% → 43.13%, tokens -50%.
3. **Loop detection v2 result-aware** (`loop_detection.py`). Two-tier escalation Reflexion + result-aware hashing (mejora sobre Reflexion vanilla).
4. **100% local + privado**. Sin cloud, sin API keys.
5. **Multilingual estructural**. Snowball stems, SequenceMatcher ratio cross-lingual (`calculator → Calculadora`).
6. **Streaming progress callbacks**. Cumple V17.
7. **Multi-backend adapter**. `pick_adapter` (Ollama/Llama.cpp/Xml).
8. **Honestidad estructural en outcomes**. `OUTCOME_COMPLETED/PARTIAL/FAILED/UNVERIFIED/NEEDS_USER/NEEDS_PERMISSION/BLOCKED_BY_POLICY/TOOL_OK_VERIFIER_INCONCLUSIVE/INTENT_NOT_FULFILLED` — 9 estados explícitos.

---

## 6. Debilidades (medidas en el código)

### 6.1 Drift de scope en agent.py (1,397 vs target 400)

`agent.py` tiene 23 métodos privados, mezclando:
- Construcción de mensajes
- Lógica de detect_archetype (duplica step_planner)
- Heurísticas de "_looks_like_surrender"
- Detection de tool-as-text con regex
- Detection de canned trivial reply
- Retry-with-nudge logic
- POST_DEEPLINK_AUTO_STEPS injection
- Loop detection wiring
- Verifier orchestration
- History compaction
- Streaming

**Anthropic dice**: "Keep loop minimal". Carter mete en agent.py muchísima lógica determinista que debería estar en módulos separados.

### 6.2 Duplicación crítica de namespace

**3 funciones `select_profile` distintas**:
- `turn_profile.py:89` — recibe (archetype, is_destructive_intent), devuelve TurnProfile
- `models/gemma4.py:160` — recibe (user_text, multi_step), devuelve GemmaTurnProfile
- `profiles.py:110` — recibe (profiles, vram_gb), devuelve hardware Profile

**3 funciones `detect_destructive_intent`/`_is_destructive`**:
- `turn_profile.py:159` — `detect_destructive_intent(user_text)`
- `models/gemma4.py:157` — re-exports `turn_profile.detect_destructive_intent`
- `step_planner.py:_is_destructive` — duplicado interno

**3 routers compitiendo** (detect_mission + plan_mission + plan_turn).

### 6.3 Violación documentada de V7 ("sin per-app hardcodes")

`step_planner.py` líneas 320-361 contienen:

```python
_WEB_APP_URLS = {"youtube": "https://...", "google": "...", "github": "...", ...}  # 18 apps
_DEEPLINK_APPS = {"spotify": (...), "steam": (...), "discord": (...), ...}        # 7 apps
_NATIVE_APPS = {"notepad", "calculadora", "explorador", ...}                       # 20 apps
```

Esto fue agregado como "forced_tool_call para imperativos clarísimos" (Pattern A). Funciona, pero **viola explícitamente el Valor 7 de ContextoCarter.md** ("Carter no debe tener hacks por app").

### 6.4 CORE_PROMPT tamaño (medido)

`prompts/gemma4_e4b_prompt.py`: 143 líneas, **13,580 chars ≈ 3,400 tokens**.

Para context 16k, eso es **21% del contexto quemado en reglas**. Anthropic Claude Code system prompt es <1,500 tokens. **2.3x más grande de lo necesario**.

Adicional: research confirmó "Large system prompts with 22+ tools result in accuracy degradation" — Carter expone 61 tools (con anchors + top-K=12-20 visibles por turn, pero el catalog crece según anaphora a k=20).

### 6.5 Cold start medido

Smoke previo: "hola" → 21.5s en primera llamada. Componentes:
- multilingual-e5-small load (~50MB modelo): 2-3s
- memory embedder: 1-2s
- _skill_registry scan dir cada turn
- 3 routers serializados antes de LLM

Target V2: trivial 3-5s. Drift **>4x sobre target**.

### 6.6 Verifier por-tool, no por-misión

`verify.py`: `register_verifier(tool_name)` mapea 1:1 tool→verifier. Cada outcome es por-tool.

`verifier_orchestrator.py`: agrega un outcome global basado en confirmed counts. Pero NO valida que la **intención original del usuario** quedó cumplida. Solo cuenta cuántos verifiers True/False.

Ejemplo concreto: si el user pide "abre Steam y busca Batman", y Carter abre Steam OK pero no buscar Batman, el verifier_orchestrator dice `PARTIAL` por counts. No hay un "mission_goal_check" que mire el texto del user y los resultados.

CLAUDE.md roadmap declara este gap: *"Verifier rewrite: pasar de 'tool ok = PASS' a 'intent fulfilled = PASS'"* — sigue pendiente.

### 6.7 Tests insuficientes (medidos)

```
tests/test_*.py: 16 archivos, 1,717 LOC
```

Coverage real estimado (por inspección):
- `test_memory.py`, `test_safety.py`, `test_verifier_orchestrator.py`, `test_loop_detection.py` — unit OK
- **Faltan**: integration tests `_execute_tool_calls`, `_chain_more_tools`, `plan_turn`, `tool_retrieval.select`, golden tests del flow completo

No hay test que ejecute `Agent.run_turn(...)` end-to-end con mock LLM. Imposible TDD sin eso.

### 6.8 Dependencia oculta de Gemma 4 quirks

`adapters/llamacpp.py`:
- Retry on `finish_reason="length"` con tool_calls truncados (Stage B.2)
- Filtrado de reasoning field cuando content=""
- Normalización tool_call `type:"function"` + id (llama-server exige)
- `chat_template_kwargs: {"enable_thinking": False}` en vision_tools por defecto

Esto está bien (parches verificables), pero **acopla** el agent a quirks específicos del backend. No hay abstracción "ModelCapability" que diga "este modelo emite thinking → filtra".

---

## 7. Deuda técnica acumulada (priorizada)

| ID | Deuda | Severidad | Estimación |
|----|-------|-----------|-----------|
| D1 | `agent.py` 1,397 LOC monolítico | **Alta** | Refactor 2-3 sesiones |
| D2 | 3 routers compitiendo (mission_detector + planner + plan_turn) | **Alta** | Colapsar a 1 |
| D3 | 3 `select_profile` con mismo nombre | Media | Renombrar + unificar |
| D4 | CORE_PROMPT 3,400 tokens vs <1,500 ideal | **Alta** | Recortar prompt |
| D5 | Per-app hardcodes en step_planner (`_WEB_APP_URLS`, `_DEEPLINK_APPS`, `_NATIVE_APPS`) | **Alta** | Mover a registry HKCR + UWP queries |
| D6 | Verifier por-tool, no por-misión | **Alta** | Crear `mission_goal.py` |
| D7 | 4 tests fallando por encoding | Baja | Arreglar strings |
| D8 | Cold start 21s vs 5s target | Media | Eager-load embedder |
| D9 | Falta integration tests del agent loop | **Alta** | Crear test_agent_integration |
| D10 | `_compute_post_action_steps` hardcodea POST_DEEPLINK_AUTO_STEPS en agent.py | Media | Mover a tool spec |
| D11 | `error_classifier.py` + `safety.py` + `verifier_orchestrator.py` overlap | Media | Unificar criterios |

---

## 8. Riesgos identificados

### R1: Performance bajo carga real
Cold start 21s viola V2 (alexa-tier). Si el usuario abre Carter y dice "hola", la primera respuesta es de >20s. Después está en target. Riesgo: usuario asume Carter está roto.

### R2: Honestidad falsa por verifier por-tool
Ejemplo: "abre Steam y busca Batman" → Steam abre OK (1 verifier True), busca Batman falla. `verifier_orchestrator` dice `PARTIAL`. El reply puede decir "listo, abrí Steam" omitiendo el fallo de búsqueda. Verifier por-misión es necesario para V3 (no mentir).

### R3: 4B tool-call bias
Documentado por Google: "4B models have a genuine tool-call bias regardless of prompt". Carter expone 61 tools (con top-K=12-20 visibles). Riesgo: Gemma llama tool cuando no debería (C13-03 vimos: llamó `system_time` en respuesta conversacional).

### R4: Drift entre prompt y código
Si el prompt dice "Steam tiene deeplink steam://" pero el código tiene fallback web_open_url, el modelo puede confundirse. Visto: prompt v3 menciona "deeplink steam://", pero `step_planner._DEEPLINK_APPS` tiene `("steam", "library", {})` que dispara forced_tool_call ANTES del LLM. **El LLM nunca decide para esos casos** — y el prompt no lo dice.

### R5: Skills + planner-light + step_planner stub overlapping
`skills.py` (Skill registry estilo Anthropic), `skill_store.py` (skill_record con LLM-critic), `planner.py` (plan stubs), `step_planner.py` (forced_tool_call). 4 mecanismos para "decir qué hacer". No hay jerarquía clara.

---

## 9. Cuello de botella principal (honesto)

**El modelo (Gemma 4 4B) es el cuello de botella estructural**. Evidencia:

1. OSWorld leaderboard: 4B no aparece. Frontier comienza en 35B (Holo3-35B 82.6%).
2. Google docs: "4B has genuine tool-call bias regardless of prompt".
3. Research: "agents take 1.4-2.7x more steps than necessary, each step 3x slower" — magnificado en 4B por razonamiento limitado.

**Pero**: 4B es el modelo correcto para hardware del usuario (16GB VRAM). Subir a 7B-14B reduce VRAM disponible para Windows + apps simultáneas.

Conclusión: **Carter debe maximizar lo que 4B puede hacer**, no aspirar a OSWorld-level. Eso significa:
- Tareas atómicas y cadenas cortas (2-4 tools) → factible.
- Misiones GUI multi-paso con dialogos → no factible sin RL post-training.
- Diseño que **mueva trabajo fuera del LLM** y deje solo "interpretar intención + descomponer + explicar".

---

## 10. Relación con Gemma 4 4B (medida)

### 10.1 Qué hace Gemma 4 4B bien (smoke verificado)

- Imperativos simples con tools obvias: `app_open`, `web_open_url`, `filesystem_*`, `terminal_run` simple.
- Cadenas 2-3 tools con dependencia clara: `create_dir → write → open` (C14-04 PASS).
- Follow-ups con referente claro: "ahora ciérralo" (C17-02 PASS).
- Multilingual + typos cuando hay vocabulario común: "stean", "habre", "q hora es".

### 10.2 Qué hace mal (smoke verificado)

- **Tool routing en conversacional**: C13-03 "si no ves Aceptar no clickees" → llamó `system_time` (claramente irrelevante). Evidencia del 4B tool-call bias.
- **Tool selection ambigua**: C14-26 abrió Python docs y usó `filesystem_read` sobre URL (path-vs-URL confusion).
- **Misiones largas (>4 pasos)**: C14-01 Steam Batman 6 tools, terminó pidiendo aclaración honesta tras vision_locate=False.
- **Razonamiento sobre estado dinámico**: cuando la app cambia post-deeplink, Gemma no actualiza su plan; sigue intentando lo que ya tenía.

### 10.3 Qué se le carga al modelo que no debería

Cargas innecesarias que código determinista podría resolver:
- Decidir "esto es trivial o no" → step_planner ya lo hace (bien).
- Decidir "esto es destructive" → safety.py ya lo hace (bien).
- Resolver "qué URL abre YouTube" → forced_tool_call (viola V7 pero funciona).
- Resolver "qué app desktop matchea 'calculator'" → resolve_app fuzzy (bien, con difflib 0.75).

Cargas que el modelo SÍ debe llevar:
- Interpretar intención ambigua ("se cerró todo, dale ese de gaming").
- Descomponer misiones ("crea backup, edita, corre test" → 3 tools).
- Explicar al usuario por qué no se pudo.

---

## 11. Conclusión Fase 1 (auditoría)

**Estado real de Carter v4** (basado en LOC, tests, smoke, código, docs SOTA):

- Diseño arquitectónico: **7.5/10** (correcto pero con drift de scope y duplicación de routers).
- Implementación: **6/10** (1397-LOC agent.py + 4 tests fallando + verifier por-tool insuficiente).
- Match con Gemma 4 4B: **5/10** (prompt 2.3x grande + 61 tools + cold start 21s + tool-call bias no mitigado explícitamente).

Estos scores son los que **defenderé contra evidencia** antes de empezar a tocar código.

**Plan**:
1. **Fase 2 — Diseño objetivo** (`01_auditoria_arquitectura.md` con propuesta).
2. **Fase 3 — Refactor seguro**:
   - Colapsar 3 routers → 1.
   - Mover per-app hardcodes a registry + UWP (data, no logica).
   - Cortar CORE_PROMPT a <1,500 tokens.
   - Crear `mission_goal.py` (verifier por-misión).
3. **Fase 4 — Optimización Gemma 4 4B** medida con bench oficial pre/post.
4. **Fase 5 — Bench 540 completo** (en curso, background).

---

## Fuentes consultadas para esta auditoría

- [Anthropic: Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
- [Google: Gemma 4 Function Calling](https://ai.google.dev/gemma/docs/capabilities/function-calling)
- [HuggingFace: Gemma 3 tool calling discussion (4B bias)](https://huggingface.co/google/gemma-3-27b-it/discussions/24)
- [arxiv 2505.03275: RAG-MCP](https://arxiv.org/abs/2505.03275)
- [Voyager NeurIPS 2023](https://voyager.minedojo.org/)
- [Reflexion NeurIPS 2023](https://arxiv.org/abs/2303.11366)
- [arxiv 2509.02544: UI-TARS-2](https://arxiv.org/abs/2509.02544)
- [pywinauto docs](https://pywinauto.readthedocs.io/)
- [llama.cpp function-calling docs](https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md)
- [Microsoft Learn: AllowSetForegroundWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-allowsetforegroundwindow)
- [OSWorld-Verified Leaderboard 2026](https://benchlm.ai/benchmarks/osWorldVerified)
- [Pydantic AI docs](https://ai.pydantic.dev/agent/)
- [ContextoCarter.md](../ContextoCarter.md) — los 30 valores del proyecto.
