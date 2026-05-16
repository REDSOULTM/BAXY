"""Contract tests for ToolRegistry.execute().

Pins the invariants every caller (agent.py, routine_runner, mcp_server) relies
on:
  1. execute() ALWAYS returns a dict, never raises (no matter how badly a
     handler misbehaves).
  2. The returned dict ALWAYS has `ok` (bool), `status` (str), `verified`
     (bool|None), `tool` (str) — these are the keys verifiers + the
     LLM-facing serializer expect.
  3. Unknown tool names degrade gracefully (ok=False, status=failed).
  4. Handler exceptions bubble through normalize_tool_result, not the caller.
  5. invalid args produce status=failed with `validation_errors` (the LLM
     reads this).

Why this exists: a handler refactor that returns a raw string, swallows an
exception inside an `except: pass`, or forgets to set `ok` would corrupt the
trace + break the verifier silently. This file is the canary.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from .memory import MemoryStore
from .state import AgentState
from .tools import ToolRegistry


class _MisbehavingRegistry(ToolRegistry):
    """Registry subclass that swaps a real handler for one that always raises.

    Lets us probe execute() without monkey-patching arbitrary tool modules.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Replace `system` with a handler that raises a RuntimeError.
        def _boom(_args):
            raise RuntimeError("simulated handler crash for contract test")
        self._impls["system"] = _boom


def _make_registry(safety_enabled: bool = False) -> ToolRegistry:
    tmp = Path(tempfile.mkdtemp(prefix="gemma4_contract_"))
    memory = MemoryStore(tmp / "mem.json")
    state = AgentState(tmp / "data" / "state.json")
    return ToolRegistry(memory, tmp / "captures", state=state, safety_enabled=safety_enabled)


class TestExecuteContract(unittest.TestCase):

    def test_unknown_tool_returns_failed_dict(self):
        reg = _make_registry()
        out = reg.execute("nonexistent_tool_xyz", {"foo": "bar"})
        self.assertIsInstance(out, dict)
        self.assertFalse(out.get("ok"))
        self.assertEqual(out.get("status"), "failed")
        self.assertEqual(out.get("tool"), "nonexistent_tool_xyz")
        self.assertIn("unknown tool", str(out.get("error", "")))

    def test_handler_exception_is_caught_and_normalized(self):
        tmp = Path(tempfile.mkdtemp(prefix="gemma4_contract_"))
        memory = MemoryStore(tmp / "mem.json")
        state = AgentState(tmp / "data" / "state.json")
        reg = _MisbehavingRegistry(
            memory, tmp / "captures", state=state, safety_enabled=False
        )
        out = reg.execute("system", {"action": "time"})
        self.assertIsInstance(out, dict)
        self.assertFalse(out.get("ok"))
        self.assertEqual(out.get("status"), "failed")
        self.assertEqual(out.get("tool"), "system")
        # The raw exception text should surface to the LLM via `error`.
        self.assertIn("RuntimeError", str(out.get("error", "")))
        self.assertIn("simulated handler crash", str(out.get("error", "")))

    def test_invalid_args_short_circuit_with_validation_errors(self):
        reg = _make_registry()
        # window only accepts a fixed set of actions per schema; an arbitrary
        # string should be rejected by _coerce_and_validate_tool_args.
        out = reg.execute("window", {"action": "fly_to_the_moon"})
        self.assertIsInstance(out, dict)
        self.assertFalse(out.get("ok"))
        self.assertEqual(out.get("status"), "failed")
        # The schema-violation payload tells the LLM what went wrong.
        self.assertIn("invalid tool arguments", str(out.get("error", "")))
        self.assertIn("validation_errors", out)

    def test_none_args_does_not_crash(self):
        reg = _make_registry()
        # Most handlers expect a dict; passing None must be normalized
        # internally to {} (or an explicit error), never AttributeError.
        out = reg.execute("system", None)  # type: ignore[arg-type]
        self.assertIsInstance(out, dict)
        # Either it succeeded with a default action, or returned a normalized
        # failure dict — never a raw exception.
        self.assertIn("status", out)
        self.assertIn("ok", out)

    def test_result_always_has_core_keys(self):
        reg = _make_registry()
        # Pick handlers across modules to exercise the normalization path.
        for tool, args in [
            ("system", {"action": "time"}),
            ("memory", {"action": "list"}),
            ("state", {"action": "ttl_inspect"}),
        ]:
            out = reg.execute(tool, args)
            with self.subTest(tool=tool):
                self.assertIsInstance(out, dict, f"{tool} returned non-dict")
                self.assertIn("ok", out)
                self.assertIn("status", out)
                self.assertIn("tool", out)
                self.assertEqual(out.get("tool"), tool)


if __name__ == "__main__":
    unittest.main()
