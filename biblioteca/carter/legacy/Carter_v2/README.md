# Carter v2

Local-first AI assistant focused on **deterministic execution + honest verification**.

## What is Carter

- **Agent loop:** plain text turn → intent → optional tool calls → verified reply.
- **Mission state machine:** compound requests (`step1 -> step2`) decompose into ordered steps with explicit `pending|running|complete|partial|failed|unverified` status.
- **Honest replies:** if a tool fails or its outcome cannot be verified, Carter says so — no fake `done`. Honest reply banners are language-neutral structured strings (`[unverified] tool=…`, `[blocked_by_policy] reason=…`).
- **Safety gates:** registry, env, power, taskkill, terminal commands all go through `session/policy.py`. Process close prefers `graceful_close` before force.
- **Memory:** persistent durable notes in `MEMORY.md`; FTS5 search over recent context. Explicit save only — no contamination of general knowledge.
- **GUI / vision:** lazy. Vision auto-detect is OFF by default. Observation ladder runs each tier at most once and degrades to `unverified` instead of pretending success.

## Run

```powershell
# from repo root (parent of Carter_v2/)
.\run_carter_gpu.ps1
```

GPU bootstrap script lives at the parent repo root. Inside `Carter_v2/`, the entry point is `run.py`.

## Layout

```
Carter_v2/
├─ src/carter_v2/         # runtime code
│  ├─ adapters/           # tool catalog + normalizer + UIA adapter
│  ├─ capabilities/       # deterministic capabilities (fs, process, vision, gui_agent, …)
│  ├─ interfaces/         # OFF_BY_DEFAULT channel integrations (slack/discord/telegram/http)
│  ├─ recovery/           # retry/fallback policies
│  ├─ session/            # session state, memory, policy, observer, skills
│  ├─ skills/             # built-in skill catalog (SKILL.md per vendor)
│  ├─ turn/               # agent loop, mission state, intent, ledger, perception
│  ├─ universal/          # LLM-driven planner + tool index
│  └─ verification/       # post-action verification
├─ tests/                 # rebuilt minimal suite (368 tests)
│  ├─ core/               # identity / agent fundamentals
│  ├─ safety/             # policy, allowlist, graceful close, registry, env, honesty
│  ├─ mission/            # mission state, decomposition, verification, language neutrality
│  ├─ tools/              # catalog selection, normalizer, ledger, app resolver
│  ├─ memory/             # contextual memory, FTS5, injection guard
│  ├─ gui_vision/         # observation ladder + vision lazy
│  └─ integration/        # hardcode guard + language-neutral router + no-app-hacks
├─ audit/                 # quality gates + baselines
│  ├─ hardcode_guard.py   # AST scanner: 0 critical findings on every commit
│  ├─ compound_smoke_runner.py
│  ├─ baselines/          # pre-cleanup snapshot + historical
│  ├─ results/            # latest gate JSON outputs
│  ├─ logs/               # historical run logs
│  └─ temp/               # archived runners (smoke_runner, _c3_strip, …)
├─ scripts/               # helper scripts
│  ├─ setup/              # setup_ollama_optimized.ps1
│  ├─ dev/                # _inspect_mem.py, ad-hoc utilities
│  └─ maintenance/        # (reserved)
├─ documentacion/
│  ├─ arquitectura/       # CURRENT_ARCHITECTURE.md, MODULE_CLASSIFICATION.md, vision_setup.md
│  ├─ reportes_finales/   # closure / delivery reports
│  ├─ auditorias/         # audit notes per phase
│  ├─ planes/             # work plans
│  ├─ decisiones/         # ADRs
│  └─ archive/            # historical context (DREAMS design notes, GEMINI work logs)
├─ backups/               # tests_legacy_<ts>/, probe_archive_<ts>/, file backups
├─ memory/                # runtime memory artifacts
├─ MEMORY.md              # runtime durable notes (read by session/memory.py)
├─ DREAMS.md              # runtime themes (read by session/memory.py)
├─ README.md              # this file
├─ pyproject.toml
└─ run.py
```

## Tests

```powershell
python -m pytest tests/ -q
```

Suite is rebuilt from zero (May 2026 cleanup). Old suite (1667 tests) lives in `backups/tests_legacy_20260501-020549/` for reference. New suite is **368 contract-focused tests** organized by category.

Run a single category:

```powershell
python -m pytest tests/mission -q
python -m pytest tests/safety -q
```

## Audit / gates

```powershell
python audit/hardcode_guard.py            # must report 0 critical
python audit/compound_smoke_runner.py     # E2E compound-task smoke
```

`hardcode_guard.py` is the canonical gate: any PR that re-introduces brand hardcodes, multilingual phrase lists, or non-empty vocabulary containers must consciously update its allowlist.

## Profiles / what is OFF by default

- **Vision auto-detect** (Ollama): OFF — set `CARTER_AUTO_OLLAMA_VISION=1` to enable.
- **LLM-based intent decomposition**: OFF — set `CARTER_INTENT_DECOMPOSITION_LLM=1` (consumes one extra round-trip).
- **Channel interfaces** (slack/discord/telegram/http): OFF unless explicitly imported.
- **Universal kernel preamble**: OFF — set `CARTER_UNIVERSAL_KERNEL_PROMPT=1`.

## Key default flags

| Flag | Default | Effect |
|---|---|---|
| `CARTER_MISSION_STATE` | `1` | Enable mission state machine. |
| `CARTER_INTENT_DECOMPOSITION` | `1` | Enable structural compound detection. |
| `CARTER_INTENT_DECOMPOSITION_LLM` | `0` | Use LLM for decomposition (extra cost). |
| `CARTER_AUTO_OLLAMA_VISION` | `0` | Auto-probe Ollama for vision model. |
| `CARTER_UNIVERSAL_KERNEL_PROMPT` | `0` | Enable universal kernel preamble. |

## Documentation

- Architecture: [documentacion/arquitectura/CURRENT_ARCHITECTURE.md](documentacion/arquitectura/CURRENT_ARCHITECTURE.md)
- Repo cleanup audit: [REPO_CLEANUP_AUDIT.md](REPO_CLEANUP_AUDIT.md)
- Repo cleanup report: [documentacion/reportes_finales/REPO_CLEANUP_REPORT.md](documentacion/reportes_finales/REPO_CLEANUP_REPORT.md)
- Module classification: [documentacion/arquitectura/MODULE_CLASSIFICATION.md](documentacion/arquitectura/MODULE_CLASSIFICATION.md)

## History

The legacy v1 implementation lives at `../Carter_v1/`. The v2 codebase has been through multiple stabilization phases (text-agent closure, hardcode elimination H1-H9, mission state machine M1-M9). All historical reports are in `documentacion/reportes_finales/` and `documentacion/auditorias/`.

