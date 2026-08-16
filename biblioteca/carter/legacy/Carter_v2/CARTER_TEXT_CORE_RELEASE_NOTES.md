# CARTER_TEXT_CORE_RELEASE_NOTES — v2 RC

**Status:** `CARTER_TEXT_CORE_RELEASE_CANDIDATE`
**Date:** RC closure pass (post AUTO_MODEL_STACK closure).
**Rig:** RTX 4060 Ti 16 GB · 24 cores · 32 GB RAM · Windows 10 26200.
**Default model:** `qwen3:8b` (rollback baseline). Recommended 16 GB
candidate: `hermes3:8b` (json_direct). Full table in
[TEXT_CORE_MODEL_DECISION.md](TEXT_CORE_MODEL_DECISION.md).

---

## What is closed in this RC

- **Engine.** Single text-turn flow with classifier → policy → model selector →
  LLM → tool dispatch → post-process → memory write.
  See [TEXT_CORE_ARCHITECTURE.md](TEXT_CORE_ARCHITECTURE.md).
- **Model layer.** Registry + selector with no hardcoded names, per-model JSON
  tool-call protocol confined to [src/carter_v2/llm/](src/carter_v2/llm).
- **Tools.** Whitelisted, risk-gated, no fake success
  (`fake_success: 0`, 24/25 pass). See
  [audit/results/RUNTIME_TOOL_PROTOCOL_FINAL_GATE.json](audit/results/RUNTIME_TOOL_PROTOCOL_FINAL_GATE.json).
- **Memory.** Explicit-write API only (`PersistentMemory.save_fact`); no
  silent contamination across topics; verified by
  [audit/results/TEXT_CORE_SOAK_TEST.json](audit/results/TEXT_CORE_SOAK_TEST.json).
- **Safety.** Risk gate + dry-run by default; destructive ops require
  confirmation. See [audit/results/SKIPPED_LIVE_FINAL_GATE.json](audit/results/SKIPPED_LIVE_FINAL_GATE.json).
- **Performance.** Budgets frozen in
  [TEXT_CORE_PERFORMANCE_FINAL.md](TEXT_CORE_PERFORMANCE_FINAL.md);
  `PERFORMANCE_READY_WITH_ENV_LIMITATIONS` and
  `ULTRA_LATENCY_READY_WITH_ENV_LIMITATIONS` honored.
- **Quality gates.**
  - pytest: 481 passed (excluding `tests/test_main_jarvis.py` and `-k "not live"`).
  - hardcode_guard: 0 / 0 / 0.
  - Soak test: SOAK_PASSED.
  - Golden matrix: 19/19 GOLDEN_MATRIX_PASSED.
  - RC aggregator: `TEXT_CORE_RC_GATES_OK`.
- **Documentation.**
  - [CARTER_TEXT_CORE_RC_AUDIT.md](CARTER_TEXT_CORE_RC_AUDIT.md)
  - [TEXT_CORE_MODEL_DECISION.md](TEXT_CORE_MODEL_DECISION.md)
  - [TEXT_CORE_ARCHITECTURE.md](TEXT_CORE_ARCHITECTURE.md)
  - [TEXT_CORE_INVARIANTS.md](TEXT_CORE_INVARIANTS.md)
  - [TEXT_CORE_PERFORMANCE_FINAL.md](TEXT_CORE_PERFORMANCE_FINAL.md)
  - [TEXT_CORE_CLEANUP_PLAN.md](TEXT_CORE_CLEANUP_PLAN.md)
  - [VOICE_CAMERA_HANDOFF_PLAN.md](VOICE_CAMERA_HANDOFF_PLAN.md)

## What is explicitly OUT of scope (future layers)

- Voice / microphone / hotword.
- Camera / always-on vision / streaming vision.
- Real-time transcription.
- Any new tool family beyond what is already in [src/carter_v2/runtime/tools/](src/carter_v2/runtime/tools).
- Any model name change as default (`qwen3:8b` stays default until the user
  explicitly approves a swap; see [TEXT_CORE_MODEL_DECISION.md](TEXT_CORE_MODEL_DECISION.md)).
- Repo cleanup / file deletion (see [TEXT_CORE_CLEANUP_PLAN.md](TEXT_CORE_CLEANUP_PLAN.md);
  plan only, no actions).

## Known non-blocking limitations

- 1/25 case in the runtime tool protocol probe is environment-conditional;
  tracked as `NON_BLOCKING_LIMITATION`.
- Last live-safe + ultra-latency runs predate the latest declarative edits to
  `model_registry.py` and `selector.py`. Those edits do not change the turn
  flow; budgets remain valid. A fresh live-safe re-run is recommended at the
  start of the voice/camera phase, not as a blocker for this RC.

## Rollback plan

1. Revert `models/selector.py` and `models/model_registry.py` to the qwen3:8b
   default if any regression is observed.
2. Re-run `python audit/runners/text_core_rc_gates.py` and
   `python audit/runners/text_core_golden_matrix.py`.
3. If both pass, the RC is restored.

## Sign-off

This RC is the canonical text-mode baseline for Carter. Voice and camera
work begin from this commit and must conform to
[VOICE_CAMERA_HANDOFF_PLAN.md](VOICE_CAMERA_HANDOFF_PLAN.md).
