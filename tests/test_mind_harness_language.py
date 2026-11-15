"""ING5 (owner's decision of 2026-11-13): the language is a setting, Spanish or English, and choosing it changes every
rule BAXY reads. Asked in English, BAXY answered in English 17 times of 120 on the 1.5.2: the model answers in the
language of the last thing it reads, and everything the mind wrote for it was Spanish. A datum of the person's
language written into one turn moved the decision to call (ING2, ING3, ING4), so the whole harness is written in
the language chosen (harness_language): in Spanish every text is the one that was written, and in English none of
what the model reads is Spanish. See INFORME_ING5."""
import ast
import json
import re
from pathlib import Path
from typing import Any, Iterator

import pytest

from baxy_mind import answer_check, answer_grounding, behavior, harness_language, routine_fill, routine_guide, web_focus
from baxy_mind import mind as mind_module
from test_mind_final import _call, _mind, _say

MODULES = (behavior, mind_module, answer_check, answer_grounding, web_focus, routine_guide, routine_fill)
DATA = json.loads((Path(mind_module.__file__).with_name("data") / "harness.en.v1.json").read_text(encoding="utf-8"))
ENGLISH = {spanish: english for spanish, english in DATA["texts"]}
# Letters and signs only Spanish writes, and words no English sentence of the harness has.
ACCENTS = re.compile(r"[áéíóúñ¿¡]")
# Names of their own, written so in English too: an example of the tools' texts names a person, a city or a game.
NAMES = re.compile("Pokémon|Lucía|Valparaíso")
WORDS = re.compile(r"\b(?:el|los|las|que|del|una|con|para|por|su|tu|esta|este|sin|hay|turno|herramienta|persona|"
                   r"llamada|ninguna|hora local|reloj|nota interna|ayuda|aún|se ejecutó)\b", re.IGNORECASE)
PAGE = {"url": "https://example.org/rfc"}
DONE = json.dumps({"status": "completed", "verification": "readback", "text": "The page lists the error codes."})
CATALOG = {"capabilities": [
    {"name": "web.fetch", "description": "Lee una página.", "group": "Web y navegador",
     "argumentsSchema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
    {"name": "audio.mute", "description": "Silencia el sonido.", "group": "Música y audio",
     "argumentsSchema": {"type": "object", "properties": {}}}], "baxyVersion": "1.5.2"}


@pytest.fixture(autouse=True)
def _back_to_spanish() -> Iterator[None]:
    yield
    harness_language.use("es")


def _accents(text: str) -> list[str]:
    """The Spanish letters and signs of a text, its proper names apart."""
    return ACCENTS.findall(NAMES.sub("", text))


def _texts(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _texts(key)
            yield from _texts(item)
    elif isinstance(value, (tuple, list, set, frozenset)):
        for item in value:
            yield from _texts(item)


def _constants(module: Any) -> dict[str, Any]:
    return {name: value for name, value in vars(module).items()
            if isinstance(value, (str, tuple, list, dict, set, frozenset, re.Pattern)) and not name.startswith("__")}


def _read(body: dict) -> str:
    """Everything a request gives the model to read: the system text, the tools and the conversation."""
    return json.dumps({"messages": body["messages"], "tools": body.get("tools")}, ensure_ascii=False)


def _session(tmp_path: Path, language: str | None) -> list[dict]:
    """A turn with a call and its receipt and a second turn in words, with the harness as the App's catalog sets it."""
    mind, server = _mind(tmp_path, [_call("web_fetch", PAGE), _say("It lists the error codes."), _say("Sure.")])
    mind.configure(CATALOG if language is None else {**CATALOG, "lang": language})
    mind.decide(1, "Can you read the page at example.org and tell me what it says about the error codes?")
    mind.continue_turn(2, DONE)
    mind.decide(3, "thanks")
    return server.bodies


def test_in_spanish_every_text_is_the_one_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The guarantee that Spanish does not change: with the language in Spanish, said or not, and back from English,
    # every constant of the mind is the value it was written with and a session reads the same bodies.
    monkeypatch.setattr(mind_module.Mind, "_clock_time",
                        staticmethod(lambda: "22:30 hora local, UTC-03:00, Thursday 2026-11-12"))
    before = {module.__name__: _constants(module) for module in MODULES}
    plain = [_read(body) for body in _session(tmp_path / "a", None)]
    assert [_read(body) for body in _session(tmp_path / "b", "es")] == plain
    assert harness_language.use("en") and harness_language.use("es")
    assert {module.__name__: _constants(module) for module in MODULES} == before
    assert [_read(body) for body in _session(tmp_path / "c", "es")] == plain


def test_in_spanish_the_harness_is_spanish(tmp_path: Path) -> None:
    bodies = _session(tmp_path, "es")
    assert "[Reloj:" in _read(bodies[0]) and "\\n[En este turno: web_fetch → " in _read(bodies[1])
    assert mind_module.SYSTEM.startswith("Eres BAXY y sólo BAXY")


def test_in_english_the_model_reads_no_spanish(tmp_path: Path) -> None:
    bodies = _session(tmp_path, "en")
    assert harness_language.current() == "en"
    for body in bodies:
        read = _read(body)
        assert not ACCENTS.search(read), ACCENTS.findall(read)
        assert not WORDS.search(read), WORDS.findall(read)
    first, second = _read(bodies[0]), _read(bodies[1])
    assert "[Clock:" in first and "[Reloj:" not in first
    assert "\\n[In this turn: web_fetch → " in second
    assert bodies[0]["messages"][0]["content"].startswith("You are BAXY and only BAXY")
    assert "Web and browser; Music and audio" in bodies[0]["messages"][0]["content"]


def test_in_english_an_update_and_a_repeating_alarm_read_no_spanish(tmp_path: Path) -> None:
    # INT36C: the 1.5.3 joins aut1 («actualízate» with no window) and rut15 (an alarm's receipt says what it will do):
    # their turns, a baxy_update check and install and a daily alarm with what it will say, read no Spanish either.
    newer = json.dumps({"status": "completed", "verification": "readback", "observed": {
        "installed": "1.5.2", "checked": True, "updatedBy": "github", "latest": "1.5.3", "newer": True}})
    started = json.dumps({"status": "completed", "verification": "readback", "observed": {
        "installed": "1.5.2", "checked": True, "latest": "1.5.3", "installerStarted": True, "appExitRequested": True,
        "delivered": True, "authority": "baxy_update_installer_started"}})
    alarm = json.dumps({"status": "completed", "verification": "readback", "observed": {
        "kind": "reminder", "title": "Good morning, Aurelio", "dueUtc": "2026-11-16T13:10:00+00:00",
        "dueLocal": "2026-11-16 10:10", "scheduledFor": "Monday 2026-11-16", "recurrence": "daily"}})
    # INT36E: with rut16 joined, a daily alarm on «every monday» is held once by «said_days»; its data, and the line of
    # the held call, read no Spanish either, and the same call again sets it.
    daily = _call("schedule_alarms", {"action": "create", "kind": "reminder", "at": "10:10",
                                      "title": "Good morning, Aurelio", "recurrence": "daily"})
    mind, server = _mind(tmp_path, [_call("baxy_update", {"action": "check"}), _call("baxy_update", {"action": "install"}),
                                    _say("Updating now."), daily, daily, _say("Done.")])
    mind.configure({**CATALOG, "lang": "en"})
    mind.wire_to_op = {**mind.wire_to_op, "baxy_update": "baxy.update", "schedule_alarms": "schedule.alarms"}
    mind.decide(1, "BAXY, update yourself")
    mind.continue_turn(2, newer)
    mind.continue_turn(3, started)
    mind.decide(4, "every monday at ten past ten in the morning say good morning Aurelio")
    mind.continue_turn(5, alarm)
    assert len(server.bodies) == 6 and "rings on all seven days" in _read(server.bodies[4])
    for body in server.bodies:
        read = _read(body)
        assert not ACCENTS.search(NAMES.sub("", read)), ACCENTS.findall(read)
        assert not WORDS.search(read), WORDS.findall(read)
    last = _read(server.bodies[-1])
    assert "it repeats every day" in last and "baxy_update" in _read(server.bodies[2])


def test_every_listed_constant_is_english_in_english() -> None:
    harness_language.use("en")
    for module, names in DATA["constants"].items():
        home = __import__(f"baxy_mind.{module}", fromlist=[module])
        for name in names:
            for text in _texts(getattr(home, name)):
                assert not _accents(text), (module, name, text[:80])


def test_what_the_mind_builds_from_its_texts_is_built_again() -> None:
    harness_language.use("en")
    system = mind_module.SYSTEM
    assert system == behavior.head(behavior.factory()) + mind_module.RULES and not ACCENTS.search(system)
    assert mind_module._ASKED_IF_DONE in system and mind_module._REPEAT in system and mind_module._CAN_DO in system
    assert mind_module._ASKED_IF_DONE not in mind_module.BEAT_SYSTEM and not ACCENTS.search(mind_module.BEAT_SYSTEM)
    assert mind_module.DOUBT_NOTE.startswith(mind_module.DOUBT_ASKED) and mind_module.DOUBT_ASKED
    assert mind_module.DOUBT_OTHER_ASKED in mind_module.DOUBT_OTHER_NOTE
    assert mind_module.DOUBT_NOTE.endswith(mind_module.ASK_ONLY)
    assert mind_module._READ_KEPT.search(mind_module.OUTPUT_READ)
    for refusal in (mind_module.WAITS_FOR_YES, mind_module.SAME_CALL_REFUSED, mind_module.CLOSE_REFUSED):
        assert refusal.startswith(mind_module.GIST_NOT_RUN)


def test_every_text_written_in_a_function_has_its_english() -> None:
    for module in MODULES:
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_t":
                text = node.args[0]
                assert isinstance(text, ast.Constant) and isinstance(text.value, str), (module.__name__, node.lineno)
                assert text.value in ENGLISH, (module.__name__, node.lineno, text.value[:80])
                assert not ACCENTS.search(ENGLISH[text.value]), (module.__name__, node.lineno)


def test_a_text_and_its_english_carry_the_same_fields() -> None:
    field = re.compile(r"\{[a-z_0-9]*\}")
    for spanish, english in DATA["texts"]:
        assert sorted(field.findall(spanish)) == sorted(field.findall(english)), spanish[:80]
        assert spanish[:1].isspace() == english[:1].isspace() and spanish[-1:].isspace() == english[-1:].isspace()
        assert spanish.count("\n") == english.count("\n"), spanish[:80]


def test_the_tools_examples_are_english_in_english(tmp_path: Path) -> None:
    mind, _ = _mind(tmp_path, [])
    spanish = dict(mind.english)
    mind.configure({**CATALOG, "lang": "en"})
    assert set(mind.english) == set(spanish) and mind.english != spanish
    for name, text in mind.english.items():
        assert not _accents(text), (name, _accents(text))
    for name, arguments in mind.arguments.items():
        for text in arguments.values():
            assert not _accents(text), name


def test_a_change_of_language_starts_the_conversation_anew(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_say("Hola."), _say("Hi.")])
    mind.configure(CATALOG)
    mind.decide(1, "hola")
    assert mind.conversation
    mind.configure({**CATALOG, "lang": "en"})
    assert mind.conversation == []
    mind.decide(2, "hello")
    assert "hola" not in _read(server.bodies[-1]).lower()
    mind.configure({**CATALOG, "lang": "en"})  # the same language again: the conversation goes on
    assert mind.conversation


def test_a_session_kept_in_the_other_language_is_not_read(tmp_path: Path) -> None:
    mind, _ = _mind(tmp_path, [_say("Hola."), _say("Hi.")])
    mind.configure(CATALOG)
    mind.decide(1, "hola")
    kept = mind.export_session()
    assert "lang" not in kept[-1]  # a Spanish session is kept as it always was
    mind.configure({**CATALOG, "lang": "en"})
    mind.load_session(kept)
    assert mind.conversation == []
    mind.decide(2, "hello")
    english = mind.export_session()
    assert english[-1]["lang"] == "en"
    mind.load_session(english)
    assert mind.conversation
    mind.configure({**CATALOG, "lang": "es"})
    mind.load_session(english)
    assert mind.conversation == []


def test_a_word_that_is_no_language_changes_nothing(tmp_path: Path) -> None:
    mind, _ = _mind(tmp_path, [])
    mind.configure({**CATALOG, "lang": "fr"})
    assert harness_language.current() == "es"
    assert not harness_language.use("es") and not harness_language.use("")


def test_in_english_the_rule_of_how_it_replies_names_the_language() -> None:
    # The one pair that is not a translation: word for word («the person's language (neutral Spanish, English or
    # Spanglish)») the 4B answered in English 52 times of 120 with no Spanish in what it read; naming the language of
    # the setting, 59 of 60 (INFORME_ING5). In Spanish the rule is the one it always was.
    spanish = behavior.REPLIES
    assert spanish.startswith("Hablas en el idioma de la persona (español neutro, inglés o spanglish)")
    harness_language.use("en")
    assert behavior.REPLIES.startswith("You speak English, ")
    assert "Spanish" not in mind_module.SYSTEM
    harness_language.use("es")
    assert behavior.REPLIES is spanish



def test_in_english_the_note_after_its_own_question_says_what_a_no_does() -> None:
    # Word for word («If what follows answers it, go on with that») a short «no» to BAXY's own question ended in the
    # thing it had offered 24 times of 50 (the 1.5.2 with the same English phrases: 7); saying what a no does, 11 of 50
    # with every yes still done, 15 of 15 (INFORME_ING5 §4.8.1). In Spanish the note is the one it always was.
    spanish = mind_module.OFFERED_NOTE
    assert "Si lo que sigue la contesta, sigue con eso;" in spanish
    harness_language.use("en")
    assert "a plain no means no tool call this turn" in mind_module.OFFERED_NOTE
    harness_language.use("es")
    assert mind_module.OFFERED_NOTE is spanish
