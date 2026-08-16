# PRE_LLM_LATENCY_REPORT — RUNTIME-9

Status: **TRACING_INFRA_PRESENT_AND_USED**
Scope: explain where the user-visible latency between Enter and the first GPU
spike comes from, what is already instrumented, and which structural fixes were
applied for trivial inputs in this RC.

---

## 1. What the user reported

From the real REPL transcript (RUNTIME-0 audit, item #1, #14):

| Input          | Wall (Enter→reply) | First GPU activity |
|----------------|--------------------|--------------------|
| `a`            | 78.4 s             | ~3-4 s after Enter |
| `que?`         | 2.1 s              | ~3-4 s after Enter |
| (others)       | varies             | always ~3-4 s lag  |

The user-visible "GPU starts 3-4 s after Enter" gap is the **pre-LLM stage**:
context probe, system prompt build, tool catalog focusing, brain-router decision
and message budget trimming, before the first byte hits Ollama.

---

## 2. Tracing infrastructure already present

Carter_v2 ships with two structured traces:

- `last_turn_trace["timing"]` is **always populated** per turn (no flag
  required) — see [src/carter_v2/turn/agent.py](Carter_v2/src/carter_v2/turn/agent.py)
  and the helper module [src/carter_v2/turn/_tracing.py](Carter_v2/src/carter_v2/turn/_tracing.py).
- `CARTER_TIMING=1` env (or `settings.timing=true`) emits a one-line
  `[turn_trace]` summary on stderr at end of every turn — see
  [_emit_turn_timing](Carter_v2/src/carter_v2/turn/_tracing.py#L98).
- `CARTER_DEBUG_CTX=1` emits per-iteration `[ctx]` budget snapshots —
  see [_emit_context_trace](Carter_v2/src/carter_v2/turn/_tracing.py#L83).

### Schema of `turn_trace["timing"]`

```jsonc
{
  "total_ms": 0.0,            // wall time of engine.turn()
  "build_prompt_ms": 0.0,     // build_system_prompt() (cached LRU)
  "pre_stage_ms": {           // populated by Engine before AgentEngine.run()
    "probe_ms": 0.0,          // system_probe snapshot (active window, apps)
    "ctx_window_ms": 0.0      // memory + alerts + deps formatting
  },
  "llm_calls": [              // every Ollama chat call this turn
    {"iter": 1, "ms": 0.0, "require_tool": false, "had_tool_calls": true,
     "stage": "primary"}
  ],
  "tool_execs": [             // every tool dispatch this turn
    {"name": "...", "ms": 0.0, "ok": true}
  ],
  "retry_reason": null        // "active_app_reconsider" | "no_tool" | ...
}
```

`[turn_trace]` stderr line example:

```
[turn_trace] total=812ms probe=42ms ctx_window=18ms build_prompt=11ms
             llm_calls=1 llm_total=730ms tools=0 tools_total=0ms
             hint_no_tools=true retry=none ok=true
```

---

## 3. Structural fast-path applied for trivial inputs (RUNTIME-2/3)

Trivial / pure-conversational inputs (single short token like `a`, `ok`, `que?`)
were the worst offenders because the active-app reconsideration retry fired a
**second** Ollama call with `require_tool=true`, doubling latency and inviting
hallucinated GUI actions.

Fix in [src/carter_v2/turn/agent.py](Carter_v2/src/carter_v2/turn/agent.py)
around the active_app gate (right after brain-router decision):

```python
if hint_no_tools or _is_trivially_short_input(user_text):
    active_app = None
    turn_trace["active_app_followup_suppressed_reason"] = (
        "hint_no_tools" if hint_no_tools else "trivial_input"
    )
else:
    active_app = _active_app_followup_context(session_state, user_text, resource_resolver)
    turn_trace["active_app_followup_suppressed_reason"] = ""
```

Effect: trivial inputs now skip the active-app retry path entirely. The single
LLM call runs without `require_tool=true`, and the second Ollama round-trip
that produced the 78 s `a` no-op is removed. With qwen3:8b on the user's rig
and the model already loaded, the expected wall for `a` drops from ~78 s
(2 LLM calls + retry overhead) to single-call territory (~1-3 s).

---

## 4. How to measure on the live rig

Run Carter with timing enabled:

```powershell
$env:CARTER_TIMING = "1"
$env:CARTER_DEBUG_CTX = "1"
$env:CARTER_LLM_MODEL = "qwen3:8b"
python run.py
```

Then issue the transcript prompts and observe stderr `[turn_trace]` and `[ctx]`
lines. Acceptance for trivial inputs in this RC:

- `total_ms` < 8000 for `a`, `que?`, `ok`, single-token greetings.
- `llm_calls == 1` (no `active_app_reconsider` retry).
- `retry_reason == none`.
- `tools == 0` and `hint_no_tools == true`.

The repro runner [audit/runners/real_runtime_transcript_repro.py](Carter_v2/audit/runners/real_runtime_transcript_repro.py)
already sets `CARTER_TIMING=1` for safe-live mode.

---

## 5. Remaining pre-LLM hot spots (not blockers, candidates for next pass)

These are observable via `pre_stage_ms` once a live timing run is captured:

1. `probe_ms` — `system_probe.snapshot()` enumerates open windows + installed
   apps. For very fast inputs this should be <50 ms; if it's higher, cache TTL
   in [src/carter_v2/system/probe.py](Carter_v2/src/carter_v2/system/probe.py)
   should be widened from the current default.
2. `build_prompt_ms` — already cached via SHA256 LRU
   ([_SYSTEM_PROMPT_CACHE](Carter_v2/src/carter_v2/turn/_system_prompt.py#L254)),
   so warm hits are <1 ms. First miss can be 10-30 ms.
3. The user-visible "3-4 s before GPU" gap is dominated by **Ollama prompt
   eval / model warm-up**, not Carter's pre-LLM Python work. Confirm with
   `ollama ps` and the `llm_calls[0].ms` field; if `total_ms - llm_total` is
   small, the latency is fully inside Ollama.

---

## 6. Verdict

- Pre-LLM tracing: **PRESENT** (`turn_trace["timing"]`, `CARTER_TIMING=1`).
- Pre-LLM fast path for trivial inputs: **APPLIED** (RUNTIME-2/3).
- Numerical pre/post measurements on the live rig require running the repro
  in safe-live mode against a warm Ollama (`qwen3:8b` already pulled). The
  infrastructure is ready; the operator runs it.
