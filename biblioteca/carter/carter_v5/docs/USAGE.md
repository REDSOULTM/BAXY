# Carter v5 — Usage Guide

## Prerequisites

1. **Windows 11** (Win32 verifier APIs)
2. **llama.cpp CUDA b9090+** at `C:\llamacpp-cuda\bin\llama-server.exe`
   - PR #21418 specialized Gemma 4 parser required.
3. **NVIDIA GPU with ≥6 GB VRAM**
4. **Python 3.10+**
5. **Gemma 4 GGUF files** in `Probando Gemma 4/models/` (see `13_carter_v5_perfiles_vram.md` for paths)

## Install

```powershell
cd "Carter OS AI/carter_v5"
pip install -e .[dev]
```

This installs the `carter` command and all dependencies.

## Quick start

### Auto-detect VRAM and start

```powershell
python -m carter_v5.cli
```

What this does:
1. Reads `nvidia-smi` to detect VRAM (in MB).
2. Maps VRAM → tier via `hardware/tier.py:detect_tier()`.
3. Spawns `llama-server` with the tier-specific model + flags.
4. Waits for `/health=ok` (max 60s).
5. Starts REPL.

### Force a specific tier

```powershell
python -m carter_v5.cli --tier tier_16gb
```

Useful for benchmarking or if auto-detection picks the wrong tier.

### Skip llama-server spawn (assume already running)

```powershell
python -m carter_v5.cli --no-spawn
```

Useful when you've already started `llama-server` manually and want Carter to just connect.

### Full perms (no safety confirmation gates)

```powershell
python -m carter_v5.cli --full-perms
```

⚠️ Bypasses the `safety/policy.py` confirmation gate for destructive actions
(`borrar`, `formatear`, `instala`, etc.). **Use only for your own machine.**

### Audio input (Whisper)

```powershell
python -m carter_v5.cli --audio
```

Enables faster-whisper-turbo for microphone STT. *Note: REPL `/voice` command
not yet wired — the flag prepares the model but you still type for now.*

## REPL commands

Inside the REPL:

| Command | Action |
|---|---|
| `salir` / `exit` / `quit` / `bye` | Exit |
| `/reset` | Clear history (keep model loaded) |
| `/traces` | Show last 10 turns (jsonl trace) |
| `/image <path>` | Send an image to Gemma 4 vision |

Anything else is treated as a text turn.

## Example session

```text
[carter] detected 16380 MB VRAM → tier=tier_16gb
[carter] llama-server not running on :8080. Spawning...
[start_llama_server] tier=tier_16gb model=gemma-4-26B-A4B-it-UD-IQ4_XS port=8080
[start_llama_server] PID=12345
[start_llama_server] READY (health=ok)

============================================================
  CARTER v5 — local assistant powered by Gemma 4
  tier: tier_16gb | model: gemma-4-26B-A4B-it-UD-IQ4_XS | vram≈14.5 GB
  tools: 16 composite | vision: yes
  Type 'salir' / 'exit' / Ctrl+C to quit.
============================================================

carter> qué hora es

Son las 15:42 del lunes 11 de mayo.

carter> abre Steam y busca Batman

[runs gui_deeplink(steam, library), gui_deeplink(steam, search, query=Batman)]
Listo, abrí Steam y busqué Batman.
  [PARTIAL: 1/2; falta navigate]

carter> /image C:\Users\usuario\Desktop\error.png

[Gemma 4 vision processes the image]
La imagen muestra un diálogo de Windows que dice "Error 0x80070005". Esto es
un código común de acceso denegado en Windows...

carter> salir
[carter] bye
```

## Manual llama-server start (advanced)

If you want to control llama-server outside of Carter:

```powershell
pwsh carter_v5\scripts\start_llama_server.ps1 -Tier tier_16gb -Foreground
```

This runs llama-server in the foreground (Ctrl+C kills it).

## Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `CARTER_V4_GOD_MODE` | Bypass safety gate | unset |
| `CARTER_V5_WHISPER_DEVICE` | `cuda` or `cpu` for Whisper | `cuda` |
| `CARTER_V5_TRACE_OFF` | Disable jsonl tracing | unset |
| `CARTER_RUNTIME_VERIFY` | Inject `verification` field in tool results | `1` |
| `CARTER_TOOL_CATALOG` | `consolidated` (16) or `individual` (60) | `consolidated` (set by tier) |

## Testing

```powershell
# Unit tests (router, mission goal, tiers)
pytest carter_v5/tests/unit/ -v

# Integration tests (agent loop with mock LLM)
pytest carter_v5/tests/integration/ -v

# Full suite
pytest carter_v5/tests/ -v
```

## Bench (when ready)

```powershell
# Per-tier bench (not yet implemented — see La razon de carter/13)
python -m carter_v5.tests.bench.run_bench --tier tier_16gb --per-cat 3
```

## Troubleshooting

### llama-server doesn't start

Check `%USERPROFILE%\.carter_v5\llama_server_<tier>.log`. Common causes:
- Model file missing — see `13_carter_v5_perfiles_vram.md` Apéndice B for paths.
- VRAM OOM — try lowering tier or reducing `-c <context>` flag.

### Vision returns empty

Verify mmproj was loaded:
```powershell
Invoke-WebRequest http://127.0.0.1:8080/v1/models
```
Should show `"capabilities": ["completion", "multimodal"]`.

### Whisper fails to load

```powershell
pip install faster-whisper
```

If on CPU only:
```powershell
$env:CARTER_V5_WHISPER_DEVICE = "cpu"
```

## Rollback to Carter v4

```powershell
cd "Carter OS AI/legacy/Carter_v4"
python ../Run_Carterv4.py
```

v4 is preserved intact under `legacy/Carter_v4/` for fallback.
