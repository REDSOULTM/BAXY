"""ALR7 (VIVO9, 1.3.3 en vivo, 2026-11-10): what the model reads to set an alarm for a time counted from now.

«Pon una alarma dentro de un minuto» went as at "20:56" at 19:56 and as at "20:11" at 20:11 (set for tomorrow): the model
worked out the clock itself. The description says a time counted from now goes as inMinutes or inSeconds, which the
tool counts from now (WindowsScheduledNotificationAdapter.TryDue), with that phrase as an example.

«Todavía no la apagues» (the model's own stop, not the acknowledgement rule) is not answered here: a sentence in
RINGING_NOTE for it left more of them ringing but stopped fewer acknowledgements (39/45 → 36/45), so it is out."""
import json
from pathlib import Path

_DATA = Path(__file__).resolve().parents[1] / "src" / "baxy_mind" / "data" / "tool_descriptions.en.v1.json"


def test_a_time_counted_from_now_goes_as_minutes_or_seconds_and_never_as_a_clock_worked_out() -> None:
    alarms = json.loads(_DATA.read_text(encoding="utf-8"))["tools"]["schedule.alarms"]
    assert ("a time counted from now (in a minute, in half an hour, in 90 seconds) goes as inMinutes or inSeconds, "
            "which the tool counts from now, never as at worked out from the clock;") in alarms
    assert "«pon una alarma dentro de un minuto» (create, alarm, inMinutes 1)" in alarms
