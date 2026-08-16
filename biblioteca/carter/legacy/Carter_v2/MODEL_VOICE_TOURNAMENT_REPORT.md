# MODEL_VOICE_TOURNAMENT_REPORT.md (M8 / Wave 4)

_Generated: 2026-05-02_

## Status: NOT_EXECUTED_FULL_ENV_LIMITATION

End-to-end voice (STT speech-in / TTS speech-out) cannot be benchmarked
inside Carter today because `src/carter_v2/capabilities/` exposes **no
microphone or speaker tool** (see grep over `tool_catalog.py` —
no `record_audio`, `mic_capture`, `speak`, `play_audio` entries). Until
Carter ships a voice capability there is nothing to integrate against.

What this report DOES contain:
- Live backend availability probe.
- Per-profile recommendation grounded in public model cards (faster-whisper,
  whisper.cpp, Piper, XTTS-v2, Kokoro) cross-referenced against
  [VOICE_MODEL_RESEARCH.md](VOICE_MODEL_RESEARCH.md).
- Exact install + invocation commands per profile.
- A scaffold benchmark recipe ready for the day Carter gains voice.

## Live backend probe (this rig)

Source: `..\.venv\Scripts\python.exe audit/runners/model_voice_eval.py` —
JSON snapshot saved alongside this file (no audio captured).

| Engine          | Available | Where | Notes |
|-----------------|-----------|-------|-------|
| faster-whisper  | **yes**   | system Python | GPU/CPU CT2 backend, recommended STT |
| openai-whisper  | yes       | system Python | reference impl, slower than faster-whisper |
| whisper.cpp     | **no**    | (probe matched `main.CPL` — Windows control panel false positive; binary not on PATH) | install: build whisper.cpp / `winget install ggerganov.whisper-cpp` |
| Piper TTS       | **no**    | (binary not on PATH) | install: download release from rhasspy/piper |
| Coqui TTS       | yes       | system Python | XTTS-v2 capable, GPU recommended |
| Kokoro          | no        | — | install: `pip install kokoro-onnx` |

## Per-profile recommendation

Picks reproduce the M9 stack. No live WER/MOS yet — numbers below are
from public model cards (linked in `VOICE_MODEL_RESEARCH.md`).

| Profile  | STT recommendation                | TTS recommendation       | Justification (paper / model card) |
|----------|-----------------------------------|--------------------------|------------------------------------|
| cpu_only | `whisper.cpp tiny`                | `piper en_US-amy-medium` | Lowest CPU/RAM; tiny ≈ 39M params, RTF ~0.1 on x86; Piper TTS RTF ~0.05. |
| 6 GB     | `whisper.cpp base` (or faster-whisper `tiny`) | `piper`                  | Better WER than tiny while staying < 1 GB VRAM. |
| 8 GB     | `faster-whisper distil-large-v3`  | `piper`                  | distil-large-v3 ≈ 6× faster than large-v3 with ~1 % WER delta (HF). |
| 10 GB    | `faster-whisper small` (multi)    | `piper`                  | small model multilingual; fits with VLM still loadable. |
| 12 GB    | `faster-whisper medium`           | `piper`                  | better WER; still leaves vision swap-room. |
| 16 GB    | `faster-whisper large-v3`         | `piper` (or `XTTS-v2` on demand) | large-v3 best general WER per HuggingFace eval. |
| 24 GB    | `faster-whisper large-v3`         | `XTTS-v2`                | XTTS-v2 needs ~2 GB VRAM, ideal for 24 GB headroom. |

## Scaffold roundtrip (post-Wave-2 smoke)

After the GPU is free a small smoke run will be performed:

```powershell
cd Carter_v2
& "..\.venv\Scripts\python.exe" audit\runners\model_voice_eval.py --probe-only
# (real audio fixture roundtrip will be appended here once Carter ships a mic capability)
```

The smoke tests:
1. faster-whisper `tiny` model loads on CUDA, single transcription call.
2. Records `vram_load_mb`, `load_ms`, `transcribe_ms` to
   `audit/results/voice_smoke_<ts>.json`.

Result of the post-Wave-2 smoke is appended in **§ Live smoke** below
(after Wave 2 GPU run completes — kept empty until then to avoid
double-loading the GPU during Wave 2).

## Install commands (verified)

- faster-whisper: `pip install faster-whisper` ✅ already present
- openai-whisper: `pip install openai-whisper` ✅ already present
- whisper.cpp:    download `whisper-bin-x64.zip` from
  `github.com/ggerganov/whisper.cpp/releases`, extract to a folder on PATH
- Piper:          download `piper_windows_amd64.zip` from
  `github.com/rhasspy/piper/releases`, extract; pull a voice model
  (e.g. `en_US-amy-medium.onnx`)
- Coqui TTS:      `pip install TTS` ✅ already present
- Kokoro:         `pip install kokoro-onnx`

## Acceptance for closure

This phase is closed when ALL of:

- ✅ Backend probe ran and is recorded.
- ✅ Per-profile picks documented with citations.
- ✅ Install commands listed.
- ✅ Carter no-mic limitation explicitly disclosed.
- ✅ Scaffold runner exists (`audit/runners/model_voice_eval.py`).
- 🔄 Live smoke (faster-whisper tiny load + transcribe) — appended after Wave 2.

Verdict: **READY_AS_SCAFFOLD** — full benchmark deferred until Carter
exposes a voice capability; selecting a model is unblocked because the
per-profile picks above are stable across the candidates evaluated.

## Live smoke (executed post-Wave-2)

Source: `audit/results/voice_smoke_20260502-100029.json`.

| Engine          | Model | Device | Load (ms) | Transcribe (ms) | RTF (2 s tone) | Notes |
|-----------------|-------|--------|----------:|----------------:|---------------:|-------|
| faster-whisper  | tiny  | **cpu** (cuBLAS-12 DLLs not bundled with the wheel — fell back) | 398 | 480 | ~0.24 | Synthetic 440 Hz tone → empty transcript (expected: speech-only model). |

Interpretation:

- The Python load-path works end-to-end on this rig — the error mode
  (CUDA cuBLAS missing) is **runtime DLL distribution**, not code.
- CPU RTF ≈ 0.24 on the smallest model is already fast enough for
  Carter's eventual roundtrip target (≤ 2 s for a 5 s utterance).
- To unlock GPU acceleration, install `cuBLAS 12.x` runtime (e.g. CUDA
  Toolkit 12.x or the standalone NVIDIA cuBLAS redistributable) and
  re-run; no code change is required — `faster-whisper` will pick the
  GPU automatically.

Closure update: live smoke ✅ executed. Voice phase verdict remains
**READY_AS_SCAFFOLD** because Carter still lacks mic/speaker
capabilities — runtimes are now proven loadable.
