# Baxy — Arquitectura (verificada por la auditoría 2026-05-21)

> Nota: el proyecto se llama ahora **Baxy** (antes Gemma 4 Agent, brevemente Carter).

Este documento captura la arquitectura que la auditoría de tres sesiones
(rondas 1–13 + continuación + cierre) **verificó leyendo el código y midiendo en
vivo** — no es diseño aspiracional. Su propósito: que quien lea la rama entienda
las capas, los invariantes que cada una garantiza, y el patrón que explicó dónde
vivían los 27 bugs reales.

> **Norte rector del proyecto (orden de prioridad ante conflicto):**
> 1. **Arquitectura** — invariantes preservados, hot-path limpio, dispatch como
>    contenedor de blast radius, lifecycle/teardown completo.
> 2. **Fiabilidad / calidad** — nunca crashear el turno, perder un reply,
>    corromper persistencia, dejar huérfanos, ni degradar en silencio.
> 3. **Latencia** — hot-path y always-on rápidos; I/O crítica con timeout; lo
>    costoso off-path / cacheado / decimado.

---

## El patrón que la auditoría confirmó (9 veces)

**Los 27 bugs reales vivieron en los BORDES — nunca en el camino feliz.**

Persistencia, recovery, daemons de background, teardown/lifecycle, primitivos
puros con edge cases, y diagnósticos. NUNCA en el dispatch del turno, los
verifiers, el servidor HTTP, el EventBus, ni el real-time de audio (vad/audio_io).

**Por qué:** el hot-path se diseñó cuidando los tres ejes (try/except por tool,
timeouts, slimming, recovery del server). Los bordes — código que corre fuera del
camino feliz (un restart, una corrupción de DB, un shutdown, un input raro) — no
recibieron ese cuidado y por eso no se ejercitaban. La auditoría los cerró con el
mismo criterio.

**Implicación para el futuro:** un cambio nuevo es de bajo riesgo si vive en el
hot-path ya blindado; es de ALTO riesgo si toca un path de lifecycle/recovery/
teardown. Ahí es donde hay que poner tests.

---

## Mapa de capas

```
┌─────────────────────────────────────────────────────────────────────┐
│  SUPERFICIES (entrada)                                                │
│  launcher.py · server.py (FastAPI/uvicorn) · chat.py (CLI) · mcp_server│
└───────────────┬───────────────────────────────────┬──────────────────┘
                │                                     │
        ┌───────▼────────┐                   ┌────────▼─────────┐
        │ ALWAYS-ON AUDIO │                   │  HOT-PATH TURNO   │
        │ audio_io→vad→   │  comando (texto)  │  agent.run_content│
        │ wake→pipeline   │ ───────────────►  │  → router → LLM   │
        │ (voice_runner)  │                   │  → dispatch tools │
        └───────┬─────────┘                   │  → verifiers      │
                │ TTS (Piper)                  │  → reply          │
                ▼                              └───┬───────┬───────┘
           speakers                                │       │
                                         ┌──────────▼──┐ ┌──▼──────────┐
                                         │ PERSISTENCIA │ │ DIAGNÓSTICOS │
                                         │ state/exp/   │ │ tracing/     │
                                         │ telemetry/   │ │ telemetry/   │
                                         │ sessions     │ │ log_recorder │
                                         └──────────────┘ └─────────────┘
        ┌────────────────────────────────────────────────────────────┐
        │ DAEMONS / LIFECYCLE: llama_server (LlamaServerManager),       │
        │ profile_watcher, agent_runner boot, EventBus, boot_progress   │
        └────────────────────────────────────────────────────────────┘
```

---

## Invariantes por capa (qué NUNCA debe pasar)

### Hot-path del turno (`agent.run_content` → dispatch → verifiers)
- **Blast radius contenido (r1):** cada tool corre envuelta en try/except
  (`ToolRegistry.execute`) Y dentro de `_run_with_timeout` (que también captura
  Exception). Una tool que crashea o cuelga se vuelve `{ok:False,error}` + timeout
  por tool — NUNCA aborta el turno.
- **Per-mode timeout (r1):** el call al LLM pasa `timeout_s=mode.request_timeout_s`
  (20–150s según el presupuesto de tokens) en el call principal Y el retry. Sin
  esto, un turno colgado heredaba 180s × 8 turnos = ~24min de freeze.
- **Reply nunca destruido (r9):** la enrichment cosmética post-LLM (mission footer)
  va en try/except — un bug post-LLM no tira abajo una respuesta ya generada.
- **Recovery del server (auditado limpio):** `llm_client._post_chat_with_recovery`
  hace health-poll + 1 retry en connection-reset (server reload).

### Always-on de audio (`audio_io` → `vad` → `wake` → `pipeline`)
- **El callback de audio nunca bloquea (limpio):** PortAudio solo hace copy +
  put_nowait (drop-on-full); el consumidor corre off-callback.
- **Wake decimado (r8, LATENCIA):** `predict()` corre cada Nth chunk (~8Hz, no
  31Hz) → ~74% menos CPU idle (medido), sin perder recall (ventana de 2s muestreada
  ~16×). El ring buffer se actualiza CADA chunk.
- **Silence gate (r-voz):** Whisper alucina sobre silencio; un piso de RMS +
  detector de alucinaciones canónicas dropea capturas vacías → `NO_SPEECH` (no
  drop silencioso).
- **Lifecycle de la voz limpio (r11):** `pipeline.stop()` resetea el state machine
  (no comando fantasma tras stop/start); `enable()` re-arranca el worker de TTS
  (no queda mudo tras un ciclo off/on).

### Persistencia (`state` / `experience` / `telemetry` / `sessions`)
- **Escritura atómica:** `state` y `sessions` usan `atomic_write_json` (os.replace)
  — nunca un JSON truncado.
- **Recovery de corrupción (r4):** `experience` pone en cuarentena una DB
  malformada (`.corrupt-<ts>`, cerrando la conexión antes para evitar WinError 32)
  y recrea una fresca. Fail-loud SOLO para schema-drift (RuntimeError).
- **Crecimiento acotado (r6):** `telemetry.rotate()` corre una vez por proceso →
  poda rows > 30 días (medido: poda 50k en 49ms, queries siguen <16ms).
- **Descarga atómica (r11):** `tts.download_voice` baja a `.part` + os.replace —
  un corte de red no deja un `.onnx` truncado que brickee el TTS.

### Daemons / lifecycle (`llama_server` / `profile_watcher` / boot)
- **Sin huérfanos (r11):** el llama-server gestionado se detiene en `atexit`
  (en Windows el hijo de Popen no muere con el padre → retendría 6GB VRAM). El
  atexit SOLO toca el server gestionado — NUNCA mata uno externo del usuario.
- **Singletons lazy thread-safe (r2/10/11):** encoder ST, reranker, tool_head,
  abstain_head, mcp registry, shared server manager — todos con double-checked
  locking. Sin esto, warmup (daemon) + primer turno hacían double-load y, en el
  router, inflaban el attempt_count que lo mataba.
- **Handles cerrados (r11):** `LlamaServerManager` cierra las copias parent de los
  log-handles del child en stop()/restart (medido: open_files vuelve a baseline).
- **Profile switch reinicia el server (r3):** cambiar de perfil VRAM hace
  force_restart (no solo setea env vars) — el downgrade "liberar VRAM para el
  juego" es real, no cosmético.

### Diagnósticos (`tracing` / `telemetry` / `log_recorder` / `loop_detection`)
- **Nunca crashean lo que observan (r6/7):** tracing deshabilita ante un path
  inescribible/malformado (OSError o ValueError) en vez de crashear el constructor;
  `event()` swallowa errores de write/encode; el loop-detector no raisea con args
  de keys mixtas. Diagnóstico que tumba el turno = bug.

### Bus de eventos (`events_bus`)
- **Nunca bloquea al publisher (limpio):** snapshot de listeners/subscribers bajo
  lock, invocación SIN lock (un listener reentrante como log_recorder no
  deadlockea); subscriber lleno → drop-oldest, cola bounded.

---

## Flujo de un turno (texto)

```
usuario  →  run_content(content)
              │
              ├─ MissionGoal.from_user_text   (regex, try/except → fallback)
              ├─ choose_mode(content)         (fast_action … research)
              ├─ ROUTER: intent_router (semántico, embed cacheado LRU) +
              │          semantic_router (top-k tools)  → selected_tool_names
              ├─ _system_message(selected)    (prompt slim; microagents CACHEADOS;
              │                                 ~1.06ms warm)
              │
              ├─ LLM call (timeout = mode.request_timeout_s)   ──► llama-server
              │     └─ _post_chat_with_recovery (health-poll + 1 retry on reset)
              │
              ├─ ¿tool_calls?  ──► dispatch:
              │      por cada call:  _run_with_timeout( execute(name,args) )
              │            execute: validate → classify (confirm?) → impl()  [try/except]
              │            verifier: verify_core.verify(...)  [try/except → confirmed F/None]
              │      (loop hasta max_agent_turns, con loop-detection guard)
              │
              ├─ summary pass (thinking off, schemas removidos → slim)
              ├─ sanitize_text(reply)         (quita <think> sin cerrar / <|...|>)
              ├─ mission footer                (try/except → no destruye reply)
              └─ AgentReply  →  (voz: feed_tts + flush_tts → Piper)
```

Cada flecha que cruza a un proceso/disco/modelo tiene su contención: timeout,
try/except, o recovery. Eso es lo que mantiene los tres ejes en el camino feliz.

---

## Adiciones recientes (2026-06-07 → 2026-06-10) — ancladas a su capa

Cambios posteriores a la auditoría base, ubicados en el mapa de capas. Ninguno
movió un invariante; varios añadieron módulos hermanos (el ratchet anti-archivo-dios
lo fuerza).

**Hot-path / routing**
- **Encoder del router reentrenado** con seed fija (reproducible) + ejemplos de
  preguntas culturales→web. Resolvió que "¿conocés a X?" se rutee a conocimiento
  en vez de a `media`. Recall holdout sin degradar (0.9820). Gate por idioma.
- **Honestidad reforzada**: el guard de turno-sin-acción regenera una respuesta de
  conocimiento (en vez de mentir "ya lo hice") y el detector estructural cubre el
  perfecto compuesto / presente continuo ("he reproducido", "estoy escuchando").
- **Geometría de ventana**: "maximiza/minimiza la app X" retira la tool homónima
  (steam/browser/app) del subset y deja `window` — antes el LLM inventaba un
  action inexistente.

**Latencia (fast-paths in-process, reemplazan spawns de PowerShell/WMI)**
- `system_info_fast`, `screenshot_fast`, `uia_fast`, `media_now_playing_fast`:
  lecturas de estado del SO por psutil/ctypes/winsdk/registro en vez de
  `subprocess` (1-2.5s → ms). Caches TTL para lo estable; warmup en boot para lo
  caro-en-frío. Búsqueda web con timeout duro.

**Módulos extraídos del hot-path (mismo patrón sibling+shim)**
- `agent_core/reply_repair.py`, `agent_core/agent_helpers.py`,
  `agent_core/latency_helpers.py`, `tools_pkg/site_resolver.py`,
  `tools_pkg/web_search.py`, `tools_pkg/web_source_quality.py`,
  `tools_pkg/visual_click_redirect.py`, `domain_tools/media_current.py`.

**Seguridad / configuración**
- **Política de confirmación** ampliada: `GEMMA4_CONFIRMATION_POLICY` ∈
  {confirm_risky (default), never, always, **all** (permisivo total)}. Toggle en
  settings. El invariante "irreversible se confirma bajo cualquier política" lo
  rompe a propósito SOLO el modo `all` (opt-in explícito).
- **STT solo-Parakeet**: `GEMMA4_STT_NO_FALLBACK` apaga el fallback a Whisper en
  los dos puntos del pipeline — si Parakeet no carga, la voz falla limpio.

**Tooling de tests**
- **Guard de suite global**: conftest RAÍZ del repo + `_suite_guards` neutralizan
  os.startfile/webbrowser/subprocess-de-apertura para que NINGÚN test abra apps,
  desde cualquier dir, sin flag. Las lecturas pasan reales.

---

## Tabla de correcciones acumuladas (27 bugs + 1 perf)

| ronda | fix | eje | invariante que protege |
|-------|-----|-----|-------------------------|
| 1 | per-mode LLM timeout | latencia+fiab | turno no se cuelga 24min |
| 1 | silent-drop → NO_SPEECH | UX | no degradar en silencio |
| 2 | locks en lazy loaders (ST/reranker/heads) | arquitectura | no double-load / router vivo |
| 2 | STT guard audio vacío | fiabilidad | no decode degenerado |
| 3 | profile_watcher reinicia server | fiab+lat | downgrade VRAM real |
| 3 | loop_detection no crashea | fiabilidad | safety-net no tumba turno |
| 3 | vision-recycle re-dispara | fiabilidad | no leak de mmproj |
| 4 | experience recupera de corrupción | fiabilidad | memoria no se rompe "para siempre" |
| 5 | playwright pw.stop() en atexit | fiabilidad | sin driver node huérfano |
| 6 | telemetry.rotate() one-shot | arq+lat | crecimiento acotado |
| 6 | chat spinner broken-pipe guard | UX | CLI no spamea traceback |
| 7 | middle_ellipsis no crece (text[-0:]) | latencia | anti context-overflow |
| 7 | sanitize <think> sin cerrar + control tokens | UX | no markup al usuario |
| 7 | tracing failsafe (mkdir/event) | fiabilidad | diagnóstico no crashea turno |
| 8 | wake throttle 31→8Hz | latencia | −74% CPU idle (medido) |
| 9 | mission footer no destruye reply | fiabilidad | reply ya generado sobrevive |
| 10 | mcp registry lock | arquitectura | singleton thread-safe |
| 10 | redact_sensitive no crashea (numpy) | fiabilidad | safety-path robusto |
| 11 | llama-server log handles cerrados | fiabilidad | sin leak de handles |
| 11 | llama-server stop en atexit + lock | fiab+arq | sin huérfano 6GB VRAM |
| 11 | tts download atómico | fiabilidad | sin .onnx truncado |
| 11 | pipeline.stop() resetea state machine | fiabilidad | sin comando fantasma |
| 11 | TTS worker re-arranca en re-enable | fiab/UX | no queda mudo |
| 12-13 | (2 rondas LIMPIAS) | — | hot-path confirmado sólido |
| cont. | tracing disabilita en path malformado | fiabilidad | constructor no crashea |
| cont. | **cache de microagents** | **latencia** | **−49% _system_message (perf)** |

(Las 21 primeras correcciones de las rondas 1-10 se detallan en la audit memory
`project_arch_audit_2026_05_21.md`.)

---

## Trampas concretas del repo (de CLAUDE.md, confirmadas)

- **ONNX Runtime congela la PC** sin throttle (busy-wait). Usar
  `scripts/_ort_throttle.py` antes de cargar modelos en loops pesados.
- **Wake LiveKit espera la frase al FINAL** de la ventana de 2s (paddear al inicio).
- **VoxCPM segfaulta en RTX 40-series** → usar `piper_vits` para TTS de training.
- **Python 3.10 runtime vs 3.11 training** → no importar `livekit` en runtime.
- **YAML con paths Windows** → comillas simples (escapes `\h`/`\t`/`\u`).
- **`pytest -k <glob amplio>`** crashea nativo (torch/onnx/sounddevice) en Windows
  → correr archivos por nombre. El full-suite por batches corre limpio.
