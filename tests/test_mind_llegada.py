"""Uso 104 (F41): the trace says how long a request waited in the mind before its decision began. A greeting took 9.2 s
with its decision at 1.1 s, and the row said nothing of the other 8."""
import json
import time
from pathlib import Path

from test_mind_final import _mind, _say


def _rows(mind) -> list[dict]:
    return [json.loads(line) for line in mind.trace.read_text(encoding="utf-8").splitlines()]


def test_a_decisions_row_says_how_long_before_it_began(tmp_path: Path) -> None:
    mind, _server = _mind(tmp_path, [_say("Hola."), _say("Hola otra vez.")])
    mind.arrived, mind.app_ms = time.perf_counter() - 2.0, 8123
    mind.decide(1, "hola")
    first = [row for row in _rows(mind) if row["stage"] == "turn.decide"][-1]
    assert first["before_ms"] >= 2000 and first["app_ms"] == 8123
    assert mind.arrived is None and mind.app_ms is None
    # A request the loop did not time says nothing, instead of the last one's wait.
    mind.decide(2, "hola")
    assert "before_ms" not in [row for row in _rows(mind) if row["stage"] == "turn.decide"][-1]
