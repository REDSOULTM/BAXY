# Auditoría Carter Agent — 2026-05-14

Modo READ-ONLY. Ningún archivo de código fue modificado. Solo se creó este
reporte en la raíz del proyecto.

## Resumen ejecutivo

- **Hallazgos críticos** (🔴 = bug real, comportamiento incorrecto): **4**
- **Hallazgos altos** (🟠 = riesgo claro o feature rota silenciosamente): **8**
- **Hallazgos medios** (🟡 = inconsistencia, deuda, o bug latente bajo carga): **14**
- **Hallazgos bajos/cosméticos** (🟢): **9**

**Recomendación general:** El repo está sano. La arquitectura aguanta, los 66
tests pasan, pyright limpio en `agent.py`/`voice/`/`ui/`. Lo que duele son
**tres focos de deuda real** que valen un día de trabajo focal: (1) el tab
TRANSCRIPT de Settings escribe env vars que ningún módulo lee y los selectores
STT model/TTS voice de la VOICE tab persisten pero nunca se aplican al
controller; (2) `AgentState`/`MemoryStore`/`Session.save` usan
read-modify-write sobre JSON sin lock — bajo carga (voz + UI + watcher
concurrentes) hay perdida de datos posible; (3) varios threads daemon usan
`time.sleep()` en vez de `Event.wait()`, lo que hace que `closeEvent` espere
hasta el siguiente tick antes de terminar el proceso. El resto son pulidos
sobre código que funciona.

---

## Top 10 bugs que arreglaría YA si tuviera 1 día

Listados por costo/beneficio, los primeros son los más importantes:

1. 🔴 **TRANSCRIPT tab guarda env vars muertos**
   [gemma4_agent/ui/settings.py:1096-1103](gemma4_agent/ui/settings.py#L1096-L1103)
   Escribe `GEMMA4_AGENT_STT_MODEL`, `GEMMA4_AGENT_TTS_VOICE`,
   `GEMMA4_AGENT_WAKE_WORD`, etc. Ningún módulo de `voice/` los lee.
   `voice/stt.py:62` lee `GEMMA4_VOICE_STT_MODEL`; `voice/tts.py:133` lee
   `GEMMA4_VOICE_TTS_VOICE`. Fix sugerido: o renombrar para que coincidan,
   o eliminar la tab TRANSCRIPT (la VOICE tab la suplanta). Costo: 15-30 min.

2. 🔴 **VOICE tab persiste `stt_model` y `tts_voice` pero el controller no los usa**
   [gemma4_agent/ui/main_window.py:919-931](gemma4_agent/ui/main_window.py#L919-L931)
   `_start_voice_controller` pasa `followup_seconds`, `close_phrases`,
   `feedback_beep`, `device`, `tts_muted` al `VoiceController` — NO pasa
   `stt_model` ni `tts_voice`. Resultado: el usuario cambia el modelo en la
   GUI, le da APPLY, no pasa nada. Fix: pasarlos vía
   `os.environ["GEMMA4_VOICE_STT_MODEL"] = voice_cfg["stt_model"]` antes de
   crear `StreamingSTT`/`StreamingTTS`, o agregar params al constructor del
   `VoiceController`. Costo: 30 min.

3. 🔴 **`SysMetrics.stop()` no join al thread, y el thread usa `time.sleep`**
   [gemma4_agent/ui/metrics.py:37-49](gemma4_agent/ui/metrics.py#L37-L49)
   El thread daemon es `name="gemma4-sysmetrics"`; `stop()` setea
   `_running=False` pero el thread está dormido en `time.sleep(self._interval)`
   (1.5s). Tarda hasta 1.5s en notar el flag y terminar. En `closeEvent` esto
   es trivial (daemon=True), pero al hacer `_restart_worker` durante una
   sesión, queda un thread fantasma sampleando psutil + lanzando
   subprocess `nvidia-smi`/`powershell` por hasta 1.5s después del flag.
   Fix: agregar `threading.Event` y usar `self._stop_event.wait(self._interval)`.
   Costo: 10 min.

4. 🔴 **`AgentState`/`MemoryStore`/`SessionStore` read-modify-write sin lock**
   [gemma4_agent/state.py:39-55](gemma4_agent/state.py#L39-L55),
   [gemma4_agent/memory.py:31-55](gemma4_agent/memory.py#L31-L55),
   [gemma4_agent/sessions.py:128-136](gemma4_agent/sessions.py#L128-L136)
   Si dos llamadas concurrentes hacen `register_resource` o `auto_save`,
   ambos hacen `_load() -> mutate -> _save()`. El segundo lee el JSON pre-
   mutación del primero y sobreescribe el cambio. **Threads concurrentes
   reales**: agente principal + watcher + voice TTS + parallel_tools
   (cuando `GEMMA4_AGENT_PARALLEL_TOOLS=true`). En operación normal es
   raro porque solo el agente write-states tools, pero el caso parallel_tools
   convierte esto en un riesgo real: dos tools pueden hacer
   `state.register_resource` al mismo tiempo. Fix: `threading.RLock` por
   instancia (no lock global) en cada `_load/_save`. Costo: 30 min.

5. 🟠 **`profile_watcher.set_active_profile` puede correr durante un turno**
   [gemma4_agent/profile_watcher.py:253-263](gemma4_agent/profile_watcher.py#L253-L263)
   El watcher cambia env vars vivos. Si el agente está a medio turno y
   `apply_profile_to_env` cambia `GEMMA4_AGENT_CONTEXT`, la siguiente call
   `client.chat` puede usar el nuevo context pero el system prompt fue
   construido con el viejo. No hay corrupción pero el comportamiento es
   inconsistente. Mejor: poner el switch en cola y aplicarlo solo al fin
   de turno. Costo: 1h.

6. 🟠 **`_run_with_timeout` deja threads zombie**
   [gemma4_agent/agent.py:1280-1309](gemma4_agent/agent.py#L1280-L1309)
   Comentario explícito reconoce esto: "we abandon it". El thread sigue
   corriendo en background hasta que la function bloqueante termine.
   Para tools fast es ok; para tools que llaman subprocess `powershell`
   con timeout 12s, deja un thread + un subprocess por cada timeout.
   No causa crashes, sí causa fuga de descriptores y subprocesos. Fix
   completo es difícil (Python no permite kill thread); fix práctico:
   en `_run_with_timeout` para tools que sabemos que spawan subprocess,
   marcar el subprocess como cancelable. Costo: 2h. Aplicar solo si
   detectás leak real en producción.

7. 🟠 **`VoiceController._cancel_timer` no espera al timer thread**
   [gemma4_agent/voice/controller.py:393-395](gemma4_agent/voice/controller.py#L393-L395)
   Setea `_timer_stop.set()` y pierde la referencia. El thread previo
   sigue corriendo hasta que el siguiente `wait(LISTENING_TIMEOUT_S)`
   retorne (puede ser hasta 5s). Si llegan dos `_start_listening_timeout`
   muy seguidos, hay dos threads daemon listo para disparar. No corrompe
   estado porque el segundo verifica `self._state == S_LISTENING` antes
   de cambiar nada, pero es ruido. Fix: hacer `join(timeout=0.1)` después
   del set. Costo: 10 min.

8. 🟠 **`_stop_stt_thread` join(0.5) silencioso**
   [gemma4_agent/voice/controller.py:477-481](gemma4_agent/voice/controller.py#L477-L481)
   Si Whisper está en medio de un `_transcribe_buffer` (cosa que puede
   tomar 1-3s en CPU), el join(0.5) retorna sin que el thread haya
   terminado. El thread sigue corriendo, eventualmente emite un STTEvent,
   y como `_on_partial`/`_on_final` aún apuntan al callback, mete texto
   en una sesión que ya cambió (ej: usuario hizo `/new` o cambio profile
   a LIGHT mientras hablaba). Fix: join con timeout grande (5s) y si no
   termina, log explícito y marcar el callback como None primero. Costo: 30 min.

9. 🟠 **`datetime.utcnow()` deprecado**
   [gemma4_agent/domain_tools.py:7140](gemma4_agent/domain_tools.py#L7140)
   Genera ICS calendar entries. En Python 3.12+ emite DeprecationWarning;
   en 3.13 se va a romper. Reemplazo: `datetime.now(timezone.utc)`.
   Costo: 5 min.

10. 🟠 **`_compact_active_history_for_retry` puede dejar `tool_call_id` huérfanos**
    [gemma4_agent/agent.py:1123-1152](gemma4_agent/agent.py#L1123-L1152)
    En el retry corta los primeros `tool` msgs sin verificar que sus
    correspondientes `assistant.tool_calls` también se hayan cortado.
    Si después un `assistant.tool_calls` queda apuntando a un
    `tool_call_id` que no está en history, llama-server devuelve
    400. La lógica `while trimmed and trimmed[0].get("role") == "tool"`
    al final lo mitiga parcialmente, pero solo elimina tool msgs huérfanos
    al *inicio*; si hay un tool msg interno cuyo assistant.tool_calls
    fue cortado, queda colgando. Fix: emparejar `assistant{tool_calls}` ↔
    `tool` pairs al cortar. Costo: 1h.

---

## Top 5 mejoras de arquitectura que harían el repo más fácil de mantener

Sin tocar comportamiento, solo organizar lo que ya hay:

1. **Consolidar normalize/fold de texto**
   Hay al menos 3 implementaciones de "lowercase + drop combining marks":
   `_fold_match` en [agent.py:1254-1258](gemma4_agent/agent.py#L1254-L1258),
   `_normalize_phrase` en [voice/controller.py:74-77](gemma4_agent/voice/controller.py#L74-L77),
   y la lambda inline en [ui/main_window.py:56-58](gemma4_agent/ui/main_window.py#L56-L58)
   (_is_whisper_hallucination). Los tres hacen exactamente lo mismo. Un
   `gemma4_agent/_text.py` con `fold(text) -> str` lo unifica.

2. **Extraer `_compute_context_budget`/`_compact_*` a `agent_history.py`**
   `agent.py` tiene 1652 LOC con la mitad dedicada a compactación de
   history. Las funciones puras (`_compact_json`, `_middle_ellipsis`,
   `_compact_tool_result`, `_message_text_estimate`, `_compute_context_budget`)
   son independientes del agente y testeables en aislamiento. Sacarlas
   reduce agent.py a ~900 LOC con la lógica principal y deja una unidad
   testeable aparte. No cambia comportamiento.

3. **Una clase `JSONStore` para state/memory/sessions**
   Los tres replican el mismo patrón: `path`, `_load`, `_save`, init dir.
   Una superclase abstracta (`gemma4_agent/_jsonstore.py`) con `_lock`
   integrado mata el bug #4 de la lista y elimina ~60 LOC duplicados.

4. **`SettingsDialog._gather` produce un dict tipado**
   El método retorna `{"env": {str: str}, "toggles": {str: bool}, ...}`
   sin schema. `_apply_settings_live` parse-checks cada campo con
   try/except. Un `@dataclass class SettingsPayload` haría que pyright
   detecte cuando un campo se renombra o falta. No cambia
   comportamiento.

5. **`ACTION_ENUMS` debería vivir junto a `COMPOUND_TOOL_SCHEMAS`**
   En [tools.py:141-204](gemma4_agent/tools.py#L141-L204) está separado de
   los schemas que va a parchear. Cuando agregás un schema nuevo, es muy
   fácil olvidar agregar el enum (no hay error, solo se cae el guardrail).
   Mover `enum` al dict de cada schema directo, evitando `_apply_action_enums`.

---

## Top 5 cosas que NO tocaría aunque parezcan "feas"

Código que funciona y refactorearlo es riesgo gratis:

1. **El SYSTEM_PROMPT gigante** ([agent.py:26-292](gemma4_agent/agent.py#L26-L292))
   267 líneas de string. Da ganas de partirlo en pieces, pero cualquier
   cambio cambia el comportamiento del LLM. El prompt está calibrado a
   los benchmarks del repo. No lo toques.

2. **Los `except Exception: pass` en `ui/main_window.py`**
   Hay 28 instancias. Cada una es defensiva contra que la GUI tire por
   un signal mal conectado o un thread tarde. Los reemplazos
   selectivos (que loggean) cuestan tiempo y no compran nada hasta que
   tengas un crash reproducible.

3. **`COMPOUND_TOOL_SCHEMAS` (3000 LOC inline en tools.py)**
   Sí, es feo. No, no lo toques. Es generated content (parecen creados
   en lote); refactorizarlo a YAML/JSON externo cambia el flow de cómo
   se cargan los schemas y obliga a re-validar los 62 tools.

4. **Los timeouts hardcoded en `voice/`**
   `LISTENING_TIMEOUT_S=5.0`, `VAD_SILENCE_MS=800`, `ABSOLUTE_TIMEOUT_S=15.0`,
   `WAKE_FEEDBACK_MS=200`. Estos números están calibrados a hardware
   específico (CPU lenta + faster-whisper int8 + Vosk small). Hacerlos
   configurables en Settings invita al usuario a quebrarlos.

5. **`domain_tools.py` (7194 LOC, 281 funcs, 0 clases)**
   Es funciones puras en un archivo enorme. Tira de pyright pero
   funcionalmente está bien. Partirlo en submódulos (notifications,
   media, smart_home, etc) toca demasiadas imports en `tools.py` y
   `eval_smoke.py`; cualquier rename rompe el orden de los schemas en
   `COMPOUND_TOOL_SCHEMAS`. Costo > beneficio.

---

## Capa 1 — Inventario de superficie

LOC totales del paquete principal `gemma4_agent/` (excluyendo subpackages):

| Módulo | LOC | Funcs (pub) | Classes | Imports | Const top-level | Notas |
|---|---|---|---|---|---|---|
| agent.py | 1652 | 39 (5) | 3 | 52 | 4 | OK |
| chat.py | 489 | 13 (5) | 1 | 32 | 1 | CLI legacy |
| config.py | 138 | 5 (3) | 1 | 7 | 3 | OK |
| domain_tools.py | 7194 | 281 (41) | 0 | 66 | 4 | 🟡 file enorme, 65 pyright errors |
| eval_smoke.py | 97 | 1 (1) | 0 | 11 | 0 | Smoke test |
| evaluator.py | 96 | 4 (1) | 0 | 2 | 1 | OK; const `MISSION_STATES` declarada pero usada (false positive del analizador) |
| experience.py | 359 | 13 (8) | 1 | 10 | 4 | OK |
| explicit_plan.py | 150 | 6 (5) | 0 | 7 | 0 | OK |
| import_triggercmd.py | 131 | 2 (1) | 0 | 8 | 0 | OK |
| knowledge.py | 253 | 15 (6) | 1 | 10 | 3 | OK |
| launcher.py | 328 | 16 (16) | 0 | 18 | 2 | CLI |
| llama_server.py | 350 | 13 (11) | 1 | 16 | 0 | OK |
| llm_client.py | 261 | 7 (3) | 1 | 7 | 0 | OK |
| memory.py | 117 | 8 (5) | 1 | 7 | 0 | 🟡 RMW sin lock (ver #4) |
| modes.py | 165 | 4 (1) | 1 | 4 | 1 | OK |
| multimodal.py | 44 | 4 (3) | 0 | 5 | 0 | OK |
| ops_tools.py | 1115 | 42 (11) | 0 | 20 | 0 | OK |
| personas.py | 126 | 3 (3) | 1 | 3 | 0 | OK |
| planner.py | 744 | 14 (5) | 2 | 7 | 4 | OK |
| profile_watcher.py | 300 | 15 (3) | 3 | 18 | 5 | OK |
| profiles.py | 383 | 11 (10) | 1 | 10 | 3 | `field` import L33 no usado (cosmético) |
| project_context.py | 91 | 4 (4) | 0 | 3 | 3 | OK |
| reasoning.py | 42 | 2 (2) | 0 | 3 | 2 | const `THINKING_KEYS` aparente unused (revisar) |
| routine_runner.py | 55 | 1 (1) | 0 | 8 | 0 | `Path` import L16 no usado |
| safety.py | 67 | 2 (1) | 1 | 3 | 0 | OK |
| semantic_router.py | 231 | 6 (5) | 1 | 7 | 4 | `warm_up()` declarado pero sin caller |
| sessions.py | 231 | 15 (10) | 3 | 11 | 0 | 🟡 RMW sin lock |
| state.py | 176 | 17 (13) | 1 | 8 | 0 | 🟡 RMW sin lock |
| subagent.py | 99 | 2 (2) | 0 | 4 | 0 | OK |
| timeline.py | 137 | 7 (3) | 1 | 7 | 0 | OK |
| tools.py | 3088 | 193 (134) | 3 | 80 | 3 | 🟡 `TOOL_SCHEMAS` constante en L3064 — sin caller dentro del repo (legacy harness usa el mismo nombre pero distinto archivo) |
| tracing.py | 67 | 5 (3) | 1 | 7 | 0 | OK |
| watcher_runner.py | 43 | 1 (1) | 0 | 7 | 0 | OK |
| voice/audio_io.py | 245 | 8 (5) | 1 | 9 | 5 | OK |
| voice/controller.py | 533 | 32 (13) | 1 | 15 | 15 | const `ALL_STATES`, `ABSOLUTE_TRANSCRIBE_S` declaradas pero sin uso fuera del módulo (uso interno solo en `ABSOLUTE_TRANSCRIBE_S`) |
| voice/stt.py | 334 | 8 (6) | 2 | 10 | 5 | OK |
| voice/tts.py | 278 | 17 (12) | 1 | 13 | 4 | `download_voice` declarado pero sin caller (era para flow de consentimiento que no se completó) |
| voice/wake.py | 291 | 8 (7) | 1 | 12 | 6 | `WAKE_PHRASES` declarado pero sin uso (debounce filtra por debate exact-match en `text`, no usa el set). `download_model` declarado pero sin caller |
| ui/main_window.py | 1270 | 53 (4) | 4 | 80 | 1 | 28 `except Exception: pass`. Funcional pero opaco |
| ui/settings.py | 1163 | 29 (4) | 1 | 57 | 2 | 🔴 TRANSCRIPT tab dead (#1) |
| ui/hud.py | 482 | 26 (6) | 1 | 21 | 0 | OK |
| ui/panels.py | 357 | 9 (4) | 0 | 27 | 2 | 5 imports unused (L9-L13: Path/QSize/pyqtSignal/QKeySequence/QShortcut) |
| ui/triggers.py | 348 | 11 (1) | 1 | 32 | 0 | OK |
| ui/memory_viewer.py | 285 | 12 (1) | 1 | 27 | 0 | OK |
| ui/sessions_panel.py | 212 | 10 (1) | 1 | 21 | 0 | OK |
| ui/tool_explorer.py | 188 | 7 (0) | 1 | 24 | 0 | OK |
| ui/agent_thread.py | 221 | 10 (5) | 2 | 14 | 0 | `time` import L21 no usado |
| ui/metrics.py | 175 | 10 (5) | 1 | 8 | 1 | 🟠 thread daemon usa `time.sleep` (#3); `re` import L10 no usado |
| ui/theme.py | 233 | 10 (10) | 1 | 4 | 1 | `ANYDICT` declarado sin uso |
| ui/log_widget.py | 101 | 6 (2) | 1 | 10 | 1 | OK |
| ui/metric_bar.py | 75 | 3 (2) | 1 | 10 | 0 | OK |
| ui/app.py | 146 | 6 (2) | 1 | 20 | 0 | 3 imports unused (Path, QLabel, QVBoxLayout) |
| ui/async_tool.py | 70 | 3 (2) | 2 | 8 | 0 | OK |

**Marca 🟡** (>5% código posiblemente muerto): solo `voice/wake.py` (3 constantes
+ función `download_model` sin caller — ~5% líneas), `voice/tts.py`
(`download_voice` sin caller — flow de consentimiento incompleto).

**TODO/FIXME/XXX en codebase**: ninguno real (los 5 hits son "MARK XXXIX",
"TODOS los samples", "TODOS los subcomponentes" — falsos positivos del grep).

---

## Capa 2 — Consistencia entre módulos

| Inconsistencia | Módulos | Severidad | Sugerencia (no implementar) |
|---|---|---|---|
| 3 implementaciones de fold normalization | [agent.py:1254-1258](gemma4_agent/agent.py#L1254-L1258), [voice/controller.py:74-77](gemma4_agent/voice/controller.py#L74-L77), [ui/main_window.py:56-58](gemma4_agent/ui/main_window.py#L56-L58) | 🟡 | Mover a `gemma4_agent/_text.py:fold(s)` |
| Env vars de voice: TRANSCRIPT tab usa `GEMMA4_AGENT_*`, runtime lee `GEMMA4_VOICE_*` | [ui/settings.py:1096-1103](gemma4_agent/ui/settings.py#L1096-L1103) vs [voice/stt.py:62](gemma4_agent/voice/stt.py#L62), [voice/tts.py:133](gemma4_agent/voice/tts.py#L133) | 🔴 | Renombrar o eliminar tab |
| VOICE tab persiste `stt_model`/`tts_voice` pero el controller no los aplica | [ui/settings.py:540-567](gemma4_agent/ui/settings.py#L540-L567) vs [ui/main_window.py:919-931](gemma4_agent/ui/main_window.py#L919-L931) | 🔴 | Aplicar a env antes de instanciar `VoiceController` |
| Patrón "JSON store con _load + _save sin lock" | `state.py`, `memory.py`, `sessions.py` | 🟠 | Clase base con `RLock` |
| `time.sleep` en threads daemon en vez de `Event.wait()` | [voice/controller.py:405](gemma4_agent/voice/controller.py#L405), [ui/metrics.py:49](gemma4_agent/ui/metrics.py#L49), [chat.py:144](gemma4_agent/chat.py#L144) | 🟡 | Reemplazar por `Event.wait` |
| Formato de tool result: `_ok`/`_err` en `tools.py`, dicts inline en `domain_tools.py` | `tools.py:84-89`, scattered | 🟢 | Importar `_ok`/`_err` en domain_tools (no cambia comportamiento) |
| Naming `path` vs `filepath` vs `file_path` | search en domain_tools y tools | 🟢 | Convención: `path` para entradas del usuario, `_path` para resultados |
| `chat_timeout` hardcoded en config vs `timeout_s` en `client.chat` | [config.py vs llm_client.py:32](gemma4_agent/llm_client.py#L32) | 🟢 | OK como está; ya es opcional |
| Handlers de error: a veces `logger.error + raise`, a veces `logger.warning + return None`, a veces `except: pass` | scattered | 🟡 | No vale la pena unificar; cada uso tiene contexto distinto |
| `parallel_tool_calls` en config y `parallel_tools` en profiles | [config.py:90](gemma4_agent/config.py#L90), [profiles.py:48](gemma4_agent/profiles.py#L48) | 🟢 | Dos vars distintas con propósito distinto pero nombres confusamente similares. Renombrar uno mejoraría legibilidad |

---

## Capa 3 — Bugs latentes por análisis estático

| Archivo:Línea | Descripción | Severidad | Reproducibilidad |
|---|---|---|---|
| [ui/metrics.py:37-49](gemma4_agent/ui/metrics.py#L37-L49) | Thread daemon usa `time.sleep(1.5)`; `stop()` no join → fuga hasta 1.5s | 🟠 | 100% al cerrar la GUI |
| [state.py:39-55](gemma4_agent/state.py#L39-L55), [memory.py:31-55](gemma4_agent/memory.py#L31-L55), [sessions.py:128-136](gemma4_agent/sessions.py#L128-L136) | Read-modify-write sin lock | 🟠 | Carrera real cuando `GEMMA4_AGENT_PARALLEL_TOOLS=true` y dos tools llaman `state.register_resource` |
| [agent.py:1280-1309](gemma4_agent/agent.py#L1280-L1309) | `_run_with_timeout` deja threads zombie sin kill | 🟡 | Sí, pero documentado: "we abandon it" |
| [voice/controller.py:477-481](gemma4_agent/voice/controller.py#L477-L481) | `_stop_stt_thread` join(0.5) — Whisper tarda 1-3s | 🟠 | Sí, ocurre al cambiar profile mid-transcribe |
| [voice/controller.py:393-395](gemma4_agent/voice/controller.py#L393-L395) | `_cancel_timer` no espera el timer thread previo | 🟡 | Sí, raro |
| [domain_tools.py:7140](gemma4_agent/domain_tools.py#L7140) | `datetime.utcnow()` deprecado | 🟡 | Sí en Python 3.13+ |
| [agent.py:1123-1152](gemma4_agent/agent.py#L1123-L1152) | `_compact_active_history_for_retry` puede dejar `tool_call_id` huérfanos | 🟠 | Solo en context overflow → retry → match exacto de límite |
| [domain_tools.py:1612](gemma4_agent/domain_tools.py#L1612) | `time.sleep(2.0)` en loop sin Event — comfy_result | 🟢 | Bloquea la tool 2s extra al cancelar |
| [tools.py:1305,1307,1328,1330,1476,1529,1538,2211,2925](gemma4_agent/tools.py#L1305) | `time.sleep` en handlers de tool — bloquean turno entero | 🟡 | Diseñado así (espera para GUI), pero si el usuario cancela tool, no hay forma |
| [semantic_router.py:104](gemma4_agent/semantic_router.py#L104) | `_STATE` global mutado sin lock | 🟡 | Carrera entre embed() concurrentes; resultado: `_ensure_loaded` puede llamarse 2x pero el segundo es idempotente |
| [agent.py:1594-1596](gemma4_agent/agent.py#L1594-L1596) | `_looks_like_context_overflow` precedencia: `"context size" in low and "exceed" in low` se evalúa después del `or`, no agrupado | 🟢 | Bajo: por precedencia, `A or B and C` == `A or (B and C)`. Aquí queda OK por casualidad |
| [profile_watcher.py:259](gemma4_agent/profile_watcher.py#L259) | Cambio de profile en mid-turn → env vars cambian durante request | 🟠 | Sí, opcional con auto-switch |
| [voice/wake.py:33,41](gemma4_agent/voice/wake.py#L33-L41) | `WAKE_PHRASES` y `WAKE_MIN_CONFIDENCE` declarados — solo MIN_CONFIDENCE usado. PHRASES nunca consultado | 🟢 | Constante muerta |
| [tools.py:3064](gemma4_agent/tools.py#L3064) | `TOOL_SCHEMAS` constante sin caller (el ToolRegistry usa `COMPOUND_TOOL_SCHEMAS`) | 🟢 | Legacy del primer prototipo |
| [voice/tts.py:51](gemma4_agent/voice/tts.py#L51) | `SENTENCE_END_RE` no incluye signos invertidos en posición intermedia bien — el regex agarra `[.!?;¡¿]\s` pero `¡Hola!` cierra en `!` final → OK al final pero `¡` al inicio nunca dispara cierre (correcto). En español los `¡¿` solo abren oración, no cierran | 🟢 | Diseño correcto |
| [ui/agent_thread.py:21](gemma4_agent/ui/agent_thread.py#L21) | `import time` no usado | 🟢 | Cosmético |
| [ui/main_window.py:1129](gemma4_agent/ui/main_window.py#L1129) | `if result == "started" or result == "external" or result == "already_running"` debería ser `in {...}` | 🟢 | Cosmético |
| [ui/main_window.py:223](gemma4_agent/ui/main_window.py#L223) | `self.worker.progress.connect(self._on_progress)` y `_on_progress` solo hace `pass` — overhead de signal por nada | 🟢 | Sin impacto medible |

---

## Capa 4 — Auditoría `voice/` (detallado)

**Firmas internas:** todas consistentes después del refactor. Caller↔callee
verificado:
- `_on_wake_detected(self, phrase, ts, wake_end_s=0.0)` —
  callers: `WakeDetector._on_wake` callback ([voice/wake.py:264-267](gemma4_agent/voice/wake.py#L264-L267))
  pasa `(matched, now, wake_end_s)`, ✅;
  `trigger_manual` ([voice/controller.py:222-224](gemma4_agent/voice/controller.py#L222-L224))
  pasa `("manual", time.monotonic(), 0.0)`, ✅;
  test_voice_state_machine pasa solo 2 args confiando en el default, OK.
- `transcribe_stream(audio_iter, prefix_audio=...)` — caller único en
  [voice/controller.py:421](gemma4_agent/voice/controller.py#L421), pasa los dos. ✅
- `feed_text(chunk)` — único caller [voice/controller.py:262](gemma4_agent/voice/controller.py#L262). ✅

**Teardowns:** `VoiceController.disable()` invoca correctamente
`self._tts.unload()`, `self._stt.unload()`, `self._wake.unload()`,
`self._audio.stop()`. Cada `unload` setea `_loaded=False` y libera el modelo.
🟡 **PERO**: `_stop_stt_thread()` solo espera 0.5s, así que si Whisper está
corriendo (típicamente 1-3s), el thread sigue alive en background y eventualmente
escribe a `_on_partial`/`_on_final` que apuntan a callbacks de un controller
ya destruido. Mitigación: el callback en `MainWindow._on_voice_final_main`
solo emite a signals; si el bridge fue `deleteLater`, la signal va a un objeto
muerto y Qt lo ignora. Riesgo bajo, pero feo.

**Estado THINKING colgado:** revisé. Hay tres caminos a `_on_reply` desde
`MainWindow`:
1. Reply normal → `_on_reply` llama `end_tts()` ✅
2. Reply con error → `_on_llm_error` llama `end_tts()` ✅
3. Worker crashea en mid-turn → la signal `state_changed` emite `"ERROR"`
   pero **`end_tts()` no se llama**. 🟠 El controller queda en THINKING para
   siempre hasta que el usuario haga clic en el mic. Fix: hookear el
   `state_changed == "ERROR"` y forzar `end_tts()` desde ahí.

**Cross-thread Qt signals:** todos los callbacks de `voice/` que vienen de
threads no-GUI pasan por `VoiceBridge.signal.emit()` ([main_window.py:914-918](gemma4_agent/ui/main_window.py#L914-L918)).
✅ Verifique cada callback:
- `on_state` → `bridge.state_changed.emit` ✅
- `on_partial` → `bridge.partial.emit` ✅
- `on_final` → `bridge.final.emit` ✅
- `on_failed` → `bridge.failed.emit` ✅

**RECURSOS:** `AudioCapture.stop()` cierra el stream + para el pump thread,
✅. `Piper out_stream.stop()` en `_run_worker.finally`, ✅. Vosk recognizer
referencia perdida → GC, OK.

**Hallazgo W-1 🟠**: `_on_voice_failed_main` solo loggea, NO llama `disable()`
ni `end_tts()`. Si el STT thread crashea (`on_failed = "stt crashed: ..."`)
y el state era TRANSCRIBING/THINKING, el controller queda colgado.
[ui/main_window.py:1075-1076](gemma4_agent/ui/main_window.py#L1075-L1076).

**Hallazgo W-2 🟡**: `_on_voice_state_main` hace `self.log.append(f"voice -> {state}")` para CADA cambio de estado. En un turno típico genera 6-8 líneas
nuevas en el log widget. Para sesiones largas eso es ruido visual.
[ui/main_window.py:1036](gemma4_agent/ui/main_window.py#L1036).

**Hallazgo W-3 🟡**: `_start_voice_controller` crea un `_Loader` QThread
local y lo guarda en `self._voice_loader` "to keep alive". Si el usuario
reenable voice (off → on → off → on), se crean nuevos loaders pero el viejo
puede no haberse limpiado si `loader.finished` no se disparó. Memory leak
acumulativo en sessions largas.
[ui/main_window.py:947-958](gemma4_agent/ui/main_window.py#L947-L958).

---

## Capa 5 — Auditoría `ui/` (detallado)

**Widgets sin destrucción:** `SettingsDialog`, `MemoryDialog`, `ToolExplorer`,
`TriggersDialog`, `SessionsPanel` se crean con `parent=self`/`parent=cw` así
que el GC de Qt los limpia al cerrar el MainWindow. ✅. Excepción notable:
`MemoryDialog` se crea NUEVO en cada `_open_memory()` sin guardar referencia
([main_window.py:585](gemma4_agent/ui/main_window.py#L585)) — Qt cleanup vía
parent funciona pero acumula dialogs si el usuario los abre repetidamente
sin cerrar el menú. Bajo.

**QThread instances:** revisé closeEvent
[main_window.py:1236-1263](gemma4_agent/ui/main_window.py#L1236-L1263):
- `self._metrics.stop()` ✅ pero sin join (ver bug #3)
- `self._profile_watcher.stop(timeout_s=2.0)` ✅ con join
- `self._server_boot_thread.wait(2000)` ✅
- `self._stop_voice_controller()` ✅
- `self.worker.stop(); self.worker.wait(1500)` ✅
🟡 `_voice_loader` QThread no se limpia explícitamente.

**Signal disconnect:** `_restart_worker` ([main_window.py:548-570](gemma4_agent/ui/main_window.py#L548-L570))
desconecta correctamente los 6 signals del worker viejo antes de crear el
nuevo. ✅. PERO: si `_restart_worker` se llama mid-turn, el viejo agent
sigue corriendo en su thread y solo "deja de emitir" al main thread (los
signals fueron desconectados). El thread no se joina porque `wait(2000)`
puede vencer antes. Resultado: dos agentes ejecutando tools simultáneamente
por hasta 2s, ambos tocando el mismo `state.json` (ver bug #4).

**`_apply_settings_live` vs persistencia:** [main_window.py:496-546](gemma4_agent/ui/main_window.py#L496-L546)
aplica persona, model_alias, agent_mode, max_turns, safety en vivo via
`dataclasses.replace`. ✅. Los settings de CONNECTION (server_url, model_path,
context_size, max_tokens) NO se aplican en vivo — requieren restart. La
GUI no advierte al usuario cuál es cual; "APPLY" guarda pero no aplica
algunos campos hasta restart. 🟡 confuso, pero el botón "RESTART AGENT"
aparece prominente.

**Coherencia TOGGLES tab ↔ env vars:** los toggles en
[ui/settings.py:38-48](gemma4_agent/ui/settings.py#L38-L48) escriben env vars
directamente con `apply_to_env` ([ui/settings.py:69-80](gemma4_agent/ui/settings.py#L69-L80)).
Los reads de toggles en runtime usan `_env_truthy` con el mismo env name.
✅. Excepción 🔴: la TRANSCRIPT tab (bug #1).

**Hallazgo U-1 🟡**: `SettingsDialog._on_apply` y `_on_restart` repiten el
mismo "gather + save + apply" pattern.
[settings.py:1111-1147](gemma4_agent/ui/settings.py#L1111-L1147). DRY,
pero refactor es bajo valor.

**Hallazgo U-2 🟡**: `_session_store` se crea con `try: from ..sessions import is_enabled as sessions_on; if sessions_on():`
[main_window.py:254-262](gemma4_agent/ui/main_window.py#L254-L262). Si la
env var `GEMMA4_AGENT_SESSIONS` cambia en runtime via Settings, el
session store NO se inicializa (la check fue solo al boot). Tendría que
restartear para activar sessions.

**Hallazgo U-3 🟢**: `_open_sessions` re-crea el `SessionsPanel` cada vez
si `self._sessions_panel is None`, lo cachea. ✅ Buena praxis.

---

## Capa 6 — Tests y cobertura

Total tests: **66 en test_gx_features.py** + **63 cases en test_router.py**
(`run()` los itera) = ~129 verificaciones.

| Test | Tipo | Riesgo | Notas |
|---|---|---|---|
| test_g4_subagent_with_mock_parent | mock-heavy | 🟡 | Valida la estructura del child agent, no su comportamiento — protege contra renames pero no contra bugs reales |
| test_audit_settings_env_names_match_config | static check | 🟢 | Bueno — atrapa drift entre Settings UI y AgentConfig |
| test_audit_atomic_write_replaces_existing | filesystem | 🟢 | Buen test funcional |
| test_voice_state_machine_wake_to_listening_to_transcribing | full mock | 🟡 | Mockea wake/stt/tts/audio. Valida estados — no la lógica de Whisper/Vosk |
| test_voice_state_machine_listening_timeout_5s | sleep-based | 🟡 | `_time.sleep(0.5)` con timeout patcheado a 0.2s. Frágil si CI es lento |
| test_profile_watcher_hysteresis | clock-mocked | 🟢 | Bien diseñado: usa `fake_clock` |
| test_stt_auto_fallback_to_base_when_slow | mock | 🟢 | Valida rollback explícito |
| test_external_server_detected_not_killed | psutil-dependent | 🟡 | Depende de que psutil pueda listar procesos en CI |
| test_g1_experience_record_and_recall | sqlite-vec dep | 🟡 | Si `sqlite_vec` no está instalado, test se skip o falla raro |
| test_h1_2_run_with_timeout_returns_on_hang | sleep 5s | 🟡 | Test que tarda >2s por diseño. Candidato a reducir timeout |
| Tests del router (63 cases) | text-based | 🟢 | Tests sin LLM, deterministic |

**Funciones públicas SIN test correspondiente** (Capa 4 y 5):
- `voice/wake.WakeDetector.unload` — sí cubierto indirectamente vía `test_voice_disabled_in_light_profile`
- `voice/tts.StreamingTTS.flush` — no test directo. Vía `feed_text` indirectamente
- `voice/tts.installed_voices` — no test
- `voice/audio_io.AudioCapture.snapshot_tail` — no test directo
- `voice/audio_io.list_input_devices` — no test
- `ui/metrics.SysMetrics` — no test
- `ui/agent_thread.AgentWorker` — solo importable test, no funcional
- `ui/hud.HudCanvas` setters — `test_u1_hud_state_setters` cubre algunos
- `ui/settings._gather_voice/_gather_profiles` — no test (riesgo de drift)

**Tests skip o `if __name__`**: ninguno con `pytest.skip` o `xfail`. `if __name__ == "__main__"` solo en main entries (correcto).

**Tests >2s candidatos a mock**: `test_h1_2_run_with_timeout_returns_on_hang`
(5s sleep), `test_voice_state_machine_wake_to_listening_to_transcribing`
(`sleep(0.3)` por timer real).

**Cobertura estimada (heurística, sin pytest-cov):**
- agent.py: ~60% (lógica principal sí; helpers de compactación parcial)
- voice/: ~75% (los 4 subsistemas + state machine cubiertos)
- ui/: ~15% (solo importable + hud setters)
- tools.py: ~20% (eval_smoke cubre status, no la lógica)
- domain_tools.py: ~5% (sin tests directos)
- planner.py: ~80% (router tests son extensos)

---

## Anexo — Métricas

| Métrica | Valor |
|---|---|
| LOC totales del paquete `gemma4_agent/` | 27,759 |
| LOC del paquete principal (sin `voice/` ni `ui/`) | 21,054 |
| LOC `voice/` | 1,681 |
| LOC `ui/` | 5,024 |
| LOC de tests (`test_gx_features.py` + `test_router.py` + `eval_smoke.py`) | 2,037 |
| Ratio test/código | ~7.3% |
| Pyright errors en `agent.py` / `voice/` / `ui/` | 0 |
| Pyright errors en `domain_tools.py` | 65 (mayormente `Optional` no chequeado) |
| Pyright errors en `tools.py` | 26 (idem) |
| Pyright errors fuera de `jarvis-*/` | 93 |
| Tests pasando reportados | 66 + router cases |
| Cobertura estimada total | ~30% |

---

## Notas finales

- No se modificó ningún archivo de código fuera de este reporte.
- El repo está más sano de lo que sugiere el volumen de notas: las 4 críticas
  son focales y arreglables en menos de medio día cada una.
- La mayor sorpresa positiva: pyright limpio en `agent.py`, `voice/` y
  `ui/`. La deuda de tipos está concentrada en `domain_tools.py` que es
  un archivo de funciones puras con dicts, donde el costo/beneficio de
  agregar TypedDicts es marginal.
- La mayor sorpresa negativa: el tab TRANSCRIPT existe, tiene controles
  funcionales, persiste valores — y no afecta nada del runtime.

---

## Fixes aplicados 2026-05-15

Tres commits separados aplican un subconjunto curado de los hallazgos:

- `de805ce` — Tanda A: voice/settings desconectados (3 fixes).
- `3f77637` — Tanda B: concurrencia y threads (5 fixes + 1 test nuevo).
- `<pendiente C>` — Tanda C: pulidos seguros (5 fixes + cleanup dead code).

### Hallazgos cerrados

| ID | Descripción corta | Commit |
|---|---|---|
| #1 | TRANSCRIPT tab guarda env vars muertas → eliminado el tab + su `_gather`. | de805ce |
| #2 | VOICE tab `stt_model`/`tts_voice` no se aplicaban → seteo `GEMMA4_VOICE_*` antes de instanciar controller + restart del controller cuando cambian mid-session. | de805ce |
| W-1 | `_on_voice_failed_main` no llamaba `end_tts()` → ahora se llama si state era TRANSCRIBING/THINKING. | de805ce |
| #3 | `SysMetrics.stop()` no joineaba el thread + `time.sleep` → reemplazado por `threading.Event.wait()` y join(2s). | 3f77637 |
| #4 | `AgentState`/`MemoryStore`/`SessionStore` RMW sin lock → `threading.RLock` por instancia. Test nuevo `test_audit_jsonstore_concurrent_writes` (10 threads concurrentes, todos los writes preservados). | 3f77637 |
| #5 | `profile_watcher` cambia env mid-turn → encolado en `_pending` y drenado por `_on_reply` post-último-chat. | 3f77637 |
| #7 | `_cancel_timer` no esperaba el timer thread previo → `join(0.1s)` antes de descartarlo. | 3f77637 |
| #8 | `_stop_stt_thread` join(0.5s) silencioso → callbacks nulificados primero, join sube a 5s, warning si no termina. | 3f77637 |
| #9 | `datetime.utcnow()` deprecado en `domain_tools.py:7140` → `datetime.now(timezone.utc)`. | Tanda C |
| W-2 | Spam de `voice -> {state}` en cada transición → solo se loggean IDLE_LISTENING/LISTENING/THINKING/SPEAKING/FAILED (transitions transients suprimidas). | Tanda C |
| W-3 | `_voice_loader` QThread leak en toggle off→on→off→on → cleanup del loader previo antes de crear el nuevo + cleanup en closeEvent. | Tanda C |
| U-2 | Sessions toggle requería restart → nuevo `_ensure_session_store()` invocado en boot y en `_apply_settings_live`. | Tanda C |
| Dead code | 12 imports/constantes unused eliminados (profiles.py `field`, routine_runner.py `Path`, ui/agent_thread.py `time`, ui/app.py `Path/QLabel/QVBoxLayout`, ui/main_window.py `QSize/QFont`, ui/metrics.py `re`, ui/panels.py 5 imports, voice/wake.py `os`/`WAKE_PHRASES`, voice/controller.py `ALL_STATES`, ui/theme.py `ANYDICT`+`Any`, tools.py `TOOL_SCHEMAS`). | Tanda C |

### Hallazgos abiertos (deliberadamente)

| ID | Descripción corta | Razón |
|---|---|---|
| #6 | `_run_with_timeout` deja threads zombie. | Sin evidencia de leak real en producción; fix completo es difícil (Python no permite kill thread). Aplicar solo cuando se detecte el leak. |
| #10 | `_compact_active_history_for_retry` puede dejar `tool_call_id` huérfanos. | Sin reproducción del case (requiere context overflow → retry → match exacto del límite). Riesgo alto/beneficio bajo sin un caso replicable. |
| Top 5 mejoras de arquitectura | Consolidar fold, extraer agent_history, JSONStore base class, SettingsPayload dataclass, ACTION_ENUMS inline. | Refactor explícitamente fuera de scope; "bugs primero, arquitectura después". |
| Top 5 NO tocar | SYSTEM_PROMPT, los 28 `except: pass`, COMPOUND_TOOL_SCHEMAS, timeouts hardcoded de voice/, domain_tools.py como reestructuración. | Funcionan y refactor es riesgo gratis. |
| 9 hallazgos verdes (🟢) | Cosméticos puros (`A or B and C` precedencia, `result in {set}` vs múltiples `or`, comment del SENTENCE_END_RE, etc). | Costo de commit > beneficio cero. |
| Tests >2s candidatos a mock | `test_h1_2_run_with_timeout_returns_on_hang` (5s sleep), `test_voice_state_machine_*` (sleep(0.3)). | Trade-off conocido; los tests verifican comportamiento de timeout real, no mockeado. |

### Validación post-fixes

- Pyright en `agent.py`/`voice/`/`ui/`/state/memory/sessions/profile_watcher/profiles/routine_runner: **0 errors**.
- `tools.py` y `domain_tools.py` siguen con sus 26+65 errores de tipos pre-existentes (Optional no chequeado, pycaw COM types). Sin cambios en ese frente.
- Tests: **67/67 passing** (66 originales + nuevo `test_audit_jsonstore_concurrent_writes`).
- `test_profile_watcher_hysteresis` actualizado para reflejar el nuevo contrato (drain explícito vía `apply_pending()`).
