"""M92 (D52): the figures said from memory and the kitchen amounts told without the read, from the independent review
of the window DEV-D run v3u (HEAD 30861483).

Each case is a real turn of window/v3u-devD: its drafts, payloads and dialogue are the recorded ones
(tests/data/c03_m92_v3u_evidence.json, from REVIEW.reviewed.jsonl and compose-audit.jsonl; «v3r:D-w10-t1» from
v3r-devD, the recipe from memory the review found right).

- D-s111 «¿Cuál es la distancia de Barcelona a París?» → «de memoria… unos 1.100 kilómetros… 2 horas y media… entre 8 y
  9 horas» (wrong). D52: the answer from memory (D35) stays for what is not a figure; a quantity, distance, duration,
  date, year or count asked is looked up and, if that is impossible, said not found (semantic.knowledge.asks_a_figure).
- D-w01-t3 «ya y pa 3 litros cuántas cucharaditas serían» → «de memoria… unas 600 cucharaditas»: the same rule; and the
  read did carry «sal por litro … es de 10 gramos»: the three drafts computed it wrong (1,5, 30–75, 150). The rule
  applied to the quantity asked is BAXY's own calculation (semantic.quantities.rated_totals, payload
  «rule_calculation»), and a report that does not give it is refused (``rule_calculation_not_given``).
- D-p29-t2 «Search for scary movies.» → a list from memory with «It (1982)»: a list or prose from memory says no figure
  the person did not say; the bracketed years of a list are dropped (semantic.quantities.unsaid_figures,
  without_listed_years).
- D-w10-t1 «¿me regalas una receta sencilla de arepas de queso?» → a recipe from memory with no quantity and «prepara la
  masa según la receta habitual». A recipe is the one form memory gives with figures (D35; v3r's was right), and only
  whole: every ingredient with its round quantity and no step pointing elsewhere (``memory_recipe_incomplete``).
- D-w01-t2 «cuánta sal le echo al agua, más o menos» → «Se le pone a gusto.»: an amount asked is answered with a figure
  or told not found (``amount_without_figure``).
- D-w10-t2 «¿Y cuánto sería eso de harina en gramos?» → «Un conversor de cocina menciona…»: a converter, a table or a
  guide that speaks is the search shown.
"""

from __future__ import annotations

import copy
import json
from fractions import Fraction
from pathlib import Path

import pytest

from baxy_mind import llm
from baxy_mind.semantic import knowledge, quantities

EVIDENCE = json.loads((Path(__file__).parent / "data" / "c03_m92_v3u_evidence.json").read_text(encoding="utf-8"))
M83_TURNS = json.loads(
    (Path(__file__).parent / "data" / "c03_m83_v3o_search_turns.json").read_text(encoding="utf-8")
)["turns"]
FAILURE = {"kind": "failure", "reason": {"operation": "web.search", "error": "web_search_results_irrelevant"}}


def _case(ident: str) -> dict:
    return EVIDENCE[ident]


def _stage(ident: str, stage: str) -> dict:
    return next(item for item in _case(ident)["stages"] if item["stage"] == stage)


def _search_payload(ident: str) -> dict:
    if ident.endswith("D-w10-t1"):
        # The recipe turn recorded only its answer from memory, whose situation the audit cut at 2 048 characters; the
        # read is the same query's in v3o (M83's evidence): the encyclopedia's «Arepa», no recipe.
        return M83_TURNS["D-w10-t1"]["payload"]
    return next(
        item["payload"] for item in _case(ident)["stages"]
        if isinstance(item["payload"], dict) and item["payload"].get("operation") == "web.search"
    )


def _search_situation(ident: str) -> dict:
    return {
        "kind": "operation", "operation": "web.search", "polarity": "success", "verified": True, "succeeded": True,
        "observed": _search_payload(ident)["seen"],
    }


def _blocked(draft: str, ident: str) -> str:
    """The compose loop's checks over the recorded search payload of the turn."""

    text = _case(ident)["text"]
    payload = _search_payload(ident)
    facts = {"situation": json.dumps(_search_situation(ident), ensure_ascii=False)}
    return (
        llm.compose_visible_defect(draft, "status", text, facts)
        or ("invented" if llm._truncated_fact_word(draft, payload) else "")
        or llm._payload_fact_defect(draft, payload, text, said=text)
    )


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


def _memory(writer: _Writer, ident: str, request: str | None = None, situation: dict | None = None) -> str | None:
    stage = _stage(ident, "from_memory")
    facts = {"priorRequests": list(stage["payload"].get("earlier_requests") or [])}
    return writer._compose_consulted_answer(
        request or stage["payload"]["request"], facts, situation or _search_situation(ident), stage["language"],
        writer._post, None, "t", memory=True,
    )


# ------------------------------------------------------------------ a figure asked is not said from memory


@pytest.mark.parametrize(
    "text",
    [
        "¿Cuál es la distancia de Barcelona a París?",  # D-s111
        "ya y pa 3 litros cuántas cucharaditas serían",  # D-w01-t3
        "oye y cuánta sal le echo al agua, más o menos, cachai",  # D-w01-t2
        "¿Y cuánto sería eso de harina en gramos, por favor?",  # D-w10-t2
        "How far is Paris from Berlin?", "how many moons does Mars have", "What year did the war end?",
        "¿En qué año se fundó Roma?", "¿cuándo nació Napoleón?", "¿Cuántos habitantes tiene Chile?",
        "cuál es la población de Chile", "¿qué tan alto es el Everest?",
    ],
)
def test_what_asks_a_figure_is_read(text: str) -> None:
    assert knowledge.asks_a_figure(text)


@pytest.mark.parametrize(
    "text",
    [
        "Search for scary movies.",  # D-p29-t2
        "Buenas, qué pena la molestia, ¿me regalas una receta sencilla de arepas de queso?",  # D-w10-t1
        "Can you find me some movies featuring Gil Bellows?", "¿Qué es un exoplaneta?", "¿Quién fue Napoleón?",
        "¿cuánto te gusta el chocolate?", "en cuanto a la historia, ¿quién fundó Roma?", "tell me about the Eiffel tower",
    ],
)
def test_what_asks_no_figure_is_not_read_as_one(text: str) -> None:
    assert not knowledge.asks_a_figure(text)


@pytest.mark.parametrize("ident", ["D-s111", "D-w01-t3"])
def test_the_recorded_figures_from_memory_are_not_asked_nor_said(ident: str) -> None:
    writer = _Writer([_stage(ident, "from_memory")["draft"]])
    assert _memory(writer, ident) is None
    assert writer.sent == []


def test_d_s111_the_not_found_report_stands() -> None:
    reply = _stage("D-s111", "third")["draft"]
    writer = _Writer([_stage("D-s111", "from_memory")["draft"]])
    facts = {"situation": json.dumps(_search_situation("D-s111"), ensure_ascii=False)}
    assert writer._answer_after_not_found(reply, _case("D-s111")["text"], facts, said=None, deadline=None) == ""
    assert writer.sent == []


def test_a_failed_quantity_lookup_is_not_answered_from_memory_either() -> None:
    writer = _Writer(["No pude comprobarlo; de memoria, puede no ser exacto: unos 30 gramos."])
    assert writer._compose_consulted_answer(
        "¿cuánta sal le echo al agua de los tallarines?", {}, FAILURE, "es", writer._post, None, "t",
    ) is None
    assert writer.sent == []


# ------------------------------------------------------------------ prose and lists from memory say no figure


def test_d_p29_t2_the_recorded_list_is_said_without_its_years() -> None:
    recorded = _stage("D-p29-t2", "from_memory")["draft"]
    assert quantities.unsaid_figures(recorded, [_case("D-p29-t2")["text"]]) == [
        "1982", "1979", "2018", "1973", "2017", "1980", "2012", "2013",
    ]
    writer = _Writer([recorded])
    reply = _memory(writer, "D-p29-t2")
    assert reply is not None and "It\n" in reply and "(" not in reply and "1982" not in reply
    assert len(writer.sent) == 1
    # The list is asked with no figure at all.
    assert "with no figure at all" in writer.sent[0]["messages"][0]["content"]


def test_a_figure_in_prose_from_memory_is_written_again_without_it() -> None:
    with_year = (
        "I couldn't check this; from memory, it may not be exact: The Lord of the Rings: The Fellowship of the Ring "
        "came out in 2001 and is a fantasy film starring Elijah Wood."
    )
    without = (
        "I couldn't check this; from memory, it may not be exact: The Lord of the Rings: The Fellowship of the Ring "
        "is a fantasy film starring Elijah Wood."
    )
    writer = _Writer([with_year, without])
    assert _memory(writer, "D-p24-t1") == without
    assert "remove 2001" in writer.sent[1]["messages"][-1]["content"]
    # Two drafts with a figure leave the not-found report standing.
    assert _memory(_Writer([with_year]), "D-p24-t1") is None


def test_d_p24_t1_the_recorded_answer_without_figures_is_said_as_it_was() -> None:
    recorded = _stage("D-p24-t1", "from_memory")["draft"]
    assert _memory(_Writer([recorded]), "D-p24-t1") == recorded


@pytest.mark.parametrize(
    ("draft", "said"),
    [
        # A number that is part of a name is the name.
        ("I couldn't check this; from memory:\n1. Apollo 13\n2. 28 Days Later\n3. Scary Movie 3", "space films"),
        ("No pude comprobarlo; de memoria: la película Ocean's 11 es de atracos.", "películas de atracos"),
        # A figure the person said is theirs.
        ("No pude comprobarlo; de memoria: estas 5 son de terror.", "dime 5 películas de terror"),
    ],
)
def test_figures_that_are_names_or_the_persons_are_kept(draft: str, said: str) -> None:
    assert quantities.unsaid_figures(draft, [said]) == []


@pytest.mark.parametrize(
    ("draft", "figures"),
    [
        ("No pude comprobarlo; de memoria: En 1492 llegó a América.", ["1492"]),
        ("I couldn't check this; from memory: it is about 1,000 km away.", ["1,000"]),
        ("No pude comprobarlo; de memoria: tiene cientos de miles de empleados y dura dos horas.",
         ["cientos de", "miles de", "dos horas"]),
    ],
)
def test_figures_memory_does_not_say(draft: str, figures: list[str]) -> None:
    assert quantities.unsaid_figures(draft, ["cuéntame"]) == figures


# ------------------------------------------------------------------ a recipe from memory is a whole one


def test_d_w10_t1_the_recorded_recipe_without_quantities_is_no_recipe() -> None:
    recorded = _stage("D-w10-t1", "from_memory")["draft"]
    assert llm._memory_recipe_incomplete(recorded)
    whole = _stage("D-w10-t1", "from_memory")["draft"].split("Ingredientes:")[0] + (
        "Ingredientes:\n- 2 tazas de harina de maíz precocida\n- 2 tazas de agua tibia\n- 1 cucharadita de sal\n"
        "- 1 taza de queso rallado\n- Aceite para freír\n\nPreparación:\n1. Mezcla la harina, el agua y la sal.\n"
        "2. Añade el queso y forma bolas aplastadas.\n3. Dóralas en la sartén unos 5 minutos por lado."
    )
    writer = _Writer([recorded, whole])
    situation = _search_situation("D-w10-t1")
    reply = writer._compose_consulted_answer(
        "Dame una receta sencilla de arepas de queso.", {}, situation, "es", writer._post, None, "t",
    )
    assert reply == whole
    assert "cada uno con su cantidad" in writer.sent[0]["messages"][0]["content"]
    assert "sin remitir a otra receta" in writer.sent[1]["messages"][-1]["content"]


def test_the_whole_recipe_from_memory_of_v3r_is_still_said() -> None:
    recorded = _stage("v3r:D-w10-t1", "from_memory")["draft"]
    assert not llm._memory_recipe_incomplete(recorded)
    writer = _Writer([recorded])
    assert writer._compose_consulted_answer(
        "Dame una receta sencilla de arepas de queso.", {}, _search_situation("D-w10-t1"), "es", writer._post, None,
        "t",
    ) == recorded


# ------------------------------------------------------------------ a per-unit rule read, applied to the quantity asked


def test_d_w01_t3_the_rule_read_is_applied_to_the_litres_asked() -> None:
    evidence = llm._search_results_text(_search_payload("D-w01-t3"))
    totals = quantities.rated_totals(_case("D-w01-t3")["text"], evidence)
    assert [item.sentence for item in totals] == ["3 litros × 10 gramos por litro = 30 gramos"]
    # The read gives what a tablespoon of coarse salt weighs, not a teaspoon: no teaspoons are counted.
    assert totals[0].values == (Fraction(30),)
    payload = llm._compose_situation_payload(_search_situation("D-w01-t3"), "es", _case("D-w01-t3")["text"])
    assert payload["rule_calculation"] == ["3 litros × 10 gramos por litro = 30 gramos"]


def test_spoons_are_counted_only_with_the_weight_of_that_spoon() -> None:
    read = "Se usan 10 g de sal por litro. Una cucharadita de sal pesa unos 5 gramos."
    assert [item.sentence for item in quantities.rated_totals("cuántas cucharaditas de sal para 3 litros", read)] == [
        "3 litros × 10 g por litro = 30 g = 6 cucharaditas",
    ]
    assert [item.sentence for item in quantities.rated_totals("cuántas cucharadas de sal para 3 litros", read)] == [
        "3 litros × 10 g por litro = 30 g",
    ]


@pytest.mark.parametrize(
    ("request_text", "read"),
    [
        ("cuánta sal le echo al agua", "Se usan 10 g de sal por litro."),  # no quantity asked
        ("para 3 litros", "Media cucharadita de sal por litro de agua."),  # no figure in a unit
        ("para 3 litros", "La receta lleva 700 gramos de harina y 4 huevos."),  # no rule per unit
    ],
)
def test_no_rule_no_calculation(request_text: str, read: str) -> None:
    assert quantities.rated_totals(request_text, read) == []


def test_d_w01_t3_the_recorded_drafts_without_the_calculation_are_refused() -> None:
    for stage in ("first", "third"):
        assert _blocked(_stage("D-w01-t3", stage)["draft"], "D-w01-t3") == "rule_calculation_not_given"
    assert _blocked("Para 3 litros, unos 30 gramos de sal.", "D-w01-t3") == ""
    # A not-found is always a report (the last resort stays publishable).
    assert _blocked("No lo encontré.", "D-w01-t3") == ""


def test_d_w01_t3_the_writer_gets_the_calculation_and_is_told_it_again() -> None:
    answer = "Para 3 litros, unos 30 gramos de sal."
    writer = _Writer([_stage("D-w01-t3", "first")["draft"], answer])
    facts = {"situation": json.dumps(_search_situation("D-w01-t3"), ensure_ascii=False)}

    reply = writer.compose_user_message(_case("D-w01-t3")["text"], "status", facts)

    assert reply == answer
    first = "\n".join(str(message["content"]) for message in writer.sent[0]["messages"])
    assert "3 litros × 10 gramos por litro = 30 gramos" in first
    assert "rule_calculation aplica a la cantidad pedida" in first
    assert "Contesta con el cálculo de BAXY" in "\n".join(str(m["content"]) for m in writer.sent[1]["messages"])


# ------------------------------------------------------------------ an amount asked is answered with a figure


def test_d_w01_t2_an_amount_answered_to_taste_is_refused() -> None:
    recorded = _stage("D-w01-t2", "first")["draft"]
    assert recorded == "Se le pone a gusto."
    assert _blocked(recorded, "D-w01-t2") == "amount_without_figure"
    payload = _search_payload("D-w01-t2")
    evidence = llm._search_results_text(payload)
    text = _case("D-w01-t2")["text"]
    assert llm._amount_report_defect("No encontré cuánta sal le echo al agua.", payload, text, evidence) == ""
    assert llm._amount_report_defect("Unos 10 gramos por litro.", payload, text, evidence) == ""
    assert llm._amount_report_defect("Una cucharada por litro.", payload, text, evidence) == ""


def test_d_w01_t2_the_writer_is_told_an_amount_was_asked() -> None:
    honest = "No encontré cuánta sal se le echa al agua."
    writer = _Writer([_stage("D-w01-t2", "first")["draft"], honest])
    facts = {"situation": json.dumps(_search_situation("D-w01-t2"), ensure_ascii=False)}

    reply = writer.compose_user_message(_case("D-w01-t2")["text"], "status", facts)

    assert reply == honest
    assert "La persona preguntó una cantidad" in "\n".join(str(m["content"]) for m in writer.sent[0]["messages"])
    assert "Se preguntó una cantidad" in "\n".join(str(m["content"]) for m in writer.sent[1]["messages"])


def test_pages_that_state_no_quantity_leave_a_plain_answer() -> None:
    # «¿cuánta agua conviene beber según la OMS?» over «conviene beber agua a lo largo del día»: nothing answer-shaped.
    payload = {"operation": "web.search", "seen": {"query": "cuanta agua beber", "results": [
        {"title": "Consejos", "url": "https://salud.example.org", "snippet": "Conviene beber agua a lo largo del día."},
    ]}}
    reply = "Conviene beber agua a lo largo del día."
    assert llm._amount_report_defect(reply, payload, "¿cuánta agua conviene beber?", reply) == ""


def test_a_search_that_asks_no_amount_is_not_held_to_a_figure() -> None:
    payload = _search_payload("D-p24-t1")
    evidence = llm._search_results_text(payload) or ""
    assert llm._amount_report_defect(
        "Es una película de fantasía con Elijah Wood.", payload, _case("D-p24-t1")["text"], evidence,
    ) == ""


# ------------------------------------------------------------------ a converter that speaks is the search shown


def test_d_w10_t2_a_converter_that_mentions_is_the_search_shown() -> None:
    recorded = _stage("D-w10-t2", "retry")["draft"]
    assert recorded.startswith("Un conversor de cocina menciona")
    payload = _search_payload("D-w10-t2")
    text = _case("D-w10-t2")["text"]
    assert llm._search_report_shows_the_search(recorded, payload, text)
    assert llm._search_report_shows_the_search("A kitchen converter mentions that flour is lighter.", payload, text)
    assert not llm._search_report_shows_the_search("La harina es más ligera que el azúcar.", payload, text)
