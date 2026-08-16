# TEXT_CORE_INVARIANTS — Carter v2 (Release Candidate)

These are the rules that MUST NEVER break. Each invariant lists where it is
enforced and how it is verified. If any of these regress, the RC is broken.

| # | Invariant | Enforcement | Verification |
|---|---|---|---|
| 1 | No hardcoded model names in runtime/session code | [src/carter_v2/models/model_registry.py](src/carter_v2/models/model_registry.py) | [audit/results/PERFORMANCE_AND_HARDCODE_FINAL_GATE.json](audit/results/PERFORMANCE_AND_HARDCODE_FINAL_GATE.json) (`hardcode_count: 0`) |
| 2 | No hardcoded "magic" sentinel strings (`Hello world`, `lorem ipsum`, etc.) | [audit/hardcode_guard.py](audit/hardcode_guard.py) | Same gate (`placeholder_count: 0`) |
| 3 | No app/path hacks (no absolute Steam/Windows paths in core) | [src/carter_v2/runtime/tools/](src/carter_v2/runtime/tools) | Same gate (`app_hack_count: 0`) |
| 4 | No fake tool success — every tool must verify its own effect | [src/carter_v2/runtime/tools/](src/carter_v2/runtime/tools) | [audit/results/RUNTIME_TOOL_PROTOCOL_FINAL_GATE.json](audit/results/RUNTIME_TOOL_PROTOCOL_FINAL_GATE.json) (`fake_success: 0`, 24/25 pass) |
| 5 | No double LLM load per process | [src/carter_v2/llm/](src/carter_v2/llm) backend cache | [audit/results/PERFORMANCE_GATE.json](audit/results/PERFORMANCE_GATE.json) |
| 6 | No protocol/model-specific hacks in `runtime/` or `session/` | Per-model JSON strategy lives only in [src/carter_v2/llm/](src/carter_v2/llm) | [audit/results/MODEL_COMPATIBILITY_FINAL_GATE.json](audit/results/MODEL_COMPATIBILITY_FINAL_GATE.json) |
| 7 | Memory writes are explicit-only (`PersistentMemory.save_fact`) | [src/carter_v2/session/memory.py](src/carter_v2/session/memory.py) | [audit/results/LLM_CONTEXT_MEMORY_PROBE.json](audit/results/LLM_CONTEXT_MEMORY_PROBE.json) + soak test |
| 8 | Risk gate runs on every tool call | [src/carter_v2/session/policy.py](src/carter_v2/session/policy.py) | [audit/results/SKIPPED_LIVE_FINAL_GATE.json](audit/results/SKIPPED_LIVE_FINAL_GATE.json) |
| 9 | Destructive actions default to dry-run | [src/carter_v2/session/policy.py](src/carter_v2/session/policy.py) | Same gate + [CARTER_TEXT_FINAL_CLOSURE_REPORT.md](../CARTER_TEXT_FINAL_CLOSURE_REPORT.md) |
| 10 | Greet / ack / noop never trigger an LLM round-trip | [src/carter_v2/runtime/](src/carter_v2/runtime) classifier | [audit/results/ULTRA_LATENCY_FINAL_GATE.json](audit/results/ULTRA_LATENCY_FINAL_GATE.json) |
| 11 | Tool reply never leaks into final user text as raw JSON | [src/carter_v2/runtime/](src/carter_v2/runtime) post-processor | [audit/results/FULL_LIVE_LLM_VALIDATION_LIVE_SAFE.json](audit/results/FULL_LIVE_LLM_VALIDATION_LIVE_SAFE.json) |
| 12 | No `action_failed` returned to user when the underlying issue is controllable | [src/carter_v2/runtime/](src/carter_v2/runtime) | [ACTION_FAILED_ELIMINATION_REPORT.md](../ACTION_FAILED_ELIMINATION_REPORT.md) |
| 13 | Soak test: 200 turns, no leak > 5 MB, no prompt growth > 2× cap, drift ≤ 5 ms | [audit/runners/text_core_soak_test.py](audit/runners/text_core_soak_test.py) | [audit/results/TEXT_CORE_SOAK_TEST.json](audit/results/TEXT_CORE_SOAK_TEST.json) (SOAK_PASSED) |
| 14 | Golden behavioural matrix: 19/19 contracts pass | [audit/runners/text_core_golden_matrix.py](audit/runners/text_core_golden_matrix.py) | [audit/results/TEXT_CORE_GOLDEN_MATRIX.json](audit/results/TEXT_CORE_GOLDEN_MATRIX.json) (GOLDEN_MATRIX_PASSED) |
| 15 | pytest green (excluding the legacy `test_main_jarvis.py` and live-only tests) | [tests/](tests) | `pytest -q --ignore=tests/test_main_jarvis.py -k "not live"` → 481 passed |
| 16 | No voice/camera/mic code paths in runtime, session, or models | [src/carter_v2/](src/carter_v2) | grep audit; [VOICE_CAMERA_HANDOFF_PLAN.md](VOICE_CAMERA_HANDOFF_PLAN.md) keeps them out |

If any invariant flips, the RC verdict in
[audit/results/CARTER_TEXT_CORE_RC_FINAL_GATE.json](audit/results/CARTER_TEXT_CORE_RC_FINAL_GATE.json)
must be downgraded and the rollback baseline (qwen3:8b default) restored.
