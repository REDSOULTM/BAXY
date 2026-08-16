# CARTER MODEL RECOMMENDATION (M10)

_Generated: 2026-05-02T16:52:39Z_

## Hardware detected

- GPU: NVIDIA GeForce RTX 4060 Ti (16380 MiB total, 14924 MiB free, CUDA=True)
- CPU cores: 24
- RAM: 32530 MiB total / 15331 MiB available
- OS: Windows-10-10.0.26200-SP0

## Profile chosen: **16gb**

- VRAM band: 14336-20480 MiB
- text budget: 8192 MiB
- vision budget: 6144 MiB
- concurrent_modals: 1
- context_default: 16384

## Selected stack

- text:   `hermes3:8b`
- vision: `qwen2.5vl:7b`
- stt:    `faster-whisper:large-v3`
- tts:    `piper:default`

## Fallback chains (in order)

- text:   hermes3:8b → gpt-oss:20b → mistral-small:24b → qwen3:8b
- vision: qwen2.5vl:7b → minicpm-v:latest
- stt:    faster-whisper:large-v3 → faster-whisper:medium
- tts:    piper:default → xtts-v2

## Load policy

- text keep_alive: 600s
- modal keep_alive: 0s
- unload text before modal: True
- max_vram_ratio: 0.85
- note: Carter actual — 16GB swap policy; voice can ride alongside text.

## Suggested .env block (copy MANUALLY — selector never writes env)

```env
CARTER_MODEL_PROFILE=16gb
CARTER_TEXT_MODEL=hermes3:8b
CARTER_VISION_MODEL=qwen2.5vl:7b
CARTER_STT_MODEL=faster-whisper:large-v3
CARTER_TTS_MODEL=piper:default
CARTER_TEXT_KEEP_ALIVE_S=600
CARTER_MODAL_KEEP_ALIVE_S=0
CARTER_MAX_VRAM_RATIO=0.85
```

## Warnings

- stt 'faster-whisper:large-v3' is non-Ollama; install via pip/extra runtime (see VOICE_MODEL_RESEARCH.md)
- tts 'piper:default' is non-Ollama; install via pip/extra runtime (see VOICE_MODEL_RESEARCH.md)

## PowerShell env block

```powershell
# --- Carter env (PowerShell) — paste manually; selector NEVER mutates env ---
$env:CARTER_MODEL_PROFILE = '16gb'
$env:CARTER_TEXT_MODEL    = 'hermes3:8b'
$env:CARTER_TOOL_PROTOCOL = 'json_direct'
$env:CARTER_VISION_MODEL  = 'qwen2.5vl:7b'
$env:CARTER_STT_MODEL     = 'faster-whisper:large-v3'
$env:CARTER_TTS_MODEL     = 'piper:default'
$env:CARTER_TEXT_KEEP_ALIVE_S  = '600'
$env:CARTER_MODAL_KEEP_ALIVE_S = '0'
$env:CARTER_MAX_VRAM_RATIO     = '0.85'
```

## Install plan

```powershell
# --- Install plan (only missing components) ---
pip install --upgrade faster-whisper  # STT runtime (CPU/GPU)
# TTS — see MODEL_TTS_TOURNAMENT_REPORT.md (piper for ≤16gb, xtts-v2 for 24gb)
```

## Rollback

```powershell
# --- Rollback to baseline qwen3:8b text default ---
Remove-Item Env:CARTER_TEXT_MODEL    -ErrorAction SilentlyContinue
Remove-Item Env:CARTER_TOOL_PROTOCOL -ErrorAction SilentlyContinue
Remove-Item Env:CARTER_MODEL_PROFILE -ErrorAction SilentlyContinue
Remove-Item Env:CARTER_VISION_MODEL  -ErrorAction SilentlyContinue
Remove-Item Env:CARTER_STT_MODEL     -ErrorAction SilentlyContinue
Remove-Item Env:CARTER_TTS_MODEL     -ErrorAction SilentlyContinue
# (Carter falls back to its hard-coded default qwen3:8b + auto tool protocol.)
```
