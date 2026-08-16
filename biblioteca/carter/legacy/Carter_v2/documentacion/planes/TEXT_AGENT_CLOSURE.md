# Carter v2 — Text Agent Closure

Date: 2026-04-26  
Branch: rebuild/v2-from-scratch  
Baseline: probe_all_tools.py 100% (165/165), pytest 761 passed

---

## Deliverables

| File | Purpose |
|------|---------|
| `TEXT_AGENT_CLOSURE_AUDIT.md` | Risk audit — solid vs fragile areas, tool pairs, guardrail gaps |
| `probe_text_hardening.py` | Adversarial probe: 9 categories, 35 tests, LLM-in-the-loop |
| `src/carter_v2/turn/invariants.py` | Deterministic guardrails: IP, calendar-create, git routing |
| `tests/test_text_agent_regressions.py` | 54 regression tests covering all historical mis-routings |
| `run_text_closure_gate.py` | CI gate: pytest + probe_all + probe_text_hardening |
| `TEXT_AGENT_CLOSURE.md` | This document |

---

## Fixes Applied

### Dispatch-level IP redirect (agent.py)
**Root cause**: qwen3:8b treats "mi IP" as a personal fact → calls `memory_recall`.  
**Fix**: Hard redirect at execution point: if `memory_recall/search/context` is called and user_text matches IP phrases, replace with `network_get_ip` or `network_get_public_ip`.  
**Invariant**: `_invariant_ip_redirect` in `invariants.py` adds a second layer.

### Calendar create → notify_toast redirect (invariants.py)
**Root cause**: qwen3 occasionally substitutes `notify_toast` for `calendar_create_event`.  
**Fix**: `_invariant_calendar_create_redirect` detects notify tools + calendar-create intent and rewrites to `calendar_create_event`.

### Git ops → GUI/web redirect (invariants.py)
**Root cause**: qwen3 occasionally uses `gui_do` or `web_search` for local git queries.  
**Fix**: `_invariant_git_redirect` detects GUI/web tools + git-intent phrases and rewrites to `code_git_status/diff/log`.

### code_run_python missing script (agent.py dispatch)
**Root cause**: qwen3 calls `code_run_python` without the `script` parameter.  
**Fix**: Dispatch-level extraction: if `script` arg is empty, extract inline code from `user_text` using `r"[:：]\s*(.+)$"`.

### NO_TOOL_NEEDED strip (agent.py)
**Root cause**: Strip was gated on `hint_no_tools=False`, so `hint_no_tools=True` path leaked the prefix into the reply.  
**Fix**: Strip runs unconditionally for any reply starting with `NO_TOOL_NEEDED:`.

### filesystem_read_text closes turn early (intent_resolution.py)
**Root cause**: `filesystem_read_text` was in the direct-close set; LLM never synthesized the content.  
**Fix**: Added `"filesystem"` to the verification-action exclusion set — returns to LLM for synthesis.

### window_get_text closes turn early (intent_resolution.py)
**Root cause**: `window_get_text` was treated as terminal step; no synthesis round.  
**Fix**: Removed from direct-close list.

### steam_run → app_open (tool_normalizer.py)
**Root cause**: `steam_run` rewrite to `app_open` was missing for non-Steam game targets.  
**Fix**: Added `steam_run` → `app_open` branch with confidence threshold 0.75.

### Greeting tokens (brain_router.py)
**Root cause**: "hi there", "gracias", short courtesies were not in `_GREETING_TOKENS`.  
**Fix**: Added `there`, `gracias`, `thanks`, `thank`, `ok`, `okay`, `sure`, `bye`, `adios`, `chao`, `chau`, `hasta`, `luego`, `pronto`.

---

## Invariants Module

`src/carter_v2/turn/invariants.py` exposes a single public API:

```python
from carter_v2.turn.invariants import apply_all

result = apply_all(tool_calls, user_text)
# result.tool_calls  — corrected list
# result.redirected  — True if any invariant fired
# result.reason      — human-readable explanation
```

Invariants run **after** LLM tool call selection and **before** normalization. They are narrow, testable, and independent of prompt text.

---

## Probe Categories (probe_text_hardening.py)

| Cat | Name | Tests |
|-----|------|-------|
| A | Conversación sin tools | 6 |
| B | Routing básico | 6 |
| C | Anti-memory-preamble | 6 |
| D | Memory real | 3 |
| E | Parámetros obligatorios | 3 |
| F | Intent continuity (git) | 3 |
| G | Honestidad y errores | 2 |
| H | Seguridad textual | 2 |
| I | Tool alias y equivalencias | 5 |

Run: `python probe_text_hardening.py`  
Gate: `python run_text_closure_gate.py`

---

## Test Coverage

```
pytest tests/                          — 761+ passed, 0 failed
pytest tests/test_text_agent_regressions.py  — 54 passed
python probe_all_tools.py              — 165/165 (100%)
```

---

## What Is Still Prompt-Dependent

See `TEXT_AGENT_CLOSURE_AUDIT.md` §3–4 for the full table. Short list:

- Calendar create vs notify_toast: invariant backstop added ✓
- Git vs gui/web: invariant backstop added ✓
- code_run_python script param: dispatch-level extraction ✓
- IP query: two-tier guard (preamble + dispatch) ✓
- Remaining: filesystem_read_lines vs read_text, system_get_dark_mode for preferences — low risk, compact desc sufficient

---

## How to Run the Full Gate

```bash
cd Carter_v2
python run_text_closure_gate.py
# For stability test (3 LLM runs of text probe):
python run_text_closure_gate.py --repeat 3
# Skip probe_all for fast iteration:
python run_text_closure_gate.py --skip-probe-all
```

Exit 0 = all gates pass. Exit 1 = closure not achieved.
