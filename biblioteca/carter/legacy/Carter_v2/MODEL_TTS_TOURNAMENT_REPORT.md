# MODEL_TTS_TOURNAMENT_REPORT (Auto Model Stack S5)

_Split from [MODEL_VOICE_TOURNAMENT_REPORT.md](MODEL_VOICE_TOURNAMENT_REPORT.md) for the
"Auto Model Stack Final" mission so TTS can be reasoned about independently per
VRAM profile._

## 1. Status

**`TTS_READY_AS_SCAFFOLD`** — Coqui TTS (XTTS-v2) installs cleanly in the venv;
Piper binary is not on PATH on this rig but is freely downloadable. The end-to-end
"speak" pipeline is gated by Carter's lack of a speaker capability
(no `speak` / `play_audio` tool in `src/carter_v2/capabilities/tool_catalog.py`).

## 2. Live backend probe (this rig)

| Engine | Available | Notes |
|--------|-----------|-------|
| Piper  | **no** (binary not on PATH) | Install: `github.com/rhasspy/piper/releases` → `piper_windows_amd64.zip` |
| Coqui TTS (XTTS-v2) | yes | `pip install TTS` already present in venv |
| Kokoro-onnx | no | Install: `pip install kokoro-onnx` |

## 3. Per-profile recommendation

Picks anchored to: Piper paper (RTF ~0.05 CPU on `medium` voice), XTTS-v2 model
card (~2 GB VRAM, voice cloning), Kokoro-onnx benchmarks (CPU-friendly).

| Profile | Primary TTS | Fallback | Voice quality | First-audio target | RAM/VRAM |
|---------|-------------|----------|---------------|-------------------:|---------:|
| cpu_only | `piper:default` (en_US-amy-medium) | — | natural | ≤ 300 ms | ~120 MB RAM |
| 6gb | `piper:default` | — | natural | ≤ 250 ms | ~120 MB RAM |
| 8gb | `piper:default` | — | natural | ≤ 200 ms | ~120 MB RAM |
| 10gb | `piper:default` | — | natural | ≤ 200 ms | ~120 MB RAM |
| 12gb | `piper:default` | (xtts-v2 opt-in) | natural | ≤ 200 ms | ~120 MB RAM |
| **16gb (Carter rig)** | **`piper:default`** | `xtts-v2` (opt-in for voice clone) | natural | ≤ 200 ms | 120 MB RAM (piper) / 2 GB VRAM (xtts) |
| 24gb | `xtts-v2` | `piper:default` | premium + clone | ≤ 800 ms (xtts) | ~2 GB VRAM |

## 4. Latency budget

Carter's UX target: ≤ 1 s from "tool emits speak()" to "first audio frame
playing". On 16 GB:

- Piper streaming: ~50 ms first audio + ~5 ms / phoneme thereafter — easily under budget.
- XTTS-v2 first audio: ~600–900 ms (model + neural vocoder); used only when voice
  cloning is requested by the operator.

## 5. Scaffold tournament command

```powershell
cd Carter_v2
& "..\.venv\Scripts\python.exe" audit\runners\model_voice_eval.py `
  --tts `
  --tts-text "Hola Carter, ¿en qué puedo ayudarte?" `
  --tts-out audit/results/tts_smoke.wav
```

Acceptance: produces a non-empty WAV under 5 s wall-clock, naturalness
spot-checked by operator.

## 6. Carter integration

Declarative wiring identical to STT:

- `TTS_FALLBACK_BY_PROFILE` in [model_registry.py](src/carter_v2/model_selection/model_registry.py).
- `tts_chain` in `Recommendation`.
- `tts_keep_alive_s` field in `LoadPolicy` (S6).

## 7. Multilingual caveat

Piper has separate voice models per language. For Spanish use
`es_ES-davefx-medium` or `es_MX-claude-high`. Selector emits the operator-facing
warning when no matching language voice is available locally (declarative table
in `voice_languages.json` — added when Carter ships speaker capability).

## 8. Acceptance for closure

- ✅ Backend probe captured.
- ✅ Per-profile picks documented.
- ✅ Install commands listed.
- ✅ Latency budget stated.
- ✅ Scaffold runner exists.
- 🔄 Live first-audio bench (Carter speaker capability blocker).

Verdict: **TTS_READY_AS_SCAFFOLD**.
