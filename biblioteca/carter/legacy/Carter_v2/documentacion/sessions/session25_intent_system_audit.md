# Session 25 - Intent System Audit

## Scope

Repo: `Carter_v2/`  
Branch observed: `rebuild/v2-from-scratch`

Voice and camera remain out of scope. This audit covers the live text/tool loop, universal runner integration, GUI fallback continuity, and probe/test coverage for compound intent handling.

## Pipeline Real

`user input -> AgentEngine.run -> system/context prompt -> backend.chat_with_tools -> tool call normalization/dispatch -> capability execution -> ledger + verification -> direct action shortcut decision -> continue / final reply / universal runner`

Relevant implementation points:

| Stage | Evidence |
| --- | --- |
| User input enters backend unchanged | `AgentEngine.run`, `tests/test_agent_intent_continuity.py::test_full_user_input_reaches_backend_without_truncation` |
| Tool schemas exposed from registry | `adapters/tools.py`, `tool_schemas_for_llm` |
| Tool calls normalized and executed | `turn/agent.py`, `dispatch_tool_call`, `tests/test_tool_normalizer.py` |
| Verification/caveats added after execution | `turn/verification.py`, `AgentEngine.run` post-tool block |
| Direct action closure decision | `turn/agent.py` calls `evaluate_direct_action_closure` |
| Structured intent state | `turn/intent_resolution.py` |
| Universal escalation remains available | `AgentEngine._try_universal_frame_text`, universal tests |
| GUI fallback continuity remains covered | `tests/test_computer_use.py`, S25 GUI continuity probe |

## Estado Actual Real

| Area | Estado | Evidencia | Acción S25 |
| --- | --- | --- | --- |
| input delivery to backend | DONE | New input preservation test | No product fix needed |
| direct action closure semantics | PARTIAL -> DONE | Previous S23 list-based prep handling was too narrow | Replaced with metadata-based `IntentResolution` |
| compound intent continuity | PARTIAL -> DONE | Write-then-read probe originally stopped after write | Mutating terminal steps now return to LLM for satisfaction check |
| global-goal satisfaction logic | PARTIAL -> DONE | `ok=True` was enough for direct reply in some paths | Closure now distinguishes substep/environment/progress/global states |
| tool prioritization | PARTIAL -> DONE | Outcome tools needed metadata clarity | Added role classification tests and kept Steam local/store descriptions distinct |
| ambiguity handling | PARTIAL -> DONE | No explicit ambiguity state existed | `IntentFrame` carries ambiguity/dependency fields; tests cover resolvable vs real ambiguity |
| universal runner escalation | DONE | S21/S25 probes use TaskFrame and checkpointed multi-step execution | Added S25 universal intent probe |
| GUI fallback continuity | DONE | S22B existed; S25 verifies prep GUI step does not close | Added S25 GUI continuity probe |
| verification-aware closure | DONE | S25 unverified probe checks caveat path | No premature success assertion |
| approval/secret-aware continuation | DONE | S22B computer-use tests remain passing in full suite | No change |

## Causa Raiz Por Subproblema

| Subproblema | Causa raiz | Corrección |
| --- | --- | --- |
| Corte prematuro del turno | `direct_action_reply` collapsed successful tool results into final replies without a structured global-satisfaction decision | Introduced `evaluate_direct_action_closure` and continuation prompt |
| Pérdida del objetivo global | The original user objective was not attached to post-tool closure decisions | `IntentFrame` persists `requested_outcome` through the turn |
| Elección subóptima de tool | The loop could accept the first tool result as enough even when it only enabled the actual outcome | Preparatory/intermediate/verification roles cannot close directly |
| Colapso al primer verbo | Open/focus/launch/read/verify/mutate were not separated semantically | Tool roles are classified from tool metadata (`capability`, `action`) |
| Ambigüedad mal resuelta | No explicit distinction between resolvable ambiguity and missing target | Added ambiguity tests; `hint_no_tools` clarification path no longer gets overwritten by tool guard |
| Preparar/leer/verificar/actuar/responder mezclados | `ok=True` was treated too close to global success | Closure now separates `tool_succeeded`, `environment_prepared`, `verification_completed`, `substep_completed`, and `global_goal_satisfied` |

## Evidencia Reproducible

| Case | Evidence |
| --- | --- |
| Full input reaches backend | `tests/test_agent_intent_continuity.py::test_full_user_input_reaches_backend_without_truncation` |
| Open/prep does not close compound request | `test_compound_request_continues_after_preparatory_direct_action` |
| File read result returns to LLM before summary | `test_intermediate_tool_result_returns_to_llm_before_final_answer` |
| Terminal simple action still closes | `test_terminal_direct_action_still_closes_without_extra_llm_call` |
| Mutating write then verify does not stop after write | `S25-INTENT-4` |
| Universal runner handles complex artifact intent | `S25-INTENT-6` |
| GUI focus preparation does not close | `S25-INTENT-7` |
| Real ambiguity asks for minimal clarification | `S25-INTENT-9` |
| Unverified preparation does not assert success | `S25-INTENT-10` |

## No Tocado

The following remain unrelated to S25 and were not used as implementation inputs: historical probes, generated readiness files, binary probe assets, session prompts, personal notes, archives, `.claude` settings, GPU helper scripts, and untracked legacy tests unrelated to intent continuity.

## Guardrails

- No app/product dictionaries added.
- No language-specific branching added.
- No filesystem crawling added.
- No URL guessing added.
- No public tool names changed.
- No capability interfaces changed.
- Voice/camera untouched.
