"""Aid «said_place», CLI1 (LEG3's finding, base c2a4c76ac: 8-9 of 24 weather requests with no place said became
weather_current {location: "Santiago"}, and the reply gave Santiago's weather as the person's own). Only the form is
compared, as «said_file_name» compares a file name: the location is in none of the person's words of the conversation
nor in any result, not even close in spelling. Nothing is read; the result says so, as data, and the model decides
again, once per turn: without location the weather is read where this PC is, approximately."""
import json
from pathlib import Path

from test_mind_final import _call, _mind, _say

READ = json.dumps({"status": "completed", "verification": "output_only", "observed": {"location": "Rosario"}})


def _not_run(mind) -> list[dict]:
    told = []
    for message in mind.conversation:
        if message["role"] == "tool" and str(message.get("content")).startswith("{"):
            body = json.loads(str(message["content"]).split("\n", 1)[0])
            if body.get("status") == "not_run":
                told.append(body)
    return told


def test_a_place_nobody_said_goes_back_and_the_model_reads_here(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("weather_current", {"location": "Santiago"}), _call("weather_current", {})])
    step = mind.decide(1, "¿va a llover hoy?")
    assert step["kind"] == "action" and not step["arguments"].get("location")
    told = _not_run(mind)
    assert len(told) == 1 and told[0]["location"] == "Santiago"


def test_it_is_told_once_and_the_same_call_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    wrong = _call("weather_current", {"location": "Santiago"})
    mind, _ = _mind(tmp_path, [wrong, wrong])
    assert mind.decide(1, "¿qué tiempo hace?")["arguments"]["location"] == "Santiago"
    assert len(_not_run(mind)) == 1


def test_a_place_said_in_the_words_is_read(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    for said, location in (("¿llueve en medellin?", "Medellín, Colombia"), ("¿qué tal el clima en Barcelna?", "Barcelona"),
                           ("¿qué temperatura hace en Londres?", "London"), ("weather in 東京 now?", "Tokyo"),
                           ("¿cómo está el tiempo en Nueva York?", "New York")):
        mind, _ = _mind(tmp_path, [_call("weather_current", {"location": location})])
        assert mind.decide(1, said)["arguments"]["location"] == location, said
        assert _not_run(mind) == [], said


def test_a_place_said_turns_before_is_read(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_say("Que te vaya bien."), _say("Hecho."),
                               _call("weather_current", {"location": "Rosario"})])
    mind.decide(1, "mañana viajo a Rosario por trabajo")
    mind.decide(2, "gracias, nada más")
    assert mind.decide(3, "¿y cómo va a estar el clima allá?")["arguments"]["location"] == "Rosario"
    assert _not_run(mind) == []


def test_a_place_a_result_showed_is_read(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    kept = json.dumps({"status": "completed", "verification": "output_only",
                       "observed": {"records": [{"label": "Ciudad donde vive", "value": "Rosario, Argentina"}]}})
    mind, _ = _mind(tmp_path, [_call("memory_recall", {"query": "ciudad"}),
                               _call("weather_current", {"location": "Rosario"})])
    assert mind.decide(1, "¿qué tiempo hace en mi ciudad?")["operation"] == "memory_recall"
    assert mind.continue_turn(2, kept)["arguments"]["location"] == "Rosario"
    assert _not_run(mind) == []


def test_without_the_aid_it_is_read(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    mind, _ = _mind(tmp_path, [_call("weather_current", {"location": "Santiago"})])
    assert mind.decide(1, "¿va a llover hoy?")["arguments"]["location"] == "Santiago"
