"""RUT10: the order of a routine said by its phrase is a turn the model reads alone (Mind._seen). Said in the
conversation where the guide had just saved it, the 4B read «cuando te diga X, haz Y… ¿La guardo? … Guardada» and asked
«¿lo cambio ahora?» or told it done with no call: 32 of 48 against 45 of 48 in a new conversation and 46 of 48 said
directly (INFORME_RUT10.md). The conversation itself keeps everything: the next turns read it whole."""
import json
from pathlib import Path

from test_mind_final import _call, _mind, _say

KEPT = {"id": "r-000001", "name": "audífonos", "trigger": {"phrase": "audífonos"}, "active": True, "steps": [],
        "order": "cámbiate a los audífonos Korvax"}
EXCHANGE = ("cuando te diga", "¿La guardo?", "Guardada")


def _guide_mind(tmp_path: Path, replies: list, kept: list | None = None):
    mind, server = _mind(tmp_path, replies)
    mind.wire_to_op = {"baxy_routines": "baxy.routines", "audio_device_set": "audio.device.set",
                       "media_control": "media.control"}
    mind.routines = kept or []
    return mind, server


def _receipt(observed: dict) -> str:
    return json.dumps({"status": "completed", "verification": "readback", "observed": observed})


def _texts(messages: list[dict]) -> list[str]:
    return [str(m.get("content") or "") for m in messages]


def _saved_now(mind) -> None:
    mind.decide(1, "Baxy, cuando te diga audífonos, cámbiate a los audífonos Korvax")
    assert mind.decide(2, "sí")["arguments"]["action"] == "create"
    mind.continue_turn(3, _receipt({"routine": KEPT, "saved": True, "runsWhen": "the person says it"}))
    mind.routines = [KEPT]


def test_the_order_of_a_routine_saved_just_now_is_read_alone(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [_call("audio_device_set", {"device": "Korvax"}), _say("Listo, en los Korvax.")])
    _saved_now(mind)
    assert mind.decide(4, "Baxy, audífonos")["operation"] == "audio.device.set"
    asked = server.bodies[0]["messages"]
    assert [m["role"] for m in asked] == ["system", "user", "user"]
    assert asked[-1] == {"role": "user", "content": "cámbiate a los audífonos Korvax"}
    # and after its call, still that turn alone: the receipt and the answer, nothing of the guide
    assert mind.continue_turn(5, _receipt({"device": "Auriculares (Korvax Pulse)"}))["reply"] == "Listo, en los Korvax."
    after = _texts(server.bodies[1]["messages"][1:])
    assert not any(part in text for text in after for part in EXCHANGE), after
    # the conversation keeps all of it, for the turns that come next
    assert any("¿La guardo?" in text for text in _texts(mind.conversation))


def test_the_turn_after_a_routine_reads_the_whole_conversation(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [_call("audio_device_set", {"device": "Korvax"}), _say("Listo."),
                                          _say("Guardaste «audífonos».")])
    _saved_now(mind)
    mind.decide(4, "Baxy, audífonos")
    mind.continue_turn(5, _receipt({"device": "Auriculares (Korvax Pulse)"}))
    mind.decide(6, "¿qué fue lo que acabas de guardar?")
    said = _texts(server.bodies[2]["messages"])
    assert any("¿La guardo?" in text for text in said) and "cámbiate a los audífonos Korvax" in said


def test_a_request_that_is_no_routine_reads_the_whole_conversation(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [_say("Es la rutina «audífonos».")])
    _saved_now(mind)
    mind.decide(4, "¿qué fue lo que acabas de guardar?")
    assert any("¿La guardo?" in text for text in _texts(server.bodies[0]["messages"]))
