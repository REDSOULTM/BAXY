"""Aid «check_language» (2026-10-25): a reply clearly in Spanish to a request clearly in English (cien: 14 of 68 English
requests of the e2e runs answered in Spanish) is written again once, with a note that says only the fact: the person
wrote in English. Never a reply; the second answer is final. Never on Spanglish, a short request, or a request that asks
for Spanish or a translation. Which language is which is a light count of function words, with names, paths, numbers,
quoted titles and what follows a colon (the text to write) left out."""
import json
from pathlib import Path

import pytest

from baxy_mind.answer_check import check, reply_is_spanish, request_is_english
from baxy_mind.mind import CHECK_NOTE, LANGUAGE_NOTE
from test_mind_aids import _trace
from test_mind_final import _call, _mind, _say


# ---- the detector ----------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("request_text", [
    "delete the old-drafts folder inside BAXY-bench",
    "In my Documents folder, inside Garden Plan, create a file named seeds.txt that says: tomatoes, basil, peppers",
    "could you switch on the ceiling lamp in my living room, it's getting dark",
    "now close Notepad without saving",
    "no, wait, leave it open",
    "actually, call it invoices instead",
    "write 'meeting moved to 4pm' into a file called update.txt in BAXY-bench",
    "so is that file actually saved now?",
    "set an alarm for 6:30",
    "minimize the Paint window, I need to see what's behind it",
])
def test_english_requests_are_english(request_text: str) -> None:
    assert request_is_english(request_text)


@pytest.mark.parametrize("request_text", [
    # Spanish, dictated Spanish with its misspellings, Spanglish.
    "borra el archivo viejo.txt de la carpeta BAXY-bench",
    "agregale tanbien silantro i paltas",
    "subele dies mas",
    "abre la calculadora please",
    "bájale el volume a 25 please",
    "now compute 15 times 12 ahí mismo",
    "no wait, mejor mute total",
    "in precios.txt de BAXY-bench, change el precio del pan de 1800 a 1950",
    "reemplaza todo lo que hay en menu_semana.txt de BAXY-bench por la palabra pending, overwrite it",
    "switch me al Bloc de notas, el que tiene lista_regalos",
    "¿cuántos files hay en la carpeta que tengo abierta en el explorer?",
    # Short: under the minimum of words once names are left out.
    "did that work?",
    "open Notepad for me",
    "play Clocks by Coldplay on Spotify",
    "yes",
    "wait, make it 6:45 instead",
    # What follows a colon is the text to write, not the person's language; quotes are titles.
    "in Notepad, type: please write this down for me now",
    "write 'backup done and all of it is there' to status.txt",
    # Spanish asked for, or a translation.
    "answer me in Spanish from now on, please",
    "translate this sentence for me: the cat is on the table",
    "how do you say good morning in español?",
])
def test_spanish_spanglish_short_and_asked_for_spanish_are_not_english(request_text: str) -> None:
    assert not request_is_english(request_text)


@pytest.mark.parametrize("reply", [
    "No puedo borrar carpetas de BAXY-bench, solo archivos. ¿Quieres que borre el archivo old-drafts?",
    "Listo, seeds.txt quedó creado en Documents/Garden Plan con el texto que pediste.",
    "¿Cierro Notepad sin guardar?",
    "No lo cierro, Notepad queda abierto.",
    "La carpeta receipts ya está creada en BAXY-bench.",
    "No puedo controlar las luces del techo.",
])
def test_spanish_replies_are_spanish(reply: str) -> None:
    assert reply_is_spanish(reply)


@pytest.mark.parametrize("reply", [
    "I set the volume to 50.",
    "Should I send old_scores.txt from BAXY-bench to the Recycle Bin?",
    "Joaquín Rivas is presenting this week on the Q3 budget.",
    "I typed «buy stamps and envelopes» into Notepad.",
    # Spanish quoted, named or read inside an English reply.
    "The file says: «Reunión de vecinos el jueves a las 19:00, en la sede de la junta».",
    "I opened Club de Lectura in Documentos.",
    "The file says: Reunión de vecinos el jueves en la sede.",
    # Too short to tell.
    "Listo.",
    "Sí, listo.",
])
def test_english_mixed_and_short_replies_are_not_spanish(reply: str) -> None:
    assert not reply_is_spanish(reply)


def _language(answer: str, request: str, receipts: list | None = None) -> list[dict]:
    return [f for f in check(answer, request, receipts or [], []) if f["rule"] == "language"]


def test_a_spanish_reply_to_an_english_request_is_one_finding_with_its_words() -> None:
    found = _language("No puedo controlar las luces del techo.",
                      "could you switch on the ceiling lamp in my living room, it's getting dark")
    assert len(found) == 1
    assert found[0]["said"] == "No puedo controlar las luces del techo."
    assert "inglés" in found[0]["fact"] and "español" in found[0]["fact"]


@pytest.mark.parametrize("answer, request_text", [
    ("I can't control your ceiling lamp.", "could you switch on the ceiling lamp in my living room, it's getting dark"),
    ("No puedo controlar las luces del techo.", "prende la lámpara del techo del living, que está oscureciendo"),
    ("Listo, la puse en 25.", "actually, that's still loud, ponla en 25"),
    ("¿Cierro Notepad sin guardar?", "close it"),
    ("Buenos días.", "translate good morning into Spanish for me, please"),
])
def test_no_finding_when_either_side_is_not_clear(answer: str, request_text: str) -> None:
    assert _language(answer, request_text) == []


def test_the_text_a_result_of_the_turn_read_is_not_the_reply_s_language() -> None:
    # «read notas.txt to me»: the reply may be the file's own Spanish words.
    read = {"op": "file.read", "tool": "file_read", "arguments": {"name": "notas.txt"},
            "observation": json.dumps({"status": "completed", "observed": {
                "text": "Comprar pan, leche y huevos para el lunes. Llamar a la tía Rosa."}}, ensure_ascii=False),
            "outcome": "completada", "completed": True, "read": True}
    request = "read notas.txt from my BAXY-bench folder out loud for me"
    assert _language("Comprar pan, leche y huevos para el lunes. Llamar a la tía Rosa.", request, [read]) == []
    assert _language("El archivo tiene una lista de compras para el lunes y una llamada.", request, [read])


# ---- the mind --------------------------------------------------------------------------------------------------------
LAMP = "could you switch on the ceiling lamp in my living room, it's getting dark"
SPANISH = "No puedo controlar las luces del techo."
ENGLISH = "I can't control your ceiling lamp."


def test_a_spanish_reply_to_english_words_is_written_again_once_words_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_say(SPANISH), _say(ENGLISH)])
    result = mind.decide(1, LAMP)
    assert result["reply"] == ENGLISH and len(server.bodies) == 2
    note = server.bodies[-1]["messages"][-1]
    assert note["role"] == "user" and note["content"] == LANGUAGE_NOTE
    assert "inglés" in note["content"] and ENGLISH not in note["content"]  # the fact, never words to say
    assert server.bodies[-1]["tool_choice"] == "none"
    said = [m["content"] for m in mind.conversation if m["role"] == "assistant" and m.get("content")]
    assert said == [ENGLISH]
    assert not any(str(m.get("content")) == LANGUAGE_NOTE for m in mind.conversation)
    checks = [r for r in _trace(mind) if r["stage"] == "turn.check"]
    assert [c["round"] for c in checks] == [1, 2] and checks[0]["findings"][0]["rule"] == "language"


def test_the_second_reply_is_final_even_in_spanish(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_say(SPANISH), _say("No puedo encender lámparas ni controlar luces.")])
    result = mind.decide(1, LAMP)
    assert result["reply"] == "No puedo encender lámparas ni controlar luces." and len(server.bodies) == 2
    assert [c["kept"] for c in _trace(mind) if c["stage"] == "turn.check" and c["round"] == 2] == [True]


def test_spanglish_is_answered_as_it_is(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_say("Listo, la calculadora quedó abierta.")])
    result = mind.decide(1, "ábreme la calculator porfa, tengo que sacar unas cuentas del almuerzo")
    assert result["reply"] == "Listo, la calculadora quedó abierta." and len(server.bodies) == 1


def test_with_a_contradiction_the_check_note_says_both(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    failed = {"status": "failed", "error": "window_not_found", "message": "No window."}
    mind, server = _mind(tmp_path, [_call("app_close", {"appId": "Paint"}),
                                    _say("Cerré Paint, ya no está en la pantalla."),
                                    _say("I couldn't close Paint: its window wasn't found.")])
    mind.wire_to_op = {"app_close": "app.close"}
    mind.decide(1, "close Paint for me, I'm finished sketching")
    result = mind.continue_turn(2, json.dumps(failed))
    assert result["reply"] == "I couldn't close Paint: its window wasn't found."
    note = server.bodies[-1]["messages"][-1]["content"]
    assert note.startswith(CHECK_NOTE[:40]) and "app_close" in note and "inglés" in note


@pytest.mark.parametrize("setting, checked", [(None, True), ("all", True), ("answer_check", False),
                                              ("answer_check,check_language", True), ("check_language", False),
                                              ("none", False)])
def test_the_language_rule_is_an_aid_of_its_own(tmp_path: Path, monkeypatch, setting, checked) -> None:
    if setting is None:
        monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    else:
        monkeypatch.setenv("BAXY_AYUDAS", setting)
    mind, server = _mind(tmp_path, [_say(SPANISH), _say(ENGLISH)])
    result = mind.decide(1, LAMP)
    assert (result["reply"] == ENGLISH) is checked
    assert len(server.bodies) == (2 if checked else 1)

