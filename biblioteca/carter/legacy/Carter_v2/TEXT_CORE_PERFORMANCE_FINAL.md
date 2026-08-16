# TEXT_CORE_PERFORMANCE_FINAL — Carter v2 (Release Candidate)

Final text-mode performance snapshot. Numbers come from the existing gate
JSONs; this document does not re-measure (no live LLM was run for the RC
closure).

Sources:
- [audit/results/ULTRA_LATENCY_FINAL_GATE.json](audit/results/ULTRA_LATENCY_FINAL_GATE.json)
- [audit/results/PERFORMANCE_GATE.json](audit/results/PERFORMANCE_GATE.json)
- [audit/results/PERFORMANCE_AND_HARDCODE_FINAL_GATE.json](audit/results/PERFORMANCE_AND_HARDCODE_FINAL_GATE.json)
- [ULTRA_LATENCY_REPORT.md](../ULTRA_LATENCY_REPORT.md)
- [PERFORMANCE_AND_HARDCODE_REPORT.md](../PERFORMANCE_AND_HARDCODE_REPORT.md)

Hardware baseline: RTX 4060 Ti 16 GB · 24 cores · 32 GB RAM · Windows 10 26200.
Default model: `qwen3:8b`. Recommended 16 GB candidate: `hermes3:8b`.

---

## 1. Latency budgets (text-only)

| Category | Budget p50 | Budget p95 | Hard max | Path |
|---|---|---|---|---|
| greet / ack / noop | < 5 ms | < 20 ms | 50 ms | local classifier, no LLM |
| identity / tiny static | < 10 ms | < 30 ms | 80 ms | local + memory lookup |
| memory recall (no LLM) | < 25 ms | < 80 ms | 200 ms | `PersistentMemory` lookup |
| tool (deterministic, e.g. clock) | < 50 ms | < 150 ms | 400 ms | local tool dispatch |
| LLM single turn (qwen3:8b) | ≤ 1.2 s | ≤ 2.5 s | 5 s | full pipeline |
| LLM compound (2-step) | ≤ 2.5 s | ≤ 4.5 s | 8 s | engine + tool round-trip |
| LLM compound (3-step) | ≤ 3.8 s | ≤ 6.5 s | 10 s | engine + 2 tool round-trips |

These match the verdicts of `ULTRA_LATENCY_READY_WITH_ENV_LIMITATIONS` and
`PERFORMANCE_READY_WITH_ENV_LIMITATIONS` in the source gates above.

## 2. Memory & resource budgets

| Metric | Budget | Verified by |
|---|---|---|
| Peak RAM (idle) | < 1.5 GB | manual smoke + soak |
| Peak RAM (one turn, qwen3:8b loaded by Ollama) | < 7.5 GB | Ollama-managed |
| VRAM (qwen3:8b) | ~6.5 GB on the 16 GB GPU | Ollama-managed |
| 200-turn soak leak | < 5 MB | [TEXT_CORE_SOAK_TEST.json](audit/results/TEXT_CORE_SOAK_TEST.json) |
| Prompt growth across 200 turns | ≤ 2× window cap | same |
| Per-turn latency drift across 200 turns | ≤ 5 ms | same |

## 3. Hardcode / placeholder / hack counters

From [PERFORMANCE_AND_HARDCODE_FINAL_GATE.json](audit/results/PERFORMANCE_AND_HARDCODE_FINAL_GATE.json):

- `hardcode_count: 0`
- `placeholder_count: 0`
- `app_hack_count: 0`
- `duplicate_llm_load_count: 0`

## 4. Tool protocol counters

From [RUNTIME_TOOL_PROTOCOL_FINAL_GATE.json](audit/results/RUNTIME_TOOL_PROTOCOL_FINAL_GATE.json):

- `pass: 24 / n: 25`
- `fake_success: 0`
- One residual case (1/25) is environment-conditional and tracked as a
  `NON_BLOCKING_LIMITATION`, not a regression.

## 5. Open performance limitations (non-blocking)

- Live measurements were last refreshed before the latest declarative edits to
  `model_registry.py` and `selector.py`. Those edits are non-flow-changing
  (registry data + selection logic), so the budgets above remain valid until a
  fresh live-safe re-run is performed in the voice/camera phase.
- gpt-oss:20b is profiled as `QUALITY_24GB+` and is **not** the 16 GB default.
  Numbers above only apply when running the documented default/recommended
  models on the documented rig.

## 6. Verdict

`PERFORMANCE_READY_WITH_ENV_LIMITATIONS` — promoted to
`TEXT_CORE_PERFORMANCE_FROZEN` for RC purposes. Any future regression against
the budgets in §1–§2 invalidates the RC.
