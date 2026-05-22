# Reporte de sesión overnight — Gemma4 Agent — 2026-05-21

Continuación de la auditoría arquitectura/fiabilidad/latencia (rondas 1–10
previas, 21 bugs). Esta sesión: **ronda 11 (5 bugs) + suite de smokes + validación
en vivo**. RED dejó la PC con recursos; usé los que eran seguros (CPU) y diferí
los GPU-dependientes porque la GPU tenía 6.7 GB en uso con el usuario jugando.

## Resumen ejecutivo

- **Ronda 11 cerró el ciclo de vida del llama-server (LlamaServerManager) y el
  ciclo enable/disable de la VOZ** — superficies nunca auditadas como unidad.
  5 bugs reales, TODOS lifecycle/teardown (el patrón confirmado por 6ª vez).
- El más grave en fiabilidad: **nadie detenía el llama-server al salir** → modelo
  huérfano reteniendo ~6 GB VRAM en Windows, y el próximo arranque lo veía
  'external' y se negaba a gestionarlo. Contradecía directamente el invariante
  "liberar VRAM" del producto.
- **18 smokes** (<1.5 s, sin GPU) como tripwire de regresión, uno por fix ganado.
- **Validación en vivo (6/7):** confirmé con números reales el 74 % menos CPU del
  wake throttle, los timeouts per-mode, la rotación de telemetry, la compaction de
  10 MB, cero memory-growth, y cero leak de handles. **Ninguna afirmación previa
  resultó falsa al medirla.**

## Fixes nuevos (ronda 11)

| commit | finding | test | módulo | eje |
|--------|---------|------|--------|-----|
| 7f22ae4 | start() filtraba 2 file handles del child-log por restart (parent copy nunca cerrada; peor en spawn-fail) | test_llama_server_log_handles (3) | llama_server.py | FIABILIDAD |
| f50dfc1 | nadie detenía el llama-server al exit (huérfano, 6 GB VRAM) + get_shared_manager sin lock (race de boot multi-thread) | test_shared_manager_lifecycle (5) | llama_server.py | FIABILIDAD + ARQUITECTURA |
| 13aa71f | download_voice dejaba .onnx truncado en corte de red → TTS bricked | test_tts_download_atomic (2) | voice/tts.py | FIABILIDAD |
| 5ddd89b | pipeline.stop() no reseteaba el state machine → comando FANTASMA tras stop/start | test_voice_pipeline_stop_reset (3) | voice/pipeline.py | FIABILIDAD |
| 3e918c5 | TTS mudo tras ciclo voz off/on (worker muerto, enable no re-arrancaba) | test_voice_runner_tts_reenable (2) | voice_runner.py | FIABILIDAD / UX |
| 8422dd6 | (bonus) middle_ellipsis crecía +3 en límite chico — tightened a STRICTLY <= limit | test_smoke_overnight | agent_compaction.py | LATENCIA |

Dos veces el test atrapó un bug en mi propio fix antes de commitear (NameError
`_threading` vs `threading`; verdict-logic en el probe de leak). Confirma el valor
de escribir el test junto al fix.

## Módulos auditados esta sesión

| módulo | resultado | observación / eje |
|--------|-----------|-------------------|
| llama_server.py | **2 FIX** | lifecycle del proceso server (handles + atexit + lock). El resto (detect_crash_signature, force_restart, _wait_for_health) limpio y acotado. |
| voice/tts.py | **1 FIX** | download atómico. is_busy/tail-grace ya bien (rondas previas). |
| voice/pipeline.py | **1 FIX** | stop() reset. El hot loop (_on_chunk dispatch try/except, state machine single-thread) SÓLIDO. |
| voice_runner.py | **1 FIX** | re-enable del TTS worker. feed_tts/flush_tts/_is_tts_busy bien. |
| voice/stt.py | LIMPIO | guard de audio vacío (round 2) + transcribe envuelto. Download delegado a faster-whisper. |
| agent_runner.py (boot/submit) | LIMPIO | boot daemon con try/except por etapa; usa get_shared_manager (toma el fix). _inbox unbounded → ver questions #4. |
| launcher.py (run_ui/start_server) | LIMPIO | shutdown de uvicorn ordenado; el server lo arranca el shared manager (toma el atexit). |
| server.py (voice endpoints) | LIMPIO | /voice/start|stop wirean callbacks bien; el reset del pipeline (mi fix) cubre el ciclo. |

## Resultados de Fase 3 (validación en vivo) — números reales

| exp | medición | veredicto |
|-----|----------|-----------|
| wake CPU throttle | N=1: 25.81 s · N=4: 6.69 s por 30 s audio → **74.1 % menos** | ✅ |
| per-mode timeout | fast 20 s → research 150 s, monótono, cableado agent.py:1042/1068 | ✅ |
| boot real | — (GPU en uso + usuario jugando) | ⏸️ diferido |
| compaction 10 MB | 2.9 ms, 10 MB → 3.5 KB | ✅ |
| telemetry 100 k | rotate poda 50 k en 49 ms, summarize 16 ms | ✅ |
| memory growth | 0.0 MB sobre 50 k ops del hot-path | ✅ |
| log-handle leak | peak open_files baseline+2 en 30 restarts (psutil) | ✅ |

Detalle en `bench/overnight_validation.md`. Probe reproducible en
`bench/_wake_cpu_probe.py`.

## Acumulado total de la auditoría

- **Bugs reales fijados:** 21 (rondas 1–10) + 5 (ronda 11) = **26 en 11 rondas**.
- **Tests nuevos esta sesión:** 18 smokes + 15 por-fix = **33 tests** nuevos.
- **Regresión:** batch final 88 + 74 = **162 passed, 0 rojos** en los módulos
  tocados + sus dependientes.

## Mapa de cobertura por eje

- **ARQUITECTURA:** hot-path del turno (dispatch, verifiers, server HTTP, EventBus,
  vad/audio_io, state, boot daemons) auditado limpio en rondas previas. Singletons
  lazy (semantic_router, reranker, tool_head, abstain_head, mcp_server,
  **+shared_manager esta sesión**) todos con double-checked locking. **Alto.**
- **FIABILIDAD:** persistencia (state, experience, telemetry), recovery (server
  reload, DB corruption), teardown (playwright, **+log-handles, +server atexit,
  +pipeline reset, +tts re-enable esta sesión**) cubiertos. **Alto.**
- **LATENCIA:** hot-path slimming, per-mode timeout, wake throttle (validado),
  compaction (validado). **Alto** en lo medible sin GPU; **falta el E2E con server
  real** (boot, TTFT, cache-reuse en vivo) — el único hueco grande, por la
  restricción de GPU.

## Próximos pasos sugeridos para cuando RED vuelva

1. **Validar el boot E2E con GPU libre** (Exp 3 diferido): tiempo a primera
   respuesta, boot_progress stages, cache-reuse de Gemma en vivo (--swa-full).
2. **Resolver `gemma4_agent/ContextoClaude.md`** (questions #2): gitignore o commit.
3. **Considerar bound en `_inbox`** solo si aparece el síntoma de flood (questions #4).
4. La auditoría de bordes (lifecycle/teardown) está prácticamente agotada: 6 rondas
   seguidas confirmaron que el hot-path está sólido y los bugs viven en los bordes.
   El siguiente filón de mayor valor es la **validación E2E con server real**, no
   más lectura estática.

## Verificación de procesos limpios (cierre)

```
llama-server: none
node.exe:     none
```
No dejé NINGÚN proceso colgado (nunca levanté el server pesado, por la restricción
de GPU). git status limpio salvo el ContextoClaude.md pre-existente (no mío).
