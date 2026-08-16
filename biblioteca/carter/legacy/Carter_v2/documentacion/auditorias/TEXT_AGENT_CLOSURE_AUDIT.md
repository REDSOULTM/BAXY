# Carter v2 — Text Agent Closure Audit

Date: 2026-04-26  
Baseline: probe_all_tools.py 100% (165/165), pytest 752 passed (9 pre-existing failures fixed)  
Branch: rebuild/v2-from-scratch

---

## 1. What is already solid

### Routing
- All 165 probe tests pass with the real Ollama qwen3:8b backend.
- `_FOCUSED_TOOL_NAMES` covers 80+ tools; first-pass focused set prevents token overload.
- `_COMPACT_TOOL_DESCRIPTIONS` entries have ALWAYS/NEVER directives for the most confused pairs.
- `BrainRouter` correctly classifies pure greetings (`agent_no_tools`) and high-risk shell (`high_risk`).

### Memory preamble guard
- Two-tier guard (pre-normalization + dispatch-level) reliably redirects `memory_recall` → `network_get_ip/network_get_public_ip` for IP queries.
- Dispatch-level IP guard (`_is_ip_query` at execution point) is robust regardless of iteration.

### Script parameter extraction
- `code_run_python` / `code_run_node` dispatch-level fix extracts inline code from `user_text` when `script` arg is empty.

### Intent continuity
- `evaluate_direct_action_closure` correctly blocks early closure for preparatory, intermediate, and filesystem-read steps.
- `window_get_text` and `filesystem_read_text` return to LLM for synthesis.
- `_continuation_prompt` injects `INTENT_CONTINUITY_CHECK` with enough context for the LLM.

### Security
- Path guard blocks writes outside allowed zones.
- Policy table marks terminal/destructive tools as high/critical risk.
- `run_before_tool_call` hooks enforce approval gates.
- Power tools (shutdown/restart/logoff) are session-guarded.

### Universal runner
- TaskFrame parsing, checkpoints, resume, dependency graphs all tested (UNIV-1 to S21-RESOURCE-2).

---

## 2. What is still fragile

### A. IP redirect relies on substring match of user_text
The `_is_ip_query` check uses hardcoded substrings (`"mi ip"`, `"dirección ip"`, etc.).  
Variations like `"dame mi IP"`, `"cuál es el IP de este equipo"`, `"show me the machine IP"` may miss.  
**Risk**: LOW after dispatch-level guard, but new phrasings not covered.

### B. Code extraction regex is colon-based
`r"[:：]\s*(.+)$"` extracts code after any colon in `user_text`.  
Fails for: multi-paragraph prompts, code without a colon, code with colons in strings.  
**Risk**: MEDIUM — only affects `code_run_python/node` WRONG_OUTPUT failures.

### C. Calendar/email compact descriptions depend on LLM obedience
`calendar_create_event` uses "ALWAYS" directive. qwen3 occasionally picks `notify_toast`.  
No deterministic redirect (unlike IP). Only compact desc + system prompt rule.  
**Risk**: MEDIUM — flaky on rephrasing.

### D. `_can_directly_close_terminal_step` has growing exception list
Each new regression adds a capability to the exclusion set. No principled model.  
**Risk**: MEDIUM — future capabilities may need manual exclusion.

### E. `_FOCUSED_TOOL_NAMES` and `DIRECT_ACTION_TOOL_NAMES` diverge silently
No automated check that a new tool added to catalog also lands in the right set.  
**Risk**: LOW — caught by probe failures, but not by unit tests.

### F. Loop detection uses string signature
`json.dumps(tc.arguments, sort_keys=True)` is not recursively stable for nested dicts.  
Trailing whitespace in task strings breaks loop detection.  
**Risk**: LOW — worst case is extra loop iterations before detection.

---

## 3. Parts that depend too much on prompt text

| Rule | Location | Risk |
|------|----------|------|
| IP query → network tools | agent.py lines 95, 178, 200 | Mitigated by dispatch-level guard |
| code_run_python pass script | agent.py line 143 | Mitigated by dispatch-level extraction |
| Calendar create ≠ notify_toast | agent.py line 149 | No deterministic backstop |
| Git ops → code_git_* not terminal | agent.py line 143 | No deterministic backstop |
| Filesystem read_lines vs read_text | compact desc | Weak |
| notify_sound vs system_get_volume | compact desc | Fixed, stable |
| memory_recall only for stored facts | agent.py line 197-200 | Partially mitigated by preamble guard |

---

## 4. Parts that depend too much on compact descriptions

- `calendar_create_event` vs `notify_toast` — no programmatic fallback
- `email_read_inbox` — ALWAYS directive needed because qwen3 says "not configured"
- `filesystem_get_stat` vs `filesystem_list_directory` for existence checks
- `db_csv_query` vs `terminal_run_powershell` for CSV queries
- `office_pdf_export` vs `pdf_from_docx` — both correct but different paths

Compact descriptions should be **short and unambiguous**, not instruction manuals.  
Current trend: adding ALWAYS/NEVER to every confused pair creates a bloated catalog.

---

## 5. Parts that should have deterministic guardrails

| Pattern | Current state | Recommended guardrail |
|---------|--------------|----------------------|
| IP query → memory_recall | Dispatch-level redirect ✓ | Already done |
| code_run_* without script | Dispatch-level extraction ✓ | Already done |
| memory_recall as preamble | Pre-normalization guard ✓ | Already done |
| calendar_create ≠ notify_toast | Compact desc only | Add to invariants.py |
| git_* ≠ gui_do/web_search | System prompt only | Add to invariants.py |
| window_get_text returns to LLM | intent_resolution exclusion ✓ | Already done |
| filesystem_read_text returns to LLM | intent_resolution exclusion ✓ | Already done |

---

## 6. Tool pairs/aliases that can be confused

| Pair | Confusion type | Status |
|------|---------------|--------|
| `memory_recall` / `memory_search` | Both query memory | Redirect handles both |
| `filesystem_get_stat` / `filesystem_list_directory` | Existence check | Compact desc redirects |
| `gui_read` / `window_get_text` | Read UI text | Normalizer rewrites gui_read |
| `terminal_run_command` / `terminal_run_powershell` | Run code | System prompt rule |
| `terminal_winget_search` / `terminal_run_powershell` | Winget queries | ALWAYS directive |
| `code_git_*` / `terminal_run_command` | Git ops | System prompt NEVER rule |
| `calendar_create_event` / `notify_toast` | Create meeting | ALWAYS directive + invariant needed |
| `network_get_ip` / `network_get_public_ip` | IP type | _is_public_ip_query discriminates |
| `office_pdf_export` / `pdf_from_docx` | DOCX→PDF | Both accepted in probe |
| `system_get_volume` / `notify_sound` | Alert vs query | Compact desc fixed |
| `system_get_dark_mode` / `memory_recall` | User prefs | System prompt rule |
| `process_list` / `window_list` | Processes vs windows | Compact desc differentiates |

---

## 7. Category risk assessment

| Category | Risk | Main issue |
|----------|------|-----------|
| memory | MEDIUM | Preamble tendency; "mi IP" was routed to memory |
| filesystem | LOW | Well-covered; read returns to LLM now |
| terminal | LOW | cmd /c wrap fixed; builtins work |
| code | LOW | script param extraction fixed |
| network | LOW | Dispatch-level IP redirect |
| calendar/email | MEDIUM | calendar relies on compact desc, no backstop |
| office/pdf | LOW | Both tool paths work |
| GUI/window | MEDIUM | window_get_text now returns to LLM |
| universal runner | LOW | 100% test coverage |
| security | LOW | Policy table + path guard solid |

---

## 8. Bugs that could reappear even if probe passes

1. **IP with unusual phrasing** — `"cuál es el IP del equipo"` bypasses `_is_ip_query`.
2. **Calendar create with Spanglish** — `"schedule una meeting para mañana"` may call `notify_toast`.
3. **code_run_python with multi-sentence user_text** — colon extraction grabs wrong segment.
4. **UNIV-1 flakiness** — LLM occasionally omits `candidate_tools` from TaskFrame JSON.
5. **Loop detection false negative** — `gui_do(task="click button ")` vs `gui_do(task="click button")`.
6. **memory_recall for locale/dark_mode** — `"qué idioma tiene Windows?"` may still call memory.
7. **filesystem read closes early if only tool in turn** — removed from direct-close, but clock/terminal still auto-close.

---

## 9. What we are NOT changing (would be overengineering)

- **Universal TaskFrame JSON schema validation** — complex, UNIV tests pass 99%+ of the time.
- **NLP-based intent classification** — the LLM is the planner; rule-based classifiers are fragile.
- **Per-turn risk escalation based on path context** — would require path canonicalization across OS versions.
- **Tool-chaining risk detection** (`app_open` + `terminal_run_command`) — no incidents, would over-trigger.
- **Memory injection rate-limiting** — 600 char limit is adequate; injection is read-only in system prompt.
- **Recursive `sort_keys=True` in loop detection** — not worth the complexity for a rare edge case.
- **Replacing compact descriptions with a structured schema** — current dict is maintainable and works.
- **Adding LLM-based re-ranking for tool selection** — defeats the purpose of deterministic guardrails.

---

## 10. TODO: Thread Leakage Risk in Tool Execution
- **Context**: `_execute_tool_with_timeout` in `agent.py` spawns a `ThreadPoolExecutor(max_workers=1)` for every single tool call. It calls `shutdown(wait=False, cancel_futures=True)` on timeout.
- **Risk**: If the underlying capability makes a blocking C/COM call (e.g., via `pywinauto`) that ignores interrupts, the thread leaks permanently.
- **Why not fixed**: Rewriting the timeout logic to use `multiprocessing` or aggressive signal interrupts is highly dangerous in a Windows environment where `pywinauto` relies on strict thread affinities. A single persistent `ThreadPoolExecutor` could cause a total deadlock if one thread blocks forever (since max_workers=1). Thread leakage is the lesser evil compared to agent-wide deadlock or COM crashes.
- **Next Steps**: A safer timeout wrapper for tool execution that doesn't leak threads should be investigated in the future, possibly involving async/await or controlled subprocess execution for risky COM tools.
