"""RUT9 (REV9, revisión a ciegas de las rutinas; documentacion/RUTINAS.md §5): what the routines' fixed path said or
saved that was not so. Each test is one of REV9's reproductions (tmp/REV9/sondas*.py), red before this round."""
import json
from pathlib import Path

import pytest

from baxy_mind import routine_guide, routines
from test_mind_final import _mind, _say

WORD = {"id": "r-000009", "name": "baxy buenas noches", "trigger": {"phrase": "baxy buenas noches"}, "active": True,
        "steps": [], "order": "apaga la luz"}
WEEKDAYS = {"id": "r-acb6ec", "name": "08:00", "active": True,
            "trigger": {"at": "08:00", "repeat": "days", "days": ["mon", "tue", "wed", "thu", "fri"]},
            "steps": [{"say": "buen día, a trabajar"}]}


def _guide_mind(tmp_path: Path, replies: list, kept: list | None = None):
    mind, server = _mind(tmp_path, replies)
    mind.wire_to_op = {"baxy_routines": "baxy.routines", "media_control": "media.control",
                       "schedule_alarms": "schedule.alarms"}
    mind.routines = kept or []
    return mind, server


def _receipt(observed: dict) -> str:
    return json.dumps({"status": "completed", "verification": "readback", "observed": observed})


def _talk(mind, words: list[str], first: int = 1) -> list[dict]:
    return [mind.decide(first + index, said) for index, said in enumerate(words)]


# H1: the list says what was saved, or BAXY's fixed sentence says nothing and the model reads the receipt.
def test_a_weekday_routine_is_listed_with_its_days_and_its_words() -> None:
    said = routine_guide.told(_receipt({"routines": [WEEKDAYS], "count": 1}), "list", "es")
    assert said == "Tienes una rutina: de lunes a viernes a las 8:00 de la mañana te digo «buen día, a trabajar»."


@pytest.mark.parametrize("cut", [
    {**WEEKDAYS, "trigger": {"at": "08:00", "repeat": "days", "days": [None, None, None, None, None]}},
    {**WEEKDAYS, "steps": [{}]},
    {**WEEKDAYS, "trigger": {"at": "08:00", "repeat": "days"}},
])
def test_a_list_whose_days_or_words_did_not_arrive_has_no_fixed_sentence(cut: dict) -> None:
    # REV9 H1: «una vez, a las 8:00 de la mañana te digo «»» for a weekday routine that says something.
    assert routine_guide.told(_receipt({"routines": [cut], "count": 1}), "list", "es") is None


# H2: a phrase that begins with BAXY's name is kept without it, as the turn is compared without it.
def test_a_phrase_said_after_the_name_is_saved_without_it_and_fires(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [])
    asked = mind.decide(1, "cuando te diga baxy buenas noches, apaga la luz")
    assert asked["reply"] == "Cuando digas «buenas noches»: «apaga la luz». ¿La guardo?"
    assert mind.decide(2, "sí")["arguments"] == {"action": "create", "phrase": "buenas noches", "order": "apaga la luz"}
    kept = [{**WORD, "name": "buenas noches", "trigger": {"phrase": "buenas noches"}}]
    for turn in ("Baxy, buenas noches", "Baxy buenas noches", "buenas noches", "Baxi, Baxy, buenas noches"):
        assert routines.ordered(turn, kept) == ("buenas noches", "buenas noches", "apaga la luz"), turn
    assert server.bodies == []


@pytest.mark.parametrize("turn", ["Baxy, buenas noches", "Baxy buenas noches", "buenas noches"])
def test_a_phrase_already_saved_with_the_name_in_front_fires_too(turn: str) -> None:
    assert routines.ordered(turn, [WORD]) == ("baxy buenas noches", "baxy buenas noches", "apaga la luz")


@pytest.mark.parametrize("said", ["cuando te diga baxy, apaga el PC", "cuando te diga Baxi, apaga la luz",
                                  "cuando te diga a, apaga el PC", "cuando te diga eh, apaga el PC"])
def test_a_phrase_that_is_only_the_name_or_a_sound_is_never_saved(tmp_path: Path, said: str) -> None:
    # REV9 H2/H7: nothing could fire it (the name is taken off every turn), or anything the ear hears would.
    mind, server = _guide_mind(tmp_path, [])
    asked = mind.decide(1, said)
    assert asked["reply"] == "¿Con una palabra tuya o a una hora?"
    assert mind._guide.step == "kind" and server.bodies == []


@pytest.mark.parametrize("word", ["baxy", "Baxi", "a", "eh", "Baxy, a"])
def test_the_guide_asks_again_for_a_word_that_is_only_the_name_or_a_sound(tmp_path: Path, word: str) -> None:
    mind, server = _guide_mind(tmp_path, [])
    said = _talk(mind, ["crea una rutina", "con una palabra", word])
    assert said[2]["reply"] == "No entendí la palabra. ¿Qué palabra vas a decir?"
    assert mind._guide.step == "phrase" and server.bodies == []


# H8: a clock is one word.
def test_a_clock_as_the_phrase_is_not_split_at_its_colon(tmp_path: Path) -> None:
    mind, _ = _guide_mind(tmp_path, [])
    assert mind.decide(1, "cuando te diga 8:00, apaga la luz")["reply"] == "Cuando digas «8:00»: «apaga la luz». ¿La guardo?"


# H4: the guide does not swallow the turns.
@pytest.mark.parametrize("leave", ["no, déjalo", "olvídate", "olvídate de eso", "mejor otro día", "never mind",
                                   "no importa", "forget about it"])
def test_natural_ways_of_leaving_close_the_guide_with_nothing_saved(tmp_path: Path, leave: str) -> None:
    mind, server = _guide_mind(tmp_path, [])
    said = _talk(mind, ["crea una rutina", "con una palabra", leave])
    assert said[2]["reply"] in ("Listo, lo dejo: no guardé ninguna rutina.", "Okay, leaving it: I didn't save any routine.")
    assert mind._guide is None and server.bodies == []


def test_another_request_at_save_it_leaves_the_guide_unsaved_and_goes_to_the_model(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [_say("Mañana, soleado.")])
    said = _talk(mind, ["crea una rutina", "con una palabra", "nube", "pon música"])
    assert said[3]["reply"] == "Cuando digas «nube»: «pon música». ¿La guardo?"
    answered = mind.decide(5, "¿qué tiempo hace mañana en la ciudad?")
    assert answered["reply"] == "Mañana, soleado."
    assert mind._guide is None and len(server.bodies) == 1
    messages = server.bodies[0]["messages"]
    assert messages[-1] == {"role": "user", "content": "¿qué tiempo hace mañana en la ciudad?"}
    assert any(routine_guide.LEFT_NOTE in str(m.get("content")) for m in messages[-3:-1])
    # and a «sí» afterwards saves nothing: the guide is gone
    assert mind._guide is None


@pytest.mark.parametrize("said", ["sí, pero cámbiale la palabra", "eh", "¿cómo?"])
def test_at_save_it_what_is_not_another_request_asks_again(tmp_path: Path, said: str) -> None:
    mind, server = _guide_mind(tmp_path, [])
    _talk(mind, ["crea una rutina", "con una palabra", "nube", "pon música"])
    assert mind.decide(5, said)["reply"].startswith("Di «sí» para guardarla o «no» para dejarla.")
    assert mind._guide.step == "confirm" and server.bodies == []


def test_two_answers_in_a_row_that_answer_nothing_leave_the_guide(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [_say("Son las tres.")])
    said = _talk(mind, ["crea una rutina", "qué tal el clima"])
    assert said[1]["reply"].startswith("No te entendí.")
    assert mind.decide(3, "pon música en la sala")["reply"] == "Son las tres."
    assert mind._guide is None and len(server.bodies) == 1


def test_an_answer_that_answers_nothing_does_not_put_off_the_silence(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [_say("Vale.")])
    _talk(mind, ["crea una rutina"])
    mind._guide_at -= 200
    at = mind._guide_at
    assert mind.decide(2, "mmm")["reply"].startswith("No te entendí.")
    assert mind._guide_at == at
    mind._guide_at -= 200   # 400 s since the last answer that answered
    assert mind.decide(3, "con una palabra")["reply"] == "Vale."
    assert mind._guide is None and len(server.bodies) == 1


# H6: the one-breath forms only at the start of the sentence, and only asking.
@pytest.mark.parametrize("said", [
    "escribe cuando te diga hola, responde adiós",
    "recuerda que cuando te diga casa, apagues todo",
    "contesta cuando te diga hola que estoy ocupado",
    "every day at 9 you say good morning and never mean it",
])
def test_complaints_and_dictations_are_the_models(tmp_path: Path, said: str) -> None:
    mind, server = _guide_mind(tmp_path, [_say("Vale.")])
    assert mind.decide(1, said)["reply"] == "Vale."
    assert mind._guide is None and len(server.bodies) == 1


@pytest.mark.parametrize(("said", "phrase", "order"), [
    ("desde hoy, cuando te diga recreo, pon la música en pausa", "recreo", "pon la música en pausa"),
    ("a partir de ahora cuando te diga cine, baja el volumen", "cine", "baja el volumen"),
    ("from now on, when I say hush, pause the music", "hush", "pause the music"),
    ("Baxy, hazme una rutina: cuando te diga burbuja, pasa el sonido", "burbuja", "pasa el sonido"),
    ("Baxi, mirá, cuando te diga bafles, cambiá la salida", "bafles", "cambiá la salida"),
])
def test_the_lead_ins_the_contract_names_still_split(tmp_path: Path, said: str, phrase: str, order: str) -> None:
    mind, _ = _guide_mind(tmp_path, [])
    english = "i say" in said.lower()
    assert mind.decide(1, said)["reply"] == (f"When you say «{phrase}»: «{order}». Shall I save it?" if english
                                             else f"Cuando digas «{phrase}»: «{order}». ¿La guardo?")


# H11: the promise at saving says what happens with BAXY closed.
def test_saving_a_timed_routine_says_what_happens_with_baxy_closed() -> None:
    routine = {**WEEKDAYS, "trigger": {"at": "09:55", "repeat": "daily"}}
    said = routine_guide.told(_receipt({"routine": routine, "saved": True, "nextRunLocal": "2026-11-12 09:55",
                                        "scheduledFor": "tomorrow"}), "create", "es")
    # «te lo digo», not «en voz alta»: with BAXY's voice off it is a line in the conversation (second blind review)
    assert said == ("Guardada. Todos los días a las 9:55 de la mañana te lo digo, sin alarma; si BAXY está cerrada, te "
                    "sale un aviso de Windows. La primera vez, mañana a las 9:55 de la mañana.")
    once = {**WEEKDAYS, "trigger": {"at": "09:55", "repeat": "once", "date": "2026-11-12"}}
    said = routine_guide.told(_receipt({"routine": once, "saved": True, "nextRunLocal": "2026-11-12 09:55",
                                        "scheduledFor": "tomorrow"}), "create", "es")
    assert said == ("Guardada. Te lo digo mañana a las 9:55 de la mañana, una sola vez y sin alarma; si BAXY está "
                    "cerrada, te sale un aviso de Windows.")


# Second blind review (REV10): a clear yes or a clear no inside a longer reply is never taken for another request.
@pytest.mark.parametrize("said", ["muy bien, guárdala", "perfect, save it", "of course, save it", "no hay problema, guárdala",
                                  "no problem, save it"])
def test_at_save_it_a_reply_with_its_yes_inside_is_asked_again_never_dropped(tmp_path: Path, said: str) -> None:
    mind, server = _guide_mind(tmp_path, [])
    _talk(mind, ["crea una rutina", "con una palabra", "nube", "pon música"])
    assert mind.decide(5, said)["reply"].startswith(("Di «sí» para guardarla", "Say «yes» to save it"))
    assert mind._guide is not None and mind._guide.step == "confirm" and server.bodies == []


def test_a_time_said_again_is_never_taken_for_another_request(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [])
    said = _talk(mind, ["crea una rutina", "a una hora", "a las 8", "a las 8", "a las 8"])
    assert said[-1]["reply"] == "¿A las 8:00 de la mañana o de la tarde?"
    assert mind._guide is not None and server.bodies == []


def test_a_list_the_app_cut_has_no_fixed_sentence() -> None:
    cut = {"routines": [WEEKDAYS], "count": 1, "routinesShown": 1, "truncated": True}
    assert routine_guide.told(_receipt(cut), "list", "es") is None
    assert routine_guide.told(_receipt({"routines": [WEEKDAYS], "count": 30}), "list", "es") is None


def test_a_guide_dropped_by_silence_tells_the_model_nothing_was_saved(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [_say("No guardé nada.")])
    _talk(mind, ["crea una rutina", "con una palabra", "nube", "pon música"])
    mind._guide_at -= 400
    assert mind.decide(5, "sí")["reply"] == "No guardé nada."
    assert mind._guide is None and len(server.bodies) == 1
    assert any(routine_guide.SILENT_NOTE in str(m.get("content")) for m in server.bodies[0]["messages"][-3:-1])


# H12: the mind folds as the store does (LocalRoutineStore.Folded: NFD without its marks, lower case).
@pytest.mark.parametrize(("one", "other", "same"), [
    ("Straße", "strasse", False), ("ﬁesta", "fiesta", False), ("Canción  ÉL!", "cancion el", True),
    ("AUDÍFONOS", "audifonos", True)])
def test_the_mind_folds_as_the_store(one: str, other: str, same: bool) -> None:
    assert (routines.fold(one) == routines.fold(other)) is same
