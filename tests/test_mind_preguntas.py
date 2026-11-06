"""Uso real 30-10 → 03-11 (G4, G10): a question that only repeats the person's words back, and an answer to a question
that was a new request and ran what BAXY had offered."""
import json
from pathlib import Path

import pytest

from baxy_mind.mind import (ANSWERED_NOTE, ASKED_CLOSED_NOT_RUN, ASKED_ECHO_NOT_RUN, ASKED_SAME_NOT_RUN, CHOICE_ANSWER,
                            OFFERED_NOTE, SYSTEM)

from test_mind_bucle import _trace
from test_mind_final import _call, _mind, _say

SEARCH = _call("web_search", {"query": "qué es WhatsApp"})


@pytest.mark.parametrize("said, echo", [
    # 03-11 03:23:01 and 03:34:25: the person's question came back as BAXY's.
    ("No, en realidad quería preguntarte ¿qué es WhatsApp?", "¿Qué es WhatsApp?"),
    ("¿cómo me llamo el Discord?", "¿Cómo te llamas en Discord?"),
    # 24-10 16:19:45.
    ("y qué ves en la primera diapositiva", "¿Qué ves en la primera diapositiva?")])
def test_a_question_that_repeats_the_persons_words_is_not_asked(tmp_path: Path, monkeypatch, said: str,
                                                               echo: str) -> None:
    # G4: the model decides again with its tools, and asking is still open to it (a datum the person did not give).
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("ask_user", {"question": echo}), SEARCH])
    step = mind.decide(1, said)
    assert step["kind"] == "action" and step["operation"] == "web_search"
    assert "tool_choice" not in server.bodies[-1]
    assert [m for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]["content"] == ASKED_ECHO_NOT_RUN
    assert [r["kind"] for r in _trace(mind) if r.get("kind") == "ask_echo"] == ["ask_echo"]


def test_a_question_that_repeats_the_answer_to_an_earlier_one_is_not_asked(tmp_path: Path, monkeypatch) -> None:
    # 03-11 03:22:51 → 03:23:01: the words compared are the person's last ones, the answer to BAXY's question.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("ask_user", {"question": "¿Qué aplicación se queda con el espacio presionado?"}),
                               _call("ask_user", {"question": "¿Qué es WhatsApp?"}), SEARCH])
    assert mind.decide(1, "hay algo raro cuando aprieto la aplicación")["kind"] == "clarify"
    step = mind.decide(2, "No, en realidad quería preguntarte ¿qué es WhatsApp?")
    assert step["kind"] == "action" and step["operation"] == "web_search"


def test_a_second_echo_in_the_turn_ends_it_in_words(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("ask_user", {"question": "¿Qué es WhatsApp?"}),
                                    _call("ask_user", {"question": "¿Oye, qué es WhatsApp?"}),
                                    _say("Es una app de mensajería.")])
    step = mind.decide(1, "oye, ¿qué es WhatsApp?")
    assert step["kind"] == "conversation" and step["reply"] == "Es una app de mensajería."
    assert server.bodies[-1]["tool_choice"] == "none"
    assert server.bodies[-1]["messages"][-1]["content"] == ASKED_CLOSED_NOT_RUN


@pytest.mark.parametrize("question", ["¿Correo o Correo?", "¿Abro Faros del Sur o Faros del Sur?",
                                      "¿Which one, Mail Plus or Mail Plus?"])
def test_a_question_that_offers_the_same_thing_twice_is_not_asked(tmp_path: Path, monkeypatch, question: str) -> None:
    # F28, 04-11 14:32: «¿X o X?» with no entry or call of that name; its answer tells nothing apart. With two of them
    # open what differs is still theirs to read: the model decides again with its tools.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("ask_user", {"question": question}), SEARCH])
    step = mind.decide(1, "cuéntame algo de eso")
    assert step["kind"] == "action" and step["operation"] == "web_search"
    assert "tool_choice" not in server.bodies[-1]
    assert [m for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]["content"] == ASKED_SAME_NOT_RUN
    assert [r["kind"] for r in _trace(mind) if r.get("kind") == "ask_same"] == ["ask_same"]


@pytest.mark.parametrize("question", ["¿Correo o Agenda?", "¿Correo de la cuenta uno o Correo de la cuenta dos?",
                                      "¿Cuál Correo?", "¿Correo?",
                                      # uso-127: the same word twice with no choice between them offers nothing twice.
                                      "¿Sobre qué cuento te cuento?", "Do you want them song by song?"])
def test_a_question_whose_options_differ_is_asked(tmp_path: Path, monkeypatch, question: str) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("ask_user", {"question": question})])
    assert mind.decide(1, "ábrelo")["kind"] == "clarify"


@pytest.mark.parametrize("said, question", [
    ("crea un documento para el informe", "¿Qué nombre le pongo al documento?"),
    ("abre el documento", "¿Qué documento abro?"),
    ("escribe hola en whatsapp", "¿A quién le escribo hola en WhatsApp?"),
    ("manda un mensaje a Juan", "¿Qué le digo a Juan?"),
    # 21-10 04:37:00, the closest real question to the line (0.74): what the person had not said yet.
    ("quiere comprar un juego en epic games y", "¿Qué juego quiere comprar en Epic Games?")])
def test_a_question_for_a_datum_the_person_did_not_give_is_asked(tmp_path: Path, monkeypatch, said: str,
                                                                question: str) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("ask_user", {"question": question})])
    step = mind.decide(1, said)
    assert step["kind"] == "clarify" and step["question"] == question


def test_without_the_aid_the_echo_is_asked(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    mind, _ = _mind(tmp_path, [_call("ask_user", {"question": "¿Qué es WhatsApp?"})])
    assert mind.decide(1, "oye, ¿qué es WhatsApp?")["kind"] == "clarify"


# G10, 02-11 21:12 → 21:15: no Walking Dead on HBO Max; BAXY offered another title and «dime un cuento» played it.
PLAY = "streaming_play_named"
NOT_FOUND = json.dumps({"status": "failed", "error": "title_not_found",
                        "candidates": ["Diarios de Vampiros", "The Last of Us"]})
OFFER = "¿La que se llama Diarios de Vampiros o otra de HBO Max?"
OFFERED = _call(PLAY, {"service": "hbo_max", "title": "Diarios de Vampiros"})


def _offered(tmp_path: Path, replies: list) -> tuple:
    mind, server = _mind(tmp_path, [_call(PLAY, {"service": "hbo_max", "title": "The Walking Dead"}),
                                    _call("ask_user", {"question": OFFER}), *replies])
    mind.risk = {PLAY: "external_communication", "web_search": "read_only", "audio_volume_step": "low_reversible"}
    assert mind.decide(1, "pon una película de zombies en HBO Max")["kind"] == "action"
    assert mind.continue_turn(2, NOT_FOUND)["kind"] == "clarify"
    return mind, server


def test_a_new_request_after_an_offer_does_not_run_the_offer(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _offered(tmp_path, [OFFERED, _say("Había una vez un zorro que…")])
    step = mind.decide(3, "dime un cuento")
    assert step["kind"] == "conversation" and step["reply"] == "Había una vez un zorro que…"
    note = server.bodies[-1]["messages"][-1]
    assert note["role"] == "user" and note["content"].startswith("[Nota interna")
    assert PLAY in note["content"] and "«Diarios de Vampiros»" in note["content"]
    answer = [m for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]["content"]
    assert answer == "dime un cuento" + ANSWERED_NOTE
    assert [r["kind"] for r in _trace(mind) if r.get("kind") == "offer_unanswered"] == ["offer_unanswered"]


def test_a_yes_to_the_offer_runs_it_when_the_model_reads_it_again(tmp_path: Path, monkeypatch) -> None:
    # Whether «sí» or «esa» chooses the offer is the model's reading: the mind tells it the value was only BAXY's, once.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _offered(tmp_path, [OFFERED, OFFERED])
    step = mind.decide(3, "sí, esa")
    assert step["kind"] == "action" and step["arguments"] == {"service": "hbo_max", "title": "Diarios de Vampiros"}


@pytest.mark.parametrize("answer", ["pon Diarios de Vampiros", "diarios de vampiros, porfa"])
def test_an_answer_that_names_the_offer_runs_it(tmp_path: Path, monkeypatch, answer: str) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _offered(tmp_path, [OFFERED])
    step = mind.decide(3, answer)
    assert step["kind"] == "action" and step["operation"] == PLAY


def test_a_read_or_a_call_without_the_offer_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _offered(tmp_path, [_call("audio_volume_step", {"direction": "down"})])
    assert mind.decide(3, "ah, y baja el volumen")["operation"] == "audio_volume_step"
    mind, _ = _offered(tmp_path, [_call("web_search", {"query": "Diarios de Vampiros"})])
    assert mind.decide(3, "¿de qué trata?")["operation"] == "web_search"


def test_without_the_aids_the_offer_runs_as_before(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    mind, server = _offered(tmp_path, [OFFERED])
    step = mind.decide(3, "dime un cuento")
    assert step["kind"] == "action" and step["operation"] == PLAY
    assert [m for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]["content"] == "dime un cuento"


# Held-out, written by an agent that did not see the change (2026-11-03). «pone la música que tú quieras, la que te
# tinque» → «¿Qué música quieres que ponga?» (0.75) is under ASKED_ECHO: a choice left to BAXY is not told by shape.
@pytest.mark.parametrize("said, echo", [("oye, que es la memoria virtual", "¿Qué es la memoria virtual?"),
                                        ("cuanto espacio me queda en el disco", "¿Cuánto espacio te queda en el disco?")])
def test_held_out_echoes_are_not_asked(tmp_path: Path, monkeypatch, said: str, echo: str) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("ask_user", {"question": echo}), SEARCH])
    assert mind.decide(1, said)["kind"] == "action"


@pytest.mark.parametrize("said, question", [
    ("mandale un correo a mi profe avisando que llego tarde",
     "¿A qué correo se lo mando? No tengo guardado el de tu profe."),
    ("abre el informe que estaba editando ayer",
     "Encontré dos documentos que modificaste ayer, «informe_lab3.docx» e «informe_final.docx». ¿Cuál abro?"),
    ("borra la carpeta de las fotos", "Tienes dos carpetas con fotos, «Fotos viaje» y «Fotos 2025». ¿Cuál borro?")])
def test_held_out_questions_for_a_missing_datum_are_asked(tmp_path: Path, monkeypatch, said: str,
                                                         question: str) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("ask_user", {"question": question})])
    assert mind.decide(1, said)["kind"] == "clarify"


HELD_OFFERS = [("pone algo de Mon Laferte", "¿Quieres que ponga «Tu falta de querer» en YouTube?",
                ("media_play_query", {"query": "Tu falta de querer"}), "no, mejor abre la calculadora",
                ("app_open", {"appId": "Calculadora"}), "dale, esa"),
               ("abre el documento de la tesis", "Encontré «tesis_capitulo2_v3.docx» en Documentos. ¿Lo abro?",
                ("file_open", {"path": "tesis_capitulo2_v3.docx"}), "espera, primero dime cuanta bateria me queda",
                ("system_battery", {}), "si, ese mismo"),
               ("quiero ver una pelicula", "¿Te pongo «Machuca» en Netflix?",
                (PLAY, {"service": "netflix", "title": "Machuca"}), "cierra el navegador mejor",
                ("app_close", {"appId": "Opera"}), "ya po, ponla")]
RISKS = {"media_play_query": "low_reversible", "file_open": "low_reversible", PLAY: "external_communication",
         "app_open": "low_reversible", "system_battery": "read_only", "app_close": "work_loss"}


@pytest.mark.parametrize("request_, question, offer, new, other, yes", HELD_OFFERS)
def test_held_out_new_requests_after_an_offer(tmp_path: Path, monkeypatch, request_: str, question: str, offer: tuple,
                                             new: str, other: tuple, yes: str) -> None:
    # Whatever the person said, the model's offer is held once; what it calls after the note runs.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    for index, (said, then) in enumerate([(new, other), (yes, offer)]):
        (tmp_path / str(index)).mkdir()
        mind, _ = _mind(tmp_path / str(index), [_call("ask_user", {"question": question}), _call(*offer),
                                                _call(*then)])
        mind.risk = RISKS
        assert mind.decide(1, request_)["kind"] == "clarify"
        step = mind.decide(2, said)
        assert step["kind"] == "action" and step["operation"] == then[0]
        assert [r["operation"] for r in _trace(mind) if r.get("kind") == "offer_unanswered"] == [offer[0]]


@pytest.mark.parametrize("aids, before, noted", [
    # Encargo 46c (aid «choice_left»): the words after BAXY's own question in words (an offer of three things closed with
    # «¿qué te tinca?») are read as after ask_user's, and may leave the choice to BAXY (a choice left to it was asked
    # again). Only the shape of BAXY's own message says it asked; SYSTEM stays as it was.
    ("", "Puedo ponerte música, abrirte un juego o buscarte un video. ¿Qué te tinca?", True),
    ("", "Listo, abrí Spotify.", False),  # no question of BAXY's before them
    ("answer_or_new", "Puedo ponerte música o abrirte un juego. ¿Qué prefieres?", False)])
def test_words_after_baxys_question_in_words_get_the_answer_note(tmp_path: Path, monkeypatch, aids: str, before: str,
                                                                  noted: bool) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", aids)
    mind, server = _mind(tmp_path, [_say("Te pongo música.")])
    mind.new_session([{"role": "user", "content": "tengo un rato libre"}, {"role": "assistant", "content": before}])
    mind.decide(1, "decidí vos nomás")
    messages = server.bodies[-1]["messages"]
    assert messages[-1] == {"role": "user", "content": "decidí vos nomás"}
    assert (messages[-2]["content"] == OFFERED_NOTE) is noted
    assert CHOICE_ANSWER in OFFERED_NOTE and CHOICE_ANSWER not in ANSWERED_NOTE and CHOICE_ANSWER not in SYSTEM


def test_the_answer_note_is_read_once_and_right_before_the_words(tmp_path: Path, monkeypatch) -> None:
    # Revisión PCR1 (L3): every check of where OFFERED_NOTE goes passed with it twice, once before the words and once
    # after. In each request of the turn, its calls' included, it is there once, right before them; the next turn, which
    # follows no question, keeps that one in the history and adds none. ATR1: read after the words (5312ca130) the model
    # asked instead of doing what it was asked (u107-D4-saludo and u107-QC3 10/10 → 0/10, 10 seeds), so it stays before.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [SEARCH, _say("Es un gas que brilla."), _say("De nada.")])
    mind.risk = {"web_search": "read_only"}
    mind.new_session([{"role": "user", "content": "Hola"}, {"role": "assistant", "content": "Buenas, ¿en qué te ayudo?"}])
    asked = {"role": "user", "content": "busca qué es una nebulosa"}
    assert mind.decide(1, asked["content"])["kind"] == "action"
    assert mind.continue_turn(2, json.dumps({"status": "completed", "results": [{"title": "Nebulosa"}]}))["kind"] == "conversation"
    thanked = {"role": "user", "content": "gracias"}
    mind.decide(3, thanked["content"])
    assert len(server.bodies) == 3
    for body, words, notes in zip(server.bodies, [asked, asked, thanked], [1, 1, 0]):
        messages = body["messages"]
        said = max(i for i, m in enumerate(messages) if m == words)
        noted = [i for i, m in enumerate(messages) if OFFERED_NOTE in str(m.get("content"))]
        assert not [i for i in noted if i > said]
        assert (said - 1 in noted) == bool(notes)
        assert len(noted) == 1


def test_words_after_an_open_question_are_attended_as_a_request(tmp_path: Path) -> None:
    # uso-107 (S08): after «Buenas tardes, ¿en qué te ayudo?», a note that read the next words as an answer to weigh
    # («puede contestarla … o ser un pedido nuevo») had a whole request asked back for the datum it gave (0/15 against
    # 15/15 with the aid off). The note says what to do with a request and with a choice left, not what the words may be.
    mind, server = _mind(tmp_path, [_say("Listo.")])
    mind.new_session([{"role": "user", "content": "Hola"}, {"role": "assistant", "content": "Buenas tardes, ¿en qué te ayudo?"}])
    mind.decide(1, 'en el bloc de notas escribe "hola"')
    note = server.bodies[-1]["messages"][-2]["content"]
    assert note == OFFERED_NOTE and "contestarla" not in note and "pedido nuevo" not in note
    assert "si le falta un dato, pregúntalo" in note
