# Carter v2 - Session 15 Migration Notes

## Criterio

The legacy loop remains the default executor for ordinary conversation and direct single-tool actions. The universal runner is used when the model produces a structured `TaskFrame` whose shape shows that a resumable plan adds value.

The selector is structure-based:

- multiple work units
- explicit dependencies
- success criteria
- mutation work units or mutation scope
- multiple structured requirements

It does not use localized keyword branches, app-brand shortcuts, or regex intent rules.

## Casos migrados al carril universal

- Multi-step `TaskFrame` responses emitted by the normal LLM turn.
- App-building style tasks represented as multiple work units with artifacts and verification.
- Data transformation tasks that create sandbox artifacts and then verify them.
- Resumed long-running runs through existing `/resume` plus richer checkpoint state.
- Missing-capability tasks, which now fail as blocked plan nodes instead of inventing a tool.

## Casos dejados en legacy

- Conversation-only turns.
- Simple direct tool calls such as open app, get system information, read a file, or run one command.
- Textual tool-call recovery for Qwen-style malformed tool calls.
- Existing deterministic normalizer corrections backed by evidence from `ResourceResolver`.

## Riesgos evitados

- No replacement of existing tools/capabilities.
- No extra preflight LLM call on every turn; auto universal routing only reacts to structured `TaskFrame` output from the normal lane.
- No broad mutation bypass. Universal runner still dispatches through the same tool registry and event bus hooks.
- No new voice, camera, or screen-vision surface.
