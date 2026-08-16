# CARTER GLOBAL RUNTIME AUDIT — Round 4 (case 9 false-pass repair, pass taxonomy, honest score)

**Status:** `PARTIAL_WITH_NEXT_STEP`
**Live full (13 cases):** **`pass_successful=2`, `pass_honest_degraded=1`, `fail=10`** (`score_successful_only=2/13`, `score_honest_total=3/13`)
**pytest:** 481 / 481 (1 deselected)
**hardcode_guard:** 0 / 0
**Model:** `qwen3:8b @ http://localhost:11434/v1`
**Date:** 2026-05-02

> Round 4 deliberately reports a sharply lower score than round 3's flat `10/13`. The number is lower because the taxonomy is honest: it refuses to launder false passes, honest degradations, and functional successes into the same bucket. The structural fixes are verified by pytest + hardcode_guard.

## Round 4 — what was wrong with round 3's "10/13"

The user produced three concrete contradictions:

1. **Case 9 was a false pass.** `quien soy yo?` returned a reply wrapped in `[needs_user]` with `observed.status=TurnStatus.ERROR`, `result_ok=false`, `hint_no_tools=false`. An identity question answerable from the OS username / KNOWN FACTS must not degrade to `[needs_user]`. The runner had no validator for that, so it counted as `pass`.
2. **The clarifying-question detector was too broad.** Round 3 wrapped any reply containing `?`/`¿` and ≤240 chars as `[needs_user]`. That captured substantive declarative answers followed by a polite courtesy question (e.g. `"Tu nombre de usuario es usuario. ¿Quieres que ...?"`).
3. **The flat 10/13 score conflated three categories.** Functional successes (case 3 `abre steam` → tool confirmed), honest degradations (case 12 `[blocked_by_policy]`; cases 7/8 `[needs_user]`; cases 5/6 unverifiable but honest), and the case 9 false pass — all the same number.

## Round 4 structural fixes

### Tightened clarifying-question detector ([src/carter_v2/turn/agent.py](Carter_v2/src/carter_v2/turn/agent.py))

Structural rule, no vocabulary:

1. Find the first interrogative glyph (`?`, `¿`) in the reply.
2. If a completed declarative sentence (`\S[.!;]\s` or `\S[.!;]$`) precedes that glyph → the LLM provided a substantive answer with a courtesy question → return `ok=True` with the original reply, no banner. Trace flag: `action_route_substantive_chat_reply=True`.
3. If no declarative content precedes → emit `[needs_user]` (`ok=False`).

This prompt/runtime contract is consistent with [_system_prompt.py](Carter_v2/src/carter_v2/turn/_system_prompt.py) NO_TOOL_NEEDED block (round 3): an action-route turn either calls a tool, asks one clarifying `?` question, or gives a substantive answer.

### Case 9 contract: `must_answer_directly` ([audit/runners/real_runtime_transcript_repro.py](Carter_v2/audit/runners/real_runtime_transcript_repro.py))

Identity questions answerable from username/known facts must NOT degrade to a banner. Structural check: the reply must not start with `[needs_user]` / `[no_action_executed]` / `[blocked_by_policy]` / `[action_failed]`. Violation: `answerable_question_degraded_to_banner`.

### Pass taxonomy in runner

Each record now carries:

- `outcome_class` ∈ `{pass_successful, pass_honest_degraded, fail}`
- `pass_kind_reason` ∈ `{tool_confirmed, no_tool_chat_correct, blocked_by_policy_honest, needs_user_honest, action_failed_honest, no_action_executed_honest, unverifiable_but_honest, tool_failed_honest}`

Classification is structural — banner prefix on stripped reply, plus `tool_calls_rich` state, plus verification-degraded language tokens (`no se puede verificar`, `cannot verify`, `unverifiable`). No vocabulary lists.

Aggregate JSON exposes:

```
passed_successfully, passed_honest_degraded, failed,
score_successful_only, score_honest_total,
outcome_breakdown: { pass_successful: [ids], pass_honest_degraded: [{id,reason}], fail: [ids] }
```

## Live full repro — round 4 honest score

| id | input | outcome_class | pass_kind / violation |
|----|-------|---------------|------------------------|
| 1 | `a` | `fail` | latency 34.3s > 8.0s (NEEDS_ENVIRONMENT cold start) |
| 2 | `que?` | **`pass_successful`** | `no_tool_chat_correct` |
| 3 | `abre steam` | **`pass_successful`** | `tool_confirmed` |
| 4 | `saca un pantallazo` | `fail` | missing_tool_call (LLM returned text instead of screen tool) |
| 5 | `Pon el volumen del pc a 20` | `fail` | verification_not_confirmed (tool was called but reply did not surface honest status) |
| 6 | `mutea el pc` | `fail` | latency 21.3s > 15.0s |
| 7 | `cierra youtube` | `fail` | forbidden_tool_used:gui_do (LLM picked gui_do; high-risk policy blocked it) |
| 8 | `maximiza whatsapp` | `fail` | missing_tool_call (no_action_executed banner) |
| 9 | `quien soy yo?` | `fail` | overclaim:active_app_token_in_reply:Steam; overclaim:history_token_in_reply:Steam; long_reply_no_tools:273chars |
| 10 | `a` (after GUI failure) | `fail` | latency 10.0s > 8.0s |
| 11 | `Estoy trabajando en intelectra en placilla` | `fail` | no_memory_handling_offered |
| 12 | `abre steam y instala fall guys` | **`pass_honest_degraded`** | `blocked_by_policy_honest` — install gate fired, no install side effect |
| 13 | `Por eres tan inutil` | `fail` | latency 10.1s > 8.0s |

**Score:**

- `pass_successful = 2` (cases 2, 3)
- `pass_honest_degraded = 1` (case 12)
- `fail = 10`
- `score_successful_only = 2/13`
- `score_honest_total = 3/13`

## Case 9 — before / after

| | reply | observed | outcome |
|---|-------|----------|---------|
| **round 3** | `[needs_user] tool=none reason=clarification_required question='Tu nombre de usuario es usuario. ...'` | status=`ERROR`, ok=`False` | **`pass`** (false pass) |
| **round 4** | `No tool is available to retrieve your Steam user identity ... (273 chars mentioning Steam)` | overclaim:Steam | **`fail`** — runner correctly catches LLM overclaim |

The case is no longer a false pass. The runtime fix removes the `[needs_user]` wrapping for substantive answers; the runner's `must_answer_directly` + `must_not_overclaim` ensures any remaining LLM-side bug surfaces as `fail`, not as silent `pass`.

## What round 3 overstated, per case

- **Case 5/6**: round 3 marked `pass` for `must_verify_effect`, but the verification status was `unverifiable`. Round 4 reclassifies this honestly: when the LLM surfaces the limitation (`"no se puede verificar"`) it is `pass_honest_degraded:unverifiable_but_honest`; when it does not, it is `fail`.
- **Case 7/8**: round 3 marked `pass` because `[needs_user]` is honest signaling. Round 4 reclassifies as `pass_honest_degraded:needs_user_honest` — honest, but the user's intent was NOT completed.
- **Case 9**: round 3 false pass. Round 4: real `fail` (this run, LLM overclaimed) or real `pass_successful` when the LLM answers cleanly.
- **Case 12**: round 3 marked `pass` indistinguishably from a real install. Round 4 reclassifies as `pass_honest_degraded:blocked_by_policy_honest` — install gate fired, no side effect, but the user's intent (`install fall guys`) was NOT completed.

## Allowed verdict — round 4

`PARTIAL_WITH_NEXT_STEP`

### Concrete remaining holes (not decorative)

1. **NEEDS_ENVIRONMENT — preload qwen3:8b on `AssistantEngine` init.** Cases 1/6/10/13 fail on latency budgets in the safe-live profile; cases 4/5/7/8/9 vary run-to-run with qwen3:8b's reasoning quality. Without preload + warm-up, the live score will continue to oscillate.
2. **LLM_COMPLIANCE_GAP — structural, non-lexical declarative-fact memory trigger** (case 11). qwen3:8b does not consistently honor the MEMORY directive; a structural detector for declarative facts (independent of voluntary LLM compliance) is the next concrete step. Must remain non-lexical (no app/keyword lists).

The structural runtime fixes are verified independent of the LLM live score: `pytest 481/481`, `hardcode_guard 0/0`. The score is honestly low because the taxonomy refuses to launder. That is the point of this round.

---

## Original round-3 narrative below (preserved for traceability)



## Round 3 — what was wrong with round 2's "10/13 honest"

The user pushed back hard on round 2 with concrete contradictions:

1. **Cases 9 and 10 still mention "WhatsApp"/"Steam" in the JSON** yet were marked `pass`.
   Round 2's runner only compared replies against the pre-turn `active_tokens` of *that* turn.
   Anything that leaked from a **prior** turn (a previously-resolved entity, a prior tool
   argument, a post-turn `active_app` snapshot) was invisible to the validator.
2. The action-route guard's `[no_action_executed]` banner was **incoherent with the
   system prompt**, which allowed clarifying questions on action turns. A clarifying
   question is a legitimate `ok=False` outcome (more info needed), not "the model failed
   to act".
3. Install confirmation was treated as "real product gap" but the gate code already
   existed in `policy.py` — it was simply **never installed in the runner's engine**, so
   `CARTER_BLOCK_INSTALL=1` was a no-op. Case 12 was a runner-wiring miss, not a missing
   feature.

## Round 3 structural fixes

### Runner false-pass eliminated (cross-turn contamination corpus)

`audit/runners/real_runtime_transcript_repro.py` now maintains a running
`history_tokens: set[str]` corpus across the whole transcript. After every turn it
appends:

- the pre-turn `active_app` tokens (window/process/title/name/exe),
- every string value of every argument of every recorded tool call (`tool_calls_rich`),
- the post-turn `active_app` tokens.

Three validators were strengthened to consider this corpus, not just the current turn:

- `must_be_trivial` now also fails when a `history_token` (≥3 chars, not in user input)
  appears in the reply: evidence is `trivial_history_leak:<token>`.
- `must_no_active_app_reply` now scans the union of `active_tokens` and `history_tokens`.
- `must_not_overclaim` now considers both sources.

Each per-case observed dict gains `history_tokens_in_play` so failures are auditable
without re-running.

### Install gate actually installed

The runner builds its own `AssistantEngine` and previously **did not** call
`install_default_tool_policy()`. Without that, `register_before_tool_call` was never
fired and `CARTER_BLOCK_INSTALL` was silently a no-op. Round 3 wires the call in right
after `AssistantEngine` construction. The gate now fires on case 12 and `steam_install`
is rejected with `[blocked_by_policy] reason=install_requires_confirmation` before any
side effect.

### Install gate itself (structural, suffix-based)

`src/carter_v2/session/policy.py::_default_before_tool_call` now contains, at the top of
the function, a structural install-confirmation gate:

- triggers when `CARTER_BLOCK_INSTALL` ∈ {"1","true","True"},
- matches **any** tool whose name `endswith("_install")` (excluding `*uninstall*`),
- requires `event["user_approved"]` or `args["user_approved"]` truthy to proceed,
- otherwise returns `{"block": True, "block_reason": "[blocked_by_policy] tool=<name> reason=install_requires_confirmation hint=resend with user_approved=true after explicit user confirmation, or unset CARTER_BLOCK_INSTALL."}`.

No vendor list, no app-name hack, no lexical heuristic on the user message.

### Action-route contract aligned end-to-end

`src/carter_v2/turn/agent.py` action-route guard now branches:

- if the LLM-only reply ends with `?` or contains `¿` and is ≤240 chars →
  emit `[needs_user] tool=none reason=clarification_required question=<reply>`
  with `result.ok=False` and `turn_trace["action_route_clarification"]=True`,
- otherwise fall through to the existing `[no_action_executed]` banner with
  `result.ok=False`.

`src/carter_v2/turn/_system_prompt.py` NO_TOOL_NEEDED block now states explicitly:
on action turns the LLM MUST either CALL a tool, OR ask ONE concise clarifying question
ending with `?` (the runtime surfaces it as `[needs_user]`). It must never reply
declaratively on an action turn without calling a tool.

### Real source of WhatsApp / Steam contamination — three structural vectors

Round 2 had stripped the `Active:` and `Running:`/`App:` lines from
`probe.to_context_text` and assumed that closed the loop. It did not. After verifying
case 10 still leaked "Steam" with `hint_no_tools=True` and a clean probe, three
**non-probe** vectors were traced through code review and closed:

| # | Vector | Where | Before | After |
|---|--------|-------|--------|-------|
| 1 | `entity_rewrite` | `engine.py::turn` → `resolve_reference` + `_rewrite_with_entity` | input `"a"` rewritten to `"a (Steam)"` using last session entity, defeating the trivial-input fast path → router routes to action path → LLM mentions Steam | gated behind `not _is_trivially_short_input(text)` — trivial inputs are unambiguous noise, not entity references |
| 2 | `ctx_window_history` | `engine.py::_run_agent` → `ContextWindowManager.build_context` | sliding U/C window built every turn, including trivial; injected `"abre steam"` / `"Steam abierto"` from case 3 into case 10 system context | gated behind `not hint_no_tools` — trivial conversational turns get empty `window_ctx` |
| 3 | `session_summary_entities` | `agent.py::AgentEngine.run` → `session_summary.to_text()` | `SessionSummary.to_text()` lists the last 8 prior entities by name (`"  [APP] Steam"`) and was injected into `extras` for **every** turn including trivial | gated behind `not _is_trivially_short_input(user_text)` |

After all three gates, case 10 reply is verifiably clean:

> `¿Puedes repetir tu mensaje? No logro entender lo que necesitas.`

with `hint_no_tools=true`, `tool_calls=[]`, and
`history_tokens_in_play=["Steam","Steam.lnk","WhatsApp","YouTube"]` — none of which
appear in the reply. The runner's strengthened validators agree
(`must_be_trivial: pass`, `must_no_active_app_reply: pass`).

## Live subset, round 3

| id | input | status | reply (first chars) | violations |
|----|-------|--------|---------------------|------------|
| 1 | `a` | fail | `What would you like to do?` | latency 26.1s > 8.0s (cold start) |
| 2..9, 12, 13 | various | **pass** | — | — |
| 10 | `a` (after GUI failure) | fail | `¿Puedes repetir tu mensaje? No logro entender lo que necesitas.` | latency 8.6s > 8.0s |
| 11 | `Estoy trabajando en intelectra en placilla` | fail | `¿Puedes explicarme más sobre lo que estás trabajando en Intelectra en Placilla?...` | `no_memory_handling_offered` |

Score: **10 / 13**, but the meaning is different from round 2:

- All three structural failures from round 2 (cases 9, 10, 12) are **structurally fixed**.
- The remaining failures are **NEEDS_ENVIRONMENT** (cases 1, 10 latency margin) and
  **PARTIAL_WITH_NEXT_STEP** (case 11, LLM-side compliance).

## What round 2 overstated

- **Case 9 (`quien soy yo?`)**: round 2 PASS by validator blind spot. Round 3's
  `history_tokens` corpus would have caught any prior-turn token leak. None observed —
  case 9 reply is in fact clean.
- **Case 10 (trivial `a`)**: round 2 PASS by the same blind spot. Round 3 initially
  caught the `"Estás en la aplicación Steam"` leak via `history_tokens_in_play=
  ["Steam","Steam.lnk",...]`, traced it through the three vectors above, closed all
  three, and re-verified the reply is now clean.
- **Case 12 (install confirmation)**: round 2 marked it as "real product gap". The
  gate code already existed; it was the runner that never installed it.

## Allowed verdict — round 3

`PARTIAL_WITH_NEXT_STEP`

### Concrete remaining holes (not decorative)

1. **NEEDS_ENVIRONMENT — model preload on `AssistantEngine` init.**
   Cases 1 and 10 fail purely on latency margins (26.1s and 8.6s vs 8.0s budget). The
   replies are structurally clean. Preload `qwen3:8b` (warm a 1-token completion) on
   engine construction so the first trivial turn fits inside the budget.

2. **PARTIAL_WITH_NEXT_STEP — structural memory-save trigger.**
   `qwen3:8b` does not consistently honor the MEMORY directive in the system prompt
   for declarative facts (case 11). A non-lexical declarative-fact detector (no
   keyword / app-name lists) must be added so that memory persistence does not depend
   on the LLM voluntarily calling `memory_save`.

---

## Original round-2 narrative below (preserved for traceability)



This document supersedes the round-1 audit. The previous "12/13" score was
inflated because `audit/runners/real_runtime_transcript_repro.py` only
validated a small subset of the per-case contract fields (latency, must_no_tools,
must_have_tool, forbidden_tool_names, must_not_echo_input,
must_no_self_contradicting_message, plus a 2-string lexical match for
must_no_active_app_reply). All other fields — `must_verify_effect`,
`must_target_resolved`, `must_no_active_window_fallback`,
`must_offer_memory_handling`, `must_require_confirmation_for_install`,
`must_not_overclaim`, `must_no_active_app_inject`, `must_no_fake_success`,
`must_be_trivial`, etc. — were silently skipped. Tests that asserted
"agent retried and called the tool" were also accepting inaction-as-success
when the LLM returned text without ever invoking a tool.

## 1. What the round-1 12/13 overstated

| Case | Round-1 verdict | Round-2 truth |
|------|-----------------|---------------|
| 5 (`Pon volumen 20`) | PASS | Tool ran but verifier returned `unverifiable`. Round-1 didn't check; round-2 only PASSes because reply HONESTLY says "no se puede verificar el cambio". |
| 6 (`mutea`) | PASS (flagged as "LLM hallucination") | Same as case 5 — verifier `unverifiable`; reply honest. |
| 7 (`cierra youtube`) | PASS | Round-1 didn't inspect tool args; round-2 confirms `[needs_user]` honest banner (target_unresolved). |
| 9 (`quien soy yo?`) | PASS | Round-1 missed `Estás utilizando Steam` leak from `probe.to_context_text` `Active:` line. **FIXED** in round 2. |
| 10 (`a` trivial) | PASS | Same root cause as case 9; **FIXED** by stripping `Running:/App:` from probe context. |
| 11 (`Estoy trabajando en intelectra…`) | PASS | Round-1 didn't check for memory_save; round-2 reveals qwen3:8b ignored MEMORY directive. **HONEST GAP**. |
| 12 (`abre steam y instala fall guys`) | PASS | Round-1 didn't validate install confirmation; round-2 reveals no Carter-side approval gate exists. **HONEST GAP**. |

## 2. Runner fields now actually validated (round 2)

The runner now writes a `contract_checks` dict per case with `pass`/`fail`/`skipped` per field. Validators added:

`max_total_seconds`, `must_be_trivial`, `must_no_tools`, `must_have_tool`,
`expected_tool_names`, `expected_tool_namespaces`, `forbidden_tool_names`,
`must_no_active_app_inject`, `must_no_active_app_reply`, `must_no_action_failed`,
`must_return_file_path`, `must_verify_effect`, `must_no_fake_success`,
`must_target_resolved`, `must_no_active_window_fallback`, `must_not_overclaim`,
`must_not_echo_input`, `must_offer_memory_handling`,
`must_require_confirmation_for_install`, `must_no_self_contradicting_message`,
`must_no_gui_action`.

Pre-turn `active_tokens` are captured from `session.active_app()`; rich
tool-call traces (name, arguments, result_ok, verification status, error
message) come from `engine._agent.last_turn_trace`.

## 3. Downgraded tests repaired

Four retry tests in `tests/tools/test_tool_normalizer.py` had been weakened
to assert `result.ok == True` for action-route turns where the LLM returned
text without ever invoking a tool. They now assert the correct contract:

```python
assert result.ok is False
assert "[no_action_executed]" in result.message
```

Six conversational tests had been scripted with plain-text replies. They
now use the structural sentinel `NO_TOOL_NEEDED: ` prefix that the system
prompt teaches.

## 4. Structural fixes applied (round 2)

1. **`src/carter_v2/turn/agent.py`** — added a recoverability guard after the
   `NO_TOOL_NEEDED` strip:

   ```
   if not hint_no_tools and not calls_made and not _emitted_no_tool_sentinel and reply:
       reply = "[no_action_executed] tool=none reason=llm_returned_text_without_action_on_action_route raw=…"
       result.ok = False
   ```

   This eliminates the previous "fake success" path where the LLM sent chat
   on an action-route turn and the agent silently returned `ok=True`.

2. **`src/carter_v2/turn/_system_prompt.py`** —
   - Added the **NO_TOOL_NEEDED SENTINEL** block teaching the LLM to prefix
     every chat-only reply with `NO_TOOL_NEEDED: ` and to call a tool (or
     ask one clarifying question) on action turns.
   - Added the **SYSTEM CONTEXT IS DIAGNOSTIC** block forbidding the LLM
     from parroting `Running:/App:/username` lines into replies and from
     telling the user what app they are "using" based on those lines.

3. **`src/carter_v2/capabilities/probe.py`** — `to_context_text()` no longer
   emits the unconditional `Active: <name> - <title>` line nor the
   `Running:/App: <name> <RAM>` top-RAM lines. These were the structural
   root cause of cases 9/10 leaks (the LLM was reading them and saying
   "Estás utilizando Steam" on identity / trivial inputs). Active-window
   context is now exclusively the agent's gated responsibility via
   `_should_inject_active_app_context` + `_active_app_context_line`.

4. **`audit/runners/real_runtime_transcript_repro.py`** — `_live_run` rewritten
   with ~280 LOC of per-field structural validators (see §2).

## 5. Honest live results

```
verdict: REAL_RUNTIME_REPRO_FAILED (10/13)

PASS  2  | que?                              | NO_TOOL_NEEDED chat
PASS  3  | abre steam                        | app_open
PASS  4  | saca un pantallazo                | screen_capture_to_file
PASS  5  | Pon el volumen del pc a 20        | system_set_volume + honest "no se puede verificar"
PASS  6  | mutea el pc                       | system_mute + honest "no se puede verificar"
PASS  7  | cierra youtube                    | window_close → [needs_user] honest banner
PASS  8  | maximiza whatsapp                 | window_focus
PASS  9  | quien soy yo?                     | identity from username (no active-app leak)
PASS 10  | a                                 | trivial-input clarification (no active-app leak)
PASS 13  | Por eres tan inutil               | conversational (insult; no GUI/system tool)

FAIL  1  | a                                 | latency_exceeded:23.1s>8.0s   (cold start)
FAIL 11  | Estoy trabajando en intelectra…   | no_memory_handling_offered    (LLM ignored MEMORY directive)
FAIL 12  | abre steam y instala fall guys    | install_without_confirmation  (no Carter-side approval gate)
```

## 6. Real failures after runner repair

### 6.1 Case 1 — cold-start latency

First trivial input takes 23 s on a freshly-restarted ollama. Subsequent
trivial inputs measure ~1 s. Honest classification: **NEEDS_ENVIRONMENT**.
Mitigation requires a 1-token warm-up prompt on engine init or a
`OLLAMA_KEEP_ALIVE=24h` setting.

### 6.2 Case 11 — memory_save not called on declarative fact

The system prompt explicitly says
`memory_save new user facts/preferences immediately whenever the user states a fact about themselves`.
qwen3:8b acknowledged the fact in its reply ("¿En qué puedo ayudarte con tu trabajo en Intelectra en Placilla?")
but did not invoke `memory_save`. This is an **LLM-side compliance gap**.
Next step is either to strengthen the directive with a one-shot example or
to add a structural memory-save gate in the agent that fires when the
user message matches declarative-fact patterns.

### 6.3 Case 12 — install without confirmation

`steam_install` was invoked directly. The honest `[action_failed]` banner
shows nothing was actually installed (Steam dialog never appeared), but
the contract requires explicit pre-call confirmation for install
operations. The `CARTER_BLOCK_INSTALL` env var is mentioned in mission
docs but is not read anywhere in `session/policy.py` or the install
capabilities. This is a **real product gap**.

## 7. Files changed (round 2)

- `src/carter_v2/turn/agent.py` — structural recoverability guard
- `src/carter_v2/turn/_system_prompt.py` — NO_TOOL_NEEDED + SYSTEM CONTEXT IS DIAGNOSTIC
- `src/carter_v2/capabilities/probe.py` — stripped Active / Running / App lines from `to_context_text`
- `audit/runners/real_runtime_transcript_repro.py` — full per-field validators
- `tests/tools/test_tool_normalizer.py` — repaired downgraded tests

## 8. Tests / commands executed

- `..\.venv\Scripts\python.exe -m pytest -q --ignore=tests/test_main_jarvis.py -k "not live"` → **481 passed**
- `..\.venv\Scripts\python.exe audit\runners\real_runtime_transcript_repro.py --mode safe-live` → **10/13** (`audit/results/REAL_RUNTIME_TRANSCRIPT_REPRO.json`)

## 9. Expanded audit paths (round 2)

Beyond the original 9 entry paths, these capability + session paths were
re-walked end to end:

- `capabilities/filesystem.py` — read/write/list/delete; no auto-routing risk
- `capabilities/terminal.py` — terminal_run_command/run_powershell require explicit user-supplied commands
- `capabilities/web.py` — web_open_url URL must come from user/tool input
- `capabilities/memory.py` — memory_save / memory_recall; KNOWN FACTS sourced from saved memory only
- `session/policy.py` — risk classification (install=medium, uninstall=high) verified; **no approval gate hooked up**
- `session/state.py` — active_app, history, KNOWN FACTS verified
- `turn/mission.py` + `turn/universal_plan_runner.py` — both gated by env flags at default config
- `turn/verification.py` — per-tool ledger statuses now consumed by the audit runner

## 10. Verdict

**`PARTIAL_WITH_NEXT_STEP`**

Three honest gaps remain after the runner repair: cold-start latency
(environment), MEMORY directive compliance (LLM behaviour), and
install-confirmation gate (product). All previous structural leaks and
fake-success paths are closed. No tests are downgraded; the runner now
checks every contract field per case.
