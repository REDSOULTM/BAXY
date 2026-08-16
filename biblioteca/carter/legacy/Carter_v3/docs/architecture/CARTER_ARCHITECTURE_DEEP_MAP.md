# CARTER_ARCHITECTURE_DEEP_MAP.md
# Carter v3 — Mapa Profundo de Arquitectura
# Generado por: Claude Code (claude-sonnet-4-6) — 2026-05-06

---

## Diagrama de flujo textual del turn loop

```
User input (texto)
  │
  ├─→ [PRE-LLM] PolicyEngine.classify_input()
  │         Si bloqueado → compose_policy_block_reply() → guards → output
  │
  ├─→ [PRE-LLM] Session state: ¿hay pending_memory_offer, pending_tool_approval, pending_intent?
  │         Si sí + input es confirmación → ejecutar acción deferida → skip LLM
  │
  ├─→ IntentClassifier.classify()
  │         → trivial_lowinfo / ambiguous_short / compound_action / question / potential_action
  │
  ├─→ synthesise_structural_tool_calls()  [fast lane sin LLM]
  │         clock → memory_save/recall → URL → app_open → web_search → screenshot → volume → filesystem → terminal
  │         Si match → saltar LLM, ir a ejecución directa
  │
  ├─→ ResourceResolver.resolve()  [fuzzy match vs procesos/ventanas/apps instaladas]
  │
  ├─→ PerceptionRouter.decide()  [INTERNAL/PROCESS/WINDOW/SYSTEM_API/WEB/SCREENSHOT/OCR/VLM]
  │
  ├─→ select_tools()  [hasta 16 tools, ordenadas por preferencia]
  │
  ├─→ build_messages()  [system_prompt + últimas 6 turns + user_input]
  │
  ├─→ call_llm()  [Ollama/OpenAI-compat/OpenAI API, timeout 60s]
  │         → AdapterResponse { text, tool_calls, thinking }
  │
  ├─→ tool_call_parser.parse()  [4 formatos: native/tagged/fenced/bare JSON]
  │
  ├─→ _materialise_steps()  [hasta 6 steps, step_budget]
  │
  ├─→ Loop de steps (hasta step_budget=6):
  │     ├─ PolicyEngine.classify_tool()  [DANGEROUS_PATTERNS en argumentos]
  │     ├─ SecretFilter en memory_save
  │     ├─ ToolDispatcher.dispatch()
  │     ├─ VerificationManager.verify()  [14 verifiers]
  │     ├─ maybe_retry_app_open()  [1 retry si PENDING/UNVERIFIABLE]
  │     └─ TurnTrace.emit()
  │
  ├─→ Fallback chains si no ejecutó tools:
  │     synthesised_action → prior_web_target → prior_reopen_match → prior_deictic_match
  │
  ├─→ compute_mission_status()  [estructural, LLM no vota]
  │
  ├─→ response_composer.compose_default_reply()  [scaffold factual determinista, en español]
  │
  ├─→ llm_verbalizer.generate_result_reply()  [LLM secundario, 20s, read-only sobre hechos]
  │
  ├─→ run_reply_guards()  [8 guards: placeholder, low_info, fake_success, overclaim, contamination, corrupt, script_mismatch, memory_echo]
  │         Si violación → fallback_for_guards()
  │
  └─→ session_state.record_*()  → output al usuario
```

---

## Tabla de componentes

| Componente | Archivo(s) | Rol | Fortalezas | Debilidades | Riesgo | Qué debería mejorar |
|---|---|---|---|---|---|---|
| **AgentEngine** | `agent.py` (~1100 líneas) | Control loop principal. Orquesta todo el turn de principio a fin. | Pipeline estrictamente ordenado. Pre-LLM policy. Step budget. Multi-layer fallback. | Monolito de 1100 líneas. Fallback chains en if-chains profundas. | MEDIO | Extraer fallback logic a módulo separado. Agregar progress reporting entre steps. |
| **Turn loop** | `agent.py:run_turn()` | Un turno completo input→output. | Orden fijo, predecible, determinista. | Sin streaming intermedio al usuario durante steps. | ALTO | Progress emits al usuario entre steps. |
| **Tool calling** | `adapters/tool_call_parser.py` | Parsea 4 formatos de tool calls de la respuesta LLM. | 4 formatos robustos. `<think>` stripping. Allowed_tools gate. | Si el LLM mezcla formatos en una respuesta, solo el primer match gana. | BAJO | OK como está. |
| **LLM adapters** | `adapters/ollama_adapter.py`, `openai_api_adapter.py`, `openai_compat_adapter.py`, `scripted_adapter.py` | Abstracción de distintos backends LLM. | Protocol-based (structural typing). Availability check via TCP. Preload support. | Solo Ollama tiene streaming desactivado explícitamente. max_output_tokens cap de 256 puede truncar respuestas largas. | MEDIO | Agregar timeout per-adapter configurable. |
| **Tool parser** | `adapters/tool_call_parser.py` | Universal parser para 4 formatos. | Robusto. Alias normalization. Thinking stripping. | Un solo parse por response — multi-tool nativo no soportado en json_schema mode. | BAJO | OK. |
| **Request patterns** | `request_patterns.py` (~584 líneas) | Extracción estructural de señales del input (URL, path, app target, deictic, clock). | Sin keyword-based routing. URL extractor maneja edge cases. Prioridad clara en synthesise. | `synthesise` retorna en primer match — puede priorizar URL sobre búsqueda. TERMINAL regex muy estrecho. | MEDIO | Expandir TERMINAL_INVOKE. Revisar order de synthesis. |
| **Intent classifier** | `resolvers/intent_classifier.py` | Clasifica input en kind estructural. Zero keyword lists. | Puramente estructural (tokens, punctuation, glyphs). Sin routing semántico. | "Abre Notepad y ciérralo" puede no clasificar como compound_action (4-5 tokens). | MEDIO | Ampliar threshold de compound_action. |
| **Session state** | `session_state.py` (~461 líneas) | TTL-based ephemeral state per turn. | TTL evita stale context. SHA-1 dedup para memory offers. Language-aware confirmation. | "Sí"/"OK"/"YES" no pasan _short_same_language_nonsecret (bug B2). No persiste cross-restart. | ALTO | Fix B2. Evaluar si sesión necesita persistencia básica. |
| **Memory** | `memory/store.py`, `declarative_detector.py` | SQLite con secret filter y dedup. Detector heurístico para facts declarativos. | Secret filter pre-write. Soft-delete (superseded). dedup_window. | Máximo 8 facts en snapshot para verbalizer. Historia silenciosamente truncada. | BAJO | Aumentar snapshot limit o hacer configurable. |
| **Local reminders** | `tools/local_reminders.py` | SQLite local para recordatorios. | Verificación real post-create (re-read). | Solo parsea ISO, offset relativo, y HH:MM. "Mañana a las 3" no parsea. NO notificación OS. | MEDIO | Ampliar parsers de fecha. Documentar que NO es sistema de OS. |
| **Policy/guards** | `security/policy.py`, `guards.py` | PolicyEngine pre-LLM + 8 guards post-reply. | 20+ dangerous patterns. Bilingüe. Arguments re-scanned. Guards cubren 8 dimensiones. | fake_success_guard solo cubre inicio del reply. notify_toast CONFIRMED sin verificación visual. reboot en inglés solitario puede no bloquear. | ALTO | Fix B3 (fake_success mid-text). Fix B4 (notify_toast→SKIPPED). Agregar `\bshutdown\b` a patterns. |
| **Verifier** | `tools/verifier.py` (~693 líneas) | Post-action readback para cada tool. 14 verifiers. | Causal baseline para app_open. Volume readback real (±5 tolerance). filesystem SHA-256. local_reminder re-read. | notify_toast usa synchronous_ok (bug B4). terminal sin exit_code → UNVERIFIABLE. Solo 1 retry en app_open. | ALTO | Fix B4. Generalizar retry a web_open y volume. |
| **Response composer** | `response_composer.py` (~358 líneas) | Scaffold factual determinista, sin LLM. | Basado en evidencia pura. Handles all tool outcomes. Casos de preexisting/already_absent. | Strings hardcoded en español. Añadir new tool requiere nueva branch. Magic numbers de truncado (180/220 chars). | MEDIO | Internacionalización o parametrización del idioma. |
| **LLM Verbalizer** | `llm_verbalizer.py` (~295 líneas) | LLM secundario hace reply natural a partir del scaffold. | Read-only sobre hechos. Constraints por-turn. Fallback a draft si retorna basura. | Segunda llamada LLM por turn = doble latencia. Max 8 facts en snapshot. JSON payload no tiene budget de tokens. | ALTO | Evaluar si verbalizer es necesario para todos los turns o solo para turns complejos. |
| **Recovery** | `recovery.py` (22 líneas) | Un solo retry para app_open con PENDING/UNVERIFIABLE. | Minimal. Bounded (1 retry, 0.5s, solo LOW/MEDIUM risk). | Solo cubre app_open. Bloquea el thread 0.5s. Puede re-abrir si primera apertura fue exitosa pero lenta. | BAJO | Generalizar a web_open y volume. Considerar async retry. |
| **Perception ladder** | `perception/ladder.py` | Mapea intent a nivel de percepción (0=INTERNAL, 7=VLM). | Cheapest viable perception. VLM nunca es default. | Umbral entre INTERNAL y PROCESS puede estar mal calibrado para algunos intents. | MEDIO | Auditar calibración en spotcheck. |
| **App resolver** | `perception/app_resolver.py` (~386 líneas) | Inventario Windows de apps instaladas (Get-StartApps + Registry + Start Menu). | TTL cache 300s. Tres fuentes. NFKD normalization. Zero aliases. | Primera llamada cuesta 200-800ms (PowerShell subprocess). AppsFolders vs Win32 heuristics pueden fallar con nombres cortos. | MEDIO | Pre-warm al inicio del agente. |
| **Resource resolver** | `resolvers/resource_resolver.py` (~206 líneas) | Fuzzy matching de target vs procesos/ventanas/apps instaladas. | Composite score: substring + SequenceMatcher + Levenshtein. Auto-adjusts cutoff para targets cortos. | Requiere rapidfuzz opcional (fallback es más lento). Puede fallar con typos ≥3 chars en nombres cortos. | BAJO | OK. Asegurar rapidfuzz en producción. |
| **Observation/UIA** | `perception/observation.py`, `uia_probe.py`, `ocr.py` | Screen observation data contract + UIA probe + OCR fallback. | Frozen dataclass. Source validation. opt-in UIA. | Sin VLM integrado. OCR es fallback básico. UIA puede ser lento con pywinauto. | MEDIO | Documentar claramente cuándo UIA está disponible vs cuando falla. |
| **Model registry/selector** | `models/registry.py`, `selector.py` | Carga profiles de modelos. Selección por perfil, sin if-model-name. | Pure function. External API gate (consent). VRAM 85% rule. | ModelRegistry falla silenciosamente si YAML mal formado. selector retorna None si ningún modelo cumple criterios. | BAJO | Agregar log de advertencia si selector retorna None. |
| **Config** | `config.py` | Carga configuración del sistema. | (No auditado en detalle en esta sesión) | | | |
| **Heartbeat** | `heartbeat.py` | Watcher de progreso del turn. | (No auditado en detalle en esta sesión) | | | |
| **CLI** | `cli/` | Interfaz de línea de comando. | (No auditado en detalle en esta sesión) | | | |
| **Test harness** | `tests/` (~30 archivos, 490 tests) | Suite de tests con ScriptedAdapter. | 30 archivos de tests. hardcode_guard en AST real. | No ejercita LLM real. live-safe-all bloquea side effects. | CRÍTICO | Agregar tests live mínimos con LLM real offline (Ollama). |

---

## Fortalezas arquitectónicas únicas de Carter

1. **"Structural evidence beats LLM text"** — compute_mission_status y verifier son 100% deterministas.
2. **Pre-LLM policy** — el engine nunca llama al LLM si la entrada es peligrosa.
3. **8-guard post-reply sweep** — fake success, contamination, script mismatch bloqueados estructuralmente.
4. **Zero hardcodes** verificados por hardcode_guard en AST real.
5. **Causal baseline en app_open verifier** — no acepta procesos preexistentes como prueba de apertura.
6. **TTL session state** — sin context leakage entre turns sin relación.
7. **ModelCapabilityProfile** — selector sin if-model-name, extensible por YAML.

## Debilidades arquitectónicas actuales

1. **Doble LLM call por turn** (planner + verbalizer) → 2x latencia en Ollama local.
2. **ScriptedAdapter-only tests** → 490 tests no prueban el LLM real.
3. **Sin progress reporting** en el loop de steps → silencio hasta que termina.
4. **response_composer en español hardcodeado** → no realmente multilingual en capa de composición.
5. **Session state no persiste** → restart pierde pending offers, approvals, owned paths.
6. **recovery.py solo cubre app_open** → web_open, volume no tienen retry.
7. **agent.py monolito** → 1100 líneas con fallback chains anidadas, difícil de testear en aislamiento.
