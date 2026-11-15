"""Aid «local_day_part», INT36A (gate u121-M0: «¿a qué hora me llegó el último correo?», with the receipt's receivedLocal
«Wednesday 2026-11-04 11:25» and the clock line's «22:00 hora local (de la noche)», was answered «a las 11:25 de la
noche» 9 of 10 on r4a; 0 of 10 on the 1.5.2, whose clock line told no part of the day). A local time of a result reaches
the model with its own part of the day, written by code from its hour as the clock's is; the receipt stays as the App
gave it."""
import json
from pathlib import Path

from baxy_mind import harness_language
from baxy_mind.mind import _local_day_parts
from test_mind_final import _call, _mind, _say

MAIL = json.dumps({"status": "completed", "verification": "output_only", "observed": {
    "subject": "Presupuesto", "receivedLocal": "Wednesday 2026-11-04 11:25", "receivedUtc": "2026-11-04T14:25:00Z"}})


def _read_by_the_model(server) -> str:
    return [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]


def test_a_local_time_of_a_result_is_read_with_its_own_part_of_the_day(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("email_latest_read", {}), _call("system_time", {})])
    mind.decide(1, "¿a qué hora me llegó el último correo?")
    mind.continue_turn(2, MAIL)
    read = _read_by_the_model(server)
    assert "Wednesday 2026-11-04 11:25 (de la mañana)" in read
    # The time in UTC is not a local time: as it came.
    assert "2026-11-04T14:25:00Z" in read and "14:25:00Z (" not in read
    # The receipt keeps what the App gave.
    assert mind._turn["receipts"][-1]["observation"] == MAIL


def test_each_part_of_the_day_is_the_clocks() -> None:
    for hour, part in (("00:10", "de la noche"), ("03:00", "de la madrugada"), ("08:05", "de la mañana"),
                       ("12:30", "del mediodía"), ("15:45", "de la tarde"), ("19:00", "de la tarde"),
                       ("22:17", "de la noche")):
        told = _local_day_parts(json.dumps({"observed": {"startLocal": f"Friday 2026-11-06 {hour}"}}))
        assert json.loads(told)["observed"]["startLocal"] == f"Friday 2026-11-06 {hour} ({part})", hour


def test_only_a_local_field_that_ends_in_an_hour_is_told() -> None:
    for same in ({"receivedUtc": "2026-11-04T14:25:00Z"}, {"startLocal": "Friday 2026-11-06"},
                 {"title": "Reunión 11:25"}, {"dueLocal": "2026-11-06 07:30:15.250"}, {"nowLocal": "25:99"},
                 {"local": "11:25"}, {"durationLocal": "1:11:25"}):
        text = json.dumps({"observed": same}, ensure_ascii=False)
        assert _local_day_parts(text) == text, same
    told = _local_day_parts('{"alarms":[{"dueLocal":"2026-11-06 07:30"},{"nextRunLocal": "2026-11-07T19:05"}]}')
    assert told == ('{"alarms":[{"dueLocal":"2026-11-06 07:30 (de la mañana)"},'
                    '{"nextRunLocal": "2026-11-07T19:05 (de la tarde)"}]}')


def test_in_english_mode_the_part_is_in_english() -> None:
    harness_language.use("en")
    try:
        told = _local_day_parts(MAIL) + _local_day_parts('{"startLocal": "Friday 2026-11-06 19:00"}')
    finally:
        harness_language.use("es")
    assert "11:25 (in the morning)" in told and "19:00 (in the evening)" in told and "de la" not in told


def test_without_the_aid_the_result_is_as_it_came(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    mind, server = _mind(tmp_path, [_call("email_latest_read", {}), _say("A las 11:25.")])
    mind.decide(1, "¿a qué hora me llegó el último correo?")
    mind.continue_turn(2, MAIL)
    assert "(de la" not in _read_by_the_model(server)
