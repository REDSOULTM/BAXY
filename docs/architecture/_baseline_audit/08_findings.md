# Fase 8 — Hallazgos consolidados (resumen ejecutivo)

> Cosechado de Fases 0→7. Cada hallazgo con: **ubicación exacta** (file:line),
> **severidad** (CRITICAL/HIGH/MED/LOW), **esfuerzo** estimado (S<1d, M=1-3d, L>3d),
> **impacto** (LOC ahorrados, deps eliminadas, latencia, riesgos).
>
> Total estimado de LOC removibles si se ejecutan TODOS los quick wins
> + refactors mayores: **~6 000-8 000 LOC** (del total 55 633) sin tocar
> funcionalidad observable. ~12-15 % del paquete.

---

## TL;DR — Lo que se puede recortar HOY (Quick Wins, <1 día c/u)

| # | Win | Ahorro | Esfuerzo | Riesgo |
|--:|---|--:|---|---|
| 1 | Crear `requirements.txt` desde imports reales | infra crítica | S | nulo |
| 2 | Eliminar las 23 "legacy plain" del dict `_impls` (siguen como métodos privados) | ~25 LOC + dispatcher surface | S | nulo (nadie las invoca externamente) |
| 3 | Eliminar `design_handoff_carter_field/` (carpeta entera) | ~varias kB + clarity | S | nulo |
| 4 | Limpiar strings "carter" en `ui_field/src/*.tsx` + rebuild | brand consistency | S | nulo |
| 5 | Borrar `traces.jsonl` y agregar rotación a `TraceLogger` (o eliminar TraceLogger entero) | 67 LOC + 1.7 MB en disco | S | bajo |
| 6 | Cambiar `AgentState.mark_cleaned` para que BORRE, no marque `closed` | 84 % del state.json = 451 KB de zombies | S | bajo (verificar que nada lee resources cerradas) |
| 7 | Colapsar `experience.flag_grounding` + `flag_grounding_by_turn` en uno | ~25 LOC | S | nulo |
| 8 | Mover `_SSRFGuardRedirectHandler` de `tools.py` a `ops_tools.py` (1-USER) | 30 LOC reubicadas | S | nulo |
| 9 | Inline `_ToolCallRecord` y `_SileroVAD` (cada uno usado en 1 sitio) | ~40 LOC | S | nulo |
| 10 | Borrar `verifiers`/`telemetry`/`ui/panels`/`ui/metrics` huérfanos | ~1 700 LOC | ~~S~~ **NO HACER** — Fase 6 confirmó que están vivos vía dynamic load |
| 11 | Sumar dependencia `pyyaml`, eliminar `_parse_yaml_simple` casero | -74 LOC, +1 dep limpia | S | nulo |
| 12 | Unificar `routine_runner.py` + `watcher_runner.py` en `task_runner --type X` | ~50 LOC | S | nulo |
| 13 | Convertir `ModelInfo` de `TypedDict` a `@dataclass(frozen=True)` | consistencia | S | nulo |

**Total quick wins listos para ejecutar: ~2 000+ LOC** (dominado por state.json bloat y los duplicates).

---

## 1 — CRITICAL (bloquean cualquier refactor mayor)

### 1.1 No existe declaración de dependencias
- **Ubicación:** raíz del repo + paquete `gemma4_agent/`.
- **Evidencia:** Fase 0 — `find -name "requirements*.txt" -o -name "pyproject.toml" -o -name "setup.py" -o -name "uv.lock"` devuelve cero matches.
- **Impacto:** el proyecto no es reproducible para terceros, ni para CI, ni para el dueño después de un reformat. El stack ML (faster-whisper, vosk, piper, torch, transformers, sentence-transformers, sqlite-vec, etc) ni siquiera está documentado.
- **Esfuerzo:** S (script que escanea imports + tabla manual de versiones).
- **Acción:** crear `requirements.txt` desde imports reales (lista de Fase 0 §3.2) + `pyproject.toml` mínimo con `[project]` name + entry points.

### 1.2 `ToolRegistry` 3 157 LOC / ~140 métodos
- **Ubicación:** `tools.py:1486`.
- **Evidencia:** Fase 2/3/7. 88 entries en `_impls` (65 visible al LLM + 23 helpers internos). Constructor instancia `MemoryStore + AgentState + KnowledgeStore + AppResolver` con efectos secundarios.
- **Impacto:** clase imposible de refactorizar sin tests sólidos; modificar cualquier tool requiere navegar 3 157 líneas.
- **Esfuerzo:** L (refactor mayor; primero hacen falta tests de las tools).
- **Acción incremental:** (a) extraer wrappers `t_X` de 1-línea a delegación auto-generada [S]; (b) eliminar 23 entries legacy de `_impls` [S]; (c) extraer `execute()` pipeline + `_PRE_VALIDATORS` a clase `ExecutePipeline` [M]; (d) split por familia (audio/video/system/web) [L].

### 1.3 `Gemma4Agent` 1 852 LOC / 21 métodos; `run_content` solo 892 LOC
- **Ubicación:** `agent.py:608` (clase), `agent.py:895-1786` (`run_content`).
- **Evidencia:** Fase 2/3/4. Tiene 4-5 responsabilidades mezcladas: turn loop + retry + parallel/sequential dispatch + mission tracking + async post-processing + guards + compaction.
- **Impacto:** imposible de testear como unidad; cualquier cambio es riesgoso. Es el #2 candidato a split del repo.
- **Esfuerzo:** L (requiere tests primero).
- **Acción incremental:** (a) extraer `_system_message + _tool_schemas_hint` a `agent/prompt_builder.py` [M]; (b) extraer 6 `_guard_*` a `agent/guards.py` [M]; (c) extraer `_compact_*` + `_summarize_history_block` + `_extract_facts` a `agent/history_compaction.py` [M]; (d) colapsar `_execute_calls_sequential` + `_execute_calls_parallel` con flag [S].

### 1.4 `domain_tools.py` 10 539 LOC con 16+ deps pesadas en cabecera
- **Ubicación:** `domain_tools.py:1-30`.
- **Evidencia:** Fase 2/7. Importa PIL, bs4, fitz, pdfplumber, pdf2image, pypdf, matplotlib, pandas, openpyxl, paho, mysql, psycopg, psycopg2, pymysql, docx, pptx **al top-level**. Cualquier proceso que importe el paquete (CLI, UI, server, MCP, runners) carga toda la pila.
- **Impacto:** boot lento (segundos), memoria base alta. La mayor parte de esas deps son para tools que muchos usuarios no van a invocar nunca.
- **Esfuerzo:** M (mover imports a dentro de cada `<name>_tool` function — son lazy desde Python 3.7+).
- **Acción:** **lazy import por handler.** Cada `<name>_tool` solo importa lo que usa. Ahorro: probablemente 50-80 % del boot time del Registry.

---

## 2 — HIGH (alto valor, esfuerzo razonable)

### 2.1 Triple duplicación de "single-thread worker para el agente"
- **Ubicación:** `ui/agent_thread.py:35` (`AgentWorker` 220 LOC) ≡ `agent_runner.py:72` (`AgentRunner` 476 LOC) ≡ `ui/main_window.py:81` (`ServerBootWorker` ~100 LOC, solo boot).
- **Evidencia:** Fase 2/3/4. Confirmado atributo por atributo: `_inbox: Queue`, `_agent`, thread builder, health polling, `submit/_run/_build_agent`. Diferencia única: pyqtSignal vs BUS pub.
- **Impacto:** ~500 LOC colapsables. Fix de bug en uno requiere fix en los 3.
- **Esfuerzo:** M (clase base `AgentSerialWorker` + 2 adaptadores delgados `QtAdapter`/`BusAdapter`).
- **Acción:** crear `agent_serial.py` con clase base; UI Desktop y UI Field son adaptadores.

### 2.2 Funciones duplicadas auto-confesadas
- **Ubicación:**
  - `tools.py::_redact_sensitive` ≡ `domain_tools.py:50::_redact_credentials` (`# CC-105: paralelo a tools._redact_sensitive`)
  - `tools.py:3945::_hard_gate` ≡ `domain_tools.py:68::_hard_gate` (`# CC-101: gate duro replicable desde domain_tools (sin ToolRegistry)`)
- **Evidencia:** Fase 2/7. Los comentarios del propio código admiten la copia y explican que se debe a evitar import circular.
- **Impacto:** dos lugares para mantener exactamente la misma lógica → divergencias silenciosas.
- **Esfuerzo:** M (extraer a `safety_helpers.py` o un módulo `_shared.py` que no importe ToolRegistry).
- **Acción:** unificar en módulo compartido. Fix de boundary issue.

### 2.3 `state.json` 538 KB con 84 % zombies
- **Ubicación:** `state.py::AgentState.mark_cleaned`.
- **Evidencia:** Fase 5 — 392/468 resources tienen `status="closed"` pero nunca se borran. Cada `_load`/`_save` reserializa 538 KB.
- **Impacto:** lecturas/escrituras crecientes. Si crece a 10 MB, latencia visible.
- **Esfuerzo:** S (cambiar `mark_cleaned` para `del data["resources"][rid]`; agregar `purge_closed(older_than_days=7)`).
- **Acción:** delete on close + retention configurable.

### 2.4 `traces.jsonl` 1.7 MB sin rotación
- **Ubicación:** `tracing.py:25`.
- **Evidencia:** Fase 5. `TraceLogger.event` solo hace `append`; no hay rotate, ni cap, ni TTL.
- **Impacto:** disco crece monótonamente. Telemetry tiene `rotate(keep_days=30)`, este no.
- **Esfuerzo:** S (file rotation por tamaño o por días).
- **Acción:** **mejor: eliminar TraceLogger entero** (ya tiene 3 sinks alternativos: LogRecorder/full + LogRecorder/chat + Timeline + opt-in Telemetry). Migrar callers a publicar al BUS y dejar que LogRecorder/full lo capture.

### 2.5 4 sinks redundantes de "qué pasó en este turn"
- **Ubicación:** `tracing.py`, `log_recorder.py`, `timeline.py`, `telemetry.py`.
- **Evidencia:** Fase 5. TraceLogger (Agent directo → `data/traces.jsonl`), LogRecorder (BUS sync → 2 archivos por sesión), Timeline (Agent → `~/.gemma4/timeline/<sid>-turn<NNN>.jsonl`), Telemetry (BUS → SQLite opt-in).
- **Impacto:** mismo evento se serializa 3-4 veces a 3-4 destinos.
- **Esfuerzo:** M (decidir cuál es el sink canónico + migrar callers + eliminar duplicados).
- **Acción:** **dejar solo LogRecorder (sync BUS listener → `full.log` + `chat.log` por sesión)** y Telemetry como opt-in para métricas numéricas. Eliminar TraceLogger y Timeline.

### 2.6 23 "legacy plain" tools en `_impls` que el LLM no ve
- **Ubicación:** `tools.py:1561-1584`.
- **Evidencia:** Fase 7. Cruce `_impls` (88) vs `COMPOUND_TOOL_SCHEMAS` (65) = 23 extras. Grep externo: `execute("filesystem_list", ...)` 0 matches. Internas: 59 referencias en `tools.py` (uso interno como helpers).
- **Impacto:** dispatcher tiene 23 keys de ruido. Cualquiera que lea `_impls` piensa que son tools del LLM.
- **Esfuerzo:** S (eliminar las 23 entries del dict; los métodos quedan como helpers privados, sin cambio funcional).
- **Acción:** delete `app_close/app_open/app_search/clipboard_*/filesystem_*/gui_*/list_*/memory_*/system_time/terminal_run/web_open_url` del literal `_impls = {...}`.

### 2.7 50+ wrappers de 1 línea `t_<name>` que solo delegan a `domain_tools`
- **Ubicación:** `tools.py:2426-2554` (35 métodos `t_office, t_audio_device, ..., t_smart_home`) + `tools.py:2336-2360` (8 métodos `t_state, t_input, ...` delegando a `ops_tools`).
- **Evidencia:** Fase 2/7. Todos son: `def t_X(self, args): return X_tool(self.state, args)`.
- **Impacto:** ~70 LOC de stubs. No agregan validación ni transformación.
- **Esfuerzo:** S (generar `_impls` dinámicamente vía un loop sobre módulos `domain_tools` y `ops_tools` con introspección).
- **Acción:** auto-registry: `for fn in inspect.getmembers(domain_tools, lambda x: callable(x) and x.__name__.endswith('_tool')): _impls[fn.__name__[:-5]] = lambda args, f=fn: f(self.state, args)`.

### 2.8 `_suggest_tools` regex multilingüe ES/EN/PT/FR/IT en 30+ buckets
- **Ubicación:** `planner.py:212-630+`.
- **Evidencia:** Fase 2/5. ~250 LOC de regex patterns en 5 idiomas. El system prompt dice "Speak Spanish by default" (`agent.py:47`).
- **Impacto:** PT/FR/IT son código no ejercitado en producción. Mayor riesgo de falso positivo en ES.
- **Esfuerzo:** S (eliminar branches PT/FR/IT; mantener ES + EN como cortesía).
- **Acción:** restringir a ES (+ EN para soporte de comandos técnicos como "open"/"play"). Ahorro: ~150 LOC.

### 2.9 `grounding_gate._FALLBACKS_BY_LANG` con 6 idiomas × 4 templates = 24 strings
- **Ubicación:** `grounding_gate.py:145-200`.
- **Evidencia:** Fase 2. Default es ES. Detector de idioma `detect_reply_language` es artesanal y solo se usa para esto.
- **Impacto:** 20 strings + 1 detector son código muerto idiomático.
- **Esfuerzo:** S.
- **Acción:** dejar solo ES (+ EN como fallback). Eliminar `detect_reply_language` o reducirlo a 2 alternativas.

### 2.10 `capability_classifier` (mDeBERTa 280 MB) cuya función es "cachear para próximo turn"
- **Ubicación:** `capability_classifier.py` + `nli_service.py`.
- **Evidencia:** Fase 2/4. En el hot path, el primer turn paga 1.2s primera inference + 280 MB memoria. El verdict del turn N solo afecta al turn N+1 (similar input).
- **Impacto:** si en producción los inputs no se repiten suficiente, ROI negativo. **Hay que medir el cache hit rate.**
- **Esfuerzo:** S para medir (loggear cache hit) + S para eliminar si no aporta.
- **Acción:** medir 1 semana de uso real con `Telemetry.record_turn(extra={"capability_cache_hit": bool})`. Si <20 %, eliminar el subsistema.

### 2.11 `CORE_PROMPT` 160 LOC raw multi-línea + `TOOL_RULES` 330 LOC dict en `agent.py`
- **Ubicación:** `agent.py:45-205` + `agent.py:206-535`.
- **Evidencia:** Fase 2. Cada cambio del prompt requiere editar y reimplementar el módulo Python.
- **Impacto:** prompts mezclados con código orchestrador, difíciles de iterar.
- **Esfuerzo:** M (extraer a `prompts/core.md` y `prompts/tool_rules/<name>.md` cargados lazy).
- **Acción:** crear `gemma4_agent/prompts/` con archivos `.md`; agregar loader simple.

### 2.12 6 `_guard_*` post-reply en Agent Core = 337 LOC de "fixups sintácticos"
- **Ubicación:** `agent.py:2194-2552`.
- **Evidencia:** Fase 2/3. `_guard_unverified_final + _guard_phrase_confirm + _build_user_facing_fallback + _guard_promise_without_action + _guard_grounded_action_claim + _guard_plan_status`. Cada uno fix-up regex+heuristic para cuando el LLM emite algo no deseado.
- **Impacto:** cada cambio de prompt o modelo puede invalidar uno → bugs silenciosos. 337 LOC de defensa.
- **Esfuerzo:** M (no para eliminar — son justificados — sino para extraer a `agent/guards.py` testeable).
- **Acción:** **mantener los guards pero extraerlos** a módulo aparte con tests por guard. Esto reduce `agent.py` y hace cada guard testeable aisladamente.

### 2.13 `mcp_server.py` 332 LOC implementa MCP JSON-RPC desde cero
- **Ubicación:** `mcp_server.py`.
- **Evidencia:** Fase 2. SDK oficial `mcp` package (Python) cubre el protocolo.
- **Impacto:** ~250 LOC ahorrables + futuro-compatible con cambios de spec MCP.
- **Esfuerzo:** M (reescribir el server con SDK).
- **Acción:** reemplazar implementación manual por SDK oficial.

### 2.14 `AppResolver` 9 fuentes de apps; probable overlap
- **Ubicación:** `tools.py:660-1155` (364 LOC, 16 métodos).
- **Evidencia:** Fase 2/3. 9 sources: path, shortcuts, start_apps, uninstall_registry, 2× Steam, Epic, common_exe_roots, manual launch.
- **Impacto:** overlap entre fuentes (e.g. Steam app aparece en uninstall_registry Y en _from_steam). Tiempo de scan multiplicado.
- **Esfuerzo:** M (medir overlap real + eliminar redundantes).
- **Acción:** instrumentar `_from_*` para ver qué porcentaje de candidatos vienen de cada fuente; eliminar las que aportan <5 % únicos.

### 2.15 `notification` 20 actions mezcla toast + timer + alarm + reminder
- **Ubicación:** `tools.py:COMPOUND_TOOL_SCHEMAS` entry de `notification` + `domain_tools.notification_tool`.
- **Evidencia:** Fase 7. Una sola tool con 20 actions de 4 dominios distintos.
- **Impacto:** confusión potencial del LLM. Cada action requiere parametrización distinta. Si `intent_validator` no tiene cross-reject pairs para estas, hay riesgo.
- **Esfuerzo:** M (split en 3-4 tools: `toast`, `timer`, `alarm`, `reminder`).
- **Acción:** evaluar tasa de mal-uso de `notification` actual; split si vale.

### 2.16 Schema drift en `experience.sqlite`
- **Ubicación:** `experience.py:106-120`.
- **Evidencia:** Fase 5. 5 columnas añadidas vía `ALTER TABLE ... ADD COLUMN` envueltas en `try/except sqlite3.OperationalError: pass`.
- **Impacto:** sin migration framework, próximos cambios de schema repetirán el patrón. El `except: pass` también traga errores genuinos (disk full).
- **Esfuerzo:** M (introducir `alembic` o un migration manual basado en `schema_version`).
- **Acción:** versionado de schema explícito.

### 2.17 No hay shutdown coordinado
- **Ubicación:** disperso — cada superficie tiene su exit hook propio.
- **Evidencia:** Fase 4. `RUNNER.stop()`, `VOICE.disable()`, `RECORDER.uninstall()`, `TELEMETRY.disable()`, `LlamaServerManager.stop()` existen pero ningún módulo los orquesta. **`llama-server.exe` sobrevive al cierre de UI.**
- **Impacto:** procesos huérfanos en disco; archivos abiertos; SQLite WAL pendiente.
- **Esfuerzo:** S (crear `gemma4_agent/shutdown.py` con `shutdown_all(timeout=10s)`).
- **Acción:** centralizar; cada superficie llama a `shutdown_all()` en su exit hook.

---

## 3 — MED (vale pero no urgente)

### 3.1 `MainWindow` 1 430 LOC / 53 métodos; `SettingsDialog` 1 148 LOC / 22 métodos
- **Ubicación:** `ui/main_window.py:186`, `ui/settings.py:83`.
- **Esfuerzo:** L (refactor UI con muchos signals).
- **Acción:** split por sub-widget (header, side panels, hud, footer, dialogs) y por tab.

### 3.2 `Skills` + `Microagents` = 2 sistemas declarativos paralelos (807 LOC)
- **Ubicación:** `skills_registry.py` (456) + `microagents.py` (351).
- **Evidencia:** docstring `skills_registry.py:16-20` se autodefiende ("Diferencia vs microagents"). Esa auto-justificación es señal.
- **Acción:** evaluar uso real en producción (cuántos skills/microagents matcheaaron en últimos 100 turns). Si hay solapamiento de propósito, quedarse con uno.

### 3.3 2 YAML parsers caseros (`skills_registry._parse_yaml_simple` 74 LOC + `microagents._FRONTMATTER_RE`)
- **Acción:** adoptar `pyyaml`. -74 LOC, +1 dep limpia (pyyaml es ubicuo).

### 3.4 `LlamaServerManager` 327 LOC mezcla spawn + stop + restart + port + profile env + vision relaunch + external probe + /props
- **Acción:** split en `ServerProcess` (lifecycle) + `ServerProbe` (queries `/health`, `/props`, port).

### 3.5 `personas.py` con 6 personas hardcoded
- **Acción:** verificar uso real (`grep set_persona|GEMMA4_AGENT_PERSONA` en traces/logs). Si solo `default` se usa, eliminar las otras 5 (~70 LOC).

### 3.6 `profiles.json` con `{}` — feature "user customiza profiles" sin uso
- **Acción:** verificar si Settings dialog tiene UI para editar profiles. Si no, eliminar 200+ LOC de manejo de overrides en `profiles.py`.

### 3.7 `Gemma4Agent._extract_facts` + `_summarize_history_block` = 2 LLM calls EXTRA por turn
- **Acción:** medir si están ON con cooldowns activos. Si default es ON con cooldown corto, comen latency budget.

### 3.8 `Gemma4Agent._execute_calls_sequential` + `_execute_calls_parallel` (86 + 97 LOC) — lógica similar
- **Acción:** colapsar a 1 método con flag `parallel: bool`.

### 3.9 `Gemma4Agent._compact_completed_history` + `_compact_active_history_for_retry` — 2 compactadores
- **Acción:** revisar si difieren genuinamente o pueden compartir base.

### 3.10 `AgentState` 17 métodos + 4 sub-stores
- **Acción:** split por sub-store (`ResourceStore` + `CheckpointStore` + `NotesStore` + `ConfirmationStore`) o al menos colapsar `update_resource` ≡ `update_resource_metadata`.

### 3.11 `experience.flag_grounding` + `flag_grounding_by_turn` — mismo método con selector
- **Acción:** colapsar.

### 3.12 `routine_runner.py` + `watcher_runner.py` — idénticos estructuralmente
- **Acción:** `task_runner --type {routine,watcher}`. Ahorro: ~50 LOC.

### 3.13 14 tools dominio-específicas sospechosas de no usarse
- **Tools:** `smart_home`, `creative_local`, `container`, `database`, `form_filler`, `peripheral`, `accessibility`, `fact_check`, `source_manager`, `email`, `printer_scanner`, `data_analysis`, `media_edit`, `study`, `habit_tracker`.
- **Acción:** medir uso en `traces.jsonl` con el script de Fase 7 §"Cómo cruzar con uso real". Cada tool no usada permite eliminar su entrada en `domain_tools.py` + su dep.

### 3.14 `TelemetryStore` 443 LOC para feature opt-in default OFF
- **Acción:** o eliminar entero (los demás sinks cubren la info), o reducir a 1 tabla flat (~60 LOC).

### 3.15 35 env vars `GEMMA4_*`
- **Acción:** auditar cuáles se cambian en producción. Las que tienen default permanente eliminar.

### 3.16 `config.AgentConfig.from_env` side-effect: aplica perfiles al construirse
- **Ubicación:** `config.py:125-141`.
- **Acción:** separar `AgentConfig.from_env()` puro de `apply_persisted_profile()` explícito.

### 3.17 `TELEMETRY` singleton se construye al **import** del módulo (`telemetry.py:443`)
- **Acción:** factory function lazy.

### 3.18 27 `pending_action` resources `open` en state.json
- **Acción:** TTL en confirmations sin resolver (auto-cancel después de N días).

### 3.19 `gui.json` y `profiles.json` sin schema/version
- **Acción:** versionar el archivo + migrar campos viejos al cambiar el formato.

### 3.20 LRU caches manuales (`semantic_router`, `nli_service`, `capability_classifier`)
- **Acción:** `functools.lru_cache` (con `cache_info` para telemetry).

### 3.21 `_PRE_VALIDATORS` mapping inconsistente con `@register_verifier` decorator
- **Acción:** unificar al patrón decorator-registry.

### 3.22 `safety.py` + 2× `_hard_gate` = 3 lugares para "esta tool es peligrosa"
- **Acción:** unificar en `safety.py`.

### 3.23 Continuation hint con regex hardcoded para 7 plataformas streaming
- **Acción:** datafile externo `streaming_brands.txt` o eliminar el patrón si no se ejercita.

### 3.24 `_build_agent` en `agent_runner.py` con 7 fases en un solo método de 150+ LOC
- **Acción:** refactor a método por fase para testeo.

---

## 4 — LOW (cosmético, oportunista)

| # | Hallazgo | Ubicación |
|--:|---|---|
| 4.1 | `voice/stt.py` docstring de 35 líneas | `voice/stt.py:1-50` |
| 4.2 | `voice/tts.py` 3 voces Piper, 1 default (otras 2 sin selector) | `voice/tts.py:35-48` |
| 4.3 | `voice_runner.py` 425 LOC para un bridge — sospecho features acumuladas | `voice_runner.py` |
| 4.4 | `_RECOVERABLE_CONN_ERRORS` 7 substrings de errores con comentarios largos | `llm_client.py:23-31` |
| 4.5 | `ModelInfo` es `TypedDict`, no `@dataclass(frozen=True)` | `model_info.py:21` |
| 4.6 | `_INCONCLUSIVE_BY_NATURE = frozenset({"gui", "browser"})` con 2 entries | `mission_outcome.py:32` |
| 4.7 | `_VERB_KIND_PATTERNS` multilingüe en `mission_goal.py` (mismo problema que 2.8) | `mission_goal.py:98+` |
| 4.8 | `OutcomeStatus` 9 estados — verificar distribución real | `mission_goal.py:43-53` |
| 4.9 | `select_tool_names._last_fallback_used` como atributo de función → race condition | `planner.py:154,181,186` |
| 4.10 | `_WHISPER_HALLUCINATIONS` duplicado en `ui/main_window.py:41` y `voice/stt.py:87` | ambos |
| 4.11 | `grounding_gate._HONEST_FALLBACK` shadow con `_FALLBACKS_BY_LANG["es"]["generic"]` | `grounding_gate.py:140` vs 147 |
| 4.12 | `domain_tools._chunk_text` hardcoded `max_chars=2200, overlap=250` | `domain_tools.py` |
| 4.13 | `knowledge._fts_query` trunca a 12 términos silenciosamente | `knowledge.py:249-253` |
| 4.14 | `MemoryStore.MAX_TOTAL_ITEMS=500` sin TTL/LRU | `memory.py:18` |
| 4.15 | `Gemma4Agent` 12 atributos de instancia state-sprawl | `agent.py:611-651` |
| 4.16 | `INHERIT_TTL_SEC` + `DANGEROUS_TOOLS_NEVER_INHERIT` en `agent.py` top-level | `agent.py:27-38` |
| 4.17 | `_SileroVAD` 1-user (inline en StreamingSTT) | `voice/stt.py:198` |
| 4.18 | `_State` (semantic_router) singleton dataclass 1-user | `semantic_router.py:95` |
| 4.19 | `_ToolCallRecord` 1-user | `mission_outcome.py:43` |
| 4.20 | `_SSRFGuardRedirectHandler` 1-user en `tools.py` | `tools.py:1365` |
| 4.21 | `boot_progress.py` mezcla `LlamaLogTail` con `emit_stage` helper | `boot_progress.py` |
| 4.22 | `prewarm.py` 140 LOC = 30 docstring + 25 core + boilerplate defensivo | `prewarm.py` |
| 4.23 | `LlamaLogTail` mejor en `llama_server.py` que en `boot_progress.py` | `boot_progress.py:56` |
| 4.24 | `multimodal._bump_image_counter` doble notificación (callback + BUS) | `multimodal.py:62-98` |
| 4.25 | `negative anchor email vs perfil` (planner.py:160-163) | `planner.py:160-163` |
| 4.26 | `semantic_router.min_score=0.25` hardcoded | `semantic_router.py` |
| 4.27 | `~/.gemma4/cache/app_inventory.json` sin TTL documentado | `AppResolver` |
| 4.28 | `captures/` y `data/generated/` dentro del package en vez de `~/.gemma4/` | gitignore implications |
| 4.29 | `backups/*.zip` y `jobs/*.log` sin cap ni TTL | |
| 4.30 | `memory.json` con solo 3 items — feature subutilizada | |
| 4.31 | `knowledge.sqlite` vacío en disco — verificar si feature se usa | |
| 4.32 | `~50 except: pass` mudos | 39 archivos con ≥1 |
| 4.33 | `1 TODO` (`domain_tools.py:5941` — `# TODO: cuando exista state.user_locale, usarlo aca con fallback.`) | `domain_tools.py:5941` |
| 4.34 | 15 funciones con >5 parámetros (top: `experience.record` 11, `voice/controller.__init__` 9, `telemetry.record_turn` 9) | varios |
| 4.35 | `from .X import Y` lazy 6+ veces en `agent.py` (disfraza grafo AST) | `agent.py` |
| 4.36 | Warmup con `messages=[{role:user,content:'.'}]` — frágil ante cambios de modelo | `agent_runner.py:380` |
| 4.37 | SQLite no se cierra en shutdown → WAL files quedan en disco | global |
| 4.38 | Daemon threads (LogRecorder, ProfileWatcher) mueren sin flush | global |
| 4.39 | `boot_progress.py` 145 LOC, mezcla constantes + clase + helper | `boot_progress.py` |
| 4.40 | `ratio lazy:eager imports = 1.18` — grafo defensivo, AST mentiroso | global |

---

## 5 — Carter residual (cosmético)

Por scope del proyecto, Carter dentro de `gemma4_agent/` es **solo
documental** (cero código vivo, confirmado en Fase 0 + Fase 6).

| Acción | Esfuerzo | Riesgo |
|---|---|---|
| Eliminar `gemma4_agent/design_handoff_carter_field/` | S | nulo |
| Limpiar strings "carter" en `ui_field/src/components/SettingsPanel.tsx`, `TopBar.tsx`, `styles/prototype.css`, `index.html` + rebuild | S | nulo |
| Limpiar comentarios "Carter v5", "Carter v4", "ContextoCarter" en docstrings de `mcp_server.py:28`, `mission_goal.py:13,39,44`, `mission_outcome.py:15,16`, `llama_server.py:309,322`, `skills_registry.py:1,48`, `verify_core.py:3` | S | nulo |

---

## 6 — Cosas que están bien y NO hay que tocar

> Para no caer en "refactor por refactor".

- **`events_bus.EventBus`** (99 LOC, 7 métodos públicos) — diseño mínimo honesto con dos canales (listeners sync + queues async) y tradeoffs explícitos. Mantener tal cual.
- **Grafo de dependencias acíclico** (0 ciclos confirmados en Fase 6). Buen logro estructural.
- **0 código muerto real** (los 4 huérfanos de Fase 0 fueron falsos positivos descartados). No hay LOC para borrar por estar huérfanos.
- **Voice Loop** (`voice/*`) — subsistema con frontera nítida; los modelos en disco están justificados; el state machine de 9 estados está bien definido.
- **Mission/Verification** subsistema completo (1 800 LOC) — heredado de Carter pero filosóficamente coherente ("honestidad por construcción"); cada estado del `OutcomeStatus` tiene justificación.
- **1 solo TODO en todo el repo** (`domain_tools.py:5941`). Limpio de deuda explícita.
- **`AudioCapture` con PortAudio callback liviano + pump thread** — patrón correcto.
- **Profiles VRAM-aware** (5 perfiles `performance/balanced_8gb/balanced/light/standby`) — diseño consciente del hardware target.

---

## 7 — Plan de ejecución sugerido

Si tengo que recortar **basura sin riesgo**, en este orden:

### Sprint 0 — Infra crítica (1 día)
1. Crear `requirements.txt` (de imports reales).
2. Crear `pyproject.toml` mínimo + entry points.
3. CI básico (lint + import test).

### Sprint 1 — Quick wins puros (1-2 días, ~2 500 LOC removidas)
4. Eliminar `design_handoff_carter_field/`.
5. Limpiar strings "carter" en `ui_field/` + rebuild.
6. Eliminar 23 entries legacy de `_impls`.
7. `mark_cleaned` que borre + script de purge de `state.json` actual.
8. Colapsar `flag_grounding` + `flag_grounding_by_turn`.
9. Inline `_ToolCallRecord`, `_SileroVAD`, `_State`.
10. Mover `_SSRFGuardRedirectHandler` a `ops_tools.py`.
11. Adoptar `pyyaml`; eliminar parser casero.
12. `task_runner --type {routine,watcher}`.
13. `ModelInfo` → dataclass.

### Sprint 2 — Medir antes de cortar (1 semana de telemetry)
14. Activar Telemetry + agregar contadores: `tool_call` por nombre, `capability_classifier` cache hit, `persona` set, `microagent` match, `skill_load`, fallback semantic, NLI usage.
15. Decidir cuáles de las 14 tools dominio-específicas eliminar.
16. Decidir si `capability_classifier` + mDeBERTa se quedan.

### Sprint 3 — Refactor mayor (3-5 días)
17. Colapsar `AgentWorker` + `AgentRunner` + `ServerBootWorker` en `agent_serial.py`.
18. Unificar `_redact_sensitive` + `_redact_credentials` en `_shared.py`.
19. Unificar `_hard_gate` × 2 + `classify_tool_call` en `safety.py`.
20. Eliminar `TraceLogger` + `Timeline`; dejar solo `LogRecorder` + opt-in `Telemetry`.
21. Lazy imports en `domain_tools.py` (por handler).
22. Extraer `CORE_PROMPT` + `TOOL_RULES` a `prompts/*.md`.

### Sprint 4 — Refactor de god-classes (semanas)
23. Split de `ToolRegistry` (con tests primero).
24. Split de `Gemma4Agent` (con tests primero).
25. Split de `MainWindow` + `SettingsDialog`.

---

## 8 — Ranking final del repo

| Aspecto | Veredicto |
|---|---|
| **Tamaño del problema** | 55 633 LOC. Tres god-modules (`tools.py` 4 825 + `domain_tools.py` 10 539 + `agent.py` 2 968) concentran 33 %. |
| **Estructura macro** | 15 containers identificados, taxonomía clara. **0 ciclos de import.** Buen logro. |
| **God classes** | 4 `[GOD MÁXIMO]`: `ToolRegistry` (3 157 LOC, 140 métodos), `Gemma4Agent` (1 852 LOC, 21 métodos), `MainWindow` (1 430 LOC, 53 métodos), `SettingsDialog` (1 148 LOC, 22 métodos). |
| **Duplicación** | 4 grandes: 3 sinks de telemetry, 3 workers del agente, 2 funciones `_redact_*` y `_hard_gate`, 2 YAML parsers. |
| **Código muerto** | **0 confirmado** vía grafo. ~70 LOC de wrappers vacíos a borrar. |
| **Sobre-ingeniería** | 4 sistemas declarativos (Personas + Skills + Microagents + TOOL_RULES), 6 piezas de routing/validation, 9 fuentes de apps en `AppResolver`. |
| **Idiomas no usados** | regex multilingüe ES/EN/PT/FR/IT en `planner` y `mission_goal`; fallbacks en 6 idiomas en `grounding_gate`. |
| **Persistencia** | **26 superficies distintas.** `state.json` 84 % zombies. `traces.jsonl` sin rotación. 4 sinks de "qué pasó este turn". |
| **Tests** | 44 tests, 1 monster (`test_gx_features.py` 2 666 LOC). |
| **Carter** | 0 código vivo, ~11 comentarios documentales + 1 carpeta legacy. |
| **Lo bien hecho** | EventBus, voice loop, mission/verification, grafo acíclico, profiles VRAM-aware, 1 solo TODO en todo el repo. |

**Conclusión:** el repo no está roto — está **maduro y sobre-ingeniado**.
La mayor parte de la deuda viene de **acumulación de features ortogonales
con propósitos solapados** (3 memorias × 3 sistemas declarativos × 4 sinks
× 3 workers × 2 UIs × etc) y de **3-4 god classes** que necesitan split
con tests sólidos antes. **No hay LOC para borrar "gratis"**; todo el
recorte requiere o quick wins puntuales o refactor con tests.
