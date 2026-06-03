# Sprint 3a — Log (minimal structural cuts)

- **Started:** 2026-05-17
- **Finished:** 2026-05-17 (same session)
- **Operator:** Claude Code (Opus 4.7)
- **Base commit:** e68440d `docs(sprint_prompts): replace Sprint 3a with minimal-structural version`
- **Final commit before this log:** 8bc3f09 `sprint3a: reduce grounding_gate fallbacks to es+en (audit §2.9)`
- **Net delta vs base:** 12 files changed, **+105 insertions, −1796 deletions = −1691 LOC**
- **`COMPOUND_TOOL_SCHEMAS`:** 65 → 65 (unchanged, as the prompt required)

## What we discarded by re-scoping

The prompt at commit `f2dff89` would have deleted 37 of the 65
compound tools based on "0 calls over 5 days". The minimal version
of Sprint 3a (`e68440d`) replaced that plan because the agent's
declared scope is "control the whole PC" — a 5-day personal-use
window doesn't justify cutting tools like `database`, `office`,
`vision`, `developer`, etc. Sprint 3a now targets only what is
**structurally** justified, independent of usage data.

## 3a.1 — NLI stack killed — commit 0b8527e ✅

### Pre-flight call-site map

```
gemma4_agent/
├── agent.py            ← 7 references: planner-time augment_subset call,
│                         experience.record() capability_label arg,
│                         async grounding_check call + _nli_cb closure,
│                         intent_validator imports (NOT NLI-deps).
├── grounding_gate.py   ← inline morphology gate + async NLI gate
│                         (split kept inline, removed async).
├── intent_validator.py ← regex + lookup of CROSS_REJECT_PAIRS;
│                         confirmed no NLI dep. Untouched.
├── voice/stt.py        ← uses _ml_import_lock with an ImportError
│                         fallback to a no-op contextmanager. Safe to
│                         delete the helper.
└── tools.py / planner.py ← no references.
```

### Removed files

| File | LOC | Reason |
|---|---|---|
| `capability_classifier.py` | 303 | Cache hit rate 3.2% over 5 days (vs 20% kill threshold from `08_findings.md §2.10`). |
| `nli_service.py` | 246 | Only consumer was `capability_classifier` + async grounding. |
| `_ml_import_lock.py` | 49 | Only existed to serialize NLI + Whisper imports; without NLI there is no race. `voice/stt.py` already falls back to a no-op cleanly. |

### Modified

- **`grounding_gate.py`**: kept the inline `detect_action_claim_without_evidence`
  + `_FALLBACKS_BY_LANG` + `format_fallback` + helpers. Removed
  `GROUNDING_LABELS`, `build_evidence_premise`, `schedule_grounding_check`
  and the `nli_service` import. `logging`/`Callable` imports dropped
  (only the async path used them). `__all__` shrunk.
- **`agent.py`**: removed the `augment_subset` call (37 LOC try/except),
  removed `classify_capability_cached` from the `experience.record()`
  path (`capability_label = None` for now, with a comment), removed
  the `schedule_grounding_check` call and its `_nli_cb` closure.

### Removed tests

| Test | Reason |
|---|---|
| `test_capability_classifier.py` | Subject removed. |
| `test_nli_service.py` | Subject removed. |
| `test_ml_import_lock.py` | Subject removed. |
| `test_daredevil_e2e.py` | Whole E2E built around the capability classifier path; no salvageable assertions outside it. |

### Modified test

- **`test_grounding_gate.py`**: trimmed `TestEvidencePremise` +
  `TestSchedulesAsyncNLI` (NLI-dep classes) + their imports. Inline
  morphology coverage (`TestPreteritMorphology`,
  `TestStartsWithActionClaim`, `TestInlineGate`) preserved.
  Result: 17/17 passing.

### Verifications

- `python -c "import gemma4_agent"` ✓
- `python -c "from gemma4_agent.tools import COMPOUND_TOOL_SCHEMAS; print(len(...))"` → 65 ✓
- `python -m gemma4_agent.launcher status` shows "tools 65 compound schemas" ✓
- `python -m unittest gemma4_agent.test_grounding_gate` → 17/17 ✓
- `python -m unittest gemma4_agent.test_session847_fixes` → 33/33 ✓

### `requirements.txt`

Confirmed via `grep -rn "import transformers"`: `transformers` was
imported **only** in `nli_service.py`. It was not pinned in our
`requirements.txt` (it came in as a transitive dep of
`sentence-transformers`), so no change to that file was needed.
`sentence-transformers` (semantic_router) and `huggingface_hub`
(voice/stt) stay.

## 3a.2.a — Planner regex ES+EN — commit a112fda ✅

`planner._suggest_tools` had ~30 buckets, most with keywords in
ES/EN/PT/FR/IT. CORE_PROMPT commits the agent to Spanish output, and
Sprint 2 traces show only ES/EN inputs.

### What we kept

- Every ES keyword.
- Every EN keyword.
- Cross-family universals: `steam`, `youtube`, `opera`, `chrome`,
  `musica`, `video`, `audio`, `document`, `pdf`, `csv`, `sql`, `ssid`,
  `wifi`, `ffmpeg`, `docker`, brand/proper nouns, technical acronyms
  (DNS, USB, HID, MQTT, etc).

### What we removed

PT-/FR-/IT-only tokens with no ES or EN cognate in the same bucket:
`bibliotheque`, `cancao`, `chanson`, `canzone`, `musique`,
`apresentacao`, `tableur`, `executer`, `cliccare`, `schermo`,
`pulsante`, `compito`, `pendente`, `lembrete`, `abitudine`,
`tapparelle`, `quando dico`, `quand je dis`, etc.

### Behaviour checks

| Input | Output | Verdict |
|---|---|---|
| `abrí Steam` (ES) | `[steam, app, window, verify, session]` | ✓ |
| `open Steam` (EN) | `[steam, app, window, verify, session]` | ✓ |
| `apri Steam` (IT) | `[steam, app, window, verify, session]` | ✓ via proper-noun match |
| `ouvrir le navigateur` (FR) | `[session]` (no keyword match) | ✓ intentional |
| `mandale mensaje en whatsapp a Juan` | `[whatsapp, contacts, …]` | ✓ |
| `pon Daredevil en Netflix` | `[media, browser, audio, …]` | ✓ |

LOC: `planner.py` 892 → 730 (**−162 LOC**).

### Tests

`test_router`, `test_router_corpus`, `test_planner_continuation`,
`test_session847_fixes` all pass. One pre-existing failure in
`test_planner_continuation::test_without_hint_short_reply_subset_empty`
was confirmed to predate this sprint (`git stash; pytest; git stash pop`
showed the same failure on HEAD).

## 3a.2.b — Grounding fallbacks ES+EN — commit 8bc3f09 ✅

`_FALLBACKS_BY_LANG` had 6 languages × 4 templates = 24 strings.
`_LANG_HINTS` had 6 buckets of phonetic hints. Both dropped to es+en.
`format_fallback`'s existing `or _FALLBACKS_BY_LANG["es"]` covers any
unknown language.

LOC: `grounding_gate.py` −33; `test_session847_fixes.py` −2 tests, +1.

### Test update

`TestLanguageAwareFallback.test_detects_italian` and
`test_detects_german` were rewritten as a single
`test_unknown_language_falls_back_to_spanish` that asserts the new
contract (unknown → es).

## 3a.2.c — `mission_goal._VERB_KIND_PATTERNS` — SKIPPED

`mission_goal.py` is in the no-touch list per the Sprint 3a prompt
("Carter-heredado y los tests son frágiles"). Even though the change
would have been cosmetic identical to the planner trim, the rule was
explicit. **Deferred to Sprint 4** which can include it under a
broader refactoring brief with tests-first methodology.

## 3a.3 — Final state

```
$ git log --oneline -6
<this commit>
8bc3f09 sprint3a: reduce grounding_gate fallbacks to es+en (audit §2.9)
a112fda sprint3a: reduce planner regex to ES+EN (audit §2.8)
0b8527e sprint3a: kill NLI stack (capability_classifier + nli_service + _ml_import_lock; async layer of grounding_gate)
e68440d docs(sprint_prompts): replace Sprint 3a with minimal-structural version
f2dff89 docs(sprint_prompts): add Sprint 3a prompt (confident cuts only)

$ git status
On branch PortandoLoMejor
nothing to commit, working tree clean

$ python -c "from gemma4_agent.tools import COMPOUND_TOOL_SCHEMAS; print(len(COMPOUND_TOOL_SCHEMAS))"
65

$ python -m gemma4_agent.launcher status
... tools  65 compound schemas ...
```

## Recap

| Commit | Delta |
|---|---|
| `0b8527e` NLI stack | 10 files, +29 / −1531 |
| `a112fda` planner regex | 1 file, +66 / −228 |
| `8bc3f09` grounding fallbacks | 2 files, +10 / −37 |
| **Total before this log** | **12 files, +105 / −1796 (−1691)** |

### Things to remember

1. **`agent.py` now records experiences with `capability_label = None`.**
   When/if a regex-based capability classifier replaces the killed NLI
   one (Sprint 4 candidate), restore that field. The Bug 2 RAG-hint
   pathway already tolerates `None`.
2. **`detect_reply_language` always returns `"es"` or `"en"`** now.
   Callers that switch on this value only need to handle those two
   cases.
3. **`intent_validator.py` is intact** (regex + `CROSS_REJECT_PAIRS`
   lookup; no NLI dep). Sprint 3b/4 may still consider whether the
   `<intent>` tag mechanism earns its complexity.

### Recommendation for Sprint 3b

Wait **7-10 days of normal use** so the three instrumentation events
added in Sprint 2 (`persona_active`, `microagent_matched`,
`skill_loaded`) accumulate enough signal to drive decisions about
those modules. Re-run `python scripts/analyze_traces.py` after that
window; the report drops back into the same path the operator already
has open.

### Recommendation for Sprint 4

Carries no data dependency. Likely candidates (per `08_findings.md`):
- Split `Gemma4Agent` god class.
- Lazy-load heavy imports (faster_whisper, sentence_transformers).
- Worker thread / sink unification.
- The `mission_goal._VERB_KIND_PATTERNS` ES+EN trim deferred above.
- Reconsider the `<intent>` tag mechanism in `intent_validator.py`.
