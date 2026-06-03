# Seed de hallazgos — checklist activa durante Fases 0→7

> No es un entregable. Es un bloc donde voy anotando con file:line cada cosa
> que matchee uno de los patrones de sobre-ingeniería que me pasó el dueño.
> Al llegar a Fase 8, todo esto se consolida y se reformatea en
> `08_findings.md` con severidad/esfuerzo/impacto.

## Criterios de búsqueda activa

- [ ] Clase base con UNA sola subclase
- [ ] Wrapper que solo reenvía sin agregar lógica
- [ ] Factories con 1 producto, Strategies con 1 estrategia, Observers con 1 listener
- [ ] Cadenas A→B→C donde A podría llamar C directo
- [ ] Flags de config que nunca cambian de valor (grep de `os.environ.get("GEMMA4_*")` vs valores usados)
- [ ] Try/except que tragan errores sin razón (`except: pass`, `except Exception: pass`)
- [ ] TODO/FIXME viejos
- [ ] Código comentado en vez de borrado
- [ ] Funciones con > 5 parámetros
- [ ] Clases que son básicamente diccionarios con métodos
- [ ] Helpers/utils usados en 1 solo lugar (revisar al construir grafo en Fase 6)
- [ ] Tests que testean el framework en vez del código del proyecto

## Hallazgos preliminares de Fase 0 (van a 08_findings.md)

### CÓDIGO MUERTO PROBABLE
- ~~`verifiers.py` (690 LOC) — huérfano~~ → **FALSO POSITIVO**: `agent.py:1262` hace `from . import verifiers as _verifiers_registry  # noqa: F401  registra via decorators`. Carga dinámica vía side-effect.
- ~~`telemetry.py` (443 LOC, `TelemetryStore` 340 LOC / 15 métodos) — huérfano~~ → **FALSO POSITIVO**: `server.py:368` mapea env var; subscribe al BUS al cargar. Opt-in por `GEMMA4_TELEMETRY`.
- ~~`ui/panels.py` (390 LOC) — huérfano~~ → **FALSO POSITIVO**: `ui/main_window.py:25-26` hace `from . import metrics as metrics_mod` + `from . import panels`. Mi scanner AST falló con `from . import X` sin sub-import.
- ~~`ui/metrics.py` (179 LOC) — huérfano~~ → **FALSO POSITIVO**: misma razón.
- ~~`data/study.sqlite` huérfano~~ → **FALSO POSITIVO**: `domain_tools.py:1019` lo crea para flashcards SM-2 (tool `study`).

### CÓDIGO MUERTO REAL (pendiente Fase 6 grafo definitivo)
- (Ninguno confirmado hasta acá.)

### CARPETAS DEUDA
- `design_handoff_carter_field/` — Carter handoff dentro de `gemma4_agent/`. Eliminar.

### DEPENDENCIAS REDUNDANTES (en domain_tools.py)
- Drivers SQL duplicados: `psycopg`+`psycopg2`, `mysql`+`pymysql`.
- Parsers PDF cuádruples: `fitz`+`pdfplumber`+`pdf2image`+`pypdf`.

### CONFIG / DECLARACIÓN
- No existe `requirements.txt` / `pyproject.toml` / `setup.py` / `uv.lock`. Quick win obligatorio.
- `ui_field/README.md` es boilerplate de Vite sin tocar.
- `ui_field/` tiene strings "carter" hardcodeadas en TSX y bundle (`SettingsPanel.tsx`, `TopBar.tsx`, `prototype.css`, `index.html`, `dist/`).

### REDUNDANCIA POSIBLE (a confirmar en Fase 2/3)
- 3 memorias paralelas: `memory.py` (JSON), `experience.py` (SQLite+vec), `knowledge.py` (SQLite+ST). **→ Fase 1: PROPÓSITOS DISTINTOS, no son redundantes. Mantener separadas pero marcar.**
- 2 sistemas de "habilidades": `microagents.py` (351 LOC) + `skills_registry.py` (456 LOC) = 807 LOC. **→ Fase 1: ortogonales según docstring (eager+trigger vs lazy+menu), pero evaluar si uno sobra en práctica.**
- 6 piezas de "intent/router/grounding": `planner` + `semantic_router` + `capability_classifier` + `nli_service` + `intent_validator` + `grounding_gate`. Cadena con 1 LLM + 2 modelos ML.
- 3 superficies de UI: `chat.py` (CLI), `ui/` (PyQt), `ui_field/`+`server.py` (React+FastAPI). Las 3 vivas.
- 11 entry-points distintos.
- **3 sinks de "lo que pasó en este turn"**: `tracing.TraceLogger` (Agent escribe directo a JSONL), `log_recorder.RECORDER` (BUS sync → 2 archivos por sesión), `telemetry.TelemetryStore` (BUS → SQLite, opt-in). Probable solapamiento de información.
- **2 wrappers "single-thread worker para Gemma4Agent"** con APIs distintas: `ui/agent_thread.AgentWorker` (UI Desktop, basado en QThread) y `agent_runner.AgentRunner` (UI Field, basado en threading + queue). Candidato a colapsar.

### FLAGS DE CONFIG A REVISAR (probables defaults eternos)
- `GEMMA4_DISABLE_TOOL_SCHEMAS_HINT` — `agent.py:792` lo marca como "legacy opt-out kept for backward compat".
- `GEMMA4_SKILLS_OFF`, `GEMMA4_MICROAGENTS_OFF`, `GEMMA4_MISSION_OFF`, `GEMMA4_EXPERIENCE_MEMORY`, `GEMMA4_KNOWLEDGE_RERANK`, `GEMMA4_SEMANTIC_FALLBACK`, `GEMMA4_TELEMETRY` — cada subsistema mayor tiene su opt-out. Cuántos se usan en producción?

### SAFETY ≠ SANDBOX
- `safety.py` se llama "safety" pero son 67 LOC de chequeos pre-call + prompts de confirmación. NO aísla la ejecución. Tools como `subprocess`, `shell`, `file_delete`, `file_write` corren en el mismo proceso del agente con permisos del usuario. Mencionar en findings.

### GOD MODULES / GOD CLASSES
- `tools.py::ToolRegistry` — 3 157 LOC, 142 métodos. El extremo del repo.
- `domain_tools.py` — 10 539 LOC, 314 funciones top-level, +20 deps externas.
- `agent.py::Gemma4Agent` — 1 852 LOC, 21 métodos.
- `ui/main_window.py::MainWindow` — 1 430 LOC, 53 métodos.
- `ui/settings.py::SettingsDialog` — 1 148 LOC, 22 métodos.

### CARTER (documental, no funcional)
- 11 menciones residuales en docstrings/comentarios — `mcp_server.py:28`, `mission_goal.py:13,39,44`, `mission_outcome.py:15,16`, `llama_server.py:309,322`, `skills_registry.py:1,48`, `verify_core.py:3`.

## Hallazgos nuevos de Fase 2 (componentes)

### CRITICAL
- **`tools.py` 4 825 LOC + `domain_tools.py` 10 539 LOC = 15 364 LOC en 2 god-modules.** `ToolRegistry` con ~86 entries en `_impls`. Re-leerlo entero inviable.
- **`domain_tools.py` carga 16+ deps pesadas en cabecera** (PIL, bs4, fitz/pdfplumber/pdf2image/pypdf, matplotlib, pandas, openpyxl, paho, mysql, psycopg, psycopg2, pymysql, docx, pptx). Cualquier importador (CLI, UI, server, mcp, runners) paga el boot.
- **`Gemma4Agent.run_content` 892 LOC en un solo método.** Imposible de testear; tocar es riesgo alto.
- **`Gemma4Agent` orquesta 21 dependencias.** God class.

### HIGH
- **`AgentWorker` (PyQt) vs `AgentRunner` (FastAPI) — duplicación confirmada** atributo a atributo. Mismas operaciones, distinto reporter. ~400 LOC colapsables.
- **`ServerBootWorker` (PyQt) vs `AgentRunner._autostart_llama_server` (FastAPI) — misma duplicación** en boot. 100+ LOC.
- **2 funciones duplicadas auto-confesadas en `tools.py` ↔ `domain_tools.py`:** `_redact_sensitive` ↔ `_redact_credentials`; `_hard_gate` ↔ `_hard_gate`. Comentarios explícitos lo admiten ("paralelo a tools._X").
- **~50 wrappers de 1 línea en `ToolRegistry._impls`** (`t_office`, `t_audio_device`, ..., `t_smart_home`) que solo reenvían a `domain_tools.<name>_tool(state, args)`. ~70 LOC de stubs. Y otros 8 wrappers (`t_state`, `t_input`, ...) a `ops_tools`. ~16 LOC más.
- **Dos familias en `_impls`** del Registry: compound (62 en `COMPOUND_TOOL_SCHEMAS`, las que ve el LLM) + legacy plain (~24, NO en schemas). Si nadie las usa, ~1 500 LOC zombies.
- **`AppResolver` 364 LOC, 9 fuentes** (path, shortcuts, start_apps, uninstall registry, 2× Steam, Epic, common_exe_roots). Probablemente reducible a 2-3 con tests de cobertura.
- **Skills + Microagents** = 2 sistemas declarativos paralelos para enrich del system_prompt (807 LOC combinados). El propio docstring se autodefiende.
- **Dos YAML parsers caseros**: `skills_registry._parse_yaml_simple` (74 LOC) y `microagents._FRONTMATTER_RE`. Cero deps en `pyyaml`.
- **`_suggest_tools` regex multilingüe ES/EN/PT/FR/IT** en 30+ buckets (~250 LOC de patterns) para un agente "Spanish by default". PT/FR/IT son código no ejercitado en producción.
- **`capability_classifier` carga mDeBERTa 280MB para 10 labels.** Costo: 1.2s primera inference. ROI a verificar.
- **`grounding_gate._FALLBACKS_BY_LANG` con 6 idiomas (es/en/it/pt/fr/de) × 4 templates = 24 strings**. Si default es ES, 20 strings son código muerto.
- **6 `_guard_*` methods en Agent Core = 337 LOC** de "post-reply sintactic fixups". Síntoma de que el LLM emite cosas no deseadas y parchamos sintácticamente. Cada cambio de prompt o modelo puede invalidar uno.
- **`CORE_PROMPT` raw multi-línea de ~160 LOC en `agent.py`.** Mejor en `.md` lazy-loaded (como skills).
- **`TOOL_RULES` dict ~330 LOC en `agent.py`** + `semantic_router.TOOL_DESCRIPTIONS` 62 entradas + `COMPOUND_TOOL_SCHEMAS` ~62 schemas en `tools.py` = **3 lugares con metadatos por-tool que pueden divergir**.
- **`launcher.run_ui --legacy-ui` spawnea `python -m gemma4_agent.ui` como subproceso** = 2 procesos Python. Aceptable, costoso.
- **`mcp_server.py` 332 LOC implementa MCP JSON-RPC desde cero.** SDK oficial `mcp` package podría reducirlo a 50-80 LOC.

### MED
- **3 LRU caches manuales** (`semantic_router._EMBED_CACHE`, `nli_service._cache`, `capability_classifier._cache`). Reinvento de `functools.lru_cache`/`OrderedDict.move_to_end`.
- `experience.flag_grounding` y `flag_grounding_by_turn` son **el mismo método con selector distinto**. Colapsable.
- `routine_runner.py` y `watcher_runner.py` **estructuralmente idénticos**. Colapsables a `task_runner --type {routine,watcher}`.
- `state.update_resource` y `state.update_resource_metadata` APIs **casi idénticas**.
- `AgentState` con **17 métodos + 4 conceptos** (resources/checkpoints/notes/confirmations) en una sola clase.
- `personas.py` con 6 personas hardcoded. Verificar cuántas se usan.
- `Gemma4Agent._extract_facts` y `_summarize_history_block` hacen **LLM calls EXTRA** dentro del turn. Si están ON con cooldown corto, comen latency budget.
- `Gemma4Agent._execute_calls_sequential` (86) y `_execute_calls_parallel` (97 LOC) **lógica similar**, distintos en serialización. Refactor a 1 método.
- `Gemma4Agent._compact_completed_history` y `_compact_active_history_for_retry` **2 compactadores**.
- `LlamaServerManager` 327 LOC, 12 métodos: mezcla spawn+stop+restart+port+profile envvar+vision relaunch+external server+ /props. Candidato split.
- **`_PRE_VALIDATORS` mapping** (`tools.py:1643`) NO usa decorator pattern como `@verifier`. Inconsistencia.
- **`safety.py` + 2× `_hard_gate` = 3 lugares para "esta tool es peligrosa"**.
- `boot_progress.py` mezcla `LlamaLogTail` (tail+regex) con `emit_stage` (helper).
- `prewarm.py` (140 LOC) tiene 30 LOC de docstring + opt-out env + double try BUS para 25 LOC de core. Sobre-documentado.
- `multimodal._bump_image_counter` emite **doble notificación** (callback + BUS) por diseño documentado. Vigilar que no crezca a 3-4 consumidores.
- `TraceLogger` y `LogRecorder/full.log` **persisten información cuasi-equivalente** en formatos cuasi-idénticos. Solo el bus path los diferencia.
- `Telemetry` con 4 tablas + 12 índices + WAL + housekeeping + export + summarize_24h (443 LOC) para una feature opt-in que probablemente nadie usa.
- `TELEMETRY` singleton se construye al **import**, llama a `AgentConfig.from_env()` (side effect).
- **35 env vars `GEMMA4_*`** (no 20 como dije antes; corregir).
- `config.AgentConfig.from_env` lee `~/.gemma4/active_profile.txt` y aplica env vars al construirse. Side-effect de import oculto.

### LOW
- `voice/stt.py` con docstring de 35 líneas explicando 9 cambios + refs. Honesto pero excesivo.
- `voice/tts.py` define 3 voces Piper, 1 default. Las otras 2 sin selector UI → muertas.
- `voice_runner.py` 425 LOC para un bridge. Sospecho features acumuladas.
- `_RECOVERABLE_CONN_ERRORS` en `llm_client.py:23` lista 7 substrings.
- `ModelInfo` es `TypedDict`, no `dataclass`. Inconsistente con el resto.
- `_INCONCLUSIVE_BY_NATURE = frozenset({"gui", "browser"})` con 2 entries. Lista bastaría.
- `_VERB_KIND_PATTERNS` multilingüe en `mission_goal.py`.
- `OutcomeStatus` 9 estados.
- `select_tool_names._last_fallback_used` setea atributo de función. **Race condition** si 2 turns paralelos.
- `_WHISPER_HALLUCINATIONS` **duplicado** en `ui/main_window.py:41` y `voice/stt.py:87` (listas distintas).
- `grounding_gate._HONEST_FALLBACK` (línea 140) shadow con `_FALLBACKS_BY_LANG["es"]["generic"]`.
- `domain_tools._chunk_text` con `max_chars=2200, overlap=250` hardcoded.
- `knowledge._fts_query` trunca a 12 términos silenciosamente.
- `MemoryStore.MAX_TOTAL_ITEMS=500` sin TTL/LRU.
- `Gemma4Agent` con 12 atributos de instancia state-sprawl (`_recent_recalls`, `_phrase_fires`, `_cached_*`, `_explicit_plan_*`, etc).
- `Gemma4Agent.clear` resetea cache de skills "por dev mode". En prod innecesario.
- `INHERIT_TTL_SEC` + `DANGEROUS_TOOLS_NEVER_INHERIT` en `agent.py` (no en `inherit_tools.py`).
- `from .X import Y` lazy dentro de métodos en `agent.py` (6+ veces). Disfraza grafo real para AST.

## Hallazgos nuevos de Fase 3 (UML de clases)

### CRITICAL/HIGH (reafirmados o ampliados)
- **`ToolRegistry` 3 157 LOC / ~140 métodos** — `[GOD MÁXIMO]` confirmado en UML. **#1 candidato a split** del repo.
- **`Gemma4Agent` 1 852 LOC / 21 métodos / 12 atributos privados** — `[GOD MÁXIMO]` confirmado. **#2 candidato a split.**
- **`MainWindow` 1 430 LOC / 53 métodos** — `[GOD MÁXIMO UI]`. **#3 candidato a split.**
- **`SettingsDialog` 1 148 LOC / 22 métodos** — `[GOD UI]`. **#4 candidato a split** (por tab).

### MED nuevos
- **`AppResolver` 16 métodos, 9 fuentes de apps** — `[GOD]`. Reducible a 3-4 fuentes.
- **`StreamingSTT` 488 LOC, 11 métodos** — `[GOD]`. Split posible: STT puro + quality check + warmup.
- **`VoiceController` 495 LOC, 27 métodos** — `[GOD]` por número de métodos. Split: state machine + lifecycle + timers + TTS bridge.
- **`ExperienceMemory` 371 LOC, 9 métodos** — `[GOD]`. Split o reducir provenance fields.
- **`TelemetryStore` 443 LOC, 15 métodos** — `[GOD]`. Reducir radicalmente o eliminar (opt-in que nadie usa).
- **`LlamaServerManager` 327 LOC, 12 métodos** — `[GOD]` borderline. Split en `ServerProcess` + `ServerProbe`.
- **`HudCanvas` 451 LOC, 26 métodos** — `[GOD UI]` nuevo. Verificar si pintura justifica el conteo.
- **`AgentState` 17 métodos, 4 sub-stores** — `[GOD]` borderline. Posible split por sub-store.

### LOW nuevos
- **`_ToolCallRecord` 1-user** (solo `compute_mission_outcome`) — inline.
- **`_SileroVAD` 1-user** (solo `StreamingSTT`) — inline.
- **`_State` (semantic_router) singleton dataclass** — inline a variables módulo.
- **`_SSRFGuardRedirectHandler` 1-user en `tools.py`** — mover a `ops_tools.py`.

### Inconsistencias de estilo (no urgentes)
- **`ModelInfo` es `TypedDict`** mientras todas las otras estructuras del repo (`MissionOutcome`, `AgentReply`, `Profile`, `Persona`, `ToolEvent`, `ExpectedOutcome`, etc) son `@dataclass(frozen=True)`. Cambiar a dataclass para consistencia.
- **`_PRE_VALIDATORS: dict[str, Callable]` mapping** mientras `VERIFIER_REGISTRY` se puebla con decorator `@register_verifier`. Mismo patrón "lookup por nombre" implementado de 2 maneras.

### Confirmaciones de Fase 2 (reafirmadas en UML)
- **`AgentRunner` ≡ `AgentWorker` ≡ `ServerBootWorker`** triple-duplicación del patrón "single-thread worker + boot".
- **`flag_grounding` ≡ `flag_grounding_by_turn`** en `ExperienceMemory`.
- **`update_resource` ≡ `update_resource_metadata`** en `AgentState`.

## Hallazgos nuevos de Fase 4 (secuencias)

### MED
- **No hay shutdown coordinado** — `RUNNER`/`VOICE`/`RECORDER`/`TELEMETRY`/`LlamaServerManager` cada uno con su `stop()` pero ningún módulo orquesta. **`llama-server.exe` sobrevive al cierre de UI** si nadie lo paró explícitamente.
- **`_build_agent` (agent_runner) 7 fases serializadas + 1 paralela en un solo método de 150+ LOC** — refactor a método por fase mejora testeo.
- **Hasta 13 threads simultáneos durante un voice turn** (audio capture+pump+wake+STT+TTS+ducker COM+runner+NLI+grounding+experience+health polling+profile watcher+log recorder). Diagnosticar problemas multi-thread va a ser un dolor.
- **Continuation hint con regex hardcoded para 7 plataformas streaming** (netflix|disney|hbo|max|prime|amazon|spotify) — cualquier plataforma nueva no dispara el hint.
- **`capability_classifier` lo único que hace este turn es "cachear para próximo"** — su valor real depende de cache hit rate en producción. Si no se repiten inputs similares, los 280MB del modelo NLI son desperdicio.

### LOW
- **Warmup con `messages=[{role:user,content:'.'}]`** — el "." como neutro es frágil; futuras versiones de Gemma pueden interpretarlo distinto.
- **SQLite no se cierra en shutdown** — WAL deja `*.sqlite-wal/-shm` en disco; SQLite los unifica al próximo open, pero es chusma.
- **Daemon threads (LogRecorder, ProfileWatcher) mueren sin flush** — sesiones largas pierden últimos N eventos.
- **Negative anchor "drop email si perfil + sin mail keywords"** (planner.py:160-163) es un parche reactivo a un bug. Si se acumulan más así, vale generalizar.
- **`semantic_router.min_score=0.25` threshold hardcoded** — si cambia el modelo de embeddings, puede ser óptimo o no.

## Hallazgos nuevos de Fase 5 (data + estado)

### HIGH
- **`state.json` no purga `closed` resources**: 392/468 entradas (84 %) son zombies. Cada read/write reserializa el JSON entero (538 KB). Necesita `mark_cleaned` que **delete**, no que solo cambie status.
- **`traces.jsonl` sin rotación**: 1.7 MB y crece para siempre. Telemetry tiene `rotate(keep_days=30)`, este sink no.
- **4to sink "timeline"** no documentado en mi Fase 1/2: `~/.gemma4/timeline/<sid>-turn<NNN>.jsonl`. Per-turn-per-session, append-only, sin rotación. Suma a la duplicación (TraceLogger + LogRecorder/full + LogRecorder/chat + Timeline = **4 sinks**).
- **`state.json` con 360 routines** persistidas: probable bloat por routines de test/dev no purgadas.
- **Schema drift en experience.sqlite**: 5 `ALTER TABLE` ad-hoc post-launch sin migration framework.

### MED
- **27 `pending_action` resources `open` en state.json** — confirmations que el usuario nunca aprobó/rechazó. Memory leak conceptual.
- **`gui.json` y `profiles.json` sin schema/version** — si la UI cambia el contrato, el archivo viejo no se migra.
- **`profiles.json` actualmente `{}`** — feature "user customiza profiles" sin uso real → 200+ LOC de overrides candidatas.
- **`knowledge.sqlite` está vacío** — verificar si feature se usa.

### LOW
- **`captures/` y `data/generated/` dentro del package** — outputs en mismo dir que código (van a aparecer en git status). Mover a `~/.gemma4/`.
- **`backups/*.zip` y `jobs/*.log` sin TTL ni cap**.
- **`memory.json` con solo 3 items** — feature subutilizada vs ExperienceMemory.
- **AppResolver cachea a `~/.gemma4/cache/app_inventory.json`** — verificar TTL.

## Hallazgos nuevos de Fase 6 (grafo de dependencias)

### Negativos (positivos = nada que arreglar)
- **0 ciclos de import detectados** — el equipo logró grafo acíclico vía lazy imports liberales. Buena propiedad estructural a preservar.
- **0 módulos de código muerto reales**. Los 4 falsos positivos de Fase 0 (`verifiers`, `telemetry`, `ui.panels`, `ui.metrics`) quedaron descartados con scanner mejorado. **No hay LOC para borrar por estar huérfanos.**

### Positivos (cosas que sí valen actuar)
- **Ratio lazy:eager = 1.18** (177 lazy vs 150 eager). Grafo defensivo. Cada lazy disfraza el grafo estático real.
- **`agent.py` re-importa `planner`, `reasoning`, `tools` tanto EAGER al top-level COMO LAZY adentro de métodos**. Redundancia. LOW.
- **`test_gx_features.py` importa 43 módulos lazy** — el test gigante 2 666 LOC trae todo el repo. Si se divide en tests focados, cada uno trae solo lo suyo.
- **God modules confirmados:** `agent` (21 in), `config` (21), `domain_tools` (20), `state` (20). Tocar cualquiera requiere validar cascadas.

## Próximos pases (a ejecutar en Fases 2-8)

- Greps a hacer durante Fase 2-6:
  - `\bexcept[: ]\s*pass` para tragones de excepciones
  - `# TODO|# FIXME|# XXX|# HACK` para deuda explícita
  - `^\s*#\s*[a-zA-Z_]+\(` y similares para código comentado
  - Funciones con `def foo(a, b, c, d, e, f` o más argumentos
  - `class \w+\(\w+\):` para encontrar herencia y luego contar subclases
  - `importlib`, `__import__`, `getattr(.*,\s*['"]` para carga dinámica que pueda salvar huérfanos
