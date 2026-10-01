"""M103: the owner script replayed in the real app at 38d03aa2 (conv-v3z2, dueno-2026-09-21).

- t36 «abre steam y ve a la biblioteca»: when the decider chose open + click (a plan), the plan step lost the
  readers' clauses — the readers add a look before the click (input.visible.controls) on the click's own clause, so
  their operations were not the turn's and every step went to the model's argument extraction, which asked «¿Qué
  aplicación del catálogo Inicio deseas abrir?» (vetoed, then a composed question). Runs where the decider chose
  only app.open passed: the failure followed the decider's choice, not a code change.
- t22 «¿Sabes qué peli estoy viendo en potplayer?»: media.status read the current media session (Spotify). What a
  named player shows is that application's window title (window.resolve).
- t25 «…te dije que investigues algo, eso debería ir a web search…» after a search: the decider asked what to look
  up. Insisting on the search asked before is that search again.
- t40/t41 «No lo hiciste mentiroso, nose no lo vi» → «No lo hice mentiroso, pero no lo vi.» (the App's conversation
  fallback, composed), and t41 the same reply again: the person's sentence turned to the first person is an echo,
  and the composer now holds the M99 repeat check too.
- t50/t51 «baxy, cierra baxy»: the self-close limit «No cierro BAXY desde el chat, ya que se cierra con la X de su
  ventana o con Alt+F4.» died as limit_gives_a_reason (M20/M21), and «No cierro el pedido.» was published.
- t45 «silencia mi microfono» (already muted): «El micrófono estaba ya silenciado, …» died as missing_failure; the
  word order «estaba ya» is the same statement as «ya estaba».

Tests use their own phrasings; the guion texts stay as evidence beside them.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.effect_intent import resolve_explicit_effects
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import dialogue as dialogue_slot
from baxy_mind.semantic.arguments import _explicit_arguments_from_evidence
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.patterns import application_shown_media_name

APPS = ("Steam", "Spotify", "Discord", "PotPlayer 64 bit", "VLC media player", "Google Chrome", "Microsoft Edge")
READS = frozenset({"app.open", "input.visible.controls", "input.visible.click", "web.search", "window.resolve",
                   "media.status", "window.application.status"})


# --- t36: the plan keeps the readers' clauses when they add a look before the click -------------------------------


@pytest.mark.parametrize(
    ("text", "app", "label"),
    [
        ("abre steam y ve a la biblioteca", "Steam", "biblioteca"),  # the guion's words
        ("Abre Steam y entra a la biblioteca.", "Steam", "biblioteca"),  # the decider's restatement
        ("abre discord y entra en ajustes", "Discord", "ajustes"),
        ("open Spotify and go to the library", "Spotify", "library"),
    ],
)
def test_an_open_and_click_plan_grounds_each_step_from_its_clause(text: str, app: str, label: str) -> None:
    read = resolve_explicit_effects(text, READS, application_names=APPS)
    assert read is not None and read.operations == ("app.open", "input.visible.controls", "input.visible.click")

    evidence = sidecar._evidence_of_expected_operations(
        ("app.open", "input.visible.click"), read.operations, read.evidence,
    )

    assert evidence is not None and len(evidence) == 2
    skeleton = sidecar._explicit_plan_skeleton(("app.open", "input.visible.click"), evidence)
    assert [step["operation"] for step in skeleton["steps"]] == ["app.open", "input.visible.click"]
    assert sidecar._explicit_arguments_from_evidence("app.open", evidence[0], APPS) == {"appId": app}
    assert sidecar._explicit_arguments_from_evidence("input.visible.click", evidence[1], APPS) == {"label": label}


def test_a_dropped_step_with_a_clause_of_its_own_is_another_request() -> None:
    # The turn kept two of three effects that each had their own clause: nothing to align.
    recognized = ("app.open", "web.search", "input.visible.click")
    evidence = ("steam", "busca hades", "ve a la biblioteca")

    assert sidecar._evidence_of_expected_operations(("app.open", "input.visible.click"), recognized, evidence) is None
    assert sidecar._evidence_of_expected_operations(("app.open",), ("app.close",), ("steam",)) is None
    assert sidecar._evidence_of_expected_operations(("app.open",), ("app.open",), ("steam",)) == ("steam",)


# --- t22: what a named player shows is its window's title -------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("Sabes que peli estoy viendo en potplayer?", "PotPlayer 64 bit"),  # the guion's words
        ("¿qué serie tengo puesta en el VLC?", "VLC media player"),
        ("what am I watching on vlc?", "VLC media player"),
        ("what's playing in potplayer", "PotPlayer 64 bit"),
        # Spotify and the browsers are their own media session.
        ("qué canción suena en spotify", None),
        ("qué video estoy viendo en chrome", None),
        # Not a question about what is shown, or a player not installed here.
        ("estoy viendo una peli en potplayer, búscala", None),
        ("qué peli estoy viendo en kodi", None),
    ],
)
def test_the_player_named_in_a_question_about_what_it_shows(text: str, name: str | None) -> None:
    assert application_shown_media_name(text, APPS) == name


def test_the_window_read_takes_the_named_player() -> None:
    assert _explicit_arguments_from_evidence("window.resolve", "¿qué estoy viendo en VLC?", APPS) == {
        "applicationName": "VLC media player"
    }


class _Decider:
    def __init__(self, decision: ContextDecision) -> None:
        self.decision = decision

    def decide_in_context(self, *_args: object, **_kwargs: object) -> ContextDecision:
        return self.decision

    def chat(self, *_args: object, **_kwargs: object) -> tuple[str, list[object]]:
        return "Vale.", []

    def clarify_after_turn_failure(self, *_args: object, **_kwargs: object) -> str:
        return "¿Qué quieres saber?"

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "es"


def _tool(operation: str) -> dict[str, object]:
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


def _decided(text: str, decision: ContextDecision) -> dict[str, object]:
    tools = [_tool(name) for name in sorted(READS)]
    return sidecar._context_decided_result(
        {"id": "m103", "text": text, "history": [{"role": "user", "content": text}]},
        llm=_Decider(decision),
        planner_catalog=PlannerCatalog(tools),
        application_names=APPS,
    )


@pytest.mark.parametrize(
    "decision",
    [
        ContextDecision("¿Qué película estoy viendo en PotPlayer?", "action", ("media.status",), ""),
        ContextDecision("¿Qué estoy viendo?", "talk", (), ""),
    ],
)
def test_a_question_about_a_named_player_reads_its_window(decision: ContextDecision) -> None:
    result = _decided("oye, ¿qué peli tengo puesta en potplayer?", decision)

    assert result["kind"] == "action"
    assert result["operation"] == "window.resolve"


def test_the_media_session_stays_for_spotify() -> None:
    decision = ContextDecision("¿Qué suena en Spotify?", "action", ("media.status",), "")

    assert _decided("¿qué canción suena en spotify?", decision)["operation"] == "media.status"


# --- t25: insisting on the search asked before is that search again ------------------------------------------------


def _searched(topic: str, request: str) -> dialogue_slot.DialogueState:
    state = dialogue_slot.DialogueState()
    state.expect(request, ["web.search"])
    state.record(
        {"kind": "operation", "operation": "web.search", "verified": True, "succeeded": True,
         "observed": {"query": topic, "count": 1}}
    )
    state.expect("sigue", [])
    return state


@pytest.mark.parametrize(
    "text",
    [
        "Si hay un pedido, obvio que hay, te dije que investigues algo, eso deberia ir a web search sino me equivoco",
        "ya te pedí que lo buscaras, no que me preguntes",
        "te dije que investigues eso",
        "eso tendría que ser una búsqueda en internet",
    ],
)
def test_insisting_on_the_search_is_the_topic_searched(text: str) -> None:
    request = _searched("El eternauta serie", "investígala").insisted_search(text)

    assert request == "busca en la web El eternauta serie"
    read = resolve_explicit_effects(request, READS, application_names=APPS)
    assert read is not None and read.operations == ("web.search",)
    assert _explicit_arguments_from_evidence("web.search", request, APPS) == {"query": "El eternauta serie"}


def test_insisting_in_english_is_said_in_english() -> None:
    request = _searched("Dune part two reviews", "look it up").insisted_search("I told you to look it up!")

    assert request == "search the web for Dune part two reviews"


@pytest.mark.parametrize(
    "text",
    [
        "te dije que no busques nada",
        "te dije que investigues el clima de mañana en Lima",
        "I told you to search for flights to Rome",
        "busca otra cosa",
    ],
)
def test_a_new_topic_or_a_no_is_not_the_old_search(text: str) -> None:
    assert _searched("El eternauta serie", "investígala").insisted_search(text) is None


def test_with_nothing_searched_there_is_nothing_to_repeat() -> None:
    assert dialogue_slot.DialogueState().insisted_search("te dije que lo investigues") is None


# --- t40/t41: the person's words turned to the first person, and the last answer again -----------------------------


def _conversation(previous: str | None = None) -> dict[str, object]:
    facts: dict[str, object] = {"situation": {"kind": "conversation", "polarity": "success"}}
    if previous is not None:
        facts["context"] = previous
    return facts


@pytest.mark.parametrize(
    ("reply", "said"),
    [
        ("No lo hice mentiroso, pero no lo vi.", "No lo hiciste mentiroso, nose no lo vi"),  # the guion's words
        ("No lo abrí, tramposo, y no lo vi.", "no lo abriste tramposo, no lo vi"),
        ("I don't believe you, I never opened it.", "i don't believe you, you never opened it"),
    ],
)
def test_the_persons_sentence_said_back_in_the_first_person_is_an_echo(reply: str, said: str) -> None:
    assert llm.compose_visible_defect(reply, "conversation", said, _conversation(), said=said) == "echo"


@pytest.mark.parametrize(
    ("reply", "said"),
    [
        ("Qué bueno que te guste crear cosas como yo.", "me gusta crear cosas como tu"),
        ("Me alegra que te sientas con ánimo.", "Yo muy bien, me siento con animo"),
        ("No llegué a hacer clic: el juego no aparecía en la pantalla.", "No lo hiciste mentiroso"),
        # A question restated with its answer is the answer.
        ("The capital of Peru is Lima.", "what is the capital of Peru"),
        ("La capital de Chile es Santiago.", "cuál es la capital de chile"),
    ],
)
def test_an_answer_with_words_of_its_own_is_no_echo(reply: str, said: str) -> None:
    assert llm.compose_visible_defect(reply, "conversation", said, _conversation(), said=said) == ""


def test_the_composed_conversation_does_not_say_the_last_answer_again() -> None:
    previous = "No llegué a hacer clic en el juego porque no aparecía en la pantalla."
    said = "dímelo tú, te mandé la misión a ti"

    assert llm.compose_visible_defect(previous, "conversation", said, _conversation(previous), said=said) == (
        "repeats_last_answer"
    )
    # Asked to say it again, it is the answer.
    assert llm.compose_visible_defect(previous, "conversation", "¿qué dijiste?", _conversation(previous)) == ""


# --- t50/t51: the self-close limit says how BAXY is closed ----------------------------------------------------------


@pytest.mark.parametrize("request_text", ["baxy, cierra baxy", "cierra BAXY"])
@pytest.mark.parametrize(
    "reply",
    [
        "No cierro BAXY desde el chat, ya que se cierra con la X de su ventana o con Alt+F4.",
        "No me cierro desde aquí porque BAXY se cierra con la X de su ventana o con Alt+F4.",
    ],
)
def test_the_self_close_limit_may_join_how_baxy_closes(request_text: str, reply: str) -> None:
    assert llm.limit_voice_defect(reply, request_text) == ""
    assert llm._unsupported_answer_contract_failure(reply, request_text) == ""


def test_any_other_limit_still_gives_no_reason() -> None:
    reply = "No reservo mesas porque no tengo acceso a restaurantes."

    assert llm.limit_voice_defect(reply, "reserva una mesa para dos") == "limit_gives_a_reason"


@pytest.mark.parametrize(
    ("reply", "request_text", "defect"),
    [
        ("No cierro el pedido.", "cierra BAXY", "limit_names_no_act"),  # the guion's final
        ("No apago la solicitud.", "apágate ya", "limit_names_no_act"),
        # The person's own words were about an order: «el pedido» is the thing.
        ("No cancelo tu pedido.", "cancela mi pedido de la tienda", ""),
    ],
)
def test_a_limit_said_of_the_request_names_no_act(reply: str, request_text: str, defect: str) -> None:
    assert ("limit_names_no_act" if llm._limit_names_no_act(reply, request_text) else "") == defect


# --- t45: «estaba ya» is «ya estaba» ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "reply",
    [
        "El micrófono estaba ya silenciado, por lo que no hubo ningún cambio.",
        "El micrófono ya estaba silenciado.",
    ],
)
def test_the_state_already_held_is_told_in_either_order(reply: str) -> None:
    situation = {
        "kind": "operation", "operation": "audio.microphone.mute", "polarity": "failure",
        "verified": False, "succeeded": False, "error": "microphone_already_muted",
    }

    assert llm.compose_visible_defect(reply, "status", "silencia el micro", {"situation": situation}) == ""
