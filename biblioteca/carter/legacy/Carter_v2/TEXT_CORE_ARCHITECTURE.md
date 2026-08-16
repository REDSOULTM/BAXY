# TEXT_CORE_ARCHITECTURE — Carter v2 (Release Candidate)

Frozen description of the **text-mode core** of Carter v2. This is the base
layer; voice, mic, camera and real-time vision will plug on top of these
interfaces without modifying the core.

---

## 1. Turn flow (single user message → single user-visible reply)

```
user_text
   │
   ▼
[runtime.session.engine] submit_text_turn(text)
   │
   ├── load MissionState (memory + recent turns + persistent facts)
   ├── classify intent (greet | identity | ack | noop | tool | compound | safety | …)
   ├── policy.preflight  → risk_gate / dry_run flags (session/policy.py)
   ├── select model      → model_registry.recommend() (no hardcoded names)
   ├── build_prompt      → system_prompt + memory window + last turns + user
   ├── llm_backends.complete(model, prompt, json_protocol_for_tools=True)
   ├── tool_dispatch     → executes ONLY if model emitted a structured tool call
   │                        and policy.allow(tool, args) returned ok
   ├── post_process      → strip placeholders, enforce no-fake-success, summarize
   └── memory.save_turn / save_fact (PersistentMemory)
   │
   ▼
final_text  (single reply, no leaked tool JSON, no placeholders)
```

Source anchors:

- [src/carter_v2/runtime/](src/carter_v2/runtime) — engine + entry points
- [src/carter_v2/session/memory.py](src/carter_v2/session/memory.py) — `PersistentMemory`
- [src/carter_v2/session/policy.py](src/carter_v2/session/policy.py) — risk gate + dry-run
- [src/carter_v2/models/](src/carter_v2/models) — registry + selector
- [src/carter_v2/llm/](src/carter_v2/llm) — backends, JSON tool-call protocol

## 2. MissionState

In-memory snapshot per turn:

- `user_text`, `intent`, `tool_calls[]`, `tool_results[]`
- `memory_window` (recent turns, capped)
- `facts` (persistent — explicit-write-only via `PersistentMemory.save_fact`)
- `policy_flags` (risk, dry_run, destructive)
- `model_choice` (selected at runtime, never hardcoded)

## 3. Tools (text-only surface)

Whitelisted in [src/carter_v2/runtime/tools/](src/carter_v2/runtime/tools):
clock/time, system info, web fetch (read-only), filesystem (read-only by
default; write requires risk gate ok), GUI/vision-from-text (offline screen
description), Steam launch (dry-run by default), compound dispatch (sequencing).

Hard rules:

- No tool runs unless the model emits a valid tool-call JSON object.
- No tool runs if `policy.allow(...)` returns deny.
- No tool returns "success" without verifying its real effect → enforced in
  [audit/results/RUNTIME_TOOL_PROTOCOL_FINAL_GATE.json](audit/results/RUNTIME_TOOL_PROTOCOL_FINAL_GATE.json)
  (24/25 cases pass, `fake_success: 0`).

## 4. Model protocol

- Registry: [src/carter_v2/models/model_registry.py](src/carter_v2/models/model_registry.py)
- Selector: [src/carter_v2/models/selector.py](src/carter_v2/models/selector.py)
- Default: `qwen3:8b` (rollback baseline).
- Recommended 16 GB: `hermes3:8b` (json_direct).
- See [TEXT_CORE_MODEL_DECISION.md](TEXT_CORE_MODEL_DECISION.md).

JSON tool-call protocol is per-model (json_direct vs. json_in_text). Selection
happens through the registry; no model name appears as a string literal in the
runtime/session code.

## 5. Memory & context

- Window: last N turns + summarized older context.
- Persistent facts: opt-in via `save_fact()` (explicit write API only).
- No silent contamination across unrelated topics — soak test enforces this
  ([audit/results/TEXT_CORE_SOAK_TEST.json](audit/results/TEXT_CORE_SOAK_TEST.json)).

## 6. GUI / vision-from-text

Read-only screen-state summarization helpers live under
[src/carter_v2/runtime/tools/](src/carter_v2/runtime/tools). They produce text
that the LLM can reason over. **No** real-time camera or microphone here.

## 7. Safety

- `session/policy.py` decides risk + dry-run for every tool invocation.
- Destructive actions default to dry-run; require explicit user confirmation.
- Validated by [SKIPPED_LIVE_FINAL_GATE.json](audit/results/SKIPPED_LIVE_FINAL_GATE.json)
  and [CARTER_TEXT_FINAL_CLOSURE_REPORT](../CARTER_TEXT_FINAL_CLOSURE_REPORT.md).

## 8. Performance budgets (text-only)

See [TEXT_CORE_PERFORMANCE_FINAL.md](TEXT_CORE_PERFORMANCE_FINAL.md). Summary:
greet/ack/noop classified locally, no LLM round-trip; tool/compound paths
budgeted via [PERFORMANCE_GATE.json](audit/results/PERFORMANCE_GATE.json) and
[ULTRA_LATENCY_FINAL_GATE.json](audit/results/ULTRA_LATENCY_FINAL_GATE.json).

## 9. Voice / camera handoff

See [VOICE_CAMERA_HANDOFF_PLAN.md](VOICE_CAMERA_HANDOFF_PLAN.md). Future layers
MUST call into the existing `submit_text_turn()` boundary; they do **not**
rewrite the engine.
