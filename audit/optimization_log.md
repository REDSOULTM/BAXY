# Optimization Log — Fase 1 del roadmap del informe de auditoría externa

- **Sesión**: 2026-05-15 (autónoma)
- **Branch**: `feature/gemma4-optimization-roadmap`
- **Snapshot base**: `1106273 wip: pre-optimization snapshot`
- **Baseline**: 143/143 Modo A PASS, 6/6 anti-bypass PASS, 71/71 tests del repo PASS.
- **Reglas**: 1 change = 1 commit. Validar entre cada uno (`py_compile` + smoke + pytest). Si rompe, revert + BLOCKED.

---

## 1.1 — Pin de build llama.cpp + warn CUDA 13.2 — APPLIED
- **Informe**: Item I1 #1, Bloque B3, TL;DR-1.
- **Commit**: `70e0180 feat(llama_server): pin build llama.cpp + warn on CUDA 13.2`.
- **Archivos**: `gemma4_agent/llama_server.py` (+108 lines).
- **Cambios**: const `LLAMA_CPP_BUILD_MIN="b9090"` + `CUDA_RUNTIME_BLOCKED="13.2"` + helper `check_llama_build()` idempotente que parsea `--version` y emite warnings. Invocado en `start()` solo tras verificar archivos para no romper tests que mockean Popen.
- **Validación**: 143/143 smoke + 71/71 tests. Smoke test inline confirma build detectado como `b9090` en la máquina del dev.
- **Riesgo residual**: si una build futura de llama-server cambia el formato de `--version`, la regex puede fallar y emitir solo el warning genérico "could not parse build". No bloquea.

## 1.2 — Reserva 1.5 GB WDDM en recommend_profile — APPLIED
- **Informe**: Item I1 #10, Bloque F1.
- **Commit**: `b049b49 feat(profiles): reserve 1.5 GB WDDM in recommend_profile`.
- **Archivos**: `gemma4_agent/profiles.py`, `gemma4_agent/test_gx_features.py`.
- **Cambios**: const `WINDOWS_VRAM_RESERVE_MB = 1500`. `recommend_profile` resta esa reserva antes de mapear. Cortes nuevos: 10500 / 4500 / 2500 MB **efectivos**. Test `test_profiles_recommend_by_vram` actualizado.
- **Validación**: 143/143 + 71/71. Confirmado que 16 GB físicos siguen → performance (preserva setup del dev).
- **Riesgo residual**: si la GPU del usuario tiene menos overhead WDDM real (Linux, dGPU con monitor secundario, etc.), la reserva es conservadora pero no destructiva.

## 1.3 — `--keep -1` defensa anti-cache-reuse-roto — APPLIED
- **Informe**: Item I1 #3, Bloque D1, TL;DR-1.
- **Commit**: `c6f1cc1 feat(llama_server): add --keep -1 to preserve system prompt cache`.
- **Archivos**: `gemma4_agent/llama_server.py` (+8 líneas).
- **Cambios**: añadido `["--keep", "-1"]` al cmd para todos los perfiles con `server_running=True`. Preserva system prompt entre turnos.
- **Validación**: 143/143 + 71/71.
- **Riesgo residual**: ninguno; cuando PR #22288 (cache-reuse Gemma 4) merge, este flag es complementario, no conflicto.

## 1.4 — Parser robusto tool_call.arguments (#21384) — APPLIED
- **Informe**: Item I1 #5, Bloque C2/D4.
- **Commit**: `1d19cfc feat(llm_client): robust tool_call.arguments parsing (#21384)`.
- **Archivos**: `gemma4_agent/llm_client.py` (+204 líneas), `test_gx_features.py` (+4 tests).
- **Cambios**: `normalize_tool_call_arguments(raw)` maneja dict/str/list/None, JSON válido, JSON-of-JSON (doble-stringificado, caso #21384), valores escalares, malformados (→ `_raw` con `_parse_error` sin levantar). `normalize_tool_calls_list` aplica al formato OpenAI. Integrado en `chat()` y `_stream_chat()`.
- **Validación**: 143/143 + 75/75 (+4 tests nuevos).
- **Riesgo residual**: si el server emite un shape OpenAI muy distinto, el helper conserva el shape original; el caller puede inspeccionar `_parse_error`.

## 1.5 — Warning loud si user fuerza KV q8_0 — APPLIED
- **Informe**: Item I1 #5, Bloque B1/B2, TL;DR-6.
- **Commit**: `83d097a feat(llama_server): opt-in KV quant via env var + loud warning`.
- **Archivos**: `gemma4_agent/llama_server.py`.
- **Cambios**: nuevo env var `GEMMA4_LLAMA_KV_TYPE`. Default vacío = F16 (sin cambios). Si user setea `q8_0` (u otra quantizada), warning grande citando localbench KL 0.377. Lista blanca de tipos válidos; valores fuera de la lista se ignoran con warning.
- **Validación**: 143/143 + 75/75.
- **Riesgo residual**: el flag es opt-in; defecto seguro.

## 1.6 — `--no-mmproj-offload` cuando vision+VRAM tight — APPLIED
- **Informe**: Item I1 #8, Bloque E1.
- **Commit**: `a7f971a feat(llama_server): --no-mmproj-offload when vision+VRAM tight`.
- **Archivos**: `gemma4_agent/llama_server.py`.
- **Cambios**: si `profile.vision_enabled=True` y perfil es balanced/light, añadir `--no-mmproj-offload`. Mitiga issue #19980.
- **Validación**: 143/143 + 75/75.
- **Riesgo residual**: hoy balanced/light tienen vision_enabled=False, no se activa por defecto; es defensa para "user edita el perfil".

## 1.7 — Vision counter + recycle hook para mmproj leak (#21690) — APPLIED
- **Informe**: Item I1 #8, Bloque E1.
- **Commit**: `bbf5e01 feat(multimodal): vision_relaunch hook for mmproj leak (#21690)`.
- **Archivos**: `gemma4_agent/multimodal.py` (+~70 líneas), `gemma4_agent/llama_server.py` (+~50), `test_gx_features.py` (+test).
- **Cambios**:
  - `multimodal.py`: counter thread-safe, `IMAGE_RELAUNCH_THRESHOLD=40`, `set_vision_relaunch_callback()`, `reset_image_counter()`, `get_image_counter()`. `image_part()` llama a `_bump_image_counter()`. Al cruzar el umbral: publish al `BUS` (`kind=vision_threshold_reached`) **y** invoca el callback registrado.
  - `llama_server.py`: nuevo método `LlamaServerManager.recycle_for_vision_leak()` que encapsula stop+start con el perfil activo (solo si `vision_enabled=True`), publica `boot_stage` al bus, resetea counter al final.
- **Validación**: 143/143 + 76/76. Test confirma counter no dispara prematuro, dispara exactamente una vez al cruzar, no re-dispara, reset funciona.
- **Riesgo residual**: el callback debe ser registrado por el orchestrator (`agent_runner.py` o `server.py`); si nadie lo registra, solo se publica al bus. El primer ciclo de uso del feature requiere wiring extra del dev — documentado en optimization_roadmap.md.

## 1.8 — Compilador tool schemas EXACT Markdown — APPLIED (helper) + DEFERRED (injection)
- **Informe**: Item I1 #7, Bloque C4.
- **Commit**: `c940bfb feat(tools): compile_tools_to_markdown_exact for system prompt injection`.
- **Archivos**: `gemma4_agent/tools.py` (+~90 líneas), `test_gx_features.py` (+test).
- **Cambios**: `compile_tools_to_markdown_exact(schemas)` produce el bloque Markdown estilo Daniel Farina OpenCode con header "EXACT parameter names — you MUST use these exactly", una sección por tool con tipos y REQUIRED/optional, enums explícitos.
- **DEFERRED**: la inyección real al system prompt vive en `gemma4_agent/agent.py:388` (NO TOCAR por constraint del brief). Para activar, el dev debe añadir una línea allí que llame `compile_tools_to_markdown_exact()` y la concatene como un nuevo `tool_schemas_hint` después de `mode_hint`. ~3 líneas de código.
- **Validación**: 143/143 + 77/77.
- **Riesgo residual**: el helper está listo; el wiring queda como follow-up trivial cuando el dev decida tocar agent.py.

## 1.9 — Feature-flag MXFP4_MOE experimental — APPLIED
- **Informe**: Item I1, Bloque A3.
- **Commit**: `746c06f feat(model_info): flag MXFP4_MOE as experimental quant with warning`.
- **Archivos**: `gemma4_agent/model_info.py` (+~30 líneas), `gemma4_agent/llama_server.py` (+15), `test_gx_features.py` (+test).
- **Cambios**: helper `is_experimental_quant(path) -> (bool, pattern)`. `LlamaServerManager.start()` lo invoca tras verificar archivos. Si el GGUF activo contiene `MXFP4_MOE` o `MXFP4`, log WARNING grande citando Unsloth (retirada de MXFP4 por degradación en attn_gate/attn_q/ssm_*).
- **Validación**: 143/143 + 78/78.
- **Riesgo residual**: el usuario que insiste en MXFP4_MOE no es bloqueado, solo advertido. Conservador por diseño.

## 1.10 — Detección de CUDA 13.2 — APPLIED (cubierto por 1.1)
- **Informe**: Bloque B3.
- **Commit**: incluido en `70e0180` (1.1).
- **Cambios**: `check_llama_build()` parsea CUDA runtime de `--version` y emite warning grande si == "13.2", citando alerta Unsloth 2026-04-11.
- **Validación**: 143/143 + 78/78. En la máquina del dev (`gemma-4-E4B-it-Q6_K`) el output de `--version` no incluye string CUDA y el chequeo devuelve `cuda=None` (sin warning). Funcional pero **dependiente del formato de --version** de la build de llama-server.
- **Riesgo residual**: si una build futura cambia el formato, no se emite warning. Como fallback, llama-server tiende a imprimir la versión CUDA en stderr al cargar el modelo; un parser adicional ahí sería más robusto pero **requiere leer el stderr live**, que es más invasivo. Postponed al roadmap Fase 3.

---

## Resumen Fase 1

| # | Item | Status | Commit | Validation |
|---|---|---|---|---|
| 1.1 | Pin build llama.cpp | APPLIED | `70e0180` | 143/143 + 71/71 |
| 1.2 | Reserva 1.5 GB WDDM | APPLIED | `b049b49` | 143/143 + 71/71 |
| 1.3 | --keep -1 | APPLIED | `c6f1cc1` | 143/143 + 71/71 |
| 1.4 | Parser tool_call args | APPLIED | `1d19cfc` | 143/143 + 75/75 |
| 1.5 | Warning KV q8_0 | APPLIED | `83d097a` | 143/143 + 75/75 |
| 1.6 | --no-mmproj-offload | APPLIED | `a7f971a` | 143/143 + 75/75 |
| 1.7 | Auto-relaunch vision | APPLIED | `bbf5e01` | 143/143 + 76/76 |
| 1.8 | Tool schemas EXACT | APPLIED (helper) / DEFERRED (injection) | `c940bfb` | 143/143 + 77/77 |
| 1.9 | MXFP4 experimental | APPLIED | `746c06f` | 143/143 + 78/78 |
| 1.10 | CUDA 13.2 warning | APPLIED (via 1.1) | `70e0180` | 143/143 + 78/78 |

**Total**: 10/10 items aplicados. **+7 tests nuevos** (71 → 78). Smoke baseline preservado (143/143, 6/6 anti-bypass).

**Baseline → final**:
- Tests del repo: 71/71 → **78/78 PASS**
- Smoke Modo A: 143/143 → **143/143 PASS**
- Anti-bypass: 6/6 → **6/6 PASS**
- Commits Fase 1: **9 commits** sobre `feature/gemma4-optimization-roadmap` (+ snapshot WIP `1106273` antes).

---

# Fase 2 — Decisiones de producto

Resolvemos las 4 decisiones documentadas en `optimization_roadmap.md`.

## 2.1 — Perfil `balanced_8gb` con UD-Q4_K_XL E4B — APPLIED
- **Decisión tomada**: en lugar de cambiar el default de `balanced` (que rompería 6 GB con la reserva WDDM), **crear un perfil intermedio** para 8 GB de VRAM.
- **Commit**: `cec6725 feat(profiles): new balanced_8gb profile with UD-Q4_K_XL E4B`.
- **Archivos**: `gemma4_agent/profiles.py`, `gemma4_agent/test_gx_features.py`, `gemma4_agent/ui/settings.py`.
- **Cambios**:
  - Nuevo `PROFILES["balanced_8gb"]` apuntando a `models/E4B/gemma-4-E4B-it-UD-Q4_K_XL.gguf`, ctx 8K, vision OFF, rerank ON, voice ON.
  - `recommend_profile` con nuevo corte 6500 MB efectivos (8 GB físicos) → `balanced_8gb` si el GGUF existe, fallback a `balanced` si no.
  - GUI tabla de perfiles editable: 3 → 4 columnas.
  - Tests V1/V4 actualizados con el tier intermedio. Detección defensiva si el GGUF está/no está.
- **Acción pendiente del dev**: bajar `unsloth/gemma-4-E4B-it-GGUF:UD-Q4_K_XL` (~4.7 GB) a `models/E4B/gemma-4-E4B-it-UD-Q4_K_XL.gguf` para activar el perfil en máquinas de 8 GB.
- **Validación**: 143/143 + 78/78.

## 2.2 — Speculative decoding opt-in via env var — APPLIED
- **Decisión tomada**: feature-flag **OFF-by-default**, opt-in via `GEMMA4_SPEC_DRAFT_MODEL`.
- **Commit**: `bcf105e feat(llama_server): opt-in speculative decoding via env var`.
- **Archivos**: `gemma4_agent/llama_server.py`, `gemma4_agent/test_gx_features.py`.
- **Cambios**:
  - Env vars: `GEMMA4_SPEC_DRAFT_MODEL` (path), `GEMMA4_SPEC_DRAFT_N_MAX` (16), `GEMMA4_SPEC_DRAFT_N_MIN` (0), `GEMMA4_SPEC_DRAFT_NGL` (99).
  - Solo se activa si: archivo existe + perfil `performance` (VRAM 12+ GB requerida).
  - Warning grande citando bench hackmd #ODXuOQNzSiyUITz7g9mtBw (negative speedup en consumer Ampere).
  - Si perfil ≠ performance o archivo falta: ignorado con info-level log.
- **Validación**: 143/143 + 79/79. Test cubre 4 casos (unset / file missing / wrong profile / activación).
- **Acción pendiente**: el dev (con 16 GB) puede experimentar bajando un draft E2B-Q4 y correr `llama-bench --model-draft` para medir acceptance rate antes de habilitar en producción.

## 2.3 — STT alternativo (Parakeet-TDT-0.6B-v3) — DEFERRED
- **Razones**:
  - Rompe "cero deps pesadas" del brief (NeMo toolkit ~1 GB de wheels).
  - Licencia NVIDIA Community Model License necesita revisión legal.
  - WER es-MX vs Whisper-small no medido.
- **Commit**: `16b3919 docs(voice): formalize DEFERRED for items 2.3 and 2.4`.
- **Archivos**: docstring formal en `gemma4_agent/voice/stt.py:StreamingSTT.load`.
- **Re-evaluar cuando**: el dev acepte la dep + licencia + tenga set de bench Common Voice 17 es-MX con jiwer.

## 2.4 — TTS alternativo (Kokoro-82M-es) — DEFERRED
- **Razones**:
  - Latencia primer chunk CPU 600-1200 ms viola el SLA "≤1 s primer fonema" del brief.
  - Requiere dep nueva (kokoro-onnx).
  - Voces es-MX/es-AR no son oficiales (parche comunitario).
- **Commit**: `16b3919` (mismo).
- **Archivos**: docstring formal en `gemma4_agent/voice/tts.py:StreamingTTS`.
- **Re-evaluar cuando**: feedback explícito de usuarios pidiendo voz más natural.

---

## Resumen Fase 2

| Item | Status | Commit | Validación |
|---|---|---|---|
| 2.1 balanced_8gb (UD-Q4_K_XL E4B) | APPLIED | `cec6725` | 143/143 + 78/78 |
| 2.2 Speculative decoding opt-in | APPLIED | `bcf105e` | 143/143 + 79/79 |
| 2.3 Parakeet STT | DEFERRED | `16b3919` | n/a |
| 2.4 Kokoro TTS | DEFERRED | `16b3919` | n/a |

**4/4 decisiones resueltas**: 2 APPLIED (con código y tests), 2 DEFERRED (con justificación en docstring).

**Baseline → Fase 2 final**:
- Tests del repo: 78/78 → **79/79 PASS** (+1 test nuevo para spec decoding)
- Smoke Modo A: **143/143 PASS** (sin regresión)
- Anti-bypass: **6/6 PASS**
- Commits Fase 2: **3 commits** sobre Fase 1.

---

# Fase 3 — Sprints autónomos (sin tocar agent.py)

Subset del roadmap de 13 sprints que se puede aplicar sin tocar archivos prohibidos.

## Sprint 12 — Hardening operacional llama-server — APPLIED
- **Commit**: `6108973 feat(llama_server): Sprint 12 — operational hardening`.
- **Archivos**: `gemma4_agent/llama_server.py`, `gemma4_agent/llm_client.py`, `test_gx_features.py` (+2 tests).
- **Invariantes nuevas en `_build_server_cmd`**:
  - `--host 127.0.0.1` (proyecto 100% local, nunca bind a 0.0.0.0).
  - `--no-webui` (cliente tiene UI propia; webui interno es ataque innecesario).
  - `--api-key <env>` opcional via `GEMMA4_LLAMA_API_KEY`.
- **`llm_client._request_headers()`**: helper que añade `Authorization: Bearer <key>` si el env var existe. Defensa en profundidad si el puerto se expone por error.
- **Validación**: 143/143 + 81/81.

## Sprint 6 — Endpoint `/agent/recycle_server` — APPLIED
- **Commit**: `2afc5cd feat(server): POST /agent/recycle_server endpoint (Sprint 6)`.
- **Archivos**: `gemma4_agent/server.py` (+55 líneas).
- **Endpoint nuevo**: `POST /agent/recycle_server` que recicla SOLO el subprocess llama-server, sin tocar el estado del agente (memory, knowledge, sessions intactos).
- **Casos de uso**:
  - Botón "restart server" en UI Field para troubleshooting.
  - El callback registrado en `multimodal.py` (item 1.7) puede invocar este endpoint vía HTTP cuando el counter cruza 40 imágenes.
- **Reset automático del image counter** al final del recycle para empezar siguiente ciclo limpio.
- **Validación**: 143/143 + 81/81.

## Sprint 11 — Telemetría local opt-in — APPLIED
- **Commit**: `fbdaed3 feat(telemetry): Sprint 11 — local-only opt-in telemetry`.
- **Archivos**: `gemma4_agent/telemetry.py` (nuevo, ~440 líneas), `test_gx_features.py` (+test).
- **Módulo nuevo `TelemetryStore`**:
  - Default OFF, opt-in via `GEMMA4_TELEMETRY=true`.
  - SQLite local en `<state_path>.parent/telemetry.sqlite` con journal_mode=WAL.
  - 4 tablas: `turns`, `sessions`, `voice`, `incidents`.
  - Auto-subscribe al BUS: persiste `vision_threshold_reached` y `boot_stage`.
  - API: `record_turn / record_session / record_voice / record_incident / summarize_last_24h / export_json / rotate`.
- **Privacidad**: cero IDs externos, cero contenido del prompt, cero tokens. Rotación 30 días.
- **Si init falla**: deshabilita en runtime, NUNCA rompe el agent.
- **Validación**: 143/143 + 82/82.

## Sprint 7 — Pre-warm KV con system prompt — APPLIED (helper only)
- **Commit**: `c84aef6 feat(prewarm): Sprint 7 — KV cache pre-warm at startup`.
- **Archivos**: `gemma4_agent/prewarm.py` (nuevo, ~115 líneas), `test_gx_features.py` (+test).
- **Función pura `prewarm_kv(client, system_prompt, tools=None, timeout_s=90)`**:
  - Hace POST `chat()` con `[system, user='.']` y `max_tokens=1`.
  - El '.' es input neutro; max_tokens=1 minimiza generación pero deja procesar prefix completo.
  - Publica `boot_stage prewarm_start/prewarm_done` al BUS.
  - Si falla: no levanta, devuelve `ok=False`. El agente arranca igual.
- **Env opt-out**: `GEMMA4_DISABLE_PREWARM=true`. Default ON. Cuando PR #22288 (fix cache-reuse) merge upstream, se puede desactivar.
- **DEFERRED wiring**: el caller (agent_runner.py post-boot) requiere tocar archivos del flujo de arranque. El helper está listo + testeado.
- **Validación**: 143/143 + 83/83.

---

## Resumen Fase 3 (subset autónomo)

| Sprint | Item | Status | Commit | Validación |
|---|---|---|---|---|
| 12 | Hardening llama-server | APPLIED | `6108973` | 143/143 + 81/81 |
| 6 | `/agent/recycle_server` | APPLIED | `2afc5cd` | 143/143 + 81/81 |
| 11 | Telemetría opt-in | APPLIED | `fbdaed3` | 143/143 + 82/82 |
| 7 | Pre-warm KV (helper) | APPLIED (helper) / DEFERRED (wiring) | `c84aef6` | 143/143 + 83/83 |

**4 sprints aplicados** sobre Fase 2. Total acumulado:

| Métrica | Baseline → Final |
|---|---|
| Tests del repo | 71/71 → **83/83 PASS** (+12 tests nuevos en total) |
| Smoke Modo A | **143/143 PASS** (sin regresión en toda la sesión) |
| Anti-bypass | **6/6 PASS** |
| Commits totales | **19** (1 WIP + 13 feat/docs Fase 1 + 3 Fase 2 + 4 Fase 3 — más este cierre) |
| Archivos nuevos | `telemetry.py`, `prewarm.py`, `_ps.py` (sesión anterior). |
| Deps nuevas | **0** |
| Constraint `agent.py` | **No tocado en toda la sesión** |

## Sprints de Fase 3 que NO se aplicaron en la primera tanda (continuación)

Tras autorización del usuario aplicamos los siguientes:

## Sprint 1 — Inyección de tool_schemas_hint en agent.py — APPLIED
- **Commit**: `c6ed18f feat(agent): Sprint 1 — inject tool_schemas_hint into system prompt`.
- **Archivos**: `gemma4_agent/agent.py`, `gemma4_agent/tools.py` (variante compact), `gemma4_agent/profiles.py` (ctx balanced_8gb 8K→16K), `test_gx_features.py`.
- **Cambios**:
  - `Gemma4Agent._tool_schemas_hint()` con auto-selección por ctx: `full` (≥32K), `compact` (≥16K), `off` (<16K). Cache a nivel-instancia.
  - `compile_tools_to_markdown_exact(compact=True)`: variante 49% más chica (~5.9K tokens vs 11.6K).
  - `balanced_8gb`: ctx 8K→16K para acomodar el hint compact. VRAM total app sube de 5.95 a 6.30 GB; sigue entrando en 8 GB nominales.
  - Overrides env: `GEMMA4_TOOL_SCHEMAS_HINT_MODE=full|compact|off|auto`, legacy `GEMMA4_DISABLE_TOOL_SCHEMAS_HINT=true`.
- **Validación**: 143/143 + 84/84.

## Sprint 4 — Wiring vision_relaunch callback — APPLIED
- **Commit**: `f5819bc feat(agent_runner): Sprint 4 — wire vision_relaunch callback`.
- **Archivos**: `gemma4_agent/agent_runner.py`.
- **Cambios**: `AgentRunner._server_manager` ahora persiste la referencia. Tras boot exitoso del server, registramos `set_vision_relaunch_callback(...)` que invoca `manager.recycle_for_vision_leak()` al cruzar el umbral de 40 imágenes (item 1.7).
- **Validación**: 143/143 + 84/84.

## Sprint 5 — Streaming SSE interleaved + edge cases — APPLIED
- **Commit**: `a2f7afd test: Sprint 5 — SSE streaming interleaved tool_calls integration`.
- **Archivos**: `test_gx_features.py` (+3 tests).
- **Cobertura nueva**:
  - Patrón interleaved (texto + tool_call + texto en mismo turno).
  - Args con `{`/`}` literales fragmentados en chunks SSE (#21384).
  - Múltiples tool_calls paralelos en chunks separados.
- **Validación**: 143/143 + 87/87.

## Sprint 8/9 — Upstream PR watch script — APPLIED + ACTION DISCOVERED
- **Commit**: `feat(audit): Sprint 8/9 — upstream PR/issue watch script`.
- **Archivo nuevo**: `audit/check_upstream_prs.py` + `audit/upstream_pr_snapshot.json`.
- **Tracking** de 6 issues/PRs upstream relevantes a Gemma 4.
- **HALLAZGO CRÍTICO 2026-05-15**: el primer run del script reportó que **#22288 está MERGED** (fix de `--cache-reuse` para Gemma 4). El issue #21468 cerrado como consecuencia. Esto significa que el `--keep -1` que aplicamos en 1.3 sigue siendo útil pero ya **no es defensa contra issue activo, sino complemento**. El dev puede considerar re-habilitar `--cache-reuse` cuando confirme la build mínima requerida.
- **Validación**: 143/143 + 87/87.

## Sprint 13 — Regression guards del propio gemma4_agent — APPLIED
- **Commit**: `1874797 test: Sprint 13 — regression guards for gemma4_agent invariants`.
- **Archivos**: `test_gx_features.py` (+5 tests).
- **Reenfoque del Sprint**: NO replicamos el harness Carter en gemma4_agent (decisión explícita del usuario: "esto es Gemma 4 Agent, no Carter"). En su lugar, agregamos tests defensivos que aseguran que los invariantes del informe externo NO se rompan en cambios futuros.
- **5 tests nuevos**:
  - a) `--mmproj` NO presente cuando vision=False (TL;DR MAL #b).
  - b) Sampling oficial Google preservado en AgentConfig defaults (TL;DR MEJOR #a).
  - c) `--host 127.0.0.1` y `--no-webui` en todos los perfiles activos (Sprint 12).
  - d) Las 62 tools listadas en compile_tools_to_markdown_exact (full + compact).
  - e) voice_enabled=True en todos los perfiles con server_running=True (req del usuario).
- **Validación**: 143/143 + **92/92**.

---

## Resumen Fase 3 — completo

| Sprint | Item del roadmap | Status | Commit | Tests |
|---|---|---|---|---|
| 12 | Hardening llama-server | APPLIED | `6108973` | +2 |
| 6 | `/agent/recycle_server` endpoint | APPLIED | `2afc5cd` | n/a |
| 11 | Telemetría opt-in | APPLIED | `fbdaed3` | +1 |
| 7 | Pre-warm KV (helper) | APPLIED (helper) | `c84aef6` | +1 |
| 1 | Inyección tool_schemas_hint | APPLIED | `c6ed18f` | +1 |
| 4 | Wiring vision_relaunch | APPLIED | `f5819bc` | n/a |
| 5 | Streaming SSE interleaved | APPLIED | `a2f7afd` | +3 |
| 8/9 | Upstream PR watch | APPLIED + finding | `4d28e91` | n/a |
| 13 | Regression guards | APPLIED | `1874797` | +5 |

**9/13 sprints del roadmap aplicados.**

Sprints todavía pendientes (requieren bench horas o decisión externa):
- **2**: A/B Carter UD-Q4_K_XL vs E2B-Q5_K_M. Requiere bajar GGUF (~4.7 GB) + bench overnight.
- **3**: Bench Carter Q4_K_M vs Q5_K_M. Bench overnight.
- **10**: Implementación final speculative decoding. Helper opt-in en 2.2 listo; falta A/B real.

Estos 3 son **trabajo de bench**, no de código. La infraestructura está completa.

---

## Estado final tras toda la sesión (Fase 1 + 2 + 3)

| Métrica | Baseline → Final |
|---|---|
| Tests del repo | 71/71 → **92/92 PASS** (+21 tests nuevos) |
| Smoke Modo A | **143/143 PASS** (sin regresión en ninguna fase) |
| Anti-bypass | **6/6 PASS** |
| Commits totales | **27** (1 WIP + 26 trabajo/docs) |
| Archivos nuevos | `_ps.py`, `telemetry.py`, `prewarm.py`, `audit/check_upstream_prs.py`, `audit/upstream_pr_snapshot.json` |
| Deps nuevas | **0** |
| Setup del dev (Q6_K) | **Preservado** durante toda la sesión |
| Hallazgo crítico vía upstream watch | **PR #22288 MERGED** → `--cache-reuse` reparado para Gemma 4 |

