# Carter v3

Local Windows AI assistant. Text-core-first. No predefined tools — generates raw code via LLM. Runs on local models via Ollama.

**Status:** `TESTS_PASS_BUT_RUNTIME_WEAK` — 490 CI tests pass, 6 runtime blockers before voice/camera. See [BLOCKERS.md](BLOCKERS.md).

---

## Structure

```
Carter_v3/
├── src/carter_v3/          # Core source
│   ├── agent.py            # AgentEngine — main turn loop
│   ├── guards.py           # Post-LLM response guards
│   ├── response_composer.py
│   ├── session_state.py    # Per-turn ephemeral state (TTL decay)
│   ├── turn_support.py     # LLM message building
│   ├── resolvers/
│   │   └── intent_classifier.py   # Structural only, zero keyword lists
│   ├── security/
│   │   └── policy.py       # Pre-LLM PolicyEngine (20+ patterns)
│   └── tools/
│       ├── catalog.py      # 32-tool declarative catalog (hard cap)
│       ├── verifier.py     # VerificationManager — per-tool readback
│       └── local_reminders.py   # SQLite reminder store
├── tests/                  # 490 pytest tests (ScriptedAdapter)
├── audit/                  # hardcode_guard.py, official_matrix_cases.py, full_matrix_runner.py
├── docs/
│   ├── audit/              # Claude Code 2026-05-06 audit (7 docs + Codex prompt)
│   └── history/            # Historical docs (FASE 0 design, import logs, cycle reports)
├── configs/
├── data/
├── BLOCKERS.md             # 6 active blockers
├── CHANGELOG.md            # Milestones + FASE 0 decision summary
└── RESIDUAL.md             # Open gaps (non-bug)
```

---

## Running

```powershell
# Install
pip install -e ".[dev]"

# Run Carter
.\run_carter_v3.ps1

# Tests
python -m pytest --tb=short -q
```

---

## Testing

**CI tests (490):** Use `ScriptedAdapter` — no real LLM, fast, deterministic.

**Matrix runner:**
```bash
# Dry-run (no side effects, scripted)
python audit/full_matrix_runner.py --mode dry-run

# Live-safe-all (real LLM, all side-effect tools blocked)
python audit/full_matrix_runner.py --mode live-safe-all

# Live (real LLM, real actions — use carefully)
python audit/full_matrix_runner.py --mode live
```

Note: `live-safe-all` blocks `app_open`, `app_close`, `web_open_url`, etc. Cases C07/C08/C10/C11/C13 pass because Carter correctly says it didn't execute — not because it actually did.

**Manual spotcheck:** See [docs/audit/CLAUDE_MANUAL_SPOTCHECK_SET.md](docs/audit/CLAUDE_MANUAL_SPOTCHECK_SET.md) (21 prompts with expected behavior and FAIL criteria).

---

## Audit (2026-05-06)

Full audit docs in [docs/audit/](docs/audit/):

| Doc | Contents |
|-----|----------|
| `CLAUDE_CARTER_V3_AUDIT_VERDICT.md` | Global verdict, ~75-80% complete |
| `CLAUDE_RUNTIME_CODE_AUDIT.md` | 20 specific findings with line refs |
| `CLAUDE_18X30_MATRIX_AUDIT.md` | Why 540/540 is not full evidence |
| `CLAUDE_CATEGORY_CAPABILITY_AUDIT.md` | 18 categories: READY/PARTIAL/WEAK/BLOCKER |
| `CLAUDE_CONTEXT_CARTER_REQUIREMENTS.md` | 30 values vs code state |
| `CLAUDE_MANUAL_SPOTCHECK_SET.md` | 21 manual test prompts |
| `CLAUDE_AUDIT_BASELINE.md` | Git state at audit time |
| `PROMPT_FOR_CHATGPT_CODEX_TO_FINISH_CARTER_V3.md` | Complete Codex prompt with all context |

---

## Architecture overview

- **AgentEngine** (`agent.py`) — `step_budget=6`, runs: policy → intent → resolver → LLM → tool dispatch → verify → guards → compose
- **IntentClassifier** — Zero keyword lists. Kinds: `trivial_lowinfo`, `ambiguous_short`, `compound_action`, `question`, `potential_action`
- **PolicyEngine** — Pre-LLM security, 20+ regex patterns, blocks before LLM sees input
- **VerificationManager** — Post-action readback for every tool (process check, volume ±5%, file hash, etc.)
- **fake_success_guard** — Blocks "listo/done/hecho" claims if verifier hasn't confirmed
- **SessionState** — `pending_intent`, `pending_memory_offer`, `pending_tool_approval`, `observed_target` — all with TTL decay
- **MemoryStore** — SQLite with secret filter and dedup window
- **LocalReminderStore** — SQLite reminders (NOT OS notifications)
- **hardcode_guard** — AST scanner; 58 files clean, zero brand/semantic keyword lists in runtime
