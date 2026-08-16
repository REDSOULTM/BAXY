---
name: gui-visual-action
description: Click/type/select on a visible UI element with conditional logic. Use when user says "haz click/clickea/presiona/escribí/tipea/selecciona X", especially with conditions like "si está visible" or "si no ves no hagas click".
priority: high
---

# Visual GUI action with conditional execution

**Tools used**: `gui`.
**Honesty-critical**: yes — respect "if visible" negative conditions; never click after `locate(visible=False)`.

The user wants to interact with a visible element on screen. The KEY is the
implicit (or explicit) condition: "si está visible, hacelo. Si no, NO."
Carter must respect the negative condition — that's V3 (honesty) and V20
(distinguir conversación vs acción).

## Chain

1. `gui(action="screenshot")` — always see the screen first.
2. `gui(action="check_blockers", screenshot_path="<latest>")` — modal/dialog? if yes, report and stop unless the user told you to handle it.
3. `gui(action="locate", target_description="<element described by user>")` — try to find it.
4. Branch:
   - If `visible=True`:
     - For click → `gui(action="click", x=..., y=...)` then `gui(action="screenshot")` to verify frame changed.
     - For type → click first if focus unclear, then `gui(action="type", value="<text>")`.
     - For keypress → `gui(action="keypress", keys="<combo>")`.
   - If `visible=False`:
     - If user said "si lo ves" / "si está visible" → REPORT honestly: "No encontré <X>. No hice click."
     - If user did NOT add a condition → can retry locate once with rephrased description, but STOP after that. Don't blind-click.

## Honesty rules (NEVER violate)

- If `gui(locate)` says `visible=False` → DO NOT click. Period.
- After any click/type, verify via `frame_diff > 0` (the verifier emits this). If `frame_diff = 0`, the action had no effect — report it.
- "Selecciona todo" → use `gui(keypress, keys="ctrl+a")` instead of mouse-based selection (more reliable).
- If user said "si no ves, no hagas click" → respect the negative; STOP without clicking.

## Loop prevention

- Max 8 tool calls.
- If 3+ consecutive `gui(locate)` return `visible=False` → STOP and report.
- If click executed but `frame_diff=0` for 2 consecutive clicks → STOP, the UI isn't responding.

## Examples

User: "haz click en el botón Aceptar si está visible"
→ screenshot, check_blockers, locate("botón Aceptar"). If visible → click + verify. If not → report no-action.

User: "si no ves el botón Aceptar, no hagas click"
→ screenshot, locate. If `visible=False` → "No encontré el botón Aceptar. No hice click." Done.

User: "abre Notepad y escribí 'hola'"
→ This is a 2-step mission: first `app(action="open", name="notepad")`, then run this skill for typing. After Notepad opens, screenshot → check focus → `gui(type, value="hola")` → verify frame_diff > 0.

User: "selecciona todo el texto en Notepad"
→ Assume Notepad has focus, `gui(keypress, keys="ctrl+a")`. Verify with screenshot.
