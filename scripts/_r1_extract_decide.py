"""R1 sprint 2026-05-28: extract Gemma4Agent.run_content decide phase
(lines 814-1596) into Gemma4Agent._decide_turn returning a TurnDecision.

This is the mechanical extraction step:
  1. Read agent.py.
  2. Find run_content (def signature: line 814).
  3. The decide phase is run_content body line 815..1596 inclusive.
  4. Insert `def _decide_turn(self, content, progress) -> TurnDecision:` just
     BEFORE `def run_content`, with body = lines 815..1596 indented +0
     (already 8-space-indented; keep as-is), but with every `return X`
     rewritten as `return TurnDecision(early_reply=X)`. The natural
     fall-through at the end of the function becomes
     `return TurnDecision(turn_id=..., mode=..., ...)`.
  5. Replace lines 815..1596 of run_content with:
        _decision = self._decide_turn(content, progress)
        if _decision.early_reply is not None:
            return _decision.early_reply
        turn_id = _decision.turn_id
        mode = _decision.mode
        plan = _decision.plan
        raw_text_early = _decision.raw_text_early
        pending_intent = _decision.pending_intent
        selected_tool_names = _decision.selected_tool_names
        semantic_fallback = _decision.semantic_fallback
        selected_schemas = _decision.selected_schemas

This script is destructive on disk; commit before running.

Idempotency: if `_decide_turn` already exists, abort (it's already extracted).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


AGENT_PY = Path("gemma4_agent/agent.py")
DECIDE_START_LINE = 815  # first line of the body (after `def run_content:`)
DECIDE_END_LINE = 1596   # last line of decide (the `self._compact_completed_history()` call is at 1596)
RUN_CONTENT_LINE = 814   # `def run_content(self, ...)`


REPLACEMENT_BLOCK = """        # R1 sprint 2026-05-28: la fase decide vivía inline acá (LOC 815-1596,
        # ~782 LOC). Extraída a _decide_turn. early_reply propaga los 4 caminos
        # cortos (jarvis-pending, multi-intent re-dispatch, reply-shortcut,
        # explicit-plan-only). Los 8 campos restantes son las locales que
        # cruzan la frontera decide → execute/finalize (mapeo AST verificó
        # que no hay más).
        _decision = self._decide_turn(content, progress)
        if _decision.early_reply is not None:
            return _decision.early_reply
        turn_id = _decision.turn_id
        mode = _decision.mode
        plan = _decision.plan
        raw_text_early = _decision.raw_text_early
        pending_intent = _decision.pending_intent
        selected_tool_names = _decision.selected_tool_names
        semantic_fallback = _decision.semantic_fallback
        selected_schemas = _decision.selected_schemas
"""


# Patterns: `return EXPRESSION` (already at depth >= 12 inside the method).
# Returns we need to wrap (4 of them, per the audit):
#   853: return _jarvis_reply
#   901: return self._run_multi_intent(_clauses, progress=progress)
#   930: return AgentReply(...)
#  1129: return AgentReply(...)
# We rewrite every `return X` where X is NOT already a TurnDecision call.
RETURN_RE = re.compile(r"^(?P<indent>\s+)return (?P<expr>(?!TurnDecision\b)[^\n]+)$")


def main() -> int:
    src = AGENT_PY.read_text(encoding="utf-8").splitlines(keepends=False)

    # Guard: already extracted?
    for i, line in enumerate(src, start=1):
        if line.lstrip().startswith("def _decide_turn"):
            print(f"ABORT: _decide_turn already exists at line {i}")
            return 1

    # Sanity: line content checks.
    expected_run_content_pattern = "def run_content"
    if expected_run_content_pattern not in src[RUN_CONTENT_LINE - 1]:
        print(f"ABORT: line {RUN_CONTENT_LINE} does not contain `def run_content`")
        print(f"   actual: {src[RUN_CONTENT_LINE - 1]!r}")
        return 1
    # Line DECIDE_START_LINE must be self._turn_counter += 1 (first body line).
    if "self._turn_counter += 1" not in src[DECIDE_START_LINE - 1]:
        print(f"ABORT: line {DECIDE_START_LINE} is not the expected first body line")
        print(f"   actual: {src[DECIDE_START_LINE - 1]!r}")
        return 1
    # Line DECIDE_END_LINE must be the _compact_completed_history call.
    if "_compact_completed_history" not in src[DECIDE_END_LINE - 1]:
        print(f"ABORT: line {DECIDE_END_LINE} is not the expected last decide line")
        print(f"   actual: {src[DECIDE_END_LINE - 1]!r}")
        return 1

    # ---------- Build _decide_turn body ----------
    # Source lines 815..1596 (1-indexed), slice [814:1596] in 0-indexed.
    decide_body_lines = src[DECIDE_START_LINE - 1: DECIDE_END_LINE]
    rewritten: list[str] = []
    rewrite_count = 0
    for line in decide_body_lines:
        m = RETURN_RE.match(line)
        if m:
            indent = m.group("indent")
            expr = m.group("expr").rstrip()
            rewritten.append(f"{indent}return TurnDecision(early_reply={expr})")
            rewrite_count += 1
        else:
            rewritten.append(line)
    # Natural end: build a final return with the 8 carry fields.
    rewritten.append("        return TurnDecision(")
    rewritten.append("            turn_id=turn_id,")
    rewritten.append("            mode=mode,")
    rewritten.append("            plan=plan,")
    rewritten.append("            raw_text_early=raw_text_early,")
    rewritten.append("            pending_intent=pending_intent,")
    rewritten.append("            selected_tool_names=selected_tool_names,")
    rewritten.append("            semantic_fallback=semantic_fallback,")
    rewritten.append("            selected_schemas=selected_schemas,")
    rewritten.append("        )")

    decide_method_lines = [
        "    def _decide_turn(self, content: str | list[dict[str, Any]], progress: ProgressCallback | None = None) -> TurnDecision:",
        '        """R1 sprint 2026-05-28: decide phase of a turn.',
        "",
        "        Runs router + abstain + planner + subset + pending_intent +",
        "        splitter + multi-intent carry. Returns a TurnDecision; if",
        "        `early_reply` is set, run_content propagates it without",
        "        executing the LLM (caso jarvis-pending handshake, multi-intent",
        "        re-dispatch, reply-message shortcut, explicit-plan only).",
        '        """',
    ]
    decide_method_lines.extend(rewritten)
    decide_method_lines.append("")  # blank line before run_content

    # ---------- Build new run_content ----------
    # Insert decide_method_lines BEFORE line RUN_CONTENT_LINE (1-indexed).
    # Then replace lines DECIDE_START_LINE..DECIDE_END_LINE with REPLACEMENT_BLOCK.
    new_lines: list[str] = []
    new_lines.extend(src[: RUN_CONTENT_LINE - 1])  # everything up to (excluding) `def run_content`
    new_lines.extend(decide_method_lines)
    # `def run_content(...)`:
    new_lines.append(src[RUN_CONTENT_LINE - 1])
    # REPLACEMENT_BLOCK (already includes trailing newline patterns):
    new_lines.extend(REPLACEMENT_BLOCK.splitlines())
    # The rest of run_content from DECIDE_END_LINE+1 onwards:
    new_lines.extend(src[DECIDE_END_LINE:])  # 0-indexed slice = lines DECIDE_END_LINE+1.. onwards

    # Need to import TurnDecision in agent.py if not already.
    have_import = any("from .turn_types import" in l for l in new_lines[:200])
    if not have_import:
        # Find the last import-from-.something line near the top and insert after.
        insert_at = None
        for i, line in enumerate(new_lines[:200]):
            if line.startswith("from .") and "import" in line:
                insert_at = i
        if insert_at is None:
            print("ABORT: could not find a place to insert TurnDecision import")
            return 1
        new_lines.insert(insert_at + 1, "from .turn_types import TurnDecision")

    AGENT_PY.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"OK: rewrote {rewrite_count} early-returns; agent.py is now {len(new_lines)} lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
