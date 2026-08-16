# Carter v3 — RESIDUAL

Current open items that are NOT bugs but are known gaps to resolve before FASE 1+ work.

For the active **bugs/blockers**, see [BLOCKERS.md](BLOCKERS.md).
For the full FASE 0 backlog (R-V2-*, R-V3-*, I-* items), see [docs/history/RESIDUAL_FASE0.md](docs/history/RESIDUAL_FASE0.md).

---

## Open after 2026-05-06 audit

### R1 — Live validation of app_open/close with real LLM

CI uses ScriptedAdapter — real Ollama never called. `app_open`, `app_close`, `web_open_url` have zero live verification.

**What's needed:** Manual spotcheck of [docs/audit/CLAUDE_MANUAL_SPOTCHECK_SET.md](docs/audit/CLAUDE_MANUAL_SPOTCHECK_SET.md) 21 prompts with Ollama running.

### R2 — Latency measurement under real LLM

C15 (latency ≤ 8s) only validated in scripted mode. Real Ollama cold-start can exceed 8s.

**What's needed:** 3 consecutive live runs of case 1 (`a`) measuring first-token time.

### R3 — LocalReminderStore: missing natural language dates

`parse_due_at()` handles ISO, relative offsets ("in 5 minutes"), HH:MM. Missing: "pasado mañana", weekday names ("el lunes"), "esta tarde/noche".

**What's needed:** Extend `parse_due_at()` with weekday + time-of-day parsing.

### R4 — notify_toast has no real visual verification

`notify_toast` uses `verifier="synchronous_ok"` — marks CONFIRMED if `result.ok=True` without checking the toast actually appeared on screen.

**What's needed:** Either accept this limitation explicitly, or add screenshot-diff verification (complex — may remain as-is).

### R5 — Working tree not committed (B1 is now a RESIDUAL after commit)

After fixing B1 (committing current working tree), this becomes residual: the tag `carter-v3-18x30-true-ready` will need to be updated or superseded with a new tag that matches the actual code.

---

## Items deferred from FASE 0 (still open)

From [docs/history/RESIDUAL_FASE0.md](docs/history/RESIDUAL_FASE0.md):

| ID | Summary | Phase |
|----|---------|-------|
| R-V2-B1 | Action-route fallback for cases 7/8 (already implemented as `synthesise_action_tool_call`) | DONE in code, needs live evidence |
| R-V2-B2 | Declarative-fact detector for memory offers | FASE 2 |
| R-V2-B3 | Cold-start latency with Ollama | FASE 1 / launcher |
| R-V2-B4 | `que?` and ambiguous mono-token handling | FASE 1 |
