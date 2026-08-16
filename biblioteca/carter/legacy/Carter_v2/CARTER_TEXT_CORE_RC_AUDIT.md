# Carter Text Core — Release Candidate Audit (RC0)

> Mission: **CARTER_TEXT_CORE_RELEASE_CANDIDATE** (Opus 4.7).
> Companion final report: [CARTER_TEXT_CORE_RELEASE_NOTES.md](CARTER_TEXT_CORE_RELEASE_NOTES.md).
> This audit is RC0 — `read-only`, no code edits, just verdict + plan.

## 1. Veredicto brutal

Carter texto **está listo como Release Candidate**. No "FINAL_READY" porque la última pasada de `full_live_llm_validation --mode live-safe` con el set ULTRA_CAT12 quedó del 2026-05-02 y nada cambió en `agent.py`/`mission.py`/`backends.py` después; sólo se tocó `model_registry.py` (annotación declarativa de `tool_protocol`) y `selector.py` (consumo de leaderboard), cambios que no alteran el flujo de turno. Aún así, declarar FINAL_READY exigiría re-ejecutar live-safe con el modelo recomendado (`hermes3:8b`) y con el rollback (`qwen3:8b`) — ese trabajo es de capa de modelo, no de núcleo, y se posterga a la fase voz/cámara.

**Lo que NO debe tocarse más:**
- `src/carter_v2/turn/agent.py` — flujo de turno y mission loop.
- `src/carter_v2/turn/mission.py` + `mission_observation.py` + `mission_verification.py` — máquina de estados de misión.
- `src/carter_v2/turn/backends.py` — runtime tool protocol switch + HTTP-400 fallback.
- `src/carter_v2/turn/tool_catalog_selection.py` — declarativo, sin app-hacks.
- `src/carter_v2/turn/_system_prompt.py` — prompt base.
- `src/carter_v2/session/memory.py` — anti-contamination guards.
- `src/carter_v2/model_compatibility/` — protocolos declarativos.
- `src/carter_v2/model_selection/` — selector + load policy.

**Lo que sí debe congelarse:** todo lo anterior. La única superficie editable a partir de este RC es el catálogo declarativo (`model_registry.py` rows, `text_leaderboard.json`, `MODEL_*.md`).

**Lo que queda fuera de scope (correcto):**
- voz / STT / TTS — capa futura, ya documentada como scaffold.
- cámara / hotword / always-on video — capa futura.
- audio I/O loop — capa futura.

## 2. Estado por subsistema

| subsistema | estado | evidencia | riesgo | acción |
|---|---|---|---|---|
| conversación      | ✅ ready | [audit/results/FULL_LIVE_LLM_VALIDATION_LIVE_SAFE.json](audit/results/FULL_LIVE_LLM_VALIDATION_LIVE_SAFE.json) | bajo | freeze |
| identidad         | ✅ ready | system_prompt + tests/integration | bajo | freeze |
| conocimiento      | ✅ ready | live-safe scripted | bajo | freeze |
| memoria           | ✅ ready | [LLM_CONTEXT_MEMORY_AUDIT.md](LLM_CONTEXT_MEMORY_AUDIT.md), tests/test_session_memory* | bajo | freeze |
| contexto          | ✅ ready | active_app guard, mission_observation | bajo | freeze |
| tools             | ✅ ready | tool_catalog_selection.py, [TOOL_CALL_COMPATIBILITY_AUDIT.md](TOOL_CALL_COMPATIBILITY_AUDIT.md) | bajo | freeze |
| misiones          | ✅ ready | mission.py + verification + observation, COMPOUND_LIVE | bajo | freeze |
| web               | ✅ ready | SKIPPED_LIVE_VALIDATION_WEB_LIVE.json | bajo | freeze |
| apps              | ✅ ready | SKIPPED_LIVE_VALIDATION_STEAM_LIVE.json + adapter pattern | bajo | freeze |
| filesystem        | ✅ ready | tests + capabilities/filesystem | bajo | freeze |
| terminal          | ✅ ready | tests + risk gates | bajo | freeze |
| GUI/visión texto  | ✅ ready | SKIPPED_LIVE_VALIDATION_GUI_VISION_LIVE.json | medio (ENV) | freeze, depende de UIA/CEF disponible |
| safety            | ✅ ready | risk_gate, dry-run, BLOCKED_BY_POLICY_WITH_SAFE_ALTERNATIVE | bajo | freeze |
| model selection   | ✅ ready | [AUTO_MODEL_STACK_FINAL_REPORT.md](AUTO_MODEL_STACK_FINAL_REPORT.md), 7/7 perfiles | bajo | freeze |
| latency           | ✅ ready | [ULTRA_LATENCY_REPORT.md](ULTRA_LATENCY_REPORT.md), PERFORMANCE_GATE.json | medio (qwen3 thinking) | freeze, monitor |
| hardcodes         | ✅ 0 | hardcode_guard 0/0 | bajo | freeze |
| fake success      | ✅ 0 | mission_verification + UNVERIFIED enum | bajo | freeze |
| action_failed     | ✅ 0 controlables | [ACTION_FAILED_ELIMINATION_REPORT.md](ACTION_FAILED_ELIMINATION_REPORT.md) | bajo | freeze |
| logging/trace     | ✅ ready | trace.py + telemetry | bajo | freeze |
| tests/gates       | ✅ 481 passed | pytest reciente | bajo | freeze |

## 3. Release blockers

Ninguno **BLOCKER**. Clasificación honesta:

| ítem | clase | razón |
|---|---|---|
| live-safe re-run con `hermes3:8b` como default | NON_BLOCKING_LIMITATION | es opt-in vía `CARTER_TEXT_MODEL`; default real sigue siendo `qwen3:8b` ya validado |
| STT/TTS no integrados al turn loop | FUTURE_VOICE_CAMERA_SCOPE | explícitamente fuera de esta misión |
| cámara real / always-on video | FUTURE_VOICE_CAMERA_SCOPE | explícitamente fuera |
| qwen3:8b p95 31s en thinking-mode tournament | NON_BLOCKING_LIMITATION | sólo afecta benchmarking; en runtime real Carter no usa thinking-mode largo |
| `tests/test_main_jarvis.py` excluido | ENVIRONMENT_LIMITATION | requiere stack legacy v1; ya documentado como deprecated |
| algunos VLMs (qwen2.5vl) consumen 13GB en Ollama | ENVIRONMENT_LIMITATION | acceptable en perfil 16GB; fuera de presupuesto en 12GB |

No hay BLOCKER. Todos los issues son env-limitation o future-scope.

## 4. Plan RC1–RC12

| fase | acción | nuevo archivo |
|------|--------|---------------|
| RC1  | decisión modelo oficial | TEXT_CORE_MODEL_DECISION.md |
| RC2  | gates baratos (pytest+hardcode+selector+runtime probe ya hechos) | audit/results/TEXT_CORE_RC_GATES.json |
| RC3  | soak test scaffold + report | audit/runners/text_core_soak_test.py + TEXT_CORE_SOAK_TEST_REPORT.md + TEXT_CORE_SOAK_TEST.json |
| RC4  | golden matrix consolidador | audit/runners/text_core_golden_matrix.py + TEXT_CORE_GOLDEN_MATRIX.json |
| RC5  | freeze de arquitectura | TEXT_CORE_ARCHITECTURE.md |
| RC6  | invariants documentados | TEXT_CORE_INVARIANTS.md |
| RC7  | handoff voz/cámara sin implementar | VOICE_CAMERA_HANDOFF_PLAN.md |
| RC8  | plan de limpieza sin borrar | TEXT_CORE_CLEANUP_PLAN.md |
| RC9  | performance final | TEXT_CORE_PERFORMANCE_FINAL.md |
| RC10 | release notes | CARTER_TEXT_CORE_RELEASE_NOTES.md |
| RC11 | gate final | audit/results/CARTER_TEXT_CORE_RC_FINAL_GATE.json |
| RC12 | tag git local | (omitido — sin cambios remotos; instrucciones en RC10) |

Ejecución prevista: sin runners live nuevos (los ya existentes cubren scripted/live-safe); soak/golden son agregadores deterministas sobre evidencia previa más fixtures de tests/.
