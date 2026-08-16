# Carter v5

**Local Windows assistant powered by Gemma 4 (multimodal: text + vision + audio).**

Built from lessons of Carter v1 → v4 (see `legacy/`) and the validated harness `Probando Gemma 4` (540/540 PASS with Gemma 4 E4B-Q6_K).

---

## Highlights

- **100% local**, no cloud. Privacy by design (ContextoCarter V1).
- **Honestidad por construcción** (V3): structural verifiers + mission-goal verifier, never claim DONE without proof.
- **Multi-profile by VRAM**: 5 tiers (6 / 8 / 10 / 12 / 16 GB), each with the best Gemma 4 quant that fits.
- **Universal** (V6, V7): cero per-app hardcodes. Resolution via Win32 registry (HKCR), Get-StartApps, SequenceMatcher cross-lingual, deeplink URI handlers.
- **Multimodal**:
  - **Text**: Gemma 4 native tool calling via `--jinja` (PR #21418 specialized parser).
  - **Vision**: mmproj-F16 loaded, `image_url` content blocks on llama-server.
  - **Audio**: faster-whisper-large-v3-turbo (external, real-time streaming on Windows).
- **Streaming SSE**: first-token <500ms target.

---

## Architecture (in 1 picture)

```
USER (text / voice / image)
  │
  ├── voice  → faster-whisper-turbo → text
  ├── image  → image_url base64 → llama-server (Gemma 4 vision)
  └── text   ─┐
              │
              ▼
       ┌──────────────────────┐
       │  core/router.py      │  ← UN router pre-LLM
       │  → Intent            │     (archetype, mission_goal, sampling)
       └──────────┬───────────┘
                  │
                  ▼
       ┌──────────────────────┐
       │ core/context_builder │  ← STABLE prefix (preserve cache)
       │  → system_msg fijo   │
       │  → tools[TIER] fijo  │
       │  → history append    │
       └──────────┬───────────┘
                  │
                  ▼
       ┌──────────────────────┐
       │ llama-server :8080   │  ← Gemma 4 (tier-specific quant)
       │  --jinja --mmproj    │
       └──────────┬───────────┘
                  │
                  ▼ tool_calls
       ┌──────────────────────┐
       │ core/execution.py    │  ← dispatch + verify + chain
       │  while tool_calls:   │
       │   - safety.evaluate  │
       │   - tools.dispatch   │
       │   - verify.verify    │
       │   - mission.update   │
       │   - loop.detect      │
       └──────────┬───────────┘
                  │
                  ▼
       ┌──────────────────────┐
       │ mission/verifier.py  │
       │ → OUTCOME state      │
       │   COMPLETED|PARTIAL| │
       │   FAILED|UNVERIFIED| │
       │   NEEDS_USER|...     │
       └──────────┬───────────┘
                  │
                  ▼
              TurnResult
```

---

## Profiles (by VRAM)

| Tier | Model | Quant | VRAM | Tools | Source |
|---|---|---|---|---|---|
| 6GB | gemma-4-E4B-it | UD-IQ2_M | 5.13 GB | 12 composite | `profiles/tier_6gb/` |
| 8GB | gemma-4-E4B-it | Q5_K_M | 6.61 GB | 14 composite | `profiles/tier_8gb/` |
| 10GB | gemma-4-E4B-it | Q8_0 | 8.16 GB | 15 composite | `profiles/tier_10gb/` |
| 12GB | gemma-4-26B-A4B-it | UD-Q3_K_XL | ~13.5 GB | 15 composite | `profiles/tier_12gb/` |
| **16GB** ⭐ | gemma-4-26B-A4B-it | UD-IQ4_XS | ~14.5 GB | 16 composite | `profiles/tier_16gb/` |

Each tier has its own `agent.py`, `prompt.py`, `config.py`, `tools_subset.py` — optimized for that VRAM.

---

## Quick start

```powershell
# 1. Install (one time)
pip install -e .[dev]

# 2. Auto-detect VRAM and start
python -m carter_v5.cli

# 3. Force a specific tier
python -m carter_v5.cli --tier 16gb

# 4. With audio (microphone via Whisper)
python -m carter_v5.cli --audio
```

---

## Folder structure

```
Carterv5/
├── core/              ← shared agent loop, router, execution, context
├── mission/           ← MissionGoal (Voyager pattern), outcomes, verifier
├── tools/             ← 60 tools registry + composite_dispatcher (16 composite)
├── adapters/          ← llamacpp (OpenAI-compat), base protocol
├── verify/            ← VerifierOutcome + runtime verifiers (pycaw, EnumWindows, frame_diff)
├── memory/            ← SQLite + multilingual-e5-small embedder
├── safety/            ← destructive intent multilingual (Snowball stems)
├── loop/              ← v2 result-aware detection (Reflexion + zeroclaw #2152 fix)
├── hardware/          ← VRAM detection + tier selector
├── observability/     ← jsonl tracing per turn
├── multimodal/        ← whisper STT + image_url base64 helpers
├── profiles/          ← one folder per tier (6/8/10/12/16 GB)
│   └── tier_<N>gb/
│       ├── agent.py
│       ├── prompt.py
│       ├── config.py
│       └── tools_subset.py
├── scripts/
│   ├── start_llama_server.ps1
│   └── start_carter.py
├── tests/
│   ├── unit/
│   ├── integration/   (mock LLM, golden paths)
│   └── bench/         (540 cases per tier)
├── cli.py             ← REPL entry point
├── pyproject.toml
└── README.md
```

---

## References

- `../La razon de carter/11_lecciones_v1_a_v4.md` — lessons from v1→v4
- `../La razon de carter/12_carter_v5_arquitectura.md` — full architecture
- `../La razon de carter/13_carter_v5_perfiles_vram.md` — per-tier specs
- `../ContextoCarter.md` — 30 design values
- `../Probando Gemma 4/` — Gemma 4 validation (540/540 reproducible)
- Gemma 4 model card: <https://huggingface.co/blog/gemma4>
- llama.cpp function calling: <https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md>

---

## License

MIT (same as legacy versions).
