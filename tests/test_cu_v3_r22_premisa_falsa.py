"""Ronda 22 de uso real v3, palanca «premisa falsa se dice con calma» (pasada r18).

Una corrección cuya premisa es falsa (lo pedido ya se hizo, o ya se intentó donde la persona dice) se rehacía o se
discutía:

- t4-c01 t4 «no po, en spotify te dije, no en youtube» tras un intento fallido en Spotify: se reintentó con la consulta
  «cumbia mientras», rehecha sobre el texto crudo (``DialogueState.attempted_again``, ``_contrastive_redecision``);
- t4-c02 t2 «no, te pedi 3 nomas y me tiraste una lista enorme» tras tres títulos en una frase, y t3-c17 t2 «no te pedi
  4 po, me tiraste como 7, solo 4» tras cuatro causas en conversación: el conteo nunca se comparaba
  (``correction_already_holds``, kind count);
- t4-c04 t2 «joder que te he dicho brillo no volumen» tras poner el brillo: se volvió a poner el brillo (kind target) y
  se vetó «Ya he puesto el brillo al 40 y sigue así» (``llm._repeats_the_last_answer``);
- t3-c18 t3 «sigue en la estándar» con Programador escrito en las líneas de la pantalla.

Las vistas son las que registró la evidencia (tandas_r20, compose_audit). Cada regla lleva sus contracasos.
"""

from __future__ import annotations

import pytest

from baxy_mind import visible_defect
from baxy_mind import dialogue_history
from baxy_mind import compose_instructions
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import decider, dialogue, listing
from baxy_mind import turn_audit
from baxy_mind import turn_followups
from baxy_mind import context_decision
from baxy_mind import send_offer


@pytest.fixture(autouse=True)
def _no_turn_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(turn_audit, "_append_turn_audit", lambda row: None)


def _state(request: str, operations: list[str], situation: dict | None, told: str) -> dialogue.DialogueState:
    state = dialogue.DialogueState()
    state.expect(request, operations)
    if situation is not None:
        state.record(situation)
    state.told(situation or {"kind": "conversation", "polarity": "success"}, told)
    return state


# --------------------------------------------------------------------------- vistas de la evidencia

CAUSES_TOLD = (
    "1. 2. El bloqueo naval alemán. 3. La invasión de Bélgica por Alemania. 4. La declaración de guerra de Rusia a "
    "Alemania."
)
BOOKS_TOLD = "Bestiario, Rayuela y Octaedro son libros de Julio Cortázar."
FIVE_BOOKS_TOLD = (
    "Bestiario, Rayuela, Octaedro, Final del juego y Historias de cronopios son libros de Julio Cortázar."
)


def _books_search() -> dict:
    # t4-c02 t1 (compose_audit trace t5): a verified web search whose final named three titles in one sentence.
    return {
        "kind": "operation", "operation": "web.search", "polarity": "success", "verified": True, "succeeded": True,
        "observed": {"version": 1, "query": "libros de Julio Cortázar", "count": 3, "results": []},
    }


def _brightness_set() -> dict:
    # t4-c04 t1 (compose_audit trace t13).
    return {
        "kind": "operation", "operation": "system.settings.set", "polarity": "success", "verified": True,
        "succeeded": True,
        "observed": {
            "version": 1, "setting": "brightness", "value": 40, "baselineValues": [40],
            "authority": "wmi_monitor_brightness_postread",
        },
    }


def _volume_set() -> dict:
    return {
        "kind": "operation", "operation": "audio.volume", "polarity": "success", "verified": True, "succeeded": True,
        "observed": {"version": 1, "level": 40},
    }


def _spotify_try_failed() -> dict:
    # t4-c01 t3 (compose_audit trace t3): the try in Spotify could not be verified.
    return {
        "kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
        "reason": {
            "kind": "operation", "operation": "media.play.query", "polarity": "failure", "verified": False,
            "succeeded": False, "error": "spotify_uia_failed", "cause": "external_effect_ambiguous",
            "effectUncertain": True,
            "observed": {
                "version": 1, "provider": "spotify", "stage": "started", "detail": "spotify_foreground_not_verified",
            },
            "target": "cumbia", "attempted": {"provider": "spotify", "query": "cumbia"},
        },
    }


SPOTIFY_TOLD = "Intenté poner cumbia en Spotify, pero no puedo confirmar si se reprodujo."


def _calculator_mission(lines: list[str], control_lines: list[int] | None = None) -> dict:
    # t3-c18 t2 (compose_audit trace t25), with the lines the view showed (model_calls: «texto TL: Calculadora |
    # Programador | HEX …»). Revisión 2: the excerpt marks the lines that are a control's label (``controlLines``);
    # none of these is.
    return {
        "kind": "operation", "operation": "mission.computer.use", "polarity": "success", "verified": True,
        "succeeded": True,
        "observed": {
            "goal": "hacer clic en programador", "application": "Calculadora", "reached": True,
            "satisfiedBy": "stepDone:input.visible.click:programador",
            "screen": {
                "title": "Calculadora",
                "values": [{"name": "Decimal 0", "state": "selected"}],
                "numbers": ["Hexadecimal 0", "Decimal 0", "Octal 0", "Binario 0"],
                "lines": lines,
                "controlLines": [] if control_lines is None else control_lines,
            },
        },
    }


# --------------------------------------------------------------------------- (1) el conteo ya se cumplía

FOUR_CAUSES_TOLD = (
    "1. El asesinato del archiduque Francisco Fernando. 2. El bloqueo naval alemán. 3. La invasión de Bélgica por "
    "Alemania. 4. La declaración de guerra de Rusia a Alemania."
)


def test_t3_c17_count_told_in_conversation_already_holds() -> None:
    state = _state("dame 4 causas de la primera guerra mundial cortito pa la prueba", [], None, FOUR_CAUSES_TOLD)
    holds = state.already_holds("no te pedi 4 po, me tiraste como 7, solo 4")
    assert holds == dialogue.AlreadyHolds("count", count=4)


@pytest.mark.parametrize(
    "told",
    [
        # Revisión 2 (bloqueante 3): the evidence's own answer numbered four and told three (item 1 is empty).
        CAUSES_TOLD,
        "1. 2. 3. 4. La declaración de guerra.",
    ],
)
def test_a_list_with_an_empty_item_holds_no_count(told: str) -> None:
    assert listing.empty_items(told) >= 1
    state = _state("dame 4 causas de la primera guerra mundial cortito pa la prueba", [], None, told)
    assert state.already_holds("no te pedi 4 po, me tiraste como 7, solo 4") is None


def test_empty_items_counts_only_items_that_say_nothing() -> None:
    assert listing.empty_items(CAUSES_TOLD) == 1
    assert listing.empty_items("1. 2. 3. 4. La declaración de guerra.") == 3
    assert listing.empty_items(FOUR_CAUSES_TOLD) == 0
    assert listing.empty_items("1. **Pollo al curry**: corta el pollo.\n2. **Tacos**: rellena.") == 0
    assert listing.empty_items(BOOKS_TOLD) == 0


def test_t4_c02_three_titles_in_one_sentence_already_hold() -> None:
    state = _state("dame 3 libros de cortazar para arrancar", ["web.search"], _books_search(), BOOKS_TOLD)
    assert state.already_holds("no, te pedi 3 nomas y me tiraste una lista enorme") == dialogue.AlreadyHolds(
        "count", count=3
    )


def test_a_sentence_opened_by_its_items_is_counted_only_as_such() -> None:
    assert listing.opening_series(BOOKS_TOLD) == 3
    assert listing.opening_series(FIVE_BOOKS_TOLD) == 5
    # Not one sentence, no conjunction, or a long clause before it: no series.
    assert listing.opening_series("Bestiario es un libro. Rayuela, Octaedro y Final del juego también.") is None
    assert listing.opening_series("Bestiario y Rayuela son libros.") is None
    assert listing.opening_series("Te recomiendo empezar por los cuentos más conocidos del autor, Rayuela y más.") is None
    # The list readers themselves are unchanged: such a sentence is still no list told.
    assert listing.listed_items(BOOKS_TOLD) == ()


@pytest.mark.parametrize(
    "text",
    [
        "no, te pedi 3 nomas y me tiraste una lista enorme",
        "te pedí 3 y me diste 5",
        "no te pedi 3 po, me tiraste como 7, solo 3",
    ],
)
def test_the_complaint_said_with_the_reproach_says_only_what_was_asked(text: str) -> None:
    assert dialogue.says_only_what_was_asked(text, "dame 3 libros de cortazar para arrancar")


@pytest.mark.parametrize(
    "text",
    [
        "te pedí 3 de terror",
        "no, te pedi 3 de terror",
        "te pedí 3 y dame 7",
        "te pedí 3, son 6",
    ],
)
def test_a_reproach_that_adds_something_is_no_count_already_held(text: str) -> None:
    state = _state("dame 3 libros de cortazar para arrancar", ["web.search"], _books_search(), BOOKS_TOLD)
    assert state.already_holds(text) is None


def test_five_told_for_three_asked_is_done_again() -> None:
    state = _state("dame 3 libros de cortazar", ["web.search"], _books_search(), FIVE_BOOKS_TOLD)
    assert state.already_holds("te pedí 3 y me diste 5") is None
    assert state.already_holds("no, te pedi 3 nomas y me tiraste una lista enorme") is None


def test_thanks_after_the_list_is_no_correction() -> None:
    state = _state("dame 3 libros de cortazar", ["web.search"], _books_search(), BOOKS_TOLD)
    assert state.already_holds("gracias") is None
    # «gracias» followed by the same list is still the last answer again.
    assert dialogue_history._repeats_the_last_answer(BOOKS_TOLD, BOOKS_TOLD, "gracias")


class _Writer:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.situations: list[dict] = []

    def compose_user_message(self, text: str, intent: str, facts: dict, *, said: str = "") -> str:
        self.situations.append(facts["situation"])
        return self.reply


def test_the_count_held_is_worded_by_the_writer_and_delivers_the_list_again() -> None:
    state = _state("dame 3 libros de cortazar para arrancar", ["web.search"], _books_search(), BOOKS_TOLD)
    writer = _Writer("Son estos 3: Bestiario, Rayuela y Octaedro.")
    text = "no, te pedi 3 nomas y me tiraste una lista enorme"
    result = turn_followups._correction_already_held({"id": "t2", "text": text, "history": []}, state, writer)
    assert result is not None and result["effectOperations"] == [] and result["reply"] == writer.reply
    assert writer.situations[0]["alreadyHolds"] == {"kind": "count", "count": "3", "previousReply": BOOKS_TOLD}
    instruction = compose_instructions._result_shape_instruction(
        {"kind": "conversation", "polarity": "success", "alreadyHolds": writer.situations[0]["alreadyHolds"]},
        "es", text,
    )
    assert "give those same items again" in instruction and "without opening with a denial" in instruction


# --------------------------------------------------------------------------- (3) el objetivo ya era ese

# The catalog's risks of these operations (ProductCatalog.cs): a set acts, a status read does not.
RISKS = {
    "system.settings.set": "low_reversible", "audio.volume": "low_reversible", "system.settings.status": "read_only",
}


def _risk(operation: str) -> str | None:
    return RISKS.get(operation)


def test_t4_c04_brightness_not_volume_after_the_brightness_already_holds() -> None:
    state = _state("pon el brillo al 40", ["system.settings.set"], _brightness_set(), "He puesto el brillo al 40.")
    holds = state.already_holds("joder que te he dicho brillo no volumen", risk_of=_risk)
    assert holds == dialogue.AlreadyHolds("target", named="brillo", untouched="volumen")
    assert holds.facts() == {"kind": "target", "named": "brillo", "untouched": "volumen"}


@pytest.mark.parametrize(
    "text",
    [
        "y ahora baja el brillo",
        "te dije la escala no el brillo, regresa la escala a 100",
        "volumen no brillo",
        "te he dicho brillo no volumen, bajalo a 20",
    ],
)
def test_after_the_brightness_another_order_or_target_goes_on(text: str) -> None:
    state = _state("pon el brillo al 40", ["system.settings.set"], _brightness_set(), "He puesto el brillo al 40.")
    assert state.already_holds(text, risk_of=_risk) is None


def test_brightness_not_volume_after_the_volume_corrects() -> None:
    state = _state("pon el volumen al 40", ["audio.volume"], _volume_set(), "Puse el volumen al 40.")
    assert state.already_holds("joder que te he dicho brillo no volumen", risk_of=_risk) is None


# --------------------------------------------------------------------------- (2) lo intentado se reintenta igual

def test_t4_c01_spotify_already_tried_is_tried_again_with_its_arguments() -> None:
    state = _state("Ponme cumbia.", ["media.play.query"], _spotify_try_failed(), SPOTIFY_TOLD)
    assert state.attempted_again("no po, en spotify te dije, no en youtube") == (
        "Ponme cumbia.", "media.play.query", (("provider", "spotify"), ("query", "cumbia")),
    )
    # Nothing was verified: nothing already holds, the try is made again.
    assert state.already_holds("no po, en spotify te dije, no en youtube") is None


@pytest.mark.parametrize(
    "text",
    ["no, en youtube", "no en spotify, en youtube", "no, otra en spotify", "y ahora sube el volumen"],
)
def test_another_service_or_another_thing_is_no_try_again(text: str) -> None:
    state = _state("Ponme cumbia.", ["media.play.query"], _spotify_try_failed(), SPOTIFY_TOLD)
    assert state.attempted_again(text) is None


def test_a_verified_turn_leaves_no_attempt() -> None:
    playing = {
        "kind": "operation", "operation": "media.play.query", "polarity": "success", "verified": True,
        "succeeded": True, "observed": {"version": 1, "provider": "youtube", "playbackStatus": "playing"},
    }
    state = _state("pon cumbia", ["media.play.query"], playing, "Está sonando cumbia en YouTube.")
    assert state.attempted_again("no po, en spotify te dije, no en youtube") is None


OPERATIONS = ("audio.volume", "media.play.query", "media.play.youtube", "media.status", "system.settings.set")


class _Decider:
    def __init__(self, request: str, decision: str, operations: tuple[str, ...] = ()) -> None:  # noqa: D107
        self.decided = decider.ContextDecision(request=request, decision=decision, operations=operations, question="")

    def decide_in_context(self, *_args: object, **_kwargs: object) -> decider.ContextDecision:
        return self.decided

    @staticmethod
    def clarify_after_turn_failure(*_args: object, **_kwargs: object) -> str:
        return "¿Qué quieres que haga?"


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


def _decided(text: str, model: _Decider, attempted: object = None) -> dict[str, object]:
    history = [
        {"role": "user", "content": "y ponme cumbia mientras"},
        {"role": "assistant", "content": SPOTIFY_TOLD},
        {"role": "user", "content": text},
    ]
    message = {"id": "t4", "text": text, "history": history}
    if attempted is not None:
        message[context_decision._ATTEMPTED_AGAIN] = attempted
    return context_decision._context_decided_result(
        message, llm=model, planner_catalog=PlannerCatalog([_tool(name) for name in OPERATIONS]),
    )


def test_t4_c01_the_try_again_reads_what_was_tried_not_the_raw_words() -> None:
    state = _state("Ponme cumbia.", ["media.play.query"], _spotify_try_failed(), SPOTIFY_TOLD)
    text = "no po, en spotify te dije, no en youtube"
    result = _decided(text, _Decider("Pon una cumbia en YouTube.", "action", ("media.play.youtube",)),
                      state.attempted_again(text))
    assert result["intentOperations"] == ["media.play.query"]
    objective = str(result["objective"]).lower()
    assert "spotify" in objective and "mientras" not in objective and "youtube" not in objective


def test_without_an_attempt_the_contrast_reads_the_last_words_as_before() -> None:
    result = _decided(
        "no po, en spotify te dije, no en youtube",
        _Decider("Pon una cumbia en YouTube.", "action", ("media.play.youtube",)),
    )
    assert result["intentOperations"] == ["media.play.query"]
    assert "mientras" in str(result["objective"]).lower()


# --------------------------------------------------------------------------- (5) el estado negado en las líneas

def test_t3_c18_programmer_written_on_the_screen_lines_already_holds() -> None:
    mission = _calculator_mission(["Calculadora", "Programador", "HEX"])
    state = _state("ahora ponla en modo programador", ["mission.computer.use"], mission, "Listo.")
    holds = state.already_holds("esa no es la de programador wey, sigue en la estandar, cambiala")
    assert holds == dialogue.AlreadyHolds("state", named="Programador")


def test_standard_written_on_the_screen_lines_is_acted_on() -> None:
    mission = _calculator_mission(["Calculadora", "Estándar"])
    state = _state("ahora ponla en modo programador", ["mission.computer.use"], mission, "Listo.")
    assert state.already_holds("esa no es la de programador wey, sigue en la estandar, cambiala") is None
    assert state.already_holds("sigue en la estandar") is None


# --------------------------------------------------------------------------- (4) el mismo hecho con su estado

def test_t4_c04_the_same_fact_said_as_still_holding_is_never_drafted() -> None:
    """Encargo TZ-HOLD rewrote this (``holds=True`` let a held target's draft keep the last answer with «ya… sigue
    así»): the held target is said with its own sentence, so no such draft is asked; judged as any reply after a
    correction, it is the last answer with a tail."""

    assert dialogue_history._repeats_the_last_answer(
        "Ya he puesto el brillo al 40 y sigue así.", "He puesto el brillo al 40.",
        "joder que te he dicho brillo no volumen",
    )
    writer = _Writer("Ya he puesto el brillo al 40 y sigue así.")
    done = _state("pon el brillo al 40", ["system.settings.set"], _brightness_set(), "He puesto el brillo al 40.")
    result = turn_followups._correction_already_held(
        {"id": "t2", "text": "joder que te he dicho brillo no volumen", "history": []}, done, writer, _risk,
    )
    assert result is not None and result["reply"] == "Lo que te dije era de «brillo»; «volumen» no lo toqué."
    assert writer.situations == []


def test_the_last_answer_with_a_tail_and_no_state_word_is_still_a_repeat() -> None:
    assert dialogue_history._repeats_the_last_answer(
        "He puesto el brillo al 40, como pediste.", "He puesto el brillo al 40.",
        "joder que te he dicho brillo no volumen",
    )
    assert dialogue_history._repeats_the_last_answer(
        "He puesto el brillo al 40.", "He puesto el brillo al 40.", "joder que te he dicho brillo no volumen",
    )


# --------------------------------------------------------------------------- revisión 1


@pytest.mark.parametrize(
    "told",
    [
        "Lo siento, no encontré libros y no puedo seguir.",
        "Perdón, no pude buscar y tampoco abrir la página.",
        "Lo intenté, pero falló y no se reprodujo nada.",
        "No pude, el navegador se cerró y no hay resultados.",
    ],
)
def test_a_failure_told_is_no_series_nor_a_count_held(told: str) -> None:
    assert listing.opening_series(told) is None
    failed = {
        "kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
        "reason": {
            "kind": "operation", "operation": "web.search", "polarity": "failure", "verified": False,
            "succeeded": False, "observed": {"version": 1, "query": "libros de cortazar"},
        },
    }
    state = _state("dame 3 libros de cortazar", ["web.search"], failed, told)
    assert state.already_holds("no, te pedí 3 libros") is None
    # The failed search is done again, as on the base.
    assert state.undelivered_reproach("no, te pedí 3 libros") == ("web.search", "dame 3 libros de cortazar")


def test_a_count_after_a_failure_told_in_words_of_success_is_not_held() -> None:
    # Even when the final's words read as a series, a final that told a failure delivered nothing.
    failed = {
        "kind": "operation", "operation": "web.search", "polarity": "failure", "verified": False, "succeeded": False,
        "observed": {"version": 1, "query": "libros de cortazar"},
    }
    state = _state("dame 3 libros de cortazar", ["web.search"], failed, BOOKS_TOLD)
    assert state.already_holds("no, te pedí 3 libros") is None


def test_a_conversation_series_with_its_copula_still_counts() -> None:
    state = _state("dame 3 libros de cortazar", [], None, BOOKS_TOLD)
    assert state.already_holds("no, te pedí 3 libros") == dialogue.AlreadyHolds("count", count=3)


LAST_BOOKS = "Bestiario, Rayuela y Octaedro son libros de Julio Cortázar."


@pytest.mark.parametrize(
    ("request_text", "reply"),
    [
        ("no, te pedí otros de terror", "Ya te dije: Bestiario, Rayuela y Octaedro son libros de Julio Cortázar."),
        ("no, eso no", "Ya, Bestiario, Rayuela y Octaedro son libros de Julio Cortázar."),
        ("no wey, te dije de borges", "Todavia: Bestiario, Rayuela y Octaedro son libros de Julio Cortázar."),
    ],
)
def test_a_state_word_in_front_of_the_last_answer_is_still_a_repeat(request_text: str, reply: str) -> None:
    assert dialogue_history._repeats_the_last_answer(reply, LAST_BOOKS, request_text)


def test_a_held_count_said_again_with_ya_is_vetoed_by_the_writer_check() -> None:
    reply = "Ya, Bestiario, Rayuela y Octaedro son libros de Julio Cortázar."
    situation = {"kind": "conversation", "polarity": "success",
                 "alreadyHolds": {"kind": "count", "count": "3", "previousReply": LAST_BOOKS}}
    defect = visible_defect.compose_visible_defect(
        reply, "conversation", "no, te pedí 3 libros", {"situation": situation}, said="no, te pedí 3 libros",
    )
    assert defect == "repeats_last_answer"


def test_a_held_target_reaches_no_writer_check() -> None:
    """Encargo TZ-HOLD rewrote this (the writer's check let «Ya he puesto el brillo al 40 y sigue así.» pass for a
    held target): a held target never reaches the writer, and its sentence passes the check of a published final."""

    situation = {"kind": "conversation", "polarity": "success",
                 "alreadyHolds": {"kind": "target", "named": "brillo", "untouched": "volumen",
                                  "previousReply": "He puesto el brillo al 40."}}
    text = "joder que te he dicho brillo no volumen"
    final = "Lo que te dije era de «brillo»; «volumen» no lo toqué."
    assert visible_defect.compose_visible_defect(final, "conversation", text, {"situation": situation}, said=text) == ""


def test_brightness_not_volume_after_a_chain_that_set_both_corrects() -> None:
    state = dialogue.DialogueState()
    state.expect("pon el brillo y el volumen al 40", ["audio.volume", "system.settings.set"])
    state.record(_volume_set())
    state.record(_brightness_set())
    state.told(_brightness_set(), "Puse el volumen y el brillo al 40.")
    assert state.already_holds("te he dicho brillo no volumen", risk_of=_risk) is None


def test_brightness_not_volume_after_a_mission_whose_steps_set_the_volume_corrects() -> None:
    mission = {
        "kind": "operation", "operation": "system.settings.set", "polarity": "success", "verified": True,
        "succeeded": True, "observed": _brightness_set()["observed"], "steps": [_volume_set(), _brightness_set()],
    }
    state = _state("pon el brillo al 40", ["system.settings.set"], mission, "He puesto el brillo al 40.")
    assert state.already_holds("te he dicho brillo no volumen", risk_of=_risk) is None


def test_brightness_not_volume_after_a_volume_try_that_failed_corrects() -> None:
    tried = {
        "kind": "operation", "operation": "audio.volume", "polarity": "failure", "verified": False,
        "succeeded": False, "observed": {"version": 1},
    }
    state = dialogue.DialogueState()
    state.expect("pon el brillo y el volumen al 40", ["system.settings.set", "audio.volume"])
    state.record(_brightness_set())
    state.record(tried)
    state.told(_brightness_set(), "He puesto el brillo al 40.")
    assert state.already_holds("te he dicho brillo no volumen", risk_of=_risk) is None


# --------------------------------------------------------------------------- revisión 2


def _brightness_read() -> dict:
    # WindowsDeviceControlAdapter.SettingStatusAsync: a verified read (effect false) that names the setting it read.
    return {
        "kind": "operation", "operation": "system.settings.status", "polarity": "success", "verified": True,
        "succeeded": True, "observed": {"version": 1, "setting": "brightness", "value": 40},
    }


def test_brightness_not_volume_after_a_brightness_read_is_no_target_held() -> None:
    # Bloqueante 2: «¿cuánto está el brillo?» → read → «no, el brillo no el volumen» is no change already made.
    state = _state("¿cuánto está el brillo?", ["system.settings.status"], _brightness_read(), "El brillo está al 40.")
    assert state.already_holds("no, el brillo no el volumen", risk_of=_risk) is None
    assert state.already_holds("joder que te he dicho brillo no volumen", risk_of=_risk) is None


def test_a_target_is_held_only_when_the_risk_of_what_acted_is_known() -> None:
    state = _state("pon el brillo al 40", ["system.settings.set"], _brightness_set(), "He puesto el brillo al 40.")
    assert state.already_holds("joder que te he dicho brillo no volumen") is None
    assert state.already_holds("joder que te he dicho brillo no volumen", risk_of=lambda operation: None) is None
    assert state.already_holds("joder que te he dicho brillo no volumen", risk_of=_risk) == dialogue.AlreadyHolds(
        "target", named="brillo", untouched="volumen"
    )


def test_the_turn_reads_the_catalog_risk_before_a_target_is_held() -> None:
    writer = _Writer("Ya está el brillo al 40; el volumen no lo toqué.")
    text = "joder que te he dicho brillo no volumen"
    read = _state("¿cuánto está el brillo?", ["system.settings.status"], _brightness_read(), "El brillo está al 40.")
    assert turn_followups._correction_already_held({"id": "t2", "text": text, "history": []}, read, writer, _risk) is None
    done = _state("pon el brillo al 40", ["system.settings.set"], _brightness_set(), "He puesto el brillo al 40.")
    result = turn_followups._correction_already_held({"id": "t2", "text": text, "history": []}, done, writer, _risk)
    assert result is not None and result["effectOperations"] == []
    # Encargo TZ-HOLD: the held target is said with its sentence, never drafted.
    assert result["reply"] == "Lo que te dije era de «brillo»; «volumen» no lo toqué." and writer.situations == []


def _ribbon_mission(lines: list[str], control_lines: list[int] | None) -> dict:
    # Bloqueante 1: a document editor where the click on «Modo de lectura» left the ribbon on screen and the mode
    # unchanged; every line is the label of a control (ComputerUseMission.ControlLines).
    screen: dict = {"title": "Documento1", "lines": lines}
    if control_lines is not None:
        screen["controlLines"] = control_lines
    return {
        "kind": "operation", "operation": "mission.computer.use", "polarity": "success", "verified": True,
        "succeeded": True,
        "observed": {
            "goal": "poner el modo de lectura", "application": "Editor", "reached": True,
            "satisfiedBy": "stepDone:input.visible.click:modo de lectura", "screen": screen,
        },
    }


RIBBON = ["Archivo Inicio Insertar Vista", "Modo de lectura", "Diseño de impresión", "Diseño web"]


@pytest.mark.parametrize("control_lines", [[0, 1, 2, 3], None])
def test_the_label_clicked_written_on_the_screen_proves_no_state(control_lines: list[int] | None) -> None:
    # Marked as a control's label, or from an excerpt that does not tell its labels apart: no line is the state.
    state = _state("ponlo en modo lectura", ["mission.computer.use"], _ribbon_mission(RIBBON, control_lines), "Listo.")
    assert state.already_holds("esa no es la de lectura, sigue en la normal") is None


def test_a_tab_label_written_on_a_dialog_proves_no_state() -> None:
    mission = _ribbon_mission(["General", "Avanzado", "Aceptar Cancelar"], [0, 1, 2])
    mission["observed"]["satisfiedBy"] = "stepDone:input.visible.click:avanzado"
    state = _state("ve a la pestaña avanzado", ["mission.computer.use"], mission, "Listo.")
    assert state.already_holds("esa no es la de avanzado, sigue en la general") is None


def test_the_same_lines_not_marked_as_labels_still_hold() -> None:
    # Counter-case: the same reading mode written as a line no control names (a status bar) is the state shown.
    state = _state("ponlo en modo lectura", ["mission.computer.use"], _ribbon_mission(RIBBON, [0, 2, 3]), "Listo.")
    assert state.already_holds("esa no es la de lectura, sigue en la normal") == dialogue.AlreadyHolds(
        "state", named="Modo de lectura"
    )


def test_the_calculator_lines_marked_as_labels_hold_nothing() -> None:
    # The same evidence lines, told apart as the navigation's labels, are no state shown.
    mission = _calculator_mission(["Calculadora", "Programador", "HEX"], [1])
    state = _state("ahora ponla en modo programador", ["mission.computer.use"], mission, "Listo.")
    assert state.already_holds("esa no es la de programador wey, sigue en la estandar, cambiala") is None


def test_the_writer_never_sees_which_lines_are_labels() -> None:
    from baxy_mind import cu_projection

    seen = cu_projection.project_seen(_calculator_mission(["Calculadora", "Programador"], [0])["observed"], "es")
    assert "controlLines" not in seen["screen"] and seen["screen"]["lines"] == ["Calculadora", "Programador"]


# --------------------------------------------------------------------------- revisión 3

GAMES_TOLD = "1. Outlast. 2. Amnesia. 3. Soma."
GAMES_SERIES = "Outlast, Amnesia y Soma son juegos de terror."
JOKES_TOLD = "¿Qué hace una abeja en el gimnasio? ¡Zum-ba!"
THREE_JOKES_TOLD = (
    "1. ¿Qué hace una abeja en el gimnasio? Zumba. 2. ¿Cuál es el café más peligroso? El ex-preso. "
    "3. ¿Qué le dice un techo a otro? Techo de menos."
)
STALE_COUNTS = (
    "no, te pedí 3 nomás y me tiraste una lista enorme",
    "no te pedi 3 po, me tiraste como 7, solo 3",
    "no, te pedí 3",
)


def _games_search() -> dict:
    return {
        "kind": "operation", "operation": "web.search", "polarity": "success", "verified": True, "succeeded": True,
        "observed": {"version": 1, "query": "juegos de terror", "count": 3, "results": []},
    }


def _conversation_turn(reply: str) -> dict:
    return {
        "type": "turn.result", "id": "t2", "kind": "conversation", "operation": None, "intentOperations": [],
        "effectOperations": [], "question": "", "reply": reply,
    }


def _games_then_jokes(games: str, jokes: str | None) -> dialogue.DialogueState:
    state = _state("busca 3 juegos de terror", ["web.search"], _games_search(), games)
    if jokes is None:
        # A conversation turn whose reply never reached the state (the shell publishes it without message.compose).
        state.expect("dame 3 chistes", [])
    else:
        send_offer._expect_decided_turn(state, _conversation_turn(jokes), {"text": "dame 3 chistes"})
    return state


@pytest.mark.parametrize("games", [GAMES_TOLD, GAMES_SERIES])
@pytest.mark.parametrize("text", STALE_COUNTS)
def test_a_final_of_a_request_before_counts_nothing(games: str, text: str) -> None:
    # Bloqueante de la revisión 3: T1 a verified search told three games, T2 «dame 3 chistes» answered in conversation,
    # T3 a count reproach: never the games again, as on the base.
    assert _games_then_jokes(games, None).already_holds(text) is None
    assert _games_then_jokes(games, JOKES_TOLD).already_holds(text) is None


@pytest.mark.parametrize("games", [GAMES_TOLD, GAMES_SERIES])
@pytest.mark.parametrize("text", STALE_COUNTS)
def test_the_correction_after_a_conversation_turn_never_tells_the_games_again(games: str, text: str) -> None:
    writer = _Writer("Son estos 3: Outlast, Amnesia y Soma.")
    history = [
        {"role": "user", "content": "busca 3 juegos de terror"},
        {"role": "assistant", "content": games},
        {"role": "user", "content": "dame 3 chistes"},
        {"role": "assistant", "content": JOKES_TOLD},
    ]
    for state in (_games_then_jokes(games, None), _games_then_jokes(games, JOKES_TOLD)):
        message = {"id": "t3", "text": text, "history": history}
        assert turn_followups._correction_already_held(message, state, writer) is None
    assert writer.situations == []


def test_a_conversation_turn_is_the_last_final_of_its_request() -> None:
    state = _games_then_jokes(GAMES_TOLD, THREE_JOKES_TOLD)
    assert state.last_final() == THREE_JOKES_TOLD
    text = "no, te pedí 3 nomás y me tiraste una lista enorme"
    assert state.already_holds(text) == dialogue.AlreadyHolds("count", count=3)
    writer = _Writer("Son estos 3 chistes: el de la abeja, el del café y el del techo.")
    history = [{"role": "user", "content": "dame 3 chistes"}, {"role": "assistant", "content": THREE_JOKES_TOLD}]
    result = turn_followups._correction_already_held({"id": "t3", "text": text, "history": history}, state, writer)
    assert result is not None and result["reply"] == writer.reply
    assert writer.situations[0]["alreadyHolds"]["previousReply"] == THREE_JOKES_TOLD


def test_t3_c17_count_told_in_a_live_conversation_turn_already_holds() -> None:
    # The live path of t3-c17: the four causes are a conversation turn's reply, never told through message.compose.
    state = dialogue.DialogueState()
    request = "dame 4 causas de la primera guerra mundial cortito pa la prueba"
    send_offer._expect_decided_turn(state, _conversation_turn(FOUR_CAUSES_TOLD), {"text": request})
    assert state.already_holds("no te pedi 4 po, me tiraste como 7, solo 4") == dialogue.AlreadyHolds("count", count=4)


def test_a_count_is_read_only_in_the_answer_the_person_saw() -> None:
    # The shell published something else than the final kept (a rejected reply, a route of its own): nothing is held.
    state = _state("dame 3 libros de cortazar", [], None, BOOKS_TOLD)
    text = "no, te pedí 3 libros"
    assert state.already_holds(text, shown="No pude responder a eso.") is None
    assert state.already_holds(text, shown=" ".join(BOOKS_TOLD.split(" "))) == dialogue.AlreadyHolds("count", count=3)


def test_an_operation_turn_leaves_the_final_to_message_compose() -> None:
    state = _state("busca 3 juegos de terror", ["web.search"], _games_search(), GAMES_TOLD)
    operation_turn = {**_conversation_turn(""), "kind": "action", "effectOperations": ["web.search"]}
    send_offer._expect_decided_turn(state, operation_turn, {"text": "busca 3 juegos de terror"})
    assert state.already_holds("no, te pedí 3") is None
