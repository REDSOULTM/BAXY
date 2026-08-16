# Current Architecture — Carter v2

Source of truth (May 2026) for the runtime architecture of Carter v2 after the radical repo cleanup.

## High level

```
user text
   │
   ▼
┌──────────────────────────────────────────────────────────────┐
│ AgentEngine (turn/agent.py)                                  │
│                                                              │
│  1. perception snapshot  ───►  session/observer.py           │
│  2. mission decomposition ──►  turn/mission.py               │
│  3. tool catalog selection ─►  turn/tool_catalog_selection   │
│  4. backend round-trip ─────►  turn/llama_backend.py /       │
│                                turn/backends.py              │
│  5. tool execution + verification:                           │
│     • adapters/tools.py  → capabilities/*                    │
│     • verification/contracts + facts                         │
│     • turn/mission_verification.py                           │
│  6. honest reply assembly ──►  turn/ledger.py                │
└──────────────────────────────────────────────────────────────┘
   │
   ▼
draft reply  →  format_mission_reply  →  user
```

## Module map (active)

| Layer | Modules | Purpose |
|---|---|---|
| **Bootstrap** | `main.py`, `__main__.py`, `config.py`, `event_bus.py`, `types.py` | Entry, config loader, observer bus, type defs |
| **Adapters** | `adapters/tools.py`, `adapters/tool_normalizer.py`, `adapters/uia.py` | Unified tool catalog, schema/arg normalization, Windows UIA bridge |
| **Capabilities** | `capabilities/{filesystem, process, system, window, gui_agent, app_resolver, _gui_planner, vision_router, …}` | Deterministic capability implementations |
| **Recovery** | `recovery/{classifier, policies, types}` | Retry/fallback decisions per failure class |
| **Session** | `session/{state, memory, policy, observer, skills, proactive, …}` | Per-session state, durable notes, policy gate, observer hooks, skills loader |
| **Skills** | `skills/<vendor>/SKILL.md` (10 built-in vendors) | Static skill catalog auto-loaded by `session/skills.py` |
| **Tasks** | `tasks/background.py` | Async/background tasks (lazy) |
| **Turn loop** | `turn/{agent, mission, mission_observation, mission_verification, ledger, invariants, perception, _system_prompt, llama_backend, backends, _text, _tracing, intent_*, tool_catalog_selection}` | The whole agent loop pipeline |
| **Universal** | `universal/{tool_index, planner, …}` | LLM-driven planner / metadata kernel |
| **Verification** | `verification/{contracts, facts}` | Fact library + post-action verification contracts |
| **Interfaces (OFF_BY_DEFAULT)** | `interfaces/{slack, discord, telegram, http, extension_relay}` | External channel integrations — lazy load |
| **Plugins** | `plugins/loader.py` | Local plugin discovery hook |

## AgentEngine flow

`turn/agent.py` is the orchestrator. Each turn:

1. **Perception snapshot** — `session/observer.py` captures process list + active window. Cheap.
2. **Mission decomposition** — `turn/mission.py.decompose_intent`:
   - Structural-only `looks_compound` (pipeline glyphs `-> => → |>`, semicolons, multi-sentence terminators, comma lists ≥ 4 tokens). **No connective word lists, no language-specific dictionaries.**
   - If `CARTER_INTENT_DECOMPOSITION_LLM=1`, ask `TaskFrameBuilder` for strict TaskFrame JSON. Otherwise structural split.
   - Single-step / trivial requests skip mission entirely.
3. **Tool catalog selection** — `turn/tool_catalog_selection.py`:
   - Per-step catalog: capability hint + peers (e.g. `app_open` step exposes `app_close` as peer).
   - Pinned tools always included.
4. **Backend call** — `turn/llama_backend.py` (default Ollama) wraps `chat_with_tools`. Backend-agnostic; scripted backend used for tests.
5. **Tool execution** — `adapters/tools.py` resolves the tool name and dispatches to a `capabilities/` implementation. Honest exit codes are propagated.
6. **Verification** — `verification/contracts.py` + `turn/mission_verification.py`:
   - App/process/window verification using perception snapshot diffs.
   - `expected_process_dead`, `expected_process_alive`, etc. are **structural verification hints** — not language strings.
   - Failure to verify demotes step → `unverified`, never silently `success`.
7. **Honest reply** — `turn/ledger.py` produces language-neutral banners:
   - `[unverified] tool=… verification=pending detail=…`
   - `[action_failed] tools=… details=…`
   - `[blocked_by_policy] tool=… reason=…`
   - `[no_action_executed]`, `[unverified_action]`
   `format_mission_reply` (in `mission_verification`) emits English-only structured banners (`Done:` / `Unverified:` / `Failed:` / `Pending:`); the LLM draft reply is preserved on `COMPLETE` so user-language carry works.

## Mission state machine

`turn/mission.py`:

```
MissionStatus  =  PENDING | RUNNING | COMPLETE | PARTIAL | FAILED | NEEDS_USER | TRIVIAL
StepStatus     =  PENDING | RUNNING | SUCCESS | FAILED | SKIPPED | UNVERIFIED
```

Transitions:
- `Mission.first_pending()` advances the cursor.
- `Mission.advance()` after a successful step.
- `Mission.settle_status()` collapses step states into final mission status.
- A mission is `COMPLETE` only if **all** steps succeeded; `PARTIAL` if any pending or unverified, `FAILED` if any critical failure.

## Observation ladder (GUI / vision)

`turn/perception.py` + `session/observer.py`:

1. **process / window tier** — always available, very cheap.
2. **UIA tier** — Windows UI Automation; lazy.
3. **Playwright / web tier** — lazy.
4. **OCR tier** — currently unavailable by design.
5. **LLM vision tier** — OFF by default (`CARTER_AUTO_OLLAMA_VISION=0`).

Each tier runs **at most once per turn**. If no tier produces evidence, the step degrades to `unverified` — never fake `success`.

## Memory

`session/memory.py`:
- `MEMORY.md` — durable notes, top priority recall (line 325 `_memory_md = _base_dir / "MEMORY.md"`).
- `DREAMS.md` — recurring themes / consolidation output (line 326).
- FTS5 over recent turn snippets, with input sanitization (`memory/fts5` test ensures sanitization).
- Explicit save only: general knowledge / probes / errors are **not** auto-saved.
- Memory promotion every 5 turns (auto, mid-session) keeps `MEMORY.md` current.

## Safety

- `session/policy.py` — central enforce_policy gate. Returns block reasons as `[blocked_by_policy] tool=… risk=… reason=…`.
- Critical actions (registry write, env persist, power, taskkill, delete) require explicit user confirmation or a callback policy.
- Process close: `graceful_close` is preferred before force; the verifier knows about graceful semantics.
- Terminal commands gated by allowlist.

## Hard-code policy

`audit/hardcode_guard.py` is the canonical gate:
- AST-aware scanner.
- Three regex families: brand strings (steam/spotify/discord/notepad/opera GX/calculadora/bloc de notas/<browser>.exe), multilingual literals (`y luego`, `and then`, `que hora es`, `abre+brand`, …), vocabulary containers (`*_TOKENS`, `*_PHRASES`, `*_VERBS`, `*_ALIASES`, `*_CONNECTORS`, `*_MARKERS`).
- 0 critical findings on every commit. Allowlist for ~22 technically correct files (Windows install paths, ProgIDs, security binary list).

## Out of scope (current)

- Voice input / output.
- Camera / multimodal real-time.
- Cloud agent fallback.
- Mobile / non-Windows hosts.

These remain documented in `documentacion/archive/DREAMS.md` (root copy is runtime state, not a doc) for future consideration but no production code targets them.

## Test surface

The rebuilt suite (368 tests, May 2026) is organized by **contract**, not by **implementation**:

| Folder | What it protects |
|---|---|
| `tests/core/` | Identity (multilang neutral) |
| `tests/safety/` | Policy enforcement, allowlist, graceful close, registry/env, honesty guardrail |
| `tests/mission/` | State machine, decomposition, observation, verification, language neutrality |
| `tests/tools/` | Catalog selection, normalizer, ledger, app resolver |
| `tests/memory/` | Contextual recall, FTS5 sanitization, injection guard |
| `tests/gui_vision/` | Vision lazy load, perception feedback |
| `tests/integration/` | Hardcode guard, router language neutrality, no-app-hacks |

Old phase-specific tests (`fase15-18`, `session9_extended_capabilities`, `openclaw_parity`, `jarvis_root_hardening`, `text_agent_regressions` 1786-line monolith) were intentionally **not** salvaged — their contracts are either covered by the new categorical tests or were tied to closed phases.
