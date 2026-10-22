"""The scene bench's reading of what a heartbeat holds (scripts/renew/bench_escenas.py): the catalog's effects as
NativeTurnLoop.BeatProposes reads them (al máximo 5.1 and R10.1), with catalogs saved with or without effects."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "renew"))

from bench_escenas import heartbeat_holds, held_by_app  # noqa: E402


@pytest.mark.parametrize("op, arguments, risk, held", [
    ("system.settings.set", {"setting": "airplane_mode", "value": 1}, "privacy_sensitive", True),
    ("bluetooth.radio.set", {"state": False}, "low_reversible", True),
    ("app.open", {"appId": "Spotify"}, "low_reversible", False),
    ("app.open", {"appId": "Spotify", "foreground": True}, "low_reversible", True),
    ("media.control", {"action": "pause"}, "low_reversible", True),
    ("media.control", {"action": "pause", "sourceApp": "Spotify.exe"}, "low_reversible", False),
    ("system.time", {"place": "Lima"}, "read_only", True),
    ("system.time", {}, "read_only", False),
    ("window.minimize", {"windowId": "w1"}, "low_reversible", False),
    ("app.close", {"appId": "Spotify"}, "work_loss", True),
])
def test_the_bench_holds_what_the_app_holds_in_a_heartbeat(op, arguments, risk, held) -> None:
    assert held_by_app(op, arguments, risk, heartbeat_holds()) is held
