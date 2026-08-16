# Carter v5 — Architecture

> Built from lessons of Carter v1–v4 (see `legacy/`), the validated harness
> `Probando Gemma 4` (540/540 PASS with Gemma 4 E4B-Q6_K), and 10 competitor
> projects analyzed in [`La razon de carter/14_auditoria_competidores.md`](../../La razon de carter/14_auditoria_competidores.md).

## Patterns absorbed from competitors

| Pattern | Source | Module in Carter v5 |
|---|---|---|
| **microagents** — markdown context injection by trigger | OpenHands `.openhands/microagents/` | `microagents/` + `core/agent_base.py:_ensure_stable_context` |
| **persistent bash session** (ConPTY) — state preserved across tool calls | OpenHands tmux pattern | `tools/bash_session.py` + `tools/terminal.py:terminal_session` |
| **MCP server** — expose tools to Cursor / Claude Desktop / goose | goose 70+ extensions | `mcp_server.py` (stdio + HTTP modes) |
| **durable state** — agent state persisted to disk, resume on restart | langgraph durable execution | `core/durable_state.py` + auto-save in `_append_history` |
| **mission goal verifier** — verify OBJECTIVE not action | Voyager NeurIPS 2023 | `mission/goal.py` + `mission/verifier.py` |
| **minimal hierarchy** — 1 Worker, no Manager/Worker split | Agent-S3 v3 simplification | `core/agent_base.py` (no sub-agents in v5.0) |
| **9 outcome states** (COMPLETED/PARTIAL/UNVERIFIED/...) | Carter v4 inheritance | `core/types.OutcomeStatus` |
| **causal recovery** (UI-TARS-2 pattern) | UI-TARS-2 paper | `tools/gui.py:_focus_window_changed_by_last_action` |



---

## Principles (from `La razon de carter/12_carter_v5_arquitectura.md`)

| # | Principle | Implementation |
|---|---|---|
| P1 | TODO sobre Gemma 4 | Each tier picks the best Gemma 4 quant that fits its VRAM |
| P2 | Honestidad por construcción (V3) | Structural verifiers + mission goal + `UNVERIFIED` honest fallback |
| P3 | Universal, sin per-app (V6, V7) | resolve_app + HKCR registry + SequenceMatcher cross-lingual |
| P4 | Stable prompt preserves cache | system_msg fixed per session, history append-only |
| P5 | Stable catalog preserves cache | tools subset per tier, NO per-turn retrieval |
| P6 | Mission-level + per-tool verifier | MissionGoal (Voyager) + per-tool VerifierOutcome |
| P7 | UN router pre-LLM, sin solapamiento | `core/router.py` único |
| P8 | Bench como sanity, calidad como criterio | bench + human review |
| P9 | Cada cambio medible aislado | one variable per iteration + golden tests |
| P10 | Trabajo determinista FUERA del LLM | LLM = interpretar/descomponer/explicar; código = el resto |

---

## Turn flow

```
USER (text / voice / image)
  │
  ├── voice  → faster-whisper-turbo → text
  ├── image  → base64 PNG → image_url block
  └── text   ─┐
              │
              ▼
       ┌──────────────────────┐
       │  core/router.py      │  ← Single pre-LLM classifier
       │  → Intent            │     (archetype, sampling, short-circuit?)
       └──────────┬───────────┘
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
  [Trivial?]          [Anything else]
    canned reply         continue
    no LLM call           │
        │                 ▼
        │       ┌──────────────────────┐
        │       │ context_builder.py   │ ← Stable prefix
        │       │  system_msg = fixed  │   (cache-friendly)
        │       │  tools = fixed[tier] │
        │       │  history = appended  │
        │       └──────────┬───────────┘
        │                  │
        │                  ▼
        │       ┌──────────────────────┐
        │       │ llama-server :8080   │ ← Gemma 4 (tier-specific quant)
        │       │  --jinja --mmproj    │
        │       └──────────┬───────────┘
        │                  │
        │                  ▼ tool_calls
        │       ┌──────────────────────┐
        │       │ core/execution.py    │ ← dispatch + verify + chain
        │       │  while tool_calls:   │
        │       │   - safety check     │
        │       │   - tools.dispatch   │
        │       │   - verify.verify    │
        │       │   - mission.update   │
        │       │   - loop.detect      │
        │       │   - vision_inline?   │ ← tier 12+/16 only
        │       │   - LLM follow-up    │
        │       └──────────┬───────────┘
        │                  │
        │                  ▼
        │       ┌──────────────────────┐
        │       │ mission/verifier.py  │ ← Voyager pattern
        │       │  → MissionOutcome    │
        │       │    COMPLETED |       │
        │       │    PARTIAL |         │
        │       │    UNVERIFIED |      │
        │       │    FAILED |          │
        │       │    NEEDS_USER |      │
        │       │    NEEDS_PERMISSION |│
        │       │    BLOCKED_BY_POLICY|│
        │       │    INTENT_NOT_FULFILLED │
        │       └──────────┬───────────┘
        │                  │
        ▼                  ▼
       TurnResult ◄────────┘
       (reply, tool_calls, outcome, trace_id, latency_ms)
```

---

## Module map

```
carter_v5/
├── core/                  ← shared agent primitives
│   ├── types.py           ← Pydantic-style dataclasses (Intent, MissionOutcome, etc.)
│   ├── router.py          ← single pre-LLM classifier
│   ├── context_builder.py ← STABLE prefix preservation
│   ├── agent_base.py      ← AgentBase ABC (run_turn)
│   └── execution.py       ← tool dispatch + chain loop
│
├── mission/               ← Voyager-style mission verifier
│   ├── goal.py            ← MissionGoal (structural detector, no LLM)
│   └── verifier.py        ← compute_mission_outcome
│
├── tools/                 ← 60 tools + composite_dispatcher (16 composite)
│   ├── __init__.py        ← @tool decorator + dispatch
│   ├── apps.py            ← universal resolve_app (cross-lingual)
│   ├── gui.py             ← causal focus + Win32 frame_diff
│   ├── gui_universal.py   ← 5-tier (deeplink/UIA/OCR/VLM) action
│   ├── filesystem.py
│   ├── web.py
│   ├── system.py          ← pycaw, system_time, etc.
│   ├── vision_tools.py    ← Gemma 4 vision via image_url
│   ├── deeplinks.py       ← HKCR registry universal
│   ├── composite_dispatcher.py  ← 16 composite → 60 individual
│   └── schemas_consolidated.json
│
├── verify/                ← per-tool verifiers + runtime checks
│   ├── core.py            ← VerifierOutcome + register_verifier
│   └── runtime.py         ← pycaw, EnumWindows, frame_diff
│
├── memory/                ← SQLite + multilingual-e5-small embedder
│   └── store.py           ← Memory(filter_secret, get_relevant, save)
│
├── safety/                ← destructive intent + confirmation
│   ├── policy.py          ← evaluate_tool_call, Snowball stems
│   └── confirm.py         ← is_affirmative/is_negative
│
├── loop/                  ← loop_detection v2 result-aware
│   └── detection.py
│
├── hardware/              ← VRAM detect + tier selector
│   ├── profile.py
│   └── tier.py            ← detect_tier + TIER_SPECS
│
├── adapters/              ← LLM backend
│   ├── llamacpp.py        ← OpenAI-compat to llama-server (default for Gemma 4)
│   └── ollama.py          ← Ollama backend con tools nativos (alternativa)
│
├── observability/         ← jsonl tracing per turn
│   └── tracing.py
│
├── multimodal/            ← STT (Whisper external) + vision helpers
│   ├── whisper_stt.py     ← faster-whisper-turbo
│   └── vision_helpers.py  ← base64 image_url encoder
│
├── profiles/              ← per-tier agent implementations
│   ├── tier_6gb/          ← E4B-IQ2_M (12 tools, 5.13 GB VRAM)
│   ├── tier_8gb/          ← E4B-Q5_K_M (14 tools, 6.61 GB VRAM)
│   ├── tier_10gb/         ← E4B-Q8_0 (15 tools, 8.16 GB VRAM)
│   ├── tier_12gb/         ← 26B-A4B-Q3_K_XL (15 tools, ~13.5 GB)
│   └── tier_16gb/ ⭐       ← 26B-A4B-IQ4_XS (16 tools, ~14.5 GB)
│
├── scripts/
│   ├── start_carter.py    ← bootstrap (detect VRAM → spawn → REPL)
│   └── start_llama_server.ps1
│
├── tests/
│   ├── unit/              ← router, mission_goal, tiers
│   └── integration/       ← agent loop with mock LLM
│
├── cli.py                 ← REPL entry point
├── pyproject.toml
└── README.md
```

---

## Multimodal capabilities by tier

| Tier | Vision (Gemma 4 native) | Audio (Whisper external) | Audio (Gemma 4 native) |
|---|:---:|:---:|:---:|
| 6GB | ✅ (image budget 560) | ✅ (faster-whisper-turbo) | ❌ |
| 8GB | ✅ (image budget 1120) | ✅ | ❌ |
| 10GB | ✅ (image budget 1120) | ✅ | ❌ |
| 12GB | ✅ + inline auto-step | ✅ | ❌ |
| 16GB | ✅ + inline auto-step | ✅ | ❌ |

**Audio native disabled across all tiers** because:
- llama-server's `input_audio` HTTP routing is NOT implemented as of 2026-05
  (ggml-org/llama.cpp issue #21868).
- Gemma 4 audio quality in Spanish rioplatense measured 2/5 in Probando Gemma 4
  Bloque D (vs Whisper-large-v3 ~95%).

When llama-server adds `input_audio` AND Gemma 4 audio improves for es-AR,
re-evaluate using native instead of Whisper.

---

## References

### Gemma 4
- [Hugging Face blog: Welcome Gemma 4](https://huggingface.co/blog/gemma4)
- [Gemma 4 function calling docs](https://ai.google.dev/gemma/docs/capabilities/text/function-calling-gemma4)
- [Probando Gemma 4 REPORTE_EXTENDIDO.md](../../docs/investigaciones/evidencia pruebas gemma4/REPORTE_EXTENDIDO.md)

### llama.cpp
- [Function calling docs](https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md)
- PR #21418 — specialized Gemma 4 parser (b9090+)
- PR #21421 — audio Conformer encoder
- Issue #21868 — input_audio HTTP routing missing

### Agent design
- [Anthropic: Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
- [Voyager NeurIPS 2023](https://voyager.minedojo.org/)
- [Reflexion NeurIPS 2023](https://arxiv.org/abs/2303.11366)
- [UI-TARS-2 (arxiv 2509.02544)](https://arxiv.org/abs/2509.02544)
- [RAG-MCP (arxiv 2505.03275)](https://arxiv.org/abs/2505.03275)
- [HuggingFace Gemma 3 4B discussion #24](https://huggingface.co/google/gemma-3-27b-it/discussions/24)

### Windows automation
- [Microsoft Learn: AllowSetForegroundWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-allowsetforegroundwindow)
- [Microsoft Learn: Registering URI Schemes](https://learn.microsoft.com/en-us/previous-versions/windows/internet-explorer/ie-developer/platform-apis/aa767914(v=vs.85))
- [pywinauto docs](https://pywinauto.readthedocs.io/)

### Speech-to-text
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- [Whisper Large V3 Turbo](https://www.baseten.co/library/whisper-large-v3-turbo-streaming/)
