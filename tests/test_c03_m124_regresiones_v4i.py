"""M124 (round v4i, 2026-10-02): the regressions of main 8a65e023 (M120–M123) against v4h, with phrasings of our own.

1. Owner's script t59: a search report named the publisher a Google News result carries in its snippet
   («…levelup.com también la llama…»). The mind exempts an identifier written inside an observed value (A7 E4,
   ``llm._observed_identifier_tokens``); the App's twin did not and the turn ended in ⚠ (Baxy.App
   ObservedResponseLiterals.WithoutObservedIdentifiers, M124RegresionesV4iTests). The mind's side is pinned here.
3. Layer A (owner's real log): since M123 a stable no-effect reading waits for the contextual decider unless it is
   certain and the decider is wrong in a known way. Two such ways were left out: reading what someone wrote in a chat
   (no operation reads a chat: the decider located the chat instead) and text the person asks BAXY to write (a CV, a
   letter, a template: the decider created an Office document with nothing written in it). Against the isolated decider
   (reserve, DEV-D, DEV-F) neither preemption breaks a turn.
4. DEV-D: the analysis of a named organization (D59.8, M121) written in the person's casual tone ran past its budget
   in its closing words after its four sections were whole; every draft died as «truncated». The whole part is kept.
"""

from __future__ import annotations

import copy
import json

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.llm import LlmRuntime
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.conversation import stable_no_effect, stable_no_effect_preempts
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.dialogue import DialogueState


# ------------------------------------------------------------------ 1. an observed publisher is no internal code


def _news_search(snippet_source: str) -> dict:
    return {
        "kind": "operation", "operation": "web.search", "polarity": "success", "verified": True, "succeeded": True,
        "observed": {"version": 1, "query": "reseñas de la película del faro", "count": 1, "results": [
            {"title": "La película del faro divide a la crítica", "url": "https://news.google.com/rss/articles/CBMiAAA",
             "snippet": f"{snippet_source}, Mon, 21 Sep 2026 07:00:00 GMT"},
        ], "authority": "google_news_rss"},
    }


def test_a_publisher_the_search_observed_is_no_internal_code() -> None:
    situation = _news_search("cinemania.es")
    said = "Según cinemania.es, la película del faro divide a la crítica."
    assert llm.compose_visible_defect(said, "status", "y qué dicen las reseñas", {"situation": situation}) != (
        "internal_code"
    )
    # A dotted name nobody observed is still refused.
    assert llm.compose_visible_defect(
        "Según cinemania.es y web.search, la película divide a la crítica.", "status", "y qué dicen las reseñas",
        {"situation": situation},
    ) == "internal_code"


# ------------------------------------------------------------------ 3. readings the decider is known to get wrong


class _Decider:
    """The model of a whole turn: the decider answers what it is given; every other call is neutral."""

    _native_tool_policy_enabled = False

    def __init__(self, decision: ContextDecision) -> None:
        self.decision = decision
        self.decisions = 0

    def decide_in_context(self, *_a, **_k):
        self.decisions += 1
        return self.decision

    def public_lookup_requested(self, _text):
        return False

    def _verify_semantic_effect_shape(self, _text):
        return "no_effect", "zero"

    def chat(self, *_a, **_k):
        return "Respuesta.", []

    def prepare_chat(self, *_a, **_k):
        return None

    def detect_response_language(self, _text):
        return "es"

    def consume_deferred_response_language(self, _text):
        return True, None

    def retire_deferred_response_language(self, _text):
        return None

    def __getattr__(self, name):
        def missing(*_a, **_k):
            raise RuntimeError(f"no {name} here")
        return missing


def _tool(name: str) -> dict:
    schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    return {"type": "function", "function": {"name": name.replace(".", "_"), "canonical_name": name,
                                             "description": name, "risk": "read_only", "parameters": schema}}


def _turn(text: str, model: _Decider) -> dict:
    tools = {name: _tool(name) for name in ("client.channel.locate", "office.document.create", "web.search")}
    return sidecar._prepare_turn_result(
        {"id": "m124", "text": text, "history": [{"role": "user", "content": text}]},
        llm=model, planner_catalog=PlannerCatalog(list(tools.values())), encoder=lambda _t: (), tool_by_name=tools,
        dialogue_state=DialogueState(),
    )


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        # What someone wrote in a chat: no operation reads a chat (the decider located it).
        ("qué fue lo último que me escribió la Coni por whatsapp", "unsupported"),
        # Text the person asks BAXY to write: written here (the decider created an empty Office document).
        ("hazme una carta de renuncia", "knowledge"),
        ("armame un curriculum para postular de garzón", "knowledge"),
        ("write me a cover letter for a barista job", "knowledge"),
    ],
)
def test_a_reading_the_decider_is_known_to_get_wrong_is_not_left_to_it(text: str, kind: str) -> None:
    reading = stable_no_effect(text, None)
    assert reading is not None and reading[0] == kind
    assert stable_no_effect_preempts(text)
    model = _Decider(ContextDecision(text, "action", ("client.channel.locate", "office.document.create"), ""))
    result = _turn(text, model)
    assert result["kind"] == "conversation" and not result.get("effectOperations")
    assert result.get("conversationKind") == kind


@pytest.mark.parametrize(
    "text",
    [
        "guarda una carta de renuncia en el escritorio",
        "manda un mensaje a la Coni por whatsapp",
        "abre el chat de mi hermano en discord",
        # A list asked for is the person's list or a search (reserve, against the isolated decider).
        "quiero quitar los tomates de la lista",
        "dame la lista de vuelos disponibles de santiago a lima para el viernes",
    ],
)
def test_a_record_or_a_message_is_still_the_decider_s(text: str) -> None:
    assert not stable_no_effect_preempts(text)


# ------------------------------------------------------------------ 4. a cut analysis keeps its whole part


SWOT_WHOLE = (
    "Ojo, que esta marca tiene su encanto, te lo digo con cariño.\n\n"
    "**Fortalezas:**\n- Un nombre que todos reconocen en el barrio.\n- Tiendas en muchas ciudades.\n\n"
    "**Debilidades:**\n- Precios que asustan a más de uno.\n\n"
    "**Oportunidades:**\n- Vender más por internet.\n\n"
    "**Amenazas:**\n- Rivales que copian todo al tiro."
)


def test_a_cut_analysis_keeps_its_whole_part() -> None:
    assert llm._whole_part_of_cut_analysis(SWOT_WHOLE + "\n\nEn resumen, la marca") == SWOT_WHOLE
    # Cut inside the sections: a SWOT without its threats is no whole part.
    assert llm._whole_part_of_cut_analysis(SWOT_WHOLE.split("**Amenazas:**")[0] + "**Amenazas:**\n- Rivales") == ""
    assert llm._whole_part_of_cut_analysis("Fortalezas:\n- Un nombre que") == ""


class _Cut(LlmRuntime):
    """The recorded drafts stand in for the model, each cut by its budget; every request is kept."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = None
        self.drafts = list(drafts)
        self.requests: list[dict] = []

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.requests.append(copy.deepcopy(payload))
        return {"choices": [{"message": {"content": self.drafts.pop(0)}, "finish_reason": "length"}]}


def test_the_consulted_analysis_cut_in_its_closing_words_is_published() -> None:
    situation = {
        "kind": "operation", "operation": "web.search", "polarity": "success", "verified": True, "succeeded": True,
        "observed": {"version": 1, "query": "Ripley empresa", "count": 1, "results": [
            {"title": "Ripley - Wikipedia", "url": "https://es.wikipedia.org/wiki/Ripley",
             "snippet": "Ripley es una empresa chilena de tiendas por departamento con tiendas en muchas ciudades."},
        ]},
    }
    swot = SWOT_WHOLE.replace("esta marca", "Ripley")
    writer = _Cut([swot + "\n\nEn resumen, Ripley", swot + "\n\nEn resumen, Ripley"])
    reply = writer.compose_user_message(
        "haz un FODA de la empresa Ripley con un tono relajado", "status", {"situation": situation},
    )
    assert reply == swot
    assert json.loads(writer.requests[0]["messages"][1]["content"])["evidence"]["title"] == "Ripley"
