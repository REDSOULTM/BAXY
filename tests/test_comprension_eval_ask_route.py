"""D73: a turn that published only a clarification counts for a gold ``ask`` in the D61 layer (DEV-I v4u I-s057);
the strict figure, the set's own gold, does not change."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import comprension_eval as ce  # noqa: E402

ASKED = {"kind": "action", "operation": "reminder.create", "effects": ["reminder.create"],
         "routes": ["clarification"], "arguments": None}


class AskRouteTests(unittest.TestCase):
    def test_only_a_clarification_published_is_asked(self) -> None:
        self.assertTrue(ce.asked_only(ASKED))

    def test_a_result_or_nothing_is_not_asked(self) -> None:
        for routes in (["result"], ["clarification", "result"], []):
            self.assertFalse(ce.asked_only({**ASKED, "routes": routes}))

    def test_strict_figure_unchanged(self) -> None:
        row = {"gold": ["op:reminder.create", "ask"], "args": {"op:reminder.create": [["luz"]]}}
        self.assertEqual(ce.verdict(row, ASKED), (True, False))

    def test_d61_layer_counts_it(self) -> None:
        row = {"id": "x", "gold": ["op:reminder.create", "ask"], "args": {"op:reminder.create": [["luz"]]}}
        summary: dict = {}
        lines = ce._d61_lines([row], {"x": ASKED}, {"x": (True, False)}, {"total": [row]}, None, False,
                              pathlib.Path("RUN.jsonl"), None, True, summary)
        self.assertEqual(summary["d61"]["d73"], 1)
        self.assertEqual(summary["d61"]["total"]["right"], 1)
        self.assertIn("D73 preguntó lo que el oro acepta 1", lines[0])

    def test_gold_without_ask_is_not_counted(self) -> None:
        row = {"id": "x", "gold": ["op:reminder.create"], "args": {"op:reminder.create": [["luz"]]}}
        summary: dict = {}
        ce._d61_lines([row], {"x": ASKED}, {"x": (True, False)}, {"total": [row]}, None, False,
                      pathlib.Path("RUN.jsonl"), None, True, summary)
        self.assertEqual(summary["d61"]["total"]["right"], 0)


if __name__ == "__main__":
    unittest.main()
