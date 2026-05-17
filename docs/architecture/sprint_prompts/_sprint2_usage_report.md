# Sprint 2 — Trace usage report

- **Source:** `C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\gemma4_agent\data\traces.jsonl`
- **Events parsed:** 6,727  (raw lines read: 6,727, corrupted skipped: 0)
- **Time range:** 2026-05-12T03:35:54-0400 → 2026-05-16T21:29:51-0400
- **Distinct turn_ids:** 1,153

## A — Tools usage

**Total tool_call events:** 186  ·  **Distinct tool names:** 20  ·  **Total tool_result events:** 185

### A.1 Tool call frequency (descending)

| tool | calls | ok | failed | needs_conf | unverif |
| --- | --- | --- | --- | --- | --- |
| steam | 43 | 43 | 0 | 0 | 0 |
| media | 36 | 27 | 8 | 0 | 0 |
| app | 26 | 18 | 8 | 0 | 0 |
| audio | 22 | 21 | 1 | 0 | 0 |
| browser | 16 | 15 | 1 | 0 | 0 |
| web | 8 | 8 | 0 | 0 | 0 |
| filesystem | 6 | 4 | 2 | 0 | 0 |
| whatsapp | 5 | 5 | 0 | 0 | 0 |
| verify | 4 | 4 | 0 | 0 | 0 |
| gui | 3 | 3 | 0 | 0 | 0 |
| window | 3 | 3 | 0 | 0 | 0 |
| contacts | 3 | 3 | 0 | 0 | 0 |
| state | 2 | 2 | 0 | 0 | 0 |
| notes_tasks | 2 | 2 | 0 | 0 | 0 |
| audio_device | 2 | 1 | 1 | 0 | 0 |
| download | 1 | 0 | 1 | 0 | 0 |
| routine | 1 | 1 | 0 | 0 | 0 |
| dependency | 1 | 1 | 0 | 0 | 0 |
| desktop_layout | 1 | 1 | 0 | 0 | 0 |
| email | 1 | 0 | 1 | 0 | 0 |

### A.2 Compound tools NEVER called in this window

_45 of 65 compound tools have zero calls in this window._

- accessibility
- backup_sync
- browser_real
- clipboard
- container
- creative_local
- data_analysis
- database
- developer
- device_settings
- document
- env
- fact_check
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
- notification
- office
- package
- peripheral
- photo_library
- printer_scanner
- registry
- reminder
- safety
- session
- skill_load
- smart_home
- source_manager
- study
- subagent
- system
- terminal
- uia
- vision
- watcher

### A.3 Overall status distribution (tool_result)

| status | count |
| --- | --- |
| ok | 162 |
| failed | 23 |

## B — Personas

**Hardcoded personas in personas.py:** default, coder, researcher, creative, planner, casual

| persona | events |
| --- | --- |
| default | 602 |

**Never seen in logs:** coder, researcher, creative, planner, casual

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

| tool | suggestions |
| --- | --- |
| media | 30 |
| browser | 30 |
| audio_device | 1 |
| audio | 1 |

## E — Routing & fallback

- `tool_subset` events with empty subset: **311 / 690** (45.1%) → triggers semantic_router fallback
- `router_miss` (router picked a tool not in the registered set): **1**
- `phrase_trigger_fired` (continuation hints / phrase routines): **192**
- `phrase_confirm_injected` (confirmation prompt injected): **180**

### E.1 Distribution of subset sizes

| schema_count | frequency |
| --- | --- |
| 0 | 326 |
| 1 | 170 |
| 2 | 16 |
| 3 | 89 |
| 4 | 65 |
| 5 | 9 |
| 6 | 7 |
| 7 | 3 |
| 9 | 2 |
| 13 | 2 |
| 16 | 1 |

## F — Mission outcomes

| status | count | share |
| --- | --- | --- |
| UNVERIFIED | 172 | 88.2% |
| COMPLETED | 10 | 5.1% |
| PARTIAL | 7 | 3.6% |
| INTENT_NOT_FULFILLED | 5 | 2.6% |
| TOOL_OK_VERIFIER_INCONCLUSIVE | 1 | 0.5% |

**Statuses never observed:** BLOCKED_BY_POLICY, FAILED, NEEDS_PERMISSION, NEEDS_USER  → candidates to collapse in Sprint 3.

## G — Top-line findings

- **45/65 compound tools never called** (45% of subsets were empty) — review for deletion in Sprint 3.
- **Microagents are unobservable**: no match event. Sprint 2.2 adds `microagent_matched`.
- **Skills are unobservable**: no `skill_load` activity. Sprint 2.2 adds `skill_loaded`.
- Capability classifier cache hit rate: **3.2%** → CANDIDATE TO KILL per Sprint 3 threshold.
- **45% of turns** hit the `subset=[]` fallback path → semantic_router carries serious load.
- Top mission_outcome status: **UNVERIFIED** (172/195 = 88%).
