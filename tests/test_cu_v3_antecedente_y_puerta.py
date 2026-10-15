"""Ronda 20 P3 (pasada r18, v3-11 in cu-universal-evidencia/v2-v3-11, last run): safety and reading at the gate.

- t1 «en onenote crea una pagina nueva»: the decider restated it «En OneNote, haz clic en «Página» para crear una nueva
  página.» and chose one input.visible.click; nothing on the screen was called that and the engine was never tried.
  Primitives of the screen whose verbs the person never said are the decider's paraphrase: the engine takes the
  person's words (``subsumed_by_mission``).
- t2 «escribe ahí: comprar pan, leche y huevos» right after t1 was told as failed (compose_audit t1: polarity=failure,
  visible_button_not_found): the text went into the title of a page that already existed. A place the person only
  points back to, whose request was told as failed, asks and never acts (``DialogueState.antecedent_failed``).
- t3 «ahora subele el zoom a 150» → «¿Cuánto le subo al zoom?»: the clarify branch now reads the conversation's
  application as the limited branch does (``clarify_in_conversation_application``).

Each with its counter-cases. Pure: DialogueState, the readers and the gate, no model.
"""

from __future__ import annotations

import json
from typing import Any

from baxy_mind import operation_floor
from baxy_mind.semantic import decider, dialogue, missions
from baxy_mind import engine_handoff
from baxy_mind import turn_history

APPS = ("BAXY", "Bloc de notas", "Microsoft Edge", "OneNote", "Spotify", "Steam")
TOOLS: dict[str, dict] = {
    operation: {}
    for operation in (
        "mission.computer.use", "input.visible.click", "input.text.type", "input.key.press", "app.open",
        "audio.app.volume.adjust", "web.search",
    )
}

T1 = "en onenote crea una pagina nueva"
T2 = "escribe ahi: comprar pan, leche y huevos"
T3 = "ahora subele el zoom a 150"
T1_FINAL = "No se creó la nueva página porque no hay ningún elemento en pantalla etiquetado como «Página» para hacer clic."
T2_FINAL = "Listo, escribí «comprar pan, leche y huevos» en «OneNote»."
# compose_audit.jsonl of v2-v3-11, last run, t1 (the situation the final was composed from).
T1_SITUATION = json.loads(
    '{"kind":"failure","polarity":"failure","cause":"mission_failed","stepCount":0,"steps":[],"reason":{"kind":'
    '"operation","operation":"input.visible.click","polarity":"failure","verified":false,"succeeded":false,"error":'
    '"visible_button_not_found","attempted":{"label":"«pagina» para crear una nueva pagina"}}}'
)
# A mission told as done (the counter-case «Listo, creé la página»).
DONE_SITUATION = {
    "kind": "operation", "operation": "mission.computer.use", "polarity": "success", "verified": True,
    "succeeded": True, "observed": {"goal": T1, "application": "OneNote", "reached": True,
                                    "windowTitle": "Sin título - OneNote"},
}
# A mission that did not reach its place, with the window it observed.
NOT_REACHED_SITUATION = {
    "kind": "operation", "operation": "mission.computer.use", "polarity": "success", "verified": True,
    "succeeded": True, "observed": {"goal": T1, "application": "OneNote", "reached": False,
                                    "windowTitle": "Microsoft OneNote"},
}


def _history(*turns: str, current: str) -> list[dict[str, str]]:
    roles = ("user", "assistant")
    return [{"role": roles[index % 2], "content": text} for index, text in enumerate(turns)] + [
        {"role": "user", "content": current}
    ]


def _message(current: str, *turns: str) -> dict[str, Any]:
    return {"id": "v3-11", "text": current, "history": _history(*turns, current=current)}


def _action(*operations: str, objective: str = "") -> dict[str, Any]:
    return {
        "type": "turn.result", "id": "v3-11", "kind": "action", "operation": operations[0],
        "intentOperations": list(operations), "effectOperations": list(operations), "question": "", "reply": "",
        "objective": objective,
    }


def _clarify(*intents: str, question: str = "¿Cuánto le subo al zoom?") -> dict[str, Any]:
    return {
        "type": "turn.result", "id": "v3-11", "kind": "clarify", "operation": None,
        "intentOperations": list(intents), "effectOperations": [], "question": question, "reply": "",
    }


def _asks(turn: dict[str, Any], message: dict[str, Any], state: dialogue.DialogueState) -> dict[str, Any]:
    return engine_handoff._asks_when_the_antecedent_failed(turn, message, state, APPS)


def _state_after(situation: dict[str, Any], final: str, request: str = T1) -> dialogue.DialogueState:
    state = dialogue.DialogueState()
    state.expect(request, ["mission.computer.use"])
    state.told(situation, final)
    return state


# --- t2: a place pointed back to whose request failed asks -------------------------------------------------------


def test_v3_11_t2_a_place_pointed_back_to_after_a_failure_asks_and_never_acts() -> None:
    state = _state_after(T1_SITUATION, T1_FINAL)
    turn = _action("mission.computer.use", objective="en OneNote, escribe ahi: comprar pan, leche y huevos")
    result = _asks(turn, _message(T2, T1, T1_FINAL), state)
    assert result["kind"] == "clarify"
    assert result["effectOperations"] == []
    assert result["intentOperations"] == ["mission.computer.use"]
    # No window was observed by t1's failure: the bare form, both requests quoted, from the floor's data.
    template = operation_floor.floor_data()["computerUse"]["antecedentFailed"]["esBare"]
    assert result["question"] == template.format(before=f"«{T1}»", said=f"«{T2}»")
    assert result["question"].endswith("?")


def test_the_question_names_the_window_the_last_observed_result_named() -> None:
    state = _state_after(NOT_REACHED_SITUATION, "No pude llegar a la página nueva.")
    result = _asks(
        _action("input.text.type"), _message(T2, T1, "No pude llegar a la página nueva."), state,
    )
    assert result["kind"] == "clarify"
    assert "«Microsoft OneNote»" in result["question"]


def test_the_question_is_one_question_the_shell_takes() -> None:
    # MindSidecarClient.IsSingleClarificationQuestion: one line, one «?», at most 512 characters.
    state = _state_after(T1_SITUATION, T1_FINAL)
    said = "escribe ahí: ¿vienes mañana? " + "x" * 600
    question = _asks(
        _action("input.text.type"), _message(said, T1, T1_FINAL), state,
    )["question"]
    assert question.count("?") == 1 and question.endswith("?")
    assert len(question) <= 512 and "\n" not in question and question == question.strip()


def test_a_success_told_lets_the_same_words_act() -> None:
    # Counter-case: «Listo, creé la página» → «escribe ahí: X» acts without asking.
    state = _state_after(DONE_SITUATION, "Listo, creé la página.")
    turn = _action("mission.computer.use", objective=T2)
    assert _asks(turn, _message(T2, T1, "Listo, creé la página."), state) is turn


def test_a_first_message_with_the_application_open_acts() -> None:
    # Counter-case: no request before, nothing failed.
    state = dialogue.DialogueState()
    turn = _action("input.text.type")
    message = {"id": "v3-11", "text": T2, "history": [{"role": "user", "content": T2}]}
    assert _asks(turn, message, state) is turn


def test_a_failure_before_an_order_that_names_its_own_place_acts() -> None:
    state = _state_after(T1_SITUATION, T1_FINAL)
    turn = _action("input.text.type")
    said = "escribí comprar pan en el bloc de notas"
    assert _asks(turn, _message(said, T1, T1_FINAL), state) is turn


def test_the_question_is_asked_once_a_yes_after_it_acts() -> None:
    state = _state_after(T1_SITUATION, T1_FINAL)
    asked = _asks(_action("mission.computer.use"), _message(T2, T1, T1_FINAL), state)
    assert asked["kind"] == "clarify"
    # The serve loop tells the state the turn's request; the question is no final of a failure.
    state.expect(T2, asked["intentOperations"])
    turn = _action("mission.computer.use", objective=T2)
    again = _message(T2, T1, T1_FINAL, T2, asked["question"])
    assert _asks(turn, again, state) is turn


def test_a_question_or_talk_after_a_failure_passes() -> None:
    state = _state_after(T1_SITUATION, T1_FINAL)
    turn = _clarify()
    assert _asks(turn, _message("¿qué hay ahí?", T1, T1_FINAL), state) is turn


def test_points_back_to_a_place() -> None:
    for said in (T2, "ponelo en ella", "type it in there", "escribilo allá", "write it in it"):
        assert dialogue.points_back_to_a_place(said), said
    for said in ("escribí hola en el bloc de notas", "is there a new page?", "crea una pagina nueva"):
        assert not dialogue.points_back_to_a_place(said), said


def test_the_failure_is_read_from_the_situation_never_from_the_words() -> None:
    slot = dialogue.read_slot({}, _history(T1, T1_FINAL, current=T2), T2)
    assert _state_after(T1_SITUATION, T1_FINAL).antecedent_failed(T2, slot) == T1
    assert _state_after(NOT_REACHED_SITUATION, "Listo.").antecedent_failed(T2, slot) == T1
    assert _state_after(DONE_SITUATION, T1_FINAL).antecedent_failed(T2, slot) is None
    # A progress notice is no final: it leaves the last one as it was.
    state = _state_after(DONE_SITUATION, "Listo.")
    state.told({"kind": "status", "polarity": "success", "cause": "acting"}, "Estoy trabajando en el pedido.")
    assert state.antecedent_failed(T2, slot) is None


# --- t1: primitives whose verbs the person never said are the engine's -------------------------------------------


def test_v3_11_t1_a_click_the_restatement_brought_is_the_engines() -> None:
    turn = _action("input.visible.click", objective="En OneNote, haz clic en «Página» para crear una nueva página.")
    result = engine_handoff._engine_for_an_unserved_order(turn, _message(T1), TOOLS, APPS)
    assert result["effectOperations"] == ["mission.computer.use"]
    assert result["objective"] == T1


def test_a_click_said_with_its_verb_and_label_stays_a_click() -> None:
    said = "en onenote haz clic en Agregar página"
    turn = _action("input.visible.click", objective=said)
    assert engine_handoff._engine_for_an_unserved_order(turn, _message(said), TOOLS, APPS)["effectOperations"] == [
        "input.visible.click"]


def test_typing_said_into_the_focused_field_stays_typing() -> None:
    turn = _action("input.text.type", objective="escribí hola")
    assert engine_handoff._engine_for_an_unserved_order(turn, _message("escribí hola"), TOOLS, APPS)["effectOperations"] == [
        "input.text.type"]


def test_a_click_the_engine_cannot_try_closes_as_today() -> None:
    # Ronda 21 (v3-35): the dictated text («comprar pan…») is never read as a paying order, so engine_can_try no
    # longer keeps it out; an order that only dictates where it points («escribe ahí: …» alone, no conversation)
    # still closes as today, by the gate below.
    assert missions.engine_can_try(T2, APPS)
    turn = _action("input.visible.click")
    assert engine_handoff._engine_for_an_unserved_order(turn, _message(T2), TOOLS, APPS) is turn


def test_a_message_leaning_on_the_turn_before_keeps_its_route() -> None:
    turn = _action("input.visible.click", objective="Haz clic en «Guardar».")
    # The shell holds the request its question belongs to; the answer is read against it.
    message = {**_message("el de guardar", "en onenote cerrá la página", "¿Cuál botón?"),
               "pendingObjective": "en onenote cerrá la página"}
    assert engine_handoff._engine_for_an_unserved_order(turn, message, TOOLS, APPS)["effectOperations"] == [
        "input.visible.click"]


def test_primitives_unsaid_reads_the_verbs_as_data() -> None:
    assert decider.primitives_unsaid(("input.visible.click",), T1)
    assert decider.primitives_unsaid(("input.visible.click", "input.text.type"), "en onenote anotá la lista")
    assert not decider.primitives_unsaid(("input.visible.click",), "en paint dale a guardar")
    assert not decider.primitives_unsaid(("input.visible.click", "input.text.type"), "escribí hola en el buscador")
    assert not decider.primitives_unsaid(("input.key.press",), "apretá enter")
    # An operation the data does not list is taken as said.
    assert not decider.primitives_unsaid(("app.open",), T1)
    assert not decider.primitives_unsaid((), T1)


# --- t3: a clarify reads the conversation's application ----------------------------------------------------------


def test_v3_11_t3_an_amount_said_inside_the_conversations_application_is_the_engines() -> None:
    message = _message(T3, T1, T1_FINAL, T2, T2_FINAL)
    result = engine_handoff._engine_for_an_unserved_order(_clarify(), message, TOOLS, APPS)
    assert result["effectOperations"] == ["mission.computer.use"]
    assert result["objective"] == f"en OneNote, {T3}"


def test_a_change_without_its_amount_keeps_asking() -> None:
    # Owner rule: a relative change without a quantity asks how much, never a default step.
    said = "ahora subele el zoom"
    assert missions.change_amount_unsaid(said)
    assert not missions.change_amount_unsaid(T3)
    assert not missions.change_amount_unsaid("ponele el zoom al máximo")
    turn = _clarify()
    assert engine_handoff._engine_for_an_unserved_order(turn, _message(said, T1, T1_FINAL, T2, T2_FINAL), TOOLS, APPS) is turn


def test_a_conversation_another_message_left_keeps_the_question() -> None:
    turn = _clarify()
    message = _message(T3, T1, T1_FINAL, "¿cuál es la capital de Francia?", "París.")
    assert engine_handoff._engine_for_an_unserved_order(turn, message, TOOLS, APPS) is turn


def test_an_answer_still_asked_about_keeps_its_question() -> None:
    turn = _clarify(question="¿A cuánto lo pongo?")
    message = {**_message("a 150 creo", T1, T1_FINAL, "subele el zoom", "¿Cuánto le subo al zoom?"),
               "pendingObjective": "subele el zoom"}
    assert engine_handoff._engine_for_an_unserved_order(turn, message, TOOLS, APPS) is turn


def test_the_applications_own_amount_is_still_asked() -> None:
    # «en Spotify subí el volumen»: the application's own service asks its own value.
    turn = _clarify("audio.app.volume.adjust", question="¿Cuánto lo subo?")
    message = _message("en Spotify subí el volumen")
    assert engine_handoff._engine_for_an_unserved_order(turn, message, TOOLS, APPS) is turn
    turn = _clarify("audio.app.volume.adjust", question="¿Cuánto lo subo?")
    message = _message("subí el volumen 10", "en Spotify poné algo de Queen", "Listo.")
    assert engine_handoff._engine_for_an_unserved_order(turn, message, TOOLS, APPS)["kind"] == "clarify"


# --- Revisión 1 ---------------------------------------------------------------------------------------------------


def test_review1_an_order_with_no_place_for_the_engine_keeps_its_typed_route() -> None:
    # Hallazgo 1: without an application or the window in front the mission presses no key, types nothing and clicks
    # nothing (NoApplicationActs); the typed route on the focused control serves these.
    for said, operation in (
        ("pon hola", "input.text.type"), ("poné hola", "input.text.type"), ("guardalo", "input.key.press"),
        ("recargá la página", "input.key.press"), ("abrí una pestaña nueva", "input.key.press"),
        ("seleccioná todo", "input.key.press"), ("copiá eso", "input.key.press"),
        ("cerrá esta pestaña", "input.key.press"), ("aceptá", "input.visible.click"),
    ):
        # Estabilización R21: engine_has_a_destination (only tests called it) is engine_destination_said with no
        # conversation, the reader the turn uses.
        assert not missions.engine_destination_said(said, APPS), said
        turn = _action(operation, objective=said)
        assert engine_handoff._engine_for_an_unserved_order(turn, _message(said), TOOLS, APPS) is turn, said


def test_review1_an_order_with_its_application_still_goes_to_the_engine() -> None:
    # Contracase: the same paraphrase inside a named application is the engine's (t1 above), and the window in front
    # the person names is a place.
    assert missions.engine_destination_said(T1, APPS)
    assert missions.engine_destination_said("en esta ventana guardalo", APPS)
    turn = _action("input.key.press", objective="en esta ventana guardalo")
    result = engine_handoff._engine_for_an_unserved_order(turn, _message("en esta ventana guardalo"), TOOLS, APPS)
    assert result["effectOperations"] == ["mission.computer.use"]


def test_review1_a_clarify_inside_the_conversation_needs_an_order_of_its_own() -> None:
    # Hallazgo 2: leaning on the turn before, talk, noise and an order without the value asked keep the question.
    history = (T1, T1_FINAL, T2, T2_FINAL)
    for said in ("hacelo de nuevo", "y lo otro", "asdf qwer", "ok", "gracias, eso es todo"):
        turn = _clarify(question="¿Qué querés que haga?")
        assert engine_handoff._engine_for_an_unserved_order(turn, _message(said, *history), TOOLS, APPS) is turn, said
    turn = _clarify(question="¿Qué nombre le pongo?")
    assert engine_handoff._engine_for_an_unserved_order(
        turn, _message("cambiale el nombre", *history), TOOLS, APPS,
    ) is turn


def test_review1_order_saying_its_value() -> None:
    assert missions.order_saying_its_value(T3)
    assert missions.order_saying_its_value("ponele el zoom al máximo")
    assert missions.order_saying_its_value("cambiale el nombre a «compras»")
    for said in ("cambiale el nombre", "hacelo de nuevo", "ok", "gracias, eso es todo", "asdf qwer", "son 150"):
        assert not missions.order_saying_its_value(said), said


def test_review1_a_place_said_in_the_same_message_acts_after_a_failure() -> None:
    # Hallazgo 3: the «ahí» points to a place the same message says; nothing of the failed turn is asked.
    state = _state_after(T1_SITUATION, T1_FINAL)
    for said in (
        "abrí el bloc de notas y escribí ahí hola", "en el bloc de notas escribí ahí hola",
        "abrí la carpeta descargas y dejá el archivo ahí", "open notepad and type hello there",
        "ahí va, ahora cerrá spotify",
    ):
        turn = _action("app.open", "input.text.type")
        assert _asks(turn, _message(said, T1, T1_FINAL), state) is turn, said
    # Contracase: the bare pointer still asks.
    assert _asks(_action("input.text.type"), _message(T2, T1, T1_FINAL), state)["kind"] == "clarify"
    assert not dialogue.points_back_to_a_place("ahí va, ahora cerrá spotify")
    assert dialogue.points_back_to_a_place("ahí va, escribilo ahí")


def test_review1_the_question_never_names_a_window_of_a_turn_before() -> None:
    # Hallazgo 4: t1 done in OneNote, then «pon queen en spotify» fails with nothing observed: the question names no
    # window (OneNote's is two turns old and nobody checked it is still open).
    state = _state_after(DONE_SITUATION, "Listo, creé la página.")
    assert state.last_window() == "Sin título - OneNote"
    state.expect("pon queen en spotify", ["mission.computer.use"])
    assert state.last_window() is None
    state.told(T1_SITUATION, "No pude poner Queen.")
    assert state.last_window() is None
    said = "escribe ahí: comprar pan"
    result = _asks(_action("input.text.type"), _message(said, T1, "Listo.", "pon queen en spotify", "No pude."), state)
    assert result["kind"] == "clarify"
    template = operation_floor.floor_data()["computerUse"]["antecedentFailed"]["esBare"]
    assert result["question"] == template.format(before="«pon queen en spotify»", said=f"«{said}»")
    assert "OneNote" not in result["question"]


# --- Revisión 2 ---------------------------------------------------------------------------------------------------


def test_review2_an_application_named_without_its_frame_is_never_the_conversations() -> None:
    # Hallazgo 1: inside a OneNote conversation, an order naming another application without «en <app>» is never
    # framed in OneNote (the engine would act in an application the request does not name): the question stands.
    history = (T1, T1_FINAL, T2, T2_FINAL)
    for said, named in (
        ("subí el zoom del bloc de notas a 150", "Bloc de notas"),
        ("subí el zoom de Microsoft Edge a 150", "Microsoft Edge"),
    ):
        assert missions.said_application(said, APPS).name == named
        turn = _clarify()
        result = engine_handoff._engine_for_an_unserved_order(turn, _message(said, *history), TOOLS, APPS)
        assert result is turn, said
        assert "OneNote" not in str(result.get("objective") or ""), said
    # Contracase: the same order without an application is the conversation's (t3).
    result = engine_handoff._engine_for_an_unserved_order(_clarify(), _message(T3, *history), TOOLS, APPS)
    assert result["objective"] == f"en OneNote, {T3}"


def test_review2_an_act_on_no_place_of_the_screen_never_asks_for_the_failed_place() -> None:
    # Hallazgo 2: after t1 failed, an «ahí» on an operation that acts on no place of the screen keeps its route.
    state = _state_after(T1_SITUATION, T1_FINAL)
    for said, operation in (
        ("déjalo ahí y cerrá spotify", "app.close"), ("pon el volumen ahí al 30", "audio.volume.set"),
        ("por ahí buscá un tutorial de onenote", "web.search"), ("bueno, ahí probá abrir chrome", "app.open"),
    ):
        turn = _action(operation)
        assert _asks(turn, _message(said, T1, T1_FINAL), state) is turn, said
    # Contracase: the same pointer on an act in the place asks.
    for operation in ("input.text.type", "input.visible.click", "input.key.press", "mission.computer.use"):
        assert _asks(_action(operation), _message(T2, T1, T1_FINAL), state)["kind"] == "clarify", operation


def test_review2_the_idioms_of_ahi_are_filler() -> None:
    # Hallazgo 2: «déjalo ahí», «por ahí», «hasta ahí» and a heading «ahí mismo» point to no place, even on a screen
    # act; «ahí mismo» after its verb is «right there» and still points back.
    state = _state_after(T1_SITUATION, T1_FINAL)
    for said in (
        "déjalo ahí y escribí hola en el buscador", "dejalo ahi, mejor apretá escape", "por ahí probá clic en Inicio",
        "hasta ahí está bien, escribí hola", "ahí mismo escribí hola", "bueno, ahí mismo escribí hola",
    ):
        assert not dialogue.points_back_to_a_place(said), said
        turn = _action("mission.computer.use")
        assert _asks(turn, _message(said, T1, T1_FINAL), state) is turn, said
    for said in ("escribilo ahí mismo", "déjalo ahí y escribí hola ahí", "por ahí escribilo ahí"):
        assert dialogue.points_back_to_a_place(said), said
        assert _asks(_action("input.text.type"), _message(said, T1, T1_FINAL), state)["kind"] == "clarify", said


# --- Revisión 3 ---------------------------------------------------------------------------------------------------

NOTEPAD_TURN = ("en el bloc de notas escribí la lista del súper", "Listo, escribí «la lista del súper» en «Bloc de notas».")


def test_review3_any_application_mentioned_keeps_the_question_inside_the_conversation() -> None:
    # Hallazgo 1: a short name, a kind of application or one not installed, mentioned without «en <app>», is never
    # framed in the conversation's OneNote; with Chrome installed or not.
    history = (T1, T1_FINAL, T2, T2_FINAL)
    for apps in (APPS, APPS + ("Google Chrome",)):
        for said in (
            "subí el zoom de chrome a 150", "subí el zoom de edge a 150", "subí el zoom del navegador a 150",
            "set chrome's zoom to 150", "cerrá las pestañas de chrome menos 2", "poné la letra del word en 14",
        ):
            assert missions.mentions_an_application(said, apps), said
            turn = _clarify()
            result = engine_handoff._engine_for_an_unserved_order(turn, _message(said, *history), TOOLS, apps)
            assert result is turn, said
        # Contracase: the order that mentions none is still the conversation's (t3).
        result = engine_handoff._engine_for_an_unserved_order(_clarify(), _message(T3, *history), TOOLS, apps)
        assert result["objective"] == f"en OneNote, {T3}"


def test_review3_mentions_an_application_reads_no_ordinary_words() -> None:
    for said in (T3, "cambiale el nombre", "subí el tamaño de la letra a 14", "crea una pagina nueva",
                 "ponele de titulo «chrome tips»", "cerrá esta pestaña", "set the zoom to 150"):
        assert not missions.mentions_an_application(said, APPS), said


def test_review3_the_conversations_application_is_never_the_place_of_a_typed_route_handed_over() -> None:
    # Hallazgo 2: after a turn in the Bloc de notas (the person's list), an order naming Chrome, Edge or Spotify, or
    # pointing at the tab or window in front, keeps its typed key press: the engine would act in the Bloc de notas.
    for said in (
        "recargá la página de chrome", "cerrá la pestaña de edge", "cerrá esta pestaña de chrome",
        "cerrá la ventana de spotify", "cerrá esta pestaña", "cerrá la ventana",
    ):
        message = _message(said, *NOTEPAD_TURN)
        history = message["history"]
        assert not missions.engine_destination_said(
            said, APPS, turn_history._prior_user_requests(history),
        ), said
        turn = _action("input.key.press", objective=said)
        assert engine_handoff._engine_for_an_unserved_order(turn, message, TOOLS, APPS) is turn, said
    # Contracase: the place the message gives itself is the engine's (revisión 1).
    assert missions.engine_destination_said(T1, APPS, NOTEPAD_TURN[:1])
    turn = _action("input.key.press", objective="subí el zoom de Microsoft Edge a 150")
    result = engine_handoff._engine_for_an_unserved_order(turn, _message("subí el zoom de Microsoft Edge a 150"), TOOLS, APPS)
    assert result["effectOperations"] == ["mission.computer.use"]
