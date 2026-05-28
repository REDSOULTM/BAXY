"""R1.2 sprint 2026-05-28: extract the execute phase from run_content into
Gemma4Agent._execute_turn.

After R1.1, run_content reads (post-F1):

    def run_content(...):
        _decision = self._decide_turn(...)
        if _decision.early_reply is not None:
            return _decision.early_reply
        turn_id = _decision.turn_id
        ... (8 unpacks) ...
        self.history.append(...)           # <-- EXECUTE PHASE BODY STARTS
        ...
        return AgentReply(...)             # <-- 4 returns total in execute

R1.2 moves the execute body (from `self.history.append({"role": "user"...})`
through the last `return AgentReply(...)` for max_turns/loop_aborted) into
`_execute_turn(self, content, decision, progress)`.

Every `return X` inside the execute body becomes the natural return of
_execute_turn (the function already returns AgentReply). run_content then
becomes a 12-line orchestrator.

This script is destructive on disk; commit before running.

Idempotency: if `_execute_turn` already exists, abort.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


AGENT_PY = Path("gemma4_agent/agent.py")


def main() -> int:
    src = AGENT_PY.read_text(encoding="utf-8").splitlines()
    # 1-indexed bookkeeping.

    # Guard: already extracted?
    for i, line in enumerate(src, start=1):
        if line.lstrip().startswith("def _execute_turn"):
            print(f"ABORT: _execute_turn already exists at line {i}")
            return 1

    # Locate run_content (the post-F1 version).
    run_content_idx = None
    for i, line in enumerate(src, start=1):
        if line.lstrip().startswith("def run_content"):
            run_content_idx = i
            break
    if run_content_idx is None:
        print("ABORT: cannot find def run_content")
        return 1

    # Locate the start of the execute body. After R1.1, the line just after
    # the 8 unpacks is `self.history.append({"role": "user", "content": _compact_live_content(content)})`.
    execute_start = None
    for i in range(run_content_idx, min(run_content_idx + 60, len(src))):
        if 'self.history.append({"role": "user", "content": _compact_live_content(content)})' in src[i - 1]:
            execute_start = i
            break
    if execute_start is None:
        print("ABORT: cannot find execute-body start (history.append user)")
        return 1

    # Locate the END of run_content (the closing return AgentReply for max_turns).
    # Walk forward from run_content_idx until we hit a line whose first 4 chars
    # are exactly "    " followed by "def " (= sibling method at class-level).
    execute_end = None
    for i in range(execute_start, len(src)):
        line = src[i - 1]
        if line.startswith("    def ") and "def run_content" not in line:
            execute_end = i - 1  # inclusive of the previous line (a blank or last return)
            break
    if execute_end is None:
        print("ABORT: cannot find run_content end (next def at class level)")
        return 1
    # Trim trailing blanks
    while execute_end > execute_start and src[execute_end - 1].strip() == "":
        execute_end -= 1

    print(f"run_content at line {run_content_idx}")
    print(f"execute body: lines {execute_start}..{execute_end} ({execute_end - execute_start + 1} LOC)")

    # ---------- Build _execute_turn ----------
    execute_body_lines = src[execute_start - 1: execute_end]
    # Inside the execute body, the locals `turn_id, mode, plan, raw_text_early,
    # pending_intent, selected_tool_names, semantic_fallback, selected_schemas`
    # are PROVIDED by the caller (run_content). Inside _execute_turn we receive
    # them as a TurnDecision and unpack at the top.

    method_lines = [
        "    def _execute_turn(self, content: str | list[dict[str, Any]], decision: TurnDecision, progress: ProgressCallback | None = None) -> AgentReply:",
        '        """R1 sprint 2026-05-28: execute phase of a turn.',
        "",
        "        Runs the LLM loop iteratively: chat() -> tool dispatch ->",
        "        feedback -> chat() ... up to max_agent_turns. Inside the loop",
        "        the assistant's reply is post-processed (verifiers, accessibility",
        "        nudges, mission outcome, footer); termination is by",
        "        max_turns/loop_aborted/LLM-said-stop. Returns the AgentReply",
        "        terminal of the turn.",
        '        """',
        "        turn_id = decision.turn_id",
        "        mode = decision.mode",
        "        plan = decision.plan",
        "        raw_text_early = decision.raw_text_early",
        "        pending_intent = decision.pending_intent",
        "        selected_tool_names = decision.selected_tool_names",
        "        semantic_fallback = decision.semantic_fallback",
        "        selected_schemas = decision.selected_schemas",
    ]
    method_lines.extend(execute_body_lines)
    method_lines.append("")

    # ---------- Build new run_content ----------
    # Lines 1..run_content_idx-1: unchanged.
    # run_content_idx..execute_start-1: the def + unpacks; keep as-is.
    # Replace execute_start..execute_end with a call to _execute_turn.
    new_lines: list[str] = []
    new_lines.extend(src[: execute_start - 1])
    new_lines.append("        # R1.2 sprint 2026-05-28: la fase execute vivía inline acá (LLM loop")
    new_lines.append("        # iterativo + tool dispatch + post-procesamiento). Extraída a")
    new_lines.append("        # _execute_turn que devuelve el AgentReply terminal del turno.")
    new_lines.append("        return self._execute_turn(content, _decision, progress)")
    # After execute_end, append the rest of the file.
    new_lines.extend(src[execute_end:])

    # Now insert _execute_turn BEFORE run_content.
    # Find run_content again in new_lines.
    new_rc_idx = None
    for i, line in enumerate(new_lines, start=1):
        if line.lstrip().startswith("def run_content"):
            new_rc_idx = i
            break
    if new_rc_idx is None:
        print("ABORT: lost run_content in new_lines")
        return 1
    final_lines: list[str] = []
    final_lines.extend(new_lines[: new_rc_idx - 1])
    final_lines.extend(method_lines)
    final_lines.extend(new_lines[new_rc_idx - 1:])

    AGENT_PY.write_text("\n".join(final_lines) + "\n", encoding="utf-8")
    print(f"OK: agent.py is now {len(final_lines)} lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
