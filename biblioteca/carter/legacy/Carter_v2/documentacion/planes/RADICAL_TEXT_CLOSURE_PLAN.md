# RADICAL TEXT CLOSURE PLAN — Carter v2 / RP2

**Fecha:** 2026-04-30
**Branch sugerida:** `radical/text-closure`
**Estado:** PROPUESTA (read-only). NO se ha modificado código. Espera aprobación antes de ejecutar.
**Base:** [PHASE_INTEGRATION_DELIVERY.md](PHASE_INTEGRATION_DELIVERY.md) + [Auditoria30/04.md](../Auditoria30/04.md).

---

## 0. Filosofía

Cierre **radical** del modo texto, no parche. Pero **controlado**: cada cambio
con evidencia, test que lo proteja, y rollback de un commit. Sin hardcodes
nuevos por frase, app, marca, personaje o idioma. Si una lista ES/EN sale, no
entra otra ES/EN/PT/FR — entra una regla **estructural** o se delega al LLM.

Reglas operativas vinculantes en este plan:

1. No hardcodes por frases / apps / marcas / personajes / idiomas.
2. No hacks (no `try/except: pass` nuevos, no flags ocultos).
3. No borrar código sin evidencia documentada (grep + tests verdes).
4. No mega-diff: cada subfase es un commit autocontenido.
5. Si un test protege comportamiento viejo, se actualiza junto al cambio
   (mismo commit) y se documenta el motivo en el commit message.
6. Si algo es riesgoso, se divide en subfases con gates intermedios.
7. **Smoke runtime real con Qwen + `CARTER_TIMING=1`** después de cada
   bloque mayor (F8, F-A1, F-A2, refactor, prompt diet).

---

## 1. Estado actual reconstruido (read-only)

### 1.1 Lo que sí está cerrado (verificado en código)

| Área | Evidencia |
|---|---|
| TURN_TRACE timing | [agent.py](src/carter_v2/turn/agent.py) `_timing` dict + `CARTER_TIMING=1`; tests `test_agent_turn_trace.py`. |
| A11 multilingüe básico | [brain_router.py](src/carter_v2/turn/brain_router.py#L61) `_GREETING_TOKENS` extendido a quien/qui/quem/wer/chi/你是谁; identity guard + `system_get_time` desc reforzada. |
| MAX_TOOL_ITERATIONS | bajado a 8 en [agent.py](src/carter_v2/turn/agent.py). |
| Probe TTL | `_DEFAULT_TTL=300` + `CARTER_PROBE_TTL` env. |
| MEMORY.md saneado | [MEMORY.md](MEMORY.md) hoy contiene 2 líneas legítimas; backup en `MEMORY.md.bak.20260430-190222`. |
| run_carter_gpu.ps1 | vision/chat split correcto (`Remove-Item Env:CARTER_LLM_*` + `CARTER_VISION_LLM_*` aparte). Ver [run_carter_gpu.ps1](../run_carter_gpu.ps1). |
| A3 json.loads | try/except con fallback `{"__raw__":..., "__parse_error__":True}`. |
| Memory hardening | `_PROMOTION_BLOCKLIST`, `_is_promotable_candidate`, `set_user_name` estructural, `RLock` compartido. |

### 1.2 Lo que sigue abierto (deuda real, no rumor)

| ID | Deuda | Evidencia |
|---|---|---|
| F8.a | `_PERSONAL_MEMORY_PHRASES` ES/EN | [invariants.py](src/carter_v2/turn/invariants.py#L23) — 12 frases hardcoded. |
| F8.b | `_IP_LOCAL_PHRASES`, `_IP_PUBLIC_PHRASES` ES/EN | [invariants.py](src/carter_v2/turn/invariants.py#L40) — listas locales. |
| F8.c | `_CALENDAR_INTENTS` ES/EN | [invariants.py](src/carter_v2/turn/invariants.py#L50) — verbos hardcoded. |
| F8.d | `_VOLUME_DIRECTION_PHRASES`, `_EXPLICIT_MUTE_PHRASES` ES/EN | [invariants.py](src/carter_v2/turn/invariants.py#L62-L70). |
| F8.e | `_LIVE_SCREEN_PHRASES` ES/EN | [invariants.py](src/carter_v2/turn/invariants.py#L72). |
| F8.f | `_GIT_INTENT_PATTERNS` ES/EN | [invariants.py](src/carter_v2/turn/invariants.py#L57). |
| F8.g | `_LIVE_QUERY_MARKERS` ES/EN en agent.py | [agent.py](src/carter_v2/turn/agent.py) líneas ~887-915. |
| F8.h | `_PERSONAL_MEMORY_QUERY_MARKERS` ES/EN | [agent.py](src/carter_v2/turn/agent.py) ~916-930. |
| F8.i | `_ACTION_QUESTION_PREFIXES` ES/EN | [agent.py](src/carter_v2/turn/agent.py) ~873-885. |
| F8.j | `_GREETING_TOKENS` aún tiene tokens ES/EN/PT/FR explícitos | [brain_router.py](src/carter_v2/turn/brain_router.py#L61). |
| F8.k | System prompt contiene ejemplos en español ("¿qué hora es?", "abre Notepad", etc.) | [agent.py](src/carter_v2/turn/agent.py) `_SYSTEM_PROMPT_TEMPLATE`. |
| A1 | `process_stop_app` → `taskkill /IM <name> /F` directo, sin paso cooperativo. | [process.py](src/carter_v2/capabilities/process.py#L216). |
| A2 | `_env_set` escribe winreg sin policy gate y sin `WM_SETTINGCHANGE`. | [system.py](src/carter_v2/capabilities/system.py#L924-L937). |
| Refactor | `agent.py` = 3194 LOC, `AgentEngine.run()` ~700 líneas. | wc / grep. |
| Universal/vision/gui | sin clasificación CORE/KEEP_LAZY/OFF_BY_DEFAULT/DELETE; corre en cada turno via `_format_universal_skill_context`, `_resource_resolver_from_probe`, `_format_vision_capability_status`. |
| Tool catalog contextual | 242 tools cargadas en cada turno; gating sólo por `hint_no_tools`. |
| Honestidad contextual | `app_open` Popen sin verificar PID vivo; `gui_do` reporta éxito sin `verified_outcome`. |
| Prompt diet | template ~145 líneas con 7000+ chars y ejemplos por marca; sin top-K ni cache real. |
| Memoria durable | aún sin file lock cross-process; `_lt_context_cache` con check-then-use; `proactive.py:553` y `memory.py:643` no comparten lock entre threads de procesos distintos. |
| Smoke runtime Qwen real | `probe_text_hardening.py` requiere Ollama, pero el stack es llamacpp; no hay smoke estable contra el backend de prod. |

---

## 2. Plan radical por fases

Cada fase es independiente, mergeable y revertible. Orden propuesto por
dependencia + riesgo creciente.

---

### F0 — Baseline congelada y safety net

**Objetivo:** asegurar que cualquier cambio se mide contra una línea base reproducible.

**Subfases:**

- F0.1 Crear branch `radical/text-closure` desde el estado actual (post Stage-2).
- F0.2 Snapshot de tests verdes: `pytest -q --ignore=tests/test_main_jarvis.py` → guardar conteo y duración en `audit/F0_baseline_tests.json`.
- F0.3 Snapshot del system prompt actual: dump de `_SYSTEM_PROMPT_TEMPLATE` y de un build real con memory+deps a `audit/F0_prompt_dump.txt` (para comparar tras prompt diet).
- F0.4 Smoke runtime con `CARTER_TIMING=1` × 6 turnos:
  - "hola"
  - "quien eres"
  - "que hora es"
  - "cuál es mi IP"
  - "abre Notepad y luego ciérralo"
  - "qué recuerdas de mí"
  Capturar `last_turn_trace["_timing"]` por turno → `audit/F0_smoke.json`.
- F0.5 Snapshot de `MEMORY.md` y de `MEMORY.md.bak.*` → `audit/F0_memory.snapshot`.

**Test gate:** baseline existe, reproducible.
**Rollback:** N/A.

---

### F1 — Refactor modular progresivo de `agent.py` (sólo splits seguros)

**Objetivo:** bajar `agent.py` de 3194 LOC a ≤ 800 LOC en `agent_engine.py`,
sin mega-diff, manteniendo la API pública (`AgentEngine.run`,
`AgentResponse`, helpers exportados).

**Restricción crítica:** F1 NO cambia comportamiento. Sólo mueve símbolos.

**Subfases (cada una un commit, todos los tests verdes entre commits):**

- F1.1 `turn/agent_response.py`: mover `AgentResponse`, `_strip_thinking_text`,
  `_strip_think_chunk`, `_textual_tool_calls`, `_tool_call_from_json`,
  `_sanitize_reply`. Re-exportar desde `agent.py` (`from .agent_response import *`).
- F1.2 `turn/agent_prompt.py`: mover `_SYSTEM_PROMPT_TEMPLATE`,
  `_SYSTEM_PROMPT_CACHE`, `_build_system_prompt`, `_format_memory_facts`,
  `_format_recent_alerts`, `_format_runtime_deps`,
  `_format_vision_capability_status`, `_format_prior_turn_context`,
  `_format_universal_skill_context` helpers.
- F1.3 `turn/agent_active_app.py`: mover `_active_app_context_line`,
  `_active_app_context`, `_active_app_followup_*`,
  `_should_reconsider_active_app`, `_resource_text_spans`,
  `_span_is_explicit_switch`, `_mentions_explicit_resource_switch`,
  `_looks_like_short_followup`, `_resource_resolver_from_probe`.
- F1.4 `turn/agent_classifiers.py`: mover (TEMPORALMENTE) los
  `_LIVE_QUERY_MARKERS`, `_PERSONAL_MEMORY_QUERY_MARKERS`,
  `_ACTION_QUESTION_PREFIXES` y sus `_looks_like_*`. Esto los aísla para
  borrarlos en F8 sin tocar agent_engine.
- F1.5 `turn/agent_backends.py`: mover `OpenAICompatAgentBackend`,
  `NullAgentBackend`, `_auto_backend`, `_try_start_ollama`, `_tcp_probe`,
  `_post_ollama_native`.
- F1.6 `turn/agent_retry.py`: mover `_retry_tool_hint`,
  `_should_accept_text_only_first_pass`, `_is_trivially_short_input`,
  `_is_low_information_text_reply`, `_active_app_gui_fallback_response`.
- F1.7 `agent.py` queda con `AgentEngine`, su `run()`, y los hooks
  estrictamente acoplados al loop. Meta: ≤ 800 LOC.

**Test gate:** todos los tests pre-existentes pasan en cada commit. Diff por
commit ≤ 600 LOC neto, mayoritariamente moves.
**Rollback:** revert por commit individual.
**Riesgo:** MEDIO — riesgo de imports circulares; mitigado con re-export shim
en `agent.py`.

---

### F8 — Eliminación radical de hardcodes multilingües (sin reemplazo lingüístico)

**Objetivo:** retirar TODA lista de frases ES/EN/PT/FR de routing y dejar
sólo **reglas estructurales** verificables (longitud, signos, tokens del
shell, patrones de tool-call) o delegar al LLM con un prompt corto.

**Principio:** si quitar X rompe un test, el test cambia para validar la regla
estructural nueva, NO para reintroducir el hardcode.

**Subfases:**

- F8.1 `_GREETING_TOKENS` → eliminar. Reemplazo en `_is_pure_conversational`:
  - regla estructural única: `len(tokens) ≤ 4 AND no '?' AND no '/' AND
    no URL-shape AND no shell-shape AND no dígito-operador`.
  - aritmética conserva su detección regex (estructural, no léxica).
  - tests `test_brain_router_*` se actualizan para verificar la regla
    estructural sobre los mismos casos (saludos cortos, identidad corta,
    "ok", "thanks", "gracias").
- F8.2 `_PERSONAL_MEMORY_PHRASES` (invariants.py) → eliminar.
  - El invariant de redirect a memory_recall pasa a depender SÓLO del
    tool_call observado (`memory_*`) + del catálogo: si el modelo NO llamó
    memory pero el catálogo no tiene memory disponible, no redirige. La
    decisión léxica vuelve al LLM.
  - Eliminar `_invariant_personal_memory_redirect` por completo si los
    tests demuestran que el LLM resuelve "qué sabes de mí" correctamente
    en ES/EN/PT/FR (smoke F8.S1).
- F8.3 `_IP_LOCAL_PHRASES`, `_IP_PUBLIC_PHRASES` → eliminar.
  - El invariant IP redirect pasa a estructural: sólo dispara si
    `tool_call ∈ memory_*` AND el user_text contiene **token "IP"**
    (case-insensitive, palabra completa) — un símbolo técnico universal,
    no una frase localizada. "public" / "local" se delega al LLM.
- F8.4 `_CALENDAR_INTENTS` → eliminar. El invariant calendar redirect
  pasa a depender SÓLO del shape: si el modelo llamó `notify_*` y NO
  hay calendar_* en el catálogo presentado, no redirige; si hay
  calendar_* y el modelo eligió notify_*, redirige basado en heurística
  de tool-shape, no de palabras.
- F8.5 `_VOLUME_DIRECTION_PHRASES`, `_EXPLICIT_MUTE_PHRASES` → eliminar.
  El invariant volume_direction redirect se vuelve estructural: si
  `tool_call=system_mute` AND `user_text` no contiene los tokens
  estructurales `mute|silenc*` Y SI no contiene número/porcentaje →
  reemplazar invariant por **descripción reforzada** del tool en el
  catálogo + delegar al LLM. (Aceptamos perder este micro-invariant si
  el smoke F8.S2 muestra que el LLM acierta ≥95%.)
- F8.6 `_LIVE_SCREEN_PHRASES` → eliminar. El invariant `live_query_redirect`
  se reemplaza por: si `tool_call ∈ memory_*` AND `user_text` contiene
  el caracter `?` o termina en signo interrogativo → el LLM decidirá en
  segundo pase con `tools=[]`; si el LLM no produce respuesta, fallback
  honesto "no tengo evidencia suficiente". Sin lista de palabras.
- F8.7 `_GIT_INTENT_PATTERNS` → eliminar. Reemplazo: el invariant git
  redirect dispara SÓLO cuando el modelo llamó `gui_do/web_*` Y el
  user_text contiene el token estructural `git` (palabra completa).
  El verbo (`status`, `log`, `diff`) se delega al LLM eligiendo el
  `code_git_*` correcto vía descripción del catálogo.
- F8.8 `_LIVE_QUERY_MARKERS` (agent.py) → eliminar. La condición
  "no aceptar text-only first-pass para live queries" se reemplaza por:
  "no aceptar si el modelo retornó tool_calls vacío Y el catálogo
  presentado contenía system_get_time/network_get_ip/etc Y el user_text
  contiene `?`". Sin frases.
- F8.9 `_PERSONAL_MEMORY_QUERY_MARKERS` (agent.py) → eliminar. Misma
  lógica estructural que F8.8: el LLM decide; honestidad como fallback.
- F8.10 `_ACTION_QUESTION_PREFIXES` → eliminar. Reemplazo: detección de
  "acción request" se basa SÓLO en presencia de `?` final + verbo
  imperativo identificado por el LLM (no por lista de prefijos).
- F8.11 `_SYSTEM_PROMPT_TEMPLATE` ejemplos en español → eliminar (se
  cubre completo en F-PROMPT). Aquí sólo borrar los ejemplos
  literales `"¿qué hora es?"`, `"abre Notepad"`, `"borra todos los
  archivos del sistema"` y dejar la **regla** ("Only call X when the
  user explicitly asks for current time, in any language") sin
  ejemplos por idioma.

**Test gate F8:**
- Suite de tests existente actualizada (los que validaban listas
  hardcoded pasan a validar la regla estructural).
- Nuevo test `test_no_hardcoded_phrase_lists.py` que falla si alguien
  re-introduce una constante con `tuple/frozenset` de strings de >2
  palabras en cualquier `turn/*.py` o `capabilities/*.py`.
- Smoke F8.S1: probe con "qué sabes de mí", "what do you know about me",
  "o que sabes de mim", "que sais-tu de moi", "was weißt du über mich"
  → cada uno llama exactamente a `memory_recall` o responde honestamente
  desde KNOWN FACTS.
- Smoke F8.S2: probe con "baja el volumen", "lower the volume", "abaixa o
  volume", "baisse le volume" → cada uno llama `system_set_volume` con
  delta negativo o `system_get_volume` primero, no `system_mute`.

**Rollback:** F8 está dividido en 11 commits independientes. Si F8.5 falla
en smoke, revert sólo de F8.5 deja el resto intacto.
**Riesgo:** ALTO. Sin smoke real con Qwen, NO se mergea.

---

### F-A1 — Cierre cooperativo de procesos (antes de `taskkill /F`)

**Objetivo:** que `process_stop_app` deje de ser un kill -9 instantáneo.
Cooperativo primero, forzado sólo si el cooperativo falla.

**Diseño (sin hardcodes por app):**

1. Añadir helper estructural `process_stop_cooperative(image_name, timeout_s)`
   en `capabilities/process.py`:
   - Paso 1: enumerar PIDs por `psutil.process_iter` que matcheen
     `image_name` exacto (no fuzzy).
   - Paso 2: para cada PID con ventana visible (vía `pywin32`
     `EnumWindows` filtrado por GetWindowThreadProcessId), enviar
     `WM_CLOSE` (`win32gui.PostMessage(hwnd, WM_CLOSE, 0, 0)`).
   - Paso 3: para cada PID sin ventana, intentar `proc.terminate()`
     (envía CTRL_BREAK en Windows si es console, o señal cooperativa).
   - Paso 4: esperar `timeout_s` (default 5s, configurable
     via `CARTER_PROCESS_STOP_TIMEOUT`, sin hardcode por app).
   - Paso 5: re-enumerar; PIDs que sobrevivieron pasan a fase forzada.
2. Modificar `_stop_app(name)`:
   - Llama primero `process_stop_cooperative(resolved, timeout_s)`.
   - Si todos los PIDs murieron → `ok=True`, evidence
     `{"method":"WM_CLOSE","pids_closed":[...]}`.
   - Si quedan PIDs → invocar `taskkill /IM <name> /F` SÓLO sobre
     esos PIDs específicos (`/PID <pid> /F`), nunca sobre image-name
     entero. Evidence `{"method":"taskkill_force","pids_killed":[...]}`
     y honestidad: `message="App stopped: <name> (cooperative timeout
     exceeded; forced N pids)"`.
3. Capability surface: `process_stop_app` añade param opcional
   `force_after_s: int | None = None` (default = settings). Si user
   explícitamente pide "force kill" / "kill -9" → policy gate eleva el
   risk a `high` y requiere aprobación si `CARTER_AUTO_APPROVE_HIGH=0`.

**Subfases:**

- F-A1.1 Helper `process_stop_cooperative` puro + tests unitarios
  (mock psutil + win32gui).
- F-A1.2 `_stop_app` orquesta cooperativo → forzado.
- F-A1.3 Update tool descriptions in `adapters/tools.py`:
  `process_stop_app` description menciona "tries graceful close
  first, escalates to force only if process refuses".
- F-A1.4 Update tests: `test_capabilities_process.py` añade caso
  cooperativo exitoso, caso cooperativo timeout → forzado, caso
  cooperativo total (no PIDs sobreviven, sin force).

**Test gate:** unitarios verdes; smoke real F-A1.S1: abrir Notepad,
pedir "cierra Notepad", verificar que el ledger registra
`method=WM_CLOSE`. Abrir un proceso "sin ventana" (servicio dummy),
pedir cierre, verificar fallback a `proc.terminate`.
**Riesgo:** MEDIO. Notepad con cambios sin guardar se queda colgado en
diálogo "guardar?". Eso es comportamiento correcto cooperativo —
el plan documenta que es la respuesta esperada, no un bug.
**Rollback:** revert F-A1.2 vuelve al `taskkill /F` original.

---

### F-A2 — Persistencia de env vars con policy gate + WM_SETTINGCHANGE

**Objetivo:** que `system_env_set(name, value, persist=True)` deje de
ser una bomba sobre el registro del usuario.

**Diseño:**

1. Whitelist estructural (no por nombre de app, sino por superficie
   técnica):
   - PERMITIDO sin elevación: cualquier nombre que NO esté en una
     blocklist de variables del sistema (`PATH`, `PATHEXT`,
     `ComSpec`, `SystemRoot`, `windir`, `TEMP`, `TMP`,
     `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `PROGRAMDATA`,
     `PROGRAMFILES`, `PROGRAMFILES(X86)`, `OS`, `NUMBER_OF_PROCESSORS`).
   - REQUIERE flag explícito `allow_system_var=True` + policy `critical`
     si está en la blocklist.
2. Validación de `value`:
   - Para cualquier var ya existente que contenga `;` (PATH-like),
     prohibir sobre-escritura completa por defecto. Param
     `mode: Literal["set", "prepend", "append"] = "set"`. `prepend`/`append`
     editan respetando el delimitador. `set` con valor que destruya
     PATH existente → policy `critical`.
3. Después del `winreg.SetValueEx`, **broadcast**
   `WM_SETTINGCHANGE` para que procesos nuevos vean el cambio sin
   reboot:
   ```python
   import ctypes
   HWND_BROADCAST = 0xFFFF
   WM_SETTINGCHANGE = 0x001A
   SMTO_ABORTIFHUNG = 0x0002
   res = ctypes.c_long()
   ctypes.windll.user32.SendMessageTimeoutW(
       HWND_BROADCAST, WM_SETTINGCHANGE, 0,
       "Environment", SMTO_ABORTIFHUNG, 5000, ctypes.byref(res),
   )
   ```
   Si la llamada falla (RPC, hung), se reporta honestamente
   `evidence.broadcast_ok=False` y se sugiere relogin.
4. Evidence siempre completo:
   `{"name", "value_len", "scope":"user", "mode", "broadcast_ok",
   "previous_value_present"}`.
5. Lectura: `system_env_get` ya existe; añadir param
   `scope: Literal["process","user","machine"] = "process"` (default
   = lectura process — compatible con uso actual). Para `user` lee
   `winreg HKCU\Environment`; para `machine` lee
   `HKLM\SYSTEM\...\Environment` (sólo lectura, set en machine
   queda fuera de alcance — no es necesidad del plan).

**Subfases:**

- F-A2.1 Helper `_persist_user_env(name, value, mode)` con whitelist
  + WM_SETTINGCHANGE.
- F-A2.2 `_env_set` orquesta validación + helper.
- F-A2.3 Tool description en `adapters/tools.py`: documentar `mode`,
  `allow_system_var`, riesgo de PATH.
- F-A2.4 Tests `test_capabilities_system_env.py`: prepend a PATH,
  set var nueva, intento sobre PATH sin `allow_system_var` → falla
  con mensaje honesto, broadcast mockeado.

**Test gate:** unitarios + smoke F-A2.S1: setear `CARTER_TEST_VAR=hello`
con persist, abrir cmd nuevo, verificar `echo %CARTER_TEST_VAR%` retorna
`hello`. Limpiar al final.
**Riesgo:** MEDIO. Cualquier bug aquí daña el registro del usuario.
Por eso la blocklist y el modo `prepend` son estrictos.
**Rollback:** revert + manual cleanup de la var de test.

---

### F-CLASSIFY — Clasificación universal/vision/gui

**Objetivo:** dejar explícito en el código y en docs qué módulos son
CORE, KEEP_LAZY, OFF_BY_DEFAULT y DELETE para el modo texto.

**No borra nada en esta fase.** Sólo etiqueta y mide. Las eliminaciones
suceden en F-DELETE tras dos sesiones de smoke verde.

**Subfases:**

- F-CLASSIFY.1 Auditar imports reales:
  - script `audit/scan_universal_imports.py` que lista cada símbolo
    importado de `..universal.*`, `..capabilities.vision*`,
    `..capabilities._gui_planner`, `..capabilities.gui_agent` desde
    `turn/*.py` y mide cuántos turnos del smoke F0.4 lo activan.
  - Output → `audit/F-CLASSIFY_imports.json`.
- F-CLASSIFY.2 Tabla de clasificación en
  `documentacion/MODULE_CLASSIFICATION.md`:

  | Módulo | Categoría | Justificación | Flag de activación |
  |---|---|---|---|
  | `universal/runner.py` | OFF_BY_DEFAULT | Sólo si `CARTER_UNIVERSAL_PLAN_RUNNER=1` (ya gated) | env existente |
  | `universal/task_frame_builder.py` | OFF_BY_DEFAULT | Sigue al runner | env existente |
  | `universal/resource_resolver.py` | KEEP_LAZY | Lo usa `_active_app_followup_context`; cargar perezoso | import dentro de fn |
  | `universal/tool_index.py` | KEEP_LAZY | Útil para top-K en F-CATALOG | import dentro de fn |
  | `universal/checkpoint.py`, `plan_graph.py`, `task_frame.py` | OFF_BY_DEFAULT | Acompañan runner | env existente |
  | `universal/computer_use.py` | DELETE_CANDIDATE | Verificar uso real en smoke; si 0 hits → propuesta de borrado en F-DELETE | — |
  | `universal/memory_store.py`, `memory_policy.py` | OFF_BY_DEFAULT | Memoria experimental separada de session/memory.py | nuevo `CARTER_UNIVERSAL_MEMORY=0` |
  | `universal/context.py::build_universal_agent_context` | KEEP_CORE | Inyecta contrato al system prompt; mantener | — |
  | `capabilities/vision_router.py` | KEEP_LAZY | Inicializar SOLO al primer tool visión | refactor en F-VISION |
  | `capabilities/vision.py`, `screen_cache.py` | KEEP_LAZY | igual | igual |
  | `capabilities/_vision_suggestions.py` | KEEP_LAZY | post-fail GUI | igual |
  | `capabilities/_gui_planner.py` | CORE | gui_do depende | — |
  | `capabilities/gui_agent.py` | CORE | gui_do depende | — |

- F-CLASSIFY.3 Hacer cumplir KEEP_LAZY: mover `from
  ..capabilities.vision_router import get_vision_router` desde el
  top de `agent_prompt.py` a dentro de `_format_vision_capability_status`
  + condicionar el bloque a "tools list contiene ≥1 tool con prefix
  `vision_` o `gui_`".
- F-CLASSIFY.4 Añadir flag `CARTER_UNIVERSAL_MEMORY=0` (default OFF)
  para `universal/memory_store.py`.

**Test gate:** smoke F0.4 re-ejecutado; comparar `audit/F-CLASSIFY_imports.json`
antes/después. Para cualquier módulo OFF_BY_DEFAULT, debe reportar 0
hits en el smoke.
**Riesgo:** BAJO (sólo gating + lazy imports).
**Rollback:** revert por subfase.

---

### F-VISION — Vision lazy real

**Objetivo:** nada de visión se inicializa hasta que un tool visión se
llame por primera vez. Status no se inyecta en el prompt si no hay
tools de visión presentes.

**Subfases:**

- F-VISION.1 `_format_vision_capability_status(tools_for_turn)` recibe
  la lista de tools del turno actual. Si ninguna empieza por
  `vision_`/`gui_` → devuelve "" sin importar nada.
- F-VISION.2 `vision_router.get_vision_router()` se mueve a inicializar
  el backend en su primer `describe_image`/`find_element`, no en
  `__init__`. El `status` queda como `tier=unknown` hasta entonces;
  si el LLM intenta call y backend no existe, error honesto.
- F-VISION.3 Test `test_vision_lazy.py`: verificar que un turno
  conversacional NO importa `vision_router` (mediante
  `sys.modules` snapshot).

**Test gate:** smoke F0.4 con "quien eres" → vision_router NO en
sys.modules tras el turno.
**Riesgo:** BAJO.
**Rollback:** revert.

---

### F-CATALOG — Tool catalog contextual real

**Objetivo:** dejar de mandar 242 tools en cada turno; mandar top-K
filtrado por contexto.

**Diseño:**

- Reusar `universal/tool_index.py::ToolIndex` como índice ya construido
  al boot.
- En cada turno (post `hint`), construir `tools_for_turn`:
  - Si `hint == "agent_no_tools"` → `[]`.
  - Si `hint == "agent_full"` → top-K (default K=64,
    `CARTER_TOOL_TOPK=64`) de `ToolIndex.search(user_text)` +
    UNIÓN con un **núcleo siempre presente** (`memory_save`,
    `memory_recall`, `system_get_time`, `network_get_ip`,
    `web_open_url`, `app_open`, `gui_do`, `terminal_run_command`,
    `filesystem_read_text`, `filesystem_list_directory` —
    estructural, no por marca).
  - Si `force_full_catalog=True` (env override o el LLM lo pidió en
    iteración previa con `meta_list_capabilities`) → todas.
- Logging por turno: `turn_trace["catalog_size"] = len(tools_for_turn)`.
- Mantener TODAS las tools registradas; sólo se filtran las que se
  presentan al LLM por turno.

**Subfases:**

- F-CATALOG.1 Helper `select_tools_for_turn(user_text, hint, prior_calls) -> list[dict]`
  en `turn/agent_prompt.py` (puro, testeable).
- F-CATALOG.2 Integración en `AgentEngine.run` reemplazando
  `tool_schemas_for_llm()` directo por `select_tools_for_turn(...)`.
- F-CATALOG.3 Tests `test_tool_catalog_selection.py`: cubrir 12
  intents distintos, verificar que el tool correcto está siempre en
  el top-K, y que el catálogo nunca excede K + núcleo.

**Test gate:** smoke F0.4 muestra `catalog_size ≤ 80` en turnos
conversacionales/simples; precisión@k del tool correcto ≥ 95% en
test_tool_catalog_selection.
**Riesgo:** MEDIO. Si el índice falla, el LLM no ve la tool que
necesita. Mitigado con núcleo siempre presente + override env
`CARTER_TOOL_TOPK=999`.
**Rollback:** revert F-CATALOG.2.

---

### F-HONESTY — Honestidad contextual completa

**Objetivo:** que el ledger refleje la verdad: si Carter no puede
verificar el outcome, NO dice "listo".

**Subfases:**

- F-HONESTY.1 `app_open`: tras `Popen`, esperar `min(2s, configurable)`
  y `process.poll()` o `psutil.pid_exists(pid)`. Si murió → `ok=False`,
  `message="Launched process exited within 2s"`, evidence con
  `returncode`. Sin hardcode por app.
- F-HONESTY.2 `gui_do`: tras la ejecución, comparar el `final_screen_hash`
  contra el inicial. Si idéntico → `verified_outcome="unchanged"`. Si
  el caller esperaba mutación, `_guard_final_reply` reescribe a
  "intenté pero no detecté cambios visibles". Sin hardcodes de
  ventanas/apps.
- F-HONESTY.3 `process_stop_app` (post F-A1): añadir `verified_outcome`
  al evidence basado en re-enumeración psutil.
- F-HONESTY.4 `_guard_final_reply` consulta `ledger.last_action.verified_outcome`
  y si es `"unchanged" | "unverified"` y la respuesta del LLM contiene
  patrón positivo estructural (presencia de "ok", "done", "listo"
  como token aislado — única lista que mantenemos por ser **palabras
  verificables del propio Carter**, no del usuario), reescribe a
  fallback honesto.

**Test gate:** unitarios + smoke F-HONESTY.S1: pedir "abre Notepad",
matar el proceso a mano dentro de 1s, verificar que Carter reporta
honestamente. Pedir un `gui_do` imposible (clic en un botón
inexistente) y verificar que la respuesta no miente.
**Riesgo:** MEDIO. Riesgo de falsos negativos (decir "no pude" cuando
sí pudo). Mitigar con telemetría — reportar tasa de
`verified_outcome=unverified` en `audit/F-HONESTY_metrics.json`.
**Rollback:** revert por subfase.

---

### F-PROMPT — Prompt diet radical

**Objetivo:** `_SYSTEM_PROMPT_TEMPLATE` actual ~7000 chars / 145 líneas
con ejemplos por marca → kernel ≤ 1500 chars + secciones lazy por
top-K tools del turno.

**Diseño:**

- Kernel estable (≤ 30 líneas):
  - Identidad ("You are Carter, …").
  - Reglas estructurales de seguridad (refuse blanket-destructive en
    rootfs/systemroot — sin lista de frases, basadas en patrón
    estructural `wipe|format|delete-all` aplicado por la POLICY layer,
    no el prompt).
  - Política tool calling (1 frase: "Call the matching tool. Honest
    error if you cannot. No success without ok=True.").
  - Política memoria (1 frase).
  - Política idioma (1 frase: "Reply in the user's language.").
- Bloques dinámicos por turno (sólo se inyectan si aplican):
  - `KNOWN_FACTS` — sólo si `relevant_facts(user_text)` no vacío.
  - `ACTIVE_APP_CONTEXT` — sólo si hay app activa.
  - `RUNTIME_DEPS` — sólo si hay deps faltantes.
  - `RECENT_ALERTS` — sólo si hay alertas <5 min.
  - `VISION_STATUS` — sólo si tools del turno incluyen vision/gui.
  - `TOOL_HINTS` — top-3 tools elegidos en F-CATALOG, con su
    descripción compacta (no la full). Sin ejemplos de marca.
- Cache real:
  - Key = sha256 de
    `(user_ref, memory_facts_hash, deps_hash, alerts_hash,
    vision_block_present, tool_hints_hash)`.
  - LRU con max 64 entradas (memoria O(MB)).
  - Invalidación explícita en `memory.set_user_name`,
    `memory.save_fact`, `memory.remember`.
- Borrar todos los ejemplos por marca en el template
  ("Discord, Spotify, Steam, and VS Code are desktop apps...",
  "Steam client: app_open(target=\"Steam\")", "Spotify desktop
  playback: ...", "YouTube is primarily a website ...").
  Reemplazar por **regla estructural** en la descripción de cada tool
  (`adapters/tools.py`):
  - `app_open`: "Use for native desktop applications by name."
  - `web_open_url`: "Use for any URL or web service."
  - `web_search_in_browser`: "Use when the user names a browser AND
    wants to search."
  Sin marcas.

**Subfases:**

- F-PROMPT.1 Crear nuevo `_SYSTEM_KERNEL` constante en
  `agent_prompt.py` (≤ 30 líneas).
- F-PROMPT.2 Refactor `_build_system_prompt` para componer kernel +
  bloques dinámicos.
- F-PROMPT.3 Auditar `adapters/tools.py` y mover los ejemplos por
  marca del system prompt a la descripción compacta de cada tool
  (sólo describiendo capacidad estructural, no marcas).
- F-PROMPT.4 Cache LRU sha256 con invalidación explícita.
- F-PROMPT.5 Test `test_system_prompt_size.py` — el prompt promedio
  en F0.4 smoke debe pesar ≤ 1500 tokens (estimado vía tiktoken).
- F-PROMPT.6 Test `test_no_brand_in_kernel.py` — kernel no contiene
  literales `Steam|Spotify|Discord|YouTube|Notepad|VS Code|Opera`.

**Test gate:** todos los tests anteriores verdes + smoke real F-PROMPT.S1
con los 6 turnos de F0.4 → reducción ≥ 50% en tokens prompt y ≥ 30%
en latencia first_llm.
**Riesgo:** ALTO. Borrar ejemplos puede degradar tool selection con
modelos pequeños. Mitigado con F-CATALOG (top-K ya focalizó tools) y
con descripciones de tool reforzadas.
**Rollback:** revert por subfase. F-PROMPT.3 es la más reversible
(sólo edita strings).

---

### F-MEMORY — Memoria durable limpia (cierre)

**Objetivo:** cerrar el residual del Phase 5 / A4-A5.

**Subfases:**

- F-MEMORY.1 File lock cross-process para `MEMORY.md` writes:
  reemplazar `RLock` por `portalocker.Lock` (best-effort,
  fallback a `RLock` si lib no disponible). Aplicar en `remember()`
  y en `proactive.py:553`.
- F-MEMORY.2 `_lt_context_cache` racy: mover el check-then-use
  dentro del `_write_lock` ya existente. Setear `_lt_context_cache=""`
  junto con `_lt_context_ts=0` en `invalidate_lt_context_cache`.
- F-MEMORY.3 SQLite: añadir `UNIQUE(entity, attribute, value)` en
  tabla `facts` (o índice + `INSERT OR IGNORE`). Migración idempotente.
- F-MEMORY.4 `_is_promotable_candidate` reforzado:
  - reject si `entity='user' AND attribute='name' AND source != 'user_stated'`.
  - reject si pasa `_OPERATIONAL_RE` ya existente.
- F-MEMORY.5 Reemplazar `except Exception: pass` en
  `session/memory.py` y `session/proactive.py` por
  `except Exception as exc: _log_memory_warning(exc, context=...)`.
  Ya existe `_log_memory_warning`. Sin nuevos `pass`.
- F-MEMORY.6 Test `test_memory_persistence_lock.py`: simular
  escritura concurrente (2 threads) y verificar integridad del MD.

**Test gate:** unitarios verdes + smoke F-MEMORY.S1: 100 turnos de
mensajes mixtos, MEMORY.md final sin duplicados, sin probe-event-id,
sin entries de `name:` con source distinto de `user_stated`.
**Riesgo:** BAJO-MEDIO.
**Rollback:** revert por subfase. F-MEMORY.3 requiere cuidado en
migración (usar `CREATE INDEX IF NOT EXISTS` y `INSERT OR IGNORE`).

---

### F-SMOKE — Smoke runtime con Qwen real y `CARTER_TIMING=1`

**Objetivo:** validación de cierre. NO se considera "cerrado" sin
esto.

**Pre-requisitos:**
- `run_carter_gpu.ps1` ya correcto (vision/chat split).
- F-CATALOG y F-PROMPT mergeados.

**Batería:**

| ID | Input | Expectativa | Métrica |
|---|---|---|---|
| S1 | `hola` | 0 tools, ≤ 1 LLM call | `total ≤ 4s` |
| S2 | `quien eres` | 0 tools | `total ≤ 5s` |
| S3 | `who are you` | 0 tools | `total ≤ 5s` |
| S4 | `quem é você` | 0 tools | `total ≤ 5s` |
| S5 | `qui es-tu` | 0 tools | `total ≤ 5s` |
| S6 | `wer bist du` | 0 tools | `total ≤ 5s` |
| S7 | `chi sei` | 0 tools | `total ≤ 5s` |
| S8 | `你是谁` | 0 tools | `total ≤ 5s` |
| S9 | `que hora es` | exactamente 1 call a `system_get_time` | `total ≤ 6s` |
| S10 | `cuál es mi IP` | exactamente 1 call a `network_get_ip` | `total ≤ 6s` |
| S11 | `cuál es mi IP pública` | 1 call a `network_get_public_ip` | `total ≤ 8s` |
| S12 | `qué sabes de mí` (tras setear color favorito) | `memory_recall` 1 vez | `total ≤ 7s` |
| S13 | `mi color favorito es verde` | `memory_save` 1 vez; MEMORY.md actualizado | `total ≤ 6s` |
| S14 | `qué es la capital de Francia` | 0 tools | `total ≤ 5s` |
| S15 | `abre Notepad` | `app_open` 1 vez; verificación PID viva | `total ≤ 7s` |
| S16 | (siguiente turno) `ciérralo` | `process_stop_app` cooperativo (WM_CLOSE) | `total ≤ 8s` |
| S17 | `2+2` | 0 tools, respuesta "4" | `total ≤ 3s` |
| S18 | `setea CARTER_TEST_VAR=hola y persíste` | `system_env_set` con WM_SETTINGCHANGE | `total ≤ 7s` |

**Reglas:**
- Smoke se ejecuta con `CARTER_TIMING=1` y captura
  `last_turn_trace["_timing"]` + `tool_calls_made` por turno.
- Output → `audit/F-SMOKE_results.json` y `.md`.
- Diff contra `audit/F0_smoke.json` (baseline).
- Gate de cierre del modo texto: TODOS los S1–S18 verdes.

**Riesgo:** depende del modelo. Si Qwen3-8B Q4_K_M falla en alguno con
≥ 1% de tasa, NO es razón para reintroducir hardcodes — es razón para
reforzar la **descripción del tool** o subir K en F-CATALOG.

---

## 3. Orden recomendado de ejecución

```
F0  (baseline)
 ├─ F1  (refactor — no behavior)         ← independiente, mergeable solo
 ├─ F-CLASSIFY                           ← independiente
 │   └─ F-VISION                         ← depende de F-CLASSIFY
 ├─ F-MEMORY                             ← independiente
 ├─ F-A1                                 ← independiente
 ├─ F-A2                                 ← independiente
 ├─ F-CATALOG                            ← depende de F1
 │   └─ F-PROMPT                         ← depende de F-CATALOG
 │       └─ F8                           ← depende de F-PROMPT (los hardcodes
 │                                          se eliminan cuando el catálogo y
 │                                          el prompt ya soportan la decisión)
 │           └─ F-HONESTY                ← depende de F8 (ledger limpio)
 │               └─ F-SMOKE              ← gate final
```

Ningún paso depende de Ollama. Todo el smoke F-SMOKE corre con
`llamacpp` + Qwen GGUF (el backend de prod).

---

## 4. Métricas de cierre (Definition of Done)

Carter texto se considera **radicalmente cerrado** cuando, en una sola
sesión continua de smoke con Qwen real:

- [ ] `agent.py` ≤ 800 LOC (post F1).
- [ ] 0 listas de frases ES/EN/PT/FR en `turn/*.py` y
      `capabilities/*.py` (verificado por `test_no_hardcoded_phrase_lists.py`).
- [ ] `process_stop_app` registra `method=WM_CLOSE` cuando el cierre es
      cooperativo y `method=taskkill_force` sólo cuando hubo timeout.
- [ ] `system_env_set` con `persist=True` ejecuta WM_SETTINGCHANGE y lo
      reporta en evidence; rechaza PATH sin `allow_system_var`.
- [ ] System prompt promedio ≤ 1500 tokens en S1–S18.
- [ ] `catalog_size ≤ 80` en S1–S14; ≤ 200 en S15–S18.
- [ ] MEMORY.md tras S1–S18 contiene SOLO facts user_stated; sin
      duplicados; sin probe-event-id; sin `name:` con otra fuente.
- [ ] Latencia: S1–S8 (conversacional) ≤ 5s; S9–S14 ≤ 7s;
      S15–S18 ≤ 10s, todos con `CARTER_TIMING=1` evidenciable.
- [ ] `vision_router` no aparece en `sys.modules` tras S1–S14.
- [ ] Suite completa de tests verde excepto los explícitamente
      `@pytest.mark.live` (que requieren Ollama / red).
- [ ] `documentacion/MODULE_CLASSIFICATION.md` existe y está al día.
- [ ] Honestidad: ningún turno de F-SMOKE produce un mensaje positivo
      cuando el ledger reporta `verified_outcome != confirmed`.

---

## 5. Lo que este plan NO hace

- No toca voz ni cámara (modo texto sólo).
- No reescribe `llama_backend.py` ni cambia samplers.
- No elimina `interfaces/{discord,slack,telegram}` (gated por env).
- No toca el schema SQLite más allá del UNIQUE en facts.
- No introduce dependencias nuevas excepto `portalocker` (opcional,
  con fallback) en F-MEMORY.
- No agrega clasificadores de idioma. La eliminación de hardcodes es
  por reglas estructurales, no por NLP.

---

## 6. Pregunta para el usuario antes de implementar

1. ¿Apruebas el orden F0 → F1 → (F-CLASSIFY/F-MEMORY/F-A1/F-A2 en
   paralelo) → F-CATALOG → F-PROMPT → F8 → F-HONESTY → F-SMOKE?
2. ¿Aceptas que en F8 algunos invariants se eliminen completamente
   (sin reemplazo léxico) si los smokes los hacen innecesarios?
3. ¿Aceptas que F-A1 deje Notepad colgado en diálogo "guardar?" en
   caso de cambios sin guardar (comportamiento cooperativo correcto)?
4. ¿Aceptas que F-A2 use whitelist estructural para vars de sistema
   (PATH, SystemRoot, etc.) y bloquee sobre-escritura sin
   `allow_system_var=True`?
5. ¿Quieres que `portalocker` se agregue a `pyproject.toml` o
   prefieres mantener fallback puro a `threading.RLock`?

Sin respuesta a estas 5, no se inicia ninguna implementación.
