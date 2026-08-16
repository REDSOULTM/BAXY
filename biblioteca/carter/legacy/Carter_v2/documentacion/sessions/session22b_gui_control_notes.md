# Session 22B - Local Safe Computer Use Notes

## Architecture

Carter now has a local universal computer-use layer in `src/carter_v2/universal/computer_use.py`.

The execution hierarchy remains unchanged:

1. Structured tool if one exists.
2. Structured tool with resolved resource evidence when enough.
3. Local visual GUI fallback when explicitly enabled for the universal runner.

The GUI layer does not replace existing capabilities. `LocalGuiActor` dispatches through the existing registry/tool surface for mouse, keyboard, focus, and scroll actions. Tests use `NoopGuiActor` to validate policy and checkpoint behavior without moving the live desktop.

## Observe -> Act -> Verify -> Resume

The visual loop is represented by:

- `VisualObservation`: timestamped screen/window/region state with safe summary.
- `VisualElement`: visible controls with kind, bounds, confidence, state, and risk context.
- `VisualActionTarget`: structured target selected from visual/resource evidence.
- `GuiAction`: explicit mouse/keyboard/wait/focus action.
- `GuiActionResult`: before/after observations, risk level, policy state, verification detail.
- `VisualRunState`: node-level visual state used by the universal runner and checkpoints.

`VisualGuiRunner.run_action()` performs:

1. observe before
2. classify risk
3. handle secret handoff if needed
4. request approval for high-risk actions
5. execute through actor
6. observe after
7. return structured verification

`PlanGraphRunner` can use GUI fallback for nodes with no viable structured tool when `allow_gui_fallback=True`. Fallback results are normal `PlanNodeResult` entries with `tool_name="gui_fallback"`, visual summary, resolved resources, and waiting states.

## Risk Policy

Risk classification is structural, not language-based:

- `LOW_RISK`: navigation, focus, scroll, wait, simple click on normal target.
- `MEDIUM_RISK`: typing and drag/drop in normal context.
- `HIGH_RISK`: destructive, account, administrative, credential, purchase, publish, upload, or send contexts.
- `BLOCKED`: bypass, exfiltration, hidden persistence, password reading, secret scraping, or evasion contexts.

High-risk actions require an approval callback. Blocked actions return a structured blocked result and do not execute.

## SecretHandoff

Secrets are handled by `SecretHandoff`.

Behavior:

- a secret-dependent action pauses if no secret is provided
- a provided secret is consumed for the action
- checkpoint serialization writes `[SECRET_REDACTED]`
- safe summaries redact secret-labeled fields and elements
- no durable memory/skill promotion is performed from secret content

## UX Inspection

The `/tasks` list now includes compact GUI metadata when present:

- `gui=<count>`
- `awaiting_secret_input`
- `awaiting_user_confirmation`
- `visual=<summary>`

Checkpoint summaries also expose GUI action counts and waiting states for resume/debugging.

## Probes

`probe_all_tools.py` includes:

- `S22B-GUI-1`: structured visual observation and low-risk click with before/after evidence.
- `S22B-GUI-2`: visible edit verified by visual before/after.
- `S22B-GUI-3`: multi-step scroll and selection.
- `S22B-GUI-4`: GUI fallback checkpoint and resume without replay.
- `S22B-GUI-5`: high-risk action requests approval instead of executing.
- `S22B-GUI-6`: SecretHandoff uses a secret without plaintext checkpoint persistence.

The probes are intentionally safe: they exercise the Carter computer-use framework with synthetic visual observations and a no-op actor. The live execution path remains wired through existing input/window capabilities via `LocalGuiActor`.

## Boundaries

No voice, webcam, camera stream, hidden operation, security bypass, product dictionary, app hack, language branch, filesystem crawling, or URL guessing was added.

Within this scope, no unresolved core S22B implementation item remains.
