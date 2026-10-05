"""D78: a reminder anchored to the moment BAXY itself said counts when it is that moment less the advance asked."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import comprension_eval as ce  # noqa: E402

ROW = {"id": "G-w42-t2", "kind": "conv", "text": "remind me half an hour before that",
       "gold": ["op:notification.schedule", "op:reminder.create"],
       "args": {"op:notification.schedule": [["19:00", "7 pm"]], "op:reminder.create": [["19:00", "7 pm"]]}}
PREVIOUS = {"kind": "action", "operation": "web.search",
            "reply": "The Lakers play against the Sacramento Kings on Monday, October 5, 2026, at 23:00 local time."}


def _record(clock: str) -> dict:
    return {"kind": "action", "operation": "notification.schedule", "effects": ["notification.schedule"],
            "arguments": {"notification.schedule": {"seen": [{"seen": {"scheduledLocalTime": clock}}]}}}


class D78Tests(unittest.TestCase):
    def test_the_real_moment_less_the_advance_counts(self) -> None:
        self.assertTrue(ce.anchored_to_what_baxy_said(ROW, _record("22:30"), PREVIOUS))

    def test_another_clock_does_not(self) -> None:
        self.assertFalse(ce.anchored_to_what_baxy_said(ROW, _record("22:00"), PREVIOUS))

    def test_no_advance_or_no_single_clock_does_not(self) -> None:
        self.assertFalse(ce.anchored_to_what_baxy_said({**ROW, "text": "remind me then"}, _record("23:00"), PREVIOUS))
        two = {**PREVIOUS, "reply": "Kick-off is at 20:00, doors open at 18:30."}
        self.assertFalse(ce.anchored_to_what_baxy_said(ROW, _record("19:30"), two))

    def test_spanish_and_pm_forms(self) -> None:
        row = {**ROW, "text": "recuérdame una hora antes del partido"}
        prev = {"reply": "Chile juega el martes a las 9 pm contra Perú."}
        self.assertTrue(ce.anchored_to_what_baxy_said(row, _record("20:00"), prev))
        row20 = {**ROW, "text": "remind me twenty minutes before that"}
        self.assertTrue(ce.anchored_to_what_baxy_said(row20, _record("19:40"), {"reply": "Kick-off is at 8pm."}))

    def test_wrong_decision_never_counts(self) -> None:
        clarify = {"kind": "clarify", "routes": ["clarification"]}
        self.assertFalse(ce.anchored_to_what_baxy_said(ROW, clarify, PREVIOUS))


if __name__ == "__main__":
    unittest.main()
