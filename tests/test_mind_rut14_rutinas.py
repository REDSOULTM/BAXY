"""RUT14 (the owner's case, 2026-11-13): a routine said naturally. What the person already said is read by the model in a
closed, typed question (routine_fill) and checked against their own words; the guide asks only what is missing, never
compares an answer with fixed words to refuse it, and saves only with their «sí»."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from baxy_mind import routine_fill, routine_guide
from baxy_mind.mind import THEIR_ANSWER_SYSTEM
from test_mind_final import _call, _say
from test_mind_routine_guide import HEADSET, _guide_mind, _receipt

# The owner's words, with another name and another greeting (nothing of theirs is kept in the tree).
FIRST = ("quiero que todos los lunes, miércoles y viernes a las 10 10 de la mañana digas Buenos días, Aurelio, que "
         "tengas una linda jornada")
AGAIN = "Quiero que simplemente los viernes, lunes y miércoles digas eso a las diez de la mañana"
TEXT = "Buenos días, Aurelio, que tengas una linda jornada"
REPEATED = f"Los lunes, miércoles y viernes a las 10:00 de la mañana, te digo: «{TEXT}». ¿La guardo?"
CREATE = {"action": "create", "at": "10:00", "repeat": "days", "days": ["mon", "wed", "fri"], "steps": ["say: " + TEXT]}
SAVED = {"id": "r-00000a", "name": "10:00", "trigger": {"at": "10:00", "repeat": "days", "days": ["mon", "wed", "fri"]},
         "active": True, "steps": [{"say": TEXT}]}


def _read(does: str = "answer", days: tuple | list = (), **fields) -> dict:
    read = {"trigger": "unsaid", "hour": "unsaid", "minute": 0, "half": "unsaid", "repeat": "unsaid",
            "days": " ".join(days), "word": "", "text_from": "last_words", "text": "",
            **fields, "does": does}
    read = {**read, "hour": str(read["hour"]), "minute": str(read["minute"])}   # written as the schema's values
    # RUT15: the fields the model wrote (routine_fill.parsed), for checked
    return {**read, "given": [key for key in ("trigger", "hour", "repeat", "days", "word", "text")
                              if read[key] not in ("unsaid", "")]}


def _compact(read):
    """RUT15: a reading as the model writes it now (routine_fill.SCHEMA): one letter per field, only those it gives,
    the hour from 0 to 23."""
    if not isinstance(read, dict) or "does" not in read:
        return read
    out = {}
    if read.get("trigger") in ("time", "word"):
        out["k"] = read["trigger"]
    if str(read.get("hour", "unsaid")) != "unsaid":
        hour = int(read["hour"])
        hour += 12 if read.get("half") == "pm" and hour < 12 else -12 if read.get("half") == "am" and hour == 12 else 0
        out["h"] = str(hour)
        if str(read.get("minute", "0")) != "0":
            out["m"] = str(read["minute"])
    if read.get("repeat") not in (None, "unsaid"):
        out["r"] = read["repeat"]
    for key, letter in (("days", "d"), ("word", "p"), ("text", "t")):
        if read.get(key):
            out[letter] = read[key]
    out["x"] = read["does"]
    return out


def _is_read(body: dict) -> bool:
    return ((body.get("response_format") or {}).get("json_schema") or {}).get("name") == "rutina"


TIMED = _read(trigger="time", hour=10, half="am", repeat="days", days=["mon", "wed", "fri"], text=TEXT)


def _reading(server, reads: list, yeses: list | None = None) -> None:
    """The fake server answers the routine's typed question with the next of ``reads`` (a dict: its JSON, as the model
    writes it now; a string: as written; an exception: raised) and the closed question of the «sí» with the next of
    ``yeses`` («maybe» with none)."""
    plain, chat = server.ask_apart, server.chat
    server.asked, server.yes_asked = [], []

    def read(body: dict) -> dict:
        server.asked.append(json.loads(json.dumps(body)))
        given = reads.pop(0)
        if isinstance(given, Exception):
            raise given
        return {"choices": [{"message": {"content": json.dumps(_compact(given)) if isinstance(given, dict) else given}}]}

    def ask_apart(body: dict, timeout: float = 60.0) -> dict:
        if _is_read(body):
            return read(body)
        if body["messages"][0]["content"] == THEIR_ANSWER_SYSTEM and yeses is not None:
            server.yes_asked.append(body)
            return {"choices": [{"message": {"content": yeses.pop(0) if yeses else "maybe"}}]}
        return plain(body, timeout)

    def chat_or_read(body: dict, timeout: float = 120.0, gives_way: bool = False) -> dict:
        return read(body) if _is_read(body) else chat(body, timeout, gives_way)

    server.ask_apart, server.chat = ask_apart, chat_or_read


def _opened(tmp_path: Path, reads: list, yeses: list | None = None, routines: list | None = None, replies: list | None = None):
    mind, server = _guide_mind(tmp_path, [_call("baxy_routines", {}), *(replies or [])], routines)
    _reading(server, reads, yeses)
    return mind, server


# ---------------------------------------------------------------------------------------------------------------------
# The owner's dialogue, turn by turn
# ---------------------------------------------------------------------------------------------------------------------

def test_the_owners_dialogue_makes_the_routine_in_three_turns(tmp_path: Path) -> None:
    mind, server = _opened(tmp_path, [TIMED, TIMED])
    first = mind.decide(1, FIRST)
    # what they said is not thrown away: the whole routine back, for their «sí»
    assert first["kind"] == "conversation" and first["reply"] == REPEATED
    second = mind.decide(2, AGAIN)
    # said again in other words: never «No te entendí. Di «con una palabra» o «a una hora»…»
    assert second["kind"] == "conversation" and REPEATED in second["reply"]
    assert "con una palabra" not in second["reply"]
    third = mind.decide(3, "sí")
    assert third["kind"] == "action" and third["operation"] == "baxy.routines" and third["arguments"] == CREATE
    told = mind.continue_turn(4, _receipt({"routine": SAVED, "saved": True}))
    assert told["kind"] == "conversation" and told["reply"].startswith("Guardada. Los lunes, miércoles y viernes a las 10:00")
    assert len(server.bodies) == 1   # the model decided once; the rest was its typed reading and the guide


def test_nothing_is_saved_before_their_yes(tmp_path: Path) -> None:
    mind, _ = _opened(tmp_path, [TIMED, TIMED])
    assert mind.decide(1, FIRST)["kind"] == "conversation"
    assert mind.decide(2, AGAIN)["kind"] == "conversation"
    assert mind._guide is not None and mind._guide.step == "confirm"


def test_the_typed_question_holds_their_words_and_a_schema_any_model_takes(tmp_path: Path) -> None:
    mind, server = _opened(tmp_path, [TIMED])
    mind.decide(1, FIRST)
    body = server.asked[0]
    assert FIRST in body["messages"][-1]["content"]
    schema = body["response_format"]["json_schema"]["schema"]
    assert body["response_format"]["type"] == "json_schema" and "grammar" not in body
    # RUT15: no field is required (only what the words give or change is written), so llama.cpp's grammar keeps the
    # order of the fields and what the words do is still written last
    assert schema["additionalProperties"] is False and "required" not in schema
    # a model by API refuses numeric and list bounds in a structured output, and without them a number or a list never
    # ended for the 4B: every field is a closed list of values or a text
    assert not {"minimum", "maximum", "integer", "array", "maxItems"} & set(json.dumps(schema).replace('"', " ").split())
    assert schema["properties"]["h"]["enum"][:2] == ["0", "1"] and len(schema["properties"]["h"]["enum"]) == 24
    assert len(schema["properties"]["m"]["enum"]) == 60 and schema["properties"]["d"] == {"type": "string"}
    assert list(schema["properties"])[-1] == "x"   # what the words do, after the fields
    # RUT15: at most 64 tokens, so a model by API answers it at its lowest effort (external_model.SHORT_REPLY_TOKENS)
    assert body["max_tokens"] <= 64


def test_the_reading_is_asked_after_the_conversation_the_server_holds(tmp_path: Path) -> None:
    # RUT15: asked apart from the conversation (ask_apart), the slot's state was saved and restored around every
    # reading: 1.3 s of each answer to the guide in Esencial and 2.4 s in Completo (RTX 3060). Asked after the
    # conversation, as a decision sends it, the server reads only what is new and nothing is set aside.
    mind, server = _opened(tmp_path, [TIMED])
    apart: list = []
    plain = server.ask_apart
    server.ask_apart = lambda body, timeout=60.0: apart.append(body) or plain(body, timeout)
    mind.decide(1, FIRST)
    read, decided = server.asked[0], server.bodies[0]
    assert not [body for body in apart if _is_read(body)]
    assert read["messages"][:len(decided["messages"])] == decided["messages"]
    assert read["tools"] == decided["tools"] and read["tool_choice"] == "none"
    assert read["messages"][-1]["role"] == "user" and FIRST in read["messages"][-1]["content"]


def test_a_number_the_ear_wrote_twice_is_told_to_the_model_as_a_datum(tmp_path: Path) -> None:
    mind, server = _opened(tmp_path, [TIMED, TIMED])
    mind.decide(1, FIRST)
    assert "«10» twice in a row" in server.asked[0]["messages"][-1]["content"]
    mind.decide(2, AGAIN)
    assert "twice in a row" not in server.asked[1]["messages"][-1]["content"]


def test_the_owners_later_answers_no_longer_meet_fixed_words(tmp_path: Path) -> None:
    # As the 1.5.2 went: the guide at its first question, and each answer of the owner's after it.
    mind, server = _guide_mind(tmp_path, [])
    _reading(server, [_read(), {**TIMED, "text_from": "before"}])   # the text is of their words before, not of the last
    assert mind.decide(1, "crea una rutina")["reply"] == "¿Con una palabra tuya o a una hora?"
    assert server.asked == []   # the closed order alone says nothing to read
    mind.conversation.insert(0, {"role": "user", "content": FIRST})   # what they had said before
    # «Pues lo que ya te dije antes»: read by the model with the conversation, not «Eso es muy largo…»
    told = mind.decide(2, "Pues lo que ya te dije antes")
    assert "No te entendí" in told["reply"] and "¿Con una palabra tuya o a una hora?" in told["reply"]   # read 1: nothing
    told = mind.decide(3, AGAIN)
    assert told["reply"] == REPEATED


# ---------------------------------------------------------------------------------------------------------------------
# Form stays deterministic: a value the person did not say is not taken
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("said", "read", "asked"), [
    # an hour nobody said
    ("quiero que los lunes me digas ánimo", _read(trigger="time", hour=9, half="am", repeat="days", days=["mon"],
                                                 text="ánimo"), "¿A qué hora?"),
    # the half of the day is asked, never assumed
    ("quiero que todos los días a las 8 me digas ánimo", _read(trigger="time", hour=8, half="am", repeat="daily",
                                                              text="ánimo"), "¿A las 8:00 de la mañana o de la tarde?"),
    # days nobody said
    ("quiero que a las 8 de la mañana me digas ánimo", _read(trigger="time", hour=8, half="am", repeat="daily",
                                                            text="ánimo"), "¿Qué días?"),
    ("quiero que los lunes a las 8 de la mañana me digas ánimo", _read(trigger="time", hour=8, half="am", repeat="days",
                                                                      days=["tue", "thu"], text="ánimo"), "¿Qué días?"),
    # a text that is not their words
    ("quiero que todos los días a las 8 de la mañana me saludes", _read(trigger="time", hour=8, half="am", repeat="daily",
                                                                       text="¡Hola! Que tengas un gran día"),
     "¿Qué quieres que te diga?"),
    # an hour that does not exist
    ("quiero que todos los días a las 8 de la mañana me digas ánimo", _read(trigger="time", hour=28, half="am",
                                                                           repeat="daily", text="ánimo"), "¿A qué hora?"),
])
def test_a_value_the_person_did_not_say_is_asked(tmp_path: Path, said: str, read: dict, asked: str) -> None:
    mind, _ = _opened(tmp_path, [read])
    told = mind.decide(1, said)
    assert told["kind"] == "conversation" and told["reply"].startswith(asked)


@pytest.mark.parametrize(("said", "read", "clock"), [
    ("los martes a las ocho de la noche dime ánimo", {"hour": 8, "half": "pm"}, "20:00"),
    ("los martes a las ocho de la noche dime ánimo", {"hour": 20, "half": "pm"}, "20:00"),
    ("los martes a las 12 de la noche dime ánimo", {"hour": 12, "half": "pm"}, "00:00"),
    ("los martes al mediodía dime ánimo", {"hour": 12, "half": "pm"}, "12:00"),
    ("los martes a las 7:45 a. m. dime ánimo", {"hour": 7, "minute": 45, "half": "am"}, "07:45"),
    ("los martes a las siete y media de la mañana dime ánimo", {"hour": 7, "minute": 30, "half": "am"}, "07:30"),
    ("on Tuesdays at 9 9 in the morning say ánimo", {"hour": 9, "half": "am"}, "09:00"),
])
def test_the_hour_read_is_the_hour_said(said: str, read: dict, clock: str) -> None:
    checked = routine_fill.checked(_read(trigger="time", repeat="days", days=["tue"], text="ánimo", **read), [said])
    assert checked.when is not None and checked.when.clock() == clock and checked.when.days == (1,)
    assert checked.text == "ánimo"


@pytest.mark.parametrize(("said", "known", "read", "days"), [
    # a day left out, or one that is inside the text: not the days they named, so the days are asked
    (["los lunes, miércoles y viernes a las 8 de la mañana dime ánimo"], (), ["wed", "fri"], None),
    (["los lunes a las 8 de la mañana dime que el martes hay reunión"], (), ["mon"], None),
    (["los lunes, miércoles y viernes a las 8 de la mañana dime ánimo"], (), ["mon", "wed", "fri"], (0, 2, 4)),
    (["los lunes, miércoles y viernes a las 8 de la mañana dime ánimo"], (), ["lunes", "miércoles", "viernes"], (0, 2, 4)),
    # with days already known: these too, or those without these
    (["de lunes a viernes a las 8 de la mañana dime ánimo", "espera, que sea también los sábados"], (0, 1, 2, 3, 4),
     ["mon", "tue", "wed", "thu", "fri", "sat"], (0, 1, 2, 3, 4, 5)),
    (["de lunes a viernes a las 8 de la mañana dime ánimo", "los viernes no"], (0, 1, 2, 3, 4),
     ["mon", "tue", "wed", "thu"], (0, 1, 2, 3)),
    (["todos los días menos el domingo a las 8 de la mañana dime ánimo"], (), ["mon", "tue", "wed", "thu", "fri", "sat"],
     (0, 1, 2, 3, 4, 5)),
])
def test_the_days_read_are_the_days_they_named(said: list, known: tuple, read: list, days) -> None:
    checked = routine_fill.checked(_read(trigger="time", hour=8, half="am", repeat="days", days=read, text="ánimo"),
                                   said, known)
    assert checked.when is not None and checked.when.clock() == "08:00"
    assert (checked.when.repeat, checked.when.days) == (("days", days) if days else (None, ()))


def test_a_text_known_changes_only_for_one_of_their_last_words(tmp_path: Path) -> None:
    # «digas eso» points back: RUT15, the model leaves the text out (only what their last words give or change is
    # written) and the text known stays
    pointed = {**TIMED, "text": ""}
    literal = {**TIMED, "text": "eso"}
    changed = {**TIMED, "text": "arriba que se enfría el café"}
    mind, _ = _opened(tmp_path, [TIMED, pointed, literal, changed])
    mind.decide(1, FIRST)
    assert REPEATED in mind.decide(2, AGAIN)["reply"]
    assert "«eso»" in mind.decide(3, AGAIN)["reply"]   # read as a new text of their last words, it is repeated for them to hear
    told = mind.decide(4, "cambia el texto, mejor que diga arriba que se enfría el café")
    assert "te digo: «arriba que se enfría el café». ¿La guardo?" in told["reply"]


def test_a_reply_that_is_not_the_object_asked_reads_nothing() -> None:
    assert routine_fill.parsed({"choices": [{"message": {"content": "maybe"}}]}) is None
    assert routine_fill.parsed({"choices": [{"message": {"content": '{"does": "whatever"}'}}]}) is None
    assert routine_fill.parsed({}) is None


@pytest.mark.parametrize("read", ["no sé", OSError("gone"), {"does": "perhaps"}])
def test_unreadable_the_guide_goes_on_as_before(tmp_path: Path, read) -> None:
    mind, _ = _opened(tmp_path, [read])
    assert mind.decide(1, FIRST)["reply"] == "¿Con una palabra tuya o a una hora?"


# ---------------------------------------------------------------------------------------------------------------------
# Answers to the guide's questions, in any words
# ---------------------------------------------------------------------------------------------------------------------

def test_closed_forms_are_still_the_readers_with_no_model(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [])
    _reading(server, [])
    said = [mind.decide(n, words)["reply"] for n, words in enumerate(
        ["nueva rutina", "a una hora", "a las ocho de la mañana, todos los días"], 1)]
    assert said == ["¿Con una palabra tuya o a una hora?", "¿A qué hora, y qué días?", "¿Qué quieres que te diga?"]
    assert server.asked == []
    assert mind.decide(4, "cancela")["reply"] == "Listo, lo dejo: no guardé ninguna rutina."
    assert server.asked == []


def test_a_long_answer_gives_its_text_and_more(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [])
    _reading(server, [_read(trigger="time", hour=7, minute=30, half="am", repeat="days", days=["sat", "sun"],
                            text="arriba que hay que regar")])
    mind.decide(1, "nueva rutina")
    mind.decide(2, "a una hora")
    asked = mind.decide(3, "a las siete y media de la mañana")
    assert asked["reply"].startswith("¿Qué días?")
    told = mind.decide(4, "pues mira que sea los sábados y los domingos y que me digas arriba que hay que regar")
    assert told["reply"] == ("Los sábados y domingos a las 7:30 de la mañana, te digo: «arriba que hay que regar». "
                             "¿La guardo?")


def test_a_correction_at_the_repetition_changes_it_and_asks_again(tmp_path: Path) -> None:
    nine = {**TIMED, "hour": 9}
    mind, _ = _opened(tmp_path, [TIMED, nine])
    mind.decide(1, FIRST)
    told = mind.decide(2, "no, mejor a las nueve")
    assert told["kind"] == "conversation" and "a las 9:00 de la mañana" in told["reply"] and "¿La guardo?" in told["reply"]
    saved = mind.decide(3, "sí")
    assert saved["kind"] == "action" and saved["arguments"]["at"] == "09:00"


def test_a_yes_in_other_words_saves_only_if_the_closed_question_reads_a_yes(tmp_path: Path) -> None:
    mind, server = _opened(tmp_path, [TIMED, _read("yes", **{k: v for k, v in TIMED.items() if k != "does"})], ["now"])
    mind.decide(1, FIRST)
    saved = mind.decide(2, "eso mismo, así está perfecto, guárdala nomás")
    assert saved["kind"] == "action" and saved["arguments"] == CREATE and len(server.yes_asked) == 1


def test_a_yes_of_the_reading_alone_does_not_save(tmp_path: Path) -> None:
    mind, server = _opened(tmp_path, [TIMED, _read("yes", **{k: v for k, v in TIMED.items() if k != "does"})], ["maybe"])
    mind.decide(1, FIRST)
    told = mind.decide(2, "puede ser, no sé")
    assert told["kind"] == "conversation" and "¿La guardo?" in told["reply"] and mind._guide is not None


def test_the_closed_question_alone_does_not_save_what_the_reading_took_for_no_yes(tmp_path: Path) -> None:
    # RUT14B: the routine said again at «¿La guardo?» is no yes, even if the closed question of the «sí» reads «now»
    # (the owner's «Quiero que simplemente los viernes…»): both readings have to say yes, and SIS3's is not even asked
    mind, server = _opened(tmp_path, [TIMED, TIMED], ["now"])
    mind.decide(1, FIRST)
    told = mind.decide(2, AGAIN)
    assert told["kind"] == "conversation" and "¿La guardo?" in told["reply"] and server.yes_asked == []


def test_a_yes_in_other_words_the_reading_calls_an_answer_saves_if_the_closed_question_reads_a_yes(tmp_path: Path) -> None:
    # RUT14B (measured: «sí, dale», «sure, save it», «yeah go ahead» read as «answer» by the 4B, the routine copied
    # from what was known): words that carry nothing of a routine are asked to SIS3's question of the «sí». RUT15: the
    # model writes only what the words give or change: at «¿La guardo?» 87 readings of c7 wrote no field (85 yes)
    mind, server = _opened(tmp_path, [TIMED, _read()], ["now"])
    mind.decide(1, FIRST)
    saved = mind.decide(2, "sí, dale")
    assert saved["kind"] == "action" and saved["arguments"] == CREATE and len(server.yes_asked) == 1


def test_at_the_repetition_a_second_answer_with_no_yes_ends_it_unsaved_in_baxys_words(tmp_path: Path) -> None:
    # RUT14B (measured: «sure, save it» twice, read «later» by SIS3): handed to the model, the 4B saved a memory and
    # said «Guardado»; at «¿La guardo?» the guide ends with its own «No la guardé.», the model not asked
    copied = {**TIMED, "text_from": "before"}
    mind, server = _opened(tmp_path, [TIMED, copied, copied], ["later", "later"])
    mind.decide(1, FIRST)
    assert "¿La guardo?" in mind.decide(2, "sure, save it")["reply"]
    told = mind.decide(3, "sure, save it")
    assert told == {**told, "kind": "conversation", "reply": "No la guardé."} and mind._guide is None
    assert len(server.bodies) == 1   # only the first decision


def test_a_no_in_other_words_does_not_save(tmp_path: Path) -> None:
    mind, _ = _opened(tmp_path, [TIMED, _read("no", **{k: v for k, v in TIMED.items() if k != "does"})])
    mind.decide(1, FIRST)
    told = mind.decide(2, "uy no, así no la quiero")
    assert told["reply"] == "No la guardé." and mind._guide is None


def test_cancel_in_other_words_leaves_it(tmp_path: Path) -> None:
    mind, _ = _opened(tmp_path, [TIMED, _read("cancel")])
    mind.decide(1, FIRST)
    told = mind.decide(2, "sabes qué, olvídate de la rutina esta")
    assert told["reply"] == "Listo, lo dejo: no guardé ninguna rutina." and mind._guide is None


def test_words_about_something_else_are_the_models_turn_at_once(tmp_path: Path) -> None:
    mind, server = _opened(tmp_path, [TIMED, _read("other")], replies=[_say("Son las cinco. La rutina no se guardó.")])
    mind.decide(1, FIRST)
    told = mind.decide(2, "oye y qué hora es ahora mismo")
    assert told["reply"] == "Son las cinco. La rutina no se guardó." and mind._guide is None
    notes = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "user"]
    assert any(routine_guide.LEFT_NOTE in note for note in notes)


def test_a_second_answer_that_adds_nothing_is_the_models_turn(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [_say("No guardé la rutina. ¿Qué necesitas?")])
    _reading(server, [_read(), _read()])
    mind.decide(1, "nueva rutina")
    again = mind.decide(2, "pues no sé, lo que tú veas mejor para mí")
    assert again["reply"] == "No te entendí. ¿Con una palabra tuya o a una hora?"   # asked again once
    left = mind.decide(3, "ya te lo dije, como tú quieras hacerlo")
    assert left["reply"] == "No guardé la rutina. ¿Qué necesitas?" and mind._guide is None


def test_asked_again_it_says_what_there_is_so_far(tmp_path: Path) -> None:
    half = _read(trigger="time", repeat="days", days=["mon", "wed"], text="a estirar")
    mind, _ = _opened(tmp_path, [half, half])
    first = mind.decide(1, "quiero que los lunes y miércoles me digas a estirar")
    assert first["reply"] == "¿A qué hora?"
    again = mind.decide(2, "pues cuando me toque el descanso")
    assert again["reply"] == "Tengo: los lunes y miércoles y decir «a estirar». ¿A qué hora?"


# ---------------------------------------------------------------------------------------------------------------------
# A routine of a word said in one breath that its form does not split
# ---------------------------------------------------------------------------------------------------------------------

def test_a_word_routine_said_naturally_is_repeated_whole(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [])
    _reading(server, [_read(trigger="word", word="hora de trabajar", text="abras el correo y subas el volumen")])
    told = mind.decide(1, "cuando yo diga hora de trabajar quiero que abras el correo y subas el volumen")
    assert told["reply"] == "Cuando digas «hora de trabajar»: «abras el correo y subas el volumen». ¿La guardo?"
    saved = mind.decide(2, "sí")
    assert saved["arguments"] == {"action": "create", "phrase": "hora de trabajar",
                                  "order": "abras el correo y subas el volumen"}
    assert server.bodies == []


def test_a_form_that_split_cleanly_is_not_read_again(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [])
    _reading(server, [])
    told = mind.decide(1, "cuando te diga cine, pausa la música")
    assert told["reply"] == "Cuando digas «cine»: «pausa la música». ¿La guardo?" and server.asked == []


def test_a_phrase_taken_read_by_the_model_is_said_taken_and_stays(tmp_path: Path) -> None:
    taken = _read(trigger="word", word="audífonos", text="pon la radio")
    mind, _ = _opened(tmp_path, [taken, taken], routines=[HEADSET])
    told = mind.decide(1, "quiero que si digo audífonos pongas la radio, ¿se puede?")
    assert told["reply"] == "Ya tienes una rutina con «audífonos». Dime otra palabra, o «cancela»."
    again = mind.decide(2, "pero es que yo quiero audífonos, pon la radio")
    assert again["reply"].startswith("Ya tienes una rutina con «audífonos».") and mind._guide is not None


# ---------------------------------------------------------------------------------------------------------------------
# RUT14B: what a blind review of RUT14's design found (each failed before its fix)
# ---------------------------------------------------------------------------------------------------------------------

def test_a_refused_order_at_the_repetition_asks_for_it_and_no_yes_saves_what_was_never_read_back(tmp_path: Path) -> None:
    first = _read(trigger="word", word="hora de trabajar", text="abras el correo")
    second = _read(trigger="word", word="a currar", text="borra la rutina cine")
    mind, server = _guide_mind(tmp_path, [])
    _reading(server, [first, second])
    mind.decide(1, "cuando yo diga hora de trabajar quiero que abras el correo")
    told = mind.decide(2, "no, mejor que la palabra sea a currar y que borra la rutina cine")
    assert "¿La guardo?" not in told["reply"] and mind._guide is not None and mind._guide.step == "order"
    assert mind.decide(3, "vale")["kind"] == "conversation"   # «vale» is no order of a routine: nothing saved


@pytest.mark.parametrize(("said", "repeat"), [
    ("quiero que a las 8 de la mañana me digas ánimo", "tomorrow"),   # «de la mañana» is no «mañana»
    ("quiero que a las once de la mañana me digas ánimo", "once"),    # «once» there is eleven
])
def test_a_day_is_read_from_the_time_said_whole_not_from_a_word_of_it(said: str, repeat: str) -> None:
    checked = routine_fill.checked(_read(trigger="time", hour=8 if "8" in said else 11, half="am", repeat=repeat,
                                         text="ánimo"), [said])
    assert checked.when is not None and checked.when.repeat is None and checked.when.offset is None


@pytest.mark.parametrize(("said", "read", "clock"), [
    # a half of the day said only inside the text: the one said with the hour stays (it was 20:00)
    ("todos los días a las 8 de la mañana dime que no llegue tarde", {"hour": 8, "half": "pm", "text": "que no llegue tarde"},
     "08:00"),
    # an hour said only inside the text (it was 02:00): asked
    ("todos los días a las 8 de la mañana dime toma 2 pastillas", {"hour": 2, "half": "am", "text": "toma 2 pastillas"}, None),
    # minutes said and read as none (it was 08:00): asked
    ("todos los días a las ocho y media de la mañana dime ánimo", {"hour": 8, "minute": 0, "half": "am", "text": "ánimo"},
     None),
    # a half of the day assumed for an hour said without one (it was 20:00): asked
    ("todos los días a las 8 dime ánimo", {"hour": 20, "half": "pm", "text": "ánimo"}, None),
])
def test_the_time_read_is_the_time_said_together_not_words_of_the_text(said: str, read: dict, clock) -> None:
    checked = routine_fill.checked(_read(trigger="time", repeat="daily", **read), [said])
    assert checked.when is not None and checked.when.repeat == "daily"
    assert checked.when.clock() == clock


def test_a_day_at_the_end_of_what_was_heard_does_not_fail_the_turn(tmp_path: Path) -> None:
    said = "quiero que a las 8 de la mañana me digas ánimo de lunes a"
    mind, _ = _opened(tmp_path, [_read(trigger="time", hour=8, half="am", repeat="days", days=["mon"], text="ánimo")])
    told = mind.decide(1, said)   # it raised IndexError: the turn failed
    assert told["kind"] == "conversation" and told["reply"].startswith("Los lunes a las 8:00 de la mañana")


def test_what_rings_while_a_routine_is_made_is_answered_as_before(tmp_path: Path) -> None:
    ring = [{"id": "a-1", "kind": "alarm", "title": "", "clock": "07:00"}]
    mind, server = _guide_mind(tmp_path, [_say("MODEL TURN")] * 2)
    _reading(server, [_read("other")])
    mind.decide(1, "nueva rutina")
    mind.decide(2, "a una hora")
    told = mind.decide(3, "apágala", ringing=ring)
    assert told["kind"] == "action" and told["operation"] == "schedule.alarms"
    assert mind._guide is not None and mind._guide.step == "when" and server.asked == []


def test_an_answer_that_moved_the_routine_starts_the_count_and_the_silence_again(tmp_path: Path, monkeypatch) -> None:
    import time as clock_module
    clock = [1000.0]
    monkeypatch.setattr(clock_module, "monotonic", lambda: clock[0])
    mind, server = _guide_mind(tmp_path, [_say("MODEL TURN")])
    _reading(server, [_read(), _read()])
    mind.decide(1, "nueva rutina")
    clock[0] = 1010.0
    assert mind.decide(2, "pues no sé, lo que tú veas")["reply"].startswith("No te entendí")
    clock[0] = 1020.0
    assert mind.decide(3, "a una hora")["reply"] == "¿A qué hora, y qué días?"
    assert mind._guide_at == 1020.0 and mind._guide.unread == 0
    clock[0] = 1030.0
    told = mind.decide(4, "cuando me levante")   # the first that adds nothing at this step: asked again, not left
    assert mind._guide is not None and "¿A qué hora" in told["reply"]


# ---------------------------------------------------------------------------------------------------------------------
# RUT15: with the language set to English (ING5)
# ---------------------------------------------------------------------------------------------------------------------

EN_FIRST = ("I want you to cheer me up on mondays, wednesdays and fridays at 10 10 in the morning, saying good morning "
            "Aurelio, have a great day")
EN_TEXT = "good morning Aurelio, have a great day"
EN_TIMED = _read(trigger="time", hour=10, half="am", repeat="days", days=["mon", "wed", "fri"], text=EN_TEXT)


def test_in_english_the_guide_its_reading_and_the_yes_question_are_english(tmp_path: Path) -> None:
    # RUT14B: «sure, save it» and «yeah go ahead» were read «later» by the closed question of the «sí», which got
    # «¿La guardo?» in Spanish. With the setting in English the guide asks and repeats in English, the typed reading
    # the model gets has no Spanish (ING5: not a word of Spanish in what the model reads), and so the question of the
    # «sí» is English too.
    from baxy_mind import harness_language
    from test_mind_harness_language import ACCENTS, WORDS
    assert harness_language.use("en")   # the App's catalog.configure «lang» (Mind.use_language)
    try:
        mind, server = _opened(tmp_path, [EN_TIMED, _read()], ["now"])
        mind.lang = "en"   # the App's turn.decide «lang», UiLanguage.Current as the setting
        first = mind.decide(1, EN_FIRST)
        assert first["reply"].endswith(f"I'll tell you: «{EN_TEXT}». Shall I save it?")
        read = json.dumps(server.asked[0]["messages"], ensure_ascii=False)
        assert not ACCENTS.search(read), ACCENTS.findall(read)
        assert not WORDS.search(read), WORDS.findall(read)
        said = mind.decide(2, "sure, save it")
        assert said["kind"] == "action" and said["operation"] == "baxy.routines"
        assert "Shall I save it?" in json.dumps(server.yes_asked[0]["messages"], ensure_ascii=False)
    finally:
        harness_language.use("es")


def _alarm_receipt(recurrence: str | None, kind: str = "reminder", title: str = "Buenos días, Aurelio") -> str:
    observed = {"kind": kind, "title": title, "dueUtc": "2026-11-16T13:10:00+00:00", "dueLocal": "2026-11-16 10:10",
                "scheduledFor": "Monday 2026-11-16", **({"recurrence": recurrence} if recurrence else {})}
    return json.dumps({"status": "completed", "verification": "readback", "observed": observed})


@pytest.mark.parametrize(("recurrence", "kind", "said", "routine"), [
    ("daily", "reminder", "«Recordatorio: Buenos días, Aurelio»; se repite todos los días, los siete de la semana", True),
    ("daily", "alarm", "«Alarma de las 10:10: Buenos días, Aurelio»; se repite todos los días", True),
    ("hourly", "reminder", "«Recordatorio: Buenos días, Aurelio»; se repite cada hora", False),
    (None, "reminder", None, False),
])
def test_a_repeating_alarm_says_what_it_will_do_and_that_a_text_on_some_days_is_a_routine(
        tmp_path: Path, recurrence, kind, said, routine) -> None:
    # RUT15: with the owner's «todos los lunes, miércoles y viernes a las 10 de la mañana digas Buenos días…» the 4B in
    # Esencial set a daily reminder (9 of 10) and said «cada lunes, miércoles y viernes… diga…». The result's facts line
    # says what it will do: a tone and its words, every day of the week; and that a text said on some days is a routine.
    call = {"action": "create", "kind": kind, "title": "Buenos días, Aurelio", "at": "10:10",
            **({"recurrence": recurrence} if recurrence else {})}
    # RUT16: «said_days» holds the first create (daily, or once on a day not named) and the same call again runs.
    mind, server = _guide_mind(tmp_path, [_call("schedule_alarms", call), _call("schedule_alarms", call), _say("Listo.")])
    assert mind.decide(1, FIRST)["kind"] == "action"
    mind.continue_turn(2, _alarm_receipt(recurrence, kind))
    facts = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    facts = facts[facts.index("[En este turno:"):]
    assert (said in facts) if said else ("se repite" not in facts and "timbre" not in facts)
    assert ("es una rutina (baxy_routines)" in facts) is routine


def test_a_day_said_instead_of_another_one_known_is_taken() -> None:
    # RUT15 (held-out of vague phrases, w21): «los sábados… dime que llame a mi madre», then «Espera, los sábados no,
    # los domingos»: the model read Sunday, and the days allowed were those named (Saturday and Sunday), those with the
    # known and those without them (nothing): Sunday alone was refused and BAXY read Saturday back again.
    first = "Los sábados a las nueve y cuarto de la noche dime que llame a mi madre"
    again = "Espera, los sábados no, los domingos. La hora sí."
    read = _read(trigger="time", hour=21, half="pm", minute=15, repeat="days", days=["sun"], text="que llame a mi madre")
    checked = routine_fill.checked(read, [first, again], (5,))
    assert checked.when is not None and checked.when.days == (6,)
    # a day nobody named is still not taken
    other = routine_fill.checked({**read, "days": "mon"}, [first, again], (5,))
    assert other.when is None or other.when.days != (0,)


def test_a_no_with_the_text_said_again_is_never_saved_even_if_the_closed_question_reads_now(tmp_path: Path) -> None:
    # RUT15 (held-out of vague phrases, w09, persona that corrects): at «¿La guardo?», «no, Mete el pollo en el horno.».
    # The model wrote again the text it had («meta…») and called the words an answer; that text is not of their last
    # words, so by form the words carried nothing of a routine (Read.bare), SIS3 was asked and read «now»: saved with no
    # «sí». A reading that writes a field of the routine is no bare yes.
    first = "hoy a las seis y cuarenta de la tarde dime meta el pollo en el horno"
    timed = _read(trigger="time", hour=6, minute=40, half="pm", repeat="today", text="meta el pollo en el horno")
    again = _read(text="meta el pollo en el horno")
    mind, server = _opened(tmp_path, [timed, again], ["now"])
    assert "¿La guardo?" in mind.decide(1, first)["reply"]
    told = mind.decide(2, "no, Mete el pollo en el horno.")
    assert told["kind"] == "conversation" and "Guardada" not in told["reply"]
    assert server.yes_asked == []
