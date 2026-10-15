"""Estabilización TZ-VETO: un dato que el redactor vetó por no estar en la fuente no se publica en el reintento.

Tandas finales z1 (main 8d90cc2d0), t2-c01 t4 «oye y cuantos discos de estudio tienen los bunkers?». La búsqueda sólo
leyó la página de la canción «Ven aquí» (``tests/data/tz_veto_bunkers.json``, entradas congeladas de
``compose_audit.jsonl``). El primer borrador «…tienen al menos un disco de estudio, Vida de perros…» cayó como
search_report_unsourced_claim sólo por «menos»; la pista pidió quitar esa palabra y conservar el resto, y el reintento
publicó «Un disco de estudio: Vida de perros.». Ningún control juzgaba una cuenta de uno: «un», «una» son también
artículos (search_report._REPORT_COUNT_WORDS empieza en dos). Ahora la respuesta a un «cuántos» que dice uno de lo
contado necesita una frase de un resultado que diga uno de eso (semantic.answer_evidence.answer_unstated), y ese veto se
juzga antes que las palabras sueltas, con su pista de «no lo encontré».
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from baxy_mind import payload_fact_checks, search_report
from baxy_mind.llm import LlmRuntime
from baxy_mind.semantic import answer_evidence

ROW = json.loads((Path(__file__).parent / "data" / "tz_veto_bunkers.json").read_text(encoding="utf-8"))
SAID = ROW["said"]
SITUATION = ROW["situation"]


def _payload(situation: str = SITUATION) -> dict:
    observed = json.loads(situation)["observed"]
    return {"seen": {key: observed[key] for key in ("query", "count", "results", "authority")}, "operation": "web.search"}


def _with_snippet(snippet: str) -> str:
    situation = json.loads(SITUATION)
    situation["observed"]["results"][0]["snippet"] = snippet
    return json.dumps(situation, ensure_ascii=False)


class _Drafts(LlmRuntime):
    """The drafts stand in for the model in order (the last one repeats); every request is kept."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = None
        self.drafts = list(drafts)
        self.requests: list[dict] = []

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.requests.append(copy.deepcopy(payload))
        content = self.drafts.pop(0) if len(self.drafts) > 1 else self.drafts[0]
        return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}


def _system_text(request: dict) -> str:
    return "\n".join(str(message.get("content") or "") for message in request["messages"] if message["role"] == "system")


# ------------------------------------------------------------------ the measured cause, on the frozen entries

def test_the_frozen_first_draft_died_only_on_the_hedge_before() -> None:
    # The cause: the words check named «menos» alone, never the count, so dropping the hedge made it pass.
    assert ROW["first_reason"] == "search_report_unsourced_claim"
    assert search_report._search_report_unsourced_words(ROW["first_draft"], _payload(), SAID) == ["menos"]
    assert search_report._search_report_unsourced_words(ROW["retry_draft"], _payload(), SAID) == []


@pytest.mark.parametrize("draft", [ROW["first_draft"], ROW["retry_draft"], "Los Bunkers tienen un disco de estudio."])
def test_a_count_of_one_no_result_says_is_the_unstated_answer(draft: str) -> None:
    assert payload_fact_checks._payload_fact_defect(draft, _payload(), SAID, said=SAID) == "search_report_answer_unstated"
    assert search_report._search_report_answer_unstated(draft, _payload(), SAID)[0].startswith("un")


@pytest.mark.parametrize(
    "draft",
    [
        ROW["z2_final"],
        "No encontré cuántos discos de estudio tienen Los Bunkers; leí que «Ven aquí» es del disco Vida de perros.",
    ],
)
def test_the_not_found_and_what_the_page_says_pass(draft: str) -> None:
    assert payload_fact_checks._payload_fact_defect(draft, _payload(), SAID, said=SAID) == ""


def test_the_frozen_turn_never_publishes_the_count_again() -> None:
    # The model of z1, draft for draft: the first, then the retry that dropped the hedge, said again by every later
    # draft (the third, and what the pages state after the not-found, M83).
    writer = _Drafts([ROW["first_draft"], ROW["retry_draft"]])
    reply = writer.compose_user_message(SAID, "status", {"situation": SITUATION}, said=SAID)
    assert "un disco" not in reply.casefold()
    assert reply.casefold() == ROW["z2_final"].casefold()
    # The retry is told which answer no result states and to say it was not found, not to keep the rest.
    hint = _system_text(writer.requests[1])
    assert "«un disco»" in hint
    assert "que no lo encontraste" in hint
    assert "Conserva el resto tal cual" not in hint


def test_a_retry_that_says_it_was_not_found_is_published() -> None:
    writer = _Drafts([ROW["first_draft"], ROW["z2_final"]])
    reply = writer.compose_user_message(SAID, "status", {"situation": SITUATION}, said=SAID)
    assert reply.casefold() == ROW["z2_final"].casefold()


def test_after_the_not_found_what_the_page_does_say_is_published() -> None:
    # M83: what the page states of what was asked replaces the bare not-found, held to the same checks.
    said = "«Ven aquí» es la primera canción del disco Vida de perros."
    writer = _Drafts([ROW["first_draft"], ROW["z2_final"], said])
    assert writer.compose_user_message(SAID, "status", {"situation": SITUATION}, said=SAID) == said


# ------------------------------------------------------------------ contracasos: the source gives the count

ONLY_ONE = _with_snippet("Vida de perros es el único disco de estudio de la banda chilena Los Bunkers.")
SEVEN = _with_snippet("Los Bunkers han publicado siete álbumes de estudio desde 1999.")


def test_a_count_of_one_the_page_says_is_published() -> None:
    draft = "Los Bunkers tienen un disco de estudio: Vida de perros."
    assert payload_fact_checks._payload_fact_defect(draft, _payload(ONLY_ONE), SAID, said=SAID) == ""
    writer = _Drafts([draft])
    assert writer.compose_user_message(SAID, "status", {"situation": ONLY_ONE}, said=SAID) == draft
    assert len(writer.requests) == 1


def test_a_count_the_page_writes_is_published() -> None:
    draft = "Los Bunkers tienen siete discos de estudio."
    assert payload_fact_checks._payload_fact_defect(draft, _payload(SEVEN), SAID, said=SAID) == ""
    writer = _Drafts([draft])
    assert writer.compose_user_message(SAID, "status", {"situation": SEVEN}, said=SAID) == draft


def test_a_count_no_page_writes_is_still_refused() -> None:
    # What does not change: a count of two or more the pages do not write is judged by the report's figures (M88).
    assert payload_fact_checks._payload_fact_defect(
        "Los Bunkers tienen dos discos de estudio.", _payload(), SAID, said=SAID,
    ) == "search_report_unsourced_claim"


# ------------------------------------------------------------------ the reading, in both languages

@pytest.mark.parametrize(
    ("question", "counted"),
    [
        (SAID, ["discos", "estudio"]),
        ("how many studio albums do the Beatles have", ["studio", "albums"]),
        ("¿Cuántas canciones tiene Vida de perros?", ["canciones", "tiene"]),
        ("quién ganó el mundial del 2014", []),
        ("dame el disco de estudio de Los Bunkers", []),
    ],
)
def test_what_a_question_of_how_many_counts(question: str, counted: list[str]) -> None:
    assert answer_evidence.counted_words(question) == counted


@pytest.mark.parametrize(
    ("sentence", "found"),
    [
        ("Un disco de estudio: Vida de perros.", ["un disco"]),
        ("They have only one studio album.", ["one studio album"]),
        ("Es su único disco de estudio.", ["unico disco"]),
        # One among others is no count, nor is an article before another thing.
        ("«Ven aquí» es una de las canciones del disco.", []),
        ("Es una canción del disco Vida de perros.", []),
    ],
)
def test_where_a_sentence_says_one_of_the_thing_counted(sentence: str, found: list[str]) -> None:
    assert answer_evidence.counts_of_one(sentence, ["discos", "estudio", "albums"]) == found


def test_every_word_that_asks_a_count_is_a_question_of_how_much() -> None:
    # One reading: the words that ask a count (answer_evidence count_asked) are among those semantic.web reads as a
    # question of how much, whose answer a report may say is not confirmed.
    from baxy_mind.semantic.web import asked_dimension_words

    for asked in answer_evidence._words()["count_asked"]:
        assert "cantidad" in asked_dimension_words(f"{asked} discos tienen"), asked


def test_a_relation_question_keeps_its_own_judgement() -> None:
    # What does not change: «quién ganó» judges the names, and asks no count.
    results = [{"title": "Copa Mundial de Fútbol de 2014", "snippet": "Se realizó en Brasil."}]
    assert answer_evidence.answer_unstated(
        "Brasil ganó la Copa Mundial de Fútbol de 2014.", "quien gano el mundial del 2014", results,
        search_report._SEARCH_NOT_FOUND,
    ) == ["Brasil"]
