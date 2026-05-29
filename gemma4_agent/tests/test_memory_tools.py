"""B2 (competidores): tool-picking guiado por memoria — tests de la lógica pura
(_recalled_success_tools) + el gate. El efecto EN VIVO (que ensanchar el subset con
tools de éxito pasado mejore el routing sin degradar el tool-calling del 4B) es
no-determinista -> validación en vivo en box fresca.
"""
import os
import unittest

from ..agent_core.agent import _recalled_success_tools, _memory_tools_enabled


def _rec(tools, status="OK", **kw):
    d = {"tools_used": tools, "outcome_code": status}
    d.update(kw)
    return d


class TestRecalledSuccessTools(unittest.TestCase):
    def test_extracts_success_tools(self):
        recalls = [_rec(["audio"]), _rec(["app", "window"])]
        self.assertEqual(_recalled_success_tools(recalls, []), ["audio", "app", "window"])

    def test_skips_failures(self):
        recalls = [_rec(["browser"], status="FAILED"), _rec(["audio"], status="OK")]
        self.assertEqual(_recalled_success_tools(recalls, []), ["audio"])

    def test_excludes_already_in_subset(self):
        recalls = [_rec(["audio", "app"])]
        self.assertEqual(_recalled_success_tools(recalls, ["audio"]), ["app"])

    def test_dedups(self):
        recalls = [_rec(["app"]), _rec(["app", "window"])]
        self.assertEqual(_recalled_success_tools(recalls, []), ["app", "window"])

    def test_caps(self):
        recalls = [_rec(["a", "b", "c", "d", "e"])]
        self.assertEqual(len(_recalled_success_tools(recalls, [], cap=3)), 3)

    def test_fail_status_via_mission_status(self):
        recalls = [{"tools_used": ["x"], "mission_status": "FAILED"}]
        self.assertEqual(_recalled_success_tools(recalls, []), [])

    def test_empty_and_none(self):
        self.assertEqual(_recalled_success_tools(None, []), [])
        self.assertEqual(_recalled_success_tools([], []), [])
        self.assertEqual(_recalled_success_tools([{"tools_used": []}], []), [])

    def test_none_recall_entry_safe(self):
        self.assertEqual(_recalled_success_tools([None, _rec(["audio"])], []), ["audio"])


class TestGate(unittest.TestCase):
    def test_default_off(self):
        prev = os.environ.pop("GEMMA4_MEMORY_TOOLS", None)
        try:
            self.assertFalse(_memory_tools_enabled())
        finally:
            if prev is not None:
                os.environ["GEMMA4_MEMORY_TOOLS"] = prev

    def test_on(self):
        prev = os.environ.get("GEMMA4_MEMORY_TOOLS")
        os.environ["GEMMA4_MEMORY_TOOLS"] = "1"
        try:
            self.assertTrue(_memory_tools_enabled())
        finally:
            if prev is None:
                os.environ.pop("GEMMA4_MEMORY_TOOLS", None)
            else:
                os.environ["GEMMA4_MEMORY_TOOLS"] = prev


if __name__ == "__main__":
    unittest.main()
