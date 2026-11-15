"""ING5B (owner's decision, ENCARGO_ING5 and ENCARGO_ING5B: «en modo inglés tiene que proteger igual»): with the
language set to English the model answers in English, and the answer check read mostly the Spanish forms of a claim
(«cerré», «ya estaba», «no encontré», «por ciento»). Each rule that has an English form here is read with it when the
harness is in English (harness_language, a setting: never guessed from the answer), beside its Spanish forms; with
the harness in Spanish the check is the very one it was, so each case below is also read in Spanish and finds what
it found before these forms existed. The App's view carries its own marks in English then («(text cut off: »,
«Text <label>: », «Controls»), and the check reads them in that language."""
import json
import re
from collections.abc import Callable
from typing import Iterator

import pytest

from baxy_mind import answer_check, harness_language
from baxy_mind.answer_check import check
from baxy_mind.mind import COMPLETED_OUTCOMES, _outcome
from test_answer_check import _mode, _saving, _view as _titled, _written

READS = {"window.application.status", "file.read", "filesystem.list", "file.find", "input.visible.controls",
         "system.status", "audio.status", "memory.recall"}
DONE = {"status": "completed", "verification": "readback"}
FAILED = {"status": "failed", "error": "window_not_found"}
SPANISH = re.compile(r"[áéíóúñ¿¡«»]|\b(?:el|la|los|las|que|del|una|con|para|por|sin|hay|turno|herramienta|persona|llamada|"
                     r"ninguna|resultado|ya estaba|no se)\b", re.IGNORECASE)


@pytest.fixture(autouse=True)
def _back_to_spanish() -> Iterator[None]:
    yield
    harness_language.use("es")


def _r(op: str, facts: dict, arguments: dict | None = None) -> dict:
    """A receipt as the mind builds it (Mind._receipt), from a result's JSON, in the language in use."""
    observation = json.dumps(facts, ensure_ascii=False)
    read = op in READS
    outcome = _outcome(observation, read=read)
    completed = outcome.startswith(harness_language.said(COMPLETED_OUTCOMES))
    return {"op": op, "tool": op.replace(".", "_"), "arguments": arguments or {}, "observation": observation,
            "outcome": outcome, "completed": completed, "read": read}


def _view(note: str = "", text: str = "Text center: Close | 800 × 600") -> dict:
    return {"status": "completed", "verification": "output_only",
            "view": "Window «Untitled - Paint.NET» (paintdotnet, window 7), in front\n"
                    f"Controls:\n[0] Button «Close» (top)\n[1] Button «Save» (top)\n{text}\n{note}\n"}


LISTED = {"status": "completed", "verification": "output_only", "observed": {"mode": "name", "count": 1, "files": [
    {"name": "minutes_draft.odt", "folder": "documents", "relativePath": "work\\minutes_draft.odt"}]}}
# (the rule, the answer, what the person said, the turn's calls as (operation, the result's facts), the session: None
# for «the turn's own calls»)
CASES: list[tuple[str, str, str, list[tuple[str, dict]], list | None]] = [
    # An act told done that did not complete, kind by kind (the English simple past and perfect of each kind).
    ("not_completed", "I've muted the sound.", "mute the sound", [("audio.mute", FAILED)], None),
    ("not_completed", "I turned the volume up.", "turn it up", [("audio.volume.adjust", FAILED)], None),
    ("not_completed", "I've typed your message into Notepad.", "type hello", [("input.text.type", FAILED)], None),
    ("not_completed", "I moved the file to Documents.", "move it", [("filesystem.known.move", FAILED)], None),
    ("not_completed", "I've minimized the window.", "minimize it", [("window.minimize", FAILED)], None),
    ("not_completed", "I paused the music.", "pause the music", [("media.control", FAILED)], None),
    ("not_completed", "I've launched the game.", "launch the game", [("game.launch", FAILED)], None),
    ("not_completed", "I've marked the task as done.", "mark it done", [("task.complete", FAILED)], None),
    ("not_completed", "I turned Bluetooth off.", "turn bluetooth off", [("bluetooth.set", FAILED)], None),
    ("not_completed", "I've now closed Paint.", "close paint", [("app.close", FAILED)], None),
    # Its passive and state forms, read only against a call of the kind that did not complete.
    ("not_completed", "Paint has been closed.", "close paint", [("app.close", FAILED)], None),
    ("not_completed", "Paint is now closed.", "close paint", [("app.close", FAILED)], None),
    ("not_completed", "The note was created.", "make a note", [("note.create", FAILED)], None),
    # With no call at all.
    ("not_completed", "I've set the brightness to 40.", "set the brightness to 40", [("display.brightness.set", FAILED)],
     None),
    ("no_call", "I've just paused the music.", "pause the music", [], []),
    ("no_call", "I muted the microphone.", "mute my microphone", [], []),
    # «Yes» to «did you open…?» and a state told with nothing called.
    ("implied_yes", "Yes, Spotify is open with one window.", "did you open Spotify?",
     [("window.application.status", {"status": "completed", "verification": "output_only",
                                     "observed": {"hasVisibleWindow": True, "visibleWindowCount": 1}})], None),
    ("unread_state", "No, Notepad is still open. Do you want me to close it?", "have you closed the notepad I asked for?",
     [], []),
    # «It was already…» after a call that changed it.
    ("already", "The sound was already muted.", "mute", [("audio.mute", {**DONE, "observed": {"muted": True}})], None),
    ("already", "There was no need to change anything.", "mute", [("audio.mute", {**DONE, "observed": {"muted": True}})],
     None),
    # A level or a percentage that is not the reading.
    ("number", "The battery is at 0.69 percent.", "battery?",
     [("system.status", {**DONE, "observed": {"percent": 69}})], None),
    ("number", "I turned the volume up and it is now at 30.", "volume up",
     [("audio.volume.adjust", {**DONE, "observed": {"level": 40}})], None),
    # «I couldn't find X» of a file a search of the turn listed.
    ("found", "I couldn't find minutes_draft.odt in your folders.", "find minutes_draft.odt", [("file.find", LISTED)], None),
    ("found", "I did not find the file minutes_draft.odt.", "find minutes_draft.odt", [("file.find", LISTED)], None),
    # An absence told over a view the App cut, with the App's marks in English.
    ("partial", "There is nothing written on the board, Paint.NET is blank.", "what does it say?",
     [("input.visible.controls", _view("(text cut off: 3 lines read are not listed, for being long or past the cap)"))],
     None),
]


def _check(answer: str, request: str, calls: list[tuple[str, dict]], session: list | None) -> list[dict]:
    receipts = [_r(op, facts) for op, facts in calls]
    told = [(r["op"], r["completed"], r["read"]) for r in receipts] if session is None else session
    return check(answer, request, receipts, told)


@pytest.mark.parametrize("rule,answer,request_,calls,session", CASES)
def test_in_english_each_rule_reads_the_english_form_of_its_claim(rule: str, answer: str, request_: str,
                                                                   calls: list, session: list | None) -> None:
    harness_language.use("en")
    findings = _check(answer, request_, calls, session)
    assert rule in [f["rule"] for f in findings], findings
    # What the model reads of a finding is its fact (mind.CHECK_NOTE): in English, none of it is Spanish.
    for finding in findings:
        assert not SPANISH.search(finding["fact"]), finding


@pytest.mark.parametrize("rule,answer,request_,calls,session", CASES)
def test_in_spanish_the_english_forms_change_nothing(rule: str, answer: str, request_: str, calls: list,
                                                     session: list | None) -> None:
    # None of these forms was read before they existed (6d4ef7064: 24 of 24), and in Spanish none is read now.
    assert rule not in [f["rule"] for f in _check(answer, request_, calls, session)]


def test_back_in_spanish_every_pattern_is_the_object_that_was_written() -> None:
    written = {name: value for name, value in vars(answer_check).items() if name.startswith("_") and name[1:2].isupper()}
    harness_language.use("en")
    assert answer_check._DONE is not written["_DONE"] and answer_check._ALREADY is not written["_ALREADY"]
    harness_language.use("es")
    for name, value in written.items():
        assert getattr(answer_check, name) is value, name


@pytest.mark.parametrize("answer", [
    "I couldn't close Paint: I did not find its window.",
    "I have not closed Paint because it had no window.",
    "Do you want me to close Paint another way?",
    "If I closed it by mistake, tell me.",
    "Paint has not been closed: its window was not found.",
])
def test_in_english_what_claims_nothing_passes(answer: str) -> None:
    harness_language.use("en")
    assert [f["rule"] for f in _check(answer, "close paint", [("app.close", FAILED)], None)] == []


def test_in_english_a_spanish_answer_is_still_read() -> None:
    harness_language.use("en")
    assert [f["rule"] for f in _check("Cerré Paint.", "cierra paint", [("app.close", FAILED)], None)] == ["not_completed"]


def test_the_view_in_english_is_read_by_its_own_marks() -> None:
    harness_language.use("en")
    answer = "There is nothing written on the board, Paint.NET is blank."
    whole = _view("(2 lines of text are not listed: they repeat the name of a listed control)")
    assert "partial" not in [f["rule"] for f in _check(answer, "", [("input.visible.controls", whole)], None)]
    # A number only the recognized text shows («Text <label>: …») is told as such, and one a control shows is not.
    look = _view(text="Text center: Ranking | 1 Winter river - score 724")
    rules = [f["rule"] for f in _check("The score is 724.", "what is the score?", [("input.visible.controls", look)], None)]
    spanish_marks = dict(look, view=look["view"].replace("Text center", "Texto centro"))
    same = [f["rule"] for f in _check("The score is 724.", "what is the score?",
                                      [("input.visible.controls", spanish_marks)], None)]
    assert rules == same


def test_in_english_what_the_model_says_it_lacks_is_not_an_absence_told() -> None:
    # Medición propia (ING5B, repetición sin modelo de la puerta en inglés, u105-U31-K2-L): «I don't have the current
    # price» after a search that failed is the model saying what it lacks, as «no tengo» is in Spanish (not a form of
    # the rule «partial», that reads «no tiene», «no hay»), and the blind judges read that answer as true.
    harness_language.use("en")
    failed = [("file.find", {"status": "failed", "error": "search_unavailable"})]
    lacks = "I can't search right now, so I don't have the current price of the plan."
    assert "partial" not in [f["rule"] for f in _check(lacks, "how much is the plan?", failed, None)]
    absent = "The folder doesn't have any file with that name."
    assert "partial" in [f["rule"] for f in _check(absent, "is the draft there?", failed, None)]


EDGE = ("Window «Test ranking - Microsoft Edge» (msedge, window 131406), in front\nControls:\n"
        "[3] Button «Back» (top left)\n[16] TabItem «Test ranking» (top left) (selected)\n"
        "[19] Pane «Test ranking - Microsoft Edge» (center)\n")
EDGE_TEXT = "Text top: Test ranking | 1 _ Winter river - score 724 | 2. The north one - scare 829 | 3 _ Paper city - score 8.1"
SAVE_AS = "open notepad, type the list and save it as lista.txt"


def _look(view: str) -> list[dict]:
    return [_r("input.visible.controls", {"status": "completed", "verification": "output_only", "view": view},
               {"application": "Microsoft Edge", "includeText": True})]


# The rules of the Spanish tests' own turns (test_answer_check.py), told in English: (the rule, whether it is found,
# the answer, the turn's results, what the person said, the memory's tool).
TOLD: list[tuple[str, bool, str, Callable[[], list[dict]], str, str | None]] = [
    ("recognized_number", True, "In the list I see, The north one has the best score, 829.",
     lambda: _look(EDGE + EDGE_TEXT), "", None),
    ("recognized_number", False, "It has 829.",
     lambda: _look(EDGE + "(+40 more, not listed because of the cap)\n" + EDGE_TEXT), "", None),
    ("recognized_number", False, "I couldn't confirm whether it is 829.", lambda: _look(EDGE + EDGE_TEXT), "", None),
    ("folder", True, "Done, I added the line to notas.txt in the BAXY-bench folder.",
     lambda: [_written(r"C:\Users\ana\notas.txt")], "", None),
    ("folder", True, "I've saved it in BAXY-bench.", lambda: [_written(r"C:\Users\ana\notas.txt")], "", None),
    ("folder", False, "I saved it in your user folder, not in BAXY-bench.",
     lambda: [_written(r"C:\Users\ana\notas.txt")], "", None),
    ("saved_name", True, "Done, I saved lista.txt in the BAXY-bench folder.",
     lambda: _saving(_titled("lista pilas, cables.txt: Bloc de notas")), SAVE_AS, None),
    ("saved_name", True, "I've saved it as lista.txt.",
     lambda: _saving(_titled("lista pilas, cables.txt: Bloc de notas")), SAVE_AS, None),
    ("mode_not_saved", True, "I set the screen to 1600x900; Windows keeps it for the next restart.",
     lambda: [_mode(False)], "", None),
    ("mode_not_saved", True, "Done, 1600x900 is saved.", lambda: [_mode(False)], "", None),
    ("mode_not_saved", False, "I set the screen to 1600x900, but it was not saved: a restart goes back to 1920x1080.",
     lambda: [_mode(False)], "", None),
    ("unread_memory", True, "I don't have any record of your birthday. Could you tell me when it is?",
     lambda: [], "When is my birthday?", "memory_recall"),
    ("unread_memory", True, "I have no record of your allergies right now.",
     lambda: [], "Do you remember my allergies?", "memory_recall"),
]


@pytest.mark.parametrize("rule,found,answer,results,request_,memory", TOLD)
def test_in_english_the_rules_of_the_spanish_turns_read_them_told_in_english(
        rule: str, found: bool, answer: str, results: Callable[[], list[dict]], request_: str,
        memory: str | None) -> None:
    def rules() -> list[str]:
        receipts = results()
        return [f["rule"] for f in check(answer, request_, receipts,
                                         [(r["op"], r["completed"], r["read"]) for r in receipts], memory=memory)]

    assert rule not in rules()  # in Spanish these English forms are not read, as before they existed
    harness_language.use("en")
    assert (rule in rules()) is found
