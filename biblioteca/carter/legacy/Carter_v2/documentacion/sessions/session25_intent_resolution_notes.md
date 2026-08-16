# Session 25 - Intent Resolution Notes

## Resumen

S25 closes the remaining compound-intent failure class in the agent loop. The fix is not app-specific: the loop now decides whether a direct tool result may close the turn by using structured execution state and tool metadata, not product names, language keywords, or a list of apps.

## Causa Raiz

The input was reaching the backend correctly. The bug was after tool execution: a successful direct action could be turned into the final answer before Carter had checked whether that tool result satisfied the user's global request.

This affected preparation and substeps:

- open/focus/launch could be treated as final work
- read/verify/inspect could be reported without giving the LLM a final synthesis pass
- mutations such as write/create could close before requested verification
- unverified tool success could sound like global success

## Implementación

| File | Change |
| --- | --- |
| `src/carter_v2/turn/intent_resolution.py` | Added `IntentFrame`, `IntentStep`, `IntentResolution`, role classification, and closure evaluation |
| `src/carter_v2/turn/agent.py` | Replaced raw direct-action shortcut closure with `evaluate_direct_action_closure` |
| `src/carter_v2/adapters/tools.py` | Exposed `tool_definition` for metadata-based role classification; preserved Steam local/store compact distinction |
| `tests/test_agent_intent_continuity.py` | Covers input delivery, continuation after prep, intermediate LLM pass, terminal simple close, GUI prep continuity |
| `tests/test_direct_action_closure.py` | Covers direct terminal/preparatory/verification/caveat closure semantics |
| `tests/test_intent_decomposition.py` | Covers intent frame and tool-role metadata classification |
| `tests/test_tool_prioritization.py` | Covers outcome-aligned roles and Steam local/store disambiguation |
| `tests/test_ambiguity_resolution.py` | Covers resolvable ambiguity and minimal clarification |
| `probe_all_tools.py` | Added S25 probes for real LLM and controlled AgentEngine continuity cases |

## Criterios Nuevos

The loop distinguishes:

- `tool_succeeded`
- `substep_completed`
- `environment_prepared`
- `intermediate_progress`
- `verification_completed`
- `global_goal_satisfied`
- `global_goal_not_yet_satisfied`
- `awaiting_user_input`
- `awaiting_secret`
- `awaiting_approval`
- `needs_replan`
- `escalate_to_universal_runner`

Direct closure is only allowed when the executed step is a self-contained terminal answer, such as clock/time or atomic input hotkeys. Preparatory, intermediate, verification, and mutating terminal substeps are returned to the LLM with an `INTENT_CONTINUITY_CHECK` prompt so the model can either continue tool-calling or explicitly finish.

## Por Qué Es General

The decision uses `ToolDefinition.capability` and `ToolDefinition.action`. It does not inspect brand names, app names, localized phrases, or product dictionaries. Steam, files, GUI, and universal-runner cases are covered because they share the same semantic states: prepare, observe/read, verify, mutate, and deliver.

## Evidencia de Tests

- `tests/test_agent_intent_continuity.py`: 6 passed
- `tests/test_direct_action_closure.py`: 4 passed
- `tests/test_intent_decomposition.py`: 3 passed
- `tests/test_tool_prioritization.py`: 3 passed
- `tests/test_ambiguity_resolution.py`: 3 passed
- Required existing suites passed individually.
- Full suite: `1246 passed, 3 warnings`

Warnings are dependency/environment warnings from existing embedding/torchvision imports, not S25 regressions.

## Evidencia de Probes

`probe_session25_results.json`:

- total: 10
- passed: 10
- failed: 0
- errors: 0
- skipped: 0

Coverage:

- LLM real read/summarize intent
- LLM real verification request
- LLM real folder analysis
- LLM real write-then-read verification
- LLM real simple terminal time request
- LLM real universal TaskFrame artifact flow
- controlled GUI focus/read continuity
- LLM real explicit-resource ambiguity resolution
- controlled real ambiguity clarification
- controlled unverified-preparation caveat

## Pendiente Real Dentro Del Scope

None. Voice and camera remain explicitly out of scope by user instruction.
