"""R1.3 sprint 2026-05-28: extract the post-LLM-no-tool-calls finalize block
from _execute_turn into Gemma4Agent._finalize_turn.

Inside _execute_turn, when the LLM returns without tool calls
(`if not raw_tool_calls:` at line ~2114), the code runs ~500 LOC of
post-processing: verifiers, accessibility nudges, mission outcome,
screen-description fallback, footer building, then returns AgentReply.

That block contains ONE `continue` (line 2231) that belongs to the outer
`for _turn` loop in _execute_turn. To preserve semantics we model the
finalize return as `AgentReply | _FinalizeContinue` (a sentinel singleton),
and the caller turns the sentinel into a `continue`.

The max_turns/loop_aborted finalize at the very END of _execute_turn
stays inline — it's only ~25 LOC.

This script is destructive on disk; commit before running.
Idempotency: if `_finalize_turn` already exists, abort.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


AGENT_PY = Path("gemma4_agent/agent.py")
SENTINEL_NAME = "_FINALIZE_CONTINUE"


def main() -> int:
    src = AGENT_PY.read_text(encoding="utf-8").splitlines()

    # Guard.
    for i, line in enumerate(src, start=1):
        if line.lstrip().startswith("def _finalize_turn"):
            print(f"ABORT: _finalize_turn already exists at line {i}")
            return 1

    # Locate the `if not raw_tool_calls:` line.
    finalize_start = None
    for i, line in enumerate(src, start=1):
        if line.strip() == "if not raw_tool_calls:":
            finalize_start = i
            break
    if finalize_start is None:
        print("ABORT: cannot find `if not raw_tool_calls:`")
        return 1

    # Locate the `return AgentReply(content=assistant_content, ...)` ending it.
    finalize_end = None
    for i in range(finalize_start, len(src)):
        line = src[i - 1]
        if "return AgentReply(content=assistant_content, tool_events=events, mission=mission)" in line:
            finalize_end = i
            break
    if finalize_end is None:
        print("ABORT: cannot find finalize return")
        return 1

    print(f"if-block at line {finalize_start}")
    print(f"finalize body: lines {finalize_start + 1}..{finalize_end}")

    # Dedent the body from depth 16 to depth 8.
    finalize_body_lines = src[finalize_start: finalize_end]
    dedented: list[str] = []
    continue_count = 0
    for line in finalize_body_lines:
        if line.startswith("                "):  # 16 spaces
            stripped = line[8:]
        elif line.strip() == "":
            stripped = ""
        else:
            print(f"WARN: unexpected indent: {line!r}")
            stripped = line
        # Replace `continue` with `return _FINALIZE_CONTINUE`.
        if stripped.strip() == "continue  # re-prompt en la próxima iteración del for _turn":
            indent = stripped[: len(stripped) - len(stripped.lstrip())]
            stripped = f"{indent}return {SENTINEL_NAME}"
            continue_count += 1
        elif stripped.strip().startswith("continue"):
            print(f"WARN: unmapped continue: {stripped!r}")
        dedented.append(stripped)

    if continue_count != 1:
        print(f"ABORT: expected 1 continue, found {continue_count}")
        return 1

    method_lines = [
        "    def _finalize_turn(",
        "        self,",
        "        content: str | list[dict[str, Any]],",
        "        assistant_content: str,",
        "        events: list[ToolEvent],",
        "        mission: dict[str, Any] | None,",
        "        msg: dict[str, Any],",
        "        raw_text_early: str,",
        "        turn_id: str,",
        "        verifier_outcomes: list,",
        "        mission_goal: Any,",
        '    ) -> "AgentReply | _FinalizeContinue":',
        '        """R1 sprint 2026-05-28: finalize phase of a turn.',
        "",
        "        Runs ONLY when the LLM finished without emitting a tool call",
        "        (the natural success path). Applies post-processing:",
        "        accessibility nudges, mission outcome, verifier footer,",
        "        screen-description fallback, proactive suffix.",
        "",
        "        Returns the terminal AgentReply, OR _FINALIZE_CONTINUE if",
        "        the a11y nudge re-prompted (the caller must `continue` its",
        "        outer for _turn loop).",
        '        """',
    ]
    method_lines.extend(dedented)
    method_lines.append("")

    # Call site replacement at the `if not raw_tool_calls:` body.
    new_lines: list[str] = []
    new_lines.extend(src[: finalize_start])  # up to and including the `if`
    new_lines.append("                # R1.3 sprint 2026-05-28: finalize (~500 LOC de post-procesamiento")
    new_lines.append("                # del reply sin tool calls) extraída a _finalize_turn. Devuelve")
    new_lines.append("                # AgentReply o el sentinel _FINALIZE_CONTINUE (que el caller")
    new_lines.append("                # traduce a `continue` del for _turn).")
    new_lines.append("                _fin_result = self._finalize_turn(")
    new_lines.append("                    content, assistant_content, events, mission, msg,")
    new_lines.append("                    raw_text_early, turn_id, verifier_outcomes, mission_goal,")
    new_lines.append("                )")
    new_lines.append("                if _fin_result is _FINALIZE_CONTINUE:")
    new_lines.append("                    continue")
    new_lines.append("                return _fin_result")
    new_lines.extend(src[finalize_end:])

    # Insert _finalize_turn BEFORE run_content.
    rc_idx = None
    for i, line in enumerate(new_lines, start=1):
        if line.lstrip().startswith("def run_content"):
            rc_idx = i
            break
    if rc_idx is None:
        print("ABORT: lost run_content")
        return 1
    final_lines: list[str] = []
    final_lines.extend(new_lines[: rc_idx - 1])
    final_lines.extend(method_lines)
    final_lines.extend(new_lines[rc_idx - 1:])

    # Add the sentinel singleton + class definition near the top of the file.
    # Inject just after the existing AgentReply dataclass (line ~158).
    insert_idx = None
    for i, line in enumerate(final_lines, start=1):
        if line.rstrip() == "class Gemma4Agent:":
            insert_idx = i - 1  # right before class
            break
    if insert_idx is None:
        print("ABORT: cannot find class Gemma4Agent")
        return 1
    sentinel_block = [
        "class _FinalizeContinue:",
        '    """Sentinel returned by Gemma4Agent._finalize_turn when the a11y',
        "    nudge re-prompted the LLM and the caller must `continue` its",
        "    outer for _turn loop. Single instance: _FINALIZE_CONTINUE.",
        "",
        "    R1 sprint 2026-05-28.",
        '    """',
        "    __slots__ = ()",
        "",
        "",
        "_FINALIZE_CONTINUE = _FinalizeContinue()",
        "",
        "",
    ]
    final_lines = final_lines[:insert_idx] + sentinel_block + final_lines[insert_idx:]

    AGENT_PY.write_text("\n".join(final_lines) + "\n", encoding="utf-8")
    print(f"OK: agent.py is now {len(final_lines)} lines; 1 continue mapped to sentinel")
    return 0


if __name__ == "__main__":
    sys.exit(main())
