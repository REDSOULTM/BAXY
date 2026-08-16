# LLM Context & Memory Hardening — Final Report
**Mission:** OPUS 4.7
**Target:** Carter v2 (`Carter_v2/src/carter_v2`)
**Scope:** L1–L12 — eliminate identity contamination, prior-turn echo, active-app leakage on trivial input, placeholder/low-information replies, runaway latency, and unconfirmed style propagation. Universal & language-neutral; zero hardcodes.
**Status:** GREEN. 420/420 pytest pass. 13/13 probe cases pass on live qwen3:8b. `hardcode_guard` 0 critical / 0 total.

---

## 1. Root cause (Phase 0 audit)

See [LLM_CONTEXT_MEMORY_AUDIT.md](LLM_CONTEXT_MEMORY_AUDIT.md) for the full flow map. Five structural defects compounded into the symptoms the user reported:

| # | Defect | Symptom |
|---|--------|---------|
| R1 | `_system_prompt._build_system_prompt` consumed `memory.get_user_name()` directly with no provenance, no confidence and no conflict detection. Any past assistant utterance ("soy Carter de Como") that ended up in the `user.name` row leaked into the next system prompt. | "soy Carter de Como" reappearing on `Quien eres?` |
| R2 | `memory.set_user_name` accepted any non-empty string; no source enum, no de-dup, no `confirmed` flag. Drift accumulated silently across sessions. | Multiple contradictory `user.name` rows |
| R3 | `agent._build_active_app_message` was injected unconditionally as a system message every turn, including for `"a"`, `"Que?"`, `"Nada"`. The model treated it as the user's actual subject. | `"a"` → reply about `mission.py` |
| R4 | `_format_prior_turn_context` had no dedup and was always injected, so two consecutive greetings produced two near-identical assistant lines that the model then echoed. | "dime hola" → repeats previous reply verbatim |
| R5 | Final-reply path had no structural low-information detector and no latency clamp. A single LLM regression produced `"////////////////////////////////////////"` after 140–154 s and was forwarded to the user untouched. | `"Nada"` → 154 s of wait + `////` placeholder |

Style leakage ("Que pasa chaval" reappearing as Carter's tone) was the same class of defect as R1 applied to the `style_preference` attribute.

---

## 2. Fixes applied (L1–L8)

### L1 — Universal user-reference resolver
- New dataclass `UserRefDecision` and pure function `resolve_user_ref(config_user, memory, os_username)` in [src/carter_v2/turn/_system_prompt.py](src/carter_v2/turn/_system_prompt.py).
- Priority is structural, not lexical:
  1. `config.user_name` (high confidence, source = `config`).
  2. Memory only when **(a)** there is exactly one distinct value, **(b)** its source is `user_stated_confirmed`, and **(c)** no conflict exists.
  3. Memory `user_stated` accepted only when the single value matches `os_username` case-fold (low confidence, source = `os_username_inferred`).
  4. Otherwise OS username, otherwise `"the user"`.
- Conflicting / suspicious values are dropped into `decision.ignored_memory_values` and surfaced in the trace as `suspicious_user_ref_ignored`.
- `_build_system_prompt` now consumes the decision; `_format_memory_facts` skips `entity=user, attribute=name` rows entirely.

### L2 — Memory write & cleanup hardening
- [src/carter_v2/session/memory.py](src/carter_v2/session/memory.py): `set_user_name(name, *, confirmed: bool = False)` now writes `source=user_stated_confirmed` only when confirmed; added `list_user_name_facts()` and `delete_user_name_fact(fact_id)` for resolver and cleanup tooling.
- [scripts/maintenance/clean_corrupt_user_identity.py](scripts/maintenance/clean_corrupt_user_identity.py): dry-run by default; `--apply` does timestamped DB backup + selective delete; emits [audit/results/memory_identity_cleanup.json](audit/results/memory_identity_cleanup.json) when run.

### L3 — Active-app context gating
- `_should_inject_active_app_context(user_text, *, mission_active, has_followup_context)` in [agent.py](src/carter_v2/turn/agent.py) returns `False` for trivial input, `True` only when a real mission is active or the input itself is a follow-up referencing a previously opened app. No app-name lists; pure structural classification (`_is_trivially_short_input`, `_looks_like_app_followup`).

### L4 — Prior-turn dedup + suppression
- `_format_prior_turn_context` deduplicates near-identical assistant replies via Jaccard ≥ 0.85 on token sets (≥ 4 tokens to qualify) and records `last_deduped_count`. Trivial inputs suppress the entire prior block (`prior_turns_suppressed_reason="trivial_input"`).

### L5 — Prompt hygiene trace
- The turn loop now emits `prompt_chars`, `prompt_static_chars`, `prompt_dynamic_chars`, `memory_block_chars`, `prior_ctx_chars`, `active_app_chars`, plus the gating fields below. Provides the visibility the audit demanded.

### L6 — Universal low-information output guard
- `_is_low_information_output(text)` in [src/carter_v2/turn/_text.py](src/carter_v2/turn/_text.py) flags: empty, no-alphanumeric, single-character repetition (≥ 8 visible, ≤ 1 distinct alnum), or > 70% dominant non-alnum symbol. **Pure structural**: no banned vocab, language-neutral, applies equally to `"////"`, `"========"`, `"!!!!!!!!"`.
- The agent loop runs the guard on the final reply, retries once with a minimal prompt + `think=False`, and falls back to `"I could not produce a useful reply for that input."` if persistent. Trace fields: `low_information_detected`, `low_information_reason`, `raw_reply_excerpt`, `low_information_retry_used`, `low_information_recovered`, `termination_reason`.

### L7 — Per-call latency clamp
- New `set_call_timeout(timeout)` + `_effective_timeout` on `OpenAICompatAgentBackend` in [src/carter_v2/turn/backends.py](src/carter_v2/turn/backends.py); all three `urlopen` sites honor the override. Agent clamps to 20 s on trivial inputs and on `hint_no_tools` turns; reset to `None` in `_return_turn`. Stops the 154 s tail.

### L8 — Style preference scope
- `_format_memory_facts` now filters `style_preference` rows unless `source=user_stated_confirmed`, so a one-off "Que pasa chaval" never becomes a system instruction.

### L9 — Autonomy doc
- [LLM_AUTONOMY_BOUNDARY.md](LLM_AUTONOMY_BOUNDARY.md) — explicit list of what the LLM decides vs. what code decides.

---

## 3. Tests (L10)

52 new tests under [tests/turn/](tests/turn) covering each layer:

| File | Tests |
|------|-------|
| [test_user_ref_resolution.py](tests/turn/test_user_ref_resolution.py) | 7 |
| [test_memory_identity_validation.py](tests/turn/test_memory_identity_validation.py) | 7 |
| [test_active_app_context_gating.py](tests/turn/test_active_app_context_gating.py) | 13 |
| [test_prior_context_dedup.py](tests/turn/test_prior_context_dedup.py) | 4 |
| [test_low_information_reply_guard.py](tests/turn/test_low_information_reply_guard.py) | 18 |
| [test_prompt_hygiene_and_latency.py](tests/turn/test_prompt_hygiene_and_latency.py) | 3 |

**Full suite:** `python -m pytest -q` → **420 passed in 30.22s** (368 baseline + 52 new). No regressions.

---

## 4. Runtime probe (L11)

[audit/runners/llm_context_memory_probe.py](audit/runners/llm_context_memory_probe.py) replays the 13 user-reported cases (groups A–G) through `AgentEngine`. Two modes:

* `--mode real`  → live Ollama backend (qwen3:8b on 127.0.0.1:11434).
* `--mode scripted` → injects the historical bad LLM outputs (e.g. `////////////////////////////////////////`, identity drift) so the L1/L4/L6 guards can be observed intercepting them deterministically.

### Results (real, qwen3:8b)
[audit/results/LLM_CONTEXT_MEMORY_PROBE_REAL.json](audit/results/LLM_CONTEXT_MEMORY_PROBE_REAL.json) — **13/13 PASS**, `cases_failed=0/13`, exit 0.

| cid | prompt | total_ms | result |
|-----|--------|----------|--------|
| A1 | hola | 17 259 | PASS (model warm-up) |
| A2 | dime hola | 719 | PASS |
| B1 | Que? | 416 | PASS |
| B2 | Quien eres? | 1 580 | PASS, no `Como` leak |
| C1 | a | 419 | PASS, no `////` |
| D1 | ¿cuál es la capital de Francia? | 4 099 | PASS |
| E1 | Que pasa chaval | 1 318 | PASS, no style row written |
| E2 | ajajaj casi amigo | 1 004 | PASS |
| E3 | Nada | 396 | PASS (was 154 000 ms) |
| F1 | abre stean | 3 301 | PASS |
| F2 | abre steam | 1 726 | PASS |
| G1 | abre steam y luego ciérralo | 46 325 | PASS (real OS work) |
| G2 | que app está activa ahora? | 2 277 | PASS |

### Results (scripted)
[audit/results/LLM_CONTEXT_MEMORY_PROBE.json](audit/results/LLM_CONTEXT_MEMORY_PROBE.json) — **13/13 PASS**. Scripted run injects `"////////////////////////////////////////"` for case C1; the L6 guard detects and recovers (`low_information_retry_used=true`, `low_information_recovered=true`, `termination_reason="low_information_recovered"`).

---

## 5. Runtime failures reproduced from user log

For each user-reported failure: cause, fix, and after-state observed in the live probe.

| User report | Before | Root cause | Fix | After (live qwen3:8b) | Evidence |
|-------------|--------|------------|-----|-----------------------|----------|
| `hola` → repeated greeting | Identical assistant line echoed back | R4: no prior-turn dedup, no trivial-input suppression | L4 | First `hola` 17 s (warm), subsequent unique replies; `prior_turns_injected_count=0` on trivial input | A1, A2 in PROBE_REAL |
| `dime hola` → echo | Same as above | R4 | L4 | unique reply 719 ms | A2 |
| `Que?` → off-topic | R3 active-app leak | R3 | L3 | `active_app_context_injected=false` | B1 |
| `Quien eres?` → "soy Carter de Como" | Drift from `user.name` row containing past assistant text | R1, R2 | L1, L2 | resolver ignores conflicting/non-confirmed memory values; `user_ref_source` reflects provenance | B2 (no `Como` substring) |
| `a` → about `mission.py` | R3 leak on single-char input | R3 | L3 | `active_app_context_injected=false`, `prior_turns_injected_count=0`, 419 ms | C1 |
| App / web question → unrelated answer | R3 + R4 priming | R3, R4 | L3, L4 | clean answer 4 099 ms | D1 |
| `Que pasa chaval` → adopted as style | R1-class drift on `style_preference` | R1 (style variant) | L8 | `style_preference` row not propagated; `memory_must_not_have_attribute` check passes | E1 |
| `ajajaj casi amigo` → tone leak | Same | Same | L8 | clean 1 004 ms | E2 |
| `Nada` → 154 s wait + `////` | R5: no low-info guard, no latency clamp | R5 | L6 + L7 | 396 ms, no placeholder; guard would intercept if it returned | E3 (real) and C1 scripted |
| `abre stean` (typo) → wrong app | App resolver pre-existing | — | unchanged; gating means typo is not poisoned by prior context | F1 PASS | F1 |
| `abre steam` | — | — | — | 1 726 ms | F2 |
| `abre steam y luego ciérralo` (compound) | Mission ran but follow-ups got contaminated | R3, R4 | L3, L4 | 46 325 ms, follow-up `que app está activa ahora?` answered cleanly | G1, G2 |

---

## 6. Gates & validation

| Gate | Result |
|------|--------|
| `python -m pytest -q` | 420 passed in 30.22 s |
| `python audit/hardcode_guard.py` | 0 findings, 0 critical |
| `python audit/runners/llm_context_memory_probe.py --mode scripted` | 13/13 PASS, exit 0 |
| `python audit/runners/llm_context_memory_probe.py --mode real` | 13/13 PASS on qwen3:8b, exit 0 |
| Compound smoke (`audit/compound_smoke_runner.py`) | 2 pre-existing failures (`gui_step_observed_via_uia_or_unverified`, `uia_unavailable_falls_back_to_unverified`) confirmed via `git stash` to predate this work — not regressions of L1–L8. |

---

## 7. Files changed / added

**Modified**
- [src/carter_v2/turn/_system_prompt.py](src/carter_v2/turn/_system_prompt.py) — `UserRefDecision`, `resolve_user_ref`, source enums, memory-fact filtering.
- [src/carter_v2/turn/_text.py](src/carter_v2/turn/_text.py) — `_is_low_information_output`, `is_low_information_output`, `low_information_reason`.
- [src/carter_v2/session/memory.py](src/carter_v2/session/memory.py) — confirmed flag, list/delete helpers.
- [src/carter_v2/turn/agent.py](src/carter_v2/turn/agent.py) — gating, dedup, low-info guard, latency clamp, full L5 trace.
- [src/carter_v2/turn/backends.py](src/carter_v2/turn/backends.py) — per-call timeout override.

**Added**
- [scripts/maintenance/clean_corrupt_user_identity.py](scripts/maintenance/clean_corrupt_user_identity.py)
- [audit/runners/llm_context_memory_probe.py](audit/runners/llm_context_memory_probe.py)
- [audit/results/LLM_CONTEXT_MEMORY_PROBE.json](audit/results/LLM_CONTEXT_MEMORY_PROBE.json)
- [audit/results/LLM_CONTEXT_MEMORY_PROBE_REAL.json](audit/results/LLM_CONTEXT_MEMORY_PROBE_REAL.json)
- [LLM_CONTEXT_MEMORY_AUDIT.md](LLM_CONTEXT_MEMORY_AUDIT.md)
- [LLM_AUTONOMY_BOUNDARY.md](LLM_AUTONOMY_BOUNDARY.md)
- [tests/turn/test_user_ref_resolution.py](tests/turn/test_user_ref_resolution.py), [test_memory_identity_validation.py](tests/turn/test_memory_identity_validation.py), [test_active_app_context_gating.py](tests/turn/test_active_app_context_gating.py), [test_prior_context_dedup.py](tests/turn/test_prior_context_dedup.py), [test_low_information_reply_guard.py](tests/turn/test_low_information_reply_guard.py), [test_prompt_hygiene_and_latency.py](tests/turn/test_prompt_hygiene_and_latency.py)

---

## 8. Risks & follow-ups

* The 20 s clamp on trivial / `hint_no_tools` turns is intentionally tight; if a future tool legitimately needs more on a single-word user input, lift the clamp via mission state (`_should_inject_active_app_context` already provides the signal).
* `_format_prior_turn_context` dedup uses Jaccard 0.85 — empirically tuned on the user log. If the model ever produces deliberately echoing utility replies (e.g. confirming list membership), revisit the threshold via the existing `last_deduped_count` trace, which makes regressions observable.
* The L1 resolver currently treats `config.user_name` as ground truth. If a future config-injection vector exists, layer that validation in `resolve_user_ref` rather than at call sites.
* Memory cleanup script ([scripts/maintenance/clean_corrupt_user_identity.py](scripts/maintenance/clean_corrupt_user_identity.py)) defaults to dry-run; consider scheduling `--apply` once after first deploy to flush historical drift, then leaving it dry-run only.

---

## 9. Closure

All 15 closure conditions specified by the mission are satisfied:

1. Identity resolver ignores conflicting/non-confirmed memory ✅ (L1, B2 pass).
2. Memory writes shape-validated and source-tagged ✅ (L2).
3. Active-app context never leaks on trivial input ✅ (L3, A1/B1/C1/E3 traces).
4. Cleanup tooling exists, dry-run safe ✅ (L2 script).
5. Prior turns deduped + suppressed on trivial input ✅ (L4, A2 trace).
6. Prompt hygiene visible in trace ✅ (L5).
7. Universal low-info guard + recovery ✅ (L6, scripted C1).
8. Per-call latency clamp ✅ (L7, E3 = 396 ms).
9. Probe JSON written ✅ (real + scripted).
10. Style preference scoped to confirmed source ✅ (L8, E1).
11. Autonomy boundary documented ✅ (L9).
12. 52 new tests, all green ✅.
13. Full pytest 420/420 ✅.
14. `hardcode_guard` 0 critical ✅.
15. Final report (this document) ✅.
