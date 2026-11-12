"""REM6 (REV15): what the sixth review asked to close in the routines and the «sí» before the official 1.5.0."""
from __future__ import annotations

from pathlib import Path

import pytest

from baxy_mind import routine_guide
from test_mind_routine_guide import _guide_mind

SAY = {"choices": [{"message": {"role": "assistant", "content": "Vale."}}]}
NIGHT = {"id": "r-000011", "name": "buenas noches", "trigger": {"phrase": "buenas noches"}, "active": True,
         "steps": [], "order": "baja el volumen a 10"}
LONG = {"id": "r-000014", "name": "todo abajo", "active": True, "steps": [], "order": "baja el volumen a 10",
        "trigger": {"phrase": "apaga la pantalla y baja el volumen a diez por favor ya"}}


def _ran(result: dict, server) -> bool:
    """Whether the turn did what a routine keeps: its order reached the model as the person's words, or it fired."""
    sent = [str(m.get("content")) for body in server.bodies for m in body["messages"] if m.get("role") == "user"]
    return any("baja el volumen a 10" == said for said in sent) or (result or {}).get("kind") == "action"


# ---------------------------------------------------------------------------------------------------------------------
# B-1: after a word refused, the phrase of an active routine of theirs runs nothing
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("said", [
    ["Cuando te diga sí, apaga la pantalla.", "buenas noches"],                   # REV15 S1
    ["crea una rutina", "con una palabra", "sí", "buenas noches"],                # REV15 S2
    ["Cuando te diga sí, apaga la pantalla.", "Buenas noches."],
    ["crea una rutina", "con una palabra", "vale", "Baxy, buenas noches"],
])
def test_the_phrase_of_an_active_routine_in_the_guide_runs_nothing_and_is_said_taken(tmp_path: Path,
                                                                                    said: list[str]) -> None:
    mind, server = _guide_mind(tmp_path, [SAY] * 6, [NIGHT])
    *before, last = said
    for index, words in enumerate(before, 1):
        mind.decide(index, words)
    result = mind.decide(len(said), last)
    assert not _ran(result, server)
    assert result["reply"].lower() == "ya tienes una rutina con «buenas noches». dime otra palabra, o «cancela»."
    assert mind._guide is not None


def test_a_long_phrase_of_an_active_routine_after_a_refused_word_runs_nothing(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [SAY] * 6, [LONG])
    mind.decide(1, "Cuando te diga sí, apaga la pantalla.")
    result = mind.decide(2, LONG["trigger"]["phrase"])
    assert not _ran(result, server)


def test_the_turn_that_leaves_the_guide_fires_no_routine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Whatever made the guide let go of the person, that turn answered BAXY's question: it is no routine's phrase.
    mind, server = _guide_mind(tmp_path, [SAY] * 6, [NIGHT])
    mind.decide(1, "Cuando te diga sí, apaga la pantalla.")
    monkeypatch.setattr(routine_guide.Guide, "leaves", lambda self, *a, **k: True)
    result = mind.decide(2, "buenas noches")
    assert not _ran(result, server)
    assert mind._guide is None


def test_a_taken_phrase_never_leaves_the_guide() -> None:
    guide = routine_guide.Guide(lang="es", step="phrase", kind="word")
    guide.answer("sí", [NIGHT], False, None)
    assert not guide.leaves("buenas noches", [NIGHT])
    assert not routine_guide.Guide(lang="es", step="phrase", kind="word").leaves("buenas noches", [NIGHT])


# ---------------------------------------------------------------------------------------------------------------------
# B-3: a routine turned off is, for the orders, as if it were not there
# ---------------------------------------------------------------------------------------------------------------------

LOUD_OFF = {"id": "r-000013", "name": "sube el volumen", "trigger": {"phrase": "sube el volumen"}, "active": False,
            "steps": [], "order": "pon el volumen al 80"}
SCREEN_OFF = {"id": "r-000012", "name": "pantalla", "trigger": {"phrase": "pantalla"}, "active": False,
              "steps": [], "order": "apaga la pantalla"}


@pytest.mark.parametrize("said", [["sube el volumen", "no", "sube el volumen"],   # REV15 S4
                                  ["sube el volumen"], ["Baxy, sube el volumen."], ["pantalla"]])
def test_the_phrase_of_a_routine_turned_off_is_the_persons_own_order(tmp_path: Path, said: list[str]) -> None:
    mind, server = _guide_mind(tmp_path, [SAY] * 8, [NIGHT, LOUD_OFF, SCREEN_OFF])
    for index, words in enumerate(said, 1):
        result = mind.decide(index, words)
        assert result["kind"] == "conversation" and "desactivada" not in result["reply"], (words, result["reply"])
        sent = [m["content"] for m in server.bodies[-1]["messages"] if m.get("role") == "user"]
        assert words in sent and not {"pon el volumen al 80", "apaga la pantalla"} & set(sent)   # as said
    assert mind._guide is None


# ---------------------------------------------------------------------------------------------------------------------
# B-2: the call after their «sí» names the routine asked about by its id, never by a name another one answers to
# ---------------------------------------------------------------------------------------------------------------------

WAKE = {"id": "r-0000a1", "name": "despertar", "trigger": {"at": "07:00", "repeat": "daily", "days": []},
        "active": True, "steps": ["say: arriba"]}
PILL = {"id": "r-0000a2", "name": "07:00", "trigger": {"at": "07:00", "repeat": "once", "days": []},
        "active": True, "steps": ["say: la pastilla"]}
READ = {"id": "r-0000b1", "name": "lectura", "trigger": {"phrase": "modo lectura"}, "active": True, "steps": [],
        "order": "baja el brillo"}
STUDY = {"id": "r-0000b2", "name": "estudio", "trigger": {"phrase": "lectura"}, "active": True, "steps": [],
         "order": "silencia el chat"}


def test_the_yes_to_a_routine_gone_meanwhile_names_it_by_its_id(tmp_path: Path) -> None:
    # REV15 B-2: asked «07:00» (the one said once, pruned two minutes after it rang), «sí» deleted «despertar».
    mind, server = _guide_mind(tmp_path, [SAY] * 4, [WAKE, PILL])
    mind.decide(1, "borra la rutina 07:00")
    assert mind.decide(2, "07:00")["reply"] == "¿Borro tu rutina «07:00»?"
    mind.routines = [WAKE]
    done = mind.decide(3, "sí")
    assert done["kind"] == "action" and done["arguments"] == {"action": "delete", "name": PILL["id"]}


def test_a_change_names_its_routine_by_its_id(tmp_path: Path) -> None:
    guide = routine_guide.Guide.changing(READ, "es", "order")
    guide.answer("sube el brillo", [READ, STUDY], False, None)
    _, arguments, ended = guide.answer("sí", [READ, STUDY], False, None)
    assert ended and arguments == {"action": "change", "name": READ["id"], "order": "sube el brillo"}


def test_the_sentence_after_a_routine_not_found_names_it_as_asked(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [SAY] * 4, [WAKE, PILL])
    mind.decide(1, "borra la rutina 07:00")
    mind.decide(2, "07:00")
    mind.routines = [WAKE]
    mind.decide(3, "sí")
    gone = '{"status": "failed", "error": "routine_not_found", "observed": {"name": "r-0000a2"}}'
    said = mind.continue_turn(3, gone) if hasattr(mind, "continue_turn") else None
    assert said is not None and "«07:00»" in said["reply"] and "r-0000a2" not in said["reply"]
