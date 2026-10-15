"""Estabilidad cu-v3 2026-10-08, redacción y finales (auditoría estab/caidas.md hallazgos 3-5, riesgos-fusion.md 7).

1. Tras fallar la redacción de un turno entendido, ni la recuperación ni el respaldo del composer preguntan con la
   frase de la persona («¿Qué quieres que haga con "en seguridad de windows decime cuándo…"?», v2-v3-61, entendido
   como followup): la clase entendida viaja (understoodAs) y el respaldo dice la causa corta. Contracaso: un turno que
   nadie entendió sigue preguntando con sus palabras (D59 §7).
2. El libro de actos respalda cada acto con la operación verificada que lo hizo (mapa verbo↔operación en
   data/act_claims.v1.json) y «paré a mitad» con el hecho de parada (v2-g1). Contracasos: sin esa operación, o sin
   parada observada, el acto sigue vetado.

Gemelos con los compose_audit reales."""

from __future__ import annotations

import json

import pytest

from baxy_mind import deterministic_finals
from baxy_mind import computer_use_finals
from baxy_mind.visible_defect import compose_visible_defect
from baxy_mind.semantic import dialogue
from baxy_mind import turn_recovery


def _verified(operation: str) -> dict:
    return {
        "kind": "operation", "operation": operation, "polarity": "success", "verified": True, "succeeded": True,
        "observed": {},
    }


# ---------------------------------------------------------------- 2. el libro de actos
TRUE_FINALS = [
    ("filesystem.trash.commit", "Moví el archivo a la papelera."),
    ("filesystem.trash.commit", "I moved the file to the recycle bin."),
    ("note.trash", "Moví la nota a la papelera."),
    ("memory.forget", "Borré ese recuerdo."),
    ("memory.forget", "Eliminé ese dato de mi memoria."),
    ("memory.forget", "I deleted that memory."),
    ("memory.correct", "Actualicé tu nombre."),
    ("calendar.event.create", "Agendé la reunión para mañana."),
    ("calendar.event.create", "I scheduled the meeting."),
    ("backup.create", "Creé el respaldo."),
    ("backup.create", "I created the backup."),
    ("notification.cancel.at", "Apagué la alarma de las 7."),
    ("notification.cancel.at", "I turned off the 7 o'clock alarm."),
]


@pytest.mark.parametrize(("operation", "reply"), TRUE_FINALS)
def test_a_true_final_is_backed_by_the_operation_that_did_it(operation, reply):
    assert computer_use_finals._claims_defect(reply, "status", _verified(operation)) == "", reply


# Contracasos: el mismo acto sin la operación que lo hace sigue vetado.
UNBACKED_FINALS = [
    ("audio.volume", "Moví el archivo a la papelera."),
    ("app.open", "Borré ese recuerdo."),
    ("app.open", "Agendé la reunión."),
    ("app.open", "Creé el respaldo."),
    ("audio.volume", "Apagué la alarma de las 7."),
    ("app.open", "Actualicé tu nombre."),
    ("memory.forget", "Agendé la reunión."),
]


@pytest.mark.parametrize(("operation", "reply"), UNBACKED_FINALS)
def test_an_act_no_verified_operation_did_is_still_refused(operation, reply):
    assert computer_use_finals._claims_defect(reply, "status", _verified(operation)) == "unbacked_act", reply


@pytest.mark.parametrize(
    ("operation", "reply"),
    [
        # Revisión r2, hallazgo 4: the declared lemmas are not widened by groups («cambiar» → configurar/poner,
        # «mover» → llevar/poner, «programar»/«anotar» → guardar/escribir, «guardar» → anotar).
        ("memory.correct", "Configuré el volumen al 50."),
        ("memory.correct", "Puse el brillo al máximo."),
        ("filesystem.trash.commit", "Llevé el archivo a Documentos."),
        ("filesystem.trash.commit", "Puse el archivo en Documentos."),
        ("note.trash", "Puse la nota en favoritos."),
        ("calendar.event.create", "Guardé el archivo."),
        ("calendar.event.create", "Escribí el correo."),
        ("backup.create", "Anoté tu cumpleaños."),
    ],
)
def test_r2_a_declared_act_does_not_open_its_whole_group(operation, reply):
    assert computer_use_finals._claims_defect(reply, "status", _verified(operation)) == "unbacked_act", reply


@pytest.mark.parametrize(
    ("operation", "reply"),
    [
        ("filesystem.trash.commit", "Envié el archivo a la papelera."),
        ("note.trash", "Mandé la nota a la papelera."),
        ("notification.cancel.at", "Desactivé el recordatorio."),
        ("memory.correct", "Cambié tu nombre a Emma."),
        ("calendar.event.create", "Creé el evento."),
    ],
)
def test_r2_the_exact_acts_still_back_their_true_finals(operation, reply):
    assert computer_use_finals._claims_defect(reply, "status", _verified(operation)) == "", reply


def test_an_unverified_operation_backs_nothing_new():
    # A single failure is told as a failure (not judged by the book), and its acts are never backed as done.
    failed = {**_verified("memory.forget"), "verified": False, "succeeded": False, "polarity": "failure"}
    assert computer_use_finals._act_ledger(failed) is None


# v2-g1/compose_audit.jsonl, trace t1 (first, retry, third: unbacked_act → no_response;deterministic_fallback).
G1_DRAFT = (
    "No pude ir a la biblioteca porque empezaste a usar el PC mientras yo lo hacía, así que paré a mitad para no "
    "estorbarte."
)


def _g1_situation(stopped: bool = True) -> dict:
    observed = {
        "goal": "ir a biblioteca; luego buscar Cuphead", "application": "Steam", "reached": False, "stepCount": 1,
        "steps": [{
            "step": 1, "operation": "input.visible.click", "source": "model", "subgoal": 0, "label": "biblioteca",
            "ok": False, "error": "input_user_interrupted", "effectUncertain": True,
        }],
        "window": {"title": "Steam", "process": "steamwebhelper", "requested": True, "foreground": False},
        "joined": False,
        "subgoals": [
            {"goal": "ir a biblioteca", "application": "Steam", "reached": False, "stepCount": 1},
            {"goal": "buscar Cuphead", "application": "Steam", "reached": False, "stepCount": 0},
        ],
        **({"stoppedBy": "input_user_interrupted"} if stopped else {}),
    }
    return {
        "kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
        "reason": {
            "kind": "operation", "operation": "mission.computer.use", "polarity": "failure", "verified": False,
            "succeeded": False, "error": "input_user_interrupted", "observed": observed,
        },
    }


def test_g1_the_stop_the_mission_observed_is_not_an_act():
    assert computer_use_finals._claims_defect(G1_DRAFT, "error", _g1_situation()) == ""
    assert computer_use_finals._claims_defect("Me detuve a mitad porque empezaste a usar el PC.", "error", _g1_situation()) == ""


def test_g1_without_an_observed_stop_the_stop_is_still_an_act():
    assert computer_use_finals._claims_defect(G1_DRAFT, "error", _g1_situation(stopped=False)) == "unbacked_act"


def test_g1_a_stop_does_not_back_other_acts():
    assert computer_use_finals._claims_defect(
        "Paré a mitad y cerré Steam para no estorbarte.", "error", _g1_situation(),
    ) == "unbacked_act"


@pytest.mark.parametrize("stopped_by", ["input_user_interrupted", "computer_use_place_not_found", "window_covered"])
@pytest.mark.parametrize(
    "reply",
    [
        "Paré la música en Spotify.",
        "Detuve la descarga del juego.",
        "Paré el temporizador.",
        "I stopped the music on Spotify.",
        "La paré a mitad.",
        "He parado la música.",
        "He parado a mitad y cerrado Steam.",
    ],
)
def test_r2_an_observed_stop_never_backs_stopping_a_thing(stopped_by, reply):
    # Revisión r2, hallazgo 1: any stop cause backed «parar»/«detener» for any object over a failed mission.
    situation = _g1_situation()
    situation["reason"]["observed"]["stoppedBy"] = stopped_by
    assert computer_use_finals._claims_defect(reply, "error", situation) == "unbacked_act", reply


@pytest.mark.parametrize(
    "reply",
    [G1_DRAFT, "Me detuve a mitad porque empezaste a usar el PC.", "I stopped halfway because you were using the PC.",
     "Paré."],
)
def test_r2_the_own_stop_still_passes_whatever_the_stop_cause(reply):
    situation = _g1_situation()
    situation["reason"]["observed"]["stoppedBy"] = "computer_use_place_not_found"
    assert computer_use_finals._claims_defect(reply, "error", situation) == "", reply


def test_g1_twin_through_the_whole_veto():
    facts = {"situation": json.dumps(_g1_situation(), ensure_ascii=False)}
    assert compose_visible_defect(G1_DRAFT, "error", "en steam anda a la biblioteca y busca cuphead", facts) == ""


# ---------------------------------------------------------------- 1. el respaldo no repite la orden como pregunta
# v2-v3-61/compose_audit.jsonl líneas 10 y 26 (deterministic_fallback) y turn_audit.jsonl (conversation_wording ×2,
# shaped_presentation, recovery stage conversation_kind «followup»).
V3_61 = "en seguridad de windows decime cuándo fue el último examen de virus"
V3_61_QUESTION = '¿Qué quieres que haga con "en seguridad de windows decime cuándo…"?'


def test_v3_61_the_words_floor_is_what_was_published():
    assert dialogue.words_floor_question(V3_61, "es") == V3_61_QUESTION


def test_v3_61_an_understood_turn_failure_says_its_short_cause():
    situation = {
        "kind": "failure", "polarity": "failure", "cause": "turn_runtime_failure", "operationAttempted": False,
        "retryable": True, "understoodAs": "followup",
    }
    said = deterministic_finals._not_understood_floor(situation, V3_61, "es")
    assert said == "No logré armar una respuesta fiable a eso."
    assert "windows" not in said.casefold() and "?" not in said
    assert deterministic_finals._not_understood_floor(situation, "on windows security tell me when", "en") == (
        "I couldn't put together a reliable answer to that."
    )


def test_v3_61_an_understood_turn_is_not_asked_back():
    situation = {
        "kind": "clarification", "cause": "ambiguous_request", "polarity": "pending", "understoodAs": "followup",
    }
    assert deterministic_finals._not_understood_floor(situation, V3_61, "es") == ""


def test_a_turn_nobody_understood_still_asks_with_their_words():
    # D59 §7 contracaso: with no understood kind the floor is the person's own words.
    for situation in (
        {"kind": "failure", "cause": "turn_runtime_failure", "operationAttempted": False, "retryable": True},
        {"kind": "clarification", "cause": "ambiguous_request", "polarity": "pending"},
    ):
        assert deterministic_finals._not_understood_floor(situation, V3_61, "es") == V3_61_QUESTION


class _ComposerFloor:
    """The model writes nothing usable: every composition ends in the composer's own floor (v3-61)."""

    def __init__(self) -> None:  # noqa: D107
        self.situations: list[dict] = []

    def clarify_after_turn_failure(self, *_args: object, **_kwargs: object) -> str:
        raise TimeoutError

    def compose_user_message(self, text: str, intent: str, facts: dict) -> str:
        situation = json.loads(facts["situation"])
        self.situations.append(situation)
        if intent == "conversation":
            return ""
        return deterministic_finals._not_understood_floor(situation, text, "es")


def test_v3_61_twin_the_recovery_of_understood_talk_never_asks_the_words_back():
    composer = _ComposerFloor()
    result = turn_recovery._recover_failed_turn(
        {"id": "v3-61", "text": V3_61, "history": []}, composer,
        failure_kinds=("conversation_wording", "conversation_wording"),
        conversation_kinds=("followup", "followup"),
    )
    assert result["question"] != V3_61_QUESTION and result["kind"] != "clarify"
    assert result["conversationKind"] == "followup"
    assert any(item.get("understoodAs") == "followup" for item in composer.situations)


@pytest.mark.parametrize(
    ("text", "failure_kinds", "conversation_kinds", "understood_as"),
    [
        # Revisión r2, hallazgo 3: the kind sent to the composer and the one the App reads are the same, also when the
        # attempts decided mixed kinds, none, or content was asked and the runtime failed (uso real t1).
        (V3_61, ("conversation_wording",) * 2, ("followup", "followup"), "followup"),
        (V3_61, ("conversation_wording",) * 2, ("followup", "knowledge"), "conversation"),
        (V3_61, ("conversation_wording",) * 2, (), "conversation"),
        ("dame 3 ideas de nombre para mi gata negra", ("runtime", "runtime"), (), "conversation"),
    ],
)
def test_r2_understood_talk_travels_to_the_app_whatever_its_kinds(text, failure_kinds, conversation_kinds, understood_as):
    composer = _ComposerFloor()
    result = turn_recovery._recover_failed_turn(
        {"id": "r2", "text": text, "history": []}, composer,
        failure_kinds=failure_kinds, conversation_kinds=conversation_kinds,
    )
    assert result["kind"] == "conversation" and not result["reply"] and not result["question"]
    assert result["understoodAs"] == understood_as
    assert any(item.get("understoodAs") == understood_as for item in composer.situations)
    # The App's failure then carries it: its floor says the short cause, never the words asked back.
    failure = {
        "kind": "failure", "cause": "turn_runtime_failure", "operationAttempted": False, "retryable": True,
        "understoodAs": result["understoodAs"],
    }
    said = deterministic_finals._not_understood_floor(failure, text, "es")
    assert said == "No logré armar una respuesta fiable a eso."


def test_r2_mixed_kinds_still_publish_no_conversation_kind():
    # M104 contracaso: understoodAs travels, conversationKind stays None when the attempts disagreed.
    result = turn_recovery._recover_failed_turn(
        {"id": "r2", "text": V3_61, "history": []}, _ComposerFloor(),
        failure_kinds=("conversation_wording",) * 2, conversation_kinds=("followup", "knowledge"),
    )
    assert result["conversationKind"] is None and result["understoodAs"] == "conversation"


def test_r2_the_apps_own_clarification_still_asks_with_their_words():
    # Revisión r2, hallazgo 2 (cien-41 027 «open that»): the App's clarification carries no understoodAs and asks.
    situation = {"kind": "clarification", "cause": "ambiguous_request", "polarity": "pending"}
    assert deterministic_finals._not_understood_floor(situation, "open that", "en") == 'What should I do with "open that"?'


def test_a_recovery_nobody_understood_still_asks_with_their_words():
    composer = _ComposerFloor()
    result = turn_recovery._recover_failed_turn(
        {"id": "v3-61", "text": V3_61, "history": []}, composer, failure_kinds=("runtime", "runtime"),
    )
    assert result["kind"] == "clarify" and result["question"] == V3_61_QUESTION
    assert "understoodAs" not in result
