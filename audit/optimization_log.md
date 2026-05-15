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

