# LLM Autonomy Boundary — Carter v2

This document records what the **LLM decides** vs what the **code decides**
in Carter v2 after the L1–L8 fixes. The split is deliberate: the LLM is
the only component that understands natural language; the code is the only
component that can guarantee safety, verification, and honest output.

## What the LLM decides

The LLM is the sole authority on:

- intent disambiguation across languages and phrasings;
- which tool from the per-turn catalog best fits the user's request;
- the conversational vs action distinction at the boundary cases the
  brain router cannot pre-classify;
- when to ask the user for clarification;
- when to apply a session style preference (the prompt presents it as
  optional context, never as a content requirement);
- summarising tool output back to the user in the user's language.

The LLM receives **only structured signals**:
- the per-turn tool catalog (descriptions are the routing rules);
- a clean system prompt with verified user_ref;
- KNOWN FACTS that have passed the read-side filters (no unconfirmed
  user.name, no auto-injected style preferences);
- mission state (when active);
- de-duplicated, length-bounded prior context;
- active-app context only when structurally relevant.

## What the code decides

The code is the sole authority on:

| Concern | Mechanism |
|---|---|
| Identity priority | `resolve_user_ref(config, memory, os_username)` with confidence + conflict detection |
| Memory write filters | structural validators in `set_user_name`; source enum (`user_stated` vs `user_stated_confirmed`) |
| Style preference scoping | `_format_memory_facts` filters `attribute='style_preference'` unless `source=user_stated_confirmed` |
| Active-app context injection | `_should_inject_active_app_context()` — trivial input never receives it |
| Prior turn dedup | structural Jaccard ≥ 0.85 on token sets |
| Prior turn suppression | `_is_trivially_short_input` gates the whole block |
| Low-information output | `is_low_information_output()` — diversity + dominant-symbol structural test |
| Latency clamps | `set_call_timeout(20s)` for trivial / no-tools turns |
| Mission verification | `MissionVerifier`, `MissionVerifier.verify`, `format_mission_reply` |
| Honest-fail banners | `ledger.format_failure`, `format_mission_reply` (English structural banners) |
| Loop detection | `_consecutive_same_call`, `_loop_detection_message` |
| Policy gates | `session/policy.enforce_policy` |
| Verification | `VerificationManager.verify`, `PerceptionMonitor` |

## What must NEVER move into the code

- vocabulary lists (verbs, connectors, greetings, names, stopwords) for any
  language;
- per-app branches (`if app == "Steam":`);
- per-locale branches that change semantics;
- regex that captures human intent ("I am called X", "remember that …");
- forced replies based on heuristic detection of conversational vs action.

## What must NEVER move into the LLM

- safety / risk classification of tools;
- the decision to skip verification;
- the decision to claim a PC action succeeded;
- writing facts to durable memory without validation;
- silently overriding user_ref with memory.

## Guardrails added in this round

- `resolve_user_ref` returns a structured `UserRefDecision` with
  `ignored_memory_values`, `conflict_detected`, `confidence`, `reason`.
- The system prompt cache is keyed on the resolved user_ref so a memory
  flip invalidates immediately without leaking prior contamination.
- All trace fields (`active_app_context_injected`,
  `prior_turns_deduped_count`, `low_information_detected`,
  `user_ref_source`, `suspicious_user_ref_ignored`, …) are emitted on
  every turn for runtime probes.
- Low-information detection is universal (any single-char repetition >
  70%, any dominant non-alphanumeric symbol, any pure-decoration line);
  the retry uses a minimal prompt with `think=False` and exits with a
  structural honest reply if it persists.
- Style preferences default to non-injection unless explicitly confirmed.
