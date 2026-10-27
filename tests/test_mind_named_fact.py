"""Aid «named_fact» (feria 2026-10-27): words answered from memory about something the person named with a name of its
own (a local brand told as another kind of product, with no doubt of a call to read: p_call 0.05) are judged by System
One, between answering in words and web_search; only its web_search is looked up, written by the model."""
import json
from pathlib import Path

from test_mind_doubt_policy import FakeSystemOne, _mind, _say
from test_mind_final import _call

SEARCH = {"type": "function", "function": {"name": "web_search", "description": "Look something up on the web. More.",
                                           "parameters": {}}}


def _named(tmp_path: Path, monkeypatch, choice, replies: list):
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, replies)
    mind.tools = [SEARCH]
    one = FakeSystemOne(choice)
    mind.system_one = one  # type: ignore[assignment]
    fills: list[str] = []

    def fill_call(body, wire):
        fills.append(wire)
        return {"name": "web_search", "arguments": {"query": "Zorvik"}, "timings": {}}

    server.fill_call = fill_call
    return mind, server, one, fills


def test_a_fact_from_memory_about_a_name_the_person_said_is_judged_and_looked_up(tmp_path, monkeypatch) -> None:
    mind, server, one, fills = _named(tmp_path, monkeypatch, "web_search",
                                      [_say("El jugo Zorvik es una bebida energética.")])
    step = mind.decide(1, "¿Qué es el jugo Zorvik?")
    assert step["kind"] == "action" and step["operation"] == "web_search" and fills == ["web_search"]
    assert set(one.asked[0]["options"]) == {"web_search", "responder_con_palabras"}
    assert "El jugo Zorvik es una bebida energética." not in [m.get("content") for m in mind.conversation]
    rows = [json.loads(line) for line in (tmp_path / "turns.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["stage"] for r in rows].count("turn.named") == 1


def test_the_words_stand_when_system_one_reads_an_answer_or_is_not_up(tmp_path, monkeypatch) -> None:
    for choice in ("responder_con_palabras", None):
        mind, server, one, fills = _named(tmp_path, monkeypatch, choice, [_say("Zorvik es una banda de rock.")])
        assert mind.decide(1, "Háblame de Zorvik, por favor.")["reply"] == "Zorvik es una banda de rock."
        assert len(one.asked) == 1 and not fills and len(server.bodies) == 1


def test_no_name_repeated_or_only_a_sentence_start_is_not_judged(tmp_path, monkeypatch) -> None:
    mind, server, one, fills = _named(tmp_path, monkeypatch, "web_search",
                                      [_say("La fotosíntesis convierte la luz en energía."), _say("¿Qué abro?"),
                                       _say("Claro, dime.")])
    assert mind.decide(1, "¿Qué es la fotosíntesis?")["kind"] == "conversation"
    assert mind.decide(2, "Abre Zorvik.")["kind"] == "conversation"
    assert mind.decide(3, "Gracias. Ayúdame con algo.")["kind"] == "conversation"
    assert one.asked == [] and not fills


def test_without_the_aid_the_words_are_not_judged(tmp_path, monkeypatch) -> None:
    mind, server, one, fills = _named(tmp_path, monkeypatch, "web_search", [_say("Zorvik es una banda.")])
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    assert mind.decide(1, "¿Conoces a Zorvik?")["reply"] == "Zorvik es una banda." and one.asked == []


def test_a_name_the_recognizer_wrote_in_lowercase_counts_when_the_answer_writes_it_as_a_name(tmp_path,
                                                                                             monkeypatch) -> None:
    # PC-L review 2026-10-27: the voice may come in lowercase; the model writes a name with its capital
    mind, server, one, fills = _named(tmp_path, monkeypatch, "web_search", [_say("El jugo Zorvik es energético.")])
    assert mind.decide(1, "qué es el jugo zorvik")["kind"] == "action" and fills == ["web_search"]


def test_what_memory_holds_is_an_option_and_never_goes_to_the_web(tmp_path, monkeypatch) -> None:
    # PC-L review 2026-10-27 (privacy): a person of the contacts or of memory is not looked up on the web
    mind, server, one, fills = _named(tmp_path, monkeypatch, "memory_recall", [_say("Lena es tu hermana.")])
    mind.tools = [SEARCH, {"type": "function", "function": {"name": "memory_recall",
                                                            "description": "Recall what you keep. More.",
                                                            "parameters": {}}}]
    assert mind.decide(1, "¿Quién es Lena?")["reply"] == "Lena es tu hermana." and not fills
    assert set(one.asked[0]["options"]) == {"web_search", "memory_recall", "responder_con_palabras"}


def test_a_name_memory_gave_in_an_earlier_turn_is_not_judged(tmp_path, monkeypatch) -> None:
    # privacy review 2026-10-27: what memory_recall returned stays in the conversation; that name is the person's
    mind, server, one, fills = _named(tmp_path, monkeypatch, "web_search",
                                      [_call("memory_recall", {"query": "Lena"}), _say("Lena es tu hermana."),
                                       _say("Lena vive en Valdivia.")])
    mind.wire_to_op = {"memory_recall": "memory.recall"}
    mind.decide(1, "¿Qué sabes de Lena?")
    mind.continue_turn(2, json.dumps({"status": "completed", "items": [{"text": "Lena es mi hermana"}]}))
    assert mind.decide(3, "Cuéntame de Lena.")["reply"] == "Lena vive en Valdivia." and one.asked == []


def test_a_fact_about_a_named_thing_that_is_not_asked_what_it_is_is_not_judged(tmp_path, monkeypatch) -> None:
    # PC-L, decision v11 2026-10-27: a capital, the letters of an acronym or what was opened, said with a name, went to
    # the web; the fair's miss was asking what a named thing is
    mind, server, one, fills = _named(tmp_path, monkeypatch, "web_search",
                                      [_say("La capital de Zorvia es Velmar."), _say("No, no abrí Descargas."),
                                       _say("ZRV stands for Zero Return Value.")])
    assert mind.decide(1, "¿Cuál es la capital de Zorvia? Siempre se me olvida")["kind"] == "conversation"
    assert mind.decide(2, "¿Ya me abriste lo de Descargas?")["kind"] == "conversation"
    assert mind.decide(3, "My nephew asked me what the letters ZRV mean")["kind"] == "conversation"
    assert one.asked == [] and not fills


def test_a_question_about_something_else_of_a_named_thing_is_not_judged(tmp_path, monkeypatch) -> None:
    # PC-L, decision v6 2026-10-27: the author of a book named before, or a word in a language, went to the web; the
    # named thing has to close the question about what or who it is
    mind, server, one, fills = _named(tmp_path, monkeypatch, "web_search",
                                      [_say("El autor de Zorvik Grande es Ana Velmar."),
                                       _say("The Zorvian word for thanks is velma.")])
    assert mind.decide(1, "Estoy leyendo Zorvik Grande, ¿quién es el autor?")["kind"] == "conversation"
    assert mind.decide(2, "I'm visiting Zorvia soon, what's the Zorvian word for thanks?")["kind"] == "conversation"
    assert one.asked == [] and not fills


def test_the_question_counts_after_a_word_or_a_sentence_before_it(tmp_path, monkeypatch) -> None:
    # code review 2026-10-27: by voice there is seldom a comma; «oye qué es…», «Hola. ¿Qué es…?» and «… y para qué
    # sirve» are the same question
    for said in ("oye qué es el jugo Zorvik", "Hola. ¿Qué es el jugo Zorvik?", "dime qué es Zorvik",
                 "¿Qué es Zorvik y para qué sirve?"):
        mind, server, one, fills = _named(tmp_path, monkeypatch, "web_search",
                                          [_say("Zorvik es una bebida energética.")])
        assert mind.decide(1, said)["operation"] == "web_search" and fills == ["web_search"], said
