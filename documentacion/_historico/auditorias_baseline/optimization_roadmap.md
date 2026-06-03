# Optimization Roadmap — Fases 2 y 3

- **Branch**: `feature/gemma4-optimization-roadmap`
- **Fase 1**: APPLIED (10/10 items). Ver `optimization_log.md`.
- **Este doc**: decisiones pendientes (Fase 2) + investigación a 90 días (Fase 3).

---

## Fase 2 — Decisiones de producto pendientes

Cada item requiere visto bueno del producto antes de aplicar. Resumen de pros/cons
del informe externo + estado actual del repo.

### 2.1 — Cambiar default de `balanced` a `unsloth/gemma-4-E4B-it-GGUF:UD-Q4_K_XL`

**Estado actual**: `balanced` apunta a `gemma-4-E2B-it-Q5_K_M.gguf` (4.70 GB VRAM cargada,
+KV F16 8K ≈ 5.10 GB total, holgura ~0.9 GB sobre 6 GB nominales).

**Propuesta del informe (Item I1 #2 / A1)**:
- Cambiar a `unsloth/gemma-4-E4B-it-GGUF:UD-Q4_K_XL` (~4.7 GB en disco).
- VRAM estimada por el informe: **~5.6–5.9 GB sin mmproj, ctx 4K**.
- Mejora esperada en Carter: **+1–2 pp** por subir de E2B (75–82 % proyectado) a E4B (85–90 % proyectado).

**Tensión real**:
- Con la reserva WDDM de 1.5 GB aplicada en 1.2, **VRAM efectiva en 6 GB físicos = 4.5 GB**.
- E4B-UD-Q4_K_XL a 4.7 GB peso → con KV F16 ctx 4K (~0.35 GB) ≈ **5.05 GB total app** vs **4.5 GB efectiva** = **NO entra**.
- Solo entraría bajando ctx a 2K (KV ~0.17 GB → 4.87 GB total app, todavía borde) o aceptando KV q8_0 (que el informe explícitamente desaconseja en TL;DR-6).

**Pros del cambio**:
- Calidad mensurable mayor (E4B > E2B en Carter proyectado).
- Modelo UD (Pareto frontier según localbench + Unsloth bench).

**Cons**:
- Requiere bajar GGUF (~4.7 GB) que el usuario aún NO tiene en disco.
- VRAM cabe sólo si re-medimos en RTX 3050 6 GB real con flags actuales (`--keep -1 --no-mmap --flash-attn on`).
- El informe avisa que la VRAM medida del cliente para E4B-Q4_K_M era 6.10 GB (en RTX 4060 Ti 16 GB sin reserva WDDM); en RTX 3050 6 GB con reserva podría no entrar.

**Decisión propuesta** (esperando ack del dev):
- (a) **Conservador**: mantener E2B-Q5_K_M en balanced. Si el usuario tiene 8 GB+, recommend_profile devuelve balanced igual; en 8 GB físicos = 6.5 GB efectivos = E4B-UD-Q4_K_XL entra cómodo. Crear un perfil intermedio `balanced-8gb` que use UD-Q4_K_XL.
- (b) **Agresivo**: bajar GGUF + medir en RTX 3050 6 GB real + decidir. Si entra: cambiar balanced default. Si no entra: opción (a).

Recomendación: **(b)** — el informe dice que es el cambio I1 #2, el más impactante de los "bajo riesgo + alta ganancia". Pero el dev tiene que decidir cuándo bajar el archivo.

### 2.2 — Activar speculative decoding E2B-draft → E4B/26B-A4B-target

**Estado actual**: no implementado.

**Propuesta del informe (Bloque D3)**:
- Solo viable en perfil `performance` con VRAM ≥ 12 GB.
- En RTX 3050 6 GB E2B(1.85 GB) + E4B(5.6 GB) = 7.45 GB → **NO entra**.
- En 8 GB borde, 12 GB+ confortable.
- Acceptance rate estimado por el informe: 40–60 % en Carter (sin medir).
- **Advertencia importante**: bench externo `hackmd.io/...` muestra que en RTX 3090 con Qwen3.6-35B-A3B speculative resulta MÁS LENTO (139.9 → 65.0 tok/s). Engine + spec-method de llama.cpp en consumer Ampere puede degradar.

**Decisión propuesta**:
- Feature-flag **off-by-default**. Implementar `--spec-draft-model` opt-in en `llama_server.py` cuando `GEMMA4_SPEC_DRAFT=path/al/gguf` esté seteado.
- Antes de promover a default: A/B con `llama-bench --model-draft` en la máquina del dev (RTX 4060 Ti 16 GB).
- Si acceptance < 50 %, dejar permanentemente off.

Recomendación: **implementar como feature-flag opt-in** (estimado 1 día). El A/B se hace en la siguiente sesión cuando haya tiempo de bench.

### 2.3 — Backend Parakeet-TDT-0.6B-v3 como alternativa a Whisper-small

**Estado actual**: STT primario es faster-whisper. Backend único.

**Propuesta del informe (Bloque E5)**:
- `nvidia/parakeet-tdt-0.6b-v3` (600M params, 25 idiomas europeos incluido español, RTF muy alto, RNN-T optimizado streaming).
- **Licencia**: NVIDIA Community Model License → requiere revisión legal del dev.
- Requiere dependencia nueva pesada: `nemo-toolkit` o equivalente. Esto **rompe la restricción "cero deps nuevas pesadas"** del brief.

**Decisión propuesta**:
- **DEFERRED**: marcar en `voice/stt.py` como TODO. Re-evaluar cuando el dev:
  - (a) revise licencia NVIDIA CML.
  - (b) acepte la dep nueva (~1 GB de wheels NeMo).
  - (c) tenga set Common Voice 17 es-MX para A/B con jiwer.

Recomendación: **mantener Whisper en producción**. Parakeet es upside futuro, no urgente.

### 2.4 — Backend Kokoro-82M-es como alternativa a Piper TTS

**Estado actual**: TTS primario es Piper VITS+ONNX.

**Propuesta del informe (Bloque E6)**:
- Kokoro-82M v1.0, Apache 2.0 (licencia friendly), español soportado.
- Latencia primer chunk CPU: ~600–1200 ms vs Piper <300 ms.
- Calidad subjetiva mayor (no medido formalmente).

**Decisión**:
- El brief dice "cero deps pesadas". Kokoro requiere `kokoro-onnx` o similar.
- Latencia +500 ms viola el objetivo "≤1 s primer fonema".

Recomendación: **DEFERRED** indefinidamente. Re-evaluar si el dev recibe feedback de usuarios pidiendo voz más natural.

---

## Fase 3 — Roadmap a 90 días (no ejecutado en esta sesión)

Tomo los 13 sprints del informe (Bloque I3) y los adapto al estado actual
post-Fase 1.

### Sprint 1 (días 1–7) — "Inyección de tool schemas EXACT al system prompt"
- **Bloqueante**: tocar `agent.py:388` para concatenar `compile_tools_to_markdown_exact()` después de mode_hint.
- Como `agent.py` está bajo constraint duro, esto requiere desbloqueo del dev.
- **Entregable**: una línea de código + bench A/B en Carter 540 (`pass_rate baseline` vs `pass_rate con schemas EXACT`).
- **Mejora esperada**: +2–4 pp Carter (cita Daniel Farina gist).

### Sprint 2 (días 8–14) — "Quant upgrade balanced"
- Decisión 2.1 resuelta.
- Si afirmativo: bajar UD-Q4_K_XL, medir VRAM real RTX 3050 6 GB (si no se tiene, hacer en máquina del dev simulando con `nvidia-smi` antes/después).
- **Entregable**: profile `balanced` con default decidido + reporte A/B.

### Sprint 3 (días 15–21) — "Bench Carter 540 con Q4_K_M y Q5_K_M"
- Hoy 99.81 % está medido con E4B-Q6_K (modelo del dev).
- Para tener números reales del modelo objetivo de producción, correr Carter 540 con:
  - E4B-Q4_K_M (lo que se usaría en 6 GB sin UD).
  - E2B-Q5_K_M (default actual de balanced).
- Toma horas; correr overnight.
- **Entregable**: pass_rate por GGUF en doc actualizada.

### Sprint 4 (días 22–28) — "Wiring del callback vision_relaunch"
- Item 1.7 dejó listo el counter + recycle method, pero **el callback no está registrado** por el orchestrator.
- En `agent_runner.py`, donde se crea `LlamaServerManager`, persistir la referencia y registrar:
  ```python
  set_vision_relaunch_callback(lambda n: manager.recycle_for_vision_leak())
  ```
- **Entregable**: feature funcional end-to-end + test de integración (40 image_parts → recycle event).

### Sprint 5 (días 29–35) — "Streaming SSE de tool calls — verificación"
- El informe (Bloque D4) confirma que SSE funciona post-PR #21418. El cliente ya soporta SSE.
- Validar empíricamente que multi-tool calls intercalados con thoughts (`<|think|>`) llegan correctamente.
- **Entregable**: integration test con prompt forzando interleaved.

### Sprint 6 (días 36–42) — "Endpoint REST `/agent/restart`"
- Para casos de mmproj leak acumulado sin tener que matar la app.
- Bloque "Bonus Quick Wins UX #6" del informe.
- **Entregable**: endpoint en `server.py` + botón en UI Field.

### Sprint 7 (días 43–49) — "Pre-warm KV con system prompt al startup"
- Item I1 #4 del informe.
- Mientras #21468 esté roto, el primer turno frío con 30K+ tokens (system + 62 tools) tarda 60–90 s.
- Pre-warm en pantalla de splash convierte eso en "esperá un minuto al primer arranque" en lugar de "esperá cada turno".
- **Entregable**: hook al final de boot que envía un "ping" sintético al LLM.

### Sprint 8 (días 50–56) — "Re-evaluar PR #22288 (cache-reuse Gemma 4)"
- Si merged: cherry-pick build, remover el comentario sobre #21468 en `llama_server.py`, medir TTFT antes/después.
- **Entregable**: decisión binaria + reporte de speedup si aplica.

### Sprint 9 (días 57–63) — "Re-evaluar PR upstream para MTP drafters"
- Discussion #22735 al 2026-05-08 no tenía PR mergeado.
- Si entra: implementar MTP en perfil `performance` (12 GB+).
- Mejora esperada: 2–3× tok/s lossless según Google.
- **Entregable**: decisión binaria.

### Sprint 10 (días 64–70) — "Speculative decoding E2B→E4B en 8 GB+"
- Decisión 2.2 resuelta.
- Si afirmativo: implementación + A/B Carter.

### Sprint 11 (días 71–77) — "Telemetría local opt-in"
- Item I4 del informe. SQLite local en `%LOCALAPPDATA%/gemma4_agent/telemetry.sqlite`.
- Métricas: TTFT, vram_peak, oom_event, tool_call_errors, parser_recover_count (las 4 últimas líneas conectan con items 1.4 y 1.7).
- **Entregable**: `telemetry.py` + opt-in en Settings.

### Sprint 12 (días 78–84) — "Seguridad operacional llama-server"
- Bloque "Bonus" del informe.
- Forzar `--host 127.0.0.1`, `--no-webui`, `--api-key`, opcional rotación de puerto.
- **Entregable**: invariantes en `_build_server_cmd` + test que un curl LAN externo es rechazado.

### Sprint 13 (días 85–90) — "Push Carter 99.81 → 100 %"
- Investigar los ~9 fallos del bench actual.
- Posiblemente requiere prompt eng o ajustes a tools individuales, no cambios de runtime.
- **Entregable**: post-mortem por categoría.

---

## Métricas de seguimiento

Cada sprint debe reportar:
- `carter_pass_rate` antes/después.
- `ttft_p50_ms` y `ttft_p95_ms` antes/después.
- `vram_peak_mb` con `nvidia-smi` durante el bench.
- Si feature flag: porcentaje de OOM events en sesiones de prueba.

Almacenar en `audit/sprint_<N>_report.md`.
