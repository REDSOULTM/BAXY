"""Ronda 24 de uso real v3, palanca «corrección con premisa falsa o ya cumplida» (tandas r23).

- t4-c01 t4 «no po, en spotify te dije, no en youtube» con Spotify sonando → «Ya está sonando … en YouTube»: el final
  de una corrección ya cumplida nombra lo que se cumple y nunca afirma lo rechazado (encargo TZ-HOLD: un efecto
  retenido se dice con su frase de datos, sin borrador);
- t3-c17 t2 «no te pedi 4 po, me tiraste como 7, solo 4» → la lista corregida (la anterior más el ítem que faltaba) se
  tomó por repetición (``llm._repeats_the_last_answer``);
- t4-c04 t2 «joder que te he dicho brillo no volumen»: «El brillo ya está al 40…» murió por cifras de memoria y «…sin
  tocar el volumen» por repetición; sin borrador, el respaldo es el hecho del estado (``llm._held_fact_final``);
- t2-c04 #3 «no espera se ve muy grande, regresala como estaba» sin ningún cambio antes → 11 clics a ciegas
  (``DialogueState.undo_of_nothing``);
- t2-c03 #3 «no bro cerraste el que no era…» tras un turno que sólo preguntó → «No, cerré la ventana…»
  (``correctedFinal.previousTurnActed``).

Cada regla lleva sus contracasos.
"""

from __future__ import annotations

import pytest

from baxy_mind import dialogue_history
from baxy_mind import visible_defect
from baxy_mind import deterministic_finals
from baxy_mind import compose_instructions
from baxy_mind.semantic import dialogue
from baxy_mind import turn_audit
from baxy_mind import turn_followups
from baxy_mind import send_offer
from baxy_mind import compose_facts


@pytest.fixture(autouse=True)
def _no_turn_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(turn_audit, "_append_turn_audit", lambda row: None)


# The catalog's risks of these operations (ProductCatalog.cs): a set acts, a read does not.
RISKS = {
    "system.settings.set": "low_reversible", "audio.volume": "low_reversible", "system.settings.status": "read_only",
    "system.time": "read_only", "media.play.query": "low_reversible", "mission.computer.use": "low_reversible",
}


def _risk(operation: str) -> str | None:
    return RISKS.get(operation)


class _Writer:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.situations: list[dict] = []

    def compose_user_message(self, text: str, intent: str, facts: dict, *, said: str = "") -> str:
        self.situations.append(facts["situation"])
        return self.reply


def _state(request: str, operations: list[str], situation: dict | None, told: str) -> dialogue.DialogueState:
    state = dialogue.DialogueState()
    state.expect(request, operations)
    if situation is not None:
        state.record(situation)
    state.told(situation or {"kind": "conversation", "polarity": "success"}, told)
    return state


def _spotify_playing() -> dict:
    return {
        "kind": "operation", "operation": "media.play.query", "polarity": "success", "verified": True,
        "succeeded": True,
        "observed": {"version": 1, "provider": "spotify", "query": "cumbia", "title": "La Pollera Colorá",
                     "playbackStatus": "playing"},
    }


def _youtube_playing() -> dict:
    return {
        "kind": "operation", "operation": "media.play.query", "polarity": "success", "verified": True,
        "succeeded": True,
        "observed": {"version": 1, "provider": "youtube", "query": "cumbia", "title": "La Pollera Colorá",
                     "playbackStatus": "playing"},
    }


def _brightness_set() -> dict:
    return {
        "kind": "operation", "operation": "system.settings.set", "polarity": "success", "verified": True,
        "succeeded": True,
        "observed": {"version": 1, "setting": "brightness", "value": 40, "baselineValues": [40]},
    }


def _defect(reply: str, situation: dict, text: str, intent: str = "conversation") -> str:
    return visible_defect.compose_visible_defect(reply, intent, text, {"situation": situation}, said=text)


# --------------------------------------------------------------------------- (1) lo rechazado nunca se afirma

T4_C01 = "no po, en spotify te dije, no en youtube"


def test_t4_c01_the_held_play_carries_the_service_and_what_plays() -> None:
    """Encargo TZ-HOLD rewrote this: the held play no longer carries the refused service (``refused`` fed only the
    writer's check of a drafted held fact); it carries the service as written and the title the play verified."""

    state = _state("pone cumbia", ["media.play.query"], _spotify_playing(), "Está sonando «La Pollera Colorá» en Spotify.")
    holds = state.already_holds(T4_C01)
    assert holds is not None and holds.kind == "playing"
    assert holds.facts() == {"kind": "playing", "named": "Spotify", "title": "La Pollera Colorá"}


def test_t4_c01_the_refused_service_is_never_said_to_play() -> None:
    """Encargo TZ-HOLD rewrote this (it judged a draft with ``held_final_defect``): a held play is said with its own
    sentence, never drafted, so the evidence's «Ya está sonando «La Pollera Colorá» en YouTube.» cannot be the final."""

    state = _state("pone cumbia", ["media.play.query"], _spotify_playing(), "Está sonando «La Pollera Colorá» en Spotify.")
    writer = _Writer("Ya está sonando «La Pollera Colorá» en YouTube.")
    result = turn_followups._correction_already_held({"id": "t4", "text": T4_C01, "history": []}, state, writer, _risk)
    assert result is not None and result["reply"] == "Ya está sonando «La Pollera Colorá» en Spotify."
    assert writer.situations == []


@pytest.mark.parametrize(
    "reply",
    ["Ya está sonando en Spotify, no en YouTube.", "Ya está sonando en YouTube.", "No está sonando en Spotify."],
)
def test_whatever_a_draft_would_say_the_held_play_is_its_sentence(reply: str) -> None:
    """Encargo TZ-HOLD rewrote this (it judged drafts that name the refused service as refused): no draft is asked."""

    state = _state("pone cumbia", ["media.play.query"], _spotify_playing(), "Está sonando «La Pollera Colorá» en Spotify.")
    writer = _Writer(reply)
    result = turn_followups._correction_already_held({"id": "t4", "text": T4_C01, "history": []}, state, writer, _risk)
    assert result is not None and result["reply"] == "Ya está sonando «La Pollera Colorá» en Spotify."
    assert writer.situations == []


def test_the_untouched_thing_of_a_held_target_is_said_by_its_sentence() -> None:
    """Encargo TZ-HOLD rewrote this (it judged drafts with ``held_final_defect``): a held target is said with its own
    sentence, which names both the thing changed and the one never touched."""

    situation = {"kind": "conversation", "polarity": "success", "alreadyHolds": dict(HELD_TARGET)}
    assert deterministic_finals._held_fact_final(situation, "es") == "Lo que te dije era de «brillo»; «volumen» no lo toqué."
    state = _state("pon el brillo al 40", ["system.settings.set"], _brightness_set(), "He puesto el brillo al 40.")
    writer = _Writer("El volumen sigue igual.")
    result = turn_followups._correction_already_held({"id": "t2", "text": T4_C04, "history": []}, state, writer, _risk)
    assert result is not None and result["reply"] == "Lo que te dije era de «brillo»; «volumen» no lo toqué."
    assert writer.situations == []


def test_a_held_count_is_worded_by_the_writer() -> None:
    """Encargo TZ-HOLD rewrote this (a held count named nothing for ``held_final_defect``): a count is the only held
    fact the writer still words — the same items again."""

    told = "Bestiario, Rayuela y Octaedro son libros de Julio Cortázar."
    state = _state("dame 3 libros de cortazar", [], None, told)
    writer = _Writer("Bestiario, Rayuela y Octaedro.")
    result = turn_followups._correction_already_held(
        {"id": "t2", "text": "no, te pedi 3 nomas y me tiraste una lista enorme", "history": []}, state, writer, _risk,
    )
    assert result is not None and result["reply"] == "Bestiario, Rayuela y Octaedro."
    assert [situation["alreadyHolds"]["kind"] for situation in writer.situations] == ["count"]


def test_a_correction_that_does_not_hold_still_acts() -> None:
    """Contracaso: «en spotify, no en youtube» with YouTube playing is acted on, never answered «ya está»."""

    state = _state("pone cumbia", ["media.play.query"], _youtube_playing(), "Está sonando «La Pollera Colorá» en YouTube.")
    assert state.already_holds(T4_C01) is None
    writer = _Writer("Ya está sonando en Spotify.")
    assert turn_followups._correction_already_held({"id": "t4", "text": T4_C01, "history": []}, state, writer, _risk) is None
    assert writer.situations == []


# --------------------------------------------------------------------------- (2) la lista corregida no es repetición

T3_C17 = "no te pedi 4 po, me tiraste como 7, solo 4"
THREE_CAUSES = (
    "1. El bloqueo naval alemán.\n2. La invasión de Bélgica por Alemania.\n3. La declaración de guerra de Rusia a "
    "Alemania."
)
FOUR_CAUSES = THREE_CAUSES + "\n4. El asesinato del archiduque Francisco Fernando."


def test_t3_c17_the_list_with_the_missing_item_is_another_answer() -> None:
    # The evidence's shape: the corrected list holds the last one word for word (``last in said``).
    assert dialogue_history._normalized_dialogue_text(THREE_CAUSES) in dialogue_history._normalized_dialogue_text(FOUR_CAUSES)
    assert not dialogue_history._repeats_the_last_answer(FOUR_CAUSES, THREE_CAUSES, T3_C17)
    situation = {"kind": "conversation", "polarity": "success", "correctedFinal": {"previousReply": THREE_CAUSES}}
    assert _defect(FOUR_CAUSES, situation, T3_C17) != "repeats_last_answer"


def test_ya_te_dije_the_last_list_is_still_a_repeat() -> None:
    """Contracaso: the same count said again with «Ya te dije:» in front is the last answer again."""

    assert dialogue_history._repeats_the_last_answer(f"Ya te dije: {THREE_CAUSES}", THREE_CAUSES, T3_C17)
    assert dialogue_history._repeats_the_last_answer(f"Ya te dije: {THREE_CAUSES}", THREE_CAUSES, "no bro, eso no era")


SEVEN_NAMED = "\n".join(
    f"{n}. Causa numero {word}." for n, word in enumerate(("uno", "dos", "tres", "cuatro", "cinco", "seis", "siete"), 1)
)
FIRST_FOUR_NAMED = "\n".join(SEVEN_NAMED.split("\n")[:4])


def test_t3_c17_the_first_items_kept_word_for_word_are_another_answer() -> None:
    """Revisión 3: the corrected list is a piece of the last one (its first 4 of 7 items as they were); the count asked
    is read before the piece-of-it check."""

    from baxy_mind.semantic import listing

    assert dialogue_history._normalized_dialogue_text(FIRST_FOUR_NAMED) in dialogue_history._normalized_dialogue_text(SEVEN_NAMED)
    assert listing.counts_listed(FIRST_FOUR_NAMED) == (4,) and listing.counts_listed(SEVEN_NAMED) == (7,)
    assert not dialogue_history._repeats_the_last_answer(FIRST_FOUR_NAMED, SEVEN_NAMED, T3_C17)
    situation = {"kind": "conversation", "polarity": "success", "correctedFinal": {"previousReply": SEVEN_NAMED}}
    assert _defect(FIRST_FOUR_NAMED, situation, T3_C17) != "repeats_last_answer"
    assert _defect(f"Aquí van solo 4:\n{FIRST_FOUR_NAMED}", situation, T3_C17) != "repeats_last_answer"


def test_the_seven_said_again_or_a_piece_after_another_correction_is_still_a_repeat() -> None:
    """Contracaso: «Ya te dije: <the same 7>» lists the same count; the same piece after a correction that disputes no
    count, and the same 7 alone, are the last answer again."""

    assert dialogue_history._repeats_the_last_answer(f"Ya te dije: {SEVEN_NAMED}", SEVEN_NAMED, T3_C17)
    assert dialogue_history._repeats_the_last_answer(SEVEN_NAMED, SEVEN_NAMED, T3_C17)
    assert dialogue_history._repeats_the_last_answer(FIRST_FOUR_NAMED, SEVEN_NAMED, "no bro, eso no era")
    situation = {"kind": "conversation", "polarity": "success", "correctedFinal": {"previousReply": SEVEN_NAMED}}
    assert _defect(f"Ya te dije: {SEVEN_NAMED}", situation, T3_C17) == "repeats_last_answer"


def test_t4_c02_three_told_for_three_asked_still_holds() -> None:
    """Contracaso: the false complaint «me tiraste una lista enorme» after three items keeps answering the three."""

    told = "Bestiario, Rayuela y Octaedro son libros de Julio Cortázar."
    state = _state("dame 3 libros de cortazar", [], None, told)
    holds = state.already_holds("no, te pedi 3 nomas y me tiraste una lista enorme")
    assert holds == dialogue.AlreadyHolds("count", count=3)


# --------------------------------------------------------------------------- (3) cifras del estado y respaldo

T4_C04 = "joder que te he dicho brillo no volumen"
HELD_TARGET = {"kind": "target", "named": "brillo", "untouched": "volumen", "previousReply": "He puesto el brillo al 40."}


def test_t4_c04_the_figure_the_state_carries_is_no_memory() -> None:
    situation = {"kind": "conversation", "polarity": "success", "alreadyHolds": dict(HELD_TARGET)}
    reply = "El brillo ya está al 40 y el volumen no se ha tocado."
    assert _defect(reply, situation, T4_C04) not in {"memory_figures", "repeats_last_answer"}


def test_a_year_from_memory_is_still_vetoed() -> None:
    """Contracaso: a year no fact of the state carries is a figure from memory."""

    situation = {"kind": "conversation", "polarity": "success", "alreadyHolds": dict(HELD_TARGET)}
    reply = "El brillo ya está al 40 como en 1987, y el volumen no se ha tocado."
    assert _defect(reply, situation, T4_C04) == "memory_figures"


def test_t4_c04_the_last_answer_with_a_tail_is_never_drafted() -> None:
    """Encargo TZ-HOLD rewrote this (``holds``/``held_words`` let a held target's draft keep the last answer with the
    untouched thing named): the held target is never drafted, so «Ya he puesto el brillo al 40, sin tocar el volumen.»
    is judged as any reply after a correction — the last answer with a tail — and the turn says the target's sentence."""

    last = "Ya he puesto el brillo al 40."
    reply = "Ya he puesto el brillo al 40, sin tocar el volumen."
    assert dialogue_history._repeats_the_last_answer(reply, last, T4_C04)
    state = _state("pon el brillo al 40", ["system.settings.set"], _brightness_set(), last)
    writer = _Writer(reply)
    result = turn_followups._correction_already_held({"id": "t2", "text": T4_C04, "history": []}, state, writer, _risk)
    assert result is not None and result["reply"] == "Lo que te dije era de «brillo»; «volumen» no lo toqué."
    assert writer.situations == []


def test_with_every_draft_dead_the_state_fact_is_the_final() -> None:
    situation = {"kind": "conversation", "polarity": "success", "alreadyHolds": dict(HELD_TARGET)}
    final = deterministic_finals._deterministic_final(situation, {}, T4_C04, "es")
    assert final == "Lo que te dije era de «brillo»; «volumen» no lo toqué."
    assert _defect(final, situation, T4_C04) == ""
    playing = {"kind": "conversation", "polarity": "success",
               "alreadyHolds": {"kind": "playing", "named": "spotify", "refused": "youtube"}}
    assert deterministic_finals._held_fact_final(playing, "en") == "It is already playing on spotify."


def test_a_held_fact_missing_a_value_gives_no_template() -> None:
    """Contracaso: a kind whose sentence wants a fact the state does not carry is never filled with nothing."""

    assert deterministic_finals._held_fact_final({"alreadyHolds": {"kind": "target", "named": "brillo"}}, "es") == ""
    assert deterministic_finals._held_fact_final({"kind": "conversation"}, "es") == ""


# --------------------------------------------------------------------------- (4) deshacer lo que no cambió

T2_C04 = "no espera se ve muy grande, regresala como estaba"
SCALE_QUESTION = "¿Qué escala específica necesitas en 125?"


def _failed_mission(observed: dict) -> dict:
    return {
        "kind": "failure", "polarity": "failure", "cause": "mission_failed",
        "reason": {"kind": "operation", "operation": "mission.computer.use", "polarity": "failure",
                   "verified": False, "succeeded": False, "observed": observed},
    }


def _scale_asked_state(observed: dict | None = None) -> dialogue.DialogueState:
    # t2-c04 #1 failed without taking a step (nothing verified, nothing tried on screen), #2 only asked.
    failed = _failed_mission({"reached": False, "stepCount": 0, "steps": []} if observed is None else observed)
    state = _state("abre configuracion y ve a pantalla", ["mission.computer.use"], failed,
                   "No pude llegar a «pantalla»: el único paso que veía ya había fallado.")
    send_offer._expect_decided_turn(
        state,
        {"kind": "clarify", "question": SCALE_QUESTION, "intentOperations": ["mission.computer.use"]},
        {"text": "ahi ponle la escala en 125"},
    )
    return state


def test_a_question_asked_is_the_last_final() -> None:
    state = _scale_asked_state()
    assert state.last_final() == SCALE_QUESTION
    assert not state.last_final_acted()


def test_t2_c04_an_undo_of_nothing_is_told_and_no_engine_is_called() -> None:
    state = _scale_asked_state()
    assert state.undo_of_nothing(T2_C04, risk_of=_risk) == "ahi ponle la escala en 125"
    writer = _Writer("No la había cambiado, así que sigue como estaba.")
    result = turn_followups._correction_already_held({"id": "t3", "text": T2_C04, "history": []}, state, writer, _risk)
    assert result is not None and result["effectOperations"] == [] and result["reply"] == writer.reply
    assert writer.situations[0]["undoNothing"]["request"] == "ahi ponle la escala en 125"
    assert "undoNothing" in compose_instructions._result_shape_instruction(writer.situations[0], "es", T2_C04)
    assert deterministic_finals._deterministic_final(writer.situations[0], {}, T2_C04, "es") == (
        "No había cambiado nada, así que sigue como estaba."
    )


def test_after_a_verified_brightness_the_undo_restores() -> None:
    """Contracaso: «regrésalo como estaba» right after a verified change is decided as before (it restores)."""

    state = _state("pon el brillo al 40", ["system.settings.set"], _brightness_set(), "He puesto el brillo al 40.")
    assert state.undo_of_nothing("regresalo como estaba", risk_of=_risk) is None


@pytest.mark.parametrize("between", ["read", "talk"])
def test_an_undo_after_a_turn_that_followed_a_change_is_decided_as_before(between: str) -> None:
    """Contracaso: a change two turns back with a read or a talk between is still there to put back."""

    state = _state("pon el brillo al 40", ["system.settings.set"], _brightness_set(), "He puesto el brillo al 40.")
    if between == "read":
        clock = {"kind": "operation", "operation": "system.time", "polarity": "success", "verified": True,
                 "succeeded": True, "observed": {"version": 1, "time": "21:10"}}
        state.expect("que hora es", ["system.time"])
        state.record(clock)
        state.told(clock, "Son las 21:10.")
    else:
        state.expect("cuentame un chiste", [])
        state.said("¿Por qué el libro de matemáticas está triste? Porque tiene muchos problemas.")
    assert state.undo_of_nothing("regresa el brillo como estaba", risk_of=_risk) is None


@pytest.mark.parametrize("text", ["te dije la escala no el brillo, regresa la escala a 100", "¿cómo estaba?"])
def test_no_undo_is_no_undo_of_nothing(text: str) -> None:
    assert _scale_asked_state().undo_of_nothing(text, risk_of=_risk) is None


def test_an_operation_whose_risk_is_unknown_counts_as_an_effect() -> None:
    state = _state("haz algo", ["thing.unknown"], {
        "kind": "operation", "operation": "thing.unknown", "polarity": "success", "verified": True, "succeeded": True,
        "observed": {"version": 1},
    }, "Hecho.")
    state.expect("ahora otra cosa", [])
    state.said("Vale.")
    assert state.undo_of_nothing("regresalo como estaba", risk_of=_risk) is None


@pytest.mark.parametrize("observed", [
    {"reached": False},
    {"reached": False, "stepCount": 2, "steps": [{"operation": "input.visible.click", "ok": True}] * 2},
])
def test_an_undo_of_a_question_after_a_mission_that_only_tried_is_of_nothing(observed: dict) -> None:
    """Estabilización G3 (tanda f2nb t2-c04 #3, rewritten from Revisión 1 de la ronda 24): «abre configuracion y ve a
    pantalla» failed after unverified clicks, «ahi ponle la escala en 125» was only asked about, and the undo went to
    the engine, which pressed the theme «Windows (oscuro)» twice and stopped with no step. The undo is of the last
    request about an operation, which did and tried nothing: nothing of it to put back, and no engine. The earlier
    mission's clicks are no change this undo names (the contracaso below keeps the one that is)."""

    assert _scale_asked_state(observed).undo_of_nothing(T2_C04, risk_of=_risk) == "ahi ponle la escala en 125"


def test_g3_contracaso_an_undo_after_a_read_that_followed_an_unverified_mission_is_decided_as_before() -> None:
    """Estabilización G3, contracaso: the request before the undo verified a read (it is no question nor a failure
    without a step); the scale the unverified mission may have set is still what the undo may name."""

    clicked = _failed_mission({"reached": False, "stepCount": 3,
                               "steps": [{"operation": "input.visible.click", "ok": True}] * 3})
    state = _state("ponle la escala en 125", ["mission.computer.use"], clicked,
                   "No pude llegar a dejar la escala en 125.")
    clock = {"kind": "operation", "operation": "system.time", "polarity": "success", "verified": True,
             "succeeded": True, "observed": {"version": 1, "time": "21:10"}}
    state.expect("que hora es", ["system.time"])
    state.record(clock)
    state.told(clock, "Son las 21:10.")
    assert state.undo_of_nothing(T2_C04, risk_of=_risk) is None


def test_g3_contracaso_a_verified_change_before_the_question_is_still_there() -> None:
    """Estabilización G3, contracaso: a change verified in any turn before the question keeps the undo decided."""

    state = _state("sube el brillo al 80", ["system.settings.set"], _brightness_set(), "He puesto el brillo al 80.")
    clicked = _failed_mission({"reached": False, "stepCount": 1, "steps": [{"operation": "input.visible.click", "ok": True}]})
    state.expect("abre configuracion y ve a pantalla", ["mission.computer.use"])
    state.record(clicked)
    state.told(clicked, "No pude llegar a «pantalla».")
    send_offer._expect_decided_turn(
        state,
        {"kind": "clarify", "question": SCALE_QUESTION, "intentOperations": ["mission.computer.use"]},
        {"text": "ahi ponle la escala en 125"},
    )
    assert state.undo_of_nothing(T2_C04, risk_of=_risk) is None


def _talk(state: dialogue.DialogueState, request: str, reply: str) -> None:
    send_offer._expect_decided_turn(state, {"kind": "conversation", "reply": reply}, {"text": request})


def test_a_change_three_turns_back_is_still_there_to_put_back() -> None:
    """Revisión 1 de la ronda 24 (bloqueante 1): brillo verificado, una lectura y una charla de por medio."""

    state = _state("sube el brillo al 80", ["system.settings.set"], _brightness_set(), "He puesto el brillo al 80.")
    clock = {"kind": "operation", "operation": "system.time", "polarity": "success", "verified": True,
             "succeeded": True, "observed": {"version": 1, "time": "21:10"}}
    state.expect("que hora es", ["system.time"])
    state.record(clock)
    state.told(clock, "Son las 21:10.")
    _talk(state, "gracias", "De nada.")
    assert state.undo_of_nothing("regresa el brillo como estaba", risk_of=_risk) is None
    writer = _Writer("No había cambiado nada, así que sigue como estaba.")
    message = {"id": "t4", "text": "regresa el brillo como estaba", "history": []}
    assert turn_followups._correction_already_held(message, state, writer, _risk) is None
    assert writer.situations == []


def test_a_change_before_a_question_and_a_dismissal_is_still_there() -> None:
    """Revisión 1 de la ronda 24 (bloqueante 1): brillo verificado, una pregunta y «nada, dejalo» de por medio."""

    state = _state("sube el brillo al 80", ["system.settings.set"], _brightness_set(), "He puesto el brillo al 80.")
    send_offer._expect_decided_turn(
        state,
        {"kind": "clarify", "question": "¿Qué quieres hacer con el volumen?", "intentOperations": ["audio.volume"]},
        {"text": "y el volumen"},
    )
    _talk(state, "nada, dejalo", "Vale.")
    assert state.undo_of_nothing("regresa el brillo como estaba", risk_of=_risk) is None


@pytest.mark.parametrize("talks", [1, 2])
def test_an_unverified_mission_before_talks_is_no_undo_of_nothing(talks: int) -> None:
    """Revisión 1 de la ronda 24 (bloqueante 2): «ponle la escala en 125» sin verificar (sus clics pudieron dejarla en
    125), una o dos charlas, y «regresala como estaba»: nunca se dice que nada cambió."""

    clicked = _failed_mission({"reached": False, "stepCount": 3,
                               "steps": [{"operation": "input.visible.click", "ok": True}] * 3})
    state = _state("ponle la escala en 125", ["mission.computer.use"], clicked,
                   "No pude llegar a dejar la escala en 125.")
    for said in ("por que?", "ok")[:talks]:
        _talk(state, said, "Porque no encontré el control.")
    assert state.undo_of_nothing(T2_C04, risk_of=_risk) is None


def test_an_undo_of_nothing_names_the_request_about_an_operation_not_a_thanks() -> None:
    """Revisión 1 de la ronda 24: what changed nothing is the last request about an operation, not a «gracias»."""

    state = _scale_asked_state()
    _talk(state, "gracias", "De nada.")
    assert state.undo_of_nothing(T2_C04, risk_of=_risk) == "ahi ponle la escala en 125"


@pytest.mark.parametrize("text", [
    "nah, dejalo como estaba y abre spotify",
    "no, mejor dejala como estaba y sube el volumen al 50",
    "regresala como estaba y despues abre la calculadora",
    "deshazlo y borra el archivo notas.txt",
    "undo that and open spotify",
    "put it back the way it was, then close chrome",
    "undo that y abre spotify",
    "ponla como estaba bro and then mute the audio",
    "cierra chrome y despues deshazlo",
    "open spotify, then undo that",
    "abre la calculadora y ponla como estaba",
])
def test_an_undo_with_another_order_after_it_is_decided_whole(text: str) -> None:
    """Revisión 4 de la ronda 24 (bloqueante 1): an undo followed by another order is never answered as an undo of
    nothing (español, inglés, spanglish); the decider reads the whole message, and its order is never lost."""

    state = _scale_asked_state()
    assert not dialogue.only_undoes(text)
    assert state.undo_of_nothing(text, risk_of=_risk) is None
    writer = _Writer("No había cambiado nada, así que sigue como estaba.")
    assert turn_followups._correction_already_held({"id": "t3", "text": text, "history": []}, state, writer, _risk) is None
    assert writer.situations == []


@pytest.mark.parametrize("text", [
    T2_C04,
    "regresala como estaba porfa",
    "dejala como estaba antes, gracias",
    "deshazlo",
    "undo that please",
    "put it back the way it was",
    "ponla back como estaba bro",
])
def test_an_undo_that_is_all_the_message_says_is_still_one(text: str) -> None:
    """Revisión 4 de la ronda 24, contracaso: what only closes the undo («porfa», «gracias», «please», «bro») leaves it
    the whole message; after a turn that changed nothing it is still told so."""

    assert dialogue.only_undoes(text)
    assert _scale_asked_state().undo_of_nothing(text, risk_of=_risk) == "ahi ponle la escala en 125"


@pytest.mark.parametrize("antecedent", [
    [("hola", "Hola, ¿en qué te ayudo?")],
    [("hola", "Hola, ¿en qué te ayudo?"), ("cuentame un chiste", "¿Por qué el mar es salado? Porque no sabe dulce.")],
    [("hey what's up", "Not much, how can I help?")],
])
@pytest.mark.parametrize("text", [
    "cambie el fondo sin querer, ponlo como estaba",
    "pon la alarma como la tenia",
    "put it back the way it was",
])
def test_an_undo_after_only_talk_is_decided_as_before(antecedent: list[tuple[str, str]], text: str) -> None:
    """Revisión 4 de la ronda 24 (bloqueante 2): with only a greeting or a talk before, no request of BAXY's was
    about an operation; nothing of its own changed or not, and «no había cambiado nada» is never said unverified
    (nor «hola» named as what changed nothing). The decider reads the message, as before."""

    state = dialogue.DialogueState()
    for said, reply in antecedent:
        _talk(state, said, reply)
    assert state.undo_of_nothing(text, risk_of=_risk) is None
    writer = _Writer("No había cambiado nada, así que sigue como estaba.")
    assert turn_followups._correction_already_held({"id": "t2", "text": text, "history": []}, state, writer, _risk) is None
    assert writer.situations == []


# --------------------------------------------------------------------------- (5) la queja tras una pregunta

T2_C03 = "no bro cerraste el que no era, te dije CONFIGURACION"
CLOSE_QUESTION = "¿Te gustaría que cierre la configuración ahora mismo?"


def _closed() -> dict:
    return {
        "kind": "operation", "operation": "app.close", "polarity": "success", "verified": True, "succeeded": True,
        "observed": {"version": 1, "application": "Configuración", "closed": 1},
    }


def _config_state(*, asked: bool) -> dialogue.DialogueState:
    opened = {
        "kind": "operation", "operation": "mission.computer.use", "polarity": "success", "verified": True,
        "succeeded": True, "observed": {"reached": True, "application": "Configuración"},
    }
    state = _state("abre configuracion que quiero ver lo de la pantalla", ["mission.computer.use"], opened,
                   "Listo, estoy en «Pantalla».")
    if asked:
        send_offer._expect_decided_turn(
            state, {"kind": "clarify", "question": CLOSE_QUESTION, "intentOperations": ["app.close"]},
            {"text": "ya cierra configuracion que me esta laggeando el valorant"},
        )
    state.expect(T2_C03, ["app.close"])
    return state


def test_t2_c03_the_reproach_after_a_question_is_of_that_question() -> None:
    state = _config_state(asked=True)
    facts = compose_facts._with_listing_and_repetition_facts({"situation": _closed()}, _closed(), state, T2_C03, T2_C03)
    corrected = facts["situation"]["correctedFinal"]
    assert corrected == {"previousReply": CLOSE_QUESTION, "previousTurnActed": False}
    assert "previousTurnActed is false" in compose_instructions._compose_shape_instruction(facts["situation"], "es", T2_C03)
    assert visible_defect.compose_visible_defect(
        "No, cerré la ventana de Configuración que pediste.", "operation", T2_C03, facts, said=T2_C03,
    ) == "denies_the_correction"
    assert visible_defect.compose_visible_defect(
        "Cerré la ventana de Configuración.", "operation", T2_C03, facts, said=T2_C03,
    ) != "denies_the_correction"


def test_a_reproach_of_an_act_told_keeps_the_last_final_without_the_flag() -> None:
    """Contracaso: after a final that told an act, correctedFinal is as before and no denial is judged."""

    state = _config_state(asked=False)
    facts = compose_facts._with_listing_and_repetition_facts({"situation": _closed()}, _closed(), state, T2_C03, T2_C03)
    assert facts["situation"]["correctedFinal"] == {"previousReply": "Listo, estoy en «Pantalla»."}
    assert visible_defect.compose_visible_defect(
        "No, cerré la ventana de Configuración que pediste.", "operation", T2_C03, facts, said=T2_C03,
    ) != "denies_the_correction"


def test_a_failed_act_after_a_question_is_not_judged_as_a_denial() -> None:
    """Contracaso: when this turn's act did not resolve the request, «No, …» may tell it."""

    state = _config_state(asked=True)
    failed = {"kind": "operation", "operation": "app.close", "polarity": "failure", "verified": True,
              "succeeded": False, "observed": {"version": 1, "application": "Configuración"}}
    facts = compose_facts._with_listing_and_repetition_facts({"situation": failed}, failed, state, T2_C03, T2_C03)
    assert visible_defect.compose_visible_defect(
        "No, no pude cerrar Configuración.", "error", T2_C03, facts, said=T2_C03,
    ) != "denies_the_correction"


@pytest.mark.parametrize(("reply", "denies"), [("No, cerré Configuración.", True), ("No había ventanas.", False),
                                                ("Nope. Done.", True), ("Cerré Configuración.", False)])
def test_opens_with_a_denial(reply: str, denies: bool) -> None:
    assert dialogue.opens_with_a_denial(reply) is denies


# --------------------------------------------------------------------------- revisión 2

# The real final of r23 t2-c03 #3 (compose_audit t2, row 16): a two-step plan told as a completed mission, with no
# ``verified``, ``succeeded`` nor ``observed`` on top, its steps as the shell sends them (JSON strings).
def _closed_by_plan(*, closed: bool = True) -> dict:
    import json

    resolved = {"kind": "operation", "operation": "window.resolve", "polarity": "success", "verified": True,
                "succeeded": True, "observed": {"version": 1, "windows": [{"title": "Configuración"}], "count": 1},
                "readOnly": True}
    close = {"kind": "operation", "operation": "app.close", "polarity": "success" if closed else "failure",
             "verified": True, "succeeded": closed, "observed": {"version": 1, "windowClosed": closed},
             "readOnly": False}
    return {"kind": "status", "polarity": "success", "cause": "mission_completed", "stepCount": 2,
            "steps": [json.dumps(resolved, ensure_ascii=False), json.dumps(close, ensure_ascii=False)],
            "completedRequest": "Cierra la ventana de Configuración."}


def test_t2_c03_the_real_plan_final_is_judged_as_a_denial() -> None:
    state = _config_state(asked=True)
    plan = _closed_by_plan()
    facts = compose_facts._with_listing_and_repetition_facts({"situation": plan}, plan, state, T2_C03, T2_C03)
    assert facts["situation"]["correctedFinal"] == {"previousReply": CLOSE_QUESTION, "previousTurnActed": False}
    assert visible_defect.compose_visible_defect(
        "No, cerré la ventana de Configuración que pediste.", "status", T2_C03, facts, said=T2_C03,
    ) == "denies_the_correction"
    assert visible_defect.compose_visible_defect(
        "Cerré la ventana de Configuración.", "status", T2_C03, facts, said=T2_C03,
    ) != "denies_the_correction"


def test_a_plan_with_a_step_that_failed_is_not_judged_as_a_denial() -> None:
    """Contracaso: a plan whose close step failed resolved nothing; «No, …» may tell it."""

    state = _config_state(asked=True)
    plan = _closed_by_plan(closed=False)
    facts = compose_facts._with_listing_and_repetition_facts({"situation": plan}, plan, state, T2_C03, T2_C03)
    assert visible_defect.compose_visible_defect(
        "No, no pude cerrar la ventana de Configuración.", "status", T2_C03, facts, said=T2_C03,
    ) != "denies_the_correction"
    assert not visible_defect._this_turn_resolved({"kind": "status", "cause": "mission_completed", "steps": []})


SCALE_ASKED = "ahi ponle la escala en 125"
SCALE_REPROACH = "no bro, te dije 125, no preguntes"


def test_t2_c04_a_composed_question_is_no_act() -> None:
    """r23 t2-c04 #2: the shell composed the question by message.compose ({kind: clarification, polarity: pending})."""

    state = _config_state(asked=False)
    state.expect(SCALE_ASKED, ["mission.computer.use"])
    question = {"kind": "clarification", "polarity": "pending", "cause": "ambiguous_request"}
    state.told(question, SCALE_QUESTION)
    assert state.last_final_acted() is False
    state.expect(SCALE_REPROACH, ["system.settings.set"])
    done = {"kind": "operation", "operation": "system.settings.set", "polarity": "success", "verified": True,
            "succeeded": True, "observed": {"version": 1, "setting": "scale", "value": 125}}
    facts = compose_facts._with_listing_and_repetition_facts({"situation": done}, done, state, SCALE_REPROACH,
                                                        SCALE_REPROACH)
    assert facts["situation"]["correctedFinal"] == {"previousReply": SCALE_QUESTION, "previousTurnActed": False}
    assert visible_defect.compose_visible_defect(
        "No, puse la escala en 125.", "operation", SCALE_REPROACH, facts, said=SCALE_REPROACH,
    ) == "denies_the_correction"


@pytest.mark.parametrize("situation", [
    {"kind": "confirmation", "polarity": "pending"},
    {"kind": "conversation", "polarity": "success"},
    {"kind": "status", "polarity": "pending"},
])
def test_questions_and_talks_told_are_no_acts(situation: dict) -> None:
    state = dialogue.DialogueState()
    state.expect("x", [])
    state.told(situation, "¿Algo?")
    assert state.last_final_acted() is False


@pytest.mark.parametrize("situation", [_brightness_set(), _failed_mission({"reached": False, "stepCount": 1})])
def test_results_told_are_acts(situation: dict) -> None:
    """Contracaso: an operation's result, done or failed, is an act."""

    state = dialogue.DialogueState()
    state.expect("x", ["system.settings.set"])
    state.told(situation, "Listo.")
    assert state.last_final_acted() is True


def test_the_held_target_fallback_claims_no_change() -> None:
    """r23 t4-c04 #1 «El brillo ya estaba al 40.» (observed.changed false): the fallback of the held target says no
    change, in either language."""

    situation = {"kind": "conversation", "polarity": "success",
                 "alreadyHolds": {**HELD_TARGET, "previousReply": "El brillo ya estaba al 40."}}
    for language in ("es", "en"):
        final = deterministic_finals._held_fact_final(situation, language)
        assert final and "cambi" not in final.casefold() and "change" not in final.casefold()
    assert _defect(deterministic_finals._held_fact_final(situation, "es"), situation, T4_C04) == ""


@pytest.mark.parametrize("request_text", ["no bro, la 3 esta mal", "no, la 2 no era esa"])
def test_a_correction_that_disputes_no_count_keeps_the_tail_as_a_repeat(request_text: str) -> None:
    """Contracaso: a correction that names a number without disputing the count is no count correction; the last
    answer with a tail is still the last answer again."""

    from baxy_mind.semantic import listing

    assert dialogue.corrects_or_insists(request_text) and not listing.count_disputed(request_text)
    assert dialogue_history._repeats_the_last_answer(FOUR_CAUSES, THREE_CAUSES, request_text)


def test_t3_c17_the_reply_that_argues_the_count_is_vetoed() -> None:
    situation = {"kind": "conversation", "polarity": "success"}
    assert _defect("Te di 3 elementos, no 7 ni 4.", situation, T3_C17) == "argues_the_count"
    assert _defect("No son 4, son 3.", situation, T3_C17) == "argues_the_count"


@pytest.mark.parametrize(("reply", "text"), [
    ("Ya te di 4, los que pediste.", T3_C17),
    (FOUR_CAUSES, T3_C17),
    ("No, no son 4 elementos.", "gracias, los 4 estan buenos"),
])
def test_what_does_not_argue_the_count_passes(reply: str, text: str) -> None:
    """Contracaso: the settled dispute said as given, the items listed, and a message that disputes nothing."""

    from baxy_mind.semantic import listing

    assert not listing.argues_the_count(reply, text)
