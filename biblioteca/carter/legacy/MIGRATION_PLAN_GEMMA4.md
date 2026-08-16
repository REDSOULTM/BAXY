# Migration plan — Gemma 4 a Carter v4

**Branch:** `feat/gemma4-integration`
**Tag rollback:** `pre-gemma4-integration`
**Fecha:** 2026-05-10

## Resumen ejecutivo

Carter v4 incorpora Gemma 4 (E4B-it-Q6_K via llama-server) como backend LLM
**opcional**, manteniendo `qwen3:4b-instruct-2507-q4_K_M` (Ollama) como
fallback empaquetado. Cambios estructurales detrás de feature flags por env
para que el rollback sea instantáneo.

- **Modelo target:** `gemma-4-E4B-it-Q6_K.gguf` (`unsloth/gemma-4-E4B-it-GGUF`)
- **Runtime:** llama.cpp build CUDA b9090+ (PR #21418 obligatorio)
- **Hardware recomendado:** RTX 4060 Ti 16 GB (la validación medida fue acá)
- **Bench medido en repo Probando Gemma 4:** 540/540 individual + 540/540 con 16 composite
- **Sampling oficial Google:** T=1.0, top_p=0.95, top_k=64, repeat_penalty=1.0, max_tokens=1280

## Lo que cambió (7 commits)

| # | Commit  | Cambio                                                          |
|---|---------|-----------------------------------------------------------------|
| 1 | c91ceb46 | adapter llama-server: env `CARTER_LLM_BACKEND` + chat_stream    |
| 2 | 8e3ca068 | catalog consolidado: 16 composites + dispatcher                 |
| 3 | ebb5d980 | hardware.profile: detect_vram_mb + recommended_model + PS1     |
| 4 | c096dcf0 | NEEDS_PERMISSION + BLOCKED_BY_POLICY outcomes                  |
| 5 | 718491a0 | streaming.ReplEmitter + wire_progress() en CLI                  |
| 6 | d5b67dfe | smoke estructural 6/6 PASS                                      |
| 7 | (este)   | MIGRATION_PLAN_GEMMA4.md + INFORME_NOCTURNO.md                  |

## Cómo invocar cada backend

### Backend Gemma 4 (recomendado para RTX ≥12 GB)

```powershell
# 1. Levantar llama-server (descarga modelo si falta)
pwsh Carter_v4/scripts/start_carter_llm.ps1

# 2. En OTRA terminal: arrancar Carter con backend forzado
$env:CARTER_LLM_BACKEND = "llama-server"
$env:CARTER_TOOL_CATALOG = "consolidated"   # 16 tools, -68% tokens
$env:CARTER_STREAM = "1"                    # streaming SSE
python Run_Carterv4.py --gemma
```

Alternativa one-liner si llama-server ya corre:

```powershell
$env:CARTER_LLM_BACKEND="llama-server"; $env:CARTER_TOOL_CATALOG="consolidated"; python Run_Carterv4.py --gemma
```

### Backend Ollama (legacy fallback)

```powershell
# Default — sin tocar env vars
python Run_Carterv4.py --no-gemma

# O explicito
$env:CARTER_LLM_BACKEND = "ollama"
$env:CARTER_TOOL_CATALOG = "individual"
python Run_Carterv4.py --no-gemma
```

### Auto-detect (default)

```powershell
# Sin env vars: pick_adapter() prueba llama-server (8080) primero, sino Ollama (11434)
python Run_Carterv4.py
```

## Rollback paso a paso

Si algo se rompe en producción:

1. **Rollback inmediato (sin tocar código):**
   ```powershell
   $env:CARTER_LLM_BACKEND = "ollama"
   $env:CARTER_TOOL_CATALOG = "individual"
   $env:CARTER_STREAM = "0"
   python Run_Carterv4.py --no-gemma
   ```
   Vuelve al stack qwen3:4b + 60 tools individuales sin streaming.

2. **Rollback hard (al commit pre-integration):**
   ```powershell
   git checkout pre-gemma4-integration
   ```
   Tag automático plantado al inicio del branch.

3. **Rollback selectivo de streaming dentro de un proceso vivo:**
   ```python
   # En código que ya cargó el adapter:
   adapter.set_progress_callback(None)
   if hasattr(adapter, "_chat_non_stream"):
       adapter.chat = adapter._chat_non_stream
   ```

## Hardware requirements

| VRAM      | Tier recomendado        | Notas                                       |
|-----------|-------------------------|---------------------------------------------|
| <6 GB     | E2B-Q4_K_M              | Fallback mínimo; menos capacidad que E4B    |
| 6-8 GB    | E4B-Q4_K_M              | Unsloth "fit-cleanly"; ~93-96% PASS         |
| 8-12 GB   | E4B-Q5_K_M              | ~96-98% PASS                                |
| 12-24 GB  | **E4B-Q6_K** ⭐         | **100% medido en bench 540 oficial**        |
| ≥24 GB    | 26B-A4B-UD-IQ4_XS       | MoE; experimental, requiere validación      |
| Sin CUDA  | `cpu-fallback`          | Carter aborta y sugiere `--no-gemma`        |

Detalle por modelo en `Carter_v4/src/carter_v4/hardware/profile.py:MODELS`.

## Cómo ejecutar el bench 540 con Gemma 4

(Esta sesión NO lo pudo correr porque llama-server estaba apagado. Pasos
para el operador humano cuando levante el server.)

```powershell
# 1. Iniciar llama-server (~30 min descarga GGUF si es first run)
pwsh Carter_v4/scripts/start_carter_llm.ps1

# 2. Esperar que /health responda 200
while ((Invoke-WebRequest -Uri http://127.0.0.1:8080/health -ErrorAction SilentlyContinue).StatusCode -ne 200) {
    Start-Sleep 5
}

# 3. Correr bench con catalog consolidado
$env:CARTER_LLM_BACKEND = "llama-server"
$env:CARTER_TOOL_CATALOG = "consolidated"
cd Carter_v4
python audit/full_matrix_runner.py --gemma --output audit/runs/post_gemma4_migration_real.json

# 4. Comparar contra baseline qwen3:4b (commit 252be0f7 — 524/540 = 97.04%)
python audit/analyze_run.py audit/runs/post_gemma4_migration_real.json
```

Si Gemma 4 da <524/540, NO mergear y abrir bug. Si da ≥524/540, mergeable.

## Decisiones que NO se tomaron en este branch

- **Cambiar el modelo default a Gemma 4 en `Run_Carterv4.py`.**
  Hoy sigue siendo qwen3:4b por defecto (env `CARTER_LLM_BACKEND` debe
  setearse explícitamente). Cambiar el default requiere bench 540 real
  confirmando ≥97.04%.

- **Forzar catalog consolidated por defecto.**
  Hoy sigue siendo `individual`. El switch a consolidated reduce 68%
  tokens pero NO está validado contra qwen3:4b (solo contra Gemma 4 en
  el repo externo). Default conservador hasta tener bench cruzado.

- **Cambiar el sampling default del adapter Ollama.**
  El adapter Ollama mantiene Qwen3-Instruct-2507 sampling (T=0.7, top_p=0.8,
  presence_penalty=1.0). Solo `LLAMACPP_DEFAULTS` migró a Google
  sampling (T=1.0, top_p=0.95, top_k=64, num_predict=1280).

## Estructura de archivos nuevos / modificados

```
Carter_v4/
├── scripts/
│   └── start_carter_llm.ps1                   [NEW] bootstrap llama-server
├── src/carter_v4/
│   ├── hardware/                              [NEW]
│   │   ├── __init__.py
│   │   └── profile.py                         detect_vram + recommended_model
│   ├── streaming.py                           [NEW] ReplEmitter + wire_progress
│   ├── adapters/
│   │   ├── __init__.py                        [MOD] CARTER_LLM_BACKEND env
│   │   └── llamacpp.py                        [MOD] chat_stream + progress callbacks
│   ├── models/
│   │   └── gemma4.py                          [MOD] num_predict 768->1280
│   ├── tools/
│   │   ├── __init__.py                        [MOD] CARTER_TOOL_CATALOG + dispatch composite
│   │   ├── schemas_consolidated.json          [NEW] 16 composite tool schemas
│   │   └── composite_dispatcher.py            [NEW] tabla (composite,action) -> tool
│   ├── verifier_orchestrator.py               [MOD] NEEDS_PERMISSION + BLOCKED_BY_POLICY
│   └── cli.py                                 [MOD] wire_progress en arranque
└── audit/
    ├── smoke_post_migration.py                [NEW] 6 invariantes estructurales
    └── runs/
        └── post_gemma4_migration.json         [NEW] resultados smoke
```

## Variables de entorno relevantes

| Env                       | Valores                              | Default          | Efecto                                              |
|---------------------------|--------------------------------------|------------------|-----------------------------------------------------|
| `CARTER_LLM_BACKEND`      | `llama-server`/`ollama`/`auto`/unset | auto             | Fuerza adapter del LLM                              |
| `CARTER_TOOL_CATALOG`     | `individual`/`consolidated`          | `individual`     | 60 vs 16 tools en el system prompt                  |
| `CARTER_STREAM`           | `1`/`0`/`true`/`false`/unset         | on si llama-server | Activa SSE streaming en REPL                       |
| `CARTER_V4_LOG_LLM_PERF`  | `1` para enable                      | off              | Loggea prompt_tok/gen_tok por llamada               |
| `CARTER_V4_GOD_MODE`      | `1` para bypass safety               | off              | DESARROLLO solamente; bypassea destructive gate     |
| `CARTER_V4_FULL_PERMS`    | `1` para sandbox off                 | off              | Filesystem sin sandbox                              |
| `CARTER_V4_BLOCK_SHUTDOWN`| `1` para bloquear shutdown tools     | off              | Lo seteamos auto en audit runner; usar en sesión interactiva si querés safety extra |
| `CARTER_V4_ENABLE_SKILLS` | `1` para Anthropic skills format     | off              | Carga el skill registry                             |

## Cómo verificar manualmente

```powershell
# Smoke estructural (6 invariantes, sin tocar LLM)
cd Carter_v4
python audit/smoke_post_migration.py
# Esperado: Total: 6/6 PASS
```
