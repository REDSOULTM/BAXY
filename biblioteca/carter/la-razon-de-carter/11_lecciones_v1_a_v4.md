# 11 — Lecciones de Carter v1 → v4

**Fecha**: 2026-05-11
**Propósito**: extraer cada error, anti-patrón y validación medida de las 4 generaciones de Carter, para diseñar v5 sin repetirlos.
**Insumos**: git log (345 commits, 8 branches), `REPORTE_EXTENDIDO.md`, `REPORTE_540_GEMMA4.md`, `INFORME_NOCTURNO.md`, `MIGRATION_PLAN_GEMMA4.md`, `CLAUDE.md`, `ContextoCarter.md`, 9 informes de auditoría en `La razon de carter/`.

---

## 1. Resumen de las 4 generaciones

| Versión | Periodo | Modelo principal | Stack | Estado final |
|---|---|---|---|---|
| **v1** | 2025 | qwen3:14b → qwen2.5-coder:14b → devstral:24b → qwen3:4b | Ollama, agent loop monolítico, sin verifier estructural | Audit reveló 61% PASS REAL en 540 (vs ~85% bench bonito). Decisión: rebuild. |
| **v2** | 2025-Q4 | qwen3:8b + llama-cpp-python in-process | Rebuild from-scratch, tests 219→1454→1481→368, F0-F8 radical hardcode removal | "1454/1454 passing" pero arquitectura llena de capas. Smoke 18/18 OK pero respuestas malas en uso real. |
| **v3** | 2026-Q1 | qwen3:4b-instruct-2507-q4_K_M | Refactorización, mission_detector + planner + verifier_orchestrator + skill_store + gui_universal | Bench v22 con Stage A-E investigación llegó a 524/540 (97.04%). Stage E rewriter anti-mentira post-LLM. |
| **v4** | 2026-Q2 | gemma-4-E4B-it-Q6_K (llama-server CUDA b9090) | Migración Gemma 4, consolidated catalog 16 tools, hardware-aware selector, NEEDS_PERMISSION outcome, streaming SSE | Smoke 18 OK estructural, calidad real "pobre". Bench 540 abortado por decisión humana. Branch `feat/gemma4-integration` con 13 commits. |

**Tendencia clara**: cada versión agregó capas (mission_detector, planner, step_planner, verifier_orchestrator, skill_store, retrieval, streaming, post-LLM rewriter, causal focus, mission_goal, eager_load...) sin remover las anteriores. **El proyecto crece por acumulación, no por reemplazo.**

---

## 2. Lo que probaron y abandonaron (decisiones medidas)

### 2.1 Modelos descartados con razón medida

| Modelo probado | Razón abandono | Fuente |
|---|---|---|
| qwen3:14b | Lento + VRAM hambriento sin gain claro | git commit `08674335` |
| qwen2.5-coder:14b | Mejor JSON pero mismo techo accuracy | `bf2c08d5` |
| devstral:24b | "Anti-cheat" + format enforcement no resolvió | `a731eae3`, `08d8c863` |
| qwen2.5:32b | VRAM al límite, latencia inviable | `2cc5fc6f` |
| llava:7b | Vision OK pero llamada extra de modelo agrega 5-10s | `de351323` → `08322e29` (fallback sin VLM) |
| qwen3:8b llama-cpp-python in-process | TabbyAPI/ExLlamaV2 mejor → Stack 2 | `8b637549` |
| qwen3:1.7b draft model | Speculative decoding NO disponible en Ollama Windows | `9310d35a` desactivado |
| Gemma 4 31B (todas quants) | 1-13/60 PASS, CUDA crashes recurrentes | REPORTE_EXTENDIDO §1 |
| Gemma 4 26B-A4B IQ2_XXS | CUDA crash a mitad de bench | REPORTE_EXTENDIDO §1 |
| `--reasoning off` | -1.5pp regresión, parser b9090 ya filtra thinking | harness v13 |
| Strip `assistant.content` cuando hay tool_calls | -1.5pp regresión | harness v13 |
| `--cache-type-k q8_0` en Gemma 4 | KL divergence 0.377 (alto) | localbench benchmark |
| max_tokens=512 | 10% casos terminan en empty reply | harness v7 |
| Templates custom (`--chat-template gemma`) | Rompe multimodal tokenization | REPORTE_EXTENDIDO §3.2 |
| Router LLM externo (mini-LLM para routing) | -50-80ms × 2 sin ganancia accuracy >5% | Opus dossier 06 §2 |
| Dual-LLM (chat + tools separados) | Bug Ollama #14578 head-of-line blocking 50s | Opus dossier 06 §3 |
| Vision activo por default | Latencia +5-10s, V13 dice "on-demand" | git commit `08322e29` |

### 2.2 Decisiones validadas con datos

| Decisión | Validación |
|---|---|
| **Sampling oficial Google Gemma 4**: T=1.0, top_p=0.95, top_k=64, repeat_penalty=1.0 | Probando Gemma 4: 540/540 con estos valores. T<0.7 degrada. |
| **max_tokens=1280** (no 768) | harness v7: 768 causaba finish_reason=length 10% casos |
| **`--jinja` en llama-server** | Tool calling Gemma 4 nativo sin parsing custom |
| **mmproj-F16 cargado** (no Q8/Q4) | Q8/Q4 rompe vision/audio nativo |
| **KV cache F16** (no Q8) | Gemma 4 sensible: KL 0.377 con q8_0 |
| **Build llama.cpp b9090+** | PR #21418 specialized Gemma 4 parser obligatorio |
| **Honestidad por construcción** | Verifier estructural (frame-diff + Win32) > LLM-as-judge |
| **Universal cross-lingual** | Snowball stems + SequenceMatcher 0.75 vs listas per-idioma |
| **Deeplinks via HKCR registry** | `is_protocol_registered()` lee SO, no hardcode |
| **AllowSetForegroundWindow + ALT trick** | SetForegroundWindow bloqueado por defecto en proceso no-foreground |
| **Loop detection v2 result-aware** | Polling legítimo no confunde con loop (zeroclaw #2152) |
| **Causal focus** | UI-TARS-2 pattern: comparar pantalla actual vs target |
| **Consolidated 16 tools** | -68% tokens, misma calidad medida en harness |
| **CORE_PROMPT v3 con ejemplos** | 540/540 reproducible. Recortar a <1500 tokens regresiona -13pts. |

---

## 3. Errores recurrentes (anti-patrones a NUNCA repetir)

### 3.1 Acumulación sin remoción

Cada generación agregó componentes:
- v1: agent loop básico + Ollama
- v2: backends genéricos + UIA + brain harness + 1454 tests
- v3: mission_detector + planner-light + step_planner + verifier_orchestrator + skill_store + tool_retrieval + reply rewriters
- v4: composite_dispatcher + hardware_profile + streaming + verify_runtime + causal focus + mission_goal + eager load

**Síntoma**: `agent.py` v4 = 1397 LOC vs target propio "< 400 LOC". Drift +250%.

**Anti-patrón**: agregar capa para arreglar un caso del bench sin auditar si la capa anterior sigue justificada.

### 3.2 Routers compitiendo

v4 termina con **3 routers en serie antes de la primera LLM call**:
- `mission_detector.detect_mission()` → bool por scoring
- `planner.plan(llm.chat)` → Plan con LLM call EXTRA
- `step_planner.plan_turn()` → TurnPlan con archetype + forced_tool_call

Y **3 funciones `select_profile` distintas** con mismo nombre en módulos diferentes (`turn_profile.py`, `models/gemma4.py`, `profiles.py`).

**Anti-patrón**: cada router fue agregado para arreglar un caso, nadie eliminó el anterior. Solapamiento conceptual.

### 3.3 Per-app hardcodes (viola V7 ContextoCarter)

`step_planner.py` líneas 320-361:
```python
_WEB_APP_URLS = {"youtube": "...", "github": "...", ...}  # 18 entries
_DEEPLINK_APPS = {"spotify": (...), "steam": (...), ...}  # 7 entries
_NATIVE_APPS = {"notepad", "calculadora", ...}            # 20 entries
```

Carter declara explícitamente en ContextoCarter.md V7: *"Carter no debe tener hacks por app"*. Pero estas listas se agregaron como "forced_tool_call para imperativos clarísimos" (Pattern A).

**Anti-patrón**: violar valor de diseño porque "funciona para los casos del bench".

### 3.4 Heurísticas post-LLM stack (8 capas de rewriter)

agent.py:462-575 tiene esta cascada después de la primera LLM call:
1. `_looks_like_surrender` regex
2. `emitted_tool_as_text` regex sobre catalog
3. `canned_trivial` detector
4. Retry-with-nudge LLM call extra
5. `strip_planning_leakage`
6. `fix_carter_vocative`
7. `rewrite_claim_to_unverified`
8. `no_action_footer`

**Síntoma**: el INFORME_NOCTURNO dice literal *"las respuestas son malas en varios casos"*. El rewriter distorsiona lo que el modelo quería decir.

**Anti-patrón**: parchar al modelo con código en lugar de prompt mejor o modelo mejor.

### 3.5 History dinámica que invalida prompt cache

Cada turn Carter construye `system_msg` con history + memory_facts + archetype-specific blocks. Eso **cambia el prompt entre turns** → llama-server invalida el KV cache → re-prefill 1-3s.

**Síntoma medido**: latencia 1-tool avg 16s en bench (vs harness puro 4.26s p50). Carter agrega ~10s overhead per turn.

**Anti-patrón**: tratar el prompt como "ensamblado dinámicamente" cuando llama-server premia prompts estables.

### 3.6 Retrieval per-turn (cambia el set de tools)

`tool_retriever.select(query, k=12)` se ejecuta cada turn y devuelve tools distintas según el embedding del prompt. Eso significa:
- El catalog `tools=[...]` que va al LLM cambia entre turns
- Cache de tools en llama-server se rompe
- Modelo ve "tools nuevas" cada turn

**Anti-patrón**: optimización (RAG-MCP) aplicada sin considerar interacción con cache.

### 3.7 Verifier por-tool, no por-misión

`verify.py` registra verifier 1:1 con tool name. `verifier_orchestrator` agrega outcome global por **counts**. NO valida si la **intención del prompt** se cumplió.

CLAUDE.md roadmap declara explícitamente: *"Verifier rewrite: pasar de 'tool ok = PASS' a 'intent fulfilled = PASS'"* — **sigue pendiente desde v3**.

### 3.8 Tests que pasan pero no validan calidad

INFORME_NOCTURNO dice:
> "El bench oficial `full_matrix_runner.py` mide **estructura** (tool correcta emitida + reply >40 chars), NO calidad de respuesta. Eso significa que varios casos del sanity 18 son 'PASS estructural / FAIL semántico'."

Ejemplos verificados:
- C09-01 "abre Steam" → "Hola! Soy Carter, ¿en qué te ayudo? Abrí Steam." (saludo + acción concat)
- C13-01 "ventana activa" → "monitoreo de GPU" (alucinación)
- C16-01 "abre stean" → "(corte: depth>3)" (loop sin resolver)

**Anti-patrón**: optimizar bench score sin medir calidad subjetiva.

### 3.9 Cambiar múltiples cosas a la vez sin medir

**Mi error reciente del 2026-05-11**: post_refactor cambió simultáneamente prompt -74%, anchors 25→8, top-K 12→8, MissionGoal, eager-load. **Resultado: -13 pts PASS rate (75.93% → 62.96%)**.

**Anti-patrón**: violar "un cambio por vez" del propio plan.

### 3.10 Modelo desalineado con uso

v1-v3 usaron qwen3:4b. Reporte Opus 06 §1 mide:
- qwen3:4b BFCL-v3: ~62%
- granite4.1:8b BFCL-v3: 68.27% (+6 pts)
- granite4.1:30b BFCL-v3 en 24GB: 73.68% (+11.7 pts)

Carter v4 migró a Gemma 4 E4B-Q6_K (mejor que qwen3:4b: +3 pts en bench Fase 2, +2 patrón A perfecto).

**Lección**: el modelo importa más que las heurísticas. Una migración bien hecha gana más que 1000 LOC de rewriter.

---

## 4. Validaciones que funcionaron en cada generación

### v1 (qwen3:14b → ... → qwen3:4b)
- ✅ Detección de errores tempranos via REBUILD_DECISIONS.md (`f027fbc3`)
- ✅ Audit honesto que reveló 61% PASS REAL (vs bench bonito que decía 85%)
- ❌ Mezcla de modelos sin criterio claro

### v2 (rebuild from-scratch)
- ✅ "Honestidad por construcción" como principio
- ✅ Verifier estructural sin LLM-as-judge
- ✅ Backend-agnostic runtime (`8ffb8a00`)
- ❌ 1454 tests pero respuestas malas en uso real
- ❌ "Radical hardcode removal" descubrió 1000+ hardcodes (síntoma de v1)

### v3 (refactorización masiva)
- ✅ Stage A-E investigación llegó a 524/540 (97.04%)
- ✅ POST_DEEPLINK auto-steps cierra Pattern O
- ✅ vision_locate_target como gate estructural pre-click
- ✅ Skills locales formato SKILL.md (Doc 07 Opus)
- ❌ Acumulación de heurísticas post-LLM
- ❌ 14 iteraciones del bench (v1 → v22) con auditor cambiando

### v4 (Gemma 4 migration)
- ✅ Adapter llama-server limpio con `--jinja`
- ✅ Composite catalog 16 tools (-68% tokens)
- ✅ Hardware-aware selector con VRAM detection
- ✅ NEEDS_PERMISSION + BLOCKED_BY_POLICY outcomes
- ✅ Streaming SSE wire en CLI + Agent
- ✅ Causal focus universal con AllowSetForegroundWindow
- ✅ Deeplink-first via HKCR registry
- ❌ Branch `feat/gemma4-integration` con calidad real "pobre" según INFORME_NOCTURNO
- ❌ Bench 540 abortado por decisión humana

---

## 5. Las 14 decisiones de arquitectura ya validadas (Probando Gemma 4)

Del repo `Probando Gemma 4/documentacion/09_arquitectura_decisiones/`:

1. **Modelo ganador**: E4B-Q6_K (95% bench Fase 2, 540/540 reproducible)
2. **Backend**: CUDA, no Vulkan (30-40% más rápido NVIDIA)
3. **Runtime**: llama.cpp, no vLLM (no requiere WSL2+Docker)
4. **Sampling**: oficial Google sin alterar
5. **Tools**: consolidated 16 composite (mismo PASS, -68% tokens, escalable a 200+)
6. **NO multi-modelo pipeline**: latencia 2-3× sin beneficio (CARGO paper 76% router accuracy)
7. **NO partir system_prompt en tiers**: monolítico 3500 tokens = 540/540
8. **NO `--reasoning off`**: -1.5pp regresión, b9090 parser ya filtra
9. **NO strip assistant.content**: -1.5pp regresión, b9090 parser ya hace
10. **Audio nativo NO reemplaza Whisper**: 2/5 en español rioplatense (vs Whisper ~95%)
11. **KV cache F16** (Gemma 4 sensible a quant)
12. **mmproj F16 SIEMPRE** (no comprimir)
13. **Verifiers reales en Carter, NO en bench**: stubs determinísticos en bench, real en Carter
14. **Streaming SSE en Carter** (primer token <500ms, no esperar p99)

**Estas 14 decisiones son base no-negociable de v5.**

---

## 6. Las 10 lecciones más importantes para v5

### L1: Empezar con el modelo
v1-v3 perdieron meses optimizando qwen3:4b cuando Gemma 4 E4B-Q6_K ganaba +3 puntos sin tocar código. **v5: target modelo PRIMERO, código DESPUÉS**.

### L2: Cada cambio tiene que ser medible
v4 post_refactor cambió 4 cosas a la vez → -13 pts. **v5: una variable por iteración, bench entre cada una**.

### L3: Prompt estable preserva cache
History dinámica + retrieval dinámico invalidan KV cache → 10s overhead per turn. **v5: prompt estable, catalog estable por sesión**.

### L4: Per-app hardcodes son anti-patrón
`_WEB_APP_URLS`, `_DEEPLINK_APPS`, `_NATIVE_APPS` violan V7. **v5: TODO por intención + registry + resolve_app universal**.

### L5: Post-LLM rewriters distorsionan
8 capas de rewriter explican "respuestas pobres". **v5: confiar en el modelo, rewriter SOLO para honestidad cuando NO hay tool ejecutado**.

### L6: Verifier por-misión, no por-tool
Voyager pattern: verificar el OBJETIVO del prompt. **v5: MissionGoal estructural + per-tool verifiers como SEÑAL secundaria**.

### L7: Routers compitiendo es debt
3 routers en serie + 3 select_profile = solapamiento conceptual. **v5: UN router pre-LLM con responsabilidades claras**.

### L8: Bench mide estructura, calidad real importa más
"PASS estructural / FAIL semántico" en INFORME_NOCTURNO. **v5: bench como sanity check, calidad real como criterio dominante**.

### L9: Agent.py debe ser legible solo
1397 LOC = "God object". **v5: agent.py < 500 LOC, módulos < 300 LOC, responsabilidades aisladas**.

### L10: Mover trabajo determinista FUERA del LLM
4B Gemma tiene tool-call bias documentado. Carter v4 le carga decisiones que código resolvería mejor. **v5: LLM solo decide intención ambigua + descomposición + explicación. Resto = código determinista**.

---

## 7. Branches en git (estado actual)

```
  Refactorizacion                              ← v3 refactor
  checkpoint-before-gemini-full-stabilization  ← v3 pre-stabilization
  checkpoint-before-jarvis-consolidation       ← v2 pre-jarvis
* feat/gemma4-integration                      ← v4 actual (HEAD)
  master                                       ← v1 baseline
  radical/text-closure                         ← v2 radical cleanup
  rebuild/v2-from-scratch                      ← v2 from-scratch attempt
  repo-cleanup-test-rebuild                    ← v2 test rebuild
```

**Para v5**: nueva branch `feat/carter-v5-multi-profile` desde `master` o desde el ContextoCarter.md de raíz. NO desde v4 (heredaría debt).

---

## 8. Síntesis: qué llevamos a v5

### Llevamos (probado, validado, no negociable):
1. Filosofía "Honestidad por construcción" (V3 ContextoCarter)
2. 30 valores de ContextoCarter.md como brújula
3. Modelo Gemma 4 (E2B/E4B/26B-A4B por tier)
4. Sampling oficial Google (T=1.0, top_p=0.95, top_k=64)
5. llama-server `--jinja` con build CUDA b9090+
6. mmproj-F16 cargado siempre
7. KV cache F16
8. CORE_PROMPT v3 (143 líneas, validado 540/540)
9. Consolidated 16 composite tools
10. Verifier estructural (frame-diff + Win32 + pycaw)
11. Causal focus (UI-TARS-2 pattern)
12. Deeplinks via HKCR registry
13. AllowSetForegroundWindow + ALT trick
14. Loop detection v2 result-aware
15. Cross-lingual SequenceMatcher 0.75
16. Streaming SSE
17. 60 tools registradas con verifiers (las MISMAS, no re-implementar)
18. Memory SQLite + embedder multilingual-e5-small

### NO llevamos (anti-patrones medidos):
1. ❌ 3 routers compitiendo (mission_detector + planner + step_planner)
2. ❌ Per-app hardcodes en step_planner
3. ❌ 8 capas de post-LLM rewriter
4. ❌ History dinámica que invalida cache
5. ❌ Retrieval per-turn que cambia catalog
6. ❌ Verifier solo por-tool (sin mission_goal)
7. ❌ agent.py monolítico
8. ❌ 3 `select_profile` con mismo nombre
9. ❌ `--reasoning off`
10. ❌ Strip assistant.content
11. ❌ Audio nativo (Whisper gana)
12. ❌ Vision activa por default (on-demand V13)
13. ❌ Cambiar múltiples variables sin medir

---

## 9. Próximos pasos

1. **Leer Doc 12** (`12_carter_v5_arquitectura.md`) — arquitectura general v5
2. **Leer Doc 13** (`13_carter_v5_perfiles_vram.md`) — 5 tiers con configuración medida
3. **Aprobar diseño** antes de tocar código
4. **Mover Carter v4 a `Carter_v4_legacy/`** (tag git para preservar historia)
5. **Crear repo `carter_v5/`** con scaffolding modular por tier
6. **Implementación tier por tier** (probablemente 16GB primero porque tenemos ground truth 540/540)

**No tocamos código hasta tener Doc 12 y 13 aprobados.**
