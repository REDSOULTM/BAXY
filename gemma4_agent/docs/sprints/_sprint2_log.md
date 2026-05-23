# Sprint 2 — Log (instrumentation only)

- **Started:** 2026-05-17
- **Finished:** 2026-05-17 (same session)
- **Operator:** Claude Code (Opus 4.7)
- **Base commit:** 6bd2bde `docs(sprint_prompts): add Sprint 2 prompt …`
- **Final commit:** 8a2ef09 `sprint2: log persona_active via TraceLogger`
- **Net delta vs base:** 3 files changed, **+684 LOC, 0 deletions**
  (pure-add sprint, as the prompt required)

## Sprint 2.1 — analyze_traces.py + first usage report — commit 079574e ✅

Built `scripts/analyze_traces.py` (stdlib only: argparse / json /
collections / pathlib / dataclasses-free). Reads
`gemma4_agent/data/traces.jsonl` and emits a Markdown report to stdout
**and** to `docs/architecture/sprint_prompts/_sprint2_usage_report.md`.

Flags:
- `--limit N` — only the last N raw lines.
- `--since YYYY-MM-DD` — events on/after this date.
- `--traces path` — alternate JSONL path.
- `--report-path path` — alternate output path (default goes next to
  this log, so weekly re-runs overwrite cleanly).

Handles corrupted lines (counts and skips), prints absolute source
path to stderr, and reconfigures stdout/stderr to UTF-8 so the
`→` arrow we use in the report doesn't blow up Windows `cp1252` consoles.

Section layout matches the prompt spec (A=tools, B=personas,
C=microagents+skills, D=capability classifier, E=routing/fallback,
F=MissionOutcome, G=top-line findings).

### First-run headline (5 days of use, 6727 events)

- **45/65 compound tools never called** in the window → strong
  candidates for Sprint 3 deletion.
- **5/6 personas never used.** Only `default` ever runs (602 of 602
  `tool_subset` events with a persona tag). `coder/researcher/creative/
  planner/casual` show 0.
- **Capability classifier cache hit rate: 3.2%.** Below the 20%
  keep/kill threshold. The sync path carries ~97% of verdicts.
- **45% of turns hit the empty-subset fallback path** (`subset=[]` →
  semantic_router). That's load-bearing infrastructure, not an edge.
- **88% of mission_outcomes are UNVERIFIED.** Four of nine statuses
  (`BLOCKED_BY_POLICY`, `FAILED`, `NEEDS_PERMISSION`, `NEEDS_USER`)
  never appeared → candidates to collapse.
- 0 `microagent_matched` and 0 `skill_loaded` events: the systems run
  but are silent in the log. Sprint 2.2 fixes this.

## Sprint 2.2 — TraceLogger instrumentation

Three commits — one per missing event kind. No production behaviour
changed; every emission is wrapped in try/except so a logger fault
cannot break a turn.

### 1.2.a microagent_matched — commit 6062cd8 ✅

In `agent.run_content()`, immediately after `raw_text_early` is
extracted, call `select_microagents(raw_text_early, load_microagents())`
and emit one event with `names=[…]` and `count` if anything matched.
Independent of the cache-merge inside `_system_message`, which mixes
fresh matches with cached carry-over and obscures per-turn freshness.

### 1.2.b skill_loaded — commit 877736a ✅

In the tool-result loop in `run_content` (next to the existing
`tool_result` event), when `name == "skill_load"` and the call
succeeded, emit `skill_loaded` with the resolved `name` and `chars`.

### 1.2.c persona_active — commit 8a2ef09 ✅

In `run_content()` right after `turn_id` is created, emit
`persona_active` with `persona` and `tone`. Previously personas were
visible only through the optional `tool_subset.persona` field, which
is missing on turns that don't reach the subset step.

Also updated `analyze_traces.py` Section B: prefer `persona_active`
counts when present, fall back to `tool_subset.persona` otherwise,
and label the source in the report.

### Capability classifier — NOT instrumented (already complete) ⏭

The prompt listed this as a candidate, but `capability_augment` and
`capability_async_dispatched` already carry `source`, `confidence`,
`added`, and `ambiguous` (see `agent.py:1222-1234`). Adding a
duplicate `capability_verdict` event would just confuse downstream
consumers. The analyzer's Section D already produces the verdict
distribution and cache hit rate from what exists. Nothing to add.

## Sprint 2.3 — Weekly re-run instructions

Run weekly after normal use:

```pwsh
python scripts/analyze_traces.py --since 2026-05-17
```

(Or omit `--since` for the full history; the file truncates by the
agent's own retention so it stays cheap to scan.)

By default the report is written to
`docs/architecture/sprint_prompts/_sprint2_usage_report.md`. Pass
`--report-path /tmp/report.md` to compare snapshots without
overwriting the canonical copy.

### When to re-run

- **Always before launching Sprint 3.** The Sprint 3 prompt will cite
  this file's findings verbatim.
- **After any change** that touches `personas.py`, `microagents/*.md`,
  `skills/*/`, or the compound tool catalogue in `tools.py`.
- **After a week of unusual usage** (heavy research session, new
  domain, etc.) — the per-tool tail may shift.

### What to look for in each section

| Section | Signal | Action |
| --- | --- | --- |
| A.2 (unused tools) | `count == 0` for 7+ days under active use | Delete in Sprint 3 |
| B (personas) | Persona with 0 turns | Collapse into default or delete |
| C.1 / C.2 | Microagent or skill with 0 matches/loads | Delete the file |
| D.1 cache rate | < 20% sustained | Eliminate classifier per audit Bug 1 |
| F (mission outcomes) | Status never observed | Collapse in Sprint 3 |

## Sprint 2.4 — Final state

`python -c "import gemma4_agent"` ✓ after each commit.

### Recommended observation window before Sprint 3

The trace currently spans **5 days / 6727 events / 751 turns** (12-16
May). That's enough volume to be statistically meaningful for the
tools-tail decisions (45 zero-call tools out of 65 is a strong signal
even at this size), but the persona/microagent/skill instrumentation
just landed and has zero new events yet.

Suggested wait: **7-10 more days of normal use** so the three new
event kinds accumulate at least 500-1000 turns each before the next
re-run. Decision factors:

- Persona signal: 5/6 personas at 0 is already a strong negative
  result; another week likely confirms this rather than discovers a
  surprise.
- Microagent / skill signal: zero observations so far are
  instrumentation gaps, not real zeros. Need real data after this
  commit.
- Tool tail: most stable signal, but a week of heavier domain work
  (e.g. an actual coding session) could move 5-10 names from the
  unused list.

If the heavy push to use `coder`/`researcher` personas this week is
deliberate, that bias gets baked in — keep an eye on the agent's mode
selector during the window.

### Findings worth surfacing in the Sprint 3 prompt

1. **Top deletion candidates by tool**: from A.2, the 45 zero-call
   tools. Cross-reference with COMPOUND_TOOL_SCHEMAS at re-run time to
   exclude any introduced after 2026-05-16.
2. **Persona consolidation**: collapse to one persona (default) unless
   the upcoming window flips this.
3. **Capability classifier removal**: 3.2% cache hit rate puts this
   firmly in "kill" territory per the audit's own threshold.
4. **Mission outcome simplification**: 4/9 statuses unused.
5. **semantic_router prominence**: 45% of turns go through it.
   Whatever Sprint 3 does to routing must keep that path fast/correct.

## Recap of commits

```
079574e sprint2: add scripts/analyze_traces.py + first usage report
6062cd8 sprint2: log microagent_matched via TraceLogger
877736a sprint2: log skill_loaded via TraceLogger
8a2ef09 sprint2: log persona_active via TraceLogger
```

## State

```
$ git log --oneline -6
8a2ef09 sprint2: log persona_active via TraceLogger
877736a sprint2: log skill_loaded via TraceLogger
6062cd8 sprint2: log microagent_matched via TraceLogger
079574e sprint2: add scripts/analyze_traces.py + first usage report
6bd2bde docs(sprint_prompts): add Sprint 2 prompt (instrumentation only)
0ccebdd chore: gather external docs + gitignore trace dumps

$ git status
On branch PortandoLoMejor
nothing to commit, working tree clean
```
