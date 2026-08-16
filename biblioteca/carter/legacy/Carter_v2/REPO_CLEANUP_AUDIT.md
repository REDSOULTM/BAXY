# Repo Cleanup Audit — Carter v2

Generated: 2026-05-01
Branch: `repo-cleanup-test-rebuild` (from `radical/text-closure` @ `9cab1368`)
Snapshot: `audit/baselines/pre_cleanup_snapshot.json`
Backup: `backups/tests_legacy_20260501-020549/` (377 files)

---

## 1. Veredicto brutal

**Qué sobra en el repo activo:**
- ~78 archivos `probe_*` (py/json/txt) y ~38 SQLite (`.probe*`, `.smoke*`, `.tmp*`, `.diag*`) vivos en la raíz como detritus de iteraciones pasadas. Cero valor para Carter actual.
- 22 markdowns históricos en raíz (FINAL_*, POST_CODEX_*, RADICAL_*, TEXT_AGENT_*, UNIVERSAL_FIX_*, COMPOUND_TASKS_*, GEMINIWORK*, HARDCODE_*, PHASE_INTEGRATION_*) — todos son reportes de fases ya cerradas.
- En `audit/`: `smoke_runner.py`, `smoke_runner_fsmoke.py`, `_c3_strip.py`, `F0_invariants.py.bak`, `F0_*`, `F-*`, `C0_*`, `C-*` baselines, `f8_test_summary.txt`, `pytest_output.txt` — historia.
- Directorios vacíos sin propósito: `audit/baselines/`, `audit/gates/`, `audit/runners/`, `audit/logs/`, `audit/results/`, `audit/temp/` (recién creados por nosotros), y `src/carter_v2/skills/{docker,git-workflow,github,notion,npm-scripts,spotify,weather,winget-update,youtube-dl}/` (sub-paquetes vacíos sin código).
- `Carter_v2.rar` en raíz — tarball antiguo.
- `MEMORY.md.bak.20260430-190222` — backup huérfano.
- `__pycache__/`, `.pytest_cache/`, `test_probe.db`, `test_skills.db` — auto-regenerables.

**Qué está desordenado:**
- Audit runners (`hardcode_guard.py`, `compound_smoke_runner.py`) están sueltos en `audit/` mientras debería existir la subcarpeta `audit/runners/`.
- Reportes/auditorías de fases conviven con código activo en raíz.
- Scripts (`setup_ollama_optimized.ps1`, `run_text_closure_gate.py`) huérfanos en raíz.
- `docs/` y `documentacion/` coexisten — duplicación conceptual.

**Qué debe moverse:**
- 22 .md históricos → `documentacion/auditorias|reportes_finales|planes|archive/`.
- Setup scripts → `scripts/setup/`.
- Runners audit → `audit/runners/`.
- Baselines/JSON → `audit/results/` y `audit/baselines/`.
- Logs/.bak → `audit/logs/`.
- Probes detritus → `backups/probe_archive_<ts>/`.

**Qué debe borrarse (después de archivar):**
- `__pycache__`, `.pytest_cache`, `test_probe.db`, `test_skills.db`.
- Sub-paquetes vacíos `src/carter_v2/skills/<vendor>/` (validar que ninguno tenga `__init__.py` que se importe).

**Qué código parece muerto:**
- `audit/smoke_runner.py`, `smoke_runner_fsmoke.py`, `_c3_strip.py` — superseded por `compound_smoke_runner.py`.
- 2 tools en `adapters/tools.py` (líneas 614, 625) marcadas `deprecated=True` — vía controlada, eliminables si nadie los referencia.
- `_old_unraisablehook` en `main.py` — variable interna, validar.

**Qué documentación es source-of-truth:**
- `README.md` (raíz), `documentacion/MODULE_CLASSIFICATION.md`, `documentacion/Plan de trabajo.md`, `documentacion/README.md`, `docs/Tareas por hacer.md`, `docs/vision_setup.md`. **MEMORY.md** es estado runtime — NO doc, debería estar en `memory/` o documentado.

**Qué documentación es histórica:**
- Todos los `*_AUDIT.md`, `*_REPORT.md`, `*_NOTES.md`, `*_DELIVERY.md`, `*_PLAN.md` en raíz.

**Qué scripts son vigentes:**
- `run.py`, `run_carter_gpu.ps1`, `audit/hardcode_guard.py`, `audit/compound_smoke_runner.py`.

**Qué scripts son temporales:**
- `setup_ollama_optimized.ps1` (one-shot setup), `run_text_closure_gate.py` (gate de fase cerrada), `_inspect_mem.py` (debug ad-hoc).

---

## 2. Inventario raíz `Carter_v2/`

| Item | Acción |
|---|---|
| `README.md` | KEEP_ROOT |
| `pyproject.toml` | KEEP_ROOT |
| `run.py` | KEEP_ROOT |
| `run_carter_gpu.ps1` (raíz padre) | KEEP_ROOT |
| `.env.example` | KEEP_ROOT |
| `.gitignore` | KEEP_ROOT |
| `src/`, `tests/`, `audit/`, `scripts/`, `documentacion/`, `backups/`, `memory/`, `artifacts/` | KEEP_ROOT |
| `docs/` | MERGE → `documentacion/` (Tareas por hacer, vision_setup) |
| `MEMORY.md` | REVIEW (runtime state, mover a `memory/MEMORY.md` si lo lee el runtime; sino archivar) |
| `MEMORY.md.bak.20260430-190222` | MOVE_BACKUP → `backups/` |
| `Carter_v2.rar` | MOVE_BACKUP → `backups/` |
| `DREAMS.md` | ARCHIVE → `documentacion/archive/` |
| `GEMINIWORK.MD`, `GEMINI_WORK_REVIEW.md` | ARCHIVE → `documentacion/archive/` |
| `COMPOUND_TASKS_VISION_AUDIT.md` | MOVE_DOCS → `documentacion/auditorias/` |
| `COMPOUND_TASKS_VISION_REPORT.md` | MOVE_DOCS → `documentacion/reportes_finales/` |
| `FINAL_TEXT_AGENT_STABILIZATION_NOTES.md` | MOVE_DOCS → `documentacion/auditorias/` |
| `FINAL_TEXT_AGENT_STABILIZATION_REPORT.md` | MOVE_DOCS → `documentacion/reportes_finales/` |
| `FINAL_TEXT_CLOSURE_AUDIT.md` | MOVE_DOCS → `documentacion/auditorias/` |
| `FINAL_TEXT_CLOSURE_REPORT.md` | MOVE_DOCS → `documentacion/reportes_finales/` |
| `HARDCODE_AUDIT.md` | MOVE_DOCS → `documentacion/auditorias/` |
| `HARDCODE_ELIMINATION_REPORT.md` | MOVE_DOCS → `documentacion/reportes_finales/` |
| `PHASE_INTEGRATION_DELIVERY.md` | MOVE_DOCS → `documentacion/reportes_finales/` |
| `POST_CODEX_MASTER_AUDIT_NOTES.md` | MOVE_DOCS → `documentacion/auditorias/` |
| `POST_CODEX_MASTER_AUDIT_REPORT.md` | MOVE_DOCS → `documentacion/reportes_finales/` |
| `POST_CODEX_UNIVERSAL_AUDIT_NOTES.md` | MOVE_DOCS → `documentacion/auditorias/` |
| `POST_CODEX_UNIVERSAL_AUDIT_REPORT.md` | MOVE_DOCS → `documentacion/reportes_finales/` |
| `RADICAL_TEXT_CLOSURE_PLAN.md` | MOVE_DOCS → `documentacion/planes/` |
| `RADICAL_TEXT_CLOSURE_REPORT.md` | MOVE_DOCS → `documentacion/reportes_finales/` |
| `TEXT_AGENT_CLOSURE.md` | MOVE_DOCS → `documentacion/planes/` |
| `TEXT_AGENT_CLOSURE_AUDIT.md` | MOVE_DOCS → `documentacion/auditorias/` |
| `UNIVERSAL_FIX_NOTES.md` | MOVE_DOCS → `documentacion/auditorias/` |
| `UNIVERSAL_FIX_REPORT.md` | MOVE_DOCS → `documentacion/reportes_finales/` |
| `setup_ollama_optimized.ps1` | MOVE_SCRIPT → `scripts/setup/` |
| `run_text_closure_gate.py` | ARCHIVE → `audit/temp/` (gate de fase cerrada) |
| `_inspect_mem.py` | ARCHIVE → `scripts/dev/_inspect_mem.py` o DELETE |
| `probe_*.{py,json,txt}` (78 archivos) | ARCHIVE → `backups/probe_archive_20260501-020549/` |
| `.probe*`, `.smoke*`, `.tmp*`, `.diag*` (38 DBs) | ARCHIVE → `backups/probe_archive_20260501-020549/` |
| `.iso_results/`, `probe_assets/`, `probe_assets_runtime/` | ARCHIVE → `backups/probe_archive_...` |
| `probe_a`, `probe_assets_r`, `probe_assets_run` | DELETE (fragmentos truncados) |
| `live_smoke_results.{json,md}` | MOVE_AUDIT → `audit/results/` |
| `test_probe.db`, `test_skills.db` | DELETE (auto-regen) |
| `__pycache__/`, `.pytest_cache/` | DELETE (auto-regen) |

---

## 3. Inventario `src/carter_v2/`

| Módulo / Archivo | Clasificación | Notas |
|---|---|---|
| `__init__.py`, `__main__.py`, `main.py` | CORE | Bootstrap |
| `config.py` | CORE | Carga de config |
| `event_bus.py` | CORE | Observer de tool calls |
| `types.py` | CORE | Types compartidos |
| `adapters/tools.py` | CORE | Catálogo unificado de tools (2 tools `deprecated=True` — REVIEW eliminación) |
| `adapters/tool_normalizer.py` | CORE | Normalización schema/args |
| `adapters/uia.py` | KEEP_LAZY | UI Automation Windows; lazy |
| `capabilities/*` | CORE | Capacidades determinísticas (filesystem, process, vision, gui_agent, app_resolver, …) |
| `capabilities/probe.py` | KEEP_LAZY | Soporte debug; verificar uso |
| `interfaces/{slack,discord,telegram,http,extension_relay}` | OFF_BY_DEFAULT | Canales externos opcionales |
| `plugins/loader.py` | KEEP_LAZY | Plugin discovery local |
| `recovery/{classifier,policies,types}` | CORE | Estrategia retry/fallback |
| `session/{state,memory,policy,skills,observer,…}` | CORE | Estado/memoria de sesión |
| `skills/<vendor>/` (docker, git-workflow, github, notion, npm-scripts, spotify, weather, winget-update, youtube-dl) | DEAD_CODE | **Sub-paquetes vacíos** — eliminar si confirmamos cero referencias |
| `tasks/background.py` | KEEP_LAZY | Tareas background opcionales |
| `turn/agent.py` | CORE | Loop principal del turno |
| `turn/{mission,mission_observation,mission_verification}.py` | CORE | Mission state machine |
| `turn/{ledger,invariants,perception,_system_prompt,llama_backend,backends,_text,_tracing}.py` | CORE | Pipeline turno |
| `turn/intent_*.py`, `turn/tool_catalog_selection.py` | CORE | Routing |
| `universal/*` | CORE | LLM-driven planner (universal kernel) |
| `verification/{contracts,facts}.py` | CORE | Verificación post-acción |

**Dead-code candidatos (validar grep):**
- `src/carter_v2/skills/<vendor>/` directorios vacíos.
- `adapters/tools.py` 2 deprecated tools.
- Posibles módulos no usados por el nuevo test set (se decide en FASE 5 después de reconstruir tests).

---

## 4. Inventario tests actuales (98 archivos, 1667 tests)

Suite completa respaldada en `backups/tests_legacy_20260501-020549/`. La clasificación sirve para extraer contratos a la nueva suite.

### CORE_CONTRACT
- `test_e2e_agent_turn.py`, `test_carter_v2.py`, `test_assistant_engine.py`, `test_capability_registry.py`, `test_carter_capabilities.py`, `test_universal_agent_kernel.py`, `test_universal_resolver.py`, `test_text_agent_regressions.py`, `test_agent_turn_trace.py`, `test_high_priority.py`, `test_medium_priority.py`, `test_pending_visible.py`, `test_a11_multilang_identity.py`, `test_identity_autoload.py`, `test_brain_router_fase7.py`, `test_dialog_helpers.py`, `test_config.py`, `test_llama_backend.py`

### SAFETY_CONTRACT
- `test_policy_fase3.py`, `test_terminal_allowlist.py`, `test_graceful_close.py`, `test_registry_errors.py`, `test_tool_timeout.py`, `test_subprocess_kill.py`, `test_honesty_guardrail.py`, `test_env_persist.py`, `test_jarvis_root_hardening.py`

### MISSION_CONTRACT
- `test_mission_state.py`, `test_mission_observation.py`, `test_mission_language_neutral.py`, `test_intent_decomposition.py`, `test_router_language_neutral.py`, `test_agent_intent_continuity.py`, `test_direct_action_closure.py`, `test_ambiguity_resolution.py`

### MEMORY_CONTRACT
- `test_memory_contextual.py`, `test_memory_fts5_sanitize.py`, `test_memory_injection.py`, `test_memory_universal_consolidation.py`, `test_session.py`, `test_phase5_memory_hardening.py`, `test_agent_misrouting_and_memory_hardening.py`

### TOOL_CONTRACT
- `test_tool_catalog_selection.py`, `test_tool_normalizer.py`, `test_tool_routing_contracts.py`, `test_tool_prioritization.py`, `test_tool_timeout.py`, `test_app_resolver.py`, `test_resource_resolver.py`, `test_input_aliases.py`, `test_context_budget_guard.py`, `test_action_ledger.py`, `test_ledger_language_neutral.py`, `test_computer_use.py`

### GUI_VISION_CONTRACT
- `test_gui_types.py`, `test_gui_do_planner.py`, `test_gui_cross_app_pipeline.py`, `test_perception_fase4.py`, `test_perception_feedback.py`, `test_perception_upgrades_pending.py`, `test_vision_router_lazy.py`, `test_window_capability.py`, `test_window_office_session9.py`, `test_ui_capability.py`, `test_system_display_keyboard.py`

### HARD_CODE_GUARD
- `test_no_runtime_hardcodes.py`, `test_no_app_hacks_in_agent.py`, `test_a11_multilang_identity.py`

### CAPABILITY_TESTS (no son contratos del agente; testean capacidades atómicas)
- `test_filesystem_capability.py`, `test_filesystem_extended.py`, `test_code_database_capabilities.py`, `test_email_calendar_capabilities.py`, `test_pdf_capability.py`, `test_process_capability.py`, `test_power_capability.py`, `test_scheduler_capability.py`, `test_system_capability.py`, `test_system_extended.py`, `test_media_files_capability.py`, `test_media_audio_devices.py`, `test_web_cookies.py`, `test_web_browser_search.py`, `test_new_capabilities.py`, `test_new_capabilities_session6.py`, `test_session9_extended_capabilities.py`

### LEGACY_BUG_TEST (fases cerradas — borrar; rescatar contratos vivos)
- `test_fase15_skills.py`, `test_fase16_watchers.py`, `test_fase17_vision.py`, `test_fase18_lessons.py`, `test_perception_fase4.py`, `test_policy_fase3.py`, `test_recovery_fase6.py`, `test_verification_fase5.py`, `test_brain_router_fase7.py`, `test_phase5_memory_hardening.py`, `test_window_office_session9.py`, `test_session9_extended_capabilities.py`, `test_new_capabilities_session6.py`

### REDUNDANT
- `test_session9_extended_capabilities.py` ↔ `test_new_capabilities_session6.py` ↔ `test_new_capabilities.py` (capability registration repetido)
- `test_carter_capabilities.py` ↔ `test_capability_registry.py`

### FRAGILE
- `test_skills_universal_filter.py` (depende de archivos en disco)
- `test_proactive_injection.py` (timing-sensitive)
- `test_main_jarvis.py` (excluido de baseline; nombre legacy v1)
- `test_openclaw_parity_features.py` (paridad histórica con repo externo)

### DELETE (al reconstruir, no rescatar)
- `test_main_jarvis.py`, `test_jarvis_root_hardening.py` (nombres v1; contratos cubiertos por nueva safety suite si aplica)
- `test_fase15_skills.py`, `test_fase16_watchers.py`, `test_fase17_vision.py`, `test_fase18_lessons.py` (fases cerradas)
- `test_openclaw_parity_features.py` (paridad histórica)

### REFERENCE_ONLY (queda en backup; útil al diseñar nuevos)
- Tests de capacidades atómicas (`*_capability.py`, `*_capabilities*.py`) — los nuevos tests integrarán por contrato, no por capacidad individual.
- Tests `fase*` — los contratos vivos se reconstruyen sin tag de fase.

---

## 5. Inventario `audit/`

| Item | Clasificación | Destino |
|---|---|---|
| `hardcode_guard.py` | VIGENT_RUNNER | `audit/runners/hardcode_guard.py` |
| `compound_smoke_runner.py` | VIGENT_RUNNER | `audit/runners/compound_smoke_runner.py` |
| `smoke_runner.py` | OBSOLETE_RUNNER | `audit/temp/` o DELETE |
| `smoke_runner_fsmoke.py` | OBSOLETE_RUNNER | `audit/temp/` o DELETE |
| `_c3_strip.py` | OBSOLETE_RUNNER | `audit/temp/` o DELETE |
| `HARDCODE_GUARD.json` | CURRENT_JSON | `audit/results/HARDCODE_GUARD.json` |
| `COMPOUND_SMOKE.json` | CURRENT_JSON | `audit/results/COMPOUND_SMOKE.json` |
| `C0_baseline.json`, `C0_pytest.txt`, `C-SMOKE_smoke.json`, `C-final_metrics.json`, `C1_pytest.txt` | HISTORICAL_JSON | `audit/baselines/historical/` |
| `F0_baseline_tests.json`, `F0_smoke.json`, `F0_smoke.log`, `F0_MEMORY.snapshot`, `F0_prompt_template.txt`, `F-SMOKE_smoke.json`, `F-SMOKE_smoke.log` | HISTORICAL_JSON | `audit/baselines/historical/` |
| `F0_invariants.py.bak` | BAK | `backups/` |
| `pytest_output.txt`, `f8_test_summary.txt` | LOG | `audit/logs/historical/` |
| `__pycache__/` | DELETE | — |

---

## 6. Inventario documentación

| Item | Clasificación | Destino |
|---|---|---|
| `README.md` (raíz) | SOURCE_OF_TRUTH | KEEP (actualizar en FASE 6) |
| `documentacion/README.md` | SOURCE_OF_TRUTH | KEEP |
| `documentacion/MODULE_CLASSIFICATION.md` | SOURCE_OF_TRUTH | → `documentacion/arquitectura/` |
| `documentacion/Plan de trabajo.md` | PLAN | → `documentacion/planes/` |
| `documentacion/{archive,auditorias,decisiones,investigaciones,planes,probes,reportes_finales,sessions}/` | KEEP | (subcarpetas existentes ya OK) |
| `docs/Tareas por hacer.md` | PLAN | → `documentacion/planes/` |
| `docs/vision_setup.md` | DOC | → `documentacion/arquitectura/vision_setup.md` |
| Markdowns históricos en raíz (22) | HISTORICAL/AUDIT/REPORT/PLAN | Tabla §2 |
| `MEMORY.md` | RUNTIME_STATE | REVIEW: si runtime lee, mantener en `memory/`; sino archivar |

---

## 7. Plan de limpieza (resumen)

| Item | Acción | Destino | Evidencia | Riesgo | Rollback |
|---|---|---|---|---|---|
| `tests/` | WIPE | — | Backup existe | Pérdida de cobertura hasta FASE 4 | Restore desde `backups/tests_legacy_20260501-020549/` |
| 78 `probe_*` raíz | ARCHIVE | `backups/probe_archive_20260501-020549/` | Ningún script vivo los referencia | Bajo | Mover de vuelta |
| 38 `.probe*/.smoke*/.tmp*/.diag*` SQLite | ARCHIVE | `backups/probe_archive_20260501-020549/` | DBs efímeras | Bajo | Restore |
| 22 `.md` históricos raíz | MOVE | `documentacion/{auditorias,reportes_finales,planes,archive}/` | Ningún import los lee | Cero | git mv |
| `setup_ollama_optimized.ps1` | MOVE | `scripts/setup/` | Sólo se invoca manualmente | Bajo | git mv |
| `run_text_closure_gate.py` | ARCHIVE | `audit/temp/` | Gate de fase cerrada | Bajo | git mv |
| `_inspect_mem.py` | MOVE | `scripts/dev/` | Debug ad-hoc | Cero | git mv |
| `audit/{hardcode_guard,compound_smoke_runner}.py` | MOVE | `audit/runners/` | Actualizar referencias en docs/scripts | Medio | Wrapper temporal o git mv |
| `audit/{HARDCODE_GUARD,COMPOUND_SMOKE}.json` | MOVE | `audit/results/` | — | Bajo | git mv |
| `audit/{C0,C-,F0,F-}*` | MOVE | `audit/baselines/historical/` | Histórico | Cero | git mv |
| `audit/{smoke_runner,smoke_runner_fsmoke,_c3_strip}.py` | DELETE (después de archive) | `audit/temp/` provisional | Sin importadores | Bajo | git revert |
| `src/carter_v2/skills/<vendor>/` (vacíos) | DELETE | — | Sin `.py` adentro | Bajo | git revert |
| `Carter_v2.rar`, `MEMORY.md.bak.*` | MOVE | `backups/` | — | Cero | — |
| `__pycache__`, `.pytest_cache`, `test_probe.db`, `test_skills.db` | DELETE | — | Auto-regen | Cero | — |
| `tests/` (nueva, mínima) | BUILD | `tests/{core,safety,mission,tools,memory,gui_vision,integration}/` | FASE 4 | Alto si rompe regresiones | Backup de tests legacy disponible |

---

## Apéndice A — Compound smoke baseline (FAIL pre-existente)

`audit/compound_smoke_runner.py` falla pre-cleanup en casos de observation-ladder (`uia_unavailable_falls_back_to_unverified`, etc.). NO es regresión introducida por la limpieza; se documenta como deuda heredada que la FASE 4 (mission + gui_vision) debe atender o re-marcar como `expected_unverified`.

## Apéndice B — Reglas para FASE 4

1. Cero frases exactas en español/inglés como contrato.
2. Cero listas de apps por nombre como contrato (Notepad/Steam/etc).
3. Cero verbos hardcodeados ("abrir", "open", "cerrar"…).
4. Backends scripted obligatorios.
5. Tests rápidos (<200ms cada uno, salvo integration smoke marcado).
6. Marca `@pytest.mark.smoke` para los que requieran apps/Ollama reales.
