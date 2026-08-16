# MODEL_STT_TOURNAMENT_REPORT (Auto Model Stack S4)

_Split from [MODEL_VOICE_TOURNAMENT_REPORT.md](MODEL_VOICE_TOURNAMENT_REPORT.md) for the
"Auto Model Stack Final" mission so STT and TTS can be reasoned about
independently per VRAM profile._

## 1. Status

**`STT_READY_AS_SCAFFOLD`** — runtimes proven loadable, per-profile picks
documented and stable, but the live tournament is gated by Carter's lack of a
microphone capability (no `record_audio` / `mic_capture` tool in
`src/carter_v2/capabilities/tool_catalog.py`). The runner exists, the fixture
exists, and the engines load cleanly; the missing piece is a **reference
transcript** to compute WER. See [audit/results/voice_smoke_20260502-100029.json](audit/results/voice_smoke_20260502-100029.json).

## 2. Live backend probe (this rig)

Source: `python audit/runners/model_voice_eval.py --probe-only`.

| Engine          | Available | Where | Load (ms) | Transcribe (ms) | RTF (2 s tone) |
|-----------------|-----------|-------|----------:|----------------:|---------------:|
| faster-whisper  | **yes**   | venv  | 398 (CPU fallback — cuBLAS 12 DLLs absent) | 480 | ~0.24 |
| openai-whisper  | yes       | venv  | — | — | — |
| whisper.cpp     | no        | not on PATH | — | — | — |

cuBLAS 12 runtime install would unlock GPU acceleration; no code change required —
`faster-whisper` autodetects CUDA.

## 3. Per-profile recommendation

Picks reflect Whisper paper + faster-whisper benchmarks (CT2 int8) cross-referenced
against the live load smoke. **Tool protocol does not apply to STT** (audio in →
text out, no LLM tool calls).

| Profile | Primary STT | Fallback chain | Quant | RAM/VRAM | Expected RTF (CPU/GPU) | Install |
|---------|-------------|----------------|-------|---------:|-----------------------:|---------|
| cpu_only | `whisper.cpp:tiny` | (none) | int8 | ~150 MB RAM | ~0.10 / —  | `winget install ggerganov.whisper-cpp` or build from source |
| 6gb | `whisper.cpp:base` | `whisper.cpp:tiny` | int8 | ~250 MB RAM, 700 MB VRAM | ~0.20 / 0.05 | as above |
| 8gb | `faster-whisper:distil-large-v3` | `faster-whisper:small` | int8 | 1 800 MB VRAM | — / 0.10 | `pip install faster-whisper` ✅ |
| 10gb | `faster-whisper:small` | `faster-whisper:distil-large-v3` | int8 | 1 024 MB VRAM | — / 0.07 | as above |
| 12gb | `faster-whisper:medium` | `faster-whisper:small` | int8 | 2 500 MB VRAM | — / 0.05 | as above |
| **16gb (Carter rig)** | **`faster-whisper:large-v3`** | `faster-whisper:medium` | int8 | 3 000 MB VRAM | — / 0.04 | as above |
| 24gb | `faster-whisper:large-v3` | `faster-whisper:medium` | fp16 | 6 000 MB VRAM | — / 0.03 | as above |

## 4. Multilingual coverage

Distil-Whisper variants are **English-only**. For Spanish (Carter's primary user
language) the selector must NOT pick `faster-whisper:distil-large-v3` as primary
— fall back to `faster-whisper:small` (multilingual) or `large-v3`. Codified in
[STT_FALLBACK_BY_PROFILE](src/carter_v2/model_selection/model_registry.py) and in
the selector's per-language warning emitted by `recommend()`.

## 5. Scaffold tournament command

When Carter ships a mic capability, run:

```powershell
cd Carter_v2
& "..\.venv\Scripts\python.exe" audit\runners\model_voice_eval.py `
  --tournament `
  --fixture audit/fixtures/voice/spanish_command.wav `
  --reference audit/fixtures/voice/spanish_command.txt
```

Acceptance: WER ≤ 0.10 on Spanish command intents, RTF ≤ 0.30 on the rig's
target hardware (CPU for cpu_only, GPU otherwise).

## 6. Carter integration

Already wired declaratively:

- `STT_FALLBACK_BY_PROFILE` in [model_registry.py](src/carter_v2/model_selection/model_registry.py)
- `stt_chain` in `Recommendation` dataclass returned by [selector.recommend()](src/carter_v2/model_selection/selector.py)
- `stt_keep_alive_s` extension in [load_policy.py](src/carter_v2/model_selection/load_policy.py) (added in S6 of this mission)

## 7. Acceptance for closure

- ✅ Live backend probe captured.
- ✅ Per-profile picks documented with citations.
- ✅ Install commands listed.
- ✅ Multilingual caveat surfaced (no distil-* for non-English).
- ✅ Scaffold runner exists + smoke-tested.
- 🔄 Live WER bench (Carter mic capability blocker).

Verdict: **STT_READY_AS_SCAFFOLD** — picks unblocked, integration unblocked,
WER bench gated on Carter capability roadmap.
