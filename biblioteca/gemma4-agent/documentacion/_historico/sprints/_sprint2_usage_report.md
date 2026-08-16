# Sprint 2 — Trace usage report

- **Source:** `C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\gemma4_agent\data\traces.jsonl`
- **Events parsed:** 2,000  (raw lines read: 6,993, corrupted skipped: 0)
- **Time range:** 2026-05-16T12:22:43-0400 → 2026-05-17T11:44:04-0400
- **Distinct turn_ids:** 319

## A — Tools usage

**Total tool_call events:** 40  ·  **Distinct tool names:** 7  ·  **Total tool_result events:** 39

### A.1 Tool call frequency (descending)

| tool | calls | ok | failed | needs_conf | unverif |
| --- | --- | --- | --- | --- | --- |
| media | 17 | 14 | 2 | 0 | 0 |
| steam | 8 | 8 | 0 | 0 | 0 |
| web | 7 | 7 | 0 | 0 | 0 |
| audio | 3 | 3 | 0 | 0 | 0 |
| contacts | 2 | 2 | 0 | 0 | 0 |
| whatsapp | 2 | 2 | 0 | 0 | 0 |
| gui | 1 | 1 | 0 | 0 | 0 |

### A.2 Compound tools NEVER called in this window

_58 of 65 compound tools have zero calls in this window._

- accessibility
- app
- audio_device
- backup_sync
- browser
- browser_real
- clipboard
- container
- creative_local
- data_analysis
- database
- dependency
- desktop_layout
- developer
- device_settings
- document
- download
- email
- env
- fact_check
- filesystem
- form_filler
- game_launcher
- habit_tracker
- input
- job_manager
- knowledge
- local_calendar
- local_search
- maintenance
- media_edit
- memory
- network
- notes_tasks
- notification
- office
- package
- peripheral
- photo_library
- printer_scanner
- registry
- reminder
- routine
- safety
- session
- skill_load
- smart_home
- source_manager
- state
- study
- subagent
- system
- terminal
- uia
- verify
- vision
- watcher
- window

### A.3 Overall status distribution (tool_result)

| status | count |
| --- | --- |
| ok | 37 |
| failed | 2 |

## B — Personas

**Hardcoded personas in personas.py:** default, coder, researcher, creative, planner, casual

_Source: persona_active (per-turn). Total turns in window: 319._

| persona | events | % of turns | recommendation |
| --- | --- | --- | --- |
| default | 20 | 6.3% | keep |

**Never seen in logs (0% of turns):** coder, researcher, creative, planner, casual
> All zero-usage personas qualify as 'candidate to delete in Sprint 3b'.

## C — Microagents and skills

### C.1 Microagents matched

> ⚠ No `microagent_matched` events found. The router currently
> doesn't log which microagent fired. Sprint 2.2 adds this.

### C.2 Skills loaded (via skill_load tool or skill_loaded event)

> ⚠ No skill load activity found in this window.

## D — Capability classifier (Bug 1 of the audit)

- `capability_augment` (verdict applied): **31**
- `capability_async_dispatched` (sent to background): **31**
- Marked ambiguous: **0**

### D.1 Verdict source (cache vs sync vs async result)

| source | count | share |
| --- | --- | --- |
| sync | 30 | 96.8% |
| cache | 1 | 3.2% |

**Cache hit rate:** 3.2%  (threshold for keep/kill: 20%)

### D.2 Tools most often suggested by classifier

| tool | suggestions | % of turns |
| --- | --- | --- |
| media | 30 | 9.4% |
| browser | 30 | 9.4% |
| audio_device | 1 | 0.3% |
| audio | 1 | 0.3% |

## E — Routing & fallback

- `tool_subset` events with empty subset: **52 / 174** (29.9%) → triggers semantic_router fallback
- `router_miss` (router picked a tool not in the registered set): **2**
- `phrase_trigger_fired` (continuation hints / phrase routines): **56**
- `phrase_confirm_injected` (confirmation prompt injected): **54**

### E.1 Distribution of subset sizes

| schema_count | frequency |
| --- | --- |
| 0 | 72 |
| 1 | 39 |
| 2 | 8 |
| 3 | 26 |
| 4 | 21 |
| 5 | 4 |
| 6 | 1 |
| 7 | 1 |
| 8 | 2 |

## F — Mission outcomes

| status | count | share |
| --- | --- | --- |
| UNVERIFIED | 153 | 88.4% |
| PARTIAL | 10 | 5.8% |
| COMPLETED | 9 | 5.2% |
| INTENT_NOT_FULFILLED | 1 | 0.6% |

**Statuses never observed:** BLOCKED_BY_POLICY, FAILED, NEEDS_PERMISSION, NEEDS_USER, TOOL_OK_VERIFIER_INCONCLUSIVE  → candidates to collapse in Sprint 3.

## G — Top-line findings

- **58/65 compound tools never called** (30% of subsets were empty) — review for deletion in Sprint 3.
- **Microagents are unobservable**: no match event. Sprint 2.2 adds `microagent_matched`.
- **Skills are unobservable**: no `skill_load` activity. Sprint 2.2 adds `skill_loaded`.
- Capability classifier cache hit rate: **3.2%** → CANDIDATE TO KILL per Sprint 3 threshold.
- **30% of turns** hit the `subset=[]` fallback path → semantic_router carries serious load.
- Top mission_outcome status: **UNVERIFIED** (153/173 = 88%).
