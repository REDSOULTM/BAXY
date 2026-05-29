"""Validate every prompts/tool_rules/*.md references actions that
actually exist in tool_schemas.py.

Hotfix G 2026-05-17. Without this test, prompt rules can drift
into promising actions that don't exist — e.g. the Bug D4
'session(action="search")' hallucination. If a rule said it, the
drift would have stuck.

The check: for each rule.md, parse `tool(action='X')` /
`tool(action="X")` patterns, look up the tool's real action list
(extracted from its schema description), and assert each
referenced action exists.

Schemas that don't enumerate actions in the description (rare;
mostly meta-tools) are skipped without failing.
"""
from __future__ import annotations

import os
import re
import unittest

from gemma4_agent.tools_pkg.tools import COMPOUND_TOOL_SCHEMAS


_RULES_DIR = os.path.join(os.path.dirname(__file__), "prompts", "tool_rules")


def _actions_for_tool(tool_name: str) -> set[str] | None:
    """Extract the action list from a schema's description.

    Most schemas have "Actions: a, b, c, d." near the start. If
    the schema has no such enumeration, return None and the test
    skips action checks for that tool.

    Some schemas have compound action names (event_create,
    git_commit, etc.) — we treat the underscore-prefixed family
    (e.g. `git_*`) as a wildcard match if a rule cites it.
    """
    for s in COMPOUND_TOOL_SCHEMAS:
        if s.get("function", {}).get("name") != tool_name:
            continue
        desc = s.get("function", {}).get("description") or ""
        # Match "Actions:" or "Action:" (singular for tools with one
        # action like terminal). Cap the search to the first 600
        # chars so we don't accidentally pick up later prose.
        m = re.search(r"Actions?:\s*([a-z_,\s/]+)", desc[:600], re.IGNORECASE)
        if not m:
            return None
        raw = m.group(1).split(".")[0]
        # Some schemas use "magnifier_start/stop" — split on / too.
        parts: set[str] = set()
        for chunk in re.split(r"[,\s/]+", raw):
            chunk = chunk.strip()
            if chunk:
                parts.add(chunk)
        return parts
    return None


_ACTION_REF = re.compile(
    r"\b([a-z_]+)\(\s*action\s*=\s*['\"]([a-z_]+)['\"]"
)

# Negative-mention exclusion. browser.md says: `NOT browser(action="minimize")`
# — that's an intentional negative example. The drift test must
# ignore matches whose left-context is a negative-mention marker,
# otherwise it flags valid pedagogical content as drift.
_NEGATIVE_PREFIX = re.compile(
    r"(?:NOT\s+|not\s+|don'?t\s+(?:use\s+)?|never\s+|avoid\s+)$",
    re.IGNORECASE,
)


def _is_negative_mention(text: str, match_start: int) -> bool:
    """True if the `tool(action='X')` match is preceded by a
    negative-mention marker like 'NOT ', "don't ", 'never ',
    'avoid '. Window: the 20 chars immediately preceding the match.
    """
    left = text[max(0, match_start - 20):match_start]
    return bool(_NEGATIVE_PREFIX.search(left))


# Wildcard family suffix: a rule may cite `developer(action='git_*')`
# as a family — accept any concrete git_* action that exists in the
# schema. Detected by trailing '_' on the literal in the regex match.
def _action_matches_family(action: str, schema_actions: set[str]) -> bool:
    if action in schema_actions:
        return True
    # Pattern: rule cites `git_` (raw '_' suffix) → match any
    # schema action that starts with that prefix.
    if action.endswith("_"):
        prefix = action  # already ends with _
        return any(a.startswith(prefix) for a in schema_actions)
    return False


class ToolRuleActionDriftTest(unittest.TestCase):
    def test_every_rule_references_real_actions(self) -> None:
        if not os.path.isdir(_RULES_DIR):
            self.skipTest(f"no rules dir at {_RULES_DIR}")
        problems: list[str] = []
        for fname in sorted(os.listdir(_RULES_DIR)):
            if not fname.endswith(".md"):
                continue
            path = os.path.join(_RULES_DIR, fname)
            with open(path, encoding="utf-8") as fh:
                body = fh.read()
            for m in _ACTION_REF.finditer(body):
                ref_tool, ref_action = m.group(1), m.group(2)
                if _is_negative_mention(body, m.start()):
                    continue
                schema_actions = _actions_for_tool(ref_tool)
                if schema_actions is None:
                    continue
                if not _action_matches_family(ref_action, schema_actions):
                    problems.append(
                        f"{fname}: references {ref_tool}(action='{ref_action}') "
                        f"but {ref_tool} schema only lists "
                        f"{sorted(schema_actions)}"
                    )
        if problems:
            self.fail(
                "Tool rule action drift detected:\n  "
                + "\n  ".join(problems)
            )


if __name__ == "__main__":
    unittest.main()
