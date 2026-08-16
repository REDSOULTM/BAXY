# Session 23 - LLM Input Flow Diagnosis

## Problem

User request:

```text
Abre steam y busca el juego "Batman Arkham Asylum" en mi biblioteca
```

Observed response before the fix:

```text
Steam ya está corriendo.
```

This looked like the model did not understand the complete user input.

## Actual Data Flow

The full user text reaches `AgentEngine.run()` unchanged.

The turn builds:

1. system prompt
2. injected runtime/universal/memory context
3. one user message containing the original user text
4. tool schema catalog

The LLM then returns tool calls. For the failing request, the real reproduction showed:

```text
tool_calls = ["steam_open_client"]
tool_result = "Steam ya está corriendo."
```

So the model did receive the input. The failure was not input truncation.

## Root Cause

After executing a tool, Carter checks whether the tool is in `DIRECT_ACTION_TOOL_NAMES`.

Before this fix, `steam_open_client`, `app_open`, and similar preparatory actions could trigger this branch:

```python
direct_reply = _direct_action_reply(executed_this_iteration)
if direct_reply is not None and not unverified_this_iteration and not caveat:
    return AgentTurnResult(...)
```

That branch is correct for simple terminal actions like:

```text
abre steam
```

But it is wrong for compound requests:

```text
abre steam y busca X
abre una app y haz Y
abre un navegador y navega a Z
```

The first tool may only satisfy a preparatory step. Returning immediately prevents the LLM from seeing the tool result and choosing the next tool.

## Fix

Added `PREPARATORY_DIRECT_ACTION_TOOL_NAMES`.

Tools in this set do not close the turn automatically:

- `app_open`
- `process_start_app`
- `steam_open_client`
- `window_focus`
- `web_open_url`
- `web_navigate`

When one of these tools succeeds, Carter appends a structured continuation prompt:

```text
The previous tool result may only satisfy a preparatory step. Re-read the original user request and the tool result. If any requested outcome remains incomplete, continue with the appropriate tool calls. If the full request is complete, answer concisely in the user's language.
```

This is structural, not language-specific:

- no Spanish/English regex
- no app dictionary
- no product-to-app mapping
- no filesystem crawling
- no URL guessing

## Reproduction After Fix

Same request:

```text
Abre steam y busca el juego "Batman Arkham Asylum" en mi biblioteca
```

Observed tool sequence after the fix:

```text
tool_calls = ["steam_open_client", "steam_search"]
```

Observed reply:

```text
El juego "Batman: Arkham Asylum" no está instalado en tu biblioteca. ¿Quieres instalarlo?
```

The loop now continues after opening Steam. The remaining imperfection is routing preference: the model chose `steam_search` instead of the more local `steam_is_installed`. Tool descriptions were tightened to distinguish local library checks from Store catalog search.

## Tests Added/Updated

Added:

- compound Steam request must continue after `steam_open_client`
- preparatory `app_open` gets a final LLM pass instead of direct return

Updated:

- old tests that expected immediate direct return after app open now expect one final LLM pass

## Current Contract

Simple commands still work, but preparatory actions no longer claim the entire request is complete by themselves.

This makes Carter safer for multi-step natural instructions without relying on language hardcodes.
