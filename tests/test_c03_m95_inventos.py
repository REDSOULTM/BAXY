"""M95 (D52): no invented fact in a visible final, and no «no lo encontré» over a read that answers, from the
independent reviews of the window DEV-D runs.

The invented turns the reviewer marked in v3o, v3r and v3u were traced to their origin and are closed by earlier work
(M85 p09-t3, M85/M88 p24-t5, M83/M89 p27-t1, M88 p12-t2, M88/M92 s111, M92 p29-t2, w01-t3, M93 s061). The review of
v3x (817dde50, HEAD of this branch) marked four more, each closed here at its origin:

- D-w10-t1 a recipe of arepas from memory, «1 taza de agua» for 2 of maize flour: D52, a recipe is its quantities and
  memory gives none, so no recipe is asked of memory (the not-found report stands).
- D-p31-t1 «los últimos 10 presidentes…» from memory: five names written twice, out of order, one nobody bore. A memory
  answer that writes the same line twice is refused (``memory_repeats``).
- D-p34-t2 «explícame cómo lo entendiste en la primera pregunta» → «En mi primera respuesta, me referí a … las de la NASA
  o las de la película "Back to the Future"», which the first answer never said. A talk sentence about BAXY's own
  earlier answer names nothing the conversation does not carry (``llm.talk_misquotes_itself``); the retry is handed the
  earlier answers word for word.
- D-w15-t4 «He guardado la nota «reunion jueves» con el resumen del informe trimestral de Documentos.»: the note holds
  those words, no summary (the argument wrote a description for content: M94's side). The report of a note whose text
  names a kind of text quotes it as written or says only that it was saved (``note_content_described``).

And the opposite failure, a not-found over a read that answers:
- D-w14-t1 «¿quién ha ganado la Vuelta este año?»: this year's event is not kept by memory, so the pertinent pages were
  never told either; what they state is now said (the report's year checks hold it to this year).
- D-w01-t2 «cuánta sal le echo al agua … para los tallarines»: the page «La regla del 1, 100 y 10: cuánta sal hay que
  echarle a la [pasta]» was not about the request because tallarines were not pasta to the filter.

One channel stayed open in every run:

- D-p28-t3 «Hustlers is perfect.» (v3l, v3r, v3u and again in v3x) → «That's a great choice, but *Hustlers* is a 2019
  film, not a 1980 movie.» A talk turn reads nothing; «2019» came from the model's memory with no notice (the reviewer
  let it pass because it is right). D52: a quantity, distance, duration, date, year or count is looked up before it is
  stated and memory answers only what is not a figure. ``llm.talk_memory_figures`` finds the figures of a talk answer
  that the conversation does not state; the unshaped talk reply is written again without them, a retry that keeps one
  loses that sentence, and the conversation message the composer writes where nothing ran is held to the same rule.

Never vetoed: a figure the conversation states (the person's or BAXY's earlier answer), what is computed from the
person's numbers (a tip, a division, a conversion of a figure read before: only a year is judged when the conversation
writes numbers), a number that is part of a name, a hexadecimal colour, code, and written content (stories, jokes).
Two of the four ⚠ of v3x were honest finals refused on the reply side, and are fixed so the new veto adds none:
- D-s014 «¿qué previsión de tiempo hay para las cuatro?» at 22:45: «No tengo el pronóstico para las cuatro, pero hoy …
  máxima de 19.5 °C…» was refused for not giving the temperature now (an hour the read does not cover is not now).
- D-s017 a recipe from memory, whole, refused four times for «Cook the macaroni according to package directions»
  (M92's deferral pattern). With no recipe asked of memory (below) the not-found report stands.

Evidence: tests/data/c03_m95_evidence.json (the review records, with the dialogue each turn lived, and the v3x drafts).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from baxy_mind import llm

EVIDENCE = json.loads((Path(__file__).parent / "data" / "c03_m95_evidence.json").read_text(encoding="utf-8"))["turns"]
P28 = EVIDENCE["v3u:D-p28-t3"]
RECORDED = P28["published"]


def _dialogue(case: dict) -> list[str]:
    return [item["content"] for item in case["lived"]]


def _person(case: dict) -> list[str]:
    return [item["content"] for item in case["lived"] if item["role"] == "user"]


class _Writer(llm.LlmRuntime):
    """The drafts stand in for the model, in order (the last one repeats); every payload sent is kept."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = None
        self._drafts = list(drafts)
        self.sent: list[dict] = []

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.sent.append(copy.deepcopy(payload))
        content = self._drafts.pop(0) if len(self._drafts) > 1 else self._drafts[0]
        return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}


def _said_to_the_model(payload: dict) -> str:
    return "\n".join(str(message["content"]) for message in payload["messages"])


def _chat(writer: _Writer, case: dict) -> str:
    history = [dict(item) for item in case["lived"]]
    reply, _ = writer.chat(case["text"], history=history, conversation_kind="knowledge", response_language="en",
                           temperature=0.0)
    return reply


# ------------------------------------------------------------------ the recorded turn


def test_the_recorded_talk_answer_gives_a_year_from_memory() -> None:
    # The same draft in v3x (HEAD 817dde50) before any veto.
    assert EVIDENCE["v3x:D-p28-t3"]["raw_replies"][0]["raw_reply"] == RECORDED
    # «1980» is BAXY's earlier answer; «2019» nothing in the conversation states.
    assert llm.talk_memory_figures(RECORDED, P28["text"], _dialogue(P28), _person(P28)) == ["2019"]


def test_the_talk_answer_is_written_again_without_the_figure() -> None:
    writer = _Writer([RECORDED, json.dumps({"answer": "Hustlers sounds like a great pick for a dramatic story."})])

    assert _chat(writer, P28) == "Hustlers sounds like a great pick for a dramatic story."
    retry = _said_to_the_model(writer.sent[1])
    assert "These figures are not in the conversation: 2019." in retry
    assert "you give no year, date, quantity or count" in retry


def test_a_retry_that_keeps_the_figure_loses_that_sentence() -> None:
    writer = _Writer([RECORDED, json.dumps({"answer": "Great choice. Hustlers came out in 2019."})])

    assert _chat(writer, P28) == "Great choice."


def test_a_retry_that_is_only_the_figure_is_no_answer() -> None:
    writer = _Writer([RECORDED, json.dumps({"answer": "Hustlers came out in 2019."})])

    with pytest.raises(llm.ConversationReplyContractError) as refused:
        _chat(writer, P28)
    assert refused.value.audit_reason == "memory_figures"


def test_the_composed_conversation_message_is_held_to_the_same_rule() -> None:
    facts = {
        "situation": json.dumps({"kind": "conversation"}),
        "context": P28["lived"][-1]["content"],
        "priorRequests": _person(P28),
    }

    assert llm.compose_visible_defect(RECORDED, "conversation", P28["text"], facts) == "memory_figures"
    assert llm.compose_visible_defect(
        "Hustlers sounds like a great pick for a dramatic story.", "conversation", P28["text"], facts,
    ) == ""


# ------------------------------------------------------------------ figures that are never vetoed


@pytest.mark.parametrize(
    "ident",
    [
        "v3u:D-w07-t3",  # «1850 dividido entre 7 es 264,2857… redondeado hacia arriba da 265.»
        "v3u:D-w19-t1",  # «El 15% de tip de 86.40 dólares es 12.96 dólares.»
        "v3u:D-w19-t2",  # «Si lo repartimos entre 3, cada uno paga 4.32 dólares.»
        "v3u:D-w16-t4",  # «The high is 18.7°C.» after the forecast read in Fahrenheit
        "v3u:D-s043",  # hexadecimal colours
        "v3l:D-p33-t2", "v3m:D-p33-t3",  # «COVID-19», «SARS-CoV-2»
        "v3u:D-w12-t1", "v3u:D-s009",  # a joke; anime with «One Piece»
    ],
)
def test_the_recorded_talk_answers_with_grounded_figures_pass(ident: str) -> None:
    case = EVIDENCE[ident]
    assert case["decision"].startswith("conversation:") and case["ok"]

    assert llm.talk_memory_figures(case["published"], case["text"], _dialogue(case), _person(case)) == []


@pytest.mark.parametrize(
    ("reply", "asked", "dialogue", "expected"),
    [
        ("La Torre Eiffel mide unos 330 metros y se inauguró en 1889.", "háblame de la torre eiffel", [], ["330", "1889"]),
        ("The first Moon landing was in 1969.", "When did people first walk on the Moon?", [], ["1969"]),
        ("Se conocen más de 5.000 exoplanetas.", "¿Qué es un exoplaneta?", [], ["5.000"]),
        ("Chile tiene unos 19 millones de habitantes.", "cuéntame algo de chile", [], ["19"]),
        ("El agua hierve a 100 °C al nivel del mar.", "por qué hierve el agua", [], ["100"]),
        # With numbers in the conversation only a year is judged; a year nobody wrote is still memory.
        ("Its sequel came out in 2024.", "and the sequel?", ["Tell me about Dune", "Dune is a 2021 film."], ["2024"]),
    ],
)
def test_figures_no_one_said_are_memory(reply: str, asked: str, dialogue: list[str], expected: list[str]) -> None:
    assert llm.talk_memory_figures(reply, asked, dialogue, dialogue[::2]) == expected


@pytest.mark.parametrize(
    ("reply", "asked", "dialogue"),
    [
        ("Windows 11 trae el menú de inicio centrado.", "¿qué tiene de nuevo windows?", []),
        # Inside a sentence; at its start («Apollo 11 llevó…») a capitalized word is not told from «Hay 669…».
        ("La misión Apollo 11 llevó a tres astronautas.", "háblame de la misión apolo", []),
        ("Hay 669 números primos entre 1 y 5000.", "¿Cuántos primos hay entre 1 y 5000?", []),
        ("Cumplirás 30 en 2025.", "nací en 1995, ¿en qué año cumplo 30?", []),
        ("That is about 37.8 °C.", "and in Celsius?", ["what's 100 F in celsius", "100 °F is hot."]),
        ("Dune came out in 2021, as I said.", "when was that again?", ["Tell me about Dune", "Dune is a 2021 film."]),
        ("Un buen nombre sería Rojo Carmesí (#B22222).", "dame un color con su código", []),
        ("Ganó el Mundial de 2010 con España.", "¿qué ganó Iniesta en 2010?", []),
    ],
)
def test_figures_the_conversation_grounds_pass(reply: str, asked: str, dialogue: list[str]) -> None:
    assert llm.talk_memory_figures(reply, asked, dialogue, dialogue[::2]) == []


def test_only_the_sentences_with_a_figure_from_memory_are_dropped() -> None:
    reply = "Es una película dramática. Se estrenó en 2019. Te va a gustar."

    assert llm._without_memory_figures(reply, ["2019"]) == "Es una película dramática. Te va a gustar."
    assert llm._without_memory_figures("Se estrenó en 2019.", ["2019"]) == ""
    # «2019» inside another number is not that figure.
    assert llm._without_memory_figures("Cuesta 20190 pesos.", ["2019"]) == "Cuesta 20190 pesos."


def test_code_and_written_content_are_not_judged() -> None:
    facts = {"situation": json.dumps({"kind": "conversation"}), "priorRequests": []}

    assert llm.compose_visible_defect(
        "```python\nprint(2019)\n```", "conversation", "escribe un programa en python que imprima un año", facts,
    ) != "memory_figures"
    writer = _Writer(["Había una vez 3 hermanos que vivían en 1890 en un pueblo pequeño."])
    reply, _ = writer.chat("cuéntame un cuento corto", history=[], conversation_kind="knowledge",
                           response_language="es", temperature=0.0)
    assert reply == "Había una vez 3 hermanos que vivían en 1890 en un pueblo pequeño."


# ------------------------------------------------------------------ the ⚠ of v3x (HEAD 817dde50) on the reply side

S014 = EVIDENCE["v3x:D-s014"]
S017 = EVIDENCE["v3x:D-s017"]


def test_an_hour_the_read_does_not_cover_is_answered_with_the_days_figures() -> None:
    # Both recorded drafts said the hour was not in the forecast and gave the day's read; both were refused for not
    # giving the temperature now, and the turn ended with no answer.
    assert len(S014["drafts"]) == 2
    for draft in S014["drafts"]:
        assert llm._payload_fact_defect(draft, S014["payload"], S014["text"]) == ""


@pytest.mark.parametrize(
    ("draft", "asked"),
    [
        # M93 stays: the hour asked is said unread or named.
        ("Hoy en Curicó hay una máxima de 19.5 °C y una mínima de 11.5 °C.", "¿qué previsión de tiempo hay para las cuatro?"),
        # With no hour asked, the weather now is the temperature now.
        ("Hoy en Curicó hay una máxima de 19.5 °C y una mínima de 11.5 °C.", "¿qué tiempo hace en curicó?"),
        # A figure the read does not carry is no figure of the day.
        ("No tengo el pronóstico para las cuatro; en Curicó habrá unos 17 °C.", "¿qué previsión de tiempo hay para las cuatro?"),
    ],
)
def test_the_weather_report_still_carries_what_was_read(draft: str, asked: str) -> None:
    assert llm._payload_fact_defect(draft, S014["payload"], asked) != ""


def test_no_recipe_is_asked_of_memory() -> None:
    # Four drafts of a whole recipe from memory were refused for «Cook the macaroni according to package directions»
    # (M92's check of a recipe from memory) and the turn ended with no answer. With no recipe said from memory (D52), the
    # writer is not asked and the search's «no lo encontré» stands.
    assert S017["reason"] == "memory_recipe_incomplete"
    writer = _Writer([S017["from_memory_draft"]])
    failure = {"kind": "failure", "reason": {"operation": "web.search", "error": "web_search_results_irrelevant"}}
    assert writer._compose_consulted_answer(S017["text"], {}, failure, "en", writer._post, None, "t", memory=True) is None
    assert writer.sent == []


# ------------------------------------------------------------------ the invented turns of the v3x review

FAILED_SEARCH = {"kind": "failure", "reason": {"operation": "web.search", "error": "web_search_results_irrelevant"}}


def _read(payload: dict) -> dict:
    return {"kind": "operation", "operation": "web.search", "polarity": "success", "verified": True, "succeeded": True,
            "observed": payload["seen"]}


def test_d_w10_t1_the_recipe_from_memory_is_not_asked() -> None:
    case = EVIDENCE["v3x:D-w10-t1"]
    assert "1 taza de agua caliente" in case["published"] and case["invented"]
    writer = _Writer([case["published"]])
    for memory in (False, True):
        assert writer._compose_consulted_answer(
            case["text"], {}, FAILED_SEARCH, "es", writer._post, None, "t", memory=memory,
        ) is None
    assert writer.sent == []


def test_d_p31_t1_a_memory_list_written_twice_is_refused() -> None:
    case = EVIDENCE["v3x:D-p31-t1"]
    recorded = next(stage["draft"] for stage in case["stages"] if stage["stage"] == "from_memory")
    assert recorded == case["published"]
    assert llm._memory_list_repeats(recorded)
    writer = _Writer([recorded])

    assert writer._compose_consulted_answer(
        case["text"], {}, FAILED_SEARCH, "es", writer._post, None, "t", memory=True,
    ) is None
    assert "Escribiste las mismas líneas dos veces" in _said_to_the_model(writer.sent[1])


@pytest.mark.parametrize(
    "draft",
    [
        "No pude comprobarlo; de memoria, puede no ser exacto:\n1. Raúl Alfonsín\n2. Carlos Menem\n3. Fernando de la Rúa",
        "No pude comprobarlo; de memoria, puede no ser exacto:\nIngredientes:\n- harina\n- agua\nPreparación:\n1. Mezcla.",
        "I couldn't check this; from memory, it may not be exact: it is a dark comedy about two brothers.",
    ],
)
def test_a_memory_answer_that_says_each_thing_once_passes(draft: str) -> None:
    assert not llm._memory_list_repeats(draft)


def test_d_p34_t2_the_answer_puts_in_the_first_answer_what_it_never_said() -> None:
    case = EVIDENCE["v3x:D-p34-t2"]
    dialogue = _dialogue(case)
    assert "NASA" not in " ".join(dialogue)

    assert llm.talk_misquotes_itself(case["published"], dialogue) == ["NASA", "Back to the Future"]
    honest = (
        "En mi primera respuesta busqué las fechas y el contenido de cápsulas del tiempo famosas y no encontré ninguna "
        "página que los diera. Otro significado es el de las cápsulas de medicamentos que liberan el fármaco poco a poco."
    )
    assert llm.talk_misquotes_itself(honest, dialogue) == []


def test_d_p34_t2_the_retry_gets_the_earlier_answers_word_for_word() -> None:
    case = EVIDENCE["v3x:D-p34-t2"]
    honest = (
        "En la primera pregunta entendí las cápsulas del tiempo como objetos guardados para el futuro; otro significado "
        "es el de las cápsulas de medicamentos."
    )
    writer = _Writer([case["published"], json.dumps({"answer": honest})])

    reply, _ = writer.chat(case["text"], history=[dict(item) for item in case["lived"]], conversation_kind="knowledge",
                           response_language="es", temperature=0.0)

    assert reply == honest
    retry = _said_to_the_model(writer.sent[1])
    assert "No dijeron «NASA», «Back to the Future»" in retry
    assert case["lived"][1]["content"][:60] in retry


def test_d_p34_t2_a_retry_that_still_misquotes_loses_that_sentence() -> None:
    case = EVIDENCE["v3x:D-p34-t2"]
    still = "En mi primera respuesta hablé de las de la NASA. Otro significado es el de las cápsulas de medicamentos."
    writer = _Writer([case["published"], json.dumps({"answer": still})])

    reply, _ = writer.chat(case["text"], history=[dict(item) for item in case["lived"]], conversation_kind="knowledge",
                           response_language="es", temperature=0.0)

    assert reply == "Otro significado es el de las cápsulas de medicamentos."


@pytest.mark.parametrize(
    "reply",
    [
        "I said Dune came out in 2021.",  # the conversation says it
        "Antes te dije que la reunión es con Marta.",
        "La Torre Eiffel está en París.",  # not about BAXY's earlier answer
        # v3l D-p34-t2: a quoted phrase, the other meaning offered, is no name.
        "Entendí «cápsulas del tiempo» como objetos guardados, pero también podría referirse a las «time capsules» de "
        "la cultura popular.",
    ],
)
def test_what_the_conversation_carries_is_not_a_misquote(reply: str) -> None:
    dialogue = ["Tell me about Dune", "Dune came out in 2021.", "¿con quién es la reunión?", "Es con Marta."]
    assert llm.talk_misquotes_itself(reply, dialogue) == []


def test_d_w15_t4_a_note_written_with_a_description_is_not_told_as_holding_it() -> None:
    case = EVIDENCE["v3x:D-w15-t4"]
    payload = case["payload"]
    assert payload["seen"]["content"] == "resumen del informe trimestral de Documentos"

    assert llm._payload_fact_defect(case["published"], payload, case["text"]) == "note_content_described"
    for honest in (
        "He guardado la nota «reunion jueves».",
        "He guardado la nota «reunion jueves» con el texto «resumen del informe trimestral de Documentos».",
    ):
        assert llm._payload_fact_defect(honest, payload, case["text"]) != "note_content_described"


def test_an_ordinary_note_is_told_with_its_text() -> None:
    payload = {"operation": "note.create", "seen": {"title": "compras", "content": "leche, pan y huevos"}}
    assert not llm._note_content_described("He guardado la nota «compras» con leche, pan y huevos.", payload)
    listed = {"operation": "note.create", "seen": {"title": "viaje", "content": "lista de cosas para la playa: toalla"}}
    assert llm._note_content_described("Guardé la nota «viaje» con la lista de cosas para la playa.", listed)


# ------------------------------------------------------------------ a not-found over a read that answers


def _after_not_found(writer: _Writer, case: dict, not_found: str) -> str:
    facts = {"situation": json.dumps(_read(case["payload"]), ensure_ascii=False)}
    return writer._answer_after_not_found(not_found, case["text"], facts, said=case["text"], deadline=None)


def test_d_w14_t1_what_the_pages_state_of_this_years_event_is_said() -> None:
    case = EVIDENCE["v3x:D-w14-t1"]
    assert case["published"] == "No encontré quién ha ganado la Vuelta este año."
    writer = _Writer(["Mas ha ganado la Vuelta a España."])

    assert _after_not_found(writer, case, case["published"]) == "Mas ha ganado la Vuelta a España."
    assert "ha ganado la Vuelta a España" in _said_to_the_model(writer.sent[0])


def test_d_w14_t1_last_years_winner_is_not_said_and_memory_is_not_asked() -> None:
    case = EVIDENCE["v3x:D-w14-t1"]
    writer = _Writer(["Jonas Vingegaard ganó La Vuelta 2025."])

    assert _after_not_found(writer, case, case["published"]) == ""
    # Two partial drafts, both refused for the other year; no answer from memory after them.
    assert len(writer.sent) == 2


def test_d_w01_t2_tallarines_are_pasta_to_the_page_filter() -> None:
    case = EVIDENCE["v3x:D-w01-t2"]
    seen = case["payload"]["seen"]
    rule = next(item for item in seen["results"] if "regla del 1, 100 y 10" in item["title"])
    assert llm._search_result_is_about(seen["query"], rule, False)
    writer = _Writer(["Se suele usar la regla del 1, 100 y 10."])

    assert _after_not_found(writer, case, "No encontré una cifra exacta.") == "Se suele usar la regla del 1, 100 y 10."
    assert "regla del 1, 100 y 10" in _said_to_the_model(writer.sent[0])
