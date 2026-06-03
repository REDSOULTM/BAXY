# Sprint 4 — Log (structural duplication removal)

- **Started:** 2026-05-17
- **Finished:** 2026-05-17 (same session)
- **Operator:** Claude Code (Opus 4.7)
- **Base commit:** b1b14dc `docs(sprint_prompts): add Sprint 4 (structural duplication removal)`
- **Final code commit:** 1d3c9ff `sprint4: remove TimelineWriter (4 sinks → 3) — audit §2.5 partial`
- **Net delta vs base:** 8 files changed, **+191 insertions, −353 deletions = −162 LOC**
- **`COMPOUND_TOOL_SCHEMAS`:** 65 → 65 (unchanged, as the prompt required)

## Headline

Three of the five planned cuts done in full, two deliberately partial.
Worker triple-collapse and TraceLogger removal were both downscoped
after pre-flight reading exposed risks the prompt couldn't have known
about; the safe slice was committed, the rest deferred to Sprint 5
with a clear note.

## 4.1 — `_redact_*` unification — commit 857d24a ✅

`tools._redact_sensitive` and `domain_tools._redact_credentials` were
byte-for-byte identical; the only reason both existed was to dodge an
import cycle. New module **`gemma4_agent/_shared.py`** holds the
canonical `redact_sensitive` (pure stdlib + typing). Both modules
keep their previous internal names via
`from ._shared import redact_sensitive as _redact_sensitive` /
`as _redact_credentials`, so the 4 call sites needed no change.

Verified: `_redact_sensitive is _redact_credentials is _shared.redact_sensitive`; `test_log_audit_fixes.py` 22/22.

## 4.2 — `_hard_gate` unification — commit 92aa99a ✅

Two conventions co-existed for the same gate:

- `tools.ToolRegistry._hard_gate`: method, uses `self.state`, `tool_name=`
  kwarg, expects the caller to read `routine_context` /
  `confirmed_at_create` off `args` and pass them as explicit kwargs.
- `domain_tools._hard_gate`: function, `state=` param, `tool=` kwarg,
  reads `routine_context` / `confirmed_at_create` from `args` itself.

Unified `_shared.hard_gate` accepts both conventions:
- `tool=` or `tool_name=` (alias)
- `routine_context=None` / `confirmed_at_create=None` triggers the
  in-body read from `args` (domain_tools style); explicit values
  override (ToolRegistry style).

`domain_tools._hard_gate` is now a re-export. `ToolRegistry._hard_gate`
is a thin wrapper that injects `self.state`. All 6 call sites unchanged.

Verified: 69/69 across the four tests the prompt called out
(`test_tool_dispatch_contract`, `test_session847_fixes`,
`test_inherit_tools_safety`, `test_log_audit_fixes`).

## 4.3 — Worker triple-collapse — commit 86c9c0a (PARTIAL) ⚠

### What the prompt asked for

Collapse `AgentWorker` (PyQt6 `QThread`, 220 LOC), `AgentRunner`
(threading.Thread, 552 LOC) and `ServerBootWorker` (nested in
main_window, ~100 LOC) into a shared `AgentSerialWorker` base + thin
adapters. Expected delta: ~440 LOC removed.

### What I found in pre-flight

After reading all three files top to bottom, the two main workers
diverge in everything except the tiny dataclass `_TurnRequest` and the
arg-preview helper `_fmt_args`:

| Aspect | `AgentRunner` | `AgentWorker` | `ServerBootWorker` |
|---|---|---|---|
| Threading | `threading.Thread(daemon=True)` | `QThread` | `QThread` |
| Output | `BUS.publish({"type": ...})` | `pyqtSignal(...)` | `pyqtSignal(...)` |
| `_build_agent` | Long: autostart llama-server → semantic_router warmup in background → /health → 1-tok warmup → KV prewarm (via `prewarm.prewarm_kv`) → vision_relaunch callback wiring | Short: build agent → /health → start 8-s health-poll daemon loop | N/A |
| Boot llama-server | Inline | Delegated to ServerBootWorker | Yes, its only purpose |
| Health loop | None (warmup latch flips once) | Background daemon every 8 s | None |
| Singleton | Module-level `RUNNER` | Per-MainWindow instance | Per-MainWindow instance |

The non-trivial differences (boot sequence, reporter style, presence
of a health loop) mean a clean shared base would need to abstract over
both output channels AND over what gets done at boot. Each call site
in MainWindow / FastAPI / WS clients has expectations about exactly
what events fire and in what order; subtle re-ordering at the shared
layer would surface as "the UI loader doesn't advance" or "the WS
client never gets `ready`". The prompt explicitly authorized scope
reduction in this case ("Si dudás entre 'refactorizar' y 'dejar': dejá").

### What I committed

Only the byte-identical pieces — `_TurnRequest` dataclass and
`fmt_tool_args` helper — moved to `_shared.py` as canonical names
(`TurnRequest`, `fmt_tool_args`). Both workers keep their internal
aliases (`_TurnRequest`, `_fmt_args`) so no call site moved.

Delta: −36 LOC instead of the planned −440. The bulk of the audit §2.1
debt remains for Sprint 5, which is already scheduled for the
god-class refactor and is the natural home for this work
(tests-first + a real Worker class extracted from `Gemma4Agent`).

`ServerBootWorker` left in place.

## 4.4 — Sink consolidation — commit 1d3c9ff (PARTIAL) ⚠

### What the prompt asked for

Remove `TraceLogger` (67 LOC, `gemma4_agent/tracing.py`) and
`TimelineWriter` (137 LOC, `gemma4_agent/timeline.py`), migrating
their callers to `LogRecorder` (canonical) via `BUS.publish`.

### What I found in pre-flight

- **TimelineWriter** has exactly one caller: `chat.py:438`.
  Producing data that duplicates a subset of what TraceLogger already
  writes. Safe to delete.
- **TraceLogger** has ~50+ call sites in `agent.py` alone
  (`self.trace.event(...)` everywhere). It writes to
  `gemma4_agent/data/traces.jsonl`, which is the input file that
  `scripts/analyze_traces.py` reads for the Sprint 2 usage reports.
  Replacing it requires:
  1. Rewriting every `self.trace.event(turn_id, kind, **payload)` to
     `BUS.publish({"type": "trace", "turn_id": turn_id, "kind": kind,
     **payload})`.
  2. Extending `LogRecorder` to capture `type: "trace"` events outside
     the FastAPI server context — chat.py CLI has no FastAPI BUS
     subscriber today.
  3. Updating `scripts/analyze_traces.py` to read the new path /
     format.

That's a large coordinated migration with high risk of breaking
observability for very little user-visible benefit (the win is
deduplication, not new feature). The Sprint 2 report we just ran
depends on the existing JSONL shape.

### What I committed

Only the safe slice: removed `gemma4_agent/timeline.py`, removed its
single caller in `chat.py:438`, removed three timeline tests in
`test_gx_features.py` plus their entries in the harness list.

Delta: −195 LOC (137 file + ~58 from chat.py / tests).

The sink count went **4 → 3**, not 4 → 2 as planned. TraceLogger
removal logged for Sprint 5 alongside the AgentSerialWorker work.

## 4.5 — Lazy imports in `domain_tools.py` — SKIPPED (premise stale) ✅

The Sprint 4 prompt called out 17 heavy top-level imports in
`domain_tools.py` (PIL, bs4, fitz, pdfplumber, pdf2image, pypdf,
matplotlib, pandas, openpyxl, paho, mysql, psycopg, psycopg2, pymysql,
docx, pptx) and asked them to be moved inside their consuming
functions for lazy loading.

```
$ grep -nE '^(import|from)\s+(PIL|bs4|fitz|pdfplumber|pdf2image|pypdf|matplotlib|pandas|openpyxl|paho|mysql|psycopg|pymysql|docx|pptx)' gemma4_agent/domain_tools.py
<no output>
```

Top-level is already clean — those packages are imported inside the
specific tool functions that use them (the lazy pattern the prompt
described). The `audit §1.4 CRITICAL` premise no longer applies.

Cold-import timing baseline:
```
python -c "import subprocess, time; t=time.time(); \
  subprocess.run(['python','-c','import gemma4_agent.tools']); \
  print(f'{time.time()-t:.3f}s')"
→ 0.152 s (before AND after Sprint 4 changes — both well below the
   "several seconds" the prompt expected to fix)
```

Nothing to do.

## 4.6 — Final verifications

```
$ python -c "from gemma4_agent.tools import COMPOUND_TOOL_SCHEMAS; print(len(COMPOUND_TOOL_SCHEMAS))"
65

$ python -m gemma4_agent.launcher status   # excerpt
server             online      http://127.0.0.1:8080
mode               auto
safety             False

$ python -m pytest test_tool_dispatch_contract.py test_session847_fixes.py \
                   test_log_audit_fixes.py test_inherit_tools_safety.py -q
69 passed, 3 subtests passed in 4.69s

$ # cold-start import time
0.152 s
```

## Recap

| Commit | Subject | Δ |
|---|---|---|
| 857d24a | unify `_redact_*` | +57 / −43 |
| 92aa99a | unify dual `_hard_gate` | +91 / −73 |
| 86c9c0a | extract `_TurnRequest` / `fmt_tool_args` | +37 / −36 |
| 1d3c9ff | remove `TimelineWriter` | +11 / −206 |
| **Total** | | **+191 / −353 → −162 LOC** |

## Deferred to Sprint 5

1. **Full `AgentSerialWorker` extraction** — collapse AgentRunner +
   AgentWorker + ServerBootWorker. Needs tests-first to handle the
   reporter-channel divergence safely.
2. **`TraceLogger` removal + sink collapse to 2** — needs coordinated
   migration of ~50+ call sites in `agent.py`, an extension to
   `LogRecorder` to handle the chat.py CLI path, and an update to
   `scripts/analyze_traces.py`.
3. **`mission_goal._VERB_KIND_PATTERNS` ES+EN trim** — already noted
   in `_sprint3a_log.md`, still pending behind the no-touch wall.

All three are in the natural Sprint 5 scope (god-class refactor with
tests-first).
