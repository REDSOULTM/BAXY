# Resumen de sesión 2026-05-28 — Bug CUDA Gemma 4 + estado de v21 + sprint v22 iniciado

**Para:** Claude Opus 4.8 Max que continúa la sesión.
**Autor saliente:** Claude Opus 4.7 (sesión 2026-05-28 tarde/noche).
**Estado al pausar:** binario b9384 descargado y extraído pero **NO instalado todavía**.

---

## El problema en una línea
`llama-server` crashea con `CUDA error: illegal memory access` (issue #22527) en Gemma 4 + flash-attn cuando el prompt cruza ~13k tokens. El bug es upstream, ABIERTO sin fix oficial, intrínseco al kernel CUDA con el head size mismatch (no-SWA=512 / SWA=256) de la arquitectura híbrida Gemma 4.

## Lo que está en el repo HOY (commit HEAD: `0ca3395`, branch `sprint1-r2-domain-tools-split`)

### Working-tree NO committeado (estado v21)

| Archivo | Cambio vs HEAD git | Línea relevante |
|---|---|---|
| `gemma4_agent/infra/llama_server.py` | Flags Plan A en CLI + INI router: `--ctx-checkpoints 0`, `--cache-ram 0`, `--no-cache-idle-slots`, `--flash-attn on`, `--swa-full`, `--keep -1`. `restart()` revertido al simple del 27-may (3 líneas, sin lock/port_wait/kill). | CLI ~340-400; INI ~676-740; restart ~1194 |
| `gemma4_agent/infra/llm_client.py` | `_try_restart_managed_server` revertido al simple del 27-may (sin smoke probe). `_post_chat_with_recovery` zombie path = 1 restart + 1 reintento (sin soft-retry, sin bucle de 3 attempts). | ~71 + ~474 |
| `gemma4_agent/agent_core/agent.py` | Hard cap final de tools = 5 después de persona+a11y+carry+stabilize. Env `GEMMA4_HARD_TOOL_CAP`. | ~1660-1685 |
| `gemma4_agent/routing/planner.py` | `MAX_SELECTED_TOOLS = 5` (era 8). Env `GEMMA4_MAX_SELECTED_TOOLS`. | ~22-31 |
| `gemma4_agent/tests/test_llm_client_retry.py` | Reescrito al flujo simple v21 (sin soft-retry tests). | clase `TestProxyZombieRecovery` |
| `gemma4_agent/tests/test_llama_server_health_probe.py` | Quitó `TestRestartTakesLock` (probaba lock + port_in_use que ya no existen). | bottom |

**IMPORTANTE:** estos cambios NO están committeados. Hay un `git status` con `AM` (added in index, modified in working tree) en los 4 archivos clave porque la sesión PREVIA (no la mía) había movido `gemma4_agent/llm_client.py` → `gemma4_agent/infra/llm_client.py` (lo mismo con `llama_server.py`) y la copia nueva quedó solo en index, sin commit final. Ver detalle en sección "Historia y descubrimiento" abajo.

### Tests
- Suite tocada: 47/47 verde (`test_circuit_breaker.py` + `test_llm_client_retry.py` + `test_llama_server_health_probe.py`).
- Suite full: no la corrí end-to-end después del revert v21; correr antes de commitear.

### Métricas v21 (estado actual en disco, antes del sprint b9384)
- Live probe 6/6 OK en **31.2s total**.
- Child PID 10595 procesó 7 tareas sin crash.
- **0 recoveries activados** durante el probe (Plan A flags + cap=5 mantienen prompts en 9-11.7k, debajo del umbral).
- Tools max por turn: 5 (cap duro).

## Historia y descubrimiento clave

El usuario reportó: "antes de ayer (27-may) el server no se caía, te juro". Yo arranqué la sesión asumiendo que el bug siempre fue así.

Investigué git log y descubrí:
1. El commit **`7b2377d` (27-may 19:46)** introdujo el auto-recovery del proxy zombie. Su mensaje dice "El server del modelo se caía sola y dejaba la app muerta (medido 4+ veces)" — confirmando que el crash YA existía, pero el recovery lo enmascaraba.
2. NO hay commits en `llm_client.py`/`llama_server.py` desde `7b2377d`.
3. PERO en el working tree los archivos tenían cambios **no committeados** que duplicaban el tamaño: la **sesión PREVIA a la mía** había agregado:
   - `_smoke_probe_chat` (8s por restart)
   - soft-retry de 12s antes de declarar zombie
   - bucle de 3 attempts con backoff (~90s en caso peor)
   - `_kill_server_on_port` + lock + port_in_use loop (~11s)
   - circuit breaker preventivo (default off pero código pesado)
4. Eso convertía cada recovery de ~3s (27-may) a ~30-90s. **Esa era la sensación de "se cae el server" del usuario** — el crash sucedía igual pero ahora era visible por la pausa larga.

**Mi v21 revierte todo eso al diseño del `7b2377d`**, manteniendo solo Plan A flags + cap=5 que reducen la frecuencia del crash sin tocar el recovery.

## Sprint v22 (en progreso al pausar)

Plan acordado con el usuario:

1. ✅ Upgrade binario `llama-server.exe` de b9260 → **b9384** (último, MERGEADO PR #22929 que mejora checkpoint placement).
2. Subir `MAX_SELECTED_TOOLS` de 5 → 8 con el binario nuevo.
3. Si crashea con MAX=8: template Jinja compacto (~2-4h, comprime 2× los tools del prompt).
4. Si todavía crashea: two-phase routing (~4-6h, mantiene catálogo de 66+ tools disponible vía router cheapo + caller con subset).

### Estado del sprint al pausar

**Hecho:**
- Verificada versión actual: b9260 (commit `3a6db741a`) en `tools/llama-cuda/llama-server.exe` del 21-may.
- Descargado `llama-b9384-bin-win-cuda-12.4-x64.zip` (260 MiB) en `%TEMP%\llama-b9384-bin-win-cuda-12.4-x64.zip`.
- Extraído en `%TEMP%\llama-b9384-extract\` — versión confirmada: `9384 (48e7078ee)`.
- Decidido usar **CUDA 12.4** (no 13.3) porque:
  - El paquete cu12.4 incluye las DLLs CUDA (cudart64_12, cublas64_12) — no usa el toolkit instalado.
  - CUDA 12.x es el rango "work fine" según Unsloth/danielhanchen; CUDA 13.2 da gibberish/broken tool calling en Gemma 4 GGUF (fuente: discussions de unsloth/gemma-4-*-GGUF en HuggingFace).
  - Mi toolkit instalado es CUDA 13.0.88 (no afectado por el bug 13.2, pero sí menos probado que 12.x).

**Falta hacer (lo que Opus 4.8 debe continuar):**
1. **Backup** del binario actual + DLLs:
   ```powershell
   $src = "tools\llama-cuda"
   $bak = "tools\llama-cuda.b9260-backup"
   if (-not (Test-Path $bak)) { Copy-Item -Path $src -Destination $bak -Recurse }
   ```
2. **Instalar b9384**:
   ```powershell
   Copy-Item "$env:TEMP\llama-b9384-extract\*" -Destination "tools\llama-cuda\" -Recurse -Force
   ```
3. **Verificar arranque** del server con b9384 (`scripts/_kill_server_ports.py` luego `scripts/_boot_server_for_eval.py`).
4. **Smoke test con MAX_TOOLS=5** (baseline para confirmar que b9384 no rompió nada): `scripts/_revert_live_probe.py`. Gate: 6/6 OK como con b9260.
5. **Subir MAX_TOOLS a 8** (env `GEMMA4_MAX_SELECTED_TOOLS=8` + `GEMMA4_HARD_TOOL_CAP=8`) y correr el live probe. Gate: 6/6 OK y `grep CUDA error` en server log = 0 en la corrida.
6. **Stress 30+ turns variados** si MAX=8 pasa. Si crashea, anotar el primer turn con prompt grande que dispara y confirmar que el crash es el mismo CUDA #22527.

### Rollback (si b9384 rompe algo)

```powershell
Copy-Item "tools\llama-cuda.b9260-backup\*" -Destination "tools\llama-cuda\" -Recurse -Force
python scripts\_kill_server_ports.py
python scripts\_boot_server_for_eval.py
```

## Lo que hay disponible si b9384 + MAX=8 no alcanzan

### Avenue 1 — Template Jinja compacto (próximo paso documentado)

Llama.cpp con `--jinja` permite override del template. La plantilla Gemma renderiza `{{ tools | tojson }}`. Si reemplazamos por un formato 2-3× más corto (firma TypeScript, formato TOON, o schema podado), 30 tools full ~14k tokens → compact ~7k. Margen para subir MAX_TOOLS a 15-20.

Implementación:
1. Crear `gemma4_agent/data/gemma4-compact.jinja` que itere los tools y emita solo `name`, `description` truncada y parámetros requeridos en una línea.
2. Agregar a `_build_server_cmd` (`gemma4_agent/infra/llama_server.py`) los flags `--chat-template-file <path-to-jinja>`.
3. Validar que el log del server muestra `Chat format: peg-gemma4` (si cae a "Generic", el parser está roto).
4. Gate: render del prompt con N tools y contar tokens; `≤13k` con N≥15.

Costo: 2-4h.

### Avenue 2 — Two-phase routing (catálogo completo)

El agent ya tiene `gemma4_agent/routing/planner.py` con `select_tool_names()` semántico. La idea es elevarlo a "fase 1 LLM-cheap" cuando keywords + semantic + cap actual no alcancen:

1. **Fase 1:** llamada barata con un único tool `route(query)→[tool_names]` que clasifica intent. Promp mínimo, sin schemas — entra en ~2k tokens.
2. **Fase 2:** segunda llamada con el subset ≤15 que `route()` devolvió.

Mantiene catálogo de 66+ tools disponible (el router puede elegir cualquiera), pero el LLM nunca ve más de 15 en un turn.

Costo: 4-6h. Latencia: +1-2s por turn (la llamada router es chica con E2B). Riesgo: tasa de acierto del router → mitigar con few-shot del propio `select_tool_names` actual.

### Avenue 3 — Sprint completo (parchar binario)

Plan B documentado en `documentacion/SPRINT_llama_cpp_recompile_swa_patch.md`. Skip de `create_checkpoint` para Gemma 4 SWA + FA. Costo: 2.5-6h. **NO recomendado mientras b9384/Avenue 1/Avenue 2 alcancen.**

## Issues upstream verificados (estado al 2026-05-28)

| Issue/PR | Estado | Build relevante | Notas |
|---|---|---|---|
| [#22527](https://github.com/ggml-org/llama.cpp/issues/22527) — CUDA illegal access Gemma 4 SWA | **ABIERTO**, sin maintainer engagement, sin PR linkeado | b8975+ | El bug. Reporter: Xuan-GUo, 29-abr. |
| [#21468](https://github.com/ggml-org/llama.cpp/issues/21468) — cache-reuse Gemma 4 | Cerrado por PR #22288 | Incluido en b9090+ | Arregló cache-reuse; NO arregla #22527. |
| [#21690](https://github.com/ggml-org/llama.cpp/issues/21690) — checkpoints OOM RAM | ABIERTO | — | Workaround `--ctx-checkpoints 0` ya aplicado en v21. |
| [PR #22929](https://github.com/ggml-org/llama.cpp/pull/22929) — checkpoint creation por message spans | **MERGED 25-may-2026** | Incluido en b9300+ y por tanto en b9384 | Cambia cuándo se crean checkpoints. Puede aliviar el patrón del crash (no toca el kernel pero reduce sus disparos). |
| [PR #21513](https://github.com/ggml-org/llama.cpp/pull/21513) — iSWA head sizes mixtos | MERGED 7-abr | Ya en b9090 | Aborda heads mixtos pero sin discusión del crash CUDA. |

## Sobre el reporte v4 del otro Claude que el usuario me trajo

Ubicado en `Investigaciones/PROMPT_RESEARCH_v4_gemma4_full_tools_no_crash.md` (el usuario lo abrió en IDE).

Verifiqué con WebFetch las claims principales:

| Claim | Verificación |
|---|---|
| PR #22929 ABIERTO al 22-may, 16 commits | ❌ INCORRECTO — **MERGEADO 25-may**. Está en master desde entonces, incluido en b9384. |
| ExLlamaV3 + TabbyAPI como backend alternativo | ⚠️ Existe `turboderp/gemma-4-31b-it-exl3` (31B, NO entra en 16 GB). **NO hay EXL3 público de E2B/E4B** — habría que convertir uno mismo. Costo real >12h, no 8h. |
| CUDA 13.2 → bajar a 12.x | ⚠️ Aplica solo a CUDA 13.2. **YO estoy en CUDA 13.0.88**, que el mismo aviso de Unsloth dice "work fine". El reporte sugería downgrade innecesario. |
| Two-phase routing (#1 del ranking) | ✅ Confirmado vs [Hermes #6839](https://github.com/NousResearch/hermes-agent/issues/6839) verbatim ("1,230 tok/s vs 134 tok/s with 8 tools"). |
| Compresión de template Jinja (#2 ranking) | ✅ Confirmado vs TOON spec (40-55% menos tokens) y Xu et al. arXiv:2407.02043. |
| Vulkan coopmat2 en NVIDIA | ⚠️ El reporte mismo lo marca como "hipótesis no verificada". |
| MLC-LLM | ✅ Confirmado NO soporta gemma4 (#3477). |
| Unsloth doc URL `unsloth.ai/docs/models/gemma-4-how-to-run-locally` | ❌ 404. La URL exacta no existe; la advertencia de CUDA 13.2 es real (HuggingFace discussions) pero la URL del reporte no resuelve. |

**Veredicto del reporte:** estructuralmente bueno (los rankings #1 y #2 son sólidos), pero con 3 errores fácticos que conviene no copiar a ciegas.

## Comandos clave de la sesión (referencia rápida)

```powershell
# Booteo del server (background; usa Plan A flags actuales)
python scripts\_kill_server_ports.py
python scripts\_boot_server_for_eval.py

# Live probe (6 turns variados, mide latencia y crashes)
python scripts\_revert_live_probe.py  # output: logs\_revert_live_probe.log

# Medir tamaño REAL del prompt enviado al server (hookea LLMClient.chat)
python scripts\_measure_agent_prompt_live.py

# Buscar crashes en server log
Select-String -Path gemma4_agent\logs\llama-server.err.log -Pattern "CUDA error|illegal memory"

# Tests del flujo recovery + planner
python -m pytest gemma4_agent\tests\test_llm_client_retry.py gemma4_agent\tests\test_circuit_breaker.py gemma4_agent\tests\test_llama_server_health_probe.py -x --tb=short -q
```

## Archivos en `Investigaciones/` relevantes

| Archivo | Qué contiene |
|---|---|
| `CONTEXTO_SESION_CUDA_BUG.md` | Contexto histórico (sesión anterior a la mía). |
| `RESULTADO_FINAL_PLAN_A.md` | Reporte "Plan A funcionó" — **engañoso**, los gates eran stress test sintéticos, no UI real con prompts grandes. |
| `RESULTADO_FINAL_V15.md` | Estado v15 de la sesión previa (con circuit breaker + smoke probe + bucle 3). |
| `PROMPT_RESEARCH_v3_gemma4_keep_no_bug.md` | Research v3 (el que produjo el Plan A). |
| `PROMPT_RESEARCH_v4_gemma4_full_tools_no_crash.md` | El prompt v4 que el usuario mandó a otro Claude. La respuesta del otro Claude está pegada al final del archivo (usuario la editó). |
| `compass_artifact_wf-8328bc51-*.md` | Research v1 (recomendaba downgrade — incorrecto). |
| `compass_artifact_wf-9af7a138-*.md` | Research v2 (recomendaba Qwen — descartado por restricción). |
| `compass_artifact_wf-e23f682e-*.md` | Research v3 (Plan A). |
| **`RESUMEN_SESION_2026_05_28_v21_v22.md`** | **ESTE archivo.** |

## Documentación adicional fuera de Investigaciones

- `documentacion/SPRINT_llama_cpp_recompile_swa_patch.md` — Plan B detallado (recompilar binario). Ya investigado, listo para ejecutar si todo lo demás falla.

## Lo más importante para Opus 4.8

1. **Antes de tocar nada:** correr `git status` y leer esta sección "Working-tree NO committeado" para entender el estado.
2. **Antes de commit:** correr la suite full (`python -m pytest gemma4_agent/tests/ -x --tb=short -q`) para verificar que el revert v21 no rompió nada más.
3. **El revert v21 que hice es la base — NO deshacerlo.** Es lo que el usuario reportó "como funcionaba el 27-may". Cualquier mejora va encima.
4. **El sprint v22 está a 2 pasos:** instalar b9384 + subir MAX_TOOLS a 8. Si eso no alcanza, Avenue 1 (template Jinja) es la siguiente.
5. **Backup CRÍTICO:** antes de instalar b9384, copiar `tools/llama-cuda/` entero a `tools/llama-cuda.b9260-backup/`. El binario actual ya funciona; no romperlo sin posibilidad de rollback.

## Memoria persistente (para anotar al final del sprint exitoso)

Conviene actualizar/crear en `~/.claude/projects/.../memory/`:
- `project_v21_recovery_revert_2026_05_28.md` — diagnóstico del recovery simple vs el complejo agregado por sesión previa.
- `project_gemma4_cuda_22527_status_2026_05_28.md` — estado actual del bug + workarounds aplicados.
- `project_v22_sprint_outcome_2026_05_28.md` — resultado final del upgrade b9384 + MAX_TOOLS y qué Avenue se aplicó.

**Restricciones que no cambian** (memoria del proyecto, ya documentadas):
- Gemma 4 sí o sí.
- Todo OSS / gratis.
- GPU local 16 GB (RTX 4060 Ti).
- Whisper en CPU.
- Latencia tier-Alexa (4-5s tope conversacional).
- El LLM responde, sin hardcodes.

---

**Buena suerte, Opus 4.8.** El usuario es paciente pero merece que esto quede sólido. La diferencia entre "anda" y "no se cae" para él pasa por la latencia de recovery — si tarda 30s pierde el flow; si tarda 3s no lo nota. Honrá eso.
