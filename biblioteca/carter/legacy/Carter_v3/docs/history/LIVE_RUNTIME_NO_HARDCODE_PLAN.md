# LIVE_RUNTIME_NO_HARDCODE_PLAN

Date: 2026-05-05
Source of truth: `ContextoCarter.md`.
Predecessor docs: `LIVE_RUNTIME_NO_HARDCODE_AUDIT.md`,
`REJECTED_HARDCODE_RUNTIME_ATTEMPT_REPORT.md`.
Baseline: checkpoint `4d9c9f2f`, suite 398/398, `hardcode_guard` clean.

This plan defines **cycle 1**. It is universal-only. Phrase-keyed
detectors and brand lists are not on the menu.

---

## Cycle 1 — Universal repair (≤ 8 changes)

### Order of operations
1. **U0 — Harden `hardcode_guard` first.** Implement before any production
   change so the same V1 mistake is mechanically refused going forward.
2. Implement U1–U6 in order (small, isolated, each compilable).
3. After U1–U6: add behaviour tests (no fixture-style phrase matching).
4. Run full suite + hardcode_guard.

### Hard limits
- ≤ 8 cycles total; ≤ 6 hours wall-clock.
- Each change has a one-line rollback (a single `git checkout -- <file>`).

---

### U0. Harden `audit/hardcode_guard.py` + add `tests/test_no_semantic_hardcodes.py`

**Files:** `audit/hardcode_guard.py`, `tests/test_no_semantic_hardcodes.py` (new).

**Why universal:** the guard scans the source tree for shapes, not for
specific words. New rules added:

- For *every* `*.py` file under `src/carter_v3/` (no allowlist exemption):
  flag any module-level `Assign` whose target name matches the regex
  `^_?[A-Z][A-Z0-9_]*_RE$` and whose value is a `re.compile(...)`
  whose pattern string contains any of the banned **brand tokens**
  (already catalogued in `DENY_BRANDS_HINT`) **or** any of the banned
  **semantic-suffix names** (`SEND_MESSAGE`, `MEDIA_PLAYBACK`,
  `ALARM_REMINDER`, `INSTALL_DOWNLOAD`, `THIRD_PARTY_MESSAGE`).
- New rule `semantic_intent_re_name`: any `*_RE` / `*_REQUEST` / `*_PATTERN`
  module-level `re.compile` whose pattern source contains 4+ alternated
  bare lowercase verbs separated by `|` *and* 2+ alternated bare
  lowercase nouns separated by `|`, regardless of file (the V1 detectors
  matched this shape exactly).
- New rule `looks_helper_brand_or_semantic_suffix`: any `def looks_*` whose
  name contains substring `alarm`, `reminder`, `media`, `playback`,
  `send_message`, `messaging`, `install`, `download`, `third_party`,
  fails. (These names are themselves the hardcode signature.)
- ALLOWLIST scope is **narrowed**: the existing exempt files keep their
  exemption only for the *constant kinds* the audit already records
  (e.g. `request_patterns.IMPERATIVE_SUFFIXES`,
  `secret_filter.SECRET_ANCHORS`). Any *new* `*_RE` constant in those
  files goes through the rules above.

**Test (`tests/test_no_semantic_hardcodes.py`):** invokes
`audit/hardcode_guard.main()` programmatically and asserts exit 0. Then
synthesises a temporary file containing each forbidden shape (in a
tmp_path under a fake `src/carter_v3/`) and asserts the guard returns 1
with the matching rule name. Never references real app brands as data;
uses placeholder tokens that match the *shape* of the rule.

**Why NOT hardcode:** the guard rules are about identifier shape and
pattern shape, not about the meaning of any specific brand. Adding a new
brand to a denylist is allowed; that denylist already exists with audit
discipline.

**Risk:** medium-low. If the guard becomes too strict it may flag
existing audited constants. Mitigation: tests assert the existing tree
still passes. Rollback: revert `audit/hardcode_guard.py` and delete the
new test.

---

### U1. Restore `prior_turns` accumulator in the REPL

**File:** `src/carter_v3/cli/launcher.py`.

**Change:** the `while True:` REPL loop maintains a small `history` list
capped at 12 items (6 user/assistant pairs) and passes it as
`prior_turns=history` to `engine.run_turn(...)`.

**Why universal:** `engine.run_turn(text, prior_turns=…)` is the public
contract; tests already exercise it. The CLI has no semantic content,
just a missing call-site argument.

**Why NOT hardcode:** no phrase, no app, no brand.

**Test:** `tests/test_pending_intent_followups.py::test_repl_history_accumulates`
exercises `launcher.main(["--once-script", scripted_input])` if a script
mode exists, otherwise it invokes the REPL function with a fake stdin
and a `ScriptedAdapter`, then asserts `engine.run_turn` was called with
a non-empty `prior_turns` on the second turn (using a small spy).

**Risk:** trivial. Rollback: `git checkout HEAD -- src/carter_v3/cli/launcher.py`.

---

### U2. Derive system prompt from `TOOL_CATALOG`

**Files:** `src/carter_v3/turn_support.py`.

**Change:** `build_messages` constructs the `system` content from:

- Carter persona block (3 sentences max, language-agnostic, no brand list).
- A *rendered* tool list: `f"- {spec.name}: {spec.description}"` over
  `iter_specs()`, optionally filtered to the same `tools_for_llm` subset
  that this turn already passed to the adapter so the system prompt and
  the function-spec view agree.
- Language-mirroring instruction.
- No-fake-success contract.

There is no enumeration of NOT-capabilities, no brand list, no
phrase list. The "what Carter cannot do" message is delivered implicitly
by the tool list being the only things named.

**Why universal:** content is derived from `TOOL_CATALOG` at runtime. If
a new tool is added or removed, the prompt updates automatically.

**Why NOT hardcode:** every dynamic line is generated from the catalog;
the static text is identity + language + verification rule, none of
which mention apps or categories.

**Test (`tests/test_runtime_persona_and_capabilities.py`):** assert that
`build_messages(...)` system content contains every catalog tool's
`name`; that it contains the persona phrase "Carter"; that swapping in a
mock catalog with a new tool name makes that name appear in the prompt
(via dependency-inject the iterator if needed; otherwise patch
`TOOL_CATALOG`).

**Risk:** medium. Larger system prompt = more tokens. Acceptable for
local Ollama. Rollback: revert `turn_support.py`.

---

### U3. Composer reads `outcome.evidence["preexisting"]` for `app_open` PENDING

**File:** `src/carter_v3/response_composer.py`.

**Change:** in the `app_open` UNVERIFIED arm, before composing the
generic "intenté abrir … pero no pude verificar" sentence, check
`outcome.evidence.get("preexisting") is True`. If so, return:

> `f"{target} ya estaba abierto antes de tu comando: detecté el proceso, pero no puedo atribuir esta apertura a esta acción."`

**Why universal:** reads an already-existing evidence key produced by
`tools/verifier.py::_app_open`. The composer treats the verifier as
truth; no phrase or app inspection.

**Why NOT hardcode:** no user-text inspection, no brand string, no per-app
arm. Applies to every `app_open` outcome the verifier records.

**Test:** `tests/test_live_regressions_from_user_log.py::test_app_open_preexisting_yields_already_running_reply`
synthesises a `VerifiedOutcome("app_open", PENDING, "...", evidence={"preexisting": True})`
and asserts the composer reply contains "ya estaba abierto" (no
specific app name asserted).

**Risk:** trivial. Rollback: revert composer.

---

### U4. Composer surfaces `data["next_step_hint"]` for any failed tool

**File:** `src/carter_v3/response_composer.py`.

**Change:** factor out `_next_step_suffix(result)` that returns
`f" Próximo paso: {hint}." if hint else ""`. Append it to the
UNVERIFIED branches of every dispatched-tool composition (one helper
call site per arm, or once at the end of `compose_default_reply`).
**No `pycaw` substring**; no per-tool wording. The hint is whatever the
dispatcher wrote into `data["next_step_hint"]`.

**Why universal:** generic data passthrough, no semantic inspection.

**Why NOT hardcode:** no string match on any payload value.

**Test:** in `tests/test_runtime_no_fake_success_live_cases.py`
synthesise a failed `system_set_volume` `ToolResult(ok=False, data={"next_step_hint": "install pycaw: pip install pycaw"})`
and assert the composer reply contains the hint substring exactly as
written by the dispatcher (i.e. echo, not paraphrase).

**Risk:** trivial.

---

### U5. Map `data["missing_dependency"]` to `policy_blocks=["needs_environment …"]`

**Files:** `src/carter_v3/agent.py` (one helper after tool execution),
plus `src/carter_v3/tools/dispatch_system.py` may need a tiny addition to
also stamp `data["missing_dependency"]` (not only the hint). The
`compute_mission_status` mapping already exists.

**Change:** after the tool-dispatch loop, before computing mission
status, scan `tool_results` for any entry where `not r.ok and isinstance(r.data, dict) and r.data.get("missing_dependency")`. For
each, append `f"needs_environment missing_dependency:{r.data['missing_dependency']}"`
to `policy_blocks`. `compute_mission_status` already maps any
`needs_environment` substring to `MissionStatus.NEEDS_USER` +
termination_reason `"needs_environment"`.

**Why universal:** triggers on a structural data field set by the
dispatcher, not on a tool name or message regex.

**Why NOT hardcode:** no tool-specific arm; any future
`MissingDependency` from any tool flows the same way.

**Test:** `tests/test_runtime_no_fake_success_live_cases.py::test_missing_dependency_routes_to_needs_environment`
runs an agent turn with a stub adapter that emits a tool call to a tool
whose dispatcher returns `data={"missing_dependency": "fakepkg"}` and
asserts mission_status == NEEDS_USER, termination_reason ==
"needs_environment".

**Risk:** medium. The reordering of `policy_blocks` evaluation must not
override real CONFIRMED outcomes. Mitigation: only inject when the
tool's own outcome is FAILED.

---

### U6. Notify-toast composer arm — narrate the toast, not the side effect

**File:** `src/carter_v3/response_composer.py`.

**Change:** add a `notify_toast` arm (currently falls into the generic
arm) that returns:

> `f"Mostré una notificación con el texto: \"{text}\"."`

regardless of what the embedded text says. Carter never claims the
side-effect implied by the toast text.

**Why universal:** literal narration of the actual side effect (a Windows
toast appeared); no semantic inspection of the text content; no per-app
behaviour. Applies whether the toast text is "alarma 9am",
"recordatorio leche", or "hola".

**Why NOT hardcode:** zero user-text inspection. Zero phrase keying. The
LLM may *try* to weaponise `notify_toast` as a fake-alarm; the composer
narrates it accurately so the user is not deceived.

**Test:** `tests/test_runtime_no_fake_success_live_cases.py::test_notify_toast_does_not_claim_side_effect`
asserts the reply for a `notify_toast(text="alarma a las 9am")` outcome
literally contains "Mostré una notificación" and does NOT contain
"programada", "configurada", "lista".

**Risk:** trivial.

---

## Out of scope for cycle 1 (deferred or rejected)

- Generic pending-intent state for arbitrary "Sí/No" follow-ups beyond
  the existing `pending_memory_offer` and `pending_tool_approval`. Needs
  a new contract; deferred to cycle 2 if cycle 1 measurements show it
  is necessary after U1+U2.
- `intent_classifier` reshaping (e.g. typo "HGOla" → greeting). Risky
  and not the source of fake-success. Defer.
- Tool catalog growth (e.g. adding an alarm tool). Out of scope; the
  whole point is that absence is honest.
- Cloud LLM, VLM, voice, camera, UI overhaul, shutdown/reboot, real
  third-party messaging, downloads, installs. All forbidden by
  `ContextoCarter.md`.
- Editing repository memory under `/memories/repo/`.

---

## Test coverage promised in cycle 1

New test files (each behaviour-only, no fixture-quoted user phrases that
encode app brands):

1. `tests/test_no_semantic_hardcodes.py` — guards U0.
2. `tests/test_runtime_persona_and_capabilities.py` — guards U2.
3. `tests/test_live_regressions_from_user_log.py` — guards U3.
4. `tests/test_runtime_no_fake_success_live_cases.py` — guards U4, U5, U6.
5. `tests/test_pending_intent_followups.py` — guards U1.

Each test file imports public modules only and uses synthetic outcomes /
synthetic adapter scripts; no live LLM dependency.

## Validation gates (cycle 1 exit criteria)

- `python -m pytest --tb=short` → all passing (398 baseline + new tests).
- `python audit/hardcode_guard.py` → exit 0.
- `python -m pytest tests/test_no_semantic_hardcodes.py -v` → all green.
- Diff is reviewable (≤ 200 lines of production code total for U1–U6).
- No file outside the named change list is modified.
- No new constant or helper appears whose name contains the substrings
  listed in U0's `looks_helper_brand_or_semantic_suffix` rule.

## Live-safe smoke (best effort, after cycle 1 passes gates)

If `qwen2.5:7b-instruct` is reachable on `localhost:11434`, run a
scripted REPL through `Run_Carterv3.py` for the critical case classes
listed in the V2 charter (Conversation/Persona, Memory, Files, Apps,
Volume, Alarms-as-honest-failure, Safety). Record results in
`LIVE_SAFE_RUNTIME_SMOKE_RESULTS.md` with exact prompt, exact reply,
mission_status, pass/fail, and an evidence note. If the live run is
blocked by environment, mark BLOCKED_BY_ENVIRONMENT and do **not**
declare LIVE_TEXT_CORE_READY.

---

End of cycle 1 plan.
