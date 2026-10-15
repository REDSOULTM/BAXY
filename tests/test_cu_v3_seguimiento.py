"""Uso real v3 tanda 2 (c04, diagnóstico r6a §b y §e): a follow-up said with a preamble stays in the conversation's
application, the coverage gate hands the engine the decider's restatement that frames it, and a correction or an undo
reads the conversation instead of starting over."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from baxy_mind import compose_instructions
from baxy_mind import visible_defect
from baxy_mind.semantic import dialogue, missions
from baxy_mind import engine_handoff
from baxy_mind import context_decision
from baxy_mind import compose_facts

APPS = tuple(
    json.loads((Path(__file__).parent / "data" / "cu_v3_start_catalog.v1.json").read_text(encoding="utf-8"))["names"]
)

C04 = (
    "abre configuracion y ve a pantalla",
    "ahi ponle la escala en 125",
    "no espera se ve muy grande, regresala como estaba",
    "te dije la escala no el brillo, regresa la escala a 100",
)


# ------------------------------------------------------------------------- inheritance through preambles (§b.1)

@pytest.mark.parametrize("turns", [C04[:2], C04[:3], C04[:4]], ids=["t2", "t3", "t4"])
def test_a_follow_up_with_a_preamble_stays_in_the_conversations_application(turns: tuple[str, ...]) -> None:
    *before, text = turns
    assert missions.mission_destination(text, APPS, before) == "Configuración"


@pytest.mark.parametrize(
    "said",
    [
        "ahi ponle la escala en 125",
        "no, ponle 125",
        "no espera se ve muy grande, regresala como estaba",
        "te dije la escala no el brillo, regresa la escala a 100",
        "wait, set it to 125",
    ],
)
def test_a_preamble_or_a_remark_before_the_order_keeps_it_an_order(said: str) -> None:
    assert missions._inherits_application(said)


@pytest.mark.parametrize(
    "said",
    [
        # Contracaso (diagnóstico): a question after the correction still ends the application.
        "no, ¿cuál es la capital de Francia?",
        "no, cual es la capital de francia",
        # A prohibition is no order; a remark alone is none either.
        "no la cierres",
        "ahí está bien",
        "te dije la escala no el brillo",
        "no bro cerraste el que no era, te dije CHROME",
    ],
)
def test_a_question_a_prohibition_or_a_remark_alone_still_cuts(said: str) -> None:
    assert not missions._inherits_application(said)


def test_a_question_after_a_correction_ends_the_conversations_application() -> None:
    assert missions.conversation_application(
        ("abre configuracion y ve a pantalla", "no, ¿cuál es la capital de Francia?"), APPS,
    ) is None


# ------------------------------------------------------------------- the decider's restatement for the engine (§b.2)

def test_the_restatement_that_frames_the_conversations_application_is_the_engines_goal() -> None:
    restated = "En Configuración, pon la escala de la pantalla en 125."
    assert missions.restatement_for_the_engine(restated, C04[1], C04[:1], APPS) == restated
    assert missions.mission_destination(restated, APPS, C04[:1]) == "Configuración"


@pytest.mark.parametrize(
    ("restated", "said", "before"),
    [
        # Contracaso: an application nobody in the conversation named is never brought in by the restatement.
        ("En Spotify, pon la escala en 125.", "ahi ponle la escala en 125", ("abre configuracion y ve a pantalla",)),
        # The person's own words name the application: theirs stay.
        ("En Configuración, pon la escala en 125.", "en paint ponle 125", ("abre configuracion y ve a pantalla",)),
        # A restatement that frames none is nothing to hand over.
        ("Pon la escala en 125.", "ahi ponle la escala en 125", ("abre configuracion y ve a pantalla",)),
    ],
)
def test_a_restatement_never_brings_in_an_application(restated: str, said: str, before: tuple[str, ...]) -> None:
    assert missions.restatement_for_the_engine(restated, said, before, APPS) is None


def test_a_restatement_never_brings_back_an_application_the_conversation_left() -> None:
    """Revisión: Spotify was named, then the conversation moved to Configuración; a restatement framing Spotify would
    send the engine to the window of t2's wrong destination («Spotify Premium» with the conversation in Configuración)."""

    before = ("abre spotify", "abre configuracion y ve a pantalla")
    assert missions.restatement_for_the_engine("En Spotify, pon la escala en 125.", C04[1], before, APPS) is None
    restated = "En Configuración, pon la escala en 125."
    assert missions.restatement_for_the_engine(restated, C04[1], before, APPS) == restated


TOOLS = {operation: {} for operation in ("mission.computer.use", "system.settings.set", "web.search")}


def _limit(restated: str) -> dict[str, object]:
    return {
        "type": "turn.result", "id": "t2-c04", "kind": "conversation", "conversationKind": "unsupported",
        "operation": None, "intentOperations": [], "effectOperations": [], "question": "", "reply": "No puedo.",
        engine_handoff._DECIDER_RESTATEMENT: restated,
    }


def _gate(turn: dict[str, object], *said: str) -> dict[str, object]:
    history = [{"role": "user", "content": text} for text in said]
    return engine_handoff._engine_for_an_unserved_order(turn, {"id": "t2-c04", "text": said[-1], "history": history}, TOOLS, APPS)


def test_the_gate_hands_the_engine_the_restatement_with_the_application() -> None:
    restated = "En Configuración, pon la escala de la pantalla en 125."
    result = _gate(_limit(restated), *C04[:2])
    assert result["effectOperations"] == ["mission.computer.use"]
    assert result["objective"] == restated
    assert engine_handoff._DECIDER_RESTATEMENT not in result


def test_the_gate_keeps_the_persons_words_when_the_restatement_invents_the_application() -> None:
    """Contracaso: a restatement framing an application nobody named never becomes the goal."""

    turn = _limit("En Spotify, pon la escala en 125.")
    result = _gate(turn, *C04[:2])
    assert result.get("objective") == C04[1]
    assert engine_handoff._DECIDER_RESTATEMENT not in result and engine_handoff._DECIDER_RESTATEMENT not in turn


# ------------------------------------------------------------------------------- undo of the last change (§e)

@pytest.mark.parametrize(
    "text",
    ["no espera se ve muy grande, regresala como estaba", "déjalo como antes", "vuelve a como estaba", "deshazlo",
     "put it back the way it was", "undo that", "vuelve a ponerlo como estaba"],
)
def test_an_undo_of_the_last_change_is_read(text: str) -> None:
    assert dialogue.asks_to_undo(text)


@pytest.mark.parametrize(
    "text",
    ["¿cómo estaba el clima ayer?", "regresa a la página anterior", "pon música",
     # Revisión: «volver a» + infinitive does it again, it undoes nothing.
     "vuelve a abrirlo como antes", "vuelve a abrir chrome como antes"],
)
def test_counter_cases_of_the_undo(text: str) -> None:
    assert not dialogue.asks_to_undo(text)


FAILED_SCALE = "No pude hacerlo en «Spotify Premium»: no vi en la pantalla un control con el que seguir."


def test_an_undo_after_a_change_that_did_not_happen_has_nothing_to_put_back() -> None:
    assert dialogue.undo_with_nothing_changed(C04[2], FAILED_SCALE)
    # Contracaso: after a change BAXY told done, the undo is no «nothing changed».
    assert not dialogue.undo_with_nothing_changed(C04[2], "Listo, puse la escala en 125 %.")


@pytest.mark.parametrize("language", ["es", "en"])
def test_the_undo_with_nothing_changed_never_claims_how_the_screen_is(language: str) -> None:
    """Revisión: the person says it changed («se ve muy grande») and a failed mission may have acted before failing;
    BAXY tells only that it made no change, never that the screen «sigue como estaba». Encargo H1 (tandas fin1/fin2
    t2-c04 t3: the writer, told this, still answered «no hay un control para revertir la escala»): the sentence is the
    floor's (data «heldFact.undoUnapplied»), said without a draft (tests/test_estab_h1_finales.py)."""

    from baxy_mind import operation_floor

    said = operation_floor.floor_data()["heldFact"][language]["undoUnapplied"]
    assert "sigue como estaba" not in said and "as it was" not in said
    assert ("no llegué a hacer ese cambio" in said.casefold()) if language == "es" else (
        "did not get to make that change" in said)


class _Limit:
    """The decider closes the turn as a limit; the writer and the question writer answer what they are given."""

    _native_tool_policy_enabled = False

    def __init__(self) -> None:
        self.asked = False

    def decide_in_context(self, *_a, **_k):
        from baxy_mind.semantic.decider import ContextDecision

        return ContextDecision(request="Deja la ventana como estaba.", decision="limit", operations=(), question="")

    def prepare_decision(self, *_a, **_k):
        return None

    def detect_response_language(self, _text):
        return "es"

    @staticmethod
    def chat(*_a, **_k):
        return "Sigue como estaba: no llegué a cambiar la escala.", []

    def clarify_after_turn_failure(self, *_a, **_k):
        self.asked = True
        return "¿Qué quieres que deje como estaba?"

    def __getattr__(self, name):
        def missing(*_a, **_k):
            raise RuntimeError(f"no {name} here")
        return missing


def _decided_undo(history: list[dict[str, str]], text: str) -> dict[str, object]:
    from baxy_mind.planner import PlannerCatalog

    tools = [
        {"type": "function", "function": {"name": name.replace(".", "_"), "canonical_name": name, "description": name,
                                          "risk": "read_only",
                                          "parameters": {"type": "object", "properties": {}, "required": [],
                                                         "additionalProperties": False}}}
        for name in TOOLS
    ]
    return context_decision._context_decided_result(
        {"id": "t2-c04-3", "text": text, "history": [*history, {"role": "user", "content": text}]},
        llm=_Limit(), planner_catalog=PlannerCatalog(tools), application_names=APPS,
    )


def test_an_undo_after_a_failed_change_is_talk_never_a_limit() -> None:
    history = [
        {"role": "user", "content": C04[1]},
        {"role": "assistant", "content": FAILED_SCALE},
    ]
    result = _decided_undo(history, C04[2])
    assert result["kind"] == "conversation" and result.get("conversationKind") != "unsupported"


def test_an_undo_with_nothing_asked_before_asks_what_to_undo() -> None:
    """Contracaso (diagnóstico §e): with no change before, what to undo is asked."""

    result = _decided_undo([], "regresala como estaba")
    assert result["kind"] == "clarify"


# ------------------------------------------------------------------------ no identical final after a correction

_CLOSE_FAILED = {
    "kind": "failure", "operation": "app.close", "verified": True, "succeeded": False,
    "observed": {"application": "Google Chrome", "windows": 0},
}
_CLOSED_NOTHING = "No se cerró Chrome porque no tenía ninguna ventana abierta."


def _told_state() -> dialogue.DialogueState:
    state = dialogue.DialogueState()
    state.expect("cierra chrome que me esta laggeando el valorant", ["app.close"])
    state.told(_CLOSE_FAILED, _CLOSED_NOTHING)
    return state


@pytest.mark.parametrize(
    "text",
    ["no bro cerraste el que no era, te dije CHROME", "te dije la escala no el brillo, regresa la escala a 100",
     "I told you Chrome, not Edge"],
)
def test_a_reproach_is_a_correction(text: str) -> None:
    assert dialogue.corrects_or_insists(text)


@pytest.mark.parametrize("text", ["¿qué te dije ayer?", "le dije a mi mamá que llegaba tarde", "y ahora baja el brillo"])
def test_counter_cases_of_the_reproach(text: str) -> None:
    assert not dialogue.corrects_or_insists(text)


def test_after_a_correction_the_last_final_is_never_told_again() -> None:
    state = _told_state()
    said = "no bro cerraste el que no era, te dije CHROME"
    state.expect(said, ["app.close"])
    facts = compose_facts._with_listing_and_repetition_facts({"situation": _CLOSE_FAILED}, _CLOSE_FAILED, state, said, said)
    assert facts["situation"]["correctedFinal"] == {"previousReply": _CLOSED_NOTHING}
    assert visible_defect.compose_visible_defect(_CLOSED_NOTHING, "error", said, facts, said=said) == "repeats_last_answer"
    assert "correctedFinal" in compose_instructions._compose_shape_instruction(facts["situation"], "es", said)
    # Other words for the same outcome pass this check.
    assert visible_defect.compose_visible_defect(
        "Chrome sigue sin ventanas abiertas: no cerré ninguna otra app.", "error", said, facts, said=said,
    ) != "repeats_last_answer"


def test_a_follow_up_that_goes_on_may_say_anything() -> None:
    """Contracaso: no correction, no constraint; and nothing told yet, nothing to hold."""

    state = _told_state()
    assert state.final_before_correction(_CLOSE_FAILED, "ok y ahora baja el brillo a like 30") is None
    assert dialogue.DialogueState().final_before_correction(_CLOSE_FAILED, "no, te dije CHROME") is None


def test_the_restatement_never_reaches_the_shell_when_the_turn_stays_a_limit() -> None:
    turn = _limit("Dime un chiste.")
    result = _gate(turn, "cuentame un chiste")
    assert engine_handoff._DECIDER_RESTATEMENT not in result


# ------------------------------------------- semilla r8: a progress notice never takes the last final's place

_PROGRESS = {"kind": "status", "polarity": "success", "cause": "acting", "phase": "acting"}
_OPENED = {
    "kind": "operation", "operation": "browser.navigate", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {"version": 1, "requestedUrl": "https://www.google.com/search?q=top+3", "browser": "Opera GX"},
}
_UNCONFIRMED = {
    "kind": "failure", "polarity": "failure", "cause": "mission_failed",
    "reason": {"kind": "operation", "operation": "browser.navigate", "polarity": "failure", "verified": False,
               "succeeded": False, "error": "user_browser_navigation_unconfirmed"},
}
_NOT_CONFIRMED = (
    "No puedo darte ese top 3 porque la página de Google se abrió en tu navegador pero no se confirmó qué mostraba."
)
_WORKING = "Estoy trabajando en la solicitud."


def _seed_state() -> dialogue.DialogueState:
    """t1 opened the search, t2 («si pero quiero buscar un top 3») worded a progress notice and then its final."""

    state = dialogue.DialogueState()
    state.expect("Podrias buscarme en google un top 3 peliculas de suspenso del 2026", ["browser.navigate"])
    state.told(_PROGRESS, "Estoy trabajando en el pedido solicitado.")
    state.told(_OPENED, "He abierto en Google la búsqueda de «un top 3 peliculas de suspenso del 2026».")
    state.expect("si pero quiero buscar un top 3", ["browser.navigate"])
    state.told(_PROGRESS, _WORKING)
    state.told(_UNCONFIRMED, _NOT_CONFIRMED)
    return state


def test_after_a_correction_the_final_held_is_the_last_final_not_the_turns_own_progress_notice() -> None:
    state = _seed_state()
    said = "ok pero lo puedes buscar en google no me importa the ice"
    state.expect(said, ["browser.navigate"])
    # t3's own notice is worded while its navigation runs, before its final.
    notice = compose_facts._with_listing_and_repetition_facts({"situation": _PROGRESS}, _PROGRESS, state, said, said)
    assert "correctedFinal" not in notice["situation"]
    state.told(_PROGRESS, _WORKING)
    facts = compose_facts._with_listing_and_repetition_facts(
        {"situation": _UNCONFIRMED}, _UNCONFIRMED, state, said, said,
    )
    assert facts["situation"]["correctedFinal"] == {"previousReply": _NOT_CONFIRMED}
    assert visible_defect.compose_visible_defect(_NOT_CONFIRMED, "error", said, facts, said=said) == "repeats_last_answer"


def test_a_progress_notice_alone_leaves_nothing_to_hold() -> None:
    """Contracaso: with only notices told there is no final, so a correction holds nothing back."""

    state = dialogue.DialogueState()
    state.expect("abre google", ["browser.navigate"])
    state.told(_PROGRESS, _WORKING)
    assert state.final_before_correction(_UNCONFIRMED, "si pero quiero buscar un top 3") is None


@pytest.mark.parametrize("said", ["otra vez", "y ahora busca el clima de mañana"])
def test_asking_again_or_going_on_may_tell_the_same_words(said: str) -> None:
    """Contracaso: «otra vez» asks for it again and a follow-up that goes on corrects nothing."""

    state = _seed_state()
    state.expect(said, ["browser.navigate"])
    state.told(_PROGRESS, _WORKING)
    assert state.final_before_correction(_UNCONFIRMED, said) is None


# ------------------------------------------------------------- putting the whole PC back is never the engine's goal

@pytest.mark.parametrize(
    "goal",
    ["restaura el sistema a un punto de restauración", "restore my pc to a restore point",
     "restaura la configuración de fábrica", "revierte la última actualización de windows",
     "regresa windows a la versión anterior", "revert the last windows update"],
)
def test_putting_the_whole_pc_back_is_never_handed_to_the_engine(goal: str) -> None:
    """Revisión: «restaura», «regresa», «revert» are order heads now; a factory reset, a restore point or an update
    rolled back wipes or restarts the PC (owner rule: never restart)."""

    assert not missions.engine_can_try(goal, APPS)


@pytest.mark.parametrize(
    "goal",
    ["en configuracion regresa la escala a 100", "En Configuración, regresa la escala como estaba.",
     "en paint regresa al color anterior"],
)
def test_putting_one_setting_back_is_still_the_engines(goal: str) -> None:
    assert missions.engine_can_try(goal, APPS)
