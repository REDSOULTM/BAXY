"""M88: the invented facts and the figures without a source of the independent review of the window DEV-D run v3r.

Each case is a real turn of window/v3r-devD (HEAD 50cee2c6): its drafts, payloads and dialogue are the recorded ones
(tests/data/c03_m88_v3r_evidence.json, from REVIEW.reviewed.jsonl and compose-audit.jsonl; D-w06-t4 from v3e2-devD).

- p24-t5 «That is confirmed to proceed.» after «I could not play Hustlers on Netflix…» (third run in a row): «I confirm
  the action will proceed.» with nothing played. Root cause: the writer of a conversation turn answering a go-ahead
  was never told that nothing ran and nothing was waiting for that yes, so every draft acknowledged it; the vetoes of
  M79/M85 chased its wordings. The go-ahead is read from the person's message (semantic.dialogue.gives_go_ahead), the
  writer is told the fact before it writes, and its answer must say it was not done (``go_ahead_not_done``).
- s111 «¿Cuál es la distancia de Barcelona a París?»: the answer from memory (D35) gave «1.080 km en línea recta» and
  «2 horas y 15 minutos». A figure from memory was said round. Superseded by M92 (D52): a figure asked is never said
  from memory; and by M95 (D52): nor is a recipe, so the round-figure rule is gone.
- p12-t2 (and v3e2 w06-t4): «There are five 24/7 stores…», «Hay dos pizzerías abiertas…» — five and two were how many
  pages were read. A count in words is judged like one in digits (llm._search_report_unsourced_counts).
- w01-t2, w01-t3, w10-t2: salt for the pasta water, teaspoons for 3 litres, grams of two cups of corn flour recited
  wrong. How much of an ingredient is looked up (semantic.knowledge.kitchen_quantity); a pure conversion between units
  of one kind is computed (semantic.quantities.conversion_asked).
"""

from __future__ import annotations

import copy
import json
from fractions import Fraction
from pathlib import Path

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import dialogue, knowledge, quantities
from baxy_mind.semantic.decider import ContextDecision

EVIDENCE = json.loads((Path(__file__).parent / "data" / "c03_m88_v3r_evidence.json").read_text(encoding="utf-8"))
CONVERSATION = json.dumps({"kind": "conversation", "polarity": "success"})


def _case(ident: str) -> dict:
    return EVIDENCE[ident]


def _stage(ident: str, stage: str = "first") -> dict:
    return next(item for item in _case(ident)["stages"] if item["stage"] == stage)


def _last_reply(ident: str) -> str:
    return next(item["content"] for item in reversed(_case(ident)["lived"]) if item["role"] == "assistant")


def _prior(ident: str) -> list[str]:
    return [item["content"] for item in _case(ident)["lived"] if item["role"] == "user"]


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


# ------------------------------------------------------------------ p24-t5: a go-ahead nothing was waiting for

P24_T5 = "D-p24-t5"
HONEST_EN = "I haven't played Hustlers yet: Netflix asks for a sign-in on this PC."


@pytest.mark.parametrize(
    "text",
    ["That is confirmed to proceed.", "Yes, do it for me.", "ok, hazlo", "adelante", "confirmo", "you may proceed",
     "go ahead please", "Confirmed.", "Está aprobado, procede."],
)
def test_a_go_ahead_is_read_from_the_persons_message(text: str) -> None:
    assert dialogue.gives_go_ahead(text)


@pytest.mark.parametrize(
    "text",
    [
        "sí", "ok", "dale", "vale",  # an answer or an acknowledgement
        "sigue", "continúa", "go on",  # more of a story or an answer: talk
        "confirma la alarma", "sigue sin funcionar", "¿procedo?", "Search for something else and I change my mind.",
    ],
)
def test_what_is_not_only_a_go_ahead_is_not_one(text: str) -> None:
    assert not dialogue.gives_go_ahead(text)


def test_after_a_question_the_go_ahead_answers_it() -> None:
    last = _last_reply(P24_T5)
    assert dialogue.go_ahead_with_nothing_pending(_case(P24_T5)["text"], last)
    assert not dialogue.go_ahead_with_nothing_pending(_case(P24_T5)["text"], "Do you want me to play Hustlers?")


def test_the_recorded_drafts_that_settle_the_go_ahead_are_refused() -> None:
    case = _case(P24_T5)
    facts = {"situation": CONVERSATION, "context": _last_reply(P24_T5), "priorRequests": _prior(P24_T5)}
    # The one the vetoes of M79 and M85 missed, and the two they caught, whatever their wording.
    assert llm.compose_visible_defect(_stage(P24_T5, "third")["draft"], "conversation", case["text"], facts) == (
        "go_ahead_not_done"
    )
    for stage in ("first", "retry"):
        assert llm.compose_visible_defect(_stage(P24_T5, stage)["draft"], "conversation", case["text"], facts)
    # Saying it was not done, and why, answers it (and is no denial of a write nobody asked for).
    assert llm.compose_visible_defect(HONEST_EN, "conversation", case["text"], facts) == ""
    spanish = {"situation": CONVERSATION, "context": "No pude poner Hustlers en Netflix: pide iniciar sesión en este PC."}
    assert llm.compose_visible_defect(
        "Todavía no lo he puesto: Netflix pide iniciar sesión en este PC.", "conversation", "ok, hazlo", spanish,
    ) == ""
    assert llm.compose_visible_defect("Perfecto, sigo adelante.", "conversation", "ok, hazlo", spanish) == (
        "go_ahead_not_done"
    )


def test_the_writer_is_told_before_it_writes_that_nothing_ran_nor_waited() -> None:
    case = _case(P24_T5)
    writer = _Writer([HONEST_EN])

    reply = writer.compose_user_message(
        case["text"], "conversation",
        {"situation": CONVERSATION, "context": _last_reply(P24_T5), "priorRequests": _prior(P24_T5)},
    )

    assert reply == HONEST_EN
    first = _said_to_the_model(writer.sent[0])
    assert "nothing ran this turn and nothing of yours was waiting for a yes" in first
    assert "I could not play Hustlers on Netflix" in first


def test_the_recorded_drafts_are_written_again_until_one_says_it_was_not_done() -> None:
    case = _case(P24_T5)
    drafts = [_stage(P24_T5, stage)["draft"] for stage in ("first", "retry", "third")]
    writer = _Writer([drafts[2], HONEST_EN])

    reply = writer.compose_user_message(
        case["text"], "conversation", {"situation": CONVERSATION, "context": _last_reply(P24_T5)},
    )

    assert reply == HONEST_EN
    assert "Never say it is confirmed, under way or will proceed" in _said_to_the_model(writer.sent[1])
    # With only the recorded drafts, none is published.
    assert _Writer(drafts).compose_user_message(
        case["text"], "conversation", {"situation": CONVERSATION, "context": _last_reply(P24_T5)},
    ) not in drafts


def test_the_minds_own_conversation_reply_is_held_to_the_same_answer() -> None:
    case = _case(P24_T5)
    history = [dict(item) for item in case["lived"] if not item["content"].startswith("[")]
    chat = _Writer([_stage(P24_T5, "third")["draft"], json.dumps({"answer": HONEST_EN})])

    reply, _ = chat.chat(case["text"], history=history, conversation_kind="knowledge", response_language="en",
                         temperature=0.0)

    assert reply == HONEST_EN
    assert "nothing of yours was waiting for a yes" in _said_to_the_model(chat.sent[0])
    assert "Never say it is confirmed" in _said_to_the_model(chat.sent[1])


# ------------------------------------------------------------------ s111: an answer from memory says round figures


def test_the_recorded_memory_answer_gives_figures_memory_cannot_hold() -> None:
    # Superseded by M92 (D52, no figure from memory) and M95 (no recipe from memory either): the recorded answer has
    # figures the person never said.
    draft = _stage("D-s111", "from_memory")["draft"]

    assert quantities.unsaid_figures(draft, [_case("D-s111")["text"]])


def test_a_figure_asked_is_never_answered_from_memory() -> None:
    # M92 (D52, superseding M88's round figures): the distance of D-s111 and the grams of D-w10-t2 are figures; the
    # writer is not even asked, and the not-found report stands.
    failure = {"kind": "failure", "reason": {"operation": "web.search", "error": "web_search_results_irrelevant"}}
    for ident in ("D-s111", "D-w10-t2"):
        writer = _Writer(["No pude comprobarlo; de memoria, puede no ser exacto: unos 1.000 kilómetros por carretera."])
        facts = {"priorRequests": _prior(ident)}
        assert writer._compose_consulted_answer(
            _case(ident)["text"], facts, failure, "es", writer._post, None, "t", memory=True,
        ) is None
        assert writer.sent == []


def test_the_memory_answer_gets_the_answer_a_follow_up_points_at() -> None:
    # M92: the same follow-up asking no figure («¿y de dónde viene eso?»).
    writer = _Writer(["No pude comprobarlo; de memoria, puede no ser exacto: la harina de maíz viene del maíz molido."])
    facts = {"context": _last_reply("D-w10-t2"), "priorRequests": _prior("D-w10-t2")}
    failure = {"kind": "failure", "reason": {"operation": "web.search", "error": "web_search_results_irrelevant"}}

    writer._compose_consulted_answer("¿y de dónde viene eso?", facts, failure, "es", writer._post, None, "t", memory=True)

    sent = json.loads(writer.sent[0]["messages"][1]["content"])
    assert "2 tazas de harina de maíz" in sent["previous_answer_for_references_only"]


# ------------------------------------------------------------------ p12-t2: a count is a count of what was read


def _report_defect(ident: str) -> str:
    case = _case(ident)
    stage = _stage(ident)
    return llm._payload_fact_defect(stage["draft"], stage["payload"], case["text"], said=case["text"])


@pytest.mark.parametrize("ident", ["D-p12-t2", "v3e2:D-w06-t4"])
def test_a_count_of_the_pages_read_is_no_count_of_stores(ident: str) -> None:
    assert _report_defect(ident) == "search_report_unsourced_claim"


def _payload(snippets: list[str]) -> dict:
    return {
        "operation": "web.search",
        "seen": {"query": "restaurantes abiertos", "count": len(snippets),
                 "results": [{"title": f"Página {n}", "url": f"https://example.org/{n}", "snippet": text}
                             for n, text in enumerate(snippets)]},
    }


@pytest.mark.parametrize(
    ("draft", "snippets"),
    [
        # The pages write the count, in digits or in words.
        ("Hay tres restaurantes abiertos en el centro.", ["Los 3 restaurantes abiertos en el centro esta noche."]),
        ("Hay tres restaurantes abiertos en el centro.", ["Tres restaurantes abiertos en el centro."]),
        # The sentence counts what it lists after its colon.
        ("Hay dos restaurantes abiertos: Don Pepe y La Estrella.",
         ["Don Pepe, restaurante abierto hasta las 23.", "La Estrella, restaurante abierto hasta la 1."]),
    ],
)
def test_a_count_the_read_gives_is_kept(draft: str, snippets: list[str]) -> None:
    assert llm._search_report_unsourced_counts(draft, "\n".join(snippets)) == []
    assert llm._payload_fact_defect(draft, _payload(snippets), "restaurantes abiertos") != "search_report_unsourced_claim"


def test_a_count_the_read_does_not_give_is_refused() -> None:
    snippets = ["Don Pepe, restaurante abierto hasta las 23.", "La Estrella, restaurante abierto hasta la 1."]
    assert llm._search_report_unsourced_counts("Hay cinco restaurantes abiertos cerca.", "\n".join(snippets)) == ["cinco"]
    # «los dos» points back at what was named; «once» is English too.
    assert llm._search_report_unsourced_counts("Los dos restaurantes abren once a week.", "\n".join(snippets)) == []
    # Counting the results read is the report's voice (SEARCH2015); counting stores is a claim about the world.
    assert llm._search_report_unsourced_counts("Se encontraron cinco resultados.", "\n".join(snippets)) == []
    assert llm._search_report_unsourced_counts("Hay dos tiendas abiertas.", "\n".join(snippets)) == ["dos"]


# ------------------------------------------------------------------ w01, w10: how much of an ingredient is looked up


def test_how_much_of_an_ingredient_is_looked_up_with_what_the_conversation_carried() -> None:
    lookup = knowledge.reference_lookup(_case("D-w01-t2")["text"], _prior("D-w01-t2"), _last_reply("D-w01-t2"))
    assert (lookup.kind, lookup.query) == ("quantity", "cuanta sal le echo al agua tallarines")
    lookup = knowledge.reference_lookup(_case("D-w01-t3")["text"], _prior("D-w01-t3"), _last_reply("D-w01-t3"))
    assert (lookup.kind, lookup.query) == ("quantity", "para 3 litros cuantas cucharaditas serian sal agua tallarines")
    # «eso» is the measure BAXY's last answer gave, asked in the unit said.
    lookup = knowledge.reference_lookup(_case("D-w10-t2")["text"], _prior("D-w10-t2"), _last_reply("D-w10-t2"))
    assert (lookup.kind, lookup.query) == ("quantity", "2 tazas de harina de maiz en gramos")


@pytest.mark.parametrize(
    "text",
    [
        "¿cuántas cucharaditas son 2 cucharadas?",  # a pure conversion: computed
        "¿cuántos gramos pesa un iPhone?",  # no ingredient
        "¿cuánta harina me queda en la lista?",  # the person's own list
        "¿cuánto te gusta el chocolate?",  # a taste
        "¿qué es la harina de maíz?",  # no amount asked
        "cuántos años tiene",
    ],
)
def test_what_is_not_an_amount_of_an_ingredient_is_not_looked_up_as_one(text: str) -> None:
    lookup = knowledge.reference_lookup(text)
    assert lookup is None or lookup.kind != "quantity"


@pytest.mark.parametrize(
    ("text", "sentence", "value"),
    [
        ("¿cuántas cucharaditas son 2 cucharadas?", "2 cucharadas = 6 cucharaditas", Fraction(6)),
        ("pasa 3 litros a ml", "3 litros = 3000 ml", Fraction(3000)),
        ("how many teaspoons are in 1 tablespoon", "1 tablespoon = 3 teaspoons", Fraction(3)),
    ],
)
def test_a_pure_conversion_is_computed(text: str, sentence: str, value: Fraction) -> None:
    conversion = quantities.conversion_asked(text, "en" if text.startswith("how") else "es")
    assert (conversion.sentence, conversion.value) == (sentence, value)
    assert sentence in [fact for fact, _, _ in quantities.derived_facts(text, "en" if text.startswith("how") else "es")]


@pytest.mark.parametrize(
    "text",
    [
        "ya y pa 3 litros cuántas cucharaditas serían",  # teaspoons of salt for 3 litres of water: not a conversion
        "cuánto son 2 tazas de harina en gramos",  # a cup's weight depends on the flour
        "250 ml de leche en gramos",  # volume into mass
    ],
)
def test_what_depends_on_the_thing_measured_is_no_pure_conversion(text: str) -> None:
    assert quantities.conversion_asked(text) is None


class _Talk:
    """The decider answers «talk» with its restatement, as it did in v3r."""

    def __init__(self, request: str) -> None:  # noqa: D107
        self.request = request
        self.chats = 0

    def decide_in_context(self, text: str, history: object, tools: object, **_kwargs: object) -> ContextDecision:
        return ContextDecision(self.request, "talk", (), "")

    def chat(self, *_args: object, **_kwargs: object) -> tuple[str, list[object]]:
        self.chats += 1
        return "Una respuesta de memoria.", []

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "es"

    @staticmethod
    def consume_deferred_response_language(_text: str) -> tuple[bool, str | None]:
        return True, "es"

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None

    @staticmethod
    def public_lookup_requested(_text: str) -> bool:
        return False

    @staticmethod
    def operation_is_the_requested_effect(*_args: object, **_kwargs: object) -> bool:
        return False

    @staticmethod
    def _verify_semantic_effect_shape(_text: str) -> tuple[str, str]:
        return "no_effect", "zero"


def _tool(operation: str) -> dict:
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"),
            "canonical_name": operation,
            "description": f"Authenticated catalog leaf {operation}.",
            "risk": "read_only",
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        },
    }


@pytest.mark.parametrize(
    ("ident", "restated"),
    [
        ("D-w01-t2", "¿Cuánta sal le echo al agua para los tallarines?"),
        ("D-w01-t3", "¿Cuántas cucharaditas de sal serían para 3 litros de agua?"),
        ("D-w10-t2", "¿Cuántos gramos son 2 tazas de harina de maíz?"),
    ],
)
def test_the_talk_about_how_much_of_an_ingredient_is_a_lookup(ident: str, restated: str) -> None:
    case = _case(ident)
    tools = {name: _tool(name) for name in ("web.search", "system.time", "notification.schedule")}
    llm_fake = _Talk(restated)

    result = sidecar._prepare_turn_result(
        {"id": "m88", "text": case["text"], "history": [*case["lived"], {"role": "user", "content": case["text"]}]},
        llm=llm_fake,
        planner_catalog=PlannerCatalog(list(tools.values())),
        encoder=lambda _texts: (),
        tool_by_name=tools,
    )

    assert (result["kind"], result["operation"]) == ("action", "web.search")
    assert llm_fake.chats == 0
