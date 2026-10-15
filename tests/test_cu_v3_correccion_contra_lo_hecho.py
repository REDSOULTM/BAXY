"""Ronda 19 de uso real v3, palanca «corrección contra lo hecho».

Una corrección no se comparaba con lo que el turno anterior ya verificó, y su lectura fallaba en cinco puntos:

- t3-c16/2 «no, en YouTube» con YouTube ya sonando volvía a lanzar ``media.play.youtube`` (``already_holds``);
- t3-c18/3 «esa no es la de programador wey, sigue en la estandar, cambiala» no era corrección
  (``reproaches_the_state``) y la misión ya había llegado a Programador (``already_holds``);
- t1-c03 #2 «no wey te pedi 5 nomas, …» tras «No lo encontré.» acababa en una pregunta que pedía los 5 títulos
  (``undelivered_reproach``, ``__main__._undelivered_done_again``);
- t2-c03 T3 la respuesta anterior más un añadido pasaba el control de repetición (``llm._repeats_the_last_answer``);
- t2-c04 T3 «no espera se ve muy grande, regresala como estaba» se leía como prohibición
  (``grammar._is_negative_effect_clause``, ``missions.engine_can_try``).

Cada regla lleva sus contracasos.
"""

from __future__ import annotations

import pytest

from baxy_mind import dialogue_history
from baxy_mind.semantic import dialogue
from baxy_mind.semantic.grammar import _fold, _is_negative_effect_clause
from baxy_mind.semantic.missions import engine_can_try
from baxy_mind import turn_audit
from baxy_mind import turn_followups
from baxy_mind import engine_handoff


@pytest.fixture(autouse=True)
def _no_turn_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(turn_audit, "_append_turn_audit", lambda row: None)


# --------------------------------------------------------------------------- hechos verificados del turno anterior

SODA = "Soda Stereo - De Musica Ligera (El Último Concierto)"
SODA_TOLD = f"Está sonando «{SODA}» en YouTube."


def _youtube_playing() -> dict:
    # t3-c16/1, as compose_audit recorded it (stage first).
    return {
        "kind": "operation", "operation": "media.play.youtube", "polarity": "success", "verified": True,
        "succeeded": True,
        "observed": {
            "version": 1, "provider": "youtube", "query": "Soda Stereo", "title": SODA,
            "finalUrl": "https://www.youtube.com/watch?v=OX-us7PEfkc", "playbackStatus": "playing",
            "authority": "user_browser_smtc_postread",
        },
    }


def _calculator_mission(values: list[dict] | None = None, numbers: list[str] | None = None) -> dict:
    # t3-c18/2, as compose_audit recorded it: the mission reached Programador and the screen read after it shows the
    # programmer's number bases; the focused navigation item «Estándar Calculadora» is no screen value.
    return {
        "kind": "operation", "operation": "mission.computer.use", "polarity": "success", "verified": True,
        "succeeded": True,
        "observed": {
            "goal": "hacer clic en programador", "application": "Calculadora", "reached": True,
            "successCheck": "stepDone:input.visible.click:programador|stepDone:input.visible.click:programmer",
            "satisfiedBy": "stepDone:input.visible.click:programador",
            "window": {"title": "Calculadora", "focused": {"kind": "ListItem", "name": "Estándar Calculadora"}},
            "screen": {
                "title": "Calculadora",
                "values": values if values is not None else [
                    {"name": "Decimal 0", "state": "selected"},
                    {"name": "Teclado numérico completo", "state": "selected"},
                    {"name": "Calculadora", "value": "Calculadora"},
                ],
                "numbers": numbers if numbers is not None else [
                    "Hexadecimal 0", "Decimal 0", "Octal 0", "Binario 0", "Se muestra 0",
                ],
            },
        },
    }


TOP5_REQUEST = "cuales son las peliculas mas taquilleras de la historia? dame el top 5"
TOP5_TOLD = (
    "1. Avatar\n2. Avengers: Endgame\n3. Avatar: El camino del agua\n4. Titanic\n"
    "5. Star Wars: El despertar de la Fuerza"
)


def _search_result() -> dict:
    return {
        "kind": "operation", "operation": "web.search", "polarity": "success", "verified": True, "succeeded": True,
        "observed": {"version": 1, "query": "peliculas mas taquilleras de la historia", "count": 5, "results": []},
    }


def _state(request: str, operation: str, situation: dict, told: str) -> dialogue.DialogueState:
    state = dialogue.DialogueState()
    state.expect(request, [operation])
    state.record(situation)
    state.told(situation, told)
    return state


# --------------------------------------------------------------------------- (a) ya está así

class _Writer:
    """The writer's seam (``compose_user_message``): records each situation and answers ``reply``."""

    def __init__(self, reply: object = "Sigue sonando en YouTube, no lo puse de nuevo.") -> None:
        self.reply = reply
        self.situations: list[dict] = []

    def compose_user_message(self, text: str, intent: str, facts: dict, *, said: str = "") -> str:
        self.situations.append(facts["situation"])
        if isinstance(self.reply, Exception):
            raise self.reply
        return str(self.reply)


def test_t3_c16_2_youtube_already_playing_is_told_not_played_again() -> None:
    state = _state("poneme algo de Soda Stereo", "media.play.youtube", _youtube_playing(), SODA_TOLD)
    holds = state.already_holds("no, en YouTube")
    assert holds == dialogue.AlreadyHolds("playing", named="YouTube", title=SODA)
    writer = _Writer()
    result = turn_followups._correction_already_held({"id": "t2", "text": "no, en YouTube", "history": []}, state, writer)
    assert result is not None and result["kind"] == "conversation"
    # Encargo TZ-HOLD rewrote this (the writer worded the held play, and in tanda z6 t4-c01 its retry denied it): a
    # held effect is said with its sentence from the data (operation_floor «heldFact.playing»), never drafted.
    assert result["effectOperations"] == [] and result["reply"] == f"Ya está sonando «{SODA}» en YouTube."
    assert writer.situations == []


def test_another_service_after_youtube_is_no_already_holds() -> None:
    state = _state("poneme algo de Soda Stereo", "media.play.youtube", _youtube_playing(), SODA_TOLD)
    assert state.already_holds("no, en Spotify") is None
    assert state.already_holds("no en youtube, en spotify") is None
    assert turn_followups._correction_already_held({"id": "t2", "text": "no, en Spotify", "history": []}, state, _Writer()) is None


def test_going_on_and_recall_are_no_corrections() -> None:
    state = _state("poneme algo de Soda Stereo", "media.play.youtube", _youtube_playing(), SODA_TOLD)
    assert state.already_holds("y ahora baja el brillo") is None
    assert state.already_holds("repetí lo que dijiste") is None


def test_t3_c18_3_programmer_read_on_screen_is_told_not_clicked_again() -> None:
    text = "esa no es la de programador wey, sigue en la estandar, cambiala"
    assert dialogue.corrects_or_insists(text)
    shown = _calculator_mission(values=[{"name": "Programador", "value": "Programador"}])
    state = _state("ahora ponla en modo programador", "mission.computer.use", shown,
                   "Llegué al Programador de la Calculadora y elegí el modo Decimal.")
    assert state.already_holds(text) == dialogue.AlreadyHolds("state", named="Programador")


def test_standard_truly_on_screen_is_acted_on() -> None:
    text = "esa no es la de programador wey, sigue en la estandar, cambiala"
    shown = _calculator_mission(values=[{"name": "Estándar", "value": "Estándar"}], numbers=["Se muestra 0"])
    state = _state("ahora ponla en modo programador", "mission.computer.use", shown, "Listo.")
    assert state.already_holds(text) is None
    # «sigue en estándar» alone names nothing the mission verified: it is acted on.
    state = _state("ahora ponla en modo programador", "mission.computer.use", _calculator_mission(), "Listo.")
    assert dialogue.corrects_or_insists("sigue en estándar")
    assert state.already_holds("sigue en estándar") is None


def test_five_told_then_te_pedi_5_says_they_were_five() -> None:
    state = _state(TOP5_REQUEST, "web.search", _search_result(), TOP5_TOLD)
    text = "no wey te pedi 5 nomas, no me sueltes la lista entera"
    assert state.already_holds(text) == dialogue.AlreadyHolds("count", count=5)
    assert state.undelivered_reproach(text) is None


def test_already_holds_needs_a_verified_last_turn() -> None:
    state = dialogue.DialogueState()
    state.expect("poneme algo de Soda Stereo", ["media.play.youtube"])
    failed = {**_youtube_playing(), "verified": True, "succeeded": False, "polarity": "failure"}
    state.record(failed)
    state.told(failed, "No pude reproducirlo.")
    assert state.already_holds("no, en YouTube") is None


def test_the_reply_is_never_a_fixed_one_in_code() -> None:
    # Revisión adversarial 2 (invariante 5): no fixed reply in the code nor in the correction words. Encargo TZ-HOLD
    # rewrote this (the held play was the writer's): a held effect is said with its sentence from the data
    # (operation_floor «heldFact»), in the reply's language; a held count is still the writer's, and no writer, a
    # writer that fails or one that says the last answer again leave the turn to be decided as before.
    from baxy_mind.semantic.grammar import correction_words

    assert "replies" not in correction_words()
    state = _state("poneme algo de Soda Stereo", "media.play.youtube", _youtube_playing(), SODA_TOLD)
    result = turn_followups._correction_already_held({"id": "t2", "text": "no, on YouTube", "history": []}, state, object())
    assert result is not None and result["reply"] == f"«{SODA}» is already playing on YouTube."
    counted = _state(TOP5_REQUEST, "web.search", _search_result(), TOP5_TOLD)
    message = {"id": "t2", "text": "no wey te pedi 5 nomas, no me sueltes la lista entera", "history": []}
    assert turn_followups._correction_already_held(message, counted, object()) is None
    assert turn_followups._correction_already_held(message, counted, _Writer(RuntimeError("down"))) is None
    assert turn_followups._correction_already_held(message, counted, _Writer(TOP5_TOLD)) is None
    assert turn_followups._correction_already_held(message, counted, _Writer("")) is None


def test_a_held_play_whose_sentence_is_the_last_final_is_decided_as_before() -> None:
    """Contracaso: the held sentence never says the last final again; the turn is decided as before."""

    said = f"Ya está sonando «{SODA}» en YouTube."
    state = _state("poneme algo de Soda Stereo", "media.play.youtube", _youtube_playing(), said)
    assert turn_followups._correction_already_held({"id": "t3", "text": "no, en YouTube", "history": []}, state, _Writer()) is None


# --------------------------------------------------------------------------- (b) reproche tras un turno fallido

def _clarify() -> dict:
    return {
        "type": "turn.result", "id": "t2", "kind": "clarify", "operation": None, "intentOperations": [],
        "effectOperations": [], "question": "¿Podrías decirme solo los 5 títulos de la lista?", "reply": "",
        "objective": "no wey te pedi 5 nomas",
    }


def test_t1_c03_2_reproach_after_a_failed_search_searches_again() -> None:
    state = _state(TOP5_REQUEST, "web.search", _search_result(), "No lo encontré.")
    text = "no wey te pedi 5 nomas, no me sueltes la lista entera"
    assert state.already_holds(text) is None
    assert state.undelivered_reproach(text) == ("web.search", TOP5_REQUEST)
    result = turn_followups._undelivered_done_again(_clarify(), {"id": "t2", "text": text}, state)
    assert result["kind"] == "action" and result["operation"] == "web.search"
    assert result["effectOperations"] == ["web.search"] and result["objective"] == TOP5_REQUEST
    assert result["question"] == ""


def test_reproach_after_an_unverified_turn_does_it_again() -> None:
    state = dialogue.DialogueState()
    state.expect("abre la calculadora", ["app.open"])
    assert state.undelivered_reproach("te pedí que abrieras la calculadora") == ("app.open", "abre la calculadora")


def test_a_reproach_that_forbids_repeats_nothing() -> None:
    state = dialogue.DialogueState()
    state.expect("abre la calculadora", ["app.open"])
    assert not dialogue.reproaches_what_was_asked("te pedí que no lo abrieras")
    assert not dialogue.reproaches_what_was_asked("I asked you not to open it")
    assert state.undelivered_reproach("te pedí que no lo abrieras") is None
    decided = _clarify()
    assert turn_followups._undelivered_done_again(decided, {"text": "te pedí que no lo abrieras"}, state) is decided


def test_only_a_question_becomes_the_turn_again() -> None:
    state = _state(TOP5_REQUEST, "web.search", _search_result(), "No lo encontré.")
    decided = {**_clarify(), "kind": "action", "operation": "web.search"}
    assert turn_followups._undelivered_done_again(decided, {"text": "no wey te pedi 5 nomas"}, state) is decided


# --------------------------------------------------------------------------- (c) reproche de estado

@pytest.mark.parametrize("text", [
    "esa no es la de programador wey, sigue en la estandar, cambiala",
    "sigue en estándar",
    "it's still on standard",
    "that's not the programmer one",
])
def test_state_reproaches_are_corrections(text: str) -> None:
    assert dialogue.reproaches_the_state(text)
    assert dialogue.corrects_or_insists(text)


@pytest.mark.parametrize("text", ["y ahora baja el brillo", "¿sigue en pie la reunión?", "and now lower the brightness"])
def test_going_on_or_asking_is_no_state_reproach(text: str) -> None:
    assert not dialogue.reproaches_the_state(text)
    assert not dialogue.corrects_or_insists(text)


# --------------------------------------------------------------------------- (d) interjecciones de corrección

def test_t2_c04_3_no_espera_is_no_prohibition() -> None:
    text = "no espera se ve muy grande, regresala como estaba"
    assert not _is_negative_effect_clause(_fold(text))
    assert engine_can_try(text, ())


@pytest.mark.parametrize("text", [
    "no bro cerraste el que no era, te dije CONFIGURACION",
    "no wait, make it bigger",
    "no che, ponelo más fuerte",
    "no, mejor ponlo en 50",
])
def test_correction_interjections_open_no_prohibition(text: str) -> None:
    assert not _is_negative_effect_clause(_fold(text))


@pytest.mark.parametrize("text", [
    "no esperes",
    "no esperes a que termine",
    "no cierres Spotify",
    "no toques el volumen",
    "no espera, no lo cierres",
    "no bro no cierres spotify",
    "no, mejor no",
])
def test_prohibitions_stay_prohibitions(text: str) -> None:
    assert _is_negative_effect_clause(_fold(text))


# --------------------------------------------------------------------------- (e) casi repetida

T2_C03_LAST = "No se cerró la ventana de Configuración porque esa aplicación no tenía ninguna ventana abierta en ese momento."


def test_t2_c03_3_the_last_answer_with_a_tail_is_a_repetition() -> None:
    reply = T2_C03_LAST[:-1] + ", por lo que no se pudo realizar la acción."
    assert dialogue_history._repeats_the_last_answer(reply, T2_C03_LAST, "no bro cerraste el que no era, te dije CONFIGURACION")


def test_a_word_or_two_changed_is_a_repetition() -> None:
    # Revisión adversarial 2: only an article, a demonstrative or a clitic changed (t3-c17/2 «los» for «las»).
    last = "Te recomiendo los cuatro libros de la saga que más se venden hoy."
    again = "Te recomiendo estos cuatro libros de la saga que más se venden hoy."
    assert dialogue_history._repeats_the_last_answer(again, last, "no, te pedí cinco")
    last = "Te dejé las cuatro novelas de la saga en la lista de hoy."
    again = "Te dejé los cuatro novelas de la saga en la lista de hoy."
    assert dialogue_history._repeats_the_last_answer(again, last, "no, te pedí cinco")


def test_recall_asked_may_repeat() -> None:
    reply = T2_C03_LAST[:-1] + ", por lo que no se pudo realizar la acción."
    assert not dialogue_history._repeats_the_last_answer(reply, T2_C03_LAST, "repetí lo que dijiste")


def test_another_number_is_another_answer() -> None:
    assert not dialogue_history._repeats_the_last_answer(
        "He puesto el brillo de la pantalla en 30.", "He puesto el brillo de la pantalla en 50.", "baja el brillo a 30"
    )


def test_a_different_answer_is_no_repetition() -> None:
    assert not dialogue_history._repeats_the_last_answer(
        "Ya está sonando en YouTube.", SODA_TOLD, "no, en YouTube"
    )
    assert not dialogue_history._repeats_the_last_answer(
        "Avatar, dirigida por James Cameron, ocupa el primer puesto de la lista.", TOP5_TOLD, "y la primera quien la dirigio"
    )


# --------------------------------------------------------------------------- revisión adversarial de la ronda 19

@pytest.mark.parametrize("text", [
    "esa no es la de programador, ponla en científica",
    "no es la de programador, quiero la científica",
    "esa no es, la de programador no me sirve, ponla en grafica",
])
def test_another_state_asked_is_no_already_holds(text: str) -> None:
    state = _state("ahora ponla en modo programador", "mission.computer.use", _calculator_mission(), "Listo.")
    assert state.already_holds(text) is None


def test_the_state_holds_only_when_read_on_the_screen() -> None:
    # Revisión adversarial 2 (invariante 2): the click receipt (satisfiedBy) and «estándar» missing from the screen
    # prove nothing; the recorded t3-c18/2 screen never reads «Programador», so the correction is acted on.
    text = "esa no es la de programador wey, sigue en la estandar, cambiala"
    state = _state("ahora ponla en modo programador", "mission.computer.use", _calculator_mission(), "Listo.")
    assert state.already_holds(text) is None
    shown = _calculator_mission(values=[{"name": "Programador", "value": "Programador"}])
    state = _state("ahora ponla en modo programador", "mission.computer.use", shown, "Listo.")
    assert state.already_holds(text) == dialogue.AlreadyHolds("state", named="Programador")


@pytest.mark.parametrize("text", [
    "te pedí 5 de terror, no de acción",
    "no, te pedí 5 de este año",
    "I asked for 5 comedies not these",
    "te pedí 5 pero en orden de recaudación",
    "no wey te pedi 5 de los 90",
])
def test_a_count_with_another_restriction_is_no_already_holds(text: str) -> None:
    state = _state(TOP5_REQUEST, "web.search", _search_result(), TOP5_TOLD)
    assert state.already_holds(text) is None


def test_a_bare_count_said_back_still_holds() -> None:
    state = _state(TOP5_REQUEST, "web.search", _search_result(), TOP5_TOLD)
    assert state.already_holds("te pedí solo 5") == dialogue.AlreadyHolds("count", count=5)


def test_another_on_the_same_service_is_no_already_holds() -> None:
    state = _state("poneme algo de Soda Stereo", "media.play.youtube", _youtube_playing(), SODA_TOLD)
    assert state.already_holds("no, otra en YouTube") is None
    assert state.already_holds("no, en YouTube") is not None


def test_playing_is_said_only_when_the_result_says_it_plays() -> None:
    paused = _youtube_playing()
    paused["observed"] = {**paused["observed"], "playbackStatus": "paused"}
    holds = dialogue.correction_already_holds(paused, "no, en YouTube", "Está en pausa.")
    assert holds is not None and holds.kind == "provider"
    assert dialogue.correction_already_holds(_youtube_playing(), "no, en YouTube", SODA_TOLD).kind == "playing"


@pytest.mark.parametrize("text", [
    "eso no es urgente, pero abre chrome",
    "that's not important, open spotify",
    "it's still early, play some music",
    "I'm still in the meeting, mute it",
    "ese no es mi problema, abre la calculadora",
    "sigue en la página 3",
    "sigue en YouTube con la siguiente canción",
    "el que sigue en la lista, ábrelo",
    "sigue siendo de noche, baja el brillo",
])
def test_new_requests_are_no_state_reproach(text: str) -> None:
    assert not dialogue.reproaches_the_state(text)
    assert not dialogue.corrects_or_insists(text)


@pytest.mark.parametrize("last, again", [
    ("No, Spotify no está abierto ahora mismo en tu PC.", "No, Discord no está abierto ahora mismo en tu PC."),
    ("El clima en Santiago está despejado y con viento suave.", "El clima en Curicó está despejado y con viento suave."),
    ("Abrí Chrome y lo dejé en primer plano para ti.", "Abrí Edge y lo dejé en primer plano para ti."),
    ("La capital de Francia es París, a orillas del Sena.", "La capital de Italia es Roma, a orillas del Tíber."),
])
def test_a_name_changed_is_another_answer(last: str, again: str) -> None:
    assert not dialogue_history._repeats_the_last_answer(again, last, "no, te pedí la otra")
    assert not dialogue_history._repeats_the_last_answer(again, last, "y el otro")


def test_the_near_repetition_is_read_only_after_a_correction() -> None:
    last = "Te recomiendo los cuatro libros de la saga que más se venden hoy."
    again = "Te recomiendo las cuatro novelas de la saga que más se venden hoy."
    assert not dialogue_history._repeats_the_last_answer(again, last, "y cuál me recomiendas para empezar")
    assert not dialogue_history._repeats_the_last_answer(T2_C03_LAST[:-1] + ", así que no hice nada.", T2_C03_LAST, "gracias")


@pytest.mark.parametrize("text", [
    "te pedí un uber ayer y no llegó",
    "I asked for a refund last week, help me write an email",
    "I asked my boss, now open teams",
    "te pedí perdón",
    "lo que te pedí ayer, ¿lo recuerdas?",
])
def test_a_reproach_of_something_else_does_nothing_again(text: str) -> None:
    state = _state(TOP5_REQUEST, "web.search", _search_result(), "No lo encontré.")
    assert state.undelivered_reproach(text) is None
    decided = _clarify()
    assert turn_followups._undelivered_done_again(decided, {"text": text}, state) is decided


def test_a_reproach_with_a_new_restriction_never_redoes_the_old_request() -> None:
    state = dialogue.DialogueState()
    state.expect("abre la calculadora", ["app.open"])
    assert state.undelivered_reproach("te pedí el bloc de notas, no la calculadora") is None
    assert state.undelivered_reproach("te pedí la calculadora") == ("app.open", "abre la calculadora")
    english = dialogue.DialogueState()
    english.expect("open the calculator", ["app.open"])
    assert english.undelivered_reproach("I asked you to open the calculator") == ("app.open", "open the calculator")


# --------------------------------------------------------------------------- revisión adversarial 2 de la ronda 19

PROHIBITIONS_AFTER_AN_INTERJECTION = [
    "no espera, mejor no cierres spotify",
    "no wey, ni se te ocurra cerrar spotify",
    "no wait, better not close spotify",
    "no bro, tampoco cierres discord",
    "no espera, ahora no",
    "no wait, not yet",
    "no espera, para",
    "no bro, cancela eso",
    "no wey, deja spotify abierto",
    "no espera, aun no",
    "no bro, ahorita no",
    "no, mejor nada",
    "no che, nada",
    "no wey, mejor no hagas nada",
    "no man, not that one",
    "no espera, olvidalo",
    "no wait, stop",
    "no wait cancel that",
    "no espera, mejor no",
    "no, mejor no",
]


@pytest.mark.parametrize("text", PROHIBITIONS_AFTER_AN_INTERJECTION)
def test_a_prohibition_after_an_interjection_stays_a_prohibition(text: str) -> None:
    assert _is_negative_effect_clause(_fold(text))
    assert not engine_can_try(text, ("Spotify", "Discord"))


@pytest.mark.parametrize("text", [
    "no espera, mejor no cierres spotify",
    "no wey, ni se te ocurra cerrar spotify",
    "no wait, better not close spotify",
    "no bro, tampoco cierres discord",
    "no espera, ahora no",
    "no wait, not yet",
    "no espera, para",
    "no bro, cancela eso",
    "no wey, deja spotify abierto",
])
def test_a_prohibition_after_an_interjection_never_reaches_the_engine(text: str) -> None:
    limit = {"type": "turn.result", "id": "t", "kind": "conversation", "conversationKind": "unsupported",
             "effectOperations": [], "intentOperations": [], "reply": "", "question": ""}
    kept = engine_handoff._engine_for_an_unserved_order(
        limit, {"id": "t", "text": text, "history": []}, {"mission.computer.use": {}}, ("Spotify", "Discord")
    )
    assert kept["kind"] == "conversation" and "mission.computer.use" not in (kept.get("effectOperations") or [])


@pytest.mark.parametrize("text", [
    "no, en youtube no",
    "no, youtube no",
    "no en youtube",
    "no en youtube no",
    "no wey, no en youtube",
    "no, nunca en youtube",
    "no, en youtube no wey",
    "no, not on youtube",
])
def test_a_refusal_of_the_service_is_never_already_held(text: str) -> None:
    state = _state("poneme algo de Soda Stereo", "media.play.youtube", _youtube_playing(), SODA_TOLD)
    assert state.already_holds(text) is None
    writer = _Writer()
    assert turn_followups._correction_already_held({"id": "t2", "text": text, "history": []}, state, writer) is None
    assert writer.situations == []


def test_a_standard_screen_or_none_never_says_programmer_holds() -> None:
    text = "esa no es la de programador wey, sigue en la estandar, cambiala"
    standard = _calculator_mission(values=[{"name": "Calculadora", "value": "Calculadora"}], numbers=["Se muestra 0"])
    state = _state("ahora ponla en modo programador", "mission.computer.use", standard, "Listo.")
    assert state.already_holds(text) is None
    blind = _calculator_mission()
    del blind["observed"]["screen"]
    state = _state("ahora ponla en modo programador", "mission.computer.use", blind, "Listo.")
    assert state.already_holds(text) is None


@pytest.mark.parametrize("last, again, said", [
    ("Subí el volumen de tu PC al 50 por ciento.", "Bajé el volumen de tu PC al 50 por ciento.",
     "no, te dije que lo bajaras"),
    ("Abrí la calculadora en tu PC hace un momento.", "Cerré la calculadora en tu PC hace un momento.",
     "no bro, te dije que la cerraras"),
    ("Dejé el wifi de tu PC apagado como pediste.", "Dejé el wifi de tu PC encendido como pediste.",
     "no, te dije que lo prendieras"),
    ("Reanudé la música que estaba sonando en tu PC.", "Pausé la música que estaba sonando en tu PC.",
     "no, te dije pausa"),
    ("I turned the volume of your PC up to 50 percent.", "I turned the volume of your PC down to 50 percent.",
     "no, I said down"),
])
def test_a_verb_or_polarity_changed_is_another_answer(last: str, again: str, said: str) -> None:
    assert not dialogue_history._repeats_the_last_answer(again, last, said)


# --------------------------------------------------------------------------- revisión adversarial 3 de la ronda 19
# La negación tras una interjección se queda por defecto; sólo la quita una orden afirmativa a BAXY leída por los
# lectores de petición que ya existen (grammar._opens_an_order). Sondas de la revisión: la base daba [] y prohibición.

SOFT_DENIALS_AFTER_AN_INTERJECTION = [
    "no espera, detente", "no wait, abort", "no espera, aborta", "no espera, basta", "no wait, enough",
    "no wait, halt", "no espera, alto", "no espera, frena", "no espera, suficiente", "no wait, nevermind",
    "no wait, never mind", "no bro, nah", "no wait, nope", "no wey, nel", "no espera, ninguno", "no wait, none",
    "no espera, sin eso", "no wey, sin cambios", "no espera, todavía", "no espera, aun no", "no espera, un momento",
    "no wait, hold up", "no wait, one sec", "no espera, luego", "no wait, later", "no bro, después",
    "no wey, mejor después", "no, mejor otro día", "no espera, en otro rato", "no espera, ya está bien",
    "no bro, así está bien", "no espera, mejor así", "no wey, gracias", "no espera, era broma", "no wait, my bad",
    "no espera, cállate", "no wait, shut up", "no bro, silencio", "no espera, lo hago yo",
    "no espera, mejor lo cierro yo",
]

APP_REFUSALS_AFTER_AN_INTERJECTION = [
    "no espera, yo abro spotify", "no wait, I'll close discord myself", "no espera, abrir spotify era broma",
    "no wait, open discord later", "no wey, discord se queda", "no bro, que spotify siga abierto",
    "no espera, spotify estaba bien", "no bro, sin abrir spotify", "no espera, después abres discord",
    "no espera, mañana cierras spotify",
]


def _engine_operations(text: str) -> list[str]:
    limit = {"type": "turn.result", "id": "t", "kind": "conversation", "conversationKind": "unsupported",
             "effectOperations": [], "intentOperations": [], "reply": "", "question": ""}
    kept = engine_handoff._engine_for_an_unserved_order(
        limit, {"id": "t", "text": text, "history": []}, {"mission.computer.use": {}}, ("Spotify", "Discord")
    )
    return list(kept.get("effectOperations") or [])


@pytest.mark.parametrize("text", SOFT_DENIALS_AFTER_AN_INTERJECTION + APP_REFUSALS_AFTER_AN_INTERJECTION)
def test_with_no_order_after_the_interjection_the_denial_stays(text: str) -> None:
    assert _is_negative_effect_clause(_fold(text))
    assert _engine_operations(text) == []


@pytest.mark.parametrize("text", PROHIBITIONS_AFTER_AN_INTERJECTION + [
    "no espera, te dije que no lo abrieras", "no espera, cancela la alarma", "no espera, abre spotify mañana",
    "no espera, ¿abres spotify?",
])
def test_no_prohibition_or_cancellation_after_an_interjection_reaches_the_engine(text: str) -> None:
    assert _engine_operations(text) == []


@pytest.mark.parametrize("text", [
    "no espera se ve muy grande, regresala como estaba",
    "no bro cerraste el que no era, te dije CONFIGURACION",
    "no wait, make it bigger",
    "no espera, cerralo",
    "no wait, close it",
    "no bro, abre discord",
    "no wait, lower it",
    "no espera, subile",
    "no wey, sigue en la estandar, cambiala",
    "no wey te pedi 5 nomas, no me sueltes la lista entera",
])
def test_an_order_after_the_interjection_drops_the_denial(text: str) -> None:
    assert not _is_negative_effect_clause(_fold(text))


def test_the_cease_orders_are_order_heads_the_readers_know() -> None:
    from baxy_mind.semantic.grammar import _COVERAGE_ACTION_HEAD, _head_is, correction_words

    assert all(_head_is(head, _COVERAGE_ACTION_HEAD) for head in correction_words()["cease_orders"])


# --------------------------------------------------------------------------- Estabilización G3 (tanda f2nb t3-c18)
# «ahora ponla en modo programador» → «Listo, estoy en «Programador»», satisfied by ``header:programador`` (the
# shell's check read the Calculator's header); the screen's excerpt never repeats the mode. «esa no es la de
# programador wey, sigue en la estandar, cambiala» went to the engine, which saw no step (8,5 s).

T3_C18 = "esa no es la de programador wey, sigue en la estandar, cambiala"


def _checked_by(satisfied: str) -> dict:
    mission = _calculator_mission()
    mission["observed"] = {**mission["observed"], "satisfiedBy": satisfied}
    return mission


@pytest.mark.parametrize(("satisfied", "named"), [
    ("header:programador", "programador"),
    ("control:=Programador:selected", "Programador"),
    ("control:Programador:on|stepDone:input.visible.click:programador", "Programador"),
    ("title:calculadora&header:programador", "programador"),
])
def test_g3_the_state_read_by_the_check_holds(satisfied: str, named: str) -> None:
    state = _state("ahora ponla en modo programador", "mission.computer.use", _checked_by(satisfied), "Listo.")
    assert state.already_holds(T3_C18) == dialogue.AlreadyHolds("state", named=named)


@pytest.mark.parametrize("satisfied", [
    "stepDone:input.visible.click:programador",
    "control:programador",
    "control:programador:off",
    "control:programador:expanded",
])
def test_g3_contracaso_a_receipt_or_a_control_not_on_reads_no_state(satisfied: str) -> None:
    state = _state("ahora ponla en modo programador", "mission.computer.use", _checked_by(satisfied), "Listo.")
    assert state.already_holds(T3_C18) is None


def test_g3_contracaso_the_claimed_state_on_screen_is_acted_on() -> None:
    shown = _checked_by("header:programador")
    shown["observed"]["screen"]["values"].append({"name": "Estándar", "value": "Estándar"})
    state = _state("ahora ponla en modo programador", "mission.computer.use", shown, "Listo.")
    assert state.already_holds(T3_C18) is None
