# Carter v3 — CHANGELOG

## Current state (2026-05-06)

**490 tests pass** (ScriptedAdapter, no real LLM).
**Status: `TESTS_PASS_BUT_RUNTIME_WEAK`** — see [BLOCKERS.md](BLOCKERS.md) for active blockers.

Active blockers before voice/camera: B1 (git integrity), B2 ("Sí"/"OK" confirmation), B3 (fake_success mid-text), B4 (notify_toast verifier), B5 (no progress reporting), B6 (system prompt execution trigger).

Full audit in [docs/audit/CLAUDE_CARTER_V3_AUDIT_VERDICT.md](docs/audit/CLAUDE_CARTER_V3_AUDIT_VERDICT.md).

---

## Key milestones

| Date | Milestone |
|------|-----------|
| 2026-04-16 | Carter v3 FASE 0 design decisions D1–D10 closed |
| 2026-04-16 | Carter v2 code imported into v3 structure (15 rounds) |
| 2026-04-28 | hardcode_guard AST scanner clean (58 files) |
| 2026-04-28 | PolicyEngine 20+ security patterns active |
| 2026-04-30 | MemoryStore SQLite with secret filter + dedup |
| 2026-05-01 | LocalReminderStore SQLite implemented |
| 2026-05-01 | 490 tests passing (ScriptedAdapter) |
| 2026-05-03 | Tag `carter-v3-18x30-true-ready` (working tree has +202 lines uncommitted — B1) |
| 2026-05-06 | Claude Code full audit — TESTS_PASS_BUT_RUNTIME_WEAK verdict |
| 2026-05-06 | Repository reorganized (docs/history, docs/audit, removed audit/runs) |

---

## FASE 0 design decisions

Full D1–D10 decision log archived at [docs/history/CHANGELOG_FASE0.md](docs/history/CHANGELOG_FASE0.md).

Summary:
- **D1** — `mission_status` computed structurally from verifier, not from LLM text
- **D2** — VerificationManager: per-tool readback before any reply
- **D3** — IntentClassifier: zero keyword lists, purely structural
- **D4** — SessionState: per-turn ephemeral with TTL decay
- **D5** — Action-route fallback: `synthesise_action_tool_call()` if LLM skips tool call
- **D6** — PolicyEngine pre-LLM with _DANGEROUS_PATTERNS + _EXFIL_PATTERNS
- **D7** — 32-tool hard cap enforced at module level
- **D8** — OllamaAdapter with `keep_alive=10m`, preload before first turn
- **D9** — LocalReminderStore SQLite (NOT OS notifications)
- **D10** — fake_success_guard: blocks listo/hecho/done without verifier confirmation
