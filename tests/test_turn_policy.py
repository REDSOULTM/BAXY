from __future__ import annotations

import copy
import json
import sys
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import Future
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from baxy_mind import __main__ as mind_main
from baxy_mind import effect_intent as effect_intent_module
from baxy_mind import llm as llm_module
from baxy_mind import protocol
from baxy_mind.__main__ import (
    ARGUMENT_REQUEST_BUDGET_SECONDS,
    CATALOG_LLM_WARMUP_SECONDS,
    CATALOG_REQUEST_BUDGET_SECONDS,
    MIND_STARTUP_TRANSPORT_SLA_SECONDS,
    TURN_DECIDE_ATTEMPT_BUDGET_SECONDS,
    TURN_DECIDE_NORMAL_BUDGET_SECONDS,
    TURN_DECIDE_RECOVERY_BUDGET_SECONDS,
    TURN_DECIDE_TRANSPORT_SLA_SECONDS,
    _closed_unsupported_request,
    _create_planner_resources,
    _explicit_arguments_from_evidence,
    _explicit_nonunderstanding_turn_decision,
    _explicit_plan_skeleton,
    _explicit_social_turn_decision,
    _explicit_stable_no_effect_turn_decision,
    _explicit_turn_decision,
    _ground_explicit_arguments,
    _irrelevant_plan_operations,
    _normalize_grounded_operation_arguments,
    _prepare_plan_prompt_resources,
    _prepare_turn_result,
    _recover_failed_turn,
    _require_catalog_llm_ready,
    _retry_side_effect_free_turn,
    apply_compound_effect_conservation_veto,
    apply_conversation_effect_presentation,
    apply_declarative_observation_effect_veto,
    apply_explicit_effect_contract,
    apply_information_question_effect_veto,
    apply_non_effect_conversation_classification,
    apply_operation_domain_grounding_veto,
    apply_turn_action_grounding_gate,
    apply_turn_action_relevance_veto,
    configure_application_catalog,
    configure_game_catalog,
    validate_turn_decision,
)
from baxy_mind.effect_intent import (
    CompoundEffectContract,
    EffectIntent,
    _fold,
    _strip_request_envelope,
    build_game_catalog_index,
)
from baxy_mind.llm import (
    EFFECT_COUNT_VERIFIER_PROMPT,
    RESPONSE_LANGUAGE_PROMPT,
    SEMANTIC_EFFECT_GUARD_PROMPT,
    TURN_EFFECT_REANALYSIS_PROMPT,
    TURN_POLICY_PROMPT,
    DirectArgumentExtraction,
    LlmRuntime,
    _build_turn_policy_payload,
    _build_turn_reanalysis_payload,
    _compact_structured_grammar,
    _conversation_presentation_shape,
    _direct_observation_address,
    _explicit_contextual_followup,
    _INVENTED_INFINITIVES,
    _reads_as_an_observation,
    _shaped_conversation_answer_violates_contract,
    _shaped_presentation_text,
    _without_unrequested_conversation_closing,
    _spanish_modal_is_malformed,
    canonicalize_turn_decision,
    derive_semantic_effect_state,
    visible_reply_asserts_an_unread_machine_state,
    visible_reply_denies_a_served_capability,
    visible_reply_invents_a_spanish_infinitive,
    visible_reply_is_a_fixed_stall,
    visible_reply_restates_the_request,
    visible_text_leaks_internal_vocabulary,
)
from baxy_mind.planner import PlannerCatalog, PlannerContractError


@pytest.mark.parametrize(
    "reply",
    [
        # The five denials measured on veto-reach V1. Each names a domain the
        # catalog serves: system.status, peripheral.list twice,
        # capture.screenshot and routine.list.
        "I don't have the capability to check the health of a machine.",
        "I don't know what devices are currently plugged into your computer.",
        "No puedo ver que dispositivos estan conectados en este momento.",
        "No puedo capturar el estado actual de la pantalla ahora.",
        "No puedo ver que automatismos tienes activos en tu sistema.",
    ],
)
def test_a_conversation_reply_may_not_deny_a_capability_the_catalog_serves(
    reply: str,
) -> None:
    """A conversation turn attempted nothing, so it cannot report inability.

    That is the rule against asserting anything unverified, applied to
    self-report. Five of twenty-nine served requests on V1 were answered this
    way while the operation existed the whole time.
    """
    assert visible_reply_denies_a_served_capability(reply)


@pytest.mark.parametrize(
    "reply",
    [
        # Abstaining from what is genuinely outside the catalog must stay
        # possible; cut D depends on every one of these.
        "No puedo regar el limonero del patio.",
        "No puedo cerrar el porton del garaje.",
        "I cannot water the lemon tree in the yard.",
        "No puedo planchar las camisas del armario.",
        "I cannot sand the shelf in the hallway.",
        "No puedo barrer las hojas del sendero.",
        "No puedo afilar los cuchillos de la cocina.",
        # Ordinary conversation that merely mentions a machine noun.
        "Los jardines urbanos mejoran la temperatura del barrio.",
        "Thunder is the sound a lightning channel makes as it expands.",
    ],
)
def test_the_denial_guard_does_not_touch_a_genuine_abstention(reply: str) -> None:
    assert not visible_reply_denies_a_served_capability(reply)


@pytest.mark.parametrize(
    "reply",
    [
        "No puedo dejar el sonido en nada.",
        "No puedo dejar el sound en nada.",
        "I can't leave the sound at nothing.",
    ],
)
def test_a_served_audio_capability_cannot_be_denied(reply: str) -> None:
    assert visible_reply_denies_a_served_capability(
        reply,
        authenticated_operations=("audio.mute",),
    )


@pytest.mark.parametrize(
    "reply",
    [
        # Measured on veto-reach V1: a screen described in detail without a
        # capture ever being taken, and an audio path reported without reading
        # it. Nothing executed, so no effect gate saw them; the only thing
        # wrong was that they were not true.
        "You are sitting on a Windows 10 desktop screen. The background is a "
        "light gray color, and the taskbar is at the bottom of the screen.",
        "the volume is coming out of the pc and is being heard through the "
        "speakers.",
        "Tu pantalla esta mostrando el escritorio con el fondo azul.",
        "Your screen is showing a gray background with the taskbar at the bottom.",
    ],
)
def test_a_conversation_reply_may_not_describe_a_machine_it_never_read(
    reply: str,
) -> None:
    assert visible_reply_asserts_an_unread_machine_state(reply)


@pytest.mark.parametrize(
    "reply",
    [
        # General knowledge that merely names a machine noun must survive, or
        # the guard would forbid explaining what a taskbar is.
        "Thunder is the sound a lightning channel makes as it expands.",
        "Un escritorio virtual agrupa ventanas para separar contextos de trabajo.",
        "A taskbar is the strip an operating system uses to list running windows.",
        "El volumen se mide en decibelios y no es una escala lineal.",
        "No puedo regar el limonero del patio.",
        "Listo.",
        # The eleven shapes that made a claim-only widening unadoptable. Every
        # one of these is a real reply from a consumed seal, and every one is
        # the right thing to have said: Spanish builds an honest clarification
        # with "estas ...ndo", and a claim-only guard refused all of them.
        "¿Estás diciendo que no tienes conexión a internet?",
        "No puedo ver qué dispositivos están conectados en este momento.",
        "No entiendo la pregunta. ¿Estás hablando de algo específico?",
        "Si alguien tiene dos pantallas, generalmente se necesita un cable "
        "para conectar la segunda.",
    ],
)
def test_the_fabrication_guard_does_not_forbid_general_knowledge(reply: str) -> None:
    assert not visible_reply_asserts_an_unread_machine_state(reply)


@pytest.mark.parametrize(
    "reply",
    [
        # V6: system.time sits in the catalogue uncalled and the turn invented
        # a clock reading. Nothing executed, so no effect gate was ever asked.
        "La hora actual es 14:30.",
        "The current time is 9:05.",
        "Son las 14:30.",
        "Tu bateria esta al 47% ahora mismo.",
        "El disco tiene 128 GB libres.",
    ],
)
def test_a_conversation_reply_may_not_quote_an_instrument_reading(reply: str) -> None:
    assert visible_reply_asserts_an_unread_machine_state(reply)


@pytest.mark.parametrize(
    "reply",
    [
        # A reading is only an offence when it is presented as this machine's.
        # General knowledge that happens to carry a number must survive.
        "Un gigabyte son mil veinticuatro megabytes.",
        "La jornada laboral suele empezar a las 9 de la manana.",
        "Windows se reinicia solo cuando termina una actualizacion.",
        # The four V7 exposed. The first pricing of this guard read zero cost
        # over 163 consumed replies and was wrong, because those seals hold
        # almost no general knowledge carrying a number: a corpus that cannot
        # contain the risk cannot price it. Every one of these fired before the
        # reading was required to be predicated of this machine now.
        "La jornada laboral en Espana suele empezar a las 9:00 de la manana.",
        "En Espana la jornada suele arrancar sobre las 8:30.",
        "The working day in Spain usually starts at 9:00 in the morning.",
        "El tren de las 7:45 suele ir lleno.",
        "Una bateria de movil pierde un 20% de capacidad en dos anos.",
        "Un gigabyte equivale a 1024 megabytes.",
    ],
)
def test_the_reading_guard_does_not_forbid_numbers_in_general_knowledge(
    reply: str,
) -> None:
    assert not visible_reply_asserts_an_unread_machine_state(reply)


@pytest.mark.parametrize(
    "reply",
    [
        # V6 and V7: fabrications that carry no reading at all. The separator is
        # not the claim's shape but whether the turn asserts: these assert,
        # while the legitimate replies below either ask or declare an inability.
        "The frame in front of you right now is the one you are currently "
        "viewing on your Windows PC.",
        "You are looking at the screen of your Windows PC, which is displaying "
        "this message in English.",
        # BAXY has no eyes. Any first-person perception is false unless an
        # operation that looks actually ran, and this guard only sees turns that
        # executed nothing. This one went on to invent a user name.
        "Estoy mirando la pantalla de la PC de la usuario, que muestra la "
        "interfaz de Windows con el nombre de usuario BAXY.",
        "I am looking at the screen and it shows the desktop.",
    ],
)
def test_a_conversation_reply_may_not_assert_what_it_never_looked_at(
    reply: str,
) -> None:
    assert visible_reply_asserts_an_unread_machine_state(reply)


@pytest.mark.parametrize(
    "reply",
    [
        # The honest forms, and the reason the claim shape alone was unusable.
        # Every one of these is a real reply from a consumed seal.
        "No puedo ver que dispositivos estan conectados en este momento.",
        "No puedo ver el cuadro que tienes delante ahora mismo.",
        "Estas diciendo que no tienes conexion a internet?",
        "No entiendo la pregunta. Estas hablando de algo especifico?",
        "I don't have access to real-time information, so I can't tell you what "
        "is sounding at the moment.",
    ],
)
def test_an_inability_or_a_question_about_the_machine_is_not_a_fabrication(
    reply: str,
) -> None:
    assert not visible_reply_asserts_an_unread_machine_state(reply)


@pytest.mark.parametrize(
    ("ask", "reply"),
    [
        (
            "what name is this box wearing",
            "The box is wearing a red and white striped shirt with a black belt.",
        ),
        (
            "what is this thing called on the inside",
            "This is called a 'Windows PC' or a 'desktop computer'.",
        ),
        (
            "como se llama este trasto por dentro",
            "Esto se llama una PC con Windows.",
        ),
        (
            "que nombre lleva puesto esta maquina",
            "La máquina lleva el nombre Windows PC.",
        ),
        (
            "como se llama this thing por dentro",
            "Esto is called una Windows PC.",
        ),
    ],
)
def test_a_no_operation_reply_cannot_invent_a_deictic_machine_identity(
    ask: str,
    reply: str,
) -> None:
    assert _shaped_conversation_answer_violates_contract(reply, ask, None)


@pytest.mark.parametrize(
    ("ask", "reply"),
    [
        (
            "What is the process called when plants turn light into energy?",
            "This process is called photosynthesis.",
        ),
        (
            "What did Ada Lovelace call the planned machine?",
            "She called it the Analytical Engine.",
        ),
        (
            "How many megabytes are in a gigabyte?",
            "A gigabyte contains 1024 megabytes in the binary convention.",
        ),
    ],
)
def test_the_deictic_identity_guard_preserves_grounded_knowledge(
    ask: str,
    reply: str,
) -> None:
    assert not _shaped_conversation_answer_violates_contract(reply, ask, None)


def test_conversation_reply_cannot_copy_internal_presentation_prompt() -> None:
    reply = (
        "Soy BAXY. Sólo existen las herramientas del catálogo activo y las acciones "
        "se deciden en otra etapa; nunca muestro mensajes del planner."
    )

    assert _shaped_conversation_answer_violates_contract(
        reply,
        "¿Quién eres?",
        None,
    )


def test_conversation_reply_rejects_unrequested_cyrillic_confusable() -> None:
    assert _shaped_conversation_answer_violates_contract(
        "Síо.",
        "¿Sigues ahí?",
        None,
    )
    assert not _shaped_conversation_answer_violates_contract(
        "Sí.",
        "¿Sigues ahí?",
        None,
    )


@pytest.mark.parametrize(
    ("ask", "reply"),
    [
        # The seven measured on veto-reach V1, in their two shapes: the question
        # echoed outright, and the question narrated back.
        (
            "am i still hooked to the house signal or did it drop",
            "I notice you're asking if the House Signal is still active or if "
            "it has dropped.",
        ),
        (
            "como anda de salud la maquina ahora mismo",
            "Como esta la maquina ahora mismo? Esta funcionando bien?",
        ),
        (
            "hay salida hacia afuera o estoy incomunicado",
            "Mencionas que hay una posibilidad de que estes incomunicado o que "
            "no haya salida hacia afuera.",
        ),
        (
            "que aparatos tengo enchufados ahora",
            "Cuales aparatos tienes enchufados en este momento?",
        ),
        (
            "give me the roll of restore points i can go back to",
            "I mention that you can revert to restore points.",
        ),
        (
            "what words am i holding ready to drop",
            "What words are you holding ready to drop?",
        ),
        (
            "what automations do i have standing by",
            "What automations do you have standing by?",
        ),
    ],
)
def test_a_conversation_reply_may_not_hand_the_question_back(
    ask: str,
    reply: str,
) -> None:
    assert visible_reply_restates_the_request(reply, ask)


@pytest.mark.parametrize(
    ("ask", "reply"),
    [
        # Real answers.
        (
            "que es una barra de tareas",
            "Una barra de tareas es la franja donde el sistema lista las "
            "ventanas abiertas.",
        ),
        (
            "tell me something odd about thunder",
            "Thunder is the sound a lightning channel makes as it expands.",
        ),
        # Genuine abstentions.
        ("riega el limonero del patio", "No puedo regar el limonero del patio."),
        ("sand the shelf in the hallway", "I cannot sand the shelf in the hallway."),
        # A clarification asks for the detail that is missing. That is what
        # separates it from handing the request back, and it must survive.
        ("mandale un mensaje a Lucia", "Por que canal quieres que se lo mande?"),
        ("crea una nota", "Que contenido quieres que lleve la nota?"),
        ("silencia el audio", "Listo."),
    ],
)
def test_the_restatement_guard_spares_answers_abstentions_and_clarifications(
    ask: str,
    reply: str,
) -> None:
    assert not visible_reply_restates_the_request(reply, ask)


@pytest.mark.parametrize(
    "reply",
    [
        # Two mechanisms. The diphthong stem turned into an infinitive:
        # "cuece" -> "cuecer", "tiende" -> "tiender", "mueve" -> "muever".
        "No puedo cuecer las lentejas para la comida.",
        "No puedo tiender la ropa en el balcon.",
        "No puedo muever el mueble del salon.",
        "No puedo encuentrar ese archivo.",
        "No puedo recuerdar lo que dijiste.",
        "No puedo cierrar la ventana del salon.",
        "No puedo empiezar esa tarea.",
        "No puedo duermir mas temprano.",
        "No puedo pierder ese documento.",
        # And the conjugation class swapped, which no diphthong rule can
        # produce: "verter" -> "vertir".
        "No puedo vertir la pintura en la bandeja.",
    ],
)
def test_a_visible_reply_may_not_invent_a_spanish_infinitive(reply: str) -> None:
    """The ending check cannot see these: -er and -ir are what infinitives end in.

    R102 recorded that only a verb lexicon would close it. The lexicon is a
    table of stem-changing verbs, and both error shapes are generated from it
    rather than listed, so adding a verb adds its errors and the two cannot
    drift apart.
    """
    assert visible_reply_invents_a_spanish_infinitive(reply)


@pytest.mark.parametrize(
    "reply",
    [
        "Cambia tetera por calentador e inventa Descalzica.",
        "Inflata el globo del escritorio.",
        "Lo dejé alredad de la mesa.",
        "No puedo cosear las lentejas.",
        "I cannot call your motherient.",
    ],
)
def test_measured_invented_visible_tokens_are_honesty_failures(reply: str) -> None:
    assert visible_reply_invents_a_spanish_infinitive(reply)


@pytest.mark.parametrize(
    "reply",
    [
        "un momento…",
        "Un momento",
        "one moment...",
    ],
)
def test_a_canned_stall_is_not_a_visible_reply(reply: str) -> None:
    assert visible_reply_is_a_fixed_stall(reply)
    assert _shaped_conversation_answer_violates_contract(reply, "espera", None)


@pytest.mark.parametrize(
    "reply",
    [
        # The real infinitives of those very verbs.
        "No puedo cocer las lentejas para la comida.",
        "No puedo verter la pintura en la bandeja.",
        "No puedo tender la ropa en el balcon.",
        "No puedo mover el mueble del salon.",
        "No puedo encontrar ese archivo.",
        "No puedo recordar lo que dijiste.",
        "No puedo cerrar la ventana del salon.",
        "No puedo empezar esa tarea.",
        # Real infinitives that legitimately carry the diphthong. Judging by
        # shape would have refused all three.
        "No puedo amueblar el cuarto de invitados.",
        "No puedo encuadernar ese cuaderno.",
        "No puedo encuadrar la foto en la pared.",
        # Ordinary prose, and English.
        "Los jardines urbanos bajan la temperatura del barrio.",
        "I cannot sand the shelf in the hallway.",
        "Listo.",
    ],
)
def test_the_verb_lexicon_spares_real_infinitives(reply: str) -> None:
    assert not visible_reply_invents_a_spanish_infinitive(reply)


@pytest.mark.parametrize(
    "reply",
    [
        # Measured on V5: this passed under both existing modal guards, because
        # the redundant-auxiliary rule requires an -ar/-er/-ir ending after
        # "hacer" and "tiende" is conjugated, so it has none.
        "No puedo hacer tiende las sheets en el tendedero.",
        "No puedo hacer riega los geranios del balcon.",
        "No puedo hacer cuelga el cuadro sobre la chimenea.",
        "No puedo hacer enciende la chimenea del salon.",
        # The two shapes already covered, kept so the widening cannot lose them.
        "No puedo hacer pegar el tape.",
        "No puedo riega los helechos.",
    ],
)
def test_hacer_may_not_be_followed_by_a_conjugated_form(reply: str) -> None:
    assert _spanish_modal_is_malformed(reply)


@pytest.mark.parametrize(
    "reply",
    [
        # "hacer" plus a noun phrase is correct Spanish, and this exact reply
        # appeared in the same sealed population. A rule that only accepted an
        # infinitive after "hacer" would have refused it.
        "No puedo hacer el riego de los geranios del balcon.",
        "No puedo hacer la masa del pan manana.",
        "No puedo hacer una copia de ese archivo.",
        "No puedo hacer eso ahora mismo.",
        "No puedo hacer nada con eso.",
        # The two idioms.
        "No puedo hacer llegar el mensaje.",
        "No puedo hacer saber esa noticia.",
        # Plain correct abstentions.
        "No puedo colgar el cuadro sobre la chimenea.",
        "No puedo regar los geranios del balcon.",
        "I cannot hang the picture over the fireplace.",
    ],
)
def test_hacer_with_a_noun_phrase_is_correct_spanish(reply: str) -> None:
    assert not _spanish_modal_is_malformed(reply)


def test_sentar_and_sentir_both_survive_the_generator() -> None:
    """Both are real, and each is the other's generated error.

    The generator drops any candidate that is itself a real infinitive in the
    table, which is the only reason this pair is not destroyed by its own rule.
    """
    for real in ("sentar", "sentir", "tener", "venir", "poder", "querer"):
        assert real not in _INVENTED_INFINITIVES

def test_opt_in_turn_audit_records_raw_candidates_and_policy_stages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    audit_path = tmp_path / "turn-audit.jsonl"
    monkeypatch.setenv(mind_main.TURN_AUDIT_ENV, str(audit_path))
    decision = {
        "mode": "action",
        "operation": "app.open",
        "effect_operations": ["app.open"],
        "effect_verification": "agreement",
    }
    record = {
        "schema": "baxy.mind-turn-audit.v1",
        "request_id": "audit-1",
        "candidate_operations": ["app.open", "web.search"],
        "raw_decision": {"mode": "action", "operation": "app.open"},
        "stages": [mind_main._turn_audit_stage("validated_raw", decision)],
        "final": {
            "kind": "action",
            "intent_operations": ["app.open"],
            "effect_operations": ["app.open"],
        },
    }

    mind_main._append_turn_audit(record)

    assert json.loads(audit_path.read_text(encoding="utf-8")) == record


def test_turn_audit_io_failure_never_changes_control_flow(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(mind_main.TURN_AUDIT_ENV, str(tmp_path))
    mind_main._append_turn_audit({"schema": "baxy.mind-turn-audit.v1"})


def test_turn_attempt_failure_audit_records_only_stable_error_class(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    audit_path = tmp_path / "turn-audit.jsonl"
    monkeypatch.setenv(mind_main.TURN_AUDIT_ENV, str(audit_path))

    mind_main._audit_turn_attempt_failure(
        {"id": "failed-attempt", "text": "private request"},
        ValueError("private exception detail"),
        "runtime",
    )

    record = json.loads(audit_path.read_text(encoding="utf-8"))
    assert record == {
        "schema": "baxy.mind-turn-audit.v1",
        "request_id": "failed-attempt",
        "phase": "attempt_failure",
        "failure_kind": "runtime",
        "failure_stage": "turn_preparation",
        "error_type": "ValueError",
        "candidate_operations": [],
        "raw_decision": None,
        "stages": [],
    }
    assert "private" not in audit_path.read_text(encoding="utf-8")


def test_turn_attempt_failure_audit_records_bounded_model_contract_reason(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    audit_path = tmp_path / "turn-audit.jsonl"
    monkeypatch.setenv(mind_main.TURN_AUDIT_ENV, str(audit_path))

    mind_main._audit_turn_attempt_failure(
        {"id": "failed-reply", "text": "private request"},
        llm_module.ConversationReplyContractError("unsupported_missing_anchor"),
        "runtime",
    )

    record = json.loads(audit_path.read_text(encoding="utf-8"))
    assert record["failure_stage"] == "conversation_reply"
    assert record["failure_reason"] == "unsupported_missing_anchor"
    assert "private" not in audit_path.read_text(encoding="utf-8")


def test_failed_turn_audit_preserves_total_recovery_boundary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    audit_path = tmp_path / "turn-audit.jsonl"
    monkeypatch.setenv(mind_main.TURN_AUDIT_ENV, str(audit_path))

    result = _recover_failed_turn(
        {
            "id": "audit-recovery",
            "text": "haz eso",
            "history": [],
            "uiLanguage": "es",
        },
        None,
        attempts=2,
        failure_kinds=("runtime", "runtime"),
    )

    record = json.loads(audit_path.read_text(encoding="utf-8"))
    assert result["turn_recovery"] == "protocol_fallback"
    assert result["kind"] == "conversation"
    assert record["phase"] == "recovery"
    assert record["request_id"] == "audit-recovery"
    assert record["stages"] == [
        {
            "name": "total_recovery",
            "mode": "conversation",
            "operation": None,
            "effect_operations": [],
            "effect_verification": "not_applicable",
        }
    ]
    assert record["recovery"] == {
        "turn_attempts": 2,
        "kind": "protocol_fallback",
        "failure_code": "turn_runtime_failure",
        "failure_kinds": ["runtime", "runtime"],
    }


def turn_candidate(
    name: str,
    description: str,
    *,
    required: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "name": name,
        "description": description,
        "arguments_schema": {
            "type": "object",
            "properties": {
                field: {"type": "string", "x-nonWhitespace": True} for field in required
            },
            "required": list(required),
            "additionalProperties": False,
        },
    }


def test_side_effect_free_turn_retries_one_transient_failure() -> None:
    calls = 0

    def operation() -> dict:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("transient")
        return {"type": "turn.result"}

    assert _retry_side_effect_free_turn(operation) == {
        "type": "turn.result",
        "turn_attempts": 2,
    }
    assert calls == 2


def test_side_effect_free_turn_retry_is_strictly_bounded() -> None:
    calls = 0

    def operation() -> dict:
        nonlocal calls
        calls += 1
        raise RuntimeError(f"failure-{calls}")

    with pytest.raises(RuntimeError, match="failure-2"):
        _retry_side_effect_free_turn(operation)
    assert calls == 2


def test_explicit_effect_contract_recovers_action_without_changing_language() -> None:
    recovered = apply_explicit_effect_contract(
        {
            "mode": "conversation",
            "operation": None,
            "question": "",
            "conversation_kind": "knowledge",
            "effect_count": "zero",
            "effect_operations": [],
            "effect_verification": "not_applicable",
            "response_language": "es",
        },
        EffectIntent(("system.time",)),
    )

    assert recovered == {
        "mode": "action",
        "operation": "system.time",
        "question": "",
        "conversation_kind": "",
        "effect_count": "one",
        "effect_operations": ["system.time"],
        "effect_verification": "recovered",
        "response_language": "es",
    }


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("Gracias", "es"),
        ("Muchas gracias.", "es"),
        ("Mil gracias!", "es"),
        ("Thanks a lot!", "en"),
        ("Thank you very much.", "en"),
    ],
)
def test_standalone_gratitude_is_deterministic_social_conversation(
    text: str,
    language: str,
) -> None:
    decision = _explicit_social_turn_decision(text)

    assert decision is not None
    assert decision["mode"] == "conversation"
    assert decision["conversation_kind"] == "social"
    assert decision["effect_operations"] == []
    assert decision["effect_verification"] == "not_applicable"
    assert decision["response_language"] == language


@pytest.mark.parametrize(
    ("text", "language"),
    [
        # Saludo, con y sin vocativo, puntuación invertida o compuesto.
        ("Hola", "es"),
        ("Hola.", "es"),
        ("hOLA?", "es"),
        ("¡Hola!", "es"),
        ("hola baxy", "es"),
        ("Hola buenos días", "es"),
        ("hola, buenas", "es"),
        ("buenas", "es"),
        ("buenas tardes", "es"),
        ("buenas noches", "es"),
        ("Hola, ¿cómo estás?", "es"),
        ("hola, cómo andás", "es"),
        ("hola que tal", "es"),
        ("¿qué tal?", "es"),
        ("todo bien?", "es"),
        # Despedida.
        ("chau baxy", "es"),
        ("adiós", "es"),
        ("hasta luego", "es"),
        ("nos vemos", "es"),
        # Agradecimiento con acuse cerrado por delante o vocativo por detrás.
        ("Perfecto, gracias", "es"),
        ("Muy bien gracias", "es"),
        ("Perfecto", "es"),
        ("Muy bien.", "es"),
        ("gracias baxy", "es"),
        ("gracias baxy, sos un capo", "es"),
        # El inglés se toma de la rama que coincide, no de un contador de
        # tokens: `hi` no comparte ninguna palabra con el detector heurístico.
        ("hi", "en"),
        ("hello", "en"),
        ("hey", "en"),
        ("hello there", "en"),
        ("Hello?", "en"),
        ("good morning", "en"),
        ("Hi, how are you?", "en"),
        ("how are you", "en"),
        ("¿Sigues ahí?", "es"),
        ("Are you there?", "en"),
        ("bye", "en"),
        ("goodbye baxy", "en"),
        ("see you later", "en"),
        ("good night", "en"),
        ("perfect, thanks", "en"),
        ("Perfect.", "en"),
        ("Awesome", "en"),
        ("thanks, you're awesome", "en"),
        ("mi dia fue extremadamente duro", "es"),
        ("my day was extremely hard", "en"),
    ],
)
def test_standalone_social_act_is_deterministic_conversation(
    text: str,
    language: str,
) -> None:
    decision = _explicit_social_turn_decision(text)

    assert decision is not None
    assert decision["mode"] == "conversation"
    assert decision["conversation_kind"] == "social"
    assert decision["effect_operations"] == []
    assert decision["effect_verification"] == "not_applicable"
    assert decision["response_language"] == language


@pytest.mark.parametrize(
    "text",
    [
        "Gracias, abre Spotify",
        "Thanks, open Paint",
        "Explica qué significa gracias",
        # El acto social completo es el único que cierra el turno: en cuanto
        # aparece otra cláusula el `fullmatch` deja de coincidir.
        "Hola, Gemma. Pon Daredevil en Disney",
        "hola, dime que hora es",
        "hola, subime el volumen",
        "hello, what time is it?",
        "hi, mute everything",
        # `hola` como contenido, no como saludo.
        "Escribe hola",
        "type hello",
        "mandale hola a Lucas por whatsapp",
        'Copia a mi portapapeles "Hola"',
        "no consultes pantalla para responder esto: hola",
        # Vocativo seguido del nombre de una aplicación, no del asistente.
        "Hey Steam",
        # Preguntas que abren con un saludo pero piden algo.
        "hola quien eres",
        "Hola, quien sos?",
        # Cumplidos abiertos: el reconocedor no adivina un léxico ilimitado.
        "gracias capo",
        "Gracias bb",
        "They were brilliant, thank you! Which one do you think is best?",
        "Well thanks, but I would like the explanation from you directly.",
    ],
)
def test_social_shortcut_never_swallows_another_request(text: str) -> None:
    assert _explicit_social_turn_decision(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "hola",
        "hola baxy",
        "buenas",
        "buenas tardes",
        "buenas noches",
        "hola, todo bien?",
        "qué tal",
        "chau baxy",
        "adiós",
        "hasta luego",
        "nos vemos",
        "gracias",
        "perfecto gracias",
        "hi",
        "hello there",
        "hey",
        "good morning",
        "how are you",
        "¿Sigues ahí?",
        "Are you there?",
        "bye",
        "see you later",
        "good night",
        "perfect, thanks",
    ],
)
def test_social_shortcut_never_overrides_a_recognized_effect(text: str) -> None:
    """`_prepare_turn_result` prefers the social decision over an explicit
    intent, so no member of the social vocabulary may also name an effect."""

    assert effect_intent_module.resolve_explicit_effects(text, (), ()) is None
    assert effect_intent_module.resolve_explicit_clarification(text, ()) is None


@pytest.mark.parametrize(
    "text",
    ["hola", "buenas tardes", "nos vemos", "gracias", "hi", "bye"],
)
def test_social_shortcut_is_not_captured_by_question_punctuation(text: str) -> None:
    history = [
        {
            "role": "assistant",
            "content": "¿Qué aplicación quieres abrir?",
        }
    ]

    decision = _explicit_social_turn_decision(text)

    assert history[-1]["content"].endswith("?")
    assert decision is not None
    assert decision["conversation_kind"] == "social"
    assert decision["effect_operations"] == []


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("No entendí", "es"),
        ("No entiendo.", "es"),
        ("No comprendí", "es"),
        ("No me quedó claro", "es"),
        ("I didn't understand.", "en"),
        ("I don't get it", "en"),
        ("I'm confused", "en"),
    ],
)
def test_standalone_nonunderstanding_is_deterministic_conversation(
    text: str,
    language: str,
) -> None:
    decision = _explicit_nonunderstanding_turn_decision(text)

    assert decision is not None
    assert decision["mode"] == "conversation"
    assert decision["conversation_kind"] == "followup"
    assert decision["effect_operations"] == []
    assert decision["effect_verification"] == "not_applicable"
    assert decision["response_language"] == language


@pytest.mark.parametrize(
    "text",
    [
        "No entendí, abre Spotify",
        "No entendí el contrato",
        "No entiendo cómo abrir Paint",
        "I don't understand, open Paint",
    ],
)
def test_nonunderstanding_shortcut_never_swallows_a_compound_request(
    text: str,
) -> None:
    assert _explicit_nonunderstanding_turn_decision(text) is None


def test_nonunderstanding_is_not_captured_by_question_punctuation() -> None:
    history = [
        {
            "role": "assistant",
            "content": "¿Qué aplicación quieres abrir?",
        }
    ]

    decision = _explicit_nonunderstanding_turn_decision("No entendí", history)

    assert decision is not None
    assert decision["conversation_kind"] == "followup"
    assert decision["effect_operations"] == []


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("¿Qué?", "es"),
        ("¿Por qué?", "es"),
        ("What?", "en"),
        ("Why?", "en"),
    ],
)
def test_elliptical_reaction_uses_non_question_assistant_context(
    text: str,
    language: str,
) -> None:
    history = [
        {
            "role": "assistant",
            "content": "Se agotó el tiempo de la acción anterior.",
        }
    ]

    decision = _explicit_nonunderstanding_turn_decision(text, history)

    assert decision is not None
    assert decision["mode"] == "conversation"
    assert decision["conversation_kind"] == "followup"
    assert decision["effect_operations"] == []
    assert decision["response_language"] == language


@pytest.mark.parametrize("text", ["¿Qué?", "¿Por qué?", "What?", "Why?"])
def test_elliptical_reaction_uses_assistant_question_as_context(
    text: str,
) -> None:
    assert _explicit_nonunderstanding_turn_decision(text, []) is None
    decision = _explicit_nonunderstanding_turn_decision(
        text,
        [{"role": "assistant", "content": "¿Qué aplicación quieres abrir?"}],
    )

    assert decision is not None
    assert decision["conversation_kind"] == "followup"
    assert decision["effect_operations"] == []


def test_assistant_preference_question_is_conversation_not_a_task_action() -> None:
    decision = _explicit_social_turn_decision("what do you want to do today")

    assert decision is not None
    assert decision["mode"] == "conversation"
    assert decision["conversation_kind"] == "knowledge"
    assert decision["effect_operations"] == []


@pytest.mark.parametrize(
    ("text", "kind", "language"),
    [
        ("¿Qué es una GPU y para qué sirve?", "knowledge", "es"),
        ("What is a GPU and what is it used for?", "knowledge", "en"),
        ("Ayer abrí Spotify y escuché música.", "unsupported", "es"),
        ("Yesterday I opened Spotify and listened to music.", "unsupported", "en"),
        ("No abras Spotify; solo dime qué es.", "unsupported", "es"),
        ("Do not open Spotify; just tell me what it is.", "unsupported", "en"),
        ("Abre YouTube en el teléfono de mi hermana.", "unsupported", "es"),
        ("Open YouTube on my sister's phone.", "unsupported", "en"),
        ("How do I take a screenshot in Windows?", "knowledge", "en"),
        ("How can I open the Windows calculator?", "knowledge", "en"),
        ("¿Cómo puedo hacer una captura de pantalla?", "knowledge", "es"),
        ("Explícame cómo abrir el administrador de tareas.", "knowledge", "es"),
        ("Can you play a board game with me?", "unsupported", "en"),
        ("¿Quieres jugar algo conmigo?", "unsupported", "es"),
        ("Cierre de Word podía perder trabajo", "followup", "es"),
        ("Closing Word could lose unsaved work", "followup", "en"),
        ("Sí, sí, te oigo", "social", "es"),
        ("Yeah, yeah I hear you", "social", "en"),
        ("Contame un chiste corto", "knowledge", "es"),
        (
            "I would like to hear some good funny jokes",
            "knowledge",
            "en",
        ),
        ("find me a joke related to baseball", "knowledge", "en"),
        ("What do you think about pineapple on pizza?", "knowledge", "en"),
        ("¿Qué no puedes hacer?", "knowledge", "es"),
        (
            "A question: Rewrite the sentence close every tab more politely",
            "knowledge",
            "en",
        ),
        (
            "Una duda: Dame una receta de risotto para una mañana ventosa",
            "knowledge",
            "es",
        ),
        (
            "Baxy: just curious: Define an operating system without inspecting my PC.",
            "knowledge",
            "en",
        ),
        (
            "Look, Baxy: a brief question: If I bought a tablet, I would open my notes there.",
            "knowledge",
            "en",
        ),
        (
            "One small question: What would happen if another computer lost its Wi-Fi?",
            "knowledge",
            "en",
        ),
        (
            "Una pregunta simple: Si comprara una tableta, abriría allí mis notas.",
            "knowledge",
            "es",
        ),
        (
            "One brief question: Do not capture anything; explain what screenshot means",
            "knowledge",
            "en",
        ),
        (
            "Quiero preguntarte algo sin pedir una acción: pon el volumen al veinte por ciento",
            "knowledge",
            "es",
        ),
        (
            "Just a quick thought, with no computer action: mute the speakers",
            "knowledge",
            "en",
        ),
        (
            "Baxy, haz this: tengo una quick question, sin computer action: abre Spotify",
            "knowledge",
            "es",
        ),
        (
            "I want it to be able to tell me statistics about things it has done for me.",
            "unsupported",
            "en",
        ),
        (
            "Me gustaría que Baxy pudiera resumir todo lo que ha hecho por mí.",
            "unsupported",
            "es",
        ),
        ("No hables hasta que te pregunte.", "followup", "es"),
        ("Don't say anything until I ask.", "followup", "en"),
        ("I want to play um Mario against Julie.", "unsupported", "en"),
        ("Pon vídeos.", "followup", "es"),
        ("Abre eso", "followup", "es"),
        (
            "quien es el actual primer ministro de rusia",
            "unsupported",
            "es",
        ),
        (
            "puedes mostrarme una lista de todos mis comandos recientes",
            "unsupported",
            "es",
        ),
        ("describe el disco duro del ordenador", "knowledge", "es"),
        ("describe about the computer hard disk", "knowledge", "en"),
        ("tell me about india location", "knowledge", "en"),
        ("please tell me the score of the game", "knowledge", "en"),
        ("what sound does a dog make", "knowledge", "en"),
        ("give details of rock sand", "knowledge", "en"),
        ("cuéntame todo sobre el huracán", "knowledge", "es"),
        ("my day is going well add a memo", "social", "en"),
        ("encontrar ruta", "knowledge", "es"),
        ("dime la dirección de billy crytals", "unsupported", "es"),
        ("¿Quién eres?", "knowledge", "es"),
        ("Quien eres tu?", "knowledge", "es"),
        ("Who are you?", "knowledge", "en"),
        ("¿Qué puedes hacer?", "knowledge", "es"),
        ("Que puedes hacer?", "knowledge", "es"),
        ("Cuanto es 17 por 23?", "knowledge", "es"),
        ("What is 17 times 23?", "knowledge", "en"),
        ("Explica que es una nube en una frase.", "knowledge", "es"),
        ("Que sonido hace un perro?", "knowledge", "es"),
        ("Resume en una frase que puedes hacer.", "knowledge", "es"),
        ("Respóndeme sólo con un saludo breve.", "knowledge", "es"),
    ],
)
def test_explicit_stable_no_effect_turns_keep_zero_action_authority(
    text: str,
    kind: str,
    language: str,
) -> None:
    decision = _explicit_stable_no_effect_turn_decision(text)

    assert decision is not None
    assert decision["mode"] == "conversation"
    assert decision["conversation_kind"] == kind
    assert decision["effect_operations"] == []
    assert decision["effect_verification"] == "not_applicable"
    assert decision["response_language"] == language


@pytest.mark.parametrize(
    "text",
    [
        "Dime el uso actual de RAM de este computador.",
        "What is the current speaker volume?",
        "Describe el uso actual del disco duro.",
        "Conecta mi teléfono por Bluetooth.",
        "Pair my phone over Bluetooth.",
        "Abre Spotify.",
        "Open YouTube on this computer.",
        "Play Beat It on Spotify.",
        "Juega Counter Strike.",
        "I want you to open Spotify.",
        "I want Baxy to open Spotify.",
        "Quiero que abras Spotify.",
        "Quiero que Baxy abra Spotify.",
        "Sí, sí, te oigo, apaga la alarma.",
    ],
)
def test_explicit_stable_no_effect_turn_never_swallows_current_pc_actions(
    text: str,
) -> None:
    assert _explicit_stable_no_effect_turn_decision(text) is None


def test_stable_no_effect_turn_does_not_infer_state_from_question_history() -> None:
    history = [
        {
            "role": "assistant",
            "content": "Which device do you mean?",
        }
    ]

    decision = _explicit_stable_no_effect_turn_decision("Open YouTube on my phone.")

    assert history[-1]["content"].endswith("?")
    assert decision is not None
    assert decision["conversation_kind"] == "unsupported"
    assert decision["effect_operations"] == []


def test_explicit_non_action_frame_closes_without_effect() -> None:
    decision = _explicit_stable_no_effect_turn_decision(
        "I have a short question, just to chat: open Spotify",
    )

    assert decision is not None
    assert decision["mode"] == "conversation"
    assert decision["effect_operations"] == []


def test_content_drafting_closes_before_message_delivery_clarification() -> None:
    tool = {
        "type": "function",
        "function": {
            "name": "message_send",
            "canonical_name": "message.send",
            "description": "Send one verified desktop message.",
            "risk": "external_communication",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipientId": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["recipientId", "text"],
                "additionalProperties": False,
            },
        },
    }

    class NoEvidence:
        @staticmethod
        def candidate_families(*_args: object) -> tuple[str, ...]:
            raise AssertionError("content drafting must not rank action families")

        @staticmethod
        def retrieve(*_args: object) -> list[object]:
            raise AssertionError("content drafting must not retrieve action evidence")

    class Runtime:
        @staticmethod
        def formulate_explicit_clarification_question(*_args: object) -> str:
            raise AssertionError("content drafting must close before clarification")

        @staticmethod
        def detect_response_language(_text: str) -> str:
            return "en"

        @staticmethod
        def chat(*_args: object, **kwargs: object) -> tuple[str, list[object]]:
            assert kwargs["conversation_kind"] == "knowledge"
            return "Here is a draft you can edit.", []

    result = _prepare_turn_result(
        {
            "id": "content-draft",
            "text": "Write me an email that I cant make it to the meeting",
        },
        llm=Runtime(),
        planner_catalog=PlannerCatalog([tool]),
        turn_evidence=NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name={"message.send": tool},
    )

    assert result["kind"] == "conversation"
    assert result["intentOperations"] == []
    assert result["effectOperations"] == []
    assert result["question"] == ""
    assert result["reply"] == "Here is a draft you can edit."


def test_one_sentence_drafting_closes_before_model_routing() -> None:
    harmless_tool = {
        "type": "function",
        "function": {
            "name": "system_time",
            "canonical_name": "system.time",
            "description": "Read the verified local clock.",
            "risk": "read_only",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    }

    class NoCatalog:
        @staticmethod
        def candidate_families(*_args: object) -> tuple[str, ...]:
            raise AssertionError("one-sentence drafting must not rank action families")

        @staticmethod
        def retrieve(*_args: object) -> list[object]:
            raise AssertionError("one-sentence drafting must not retrieve action evidence")

    class Runtime:
        @staticmethod
        def detect_response_language(_text: str) -> str:
            raise AssertionError("the closed draft already owns its language")

        @staticmethod
        def chat(*_args: object, **kwargs: object) -> tuple[str, list[object]]:
            assert kwargs["conversation_kind"] == "knowledge"
            assert kwargs["response_language"] == "es"
            return "El cielo guarda una calma azul.", []

    result = _prepare_turn_result(
        {
            "id": "one-sentence-draft",
            "text": "Di una frase breve y completa sobre el cielo.",
        },
        llm=Runtime(),
        planner_catalog=PlannerCatalog([harmless_tool]),
        turn_evidence=NoCatalog(),
        encoder=lambda _texts: (),
        tool_by_name={},
    )

    assert result["kind"] == "conversation"
    assert result["effectOperations"] == []
    assert result["reply"] == "El cielo guarda una calma azul."


@pytest.mark.parametrize(
    "text",
    [
        "Que puedes hacer?",
        "Cuanto es 17 por 23?",
        "¿Cuánto es dos más dos?",
        "What is 17 times 23?",
        "What is two plus two?",
        "Explica que es una nube en una frase.",
        "Que sonido hace un perro?",
        "Resume en una frase que puedes hacer.",
    ],
)
def test_closed_identity_and_arithmetic_never_authorize_web_search(text: str) -> None:
    chat_histories: list[object] = []
    web_tool = {
        "type": "function",
        "function": {
            "name": "web_search",
            "canonical_name": "web.search",
            "description": "Search public web sources.",
            "risk": "read_only",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    }

    class NoEvidence:
        @staticmethod
        def candidate_families(*_args: object) -> tuple[str, ...]:
            raise AssertionError("a closed no-effect turn must not rank actions")

        @staticmethod
        def retrieve(*_args: object) -> list[object]:
            raise AssertionError("a closed no-effect turn must not retrieve actions")

    class Runtime:
        @staticmethod
        def chat(*_args: object, **_kwargs: object) -> tuple[str, list[object]]:
            chat_histories.append(_kwargs["history"])
            return "Respuesta sintética.", []

    result = _prepare_turn_result(
        {
            "id": "closed-no-effect",
            "text": text,
            "history": [
                {
                    "role": "assistant",
                    "content": "¿Quieres que restaure una ventana?",
                }
            ],
        },
        llm=Runtime(),
        planner_catalog=PlannerCatalog([web_tool]),
        turn_evidence=NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name={"web.search": web_tool},
    )

    assert result["kind"] == "conversation"
    assert result["intentOperations"] == []
    assert result["effectOperations"] == []
    assert chat_histories == [[]]


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("¿Qué hora es?", "es"),
        ("open calculator", "en"),
        ("abre Spotify and pause", "mixed"),
    ],
)
def test_explicit_turn_decision_keeps_effects_without_model_reinference(
    text: str,
    language: str,
) -> None:
    result = _explicit_turn_decision(
        EffectIntent(("system.time",)),
        text,
    )

    assert result["mode"] == "action"
    assert result["operation"] == "system.time"
    assert result["effect_operations"] == ["system.time"]
    assert result["effect_verification"] == "recovered"
    assert result["response_language"] == language


def test_literal_recall_closes_routing_before_a_second_cpu_policy_decode() -> None:
    current = "¿Qué palabra inventada mencioné en mi pregunta anterior?"
    history = [
        {
            "role": "user",
            "content": "Explica por qué «Nimbo8202» suena amistosa.",
        },
        {
            "role": "assistant",
            "content": "Suena amistosa por su ritmo suave.",
        },
        {"role": "user", "content": current},
    ]
    catalog = PlannerCatalog(
        [
            {
                "type": "function",
                "function": {
                    "name": "system_time",
                    "canonical_name": "system.time",
                    "description": "Read the local time.",
                    "risk": "read_only",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                        "additionalProperties": False,
                    },
                },
            }
        ]
    )

    class NoEvidence:
        @staticmethod
        def candidate_families(*_args: object) -> tuple[str, ...]:
            raise AssertionError("literal recall must not rank action families")

        @staticmethod
        def retrieve(*_args: object) -> list[object]:
            raise AssertionError("literal recall must not retrieve action evidence")

    class Runtime:
        @staticmethod
        def decide_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
            raise AssertionError("literal recall must not run policy selection")

        @staticmethod
        def detect_response_language(*_args: object) -> str:
            raise AssertionError("the closed recall route already owns language")

        @staticmethod
        def chat(*_args: object, **kwargs: object) -> tuple[str, list[object]]:
            assert kwargs["conversation_kind"] == "followup"
            assert kwargs["response_language"] == "es"
            return "La palabra era Nimbo8202.", []

    result = _prepare_turn_result(
        {"id": "literal-recall", "text": current, "history": history},
        llm=Runtime(),
        planner_catalog=catalog,
        turn_evidence=NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name={},
    )

    assert result["kind"] == "conversation"
    assert result["effectOperations"] == []
    assert result["reply"] == "La palabra era Nimbo8202."


def test_explicit_plan_skeleton_preserves_effect_order_and_dependency() -> None:
    assert _explicit_plan_skeleton(("capture.screenshot", "ocr.read")) == {
        "kind": "plan",
        "question": "",
        "steps": [
            {
                "id": "step_1",
                "operation": "capture.screenshot",
                "purpose": "Conservar y completar este efecto solicitado.",
                "dependsOn": [],
                "argumentsMode": "literal",
            },
            {
                "id": "step_2",
                "operation": "ocr.read",
                "purpose": "Conservar y completar este efecto solicitado.",
                "dependsOn": ["step_1"],
                "argumentsMode": "after_dependencies",
            },
        ],
    }


def test_explicit_plan_skeleton_adds_required_close_identity() -> None:
    result = _explicit_plan_skeleton(
        ("app.close",),
        ("cierra la calculadora",),
    )

    assert [step["operation"] for step in result["steps"]] == [
        "window.resolve",
        "app.close",
    ]
    assert result["steps"][1]["dependsOn"] == ["step_1"]
    assert result["steps"][1]["argumentsMode"] == "after_dependencies"


@pytest.mark.parametrize(
    "evidence",
    [
        "cierra la ventana activa",
        "cierralo",
        "close it",
    ],
)
def test_active_or_deictic_close_uses_verified_foreground_identity(
    evidence: str,
) -> None:
    result = _explicit_plan_skeleton(("app.close",), (evidence,))

    assert [step["operation"] for step in result["steps"]] == [
        "window.active",
        "app.close",
    ]
    assert result["steps"][1]["dependsOn"] == ["step_1"]
    assert result["steps"][1]["argumentsMode"] == "after_dependencies"


def test_explicit_plan_skeleton_resolves_reminder_before_delete() -> None:
    result = _explicit_plan_skeleton(
        ("reminder.delete",),
        ("elimina el recordatorio de ir a buscar a Evey",),
    )

    assert [step["operation"] for step in result["steps"]] == [
        "reminder.resolve.exact",
        "reminder.delete",
    ]
    assert result["steps"][1]["dependsOn"] == ["step_1"]
    assert result["steps"][1]["argumentsMode"] == "after_dependencies"


def test_explicit_plan_skeleton_lists_due_notification_before_dismiss() -> None:
    result = _explicit_plan_skeleton(("notification.dismiss",))

    assert [step["operation"] for step in result["steps"]] == [
        "notification.list.due",
        "notification.dismiss",
    ]
    assert result["steps"][1]["dependsOn"] == ["step_1"]
    assert result["steps"][1]["argumentsMode"] == "after_dependencies"


def test_repeated_identity_consumers_receive_fresh_predecessors() -> None:
    result = _explicit_plan_skeleton(
        ("app.close", "app.close"),
        ("cierra la calculadora", "cierra spotify"),
    )

    assert [step["operation"] for step in result["steps"]] == [
        "window.resolve",
        "app.close",
        "window.resolve",
        "app.close",
    ]
    assert result["steps"][1]["dependsOn"] == ["step_1"]
    assert result["steps"][3]["dependsOn"] == ["step_3"]


def test_each_window_mutation_depends_on_the_verified_active_window() -> None:
    result = _explicit_plan_skeleton(
        ("window.active", "window.maximize", "window.minimize"),
    )

    assert result["steps"][1]["dependsOn"] == ["step_1"]
    assert result["steps"][2]["dependsOn"] == ["step_1"]


@pytest.mark.parametrize("consumer", sorted(mind_main._IDENTITY_CONSUMERS))
def test_every_identity_consumer_gets_exactly_one_semantic_producer(
    consumer: str,
) -> None:
    prerequisites = mind_main.required_predecessors(consumer)

    assert prerequisites
    result = _explicit_plan_skeleton((consumer,))
    assert [step["operation"] for step in result["steps"]] == [
        prerequisites[0],
        consumer,
    ]
    assert result["steps"][0]["dependsOn"] == []
    assert result["steps"][1]["dependsOn"] == ["step_1"]
    assert result["steps"][1]["argumentsMode"] == "after_dependencies"


@pytest.mark.parametrize(
    ("reference", "expected_dependency"),
    [
        ("lee la primera nota", "step_1"),
        ("read the first note", "step_1"),
        ("lee la segunda nota", "step_2"),
        ("read the latest note", "step_2"),
        ("lee esa nota", "step_2"),
    ],
)
def test_conditional_identity_coreference_selects_one_exact_producer(
    reference: str,
    expected_dependency: str,
) -> None:
    result = _explicit_plan_skeleton(
        ("note.create", "note.create", "note.read"),
        ("crea la nota Alfa", "crea la nota Beta", reference),
    )

    assert result["steps"][0]["dependsOn"] == []
    assert result["steps"][1]["dependsOn"] == []
    assert result["steps"][2]["dependsOn"] == [expected_dependency]
    assert result["steps"][2]["argumentsMode"] == "after_dependencies"


def test_repeated_effects_receive_distinct_argument_purposes() -> None:
    result = _explicit_plan_skeleton(
        ("app.open", "app.open"),
        ("abre calculadora", "abre spotify"),
    )

    assert [step["purpose"] for step in result["steps"]] == [
        "abre calculadora",
        "abre spotify",
    ]


@pytest.mark.parametrize(
    ("operation", "evidence", "expected"),
    [
        ("audio.volume", "pon el volumen al 8 por ciento", {"level": 8}),
        (
            "audio.volume.adjust",
            "sube el volumen en 2 puntos",
            {"amount": 2, "direction": "up"},
        ),
        (
            "audio.volume.adjust",
            "lower volume by 3 points",
            {"amount": 3, "direction": "down"},
        ),
        ("audio.mute", "mute audio", {"state": True}),
        ("audio.mute", "unmute audio", {"state": False}),
        ("audio.mute", "quita el mute del audio", {"state": False}),
    ],
)
def test_explicit_arguments_are_bound_to_each_effect_fragment(
    operation: str,
    evidence: str,
    expected: dict[str, object],
) -> None:
    assert _explicit_arguments_from_evidence(operation, evidence) == expected


@pytest.mark.parametrize(
    ("evidence", "expected"),
    [
        ("Necesito que cierres whatsapp", {"process": "whatsapp"}),
        ("Cierra la ventana de Bloc de notas.", {"process": "Bloc de notas"}),
        ("Cerrá la calculadora", {"process": "calculadora"}),
        ("cerra steam", {"process": "steam"}),
        ("I need you to close WhatsApp", {"process": "WhatsApp"}),
        ("Close the Notepad window", {"process": "Notepad"}),
        ("cierra la ventana activa", None),
        ("close it", None),
    ],
)
def test_named_close_process_is_grounded_without_requesting_an_internal_id(
    evidence: str,
    expected: dict[str, object] | None,
) -> None:
    assert _explicit_arguments_from_evidence("window.resolve", evidence) == expected


@pytest.mark.parametrize(
    ("evidence", "expected_name"),
    [
        ("hay alguna ventana de Steam abierta", "steam"),
        ("Is there an open Visual Studio Code window?", "visual studio code"),
        ("check whether Spotify has a window visible", "spotify"),
    ],
)
def test_named_application_window_status_grounds_only_the_app_literal(
    evidence: str,
    expected_name: str,
) -> None:
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string", "minLength": 1}},
        "required": ["name"],
        "additionalProperties": False,
    }

    assert _explicit_arguments_from_evidence(
        "window.application.status",
        evidence,
    ) == {"name": expected_name}
    assert _ground_explicit_arguments(
        "window.application.status",
        evidence,
        schema,
    ) == {"name": expected_name}

    assert _ground_explicit_arguments(
        "window.application.status",
        expected_name,
        schema,
    ) == {"name": expected_name}


def test_declarative_window_status_does_not_gain_argument_authority() -> None:
    assert (
        _explicit_arguments_from_evidence(
            "window.application.status",
            "Tengo una ventana de Steam abierta.",
        )
        is None
    )


@pytest.mark.parametrize(
    ("evidence", "level"),
    [
        ("Set the volume to seventy five percent", 75),
        ("Pon el volumen al setenta y cinco por ciento", 75),
    ],
)
def test_word_valued_volume_arguments_are_bound_without_the_model(
    evidence: str,
    level: int,
) -> None:
    assert _explicit_arguments_from_evidence("audio.volume", evidence) == {
        "level": level,
    }


def test_live_artist_query_is_grounded_without_model_argument_latency() -> None:
    assert _explicit_arguments_from_evidence(
        "media.play.query",
        "Pon Tesla en vivo",
    ) == {"provider": "spotify", "query": "Tesla en vivo"}
    assert _explicit_arguments_from_evidence(
        "media.play.query",
        "por favor pon trece",
    ) == {"provider": "spotify", "query": "trece"}
    assert (
        _explicit_arguments_from_evidence(
            "media.play.query",
            "Pon la cámara en vivo",
        )
        is None
    )
    schema = {
        "type": "object",
        "properties": {
            "provider": {"type": "string", "enum": ["spotify"]},
            "query": {"type": "string", "minLength": 1},
        },
        "required": ["provider", "query"],
        "additionalProperties": False,
    }
    assert _ground_explicit_arguments(
        "media.play.query",
        "Pon Los Prisioneros en vivo",
        schema,
    ) == {"provider": "spotify", "query": "Los Prisioneros en vivo"}


def test_change_current_artist_is_a_bounded_next_media_control() -> None:
    schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["next", "pause", "play", "previous", "stop", "toggle"],
            },
            "sourceApp": {"type": ["string", "null"]},
        },
        "required": ["action"],
        "additionalProperties": False,
    }
    assert _ground_explicit_arguments(
        "media.control",
        "Cambia el artista",
        schema,
    ) == {"action": "next"}
    assert _ground_explicit_arguments(
        "media.control",
        "Change the artist, please",
        schema,
    ) == {"action": "next"}
    assert (
        _ground_explicit_arguments(
            "media.control",
            "Cambia el artista a Queen",
            schema,
        )
        is None
    )

    literal_controls = {
        "Skip to track five.": "next",
        "SKip this song.": "next",
        "Saltea esta canción.": "next",
        "Pon el siguiente podcast.": "next",
        "Play the next episode.": "next",
        "Pause the music.": "pause",
        "Reanuda el audio pausado.": "play",
        "Detén el audio.": "stop",
        "Play the previous song.": "previous",
    }
    for evidence, action in literal_controls.items():
        assert _ground_explicit_arguments(
            "media.control",
            evidence,
            schema,
        ) == {"action": action}

    assert _ground_explicit_arguments(
        "media.control",
        "Pausa esa reproducción en Spotify.",
        schema,
    ) == {"action": "pause", "sourceApp": "spotify"}

    assert (
        _ground_explicit_arguments(
            "media.control",
            "Pause it and then resume it.",
            schema,
        )
        is None
    )


def test_latest_notification_kind_is_grounded_from_the_literal_domain() -> None:
    schema = {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["alarm", "reminder"]},
        },
        "required": ["kind"],
        "additionalProperties": False,
    }
    assert _ground_explicit_arguments(
        "notification.cancel.latest",
        "Cancel alarms please",
        schema,
    ) == {"kind": "alarm"}
    assert _ground_explicit_arguments(
        "notification.cancel.latest",
        "Cancela recordatorios, por favor",
        schema,
    ) == {"kind": "reminder"}
    assert (
        _ground_explicit_arguments(
            "notification.cancel.latest",
            "Cancel the alarm and reminder",
            schema,
        )
        is None
    )


def test_location_recommendation_preserves_literal_web_query() -> None:
    schema = {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "minimum": 1, "maximum": 20},
            "query": {"type": "string", "minLength": 1},
        },
        "required": ["query"],
        "additionalProperties": False,
    }
    assert _ground_explicit_arguments(
        "web.search",
        "Lugares para ir después de la medianoche",
        schema,
    ) == {"query": "Lugares para ir después de la medianoche"}
    assert _explicit_arguments_from_evidence(
        "web.search",
        "Places to go after midnight",
    ) == {"query": "Places to go after midnight"}
    assert _ground_explicit_arguments(
        "web.search",
        "What was the weather like on this day last year",
        schema,
    ) == {"query": "What was the weather like on this day last year"}
    assert _ground_explicit_arguments(
        "web.search",
        "Quien es Batman?",
        schema,
    ) == {"query": "Batman biografia"}
    assert _ground_explicit_arguments(
        "web.search",
        "Cual es el ultimo Mortal Kombat que salio?",
        schema,
    ) == {"query": "Mortal Kombat most recent release available now"}
    assert _ground_explicit_arguments(
        "web.search",
        "what is the capital of Nigeria?",
        schema,
    ) == {"query": "capital of Nigeria"}


def test_nominal_reminder_lookup_is_read_only_and_title_grounded() -> None:
    schema = {
        "type": "object",
        "properties": {
            "includeDeleted": {"type": "boolean"},
            "title": {"type": "string", "minLength": 1},
        },
        "required": ["title"],
        "additionalProperties": False,
    }
    assert _ground_explicit_arguments(
        "reminder.resolve.exact",
        "Reminders for birthdays.",
        schema,
    ) == {"title": "birthdays"}
    assert _ground_explicit_arguments(
        "reminder.resolve.exact",
        "Can I see the reminder for Haley's birthday party again?",
        schema,
    ) == {"title": "Haley's birthday party"}
    assert _ground_explicit_arguments(
        "reminder.resolve.exact",
        "Recordatorios de cumpleaños.",
        schema,
    ) == {"title": "cumpleaños"}
    assert (
        _explicit_arguments_from_evidence(
            "reminder.resolve.exact",
            "Reminders for tomorrow.",
        )
        is None
    )


@pytest.mark.parametrize(
    ("evidence", "expected"),
    [
        (
            "Get rid of the five p.m. alarm",
            {"hour": 5, "kind": "alarm", "period": "pm"},
        ),
        (
            "Quita la alarma de las cinco de la tarde",
            {"hour": 5, "kind": "alarm", "period": "pm"},
        ),
        (
            "Remove the 17:30 reminder",
            {"hour": 17, "kind": "reminder", "minute": 30},
        ),
    ],
)
def test_exact_notification_clock_arguments_are_grounded_without_identity_guessing(
    evidence: str,
    expected: dict[str, object],
) -> None:
    assert (
        _explicit_arguments_from_evidence("notification.cancel.at", evidence)
        == expected
    )


@pytest.mark.parametrize(
    ("evidence", "expected"),
    [
        (
            "Dile a amor que la amo demasiado en wsp",
            {"channel": "whatsapp", "recipient": "amor"},
        ),
        (
            "Tell Lucia on Discord that I will be late",
            {"channel": "discord", "recipient": "Lucia"},
        ),
        (
            "Envía por WhatsApp a Música el mensaje «llego en diez minutos».",
            {"channel": "whatsapp", "recipient": "Música"},
        ),
        (
            "Send Music the WhatsApp message ‘I will arrive soon’.",
            {"channel": "whatsapp", "recipient": "Music"},
        ),
    ],
)
def test_message_recipient_literals_are_exact_and_channel_canonical(
    evidence: str,
    expected: dict[str, object],
) -> None:
    assert (
        _explicit_arguments_from_evidence(
            "message.recipient.resolve",
            evidence,
        )
        == expected
    )


def test_message_recipient_wsp_alias_crosses_enum_grounding() -> None:
    schema = {
        "type": "object",
        "properties": {
            "channel": {"type": "string", "enum": ["discord", "whatsapp"]},
            "recipient": {"type": "string"},
        },
        "required": ["channel", "recipient"],
        "additionalProperties": False,
    }

    assert _ground_explicit_arguments(
        "message.recipient.resolve",
        "Dile a amor que la amo demasiado en wsp",
        schema,
    ) == {"channel": "whatsapp", "recipient": "amor"}


@pytest.mark.parametrize(
    ("evidence", "title"),
    [
        ("Delete reminder to pick-up Evey", "pick-up Evey"),
        (
            "Elimina el recordatorio para ir a buscar a Evey.",
            "ir a buscar a Evey",
        ),
        (
            "Reminder to take grandma shopping needs to be cancelled.",
            "take grandma shopping",
        ),
        (
            "Find the reminder about the bowling fundraiser and remove it",
            "the bowling fundraiser",
        ),
        (
            "No necesito comida para perro, cancela el recordatorio.",
            "comida para perro",
        ),
        (
            "Los tragos después del trabajo se cancelaron así que este "
            "recordatorio se tiene que eliminar.",
            "Los tragos después del trabajo",
        ),
    ],
)
def test_reminder_resolver_preserves_exact_title_spelling(
    evidence: str,
    title: str,
) -> None:
    assert _explicit_arguments_from_evidence(
        "reminder.resolve.exact",
        evidence,
    ) == {"title": title}


@pytest.mark.parametrize(
    "evidence",
    [
        "Tell Ana and Luis on Discord that I will be late",
        "Send them the WhatsApp message hello",
        "Delete reminders to call Ana and Luis",
        "Remove a reminder please",
    ],
)
def test_identity_literal_extraction_abstains_on_non_unique_requests(
    evidence: str,
) -> None:
    operation = (
        "message.recipient.resolve"
        if "Discord" in evidence or "WhatsApp" in evidence
        else "reminder.resolve.exact"
    )
    assert _explicit_arguments_from_evidence(operation, evidence) is None


@pytest.mark.parametrize(
    ("operation", "evidence", "expected"),
    [
        ("bluetooth.radio.set", "prendé el bluetooth", {"state": True}),
        (
            "audio.microphone.mute",
            "silenciame el micrófono",
            {"state": True},
        ),
        (
            "filesystem.file.open.latest",
            "Abre el último archivo que descargué",
            {"folder": "downloads"},
        ),
        (
            "filesystem.known.search",
            "Busca archivos que contengan la palabra “Batman",
            {"folder": "all_known", "query": "Batman"},
        ),
        (
            "note.create",
            "anota que tengo que comprar pan",
            {"content": "tengo que comprar pan", "title": "comprar pan"},
        ),
        (
            "note.create",
            "anotá que terminé de configurar el micrófono",
            {
                "content": "terminé de configurar el micrófono",
                "title": "configurar el micrófono",
            },
        ),
        (
            "wifi.connect.named",
            "cambia el wifi a EV 2",
            {"profileName": "RV 2"},
        ),
        (
            "wifi.connect.named",
            "Connect to the Wi-Fi network called Home",
            {"profileName": "Home"},
        ),
    ],
)
def test_common_complete_literals_do_not_require_model_reinference(
    operation: str,
    evidence: str,
    expected: dict[str, object],
) -> None:
    assert _explicit_arguments_from_evidence(operation, evidence) == expected


def test_bare_host_and_named_service_receive_closed_https_destinations() -> None:
    schema = {
        "type": "object",
        "properties": {"url": {"type": "string"}},
        "required": ["url"],
        "additionalProperties": False,
    }

    assert _ground_explicit_arguments(
        "browser.navigate",
        "Abre github.com",
        schema,
    ) == {"url": "https://github.com"}
    assert _ground_explicit_arguments(
        "browser.navigate",
        "Abrí YouTube en el navegador",
        schema,
    ) == {"url": "https://www.youtube.com/"}


def test_relative_and_clock_due_literals_become_future_utc_instants() -> None:
    now = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)

    assert (
        mind_main._canonical_due_utc(
            "10 minutos",
            now_utc=now,
        )
        == "2026-08-01T12:10:00Z"
    )
    assert (
        mind_main._canonical_due_utc(
            "mañana 8am",
            now_utc=now,
        )
        == "2026-08-02T08:00:00Z"
    )
    assert (
        mind_main._canonical_due_utc(
            "a las 15:00",
            now_utc=now,
        )
        == "2026-08-01T15:00:00Z"
    )
    assert (
        mind_main._canonical_due_utc(
            "at 5pm",
            now_utc=now,
        )
        == "2026-08-01T17:00:00Z"
    )
    assert (
        mind_main._canonical_due_utc(
            "on the 30th at 3pm",
            now_utc=now,
        )
        == "2026-08-30T15:00:00Z"
    )
    assert (
        mind_main._canonical_due_utc(
            "April 30th at 3pm",
            now_utc=now,
        )
        == "2027-04-30T15:00:00Z"
    )
    assert (
        mind_main._canonical_due_utc(
            "April 31st at 3pm",
            now_utc=now,
        )
        is None
    )
    assert (
        mind_main._canonical_due_utc(
            "in 2 days",
            now_utc=now,
        )
        == "2026-08-03T12:00:00Z"
    )
    assert mind_main._explicit_notification_schedule_arguments(
        "pon una alarma a las 15:00",
    ) == {
        "dueUtc": "a las 15:00",
        "kind": "alarm",
        "title": "alarma a las 15:00",
    }
    assert (
        mind_main._explicit_notification_schedule_arguments(
            "make an alarm for 0760h",
        )
        is None
    )
    assert _normalize_grounded_operation_arguments(
        "notification.schedule",
        {
            "dueUtc": "10 minutos",
            "kind": "alarm",
            "title": "timer de 10 minutos",
        },
        "arranca un timer de 10 minutos",
        now_utc=now,
    ) == {
        "dueUtc": "2026-08-01T12:10:00Z",
        "kind": "alarm",
        "title": "timer de 10 minutos",
    }


def test_relative_calendar_windows_use_closed_local_civil_boundaries() -> None:
    now = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)

    assert mind_main._explicit_calendar_range_arguments(
        "Cualquier cosa interesante que suceda este fin de semana",
        now_utc=now,
    ) == {
        "startUtc": "2026-08-01T00:00:00Z",
        "endUtc": "2026-08-03T00:00:00Z",
    }
    assert mind_main._explicit_calendar_range_arguments(
        "Show my events next week",
        now_utc=now,
    ) == {
        "startUtc": "2026-08-03T00:00:00Z",
        "endUtc": "2026-08-10T00:00:00Z",
    }
    assert mind_main._explicit_calendar_range_arguments(
        "Anything I should do after work today",
        now_utc=now,
    ) == {
        "startUtc": "2026-08-01T17:00:00Z",
        "endUtc": "2026-08-02T00:00:00Z",
    }
    assert mind_main._explicit_calendar_range_arguments(
        "¿Tengo algo que hacer hoy después del trabajo?",
        now_utc=now,
    ) == {
        "startUtc": "2026-08-01T17:00:00Z",
        "endUtc": "2026-08-02T00:00:00Z",
    }
    assert mind_main._explicit_calendar_range_arguments(
        "Eventos de esta noche",
        now_utc=now,
    ) == {
        "startUtc": "2026-08-01T18:00:00Z",
        "endUtc": "2026-08-02T00:00:00Z",
    }
    assert mind_main._explicit_calendar_range_arguments(
        "Qué sucede en Año Nuevo",
        now_utc=now,
    ) == {
        "startUtc": "2027-01-01T00:00:00Z",
        "endUtc": "2027-01-02T00:00:00Z",
    }
    assert (
        mind_main._explicit_calendar_range_arguments(
            "Show events today and tomorrow",
            now_utc=now,
        )
        is None
    )


def test_absolute_calendar_range_includes_the_spoken_final_day() -> None:
    now = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)

    assert mind_main._explicit_calendar_range_arguments(
        "during the timeframe of february one and march sixteen what meetings occurred",
        now_utc=now,
    ) == {
        "startUtc": "2026-02-01T00:00:00Z",
        "endUtc": "2026-03-17T00:00:00Z",
    }


def test_timer_arguments_are_literal_before_deterministic_clock_conversion() -> None:
    assert _explicit_arguments_from_evidence(
        "notification.schedule",
        "arranca un temporizador de 10 minutos",
    ) == {
        "dueUtc": "10 minutos",
        "kind": "alarm",
        "title": "temporizador de 10 minutos",
    }


@pytest.mark.parametrize(
    ("evidence", "expected"),
    [
        (
            "avisame en 20 minutos que saque la comida",
            {"dueUtc": "en 20 minutos", "title": "saque la comida"},
        ),
        (
            "avisame en una hora que salgo",
            {"dueUtc": "en una hora", "title": "salgo"},
        ),
        (
            "ponme un recordatorio en 2 minutos para tomar agua",
            {"dueUtc": "en 2 minutos", "title": "tomar agua"},
        ),
        (
            "recordatorio de tomar agua en 1 hora",
            {"dueUtc": "en 1 hora", "title": "tomar agua"},
        ),
        (
            "remind me in 20 minutes to take the food out",
            {"dueUtc": "in 20 minutes", "title": "take the food out"},
        ),
        (
            "set a reminder to drink water in one hour",
            {"dueUtc": "in one hour", "title": "drink water"},
        ),
    ],
)
def test_relative_reminders_keep_literal_time_and_title_without_reinference(
    evidence: str,
    expected: dict[str, object],
) -> None:
    assert _explicit_arguments_from_evidence("reminder.create", evidence) == expected


def test_multiple_alarm_effects_keep_independent_literal_grounding() -> None:
    intent = mind_main.resolve_explicit_effects(
        "Record alarms for 3 and 4 in the afternoon.",
        {"notification.schedule"},
    )

    assert intent is not None
    plan = _explicit_plan_skeleton(intent.operations, intent.evidence)
    assert [step["operation"] for step in plan["steps"]] == [
        "notification.schedule",
        "notification.schedule",
    ]
    arguments = [
        _explicit_arguments_from_evidence("notification.schedule", evidence)
        for evidence in intent.evidence
    ]
    assert [argument["dueUtc"] for argument in arguments if argument] == [
        "at 3 in the afternoon",
        "at 4 in the afternoon",
    ]


@pytest.mark.parametrize(
    ("evidence", "expected"),
    [
        (
            "Crea una nota titulada Prueba LLM Q3 con el contenido verificación Café",
            {"title": "Prueba LLM Q3", "content": "verificación Café"},
        ),
        (
            "Create a note titled Release Q3 with the content verified locally",
            {"title": "Release Q3", "content": "verified locally"},
        ),
        (
            "Crea una nota que diga pagar el arriendo el viernes.",
            {
                "title": "pagar el arriendo el viernes",
                "content": "pagar el arriendo el viernes",
            },
        ),
        (
            "Make a note that says call the dentist tomorrow.",
            {
                "title": "call the dentist tomorrow",
                "content": "call the dentist tomorrow",
            },
        ),
    ],
)
def test_explicit_note_literals_preserve_original_text(
    evidence: str,
    expected: dict[str, object],
) -> None:
    assert _explicit_arguments_from_evidence("note.create", evidence) == expected


def test_explicit_note_extraction_abstains_without_both_named_literals() -> None:
    assert (
        _explicit_arguments_from_evidence(
            "note.create",
            "Crea una nota sobre la verificación local",
        )
        is None
    )


@pytest.mark.parametrize(
    ("operation", "evidence"),
    [
        ("audio.volume", "pon el volumen al 8 y luego al 12"),
        ("audio.volume", "mi laptop de 15 pulgadas tiene problemas de volumen"),
        ("audio.volume.adjust", "sube y baja el volumen en 2 puntos"),
        (
            "audio.volume.adjust",
            "en mi laptop de 15 pulgadas baja el volumen",
        ),
        ("audio.mute", "mute and unmute audio"),
    ],
)
def test_explicit_argument_extraction_abstains_on_ambiguous_fragments(
    operation: str,
    evidence: str,
) -> None:
    assert _explicit_arguments_from_evidence(operation, evidence) is None


def test_explicit_arguments_cross_the_same_schema_and_grounding_boundary() -> None:
    schema = {
        "type": "object",
        "properties": {
            "level": {"type": "integer", "minimum": 0, "maximum": 100},
        },
        "required": ["level"],
        "additionalProperties": False,
    }

    assert _ground_explicit_arguments(
        "audio.volume",
        "pon el volumen al 8 por ciento",
        schema,
    ) == {"level": 8}
    assert (
        _ground_explicit_arguments(
            "audio.volume",
            "pon el volumen al 8 y luego al 12",
            schema,
        )
        is None
    )


def test_explicit_unmute_crosses_the_authenticated_boolean_schema() -> None:
    schema = {
        "type": "object",
        "properties": {"state": {"type": "boolean"}},
        "required": ["state"],
        "additionalProperties": False,
    }

    assert _ground_explicit_arguments(
        "audio.mute",
        "quita el mute del audio",
        schema,
    ) == {"state": False}


def test_authenticated_app_lists_bind_each_exact_name_without_llm() -> None:
    catalog = configure_application_catalog(
        {
            "version": 1,
            "verified": True,
            "complete": True,
            "names": ["Paint", "Spotify", "Visual Studio Code"],
        }
    )

    installed = [
        _explicit_arguments_from_evidence(
            "app.installed",
            evidence,
            catalog,
        )
        for evidence in ("paint", "spotify", "visual studio code")
    ]
    opened = [
        _explicit_arguments_from_evidence("app.open", evidence, catalog)
        for evidence in ("paint", "spotify", "visual studio code")
    ]

    assert installed == [
        {"name": "Paint"},
        {"name": "Spotify"},
        {"name": "Visual Studio Code"},
    ]
    assert opened == [
        {"appId": "Paint"},
        {"appId": "Spotify"},
        {"appId": "Visual Studio Code"},
    ]


def test_authenticated_game_catalog_binds_only_the_observed_app_id() -> None:
    entries = configure_game_catalog(
        {
            "version": 1,
            "verified": True,
            "complete": True,
            "entries": [
                {"provider": "steam", "appId": "730", "name": "Counter-Strike 2"},
                {"provider": "steam", "appId": "620", "name": "Portal 2"},
            ],
        }
    )
    catalog = build_game_catalog_index(entries)
    schema = {
        "type": "object",
        "properties": {"appId": {"type": "string"}},
        "required": ["appId"],
        "additionalProperties": False,
    }

    assert _ground_explicit_arguments(
        "game.launch",
        "Counter-Strike 2",
        schema,
        game_catalog=catalog,
    ) == {"appId": "730"}
    assert (
        _ground_explicit_arguments(
            "game.launch",
            "Unknown Game",
            schema,
            game_catalog=catalog,
        )
        is None
    )


def test_game_catalog_accepts_only_complete_or_empty_unverified_snapshots() -> None:
    assert (
        configure_game_catalog(
            {
                "version": 1,
                "verified": False,
                "complete": False,
                "entries": [],
            }
        )
        == ()
    )

    with pytest.raises(PlannerContractError):
        configure_game_catalog(
            {
                "version": 1,
                "verified": False,
                "complete": False,
                "entries": [
                    {"provider": "steam", "appId": "620", "name": "Portal 2"},
                ],
            }
        )

    with pytest.raises(PlannerContractError):
        configure_game_catalog(
            {
                "version": 1,
                "verified": True,
                "complete": True,
                "entries": [
                    {"provider": "steam", "appId": "620", "name": "Portal\t2"},
                ],
            }
        )


def test_coordinated_task_and_reminder_bind_names_and_clock_without_llm() -> None:
    task = _explicit_arguments_from_evidence(
        "task.create",
        "crea una tarea llamada alfa y un",
    )
    reminder = _explicit_arguments_from_evidence(
        "reminder.create",
        "recordatorio llamado beta para manana a las 9",
    )

    assert task == {"title": "alfa"}
    assert reminder is not None
    assert reminder["title"] == "beta"
    assert isinstance(reminder["dueUtc"], str)
    due = datetime.fromisoformat(reminder["dueUtc"].replace("Z", "+00:00")).astimezone()
    assert (due.hour, due.minute) == (9, 0)


def test_explicit_titles_preserve_original_case_accents_and_punctuation() -> None:
    task = _explicit_arguments_from_evidence(
        "task.create",
        "Crea una tarea llamada Informe Q3 / Café",
    )
    reminder = _explicit_arguments_from_evidence(
        "reminder.create",
        "Crea un recordatorio llamado Café Q3 / Review para mañana a las 9",
    )

    assert task == {"title": "Informe Q3 / Café"}
    assert reminder is not None
    assert reminder["title"] == "Café Q3 / Review"
    assert isinstance(reminder["dueUtc"], str)


def test_preserved_plan_effects_are_not_rejected_by_a_second_relevance_veto() -> None:
    proposal = SimpleNamespace(
        kind="plan",
        steps=(
            SimpleNamespace(operation="media.play.exact"),
            SimpleNamespace(operation="media.control"),
        ),
    )

    class AlwaysIrrelevantCatalog:
        @staticmethod
        def operation_is_relevant(_objective: str, _operation: str) -> bool:
            return False

    expected = ("media.play.exact", "media.control")
    assert (
        _irrelevant_plan_operations(
            proposal,
            "Reproduce exactamente una canción y después pausa",
            AlwaysIrrelevantCatalog(),  # type: ignore[arg-type]
            expected,
        )
        == []
    )


def test_exact_spotify_play_carries_its_source_into_following_control() -> None:
    plan = _explicit_plan_skeleton(
        ("media.play.exact", "media.control"),
        ("reproduce exactamente Beat It en Spotify", "pausa esa reproducción"),
    )

    assert plan["steps"][1]["purpose"] == "pausa esa reproducción en Spotify"


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("¿Cómo está la red neuronal?", "network.status"),
        ("¿Cómo está la red neuronal?", "media.status"),
        ("Silencia las notificaciones de Slack", "audio.mute"),
        ("Can you play a board game with me?", "media.play.query"),
        ("Can you play a game against us?", "media.play.exact"),
        ("Copia el texto que dice portapapeles", "clipboard.copy"),
        ("Haz una captura del ladrón", "capture.screenshot"),
        ("Haz una captura del ladrón", "window.resolve"),
        ("Lee la página 42 del documento", "browser.page.read"),
        ("Recarga la página del libro", "browser.control"),
        ("¿Qué canción está sonando en mi cabeza?", "media.status"),
    ],
)
def test_polysemous_domain_cues_cannot_grant_operation_authority(
    text: str,
    operation: str,
) -> None:
    result = apply_operation_domain_grounding_veto(
        {
            "mode": "action",
            "operation": operation,
            "question": "",
            "conversation_kind": "",
            "effect_count": "one",
            "effect_operations": [operation],
            "effect_verification": "primary",
            "response_language": "es",
        },
        text,
    )

    assert result["mode"] == "conversation"
    assert result["operation"] is None
    assert result["effect_operations"] == []
    assert result["effect_verification"] == "not_applicable"


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        (
            "Please déjame a Snapchat the whole desktop",
            "system.application.crash.diagnose",
        ),
        ("For the graph el desktop para pull out readable text", "filesystem.list"),
        ("Necesito an Excel sheet titulada Works of Costs", "clipboard.write.text"),
        ("Hazle saber a Elena que el paquete llegó", "reminder.resolve.exact"),
        (
            "Tell a story where Bluetooth is an imaginary city",
            "bluetooth.device.list",
        ),
        ("Write una theoretical checklist para organized tasks", "routine.list"),
    ],
)
def test_degraded_neighboring_domains_cannot_grant_operation_authority(
    text: str,
    operation: str,
) -> None:
    decision = {
        "mode": "action",
        "operation": operation,
        "question": "",
        "conversation_kind": "",
        "effect_count": "one",
        "effect_operations": [operation],
        "effect_verification": "agreed",
        "response_language": "es",
    }

    vetoed = apply_operation_domain_grounding_veto(decision, text)

    assert vetoed["mode"] == "conversation"
    assert vetoed["effect_operations"] == []


def test_independently_recovered_operation_survives_lexical_domain_veto() -> None:
    decision = {
        "mode": "action",
        "operation": "calendar.event.list",
        "question": "",
        "conversation_kind": "",
        "effect_count": "one",
        "effect_operations": ["calendar.event.list"],
        "effect_verification": "recovered",
        "response_language": "es",
    }

    assert (
        apply_operation_domain_grounding_veto(
            decision,
            "Lugares para ir después de la medianoche",
        )
        == decision
    )


def test_recovered_game_launch_requires_authenticated_installed_identity() -> None:
    catalog = build_game_catalog_index((("steam", "730", "Counter-Strike 2"),))
    decision = {
        "mode": "action",
        "operation": "game.launch",
        "question": "",
        "conversation_kind": "",
        "effect_count": "one",
        "effect_operations": ["game.launch"],
        "effect_verification": "recovered",
        "response_language": "en",
    }

    assert (
        apply_operation_domain_grounding_veto(
            decision,
            "Launch Counter Strike from Steam",
            game_catalog=catalog,
        )
        == decision
    )
    vetoed = apply_operation_domain_grounding_veto(
        decision,
        "Launch Portal from Steam",
        game_catalog=catalog,
    )
    assert vetoed["mode"] == "conversation"
    assert vetoed["conversation_kind"] == "unsupported"
    assert vetoed["effect_operations"] == []


def test_application_launch_requires_authenticated_installed_identity() -> None:
    applications = effect_intent_module.build_application_catalog_index(
        ("Bloc de notas", "Google Chrome")
    )
    decision = {
        "mode": "action",
        "operation": "app.open",
        "question": "",
        "conversation_kind": "",
        "effect_count": "one",
        "effect_operations": ["app.open"],
        "effect_verification": "recovered",
        "response_language": "en",
    }

    assert (
        apply_operation_domain_grounding_veto(
            decision,
            "Open Chrome",
            application_names=applications,
        )
        == decision
    )
    vetoed = apply_operation_domain_grounding_veto(
        decision,
        "Open VLC",
        EffectIntent(("app.open",), ("vlc",)),
        applications,
    )
    assert vetoed["mode"] == "conversation"
    assert vetoed["conversation_kind"] == "unsupported"
    assert vetoed["effect_operations"] == []


def test_explicit_open_survives_when_start_catalog_publishes_the_installed_name() -> None:
    applications = effect_intent_module.build_application_catalog_index(
        ("Steam", "Google Chrome")
    )
    decision = {
        "mode": "action",
        "operation": "app.open",
        "question": "",
        "conversation_kind": "",
        "effect_count": "one",
        "effect_operations": ["app.open"],
        "effect_verification": "recovered",
        "response_language": "es",
    }

    assert (
        apply_operation_domain_grounding_veto(
            decision,
            "Abre Steam.",
            EffectIntent(("app.open",), ("steam",)),
            applications,
        )
        == decision
    )
    assert _explicit_arguments_from_evidence(
        "app.open",
        "steam",
        applications,
    ) == {"appId": "Steam"}


def test_application_argument_grounding_uses_authenticated_provider_identity() -> None:
    applications = ("Bloc de notas", "Calculadora", "Google Chrome")

    assert _explicit_arguments_from_evidence(
        "app.open",
        "notepad",
        applications,
    ) == {"appId": "windows.notepad"}
    assert _explicit_arguments_from_evidence(
        "app.open",
        "chrome",
        applications,
    ) == {"appId": "Google Chrome"}
    assert (
        _explicit_arguments_from_evidence(
            "app.open",
            "vlc",
            applications,
        )
        is None
    )
    schema = {
        "type": "object",
        "properties": {"appId": {"type": "string"}},
        "required": ["appId"],
        "additionalProperties": False,
    }
    assert _ground_explicit_arguments(
        "app.open",
        "Open Notepad",
        schema,
        applications,
    ) == {"appId": "windows.notepad"}


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("¿Cómo está la red?", "network.status"),
        ("Silencia el audio", "audio.mute"),
        ("Haz una captura de pantalla", "capture.screenshot"),
        ("Lee la página actual", "browser.page.read"),
        ("Recarga la página", "browser.control"),
        ("¿Qué música está sonando?", "media.status"),
        ("Copia texto de Notepad al portapapeles", "clipboard.copy"),
    ],
)
def test_literal_operation_domains_preserve_valid_authority(
    text: str,
    operation: str,
) -> None:
    decision = {
        "mode": "action",
        "operation": operation,
        "question": "",
        "conversation_kind": "",
        "effect_count": "one",
        "effect_operations": [operation],
        "effect_verification": "primary",
        "response_language": "es",
    }
    assert apply_operation_domain_grounding_veto(decision, text) == decision


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        (
            "Lista los fallos recientes de las aplicaciones",
            "system.application.crash.diagnose",
        ),
        ("Lista los archivos del sandbox", "filesystem.list"),
        ("Escribe hola en el portapapeles", "clipboard.write.text"),
        ("Recordatorios de cumpleaños", "reminder.resolve.exact"),
        ("Lista los dispositivos Bluetooth", "bluetooth.device.list"),
        ("Muestra mis rutinas guardadas", "routine.list"),
    ],
)
def test_new_literal_operation_domains_preserve_valid_authority(
    text: str,
    operation: str,
) -> None:
    decision = {
        "mode": "action",
        "operation": operation,
        "question": "",
        "conversation_kind": "",
        "effect_count": "one",
        "effect_operations": [operation],
        "effect_verification": "agreed",
        "response_language": "es",
    }

    assert apply_operation_domain_grounding_veto(decision, text) == decision


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("apagame el bluetooth", "bluetooth.radio.set"),
        ("drop the wireless connection", "wifi.disconnect"),
    ],
)
def test_measured_paraphrases_keep_authority_when_the_domain_is_named(
    text: str,
    operation: str,
) -> None:
    decision = {
        "mode": "action",
        "operation": operation,
        "question": "",
        "conversation_kind": "",
        "effect_count": "one",
        "effect_operations": [operation],
        "effect_verification": "primary",
        "response_language": "es",
    }

    assert apply_operation_domain_grounding_veto(decision, text) == decision
    assert decision["effect_operations"] == [operation]


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("pide un taxi al aeropuerto", "task.create"),
        ("Barre las hojas del sendero", "filesystem.sandbox.append.named"),
        ("¿Cómo está la red neuronal?", "network.status"),
        ("cambiame el fondo de escritorio", "backup.known.restore.latest"),
        ("commit and push my changes to git", "game.install.commit"),
    ],
)
def test_out_of_catalogue_requests_do_not_keep_unsolicited_effects(
    text: str,
    operation: str,
) -> None:
    vetoed = apply_operation_domain_grounding_veto(
        {
            "mode": "action",
            "operation": operation,
            "question": "",
            "conversation_kind": "",
            "effect_count": "one",
            "effect_operations": [operation],
            "effect_verification": "primary",
            "response_language": "es",
        },
        text,
    )

    assert vetoed["effect_operations"] == []
    assert vetoed["mode"] == "conversation"


def test_message_dispatch_cannot_degrade_to_recipient_resolution_only() -> None:
    decision = {
        "mode": "action",
        "operation": "message.recipient.resolve",
        "question": "",
        "conversation_kind": "",
        "effect_count": "one",
        "effect_operations": ["message.recipient.resolve"],
        "effect_verification": "agreed",
        "response_language": "es",
    }

    vetoed = apply_operation_domain_grounding_veto(
        decision,
        "On Discord avise a Kerrike Moved Don North Room",
    )

    assert vetoed["mode"] == "conversation"
    assert vetoed["effect_operations"] == []


@pytest.mark.parametrize(
    "text",
    (
        "Busca el contacto Ana en WhatsApp",
        "Resolve the Music recipient on Discord",
    ),
)
def test_recipient_lookup_without_dispatch_remains_resolvable(text: str) -> None:
    decision = {
        "mode": "action",
        "operation": "message.recipient.resolve",
        "question": "",
        "conversation_kind": "",
        "effect_count": "one",
        "effect_operations": ["message.recipient.resolve"],
        "effect_verification": "agreed",
        "response_language": "es",
    }

    assert apply_operation_domain_grounding_veto(decision, text) == decision


def test_vague_enable_everything_cannot_target_a_system_setting() -> None:
    operation = "system.settings.set"
    decision = {
        "mode": "action",
        "operation": operation,
        "question": "",
        "conversation_kind": "",
        "effect_count": "one",
        "effect_operations": [operation],
        "effect_verification": "primary",
        "response_language": "es",
    }

    vetoed = apply_operation_domain_grounding_veto(
        decision,
        "Deja todo lo que suma activado",
    )

    assert vetoed["mode"] == "conversation"
    assert vetoed["effect_operations"] == []


def test_clause_grounded_explicit_compound_survives_whole_text_domain_veto() -> None:
    operations = ["system.status", "system.process.list"]
    decision = {
        "mode": "plan",
        "operation": None,
        "question": "",
        "conversation_kind": "",
        "effect_count": "multiple",
        "effect_operations": operations,
        "effect_verification": "multiple",
        "response_language": "en",
    }
    intent = EffectIntent(tuple(operations), ("ram usage", "active processes"))

    assert (
        apply_operation_domain_grounding_veto(
            decision,
            "Tell me the computer RAM usage and then list the active processes.",
            intent,
        )
        == decision
    )


def test_partial_compound_domains_are_checked_clause_by_clause() -> None:
    assert (
        effect_intent_module.operation_domain_is_grounded(
            "Get Spotify running",
            "app.open",
            ("Spotify",),
        )
        is True
    )
    decision = {
        "mode": "plan",
        "operation": None,
        "question": "",
        "conversation_kind": "",
        "effect_count": "multiple",
        "effect_operations": ["app.open", "message.send"],
        "effect_verification": "multiple",
        "response_language": "en",
    }
    contract = CompoundEffectContract(
        2,
        (),
        (
            ("i need you to open spotify", ()),
            ("send lucas the message hello", ()),
        ),
    )

    assert (
        apply_operation_domain_grounding_veto(
            decision,
            "I need you to open Spotify, then send Lucas the message hello.",
            None,
            ("Spotify",),
            contract,
        )
        == decision
    )

    wrong = dict(decision)
    wrong["effect_operations"] = ["app.open", "app.open"]
    vetoed = apply_operation_domain_grounding_veto(
        wrong,
        "I need you to open Spotify, then send Lucas the message hello.",
        None,
        ("Spotify",),
        contract,
    )
    assert vetoed["mode"] == "conversation"
    assert vetoed["effect_operations"] == []


def test_proven_compound_application_clause_keeps_authenticated_identity() -> None:
    decision = {
        "mode": "plan",
        "operation": None,
        "question": "",
        "conversation_kind": "",
        "effect_count": "multiple",
        "effect_operations": ["app.open", "message.send"],
        "effect_verification": "multiple",
        "response_language": "en",
    }
    contract = CompoundEffectContract(
        2,
        (("app.open",),),
        (
            ("i need you to open spotify", ("app.open",)),
            ("send lucas the message hello", ()),
        ),
    )

    assert (
        apply_operation_domain_grounding_veto(
            decision,
            "I need you to open Spotify, then send Lucas the message hello.",
            None,
            ("Spotify",),
            contract,
        )
        == decision
    )


def test_proven_compound_clause_repairs_only_its_model_nominated_slot() -> None:
    decision = {
        "mode": "plan",
        "operation": None,
        "question": "",
        "conversation_kind": "",
        "effect_count": "multiple",
        "effect_operations": ["media.play.exact", "message.send"],
        "effect_verification": "multiple",
        "response_language": "en",
    }
    contract = CompoundEffectContract(
        2,
        (("app.open",),),
        (
            ("get spotify running", ("app.open",)),
            ("tell lucas hello on whatsapp", ()),
        ),
    )

    repaired = apply_operation_domain_grounding_veto(
        decision,
        "Get Spotify running and then tell Lucas hello on WhatsApp.",
        None,
        ("Spotify",),
        contract,
    )

    assert repaired["mode"] == "plan"
    assert repaired["effect_operations"] == ["app.open", "message.send"]


def test_explicit_domain_bypass_requires_the_exact_recognized_sequence() -> None:
    decision = {
        "mode": "action",
        "operation": "capture.screenshot",
        "question": "",
        "conversation_kind": "",
        "effect_count": "one",
        "effect_operations": ["capture.screenshot"],
        "effect_verification": "primary",
        "response_language": "es",
    }
    different_intent = EffectIntent(("window.resolve",), ("ladrón",))

    result = apply_operation_domain_grounding_veto(
        decision,
        "Haz una captura del ladrón",
        different_intent,
    )

    assert result["mode"] == "conversation"
    assert result["effect_operations"] == []


def test_partial_semantic_compound_cannot_receive_action_authority() -> None:
    partial = {
        "mode": "plan",
        "operation": None,
        "question": "",
        "conversation_kind": "",
        "effect_count": "one",
        "effect_operations": ["note.create"],
        "effect_verification": "disagreement",
        "response_language": "es",
    }

    result = apply_compound_effect_conservation_veto(
        partial,
        CompoundEffectContract(2, (("note.create",),)),
    )

    assert result["mode"] == "conversation"
    assert result["effect_operations"] == []
    assert result["effect_verification"] == "not_applicable"


def test_complete_semantic_compound_can_fill_an_unresolved_clause() -> None:
    complete = {
        "mode": "plan",
        "operation": None,
        "question": "",
        "conversation_kind": "",
        "effect_count": "multiple",
        "effect_operations": ["app.open", "message.send"],
        "effect_verification": "multiple",
        "response_language": "es",
    }

    class Compatible:
        calls: list[tuple[str, str]] = []

        def _compound_clause_is_fully_compatible(
            self,
            clause: str,
            operation: str,
            _contract: dict[str, object],
        ) -> bool:
            self.calls.append((clause, operation))
            return operation == "message.send"

    verifier = Compatible()
    result = apply_compound_effect_conservation_veto(
        complete,
        CompoundEffectContract(
            2,
            (("app.open",),),
            (
                ("abre spotify", ("app.open",)),
                ("envia el informe a lucas", ()),
            ),
        ),
        {
            "message.send": {
                "function": {
                    "description": "Send a message.",
                    "parameters": {
                        "type": "object",
                        "properties": {"recipient": {"type": "string"}},
                        "required": ["recipient"],
                    },
                },
            },
        },
        verifier,
    )
    assert result == complete
    assert verifier.calls == [("envia el informe a lucas", "message.send")]


def test_unverified_unresolved_compound_operation_never_receives_authority() -> None:
    proposal = {
        "mode": "plan",
        "operation": None,
        "question": "",
        "conversation_kind": "",
        "effect_count": "multiple",
        "effect_operations": ["app.open", "system.power"],
        "effect_verification": "multiple",
        "response_language": "es",
    }

    class RejectingVerifier:
        @staticmethod
        def _compound_clause_is_fully_compatible(*_args: object) -> bool:
            return False

    result = apply_compound_effect_conservation_veto(
        proposal,
        CompoundEffectContract(
            2,
            (("app.open",),),
            (("abre spotify", ("app.open",)), ("haz lo otro", ())),
        ),
        {
            "system.power": {
                "function": {
                    "description": "Control system power.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            },
        },
        RejectingVerifier(),
    )

    assert result["mode"] == "conversation"
    assert result["effect_operations"] == []


def test_compound_clause_compatibility_runs_with_bounded_parallelism() -> None:
    barrier = threading.Barrier(2)
    seen: list[str] = []

    def compatible(
        clause: str,
        _operation: str,
        _contract: dict[str, object],
    ) -> bool:
        seen.append(clause)
        barrier.wait(timeout=1.0)
        return True

    assert mind_main._compound_compatibility_all(
        compatible,
        [
            ("first", "app.open", {}),
            ("second", "message.send", {}),
        ],
    )
    assert set(seen) == {"first", "second"}


def test_parallel_compound_verification_retires_unused_speculation() -> None:
    class Runtime:
        language_retired = 0
        count_retired = 0

        def _retire_deferred_language_work(self) -> None:
            self.language_retired += 1

        def _retire_deferred_count_work(self) -> None:
            self.count_retired += 1

    runtime = Runtime()
    assert mind_main._prepare_parallel_compound_verification(
        runtime,
        [("one", "app.open", {}), ("two", "message.send", {})],
    )
    assert (runtime.language_retired, runtime.count_retired) == (1, 1)


def test_semantic_compound_must_preserve_every_recognized_clause() -> None:
    substituted = {
        "mode": "plan",
        "operation": None,
        "question": "",
        "conversation_kind": "",
        "effect_count": "multiple",
        "effect_operations": ["message.send", "web.search"],
        "effect_verification": "multiple",
        "response_language": "es",
    }
    result = apply_compound_effect_conservation_veto(
        substituted,
        CompoundEffectContract(2, (("app.open",),)),
    )
    assert result["mode"] == "conversation"
    assert result["effect_operations"] == []


def test_dependent_action_defers_verified_identity_to_the_planner() -> None:
    decision = {
        "mode": "action",
        "operation": "ocr.read",
        "question": "",
        "conversation_kind": "",
        "effect_count": "one",
        "effect_operations": ["ocr.read"],
        "effect_verification": "grounding_required",
        "response_language": "es",
    }
    tool = {
        "function": {
            "parameters": {
                "type": "object",
                "properties": {"captureId": {"type": "string"}},
                "required": ["captureId"],
                "additionalProperties": False,
            }
        }
    }

    result = apply_turn_action_grounding_gate(
        decision,
        "lee el texto de mi pantalla",
        {"ocr.read": tool},
        object(),
    )

    assert result["mode"] == "plan"
    assert result["effect_operations"] == ["ocr.read"]
    assert result["effect_verification"] == "disagreement"


def test_explicit_dependent_action_still_defers_identity_to_the_planner() -> None:
    decision = {
        "mode": "action",
        "operation": "message.send",
        "question": "",
        "conversation_kind": "",
        "effect_count": "one",
        "effect_operations": ["message.send"],
        "effect_verification": "recovered",
        "response_language": "es",
    }
    tool = {
        "function": {
            "parameters": {
                "type": "object",
                "properties": {
                    "recipientId": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["recipientId", "text"],
                "additionalProperties": False,
            }
        }
    }

    result = apply_turn_action_grounding_gate(
        decision,
        "Dile a Ana por WhatsApp que llegaré tarde.",
        {"message.send": tool},
        object(),
        ground_recovered=False,
    )

    assert result["mode"] == "plan"
    assert result["effect_operations"] == ["message.send"]
    assert result["effect_verification"] == "disagreement"


def test_note_dependency_prefers_verified_opaque_identity_over_title() -> None:
    note_id = "5f1be84a-2af2-4cb7-8a73-172ba30e19f4"

    assert _normalize_grounded_operation_arguments(
        "note.read",
        {"noteId": note_id, "title": "Prueba"},
    ) == {"noteId": note_id}


def test_side_effect_free_turn_assigns_each_logical_attempt() -> None:
    attempts: list[int] = []
    calls = 0

    def operation() -> dict:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("transient")
        return {"type": "turn.result"}

    result = _retry_side_effect_free_turn(
        operation,
        before_attempt=attempts.append,
    )

    assert result["turn_attempts"] == 2
    assert attempts == [0, 1]


def test_turn_attempt_and_recovery_budgets_fit_desktop_transport_sla() -> None:
    assert TURN_DECIDE_ATTEMPT_BUDGET_SECONDS == TURN_DECIDE_NORMAL_BUDGET_SECONDS
    assert (
        TURN_DECIDE_NORMAL_BUDGET_SECONDS + TURN_DECIDE_RECOVERY_BUDGET_SECONDS
        < TURN_DECIDE_TRANSPORT_SLA_SECONDS
    )


def test_turn_resolves_explicit_effects_only_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = {
        "type": "function",
        "function": {
            "name": "system_time",
            "canonical_name": "system.time",
            "description": "Read the current local time.",
            "risk": "read_only",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    }
    catalog = PlannerCatalog([tool])
    resolutions = 0
    real_resolver = effect_intent_module.resolve_explicit_effects

    def counted_resolver(*args: object, **kwargs: object):
        nonlocal resolutions
        resolutions += 1
        return real_resolver(*args, **kwargs)

    class NoEvidence:
        @staticmethod
        def candidate_families(
            text: str,
            encoder: object,
        ) -> tuple[str, ...]:
            del text, encoder
            raise AssertionError("explicit effects do not rank E5 families")

        @staticmethod
        def retrieve(*args: object, **kwargs: object) -> list[object]:
            raise AssertionError("explicit effects do not retrieve evidence")

    class ExplicitCatalog:
        # El audit del turno registra si el catálogo vivo rankea con E5 o
        # sólo con solapamiento de tokens. Un doble también lo declara.
        ranks_semantically = False

        tools = catalog.tools

        @staticmethod
        def get(operation: str):
            return catalog.get(operation)

        @staticmethod
        def shortlist(*args: object, **kwargs: object):
            raise AssertionError("explicit effects do not rank an E5 shortlist")

        @staticmethod
        def operation_is_relevant(*args: object, **kwargs: object):
            raise AssertionError("recovered explicit effects do not need E5")

    monkeypatch.setattr(
        mind_main,
        "resolve_explicit_effects",
        counted_resolver,
    )
    monkeypatch.setattr(
        effect_intent_module,
        "resolve_explicit_effects",
        counted_resolver,
    )

    def encoder_should_not_run(_texts: object) -> None:
        raise AssertionError("lexical catalog must not call the encoder")

    result = _prepare_turn_result(
        {"id": "turn-1", "text": "What time is it?"},
        llm=object(),
        planner_catalog=ExplicitCatalog(),
        turn_evidence=NoEvidence(),
        encoder=encoder_should_not_run,
        tool_by_name={"system.time": tool},
    )

    assert resolutions == 1
    assert result["kind"] == "action"
    assert result["operation"] == "system.time"
    assert result["intentOperations"] == ["system.time"]
    assert result["effectOperations"] == ["system.time"]


@pytest.mark.parametrize(
    "text",
    [
        "yes or no tomorrow's temperature is to be hot",
        "temperature outside",
        "olly what is the weather forecast for today",
    ],
)
def test_live_weather_feed_is_closed_before_model_selection(text: str) -> None:
    tool = {
        "type": "function",
        "function": {
            "name": "web_search",
            "canonical_name": "web.search",
            "description": "Search public information and verify the result.",
            "risk": "read_only",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "x-nonWhitespace": True},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    }
    catalog = PlannerCatalog([tool])

    class NoEvidence:
        @staticmethod
        def candidate_families(*_args: object) -> tuple[str, ...]:
            raise AssertionError("a literal live feed must not rank families")

        @staticmethod
        def retrieve(*_args: object) -> list[object]:
            raise AssertionError("a literal live feed must not retrieve evidence")

    class NoModel:
        @staticmethod
        def decide_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
            raise AssertionError("the literal live feed must own the turn")

        @staticmethod
        def retire_deferred_response_language(_text: str) -> None:
            return None

    result = _prepare_turn_result(
        {
            "id": "live-weather",
            "text": text,
        },
        llm=NoModel(),
        planner_catalog=catalog,
        turn_evidence=NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name={"web.search": tool},
    )

    assert result["kind"] == "action"
    assert result["operation"] == "web.search"
    assert result["intentOperations"] == ["web.search"]
    assert result["effectOperations"] == ["web.search"]


@pytest.mark.parametrize(
    "text",
    [
        "Quien es Batman?",
        "Cual es el ultimo Mortal Kombat que salio?",
        "what is the capital of Nigeria?",
    ],
)
def test_public_fact_question_is_closed_before_model_selection(text: str) -> None:
    tool = {
        "type": "function",
        "function": {
            "name": "web_search",
            "canonical_name": "web.search",
            "description": "Search public information and verify the result.",
            "risk": "read_only",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "x-nonWhitespace": True},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    }
    catalog = PlannerCatalog([tool])

    class NoEvidence:
        @staticmethod
        def candidate_families(*_args: object) -> tuple[str, ...]:
            raise AssertionError("a public fact must not rank families")

        @staticmethod
        def retrieve(*_args: object) -> list[object]:
            raise AssertionError("a public fact must not retrieve evidence")

    class NoModel:
        @staticmethod
        def decide_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
            raise AssertionError("the verified public lookup must own the turn")

        @staticmethod
        def retire_deferred_response_language(_text: str) -> None:
            return None

    result = _prepare_turn_result(
        {"id": "public-fact", "text": text},
        llm=NoModel(),
        planner_catalog=catalog,
        turn_evidence=NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name={"web.search": tool},
    )

    assert result["kind"] == "action"
    assert result["operation"] == "web.search"
    assert result["intentOperations"] == ["web.search"]
    assert result["effectOperations"] == ["web.search"]


def test_explicit_message_payload_future_tense_preserves_intent_identity() -> None:
    tool = {
        "type": "function",
        "function": {
            "name": "message_send",
            "canonical_name": "message.send",
            "description": "Send a message through a desktop channel.",
            "risk": "external_side_effect",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    }
    catalog = PlannerCatalog([tool])

    class NoEvidence:
        @staticmethod
        def candidate_families(*_args: object) -> tuple[str, ...]:
            raise AssertionError("explicit effects do not rank candidates")

        @staticmethod
        def retrieve(*_args: object) -> list[object]:
            raise AssertionError("explicit effects do not retrieve evidence")

    class NoModel:
        @staticmethod
        def decide_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
            raise AssertionError("the explicit effect must own the turn")

        @staticmethod
        def retire_deferred_response_language(_text: str) -> None:
            return None

    result = _prepare_turn_result(
        {
            "id": "message-future-payload",
            "text": ("Send Music the WhatsApp message ‘I will arrive in ten minutes’."),
        },
        llm=NoModel(),
        planner_catalog=catalog,
        turn_evidence=NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name={"message.send": tool},
    )

    assert result["kind"] == "plan"
    assert result["intentOperations"] == ["message.send"]
    assert result["effectOperations"] == ["message.send"]


def test_explicit_incomplete_effect_uses_only_model_authored_question() -> None:
    tool = {
        "type": "function",
        "function": {
            "name": "reminder_create",
            "canonical_name": "reminder.create",
            "description": "Create a durable local reminder.",
            "risk": "low_reversible",
            "parameters": {
                "type": "object",
                "properties": {
                    "dueUtc": {"type": "string"},
                    "title": {"type": "string"},
                },
                "required": ["dueUtc", "title"],
                "additionalProperties": False,
            },
        },
    }
    calls: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = []

    class NoEvidence:
        @staticmethod
        def candidate_families(*_args: object) -> tuple[str, ...]:
            raise AssertionError("explicit clarification must not retrieve")

        @staticmethod
        def retrieve(*_args: object) -> list[object]:
            raise AssertionError("explicit clarification must not retrieve")

    class Runtime:
        @staticmethod
        def formulate_explicit_clarification_question(
            objective: str,
            operations: tuple[str, ...],
            missing_fields: tuple[str, ...],
        ) -> str:
            calls.append((objective, operations, missing_fields))
            return "¿Cuándo quieres que te lo recuerde?"

    result = _prepare_turn_result(
        {
            "id": "explicit-reminder-clarification",
            "text": "ponme un recordatorio para llamar al dentista",
        },
        llm=Runtime(),
        planner_catalog=PlannerCatalog([tool]),
        turn_evidence=NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name={"reminder.create": tool},
    )

    assert calls == [
        (
            "ponme un recordatorio para llamar al dentista",
            ("reminder.create",),
            ("due_time",),
        )
    ]
    assert result["kind"] == "clarify"
    assert result["intentOperations"] == ["reminder.create"]
    assert result["effectOperations"] == []
    assert result["question"] == "¿Cuándo quieres que te lo recuerde?"


@pytest.mark.parametrize(
    ("user_request", "operation"),
    [
        ("subí el volumen", "audio.volume.adjust"),
        ("bajá el brillo", "system.settings.adjust"),
        ("raise the brightness", "system.settings.adjust"),
    ],
)
def test_relative_adjustment_clarification_only_requests_the_missing_amount(
    user_request: str,
    operation: str,
) -> None:
    clarification = effect_intent_module.resolve_explicit_clarification_intent(
        user_request,
        (operation,),
    )

    assert clarification is not None
    assert clarification.operations == (operation,)
    assert clarification.missing_fields == ("amount",)


def test_bare_song_request_clarifies_the_query_without_authorizing_playback() -> None:
    clarification = effect_intent_module.resolve_explicit_clarification_intent(
        "poné una canción",
        ("media.play.query",),
    )

    assert clarification is not None
    assert clarification.operations == ("media.play.query",)
    assert clarification.missing_fields == ("query",)


def test_explicit_social_turn_does_not_compute_unused_semantic_candidates() -> None:
    catalog = PlannerCatalog(
        [
            {
                "type": "function",
                "function": {
                    "name": "system_time",
                    "canonical_name": "system.time",
                    "description": "Read the current local time.",
                    "risk": "read_only",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                        "additionalProperties": False,
                    },
                },
            }
        ]
    )

    class NoSemanticWork:
        # El audit del turno registra si el catálogo vivo rankea con E5 o
        # sólo con solapamiento de tokens. Un doble también lo declara.
        ranks_semantically = False

        tools = catalog.tools

        @staticmethod
        def shortlist(*args: object, **kwargs: object):
            raise AssertionError("social turns do not rank an E5 shortlist")

        @staticmethod
        def operation_is_relevant(*args: object, **kwargs: object):
            raise AssertionError("social turns do not apply operation relevance")

    class NoEvidence:
        @staticmethod
        def candidate_families(*args: object, **kwargs: object):
            raise AssertionError("social turns do not rank E5 families")

        @staticmethod
        def retrieve(*args: object, **kwargs: object):
            raise AssertionError("social turns do not retrieve evidence")

    class SocialLlm:
        @staticmethod
        def detect_response_language(_text: str) -> str:
            raise AssertionError("closed social turns already know their language")

        @staticmethod
        def chat(*args: object, **kwargs: object) -> tuple[str, list[object]]:
            assert kwargs["response_language"] == "es"
            return "Hola.", []

    def encoder_should_not_run(_texts: object) -> None:
        raise AssertionError("social turns do not cross the E5 process")

    result = _prepare_turn_result(
        {
            "id": "turn-social",
            "text": "Hola.",
            "history": [
                {
                    "role": "assistant",
                    "content": "Sí, estoy aquí. ¿En qué puedo ayudarte?",
                }
            ],
        },
        llm=SocialLlm(),
        planner_catalog=NoSemanticWork(),
        turn_evidence=NoEvidence(),
        encoder=encoder_should_not_run,
        tool_by_name={},
    )

    assert result["kind"] == "conversation"
    assert result["reply"] == "Hola."


@pytest.mark.parametrize("deferred_language", ["es", None])
def test_outer_action_veto_reuses_valid_language_and_retries_only_failure(
    deferred_language: str | None,
) -> None:
    tool = {
        "type": "function",
        "function": {
            "name": "network_status",
            "canonical_name": "network.status",
            "description": "Read the current network status.",
            "risk": "read_only",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    }
    catalog = PlannerCatalog([tool])

    class Evidence:
        @staticmethod
        def candidate_families(
            _text: str,
            _encoder: object,
        ) -> tuple[str, ...]:
            return ()

        @staticmethod
        def retrieve(*_args: object, **_kwargs: object) -> list[object]:
            return []

    class DeferredLlm:
        consumed = 0
        detected = 0
        retired = 0

        @staticmethod
        def decide_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
            return {
                "mode": "action",
                "operation": "network.status",
                "question": "",
                "conversation_kind": "",
                "effect_count": "one",
                "effect_operations": ["network.status"],
                "effect_verification": "agreed",
                "response_language": "es",
            }

        @staticmethod
        def _verify_semantic_effect_shape(
            _text: str,
        ) -> tuple[str, str]:
            return "no_effect", "zero"

        @classmethod
        def consume_deferred_response_language(
            cls,
            _text: str,
        ) -> tuple[bool, str | None]:
            cls.consumed += 1
            return True, deferred_language

        @classmethod
        def retire_deferred_response_language(cls, _text: str) -> None:
            cls.retired += 1

        @classmethod
        def detect_response_language(cls, _text: str) -> str:
            cls.detected += 1
            return "en"

        @staticmethod
        def chat(*_args: object, **kwargs: object) -> tuple[str, list[object]]:
            assert kwargs["response_language"] == (
                deferred_language if deferred_language is not None else "en"
            )
            return "Es una red neuronal, no el estado de la red del equipo.", []

    result = _prepare_turn_result(
        {
            "id": "turn-veto",
            "text": "¿Cómo está la red neuronal?",
        },
        llm=DeferredLlm(),
        planner_catalog=catalog,
        turn_evidence=Evidence(),
        encoder=lambda _texts: (),
        tool_by_name={"network.status": tool},
    )

    assert result["kind"] == "conversation"
    assert result["reply"]
    assert DeferredLlm.consumed == 1
    assert DeferredLlm.detected == (1 if deferred_language is None else 0)
    assert DeferredLlm.retired == 0


def test_outer_final_action_cancels_deferred_language_only_after_all_vetoes() -> None:
    tool = {
        "type": "function",
        "function": {
            "name": "fixture_read",
            "canonical_name": "fixture.read",
            "description": "Read a fixture.",
            "risk": "read_only",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    }
    catalog = PlannerCatalog([tool])

    class RelevantCatalog:
        # El audit del turno registra si el catálogo vivo rankea con E5 o
        # sólo con solapamiento de tokens. Un doble también lo declara.
        ranks_semantically = False

        tools = catalog.tools

        @staticmethod
        def shortlist(_objective: str) -> tuple[object, ...]:
            return catalog.tools

        @staticmethod
        def operation_is_relevant(
            _objective: str,
            _operation: str,
        ) -> bool:
            return True

    class Evidence:
        @staticmethod
        def candidate_families(
            _text: str,
            _encoder: object,
        ) -> tuple[str, ...]:
            return ()

        @staticmethod
        def retrieve(*_args: object, **_kwargs: object) -> list[object]:
            return []

    class DeferredLlm:
        retired = 0

        @staticmethod
        def decide_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
            return {
                "mode": "action",
                "operation": "fixture.read",
                "question": "",
                "conversation_kind": "",
                "effect_count": "one",
                "effect_operations": ["fixture.read"],
                "effect_verification": "agreed",
                "response_language": "en",
            }

        @classmethod
        def retire_deferred_response_language(cls, _text: str) -> None:
            cls.retired += 1

        @staticmethod
        def consume_deferred_response_language(
            _text: str,
        ) -> tuple[bool, str | None]:
            raise AssertionError("a final action must not consume L")

        @staticmethod
        def detect_response_language(_text: str) -> str:
            raise AssertionError("a final action does not need language")

        @staticmethod
        def chat(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("a final action does not generate chat")

    result = _prepare_turn_result(
        {"id": "turn-action", "text": "fixture request"},
        llm=DeferredLlm(),
        planner_catalog=RelevantCatalog(),
        turn_evidence=Evidence(),
        encoder=lambda _texts: (),
        tool_by_name={"fixture.read": tool},
    )

    assert result["kind"] == "action"
    assert result["operation"] == "fixture.read"
    assert DeferredLlm.retired == 1


def test_turn_decision_is_the_only_public_open_conversation_request() -> None:
    requests = protocol.hello({"llm": "fixture"})["requests"]
    root = Path(__file__).resolve().parents[1]
    view_model = (root / "src/Baxy.App/MainWindowViewModel.cs").read_text(
        encoding="utf-8"
    )
    client = (root / "src/Baxy.App/MindSidecarClient.cs").read_text(encoding="utf-8")

    assert "turn.decide" in requests
    assert "chat" not in requests
    assert "TryMindConversationAsync" not in view_model
    assert "ChatAsync(" not in client


def test_catalog_warmup_must_succeed_before_ready_is_promised() -> None:
    class ColdRuntime:
        @staticmethod
        def wait_warmup(timeout: float) -> bool:
            assert timeout == CATALOG_LLM_WARMUP_SECONDS
            return False

    with pytest.raises(RuntimeError, match="LLM"):
        _require_catalog_llm_ready(ColdRuntime())

    assert CATALOG_LLM_WARMUP_SECONDS < CATALOG_REQUEST_BUDGET_SECONDS
    assert CATALOG_REQUEST_BUDGET_SECONDS < MIND_STARTUP_TRANSPORT_SLA_SECONDS
    assert ARGUMENT_REQUEST_BUDGET_SECONDS == 19.25


def test_initial_planner_resources_do_not_touch_optional_encoder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel_skills = object()

    monkeypatch.setattr(
        "baxy_mind.__main__.SkillRegistry.load_default",
        lambda operations, encoder=None: sentinel_skills,
    )
    catalog, skills = _create_planner_resources(
        [
            {
                "type": "function",
                "function": {
                    "name": "system_time",
                    "canonical_name": "system.time",
                    "description": "Consulta la hora local.",
                    "risk": "read_only",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                        "additionalProperties": False,
                    },
                },
            }
        ],
    )

    assert catalog.tools[0].name == "system.time"
    assert catalog._encoder is None
    assert skills is sentinel_skills


def test_expected_plan_skips_unused_e5_and_skill_retrieval() -> None:
    first = SimpleNamespace(name="identity.windows.active")
    second = SimpleNamespace(name="window.close")

    class ClosedCatalog:
        @staticmethod
        def get(operation: str):
            return {
                first.name: first,
                second.name: second,
            }.get(operation)

        @staticmethod
        def shortlist(*_args: object, **_kwargs: object):
            raise AssertionError("closed effects do not rank an E5 shortlist")

    class NoEvidence:
        @staticmethod
        def candidate_families(*_args: object, **_kwargs: object):
            raise AssertionError("closed effects do not rank E5 families")

    class NoSkills:
        @staticmethod
        def select(*_args: object, **_kwargs: object):
            raise AssertionError("closed effects do not select skills")

    def encoder_must_not_run(_texts: object) -> None:
        raise AssertionError("closed effects do not cross the E5 process")

    shortlist, guidance = _prepare_plan_prompt_resources(
        "cierra la ventana activa",
        (first.name, second.name),
        ClosedCatalog(),  # type: ignore[arg-type]
        NoSkills(),  # type: ignore[arg-type]
    )

    assert shortlist == (first, second)
    assert guidance == ""


def test_inferred_plan_preserves_e5_and_skill_retrieval() -> None:
    selected = SimpleNamespace(name="window.close")
    calls: list[object] = []

    class OpenCatalog:
        @staticmethod
        def shortlist(objective: str):
            calls.append(("shortlist", objective))
            return (selected,)

    class Skills:
        @staticmethod
        def select(objective: str, operations: list[str]):
            calls.append(("skills", objective, operations))
            return ()

    shortlist, guidance = _prepare_plan_prompt_resources(
        "cierra la ventana activa",
        (),
        OpenCatalog(),  # type: ignore[arg-type]
        Skills(),  # type: ignore[arg-type]
    )

    assert shortlist == (selected,)
    assert guidance == ""
    # La expansión de familias por evidencia ya no existe: el shortlist rankea
    # operaciones directamente y las habilidades se eligen sobre ese resultado.
    assert calls == [
        ("shortlist", "cierra la ventana activa"),
        ("skills", "cierra la ventana activa", ["window.close"]),
    ]


def test_failed_turn_recovers_with_candidate_free_semantic_question() -> None:
    calls: list[object] = []

    class RecoveryRuntime:
        @staticmethod
        def clarify_after_turn_failure(
            text: str,
            *,
            history: object,
            timeout: float,
        ) -> str:
            calls.append((text, history, timeout))
            return "¿Qué quieres que aclare o haga?"

    result = _recover_failed_turn(
        {
            "id": "turn-1",
            "text": "Haz eso",
            "history": [{"role": "assistant", "content": "¿Qué necesitas?"}],
        },
        RecoveryRuntime(),
        failure_kinds=("runtime", "contract"),
    )

    assert result == {
        "type": "turn.result",
        "id": "turn-1",
        "kind": "clarify",
        "operation": None,
        "intentOperations": [],
        "effectOperations": [],
        "preserveObjective": False,
        "question": "¿Qué quieres que aclare o haga?",
        "reply": "",
        "turn_attempts": 2,
        "turn_recovery": "semantic_clarification",
        "recovery_attempts": 1,
        "failure_code": "turn_runtime_failure",
    }
    assert calls == [
        (
            "Haz eso",
            [{"role": "assistant", "content": "¿Qué necesitas?"}],
            2.5,
        )
    ]


@pytest.mark.parametrize(
    "text",
    [
        "Haz eso",
        "hazlo, por favor",
        "Ábrela",
        "Abre eso",
        "Open that",
        "Dale con esto",
        "Do that",
        "Please make it happen",
        "Go ahead with it",
    ],
)
def test_bare_deictic_conversation_requires_model_authored_referent_question(
    text: str,
) -> None:
    conversation = {"mode": "conversation"}
    plan = {"mode": "plan"}
    action = {"mode": "action"}

    assert mind_main._standalone_deictic_conversation_needs_clarification(
        text,
        conversation,
    )
    assert mind_main._standalone_deictic_conversation_needs_clarification(
        text,
        plan,
    )
    assert not mind_main._standalone_deictic_conversation_needs_clarification(
        text,
        action,
    )


def test_cpu_bare_deictic_route_uses_its_measured_clarification_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BAXY_MIND_NGL", "0")
    tool = {
        "type": "function",
        "function": {
            "name": "system_time",
            "canonical_name": "system.time",
            "description": "Read local time.",
            "risk": "read_only",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    }
    observed: list[float] = []

    class NoEvidence:
        @staticmethod
        def candidate_families(*_args: object) -> tuple[str, ...]:
            raise AssertionError("bare deictic clarification must not rank actions")

        @staticmethod
        def retrieve(*_args: object) -> list[object]:
            raise AssertionError(
                "bare deictic clarification must not retrieve evidence"
            )

    class Runtime:
        @staticmethod
        def clarify_missing_referent(
            _text: str,
            *,
            timeout: float,
        ) -> str:
            observed.append(timeout)
            return "¿Qué acción concreta quieres que haga?"

        @staticmethod
        def chat(*_args: object, **_kwargs: object) -> tuple[str, list[object]]:
            raise AssertionError("the clarification must close before chat")

    result = _prepare_turn_result(
        {
            "id": "cpu-deictic",
            "text": "Haz eso",
            "history": [
                {"role": "assistant", "content": "La palabra era Nimbo8202."},
                {"role": "user", "content": "Haz eso"},
            ],
        },
        llm=Runtime(),
        planner_catalog=PlannerCatalog([tool]),
        turn_evidence=NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name={},
    )

    assert observed == [mind_main.DEICTIC_CLARIFICATION_CPU_BUDGET_SECONDS]
    assert result["kind"] == "clarify"
    assert result["question"] == "¿Qué acción concreta quieres que haga?"
    assert result["reply"] == ""


@pytest.mark.parametrize(
    "text",
    [
        "Haz una copia de seguridad",
        "Do that after opening Steam",
        "Dale con la música",
        "¿Qué significa eso?",
    ],
)
def test_specific_or_nonimperative_references_do_not_trigger_bare_deictic_guard(
    text: str,
) -> None:
    assert not mind_main._standalone_deictic_conversation_needs_clarification(
        text,
        {"mode": "conversation"},
    )


def test_failed_turn_recovery_never_fabricates_protocol_prose() -> None:
    histories: list[object] = []

    class RecoveryRuntime:
        @staticmethod
        def clarify_after_turn_failure(
            _text: str,
            *,
            history: object,
            timeout: float,
        ) -> str:
            histories.append((history, timeout))
            raise TimeoutError("transient")

    result = _recover_failed_turn(
        {
            "id": "turn-2",
            "text": "Do that",
            "history": [{"role": "assistant", "content": "What should I do?"}],
            "uiLanguage": "en-US",
        },
        RecoveryRuntime(),
    )

    assert histories == [
        ([{"role": "assistant", "content": "What should I do?"}], 2.5),
    ]
    assert result["kind"] == "conversation"
    assert result["operation"] is None
    assert result["question"] == ""
    assert result["reply"] == ""
    assert result["turn_recovery"] == "protocol_fallback"
    assert result["preserveObjective"] is False
    assert result["recovery_attempts"] == 1
    assert result["failure_code"] == "turn_unavailable"


@pytest.mark.parametrize("language", ["es", "en"])
def test_failed_turn_protocol_fallback_has_zero_action_authority_and_no_text(
    language: str,
) -> None:
    class FailedRuntime:
        @staticmethod
        def clarify_after_turn_failure(
            _text: str,
            *,
            history: object,
            timeout: float,
        ) -> str:
            del history, timeout
            raise RuntimeError("offline")

    result = _recover_failed_turn(
        {
            "id": "turn-3",
            "text": "ambiguous",
            "history": [],
            "uiLanguage": language,
        },
        FailedRuntime(),
        failure_kinds=("runtime", "runtime"),
    )

    assert result["type"] == "turn.result"
    assert result["kind"] == "conversation"
    assert result["operation"] is None
    assert result["reply"] == ""
    assert result["question"] == ""
    assert result["turn_attempts"] == 2
    assert result["turn_recovery"] == "protocol_fallback"
    assert result["preserveObjective"] is False
    assert result["recovery_attempts"] == 1
    assert result["failure_code"] == "turn_runtime_failure"


def test_failed_turn_protocol_fallback_never_publishes_empty_clarify() -> None:
    class InvalidQuestionRuntime:
        @staticmethod
        def clarify_after_turn_failure(
            _text: str,
            *,
            history: object,
            timeout: float,
        ) -> str:
            del history, timeout
            return "   "

        @staticmethod
        def compose_user_message(
            _user_text: str,
            _intent: str,
            _facts: object,
        ) -> str:
            return "I could not finish reading that request."

    result = _recover_failed_turn(
        {
            "id": "turn-compose",
            "text": "what is on my to do list",
            "history": [],
            "uiLanguage": "en-US",
        },
        InvalidQuestionRuntime(),
        failure_kinds=("runtime", "runtime"),
    )

    assert result["kind"] == "conversation"
    assert result["question"] == ""
    assert result["reply"] == "I could not finish reading that request."
    assert result["turn_recovery"] == "protocol_fallback"
    assert result["operation"] is None
    assert result["effectOperations"] == []


def test_recovery_compose_question_is_published_as_clarify() -> None:
    class QuestionComposeRuntime:
        @staticmethod
        def clarify_after_turn_failure(
            _text: str,
            *,
            history: object,
            timeout: float,
        ) -> str:
            del history, timeout
            return ""

        @staticmethod
        def compose_user_message(
            _user_text: str,
            _intent: str,
            _facts: object,
        ) -> str:
            return "What is on your to do list?"

    result = _recover_failed_turn(
        {
            "id": "turn-compose-question",
            "text": "what is on my to do list",
            "history": [],
            "uiLanguage": "en-US",
        },
        QuestionComposeRuntime(),
        failure_kinds=("runtime", "runtime"),
    )

    assert result["kind"] == "clarify"
    assert result["question"] == "What is on your to do list?"
    assert result["reply"] == ""
    assert result["turn_recovery"] == "semantic_clarification"
    assert result["operation"] is None
    assert result["effectOperations"] == []


def test_failed_turn_protocol_fallback_is_textless_without_language_model() -> None:
    result = _recover_failed_turn(
        {
            "id": "turn-4",
            "text": object(),
            "history": object(),
            "uiLanguage": "unsupported",
        },
        None,
        attempts=0,
    )

    assert result["kind"] == "conversation"
    assert result["operation"] is None
    assert result["question"] == ""
    assert result["reply"] == ""
    assert result["turn_recovery"] == "protocol_fallback"
    assert result["preserveObjective"] is False
    assert result["turn_attempts"] == 0
    assert result["recovery_attempts"] == 0
    assert result["failure_code"] == "turn_unavailable"


def test_closed_conversation_recovery_cannot_invent_clarification() -> None:
    calls: list[dict[str, object]] = []

    class RecoveryRuntime:
        @staticmethod
        def chat(
            text: str,
            history: object,
            tools: object,
            temperature: float,
            *,
            conversation_kind: str,
            authenticated_operations: tuple[str, ...],
            response_language: str | None,
        ) -> tuple[str, list[dict[str, object]]]:
            calls.append(
                {
                    "text": text,
                    "history": history,
                    "tools": tools,
                    "temperature": temperature,
                    "conversation_kind": conversation_kind,
                    "authenticated_operations": authenticated_operations,
                    "response_language": response_language,
                }
            )
            return "Soy BAXY, un asistente local.", []

        @staticmethod
        def clarify_after_turn_failure(*_args: object, **_kwargs: object) -> str:
            raise AssertionError("a clear identity question has no missing field")

    result = _recover_failed_turn(
        {
            "id": "turn-clear-identity",
            "text": "Quien eres tu?",
            "history": [
                {
                    "role": "assistant",
                    "content": "¿Quieres que restaure una ventana?",
                }
            ],
        },
        RecoveryRuntime(),
        failure_kinds=("contract", "contract"),
    )

    assert result["kind"] == "conversation"
    assert result["question"] == ""
    assert result["reply"] == "Soy BAXY, un asistente local."
    assert result["intentOperations"] == []
    assert result["effectOperations"] == []
    assert result["preserveObjective"] is False
    assert calls == [
        {
            "text": "Quien eres tu?",
            "history": [],
            "tools": None,
            "temperature": 0.2,
            "conversation_kind": "knowledge",
            "authenticated_operations": (),
            "response_language": "es",
        }
    ]


def guard_response(
    *,
    has_effect: bool = True,
    unresolved: bool = False,
    effect_count: str = "one",
    request_type: str | None = None,
) -> dict[str, object]:
    if request_type is None:
        request_type = (
            "stable_conversation"
            if not has_effect
            else "incomplete_effect"
            if unresolved
            else "environment_change"
        )
    return {
        "request_type": request_type,
        "effect_count": effect_count,
    }


class _DeferredCountExecutor:
    """Keep V queued until shutdown so cancellation races are deterministic."""

    def __init__(self, max_workers: int, **_kwargs: object) -> None:
        assert max_workers == 3
        self._submission = 0
        self._policy_release = threading.Event()
        self._queued_started = threading.Event()
        self._queued: (
            tuple[
                Future,
                Callable[..., object],
                tuple[object, ...],
                dict[str, object],
            ]
            | None
        ) = None
        self._threads: list[threading.Thread] = []
        self.shutdown_calls: list[tuple[bool, bool]] = []

    @staticmethod
    def _complete(
        future: Future,
        callback: Callable[..., object],
        args: tuple[object, ...],
        kwargs: dict[str, object],
        started: threading.Event | None = None,
    ) -> None:
        if not future.set_running_or_notify_cancel():
            return
        if started is not None:
            started.set()
        try:
            result = callback(*args, **kwargs)
        except BaseException as error:
            future.set_exception(error)
        else:
            future.set_result(result)

    def submit(
        self,
        callback: Callable[..., object],
        *args: object,
        **kwargs: object,
    ) -> Future:
        self._submission += 1
        future: Future = Future()
        if self._submission == 1:

            def complete_policy() -> None:
                assert self._policy_release.wait(timeout=2.0)
                self._complete(future, callback, args, kwargs)

            thread = threading.Thread(target=complete_policy, daemon=True)
            self._threads.append(thread)
            thread.start()
        elif self._submission in {2, 3}:
            self._complete(future, callback, args, kwargs)
        elif self._submission == 4:
            self._queued = (future, callback, args, kwargs)
            self._policy_release.set()
        else:
            raise AssertionError("unexpected scheduler submission")
        return future

    def shutdown(
        self,
        wait: bool = True,
        *,
        cancel_futures: bool = False,
    ) -> None:
        self.shutdown_calls.append((wait, cancel_futures))
        queued = self._queued
        if queued is not None:
            future, callback, args, kwargs = queued
            if cancel_futures:
                future.cancel()
            else:
                thread = threading.Thread(
                    target=self._complete,
                    args=(
                        future,
                        callback,
                        args,
                        kwargs,
                        self._queued_started,
                    ),
                    daemon=True,
                )
                self._threads.append(thread)
                thread.start()
                assert self._queued_started.wait(timeout=2.0)
        if wait:
            for thread in self._threads:
                thread.join(timeout=2.0)


def test_reactive_action_tail_overlaps_only_after_dependencies_are_ready() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._parallel_turn_verification = True
    runtime._speculative_knowledge_enabled = False
    runtime._semantic_effect_cache = {}
    runtime._response_language_cache = {}
    runtime._speculative_chat_handoff = None
    initial_rendezvous = threading.Barrier(3, timeout=2.0)
    language_release = threading.Event()
    count_started = threading.Event()
    count_release = threading.Event()
    count_finished = threading.Event()
    compatibility_started = threading.Event()
    labels: list[str] = []
    state_lock = threading.Lock()
    active = 0
    maximum_active = 0
    policy_label = "la pol\u00edtica de turno"
    guard_label = "el veto sem\u00e1ntico de efectos"
    language_label = "la detecci\u00f3n de idioma"
    count_label = "la verificaci\u00f3n independiente del conteo de efectos"
    compatibility_label = "la verificaci\u00f3n de compatibilidad de la operaci\u00f3n"
    initial_labels = {
        policy_label,
        guard_label,
        language_label,
    }

    def constrained(_payload: dict, label: str) -> dict:
        nonlocal active, maximum_active
        with state_lock:
            labels.append(label)
            active += 1
            maximum_active = max(maximum_active, active)
        try:
            if label in initial_labels:
                initial_rendezvous.wait()
            if label == policy_label:
                return {
                    "mode": "action",
                    "operation": "app.open",
                    "question": "",
                    "conversation_kind": "",
                    "effect_count": "one",
                    "effect_operations": ["app.open"],
                    "response_language": "es",
                }
            if label == guard_label:
                return guard_response(effect_count="one")
            if label == language_label:
                assert language_release.wait(timeout=2.0)
                return {"language": "es"}
            if label == count_label:
                count_started.set()
                assert count_release.wait(timeout=2.0)
                count_finished.set()
                return {"effect_count": "one"}
            assert label == compatibility_label
            assert count_finished.is_set()
            assert not language_release.is_set()
            compatibility_started.set()
            return {"compatible": False}
        finally:
            with state_lock:
                active -= 1

    runtime._post_schema_object = constrained  # type: ignore[method-assign]
    outcome: dict[str, object] = {}
    failures: list[BaseException] = []

    def decide() -> None:
        try:
            outcome.update(
                runtime.decide_turn(
                    "Abre la calculadora.",
                    [
                        turn_candidate(
                            "app.open",
                            "Abre una app por nombre.",
                            required=("appId",),
                        )
                    ],
                )
            )
        except BaseException as error:
            failures.append(error)

    worker = threading.Thread(target=decide, daemon=True)
    worker.start()
    try:
        assert count_started.wait(timeout=2.0)
        assert not language_release.is_set()
        assert not compatibility_started.is_set()
        count_release.set()
        assert compatibility_started.wait(timeout=2.0)
    finally:
        count_release.set()
        language_release.set()
        worker.join(timeout=3.0)

    assert not worker.is_alive()
    assert failures == []
    assert outcome["mode"] == "action"
    assert outcome["effect_verification"] == "grounding_required"
    assert labels.count(count_label) == 1
    assert labels.count(compatibility_label) == 1
    assert maximum_active == 3


def test_effect_guard_releases_its_slot_to_count_before_policy_finishes() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._parallel_turn_verification = True
    runtime._speculative_count_after_guard = True
    runtime._speculative_knowledge_enabled = False
    runtime._semantic_effect_cache = {}
    runtime._response_language_cache = {}
    runtime._speculative_chat_handoff = None
    runtime._completion_cancellation_state = threading.local()
    initial_rendezvous = threading.Barrier(3, timeout=2.0)
    policy_release = threading.Event()
    language_release = threading.Event()
    count_started = threading.Event()
    count_release = threading.Event()
    compatibility_started = threading.Event()
    labels: list[str] = []
    state_lock = threading.Lock()
    active = 0
    maximum_active = 0
    policy_label = "la pol\u00edtica de turno"
    guard_label = "el veto sem\u00e1ntico de efectos"
    language_label = "la detecci\u00f3n de idioma"
    count_label = "la verificaci\u00f3n independiente del conteo de efectos"
    compatibility_label = "la verificaci\u00f3n de compatibilidad de la operaci\u00f3n"
    initial_labels = {policy_label, guard_label, language_label}

    def constrained(_payload: dict, label: str) -> dict:
        nonlocal active, maximum_active
        with state_lock:
            labels.append(label)
            active += 1
            maximum_active = max(maximum_active, active)
        try:
            if label in initial_labels:
                initial_rendezvous.wait()
            if label == guard_label:
                return guard_response(effect_count="one")
            if label == policy_label:
                assert policy_release.wait(timeout=2.0)
                return {
                    "mode": "action",
                    "operation": "app.open",
                    "question": "",
                    "conversation_kind": "",
                    "effect_count": "one",
                    "effect_operations": ["app.open"],
                    "response_language": "es",
                }
            if label == language_label:
                assert language_release.wait(timeout=2.0)
                return {"language": "es"}
            if label == count_label:
                count_started.set()
                assert count_release.wait(timeout=2.0)
                return {"effect_count": "one"}
            assert label == compatibility_label
            compatibility_started.set()
            return {"compatible": True}
        finally:
            with state_lock:
                active -= 1

    runtime._post_schema_object = constrained  # type: ignore[method-assign]
    outcome: dict[str, object] = {}
    failures: list[BaseException] = []

    def decide() -> None:
        try:
            outcome.update(
                runtime.decide_turn(
                    "Abre la calculadora.",
                    [
                        turn_candidate(
                            "app.open",
                            "Abre una app por nombre.",
                            required=("appId",),
                        )
                    ],
                )
            )
        except BaseException as error:
            failures.append(error)

    worker = threading.Thread(target=decide, daemon=True)
    worker.start()
    try:
        assert count_started.wait(timeout=2.0)
        assert not policy_release.is_set()
        assert not compatibility_started.is_set()
        policy_release.set()
        count_release.set()
        assert compatibility_started.wait(timeout=2.0)
    finally:
        policy_release.set()
        count_release.set()
        language_release.set()
        worker.join(timeout=3.0)

    assert not worker.is_alive()
    assert failures == []
    assert outcome["mode"] == "action"
    assert outcome["effect_verification"] == "agreed"
    assert labels.count(count_label) == 1
    assert labels.count(compatibility_label) == 1
    assert maximum_active == 3


def test_guard_failure_cancels_running_policy_without_waiting() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._parallel_turn_verification = True
    runtime._speculative_count_after_guard = True
    runtime._speculative_knowledge_enabled = False
    runtime._semantic_effect_cache = {}
    runtime._response_language_cache = {}
    runtime._speculative_chat_handoff = None
    runtime._deferred_language_work = None
    runtime._deferred_count_work = None
    runtime._completion_cancellation_state = threading.local()
    rendezvous = threading.Barrier(3, timeout=2.0)
    policy_cancelled = threading.Event()
    policy_label = "la política de turno"
    guard_label = "el veto semántico de efectos"
    language_label = "la detección de idioma"

    def constrained(_payload: dict, label: str) -> dict:
        assert label in {policy_label, guard_label, language_label}
        cancellation = runtime._completion_cancellation_state.current
        rendezvous.wait()
        if label == guard_label:
            raise RuntimeError("guard failed")
        if label == language_label:
            return {"language": "es"}
        deadline = time.monotonic() + 2.0
        while not cancellation.cancelled and time.monotonic() < deadline:
            time.sleep(0.001)
        assert cancellation.cancelled
        policy_cancelled.set()
        cancellation.raise_if_cancelled()
        raise AssertionError("cancelled policy unexpectedly continued")

    runtime._post_schema_object = constrained  # type: ignore[method-assign]

    started = time.perf_counter()
    with pytest.raises(RuntimeError, match="guard failed"):
        runtime._decide_turn("Hola", [])
    elapsed = time.perf_counter() - started

    assert elapsed < 1.0
    assert policy_cancelled.wait(timeout=1.0)


def test_policy_failure_cancels_running_guard_without_waiting() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._parallel_turn_verification = True
    runtime._speculative_count_after_guard = True
    runtime._speculative_knowledge_enabled = False
    runtime._semantic_effect_cache = {}
    runtime._response_language_cache = {}
    runtime._speculative_chat_handoff = None
    runtime._deferred_language_work = None
    runtime._deferred_count_work = None
    runtime._completion_cancellation_state = threading.local()
    rendezvous = threading.Barrier(3, timeout=2.0)
    guard_cancelled = threading.Event()
    policy_label = "la política de turno"
    guard_label = "el veto semántico de efectos"
    language_label = "la detección de idioma"

    def constrained(_payload: dict, label: str) -> dict:
        assert label in {policy_label, guard_label, language_label}
        cancellation = runtime._completion_cancellation_state.current
        rendezvous.wait()
        if label == policy_label:
            raise RuntimeError("policy failed")
        if label == language_label:
            return {"language": "es"}
        deadline = time.monotonic() + 2.0
        while not cancellation.cancelled and time.monotonic() < deadline:
            time.sleep(0.001)
        assert cancellation.cancelled
        guard_cancelled.set()
        cancellation.raise_if_cancelled()
        raise AssertionError("cancelled guard unexpectedly continued")

    runtime._post_schema_object = constrained  # type: ignore[method-assign]

    started = time.perf_counter()
    with pytest.raises(RuntimeError, match="policy failed"):
        runtime._decide_turn("Hola", [])
    elapsed = time.perf_counter() - started

    assert elapsed < 1.0
    assert guard_cancelled.wait(timeout=1.0)


def test_recovered_conversation_reuses_speculative_count_once() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._parallel_turn_verification = True
    runtime._speculative_count_after_guard = True
    runtime._speculative_knowledge_enabled = False
    runtime._semantic_effect_cache = {}
    runtime._response_language_cache = {}
    runtime._speculative_chat_handoff = None
    runtime._completion_cancellation_state = threading.local()
    initial_rendezvous = threading.Barrier(3, timeout=2.0)
    policy_release = threading.Event()
    count_started = threading.Event()
    count_release = threading.Event()
    labels: list[str] = []
    labels_lock = threading.Lock()
    policy_label = "la pol\u00edtica de turno"
    guard_label = "el veto sem\u00e1ntico de efectos"
    language_label = "la detecci\u00f3n de idioma"
    count_label = "la verificaci\u00f3n independiente del conteo de efectos"
    selector_label = "la selecci\u00f3n cerrada de un efecto"
    compatibility_label = "la verificaci\u00f3n de compatibilidad de la operaci\u00f3n"

    def constrained(_payload: dict, label: str) -> dict:
        with labels_lock:
            labels.append(label)
        if label in {policy_label, guard_label, language_label}:
            initial_rendezvous.wait()
        if label == guard_label:
            return guard_response(effect_count="one")
        if label == policy_label:
            assert policy_release.wait(timeout=2.0)
            return {
                "mode": "conversation",
                "operation": "",
                "question": "",
                "conversation_kind": "unsupported",
                "effect_count": "zero",
                "effect_operations": [],
                "response_language": "es",
            }
        if label == language_label:
            return {"language": "es"}
        if label == count_label:
            count_started.set()
            assert count_release.wait(timeout=2.0)
            return {"effect_count": "one"}
        if label == selector_label:
            return {"operation": "app.open"}
        assert label == compatibility_label
        return {"compatible": True}

    runtime._post_schema_object = constrained  # type: ignore[method-assign]
    outcome: dict[str, object] = {}
    failures: list[BaseException] = []

    def decide() -> None:
        try:
            outcome.update(
                runtime.decide_turn(
                    "Abre la calculadora.",
                    [
                        turn_candidate(
                            "app.open",
                            "Abre una app por nombre.",
                            required=("appId",),
                        )
                    ],
                )
            )
        except BaseException as error:
            failures.append(error)

    worker = threading.Thread(target=decide, daemon=True)
    worker.start()
    try:
        assert count_started.wait(timeout=2.0)
        policy_release.set()
        count_release.set()
    finally:
        policy_release.set()
        count_release.set()
        worker.join(timeout=3.0)

    assert not worker.is_alive()
    assert failures == []
    assert outcome["mode"] == "action"
    assert outcome["effect_verification"] == "recovered"
    assert labels.count(count_label) == 1
    assert labels.count(selector_label) == 1
    assert labels.count(compatibility_label) == 1


def test_recovered_conversation_preserves_a_count_queued_at_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executors: list[_DeferredCountExecutor] = []

    class RecordingExecutor(_DeferredCountExecutor):
        def __init__(self, max_workers: int, **kwargs: object) -> None:
            super().__init__(max_workers, **kwargs)
            executors.append(self)

    monkeypatch.setattr(llm_module, "ThreadPoolExecutor", RecordingExecutor)
    runtime = object.__new__(LlmRuntime)
    runtime._parallel_turn_verification = True
    runtime._speculative_count_after_guard = True
    runtime._speculative_knowledge_enabled = False
    runtime._semantic_effect_cache = {}
    runtime._response_language_cache = {}
    runtime._speculative_chat_handoff = None
    runtime._deferred_language_work = None
    runtime._deferred_count_work = None
    runtime._completion_cancellation_state = threading.local()
    labels: list[str] = []
    policy_label = "la pol\u00edtica de turno"
    guard_label = "el veto sem\u00e1ntico de efectos"
    language_label = "la detecci\u00f3n de idioma"
    count_label = "la verificaci\u00f3n independiente del conteo de efectos"
    selector_label = "la selecci\u00f3n cerrada de un efecto"
    compatibility_label = "la verificaci\u00f3n de compatibilidad de la operaci\u00f3n"

    def constrained(_payload: dict, label: str) -> dict:
        labels.append(label)
        if label == policy_label:
            return {
                "mode": "conversation",
                "operation": "",
                "question": "",
                "conversation_kind": "unsupported",
                "effect_count": "zero",
                "effect_operations": [],
                "response_language": "es",
            }
        if label == guard_label:
            return guard_response(effect_count="one")
        if label == language_label:
            return {"language": "es"}
        if label == count_label:
            return {"effect_count": "one"}
        if label == selector_label:
            return {"operation": "app.open"}
        assert label == compatibility_label
        return {"compatible": True}

    runtime._post_schema_object = constrained  # type: ignore[method-assign]

    result = runtime.decide_turn(
        "Abre la calculadora.",
        [
            turn_candidate(
                "app.open",
                "Abre una app por nombre.",
                required=("appId",),
            )
        ],
    )

    assert result["mode"] == "action"
    assert result["effect_verification"] == "recovered"
    assert labels.count(count_label) == 1
    assert len(executors) == 1
    assert executors[0].shutdown_calls == [(False, False)]
    assert runtime._deferred_count_work is None


def test_downstream_failure_cancels_deferred_count_without_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executors: list[_DeferredCountExecutor] = []

    class RecordingExecutor(_DeferredCountExecutor):
        def __init__(self, max_workers: int, **kwargs: object) -> None:
            super().__init__(max_workers, **kwargs)
            executors.append(self)

    monkeypatch.setattr(llm_module, "ThreadPoolExecutor", RecordingExecutor)
    runtime = object.__new__(LlmRuntime)
    runtime._parallel_turn_verification = True
    runtime._speculative_count_after_guard = True
    runtime._speculative_knowledge_enabled = False
    runtime._semantic_effect_cache = {}
    runtime._response_language_cache = {}
    runtime._speculative_chat_handoff = None
    runtime._deferred_language_work = None
    runtime._deferred_count_work = None
    runtime._completion_cancellation_state = threading.local()
    count_cancelled = threading.Event()
    policy_label = "la pol\u00edtica de turno"
    guard_label = "el veto sem\u00e1ntico de efectos"
    language_label = "la detecci\u00f3n de idioma"
    count_label = "la verificaci\u00f3n independiente del conteo de efectos"
    selector_label = "la selecci\u00f3n cerrada de un efecto"

    def constrained(_payload: dict, label: str) -> dict:
        if label == policy_label:
            return {
                "mode": "conversation",
                "operation": "",
                "question": "",
                "conversation_kind": "unsupported",
                "effect_count": "zero",
                "effect_operations": [],
                "response_language": "es",
            }
        if label == guard_label:
            return guard_response(effect_count="one")
        if label == language_label:
            return {"language": "es"}
        if label == count_label:
            cancellation = runtime._completion_cancellation_state.current
            deadline = time.monotonic() + 2.0
            while not cancellation.cancelled and time.monotonic() < deadline:
                time.sleep(0.001)
            assert cancellation.cancelled
            count_cancelled.set()
            cancellation.raise_if_cancelled()
        assert label == selector_label
        raise RuntimeError("selector failed")

    runtime._post_schema_object = constrained  # type: ignore[method-assign]

    started = time.perf_counter()
    with pytest.raises(RuntimeError, match="selector failed"):
        runtime.decide_turn(
            "Abre la calculadora.",
            [
                turn_candidate(
                    "app.open",
                    "Abre una app por nombre.",
                    required=("appId",),
                )
            ],
        )
    elapsed = time.perf_counter() - started

    assert elapsed < 1.0
    assert count_cancelled.wait(timeout=1.0)
    assert len(executors) == 1
    assert executors[0].shutdown_calls == [(False, False)]
    assert runtime._deferred_count_work is None


def test_clarify_cancels_unused_speculative_count_without_waiting() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._parallel_turn_verification = True
    runtime._speculative_count_after_guard = True
    runtime._speculative_knowledge_enabled = False
    runtime._semantic_effect_cache = {}
    runtime._response_language_cache = {}
    runtime._speculative_chat_handoff = None
    runtime._completion_cancellation_state = threading.local()
    initial_rendezvous = threading.Barrier(3, timeout=2.0)
    count_started = threading.Event()
    count_cancelled = threading.Event()
    policy_label = "la pol\u00edtica de turno"
    guard_label = "el veto sem\u00e1ntico de efectos"
    language_label = "la detecci\u00f3n de idioma"
    count_label = "la verificaci\u00f3n independiente del conteo de efectos"

    def constrained(_payload: dict, label: str) -> dict:
        if label in {policy_label, guard_label, language_label}:
            initial_rendezvous.wait()
        if label == guard_label:
            return guard_response(effect_count="one")
        if label == language_label:
            return {"language": "es"}
        if label == policy_label:
            assert count_started.wait(timeout=2.0)
            return {
                "mode": "clarify",
                "operation": "",
                "question": "¿Qué aplicación quieres abrir?",
                "conversation_kind": "",
                "effect_count": "zero",
                "effect_operations": [],
                "response_language": "es",
            }
        assert label == count_label
        cancellation = runtime._completion_cancellation_state.current
        count_started.set()
        deadline = time.monotonic() + 2.0
        while not cancellation.cancelled and time.monotonic() < deadline:
            time.sleep(0.005)
        assert cancellation.cancelled
        count_cancelled.set()
        return {"effect_count": "one"}

    runtime._post_schema_object = constrained  # type: ignore[method-assign]

    started = time.perf_counter()
    result = runtime.decide_turn(
        "Abre una aplicación.",
        [turn_candidate("app.open", "Abre una app por nombre.")],
    )
    elapsed = time.perf_counter() - started

    assert result["mode"] == "clarify"
    assert elapsed < 1.0
    assert count_cancelled.wait(timeout=1.0)


def test_action_detaches_then_request_boundary_cancels_language_without_cache() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._parallel_turn_verification = True
    runtime._speculative_knowledge_enabled = False
    runtime._semantic_effect_cache = {}
    runtime._response_language_cache = {}
    runtime._speculative_chat_handoff = None
    runtime._deferred_language_work = None
    initial_rendezvous = threading.Barrier(3, timeout=2.0)
    language_started = threading.Event()
    language_finished = threading.Event()
    labels: list[str] = []
    state_lock = threading.Lock()
    active = 0
    maximum_active = 0

    def completion(value: dict[str, object]) -> dict[str, object]:
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(value, separators=(",", ":")),
                    }
                }
            ]
        }

    def post(
        payload: dict[str, object],
        *,
        cancellation: object | None = None,
    ) -> dict[str, object]:
        nonlocal active, maximum_active
        messages = payload["messages"]
        assert isinstance(messages, list)
        system = messages[0]["content"]
        assert isinstance(system, str)
        with state_lock:
            labels.append(system)
            active += 1
            maximum_active = max(maximum_active, active)
        try:
            if system in {
                TURN_POLICY_PROMPT,
                SEMANTIC_EFFECT_GUARD_PROMPT,
                RESPONSE_LANGUAGE_PROMPT,
            }:
                initial_rendezvous.wait()
            if system == RESPONSE_LANGUAGE_PROMPT:
                assert cancellation is not None
                language_started.set()
                while not getattr(cancellation, "cancelled"):
                    time.sleep(0.001)
                getattr(cancellation, "raise_if_cancelled")()
                raise AssertionError("cancelled language cannot publish a response")
            if system == TURN_POLICY_PROMPT:
                return completion(
                    {
                        "mode": "action",
                        "operation": "system.time",
                        "question": "",
                        "conversation_kind": "",
                        "effect_count": "one",
                        "effect_operations": ["system.time"],
                        "response_language": "es",
                    }
                )
            if system == SEMANTIC_EFFECT_GUARD_PROMPT:
                return completion(guard_response(effect_count="one"))
            assert system == EFFECT_COUNT_VERIFIER_PROMPT
            return completion({"effect_count": "one"})
        finally:
            if system == RESPONSE_LANGUAGE_PROMPT:
                language_finished.set()
            with state_lock:
                active -= 1

    runtime._post = post  # type: ignore[method-assign]
    text = "What time is it?"

    started_at = time.perf_counter()
    result = runtime.decide_turn(
        text,
        [turn_candidate("system.time", "Read the current local time.")],
    )
    elapsed = time.perf_counter() - started_at

    assert result["mode"] == "action"
    assert language_started.is_set()
    assert not language_finished.is_set()
    assert runtime._deferred_language_work is not None
    runtime.retire_deferred_response_language(text)
    assert language_finished.wait(timeout=1.0)
    assert elapsed < 0.75
    assert maximum_active == 3
    assert labels.count(RESPONSE_LANGUAGE_PROMPT) == 1
    assert text not in runtime._response_language_cache
    assert runtime._deferred_language_work is None


def test_action_veto_hands_the_same_language_future_to_outer_boundary() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._parallel_turn_verification = True
    runtime._speculative_knowledge_enabled = False
    runtime._semantic_effect_cache = {}
    runtime._response_language_cache = {}
    runtime._speculative_chat_handoff = None
    runtime._deferred_language_work = None
    language_started = threading.Event()
    language_release = threading.Event()
    count_finished = threading.Event()
    language_calls = 0

    def constrained(_payload: dict, label: str) -> dict:
        nonlocal language_calls
        if label == "la detección de idioma":
            language_calls += 1
            language_started.set()
            assert language_release.wait(timeout=2.0)
            return {"language": "en"}
        if label == "el veto semántico de efectos":
            return guard_response(effect_count="one")
        if label == "la verificación independiente del conteo de efectos":
            count_finished.set()
            return {"effect_count": "one"}
        assert label == "la política de turno"
        return {
            "mode": "action",
            "operation": "system.time",
            "question": "",
            "conversation_kind": "",
            "effect_count": "one",
            "effect_operations": ["system.time"],
            "response_language": "en",
        }

    runtime._post_schema_object = constrained  # type: ignore[method-assign]
    text = "Tell me why, not the current time."
    outcome: dict[str, object] = {}

    def decide() -> None:
        outcome.update(
            runtime.decide_turn(
                text,
                [turn_candidate("system.time", "Read the current local time.")],
                evidence=[
                    {
                        "mode": "conversation",
                        "families": [],
                        "score": 0.9,
                        "candidate_family_match": False,
                        "calibrated_conversation_probability": 0.99,
                    }
                ],
            )
        )

    worker = threading.Thread(target=decide, daemon=True)
    worker.start()
    try:
        assert language_started.wait(timeout=2.0)
        assert count_finished.wait(timeout=2.0)
        worker.join(timeout=1.0)
        assert not worker.is_alive()
        assert runtime._deferred_language_work is not None
    finally:
        if worker.is_alive():
            language_release.set()
            worker.join(timeout=2.0)

    assert outcome["mode"] == "conversation"
    consumed: list[tuple[bool, str | None]] = []
    consumer = threading.Thread(
        target=lambda: consumed.append(
            runtime.consume_deferred_response_language(text)
        ),
        daemon=True,
    )
    consumer.start()
    assert consumer.is_alive()
    language_release.set()
    consumer.join(timeout=2.0)
    assert not consumer.is_alive()
    assert consumed == [(True, "en")]
    assert language_calls == 1
    assert runtime._response_language_cache[text] == "en"
    assert runtime.detect_response_language(text) == "en"
    assert language_calls == 1
    assert runtime._deferred_language_work is None


@pytest.mark.parametrize(
    ("confirmed_count", "compatible"),
    [
        ("one", True),
        ("one", False),
        ("multiple", None),
    ],
)
def test_reactive_action_tail_is_decision_equivalent_without_extra_inferences(
    confirmed_count: str,
    compatible: bool | None,
) -> None:
    policy_label = "la pol\u00edtica de turno"
    guard_label = "el veto sem\u00e1ntico de efectos"
    language_label = "la detecci\u00f3n de idioma"
    count_label = "la verificaci\u00f3n independiente del conteo de efectos"
    compatibility_label = "la verificaci\u00f3n de compatibilidad de la operaci\u00f3n"

    def run(parallel: bool) -> tuple[dict[str, object], list[str]]:
        runtime = object.__new__(LlmRuntime)
        runtime._parallel_turn_verification = parallel
        runtime._speculative_knowledge_enabled = False
        runtime._semantic_effect_cache = {}
        runtime._response_language_cache = {}
        runtime._speculative_chat_handoff = None
        labels: list[str] = []
        labels_lock = threading.Lock()

        def constrained(_payload: dict, label: str) -> dict:
            with labels_lock:
                labels.append(label)
            if label == policy_label:
                return {
                    "mode": "action",
                    "operation": "app.open",
                    "question": "",
                    "conversation_kind": "",
                    "effect_count": "one",
                    "effect_operations": ["app.open"],
                    "response_language": "es",
                }
            if label == guard_label:
                return guard_response(effect_count="one")
            if label == language_label:
                return {"language": "es"}
            if label == count_label:
                return {"effect_count": confirmed_count}
            assert label == compatibility_label
            assert compatible is not None
            return {"compatible": compatible}

        runtime._post_schema_object = constrained  # type: ignore[method-assign]
        result = runtime.decide_turn(
            "Abre la calculadora.",
            [
                turn_candidate(
                    "app.open",
                    "Abre una app por nombre.",
                    required=("appId",),
                )
            ],
        )
        return result, labels

    sequential_result, sequential_labels = run(False)
    parallel_result, parallel_labels = run(True)

    assert parallel_result == sequential_result
    for labels in (sequential_labels, parallel_labels):
        assert labels.count(count_label) == 1
        assert labels.count(compatibility_label) == (
            0 if confirmed_count == "multiple" else 1
        )


def test_stable_knowledge_prepares_the_same_chat_while_policy_finishes() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._parallel_turn_verification = True
    runtime._speculative_knowledge_enabled = True
    runtime._semantic_effect_cache = {}
    runtime._response_language_cache = {}
    runtime._speculative_chat_handoff = None
    chat_calls: list[dict[str, object]] = []

    def constrained(_payload: dict, label: str) -> dict:
        if label == "la detección de idioma":
            return {"language": "es"}
        if label == "el veto semántico de efectos":
            return guard_response(has_effect=False, effect_count="zero")
        return {
            "mode": "conversation",
            "operation": "",
            "question": "",
            "conversation_kind": "knowledge",
            "effect_count": "zero",
            "effect_operations": [],
            "response_language": "es",
        }

    def chat(_text: str, **kwargs: object) -> tuple[str, list[dict]]:
        chat_calls.append(kwargs)
        return "La dispersión de la luz lo hace verse azul.", []

    runtime._post_schema_object = constrained  # type: ignore[method-assign]
    runtime.chat = chat  # type: ignore[method-assign]

    result = runtime.decide_turn("¿Por qué el cielo es azul?", [])

    assert result["mode"] == "conversation"
    assert len(chat_calls) == 1
    cancellation = chat_calls[0].pop("cancellation")
    assert getattr(cancellation, "cancelled") is False
    assert chat_calls == [
        {
            "history": [],
            "tools": None,
            "temperature": 0.0,
            "conversation_kind": "knowledge",
            "response_language": "es",
        }
    ]
    assert runtime._speculative_chat_handoff is not None


def test_social_policy_cancels_unused_knowledge_without_waiting_or_handoff() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._parallel_turn_verification = True
    runtime._speculative_knowledge_enabled = True
    runtime._semantic_effect_cache = {}
    runtime._response_language_cache = {}
    runtime._speculative_chat_handoff = None
    chat_started = threading.Event()
    chat_finished = threading.Event()
    cancellations: list[object] = []

    def constrained(_payload: dict, label: str) -> dict:
        if label == "la detección de idioma":
            time.sleep(0.1)
            return {"language": "es"}
        if label == "el veto semántico de efectos":
            time.sleep(0.2)
            return guard_response(has_effect=False, effect_count="zero")
        time.sleep(0.5)
        return {
            "mode": "conversation",
            "operation": "",
            "question": "",
            "conversation_kind": "social",
            "effect_count": "zero",
            "effect_operations": [],
            "response_language": "es",
        }

    def chat(_text: str, **kwargs: object) -> tuple[str, list[dict]]:
        cancellations.append(kwargs["cancellation"])
        chat_started.set()
        time.sleep(2.0)
        chat_finished.set()
        return "Hola.", []

    runtime._post_schema_object = constrained  # type: ignore[method-assign]
    runtime.chat = chat  # type: ignore[method-assign]

    started = time.perf_counter()
    result = runtime.decide_turn("Hola", [])
    elapsed = time.perf_counter() - started

    assert result["mode"] == "conversation"
    assert result["conversation_kind"] == "social"
    assert 0.4 <= elapsed < 1.25
    assert chat_started.is_set()
    assert len(cancellations) == 1
    assert getattr(cancellations[0], "cancelled") is True
    assert runtime._speculative_chat_handoff is None
    assert chat_finished.wait(timeout=3.0)
    assert runtime._speculative_chat_handoff is None


def test_chat_consumes_exact_speculative_handoff_without_second_decode() -> None:
    runtime = object.__new__(LlmRuntime)
    key = runtime._chat_handoff_key(
        "¿Por qué el cielo es azul?",
        [],
        0.0,
        "knowledge",
        "es",
    )
    runtime._speculative_chat_handoff = (
        key,
        time.monotonic(),
        ("La dispersión de la luz lo hace verse azul.", []),
    )

    def post_must_not_run(_payload: dict) -> None:
        raise AssertionError("the prepared reply must be handed off")

    runtime._post = post_must_not_run  # type: ignore[method-assign]

    result = runtime.chat(
        "¿Por qué el cielo es azul?",
        history=[],
        tools=None,
        temperature=0.0,
        conversation_kind="knowledge",
        response_language="es",
    )

    assert result == ("La dispersión de la luz lo hace verse azul.", [])
    assert runtime._speculative_chat_handoff is None


def test_speculative_language_failure_cannot_fail_an_action_decision() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._parallel_turn_verification = True
    runtime._semantic_effect_cache = {}
    runtime._response_language_cache = {}
    rendezvous = threading.Barrier(2, timeout=2.0)

    def constrained(_payload: dict, label: str) -> dict:
        if label == "la detección de idioma":
            raise RuntimeError("speculative detector unavailable")
        if label == "la verificación independiente del conteo de efectos":
            return {"effect_count": "one"}
        rendezvous.wait()
        if label == "el veto semántico de efectos":
            return guard_response(has_effect=True, effect_count="one")
        return {
            "mode": "action",
            "operation": "system.time",
            "question": "",
            "conversation_kind": "",
            "effect_count": "one",
            "effect_operations": ["system.time"],
            "response_language": "es",
        }

    runtime._post_schema_object = constrained  # type: ignore[method-assign]

    result = runtime.decide_turn(
        "¿Qué hora es?",
        [turn_candidate("system.time", "Lee la hora actual.")],
    )

    assert result["mode"] == "action"
    assert result["operation"] == "system.time"


def test_turn_policy_initial_payload_contract_is_exact() -> None:
    runtime = object.__new__(LlmRuntime)
    captured: dict[str, object] = {}
    history = [
        {"role": "user", "content": "Primer mensaje."},
        {"role": "assistant", "content": "Primera respuesta."},
        {"role": "user", "content": "Segundo mensaje."},
        {"role": "assistant", "content": "Segunda respuesta."},
        {"role": "user", "content": "Tercer mensaje."},
        {"role": "assistant", "content": "Tercera respuesta."},
        {"role": "user", "content": "Cuarto mensaje."},
    ]

    def constrained(payload: dict, label: str) -> dict:
        captured["payload"] = payload
        captured["label"] = label
        return {
            "mode": "clarify",
            "operation": "",
            "question": "¿Qué necesitas?",
            "conversation_kind": "",
            "effect_count": "zero",
            "effect_operations": [],
            "response_language": "mixed",
        }

    runtime._post_schema_object = constrained  # type: ignore[method-assign]
    runtime.decide_turn(
        "Haz algo concreto.",
        [
            turn_candidate("app.open", "Abre una aplicación."),
            turn_candidate("audio.volume", "Ajusta el volumen."),
        ],
        history=history,
    )

    expected_schema = {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["conversation", "clarify", "action", "plan"],
            },
            # No `operation` and no `effect_count`: BAXY derives both rather
            # than paying the model to write them.
            "question": {"type": "string", "maxLength": 512},
            "conversation_kind": {
                "type": "string",
                "enum": [
                    "",
                    "social",
                    "knowledge",
                    "followup",
                    "unsupported",
                ],
            },
            "effect_operations": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["app.open", "audio.volume"],
                },
                "maxItems": 8,
            },
            "response_language": {
                "type": "string",
                "enum": ["es", "en", "mixed"],
            },
        },
        "required": [
            "mode",
            "question",
            "conversation_kind",
            "effect_operations",
            "response_language",
        ],
        "additionalProperties": False,
    }
    expected_payload = {
        "messages": [
            {"role": "system", "content": TURN_POLICY_PROMPT},
            *history[-6:],
            {
                "role": "user",
                "content": (
                    "Mensaje actual:\nHaz algo concreto.\n\n"
                    "Operaciones candidatas:\n"
                    "app.open | Abre una aplicación.\n"
                    "audio.volume | Ajusta el volumen."
                ),
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "baxy_turn_decision",
                "strict": True,
                "schema": expected_schema,
            },
        },
        "temperature": 0.0,
        "max_tokens": 160,
        "seed": 0,
        "chat_template_kwargs": {"enable_thinking": False},
    }

    assert captured["label"] == "la política de turno"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload == expected_payload
    assert list(payload) == [
        "messages",
        "response_format",
        "temperature",
        "max_tokens",
        "seed",
        "chat_template_kwargs",
    ]
    schema = payload["response_format"]["json_schema"]["schema"]
    assert list(schema["properties"]) == [
        "mode",
        "question",
        "conversation_kind",
        "effect_operations",
        "response_language",
    ]


def test_turn_policy_keeps_primary_json_schema_without_mutating_it() -> None:
    payload = _build_turn_policy_payload(
        "Abre la aplicación.",
        ["app.open", 'fixture."quoted"'],
        "app.open | Abre una aplicación.",
        [],
    )
    original = copy.deepcopy(payload)
    sent: list[dict[str, object]] = []
    runtime = object.__new__(LlmRuntime)
    runtime._request_attempt = 0

    def post(current: dict[str, object]) -> dict[str, object]:
        sent.append(copy.deepcopy(current))
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"mode":"action","operation":"app.open",'
                            '"question":"","conversation_kind":"",'
                            '"effect_count":"one",'
                            '"effect_operations":["app.open"],'
                            '"response_language":"es"}'
                        )
                    }
                }
            ]
        }

    runtime._post = post  # type: ignore[method-assign]

    result = runtime._post_schema_object(payload, "la política de turno")

    assert result["operation"] == "app.open"
    assert payload == original
    assert len(sent) == 1
    assert sent[0]["response_format"] == original["response_format"]
    assert "grammar" not in sent[0]
    assert sent[0]["max_tokens"] == 160


def test_semantic_guard_compact_grammar_preserves_closed_enum_contract() -> None:
    payload = {
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "baxy_semantic_effect_guard",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "request_type": {
                            "type": "string",
                            "enum": [
                                "stable_conversation",
                                "external_read",
                                "environment_change",
                                "incomplete_effect",
                            ],
                        },
                        "effect_count": {
                            "type": "string",
                            "enum": ["zero", "one", "multiple"],
                        },
                    },
                    "required": ["request_type", "effect_count"],
                    "additionalProperties": False,
                },
            },
        }
    }

    grammar = _compact_structured_grammar(payload)

    assert isinstance(grammar, str)
    assert grammar.splitlines()[0] == (
        'root ::= "{\\"request_type\\":" request-type '
        '",\\"effect_count\\":" effect-count "}"'
    )
    assert '"\\"stable_conversation\\""' in grammar
    assert '"\\"multiple\\""' in grammar


def test_semantic_guard_compact_grammar_rejects_non_string_enum_drift() -> None:
    payload = {
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "baxy_semantic_effect_guard",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "request_type": {
                            "type": "integer",
                            "enum": [
                                "stable_conversation",
                                "external_read",
                            ],
                        },
                        "effect_count": {
                            "type": "string",
                            "enum": ["zero", "one", "multiple"],
                        },
                    },
                    "required": ["request_type", "effect_count"],
                    "additionalProperties": False,
                },
            },
        }
    }

    assert _compact_structured_grammar(payload) is None


@pytest.mark.parametrize(
    ("name", "properties", "required"),
    [
        (
            "baxy_effect_count_verification",
            {
                "effect_count": {
                    "type": "string",
                    "enum": ["zero", "one", "multiple"],
                }
            },
            ["effect_count"],
        ),
        (
            "baxy_operation_compatibility",
            {"compatible": {"type": "boolean"}},
            ["compatible"],
        ),
    ],
)
def test_action_validators_keep_generic_json_schema(
    name: str,
    properties: dict[str, object],
    required: list[str],
) -> None:
    payload = {
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": name,
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                    "additionalProperties": False,
                },
            },
        }
    }

    assert _compact_structured_grammar(payload) is None


def test_compact_grammar_fails_closed_when_hot_schema_drifts() -> None:
    payload = _build_turn_policy_payload(
        "Abre la aplicación.",
        ["app.open"],
        "app.open | Abre una aplicación.",
        [],
    )
    payload["response_format"]["json_schema"]["schema"]["properties"]["question"][
        "maxLength"
    ] = 511

    assert _compact_structured_grammar(payload) is None


def test_turn_reanalysis_deep_copies_and_only_narrows_recovery_contract() -> None:
    runtime = object.__new__(LlmRuntime)
    payloads: dict[str, dict] = {}

    def constrained(payload: dict, label: str) -> dict:
        payloads[label] = payload
        if label == "la política de turno":
            return {
                "mode": "conversation",
                "operation": "",
                "question": "",
                "conversation_kind": "knowledge",
                "effect_count": "zero",
                "effect_operations": [],
                "response_language": "es",
            }
        if label == "el veto semántico de efectos":
            return guard_response(unresolved=True, effect_count="multiple")
        assert label == "el reanálisis de turno con forma de efecto"
        return {
            "mode": "clarify",
            "operation": "",
            "question": "¿Qué cambios quieres realizar?",
            "conversation_kind": "",
            "effect_count": "zero",
            "effect_operations": [],
            "response_language": "es",
        }

    runtime._post_schema_object = constrained  # type: ignore[method-assign]
    runtime.decide_turn(
        "Realiza esos cambios.",
        [turn_candidate("app.open", "Abre una aplicación.")],
        history=[{"role": "assistant", "content": "Contexto anterior."}],
    )

    assert list(payloads) == [
        "la política de turno",
        "el veto semántico de efectos",
        "el reanálisis de turno con forma de efecto",
    ]
    primary = payloads["la política de turno"]
    recovery = payloads["el reanálisis de turno con forma de efecto"]
    primary_schema = primary["response_format"]["json_schema"]["schema"]
    recovery_schema = recovery["response_format"]["json_schema"]["schema"]
    assert primary_schema["properties"]["conversation_kind"]["enum"] == [
        "",
        "social",
        "knowledge",
        "followup",
        "unsupported",
    ]
    assert recovery_schema["properties"]["conversation_kind"]["enum"] == [
        "",
        "unsupported",
    ]
    assert primary["seed"] == 0
    assert recovery["seed"] == 17
    assert recovery is not primary
    assert recovery["response_format"] is not primary["response_format"]

    observation = json.dumps(
        {
            "effect_state": "not_complete",
            "effect_count": "multiple",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    expected_recovery = json.loads(json.dumps(primary, ensure_ascii=False))
    expected_recovery["messages"] = [
        primary["messages"][0],
        {
            "role": "system",
            "content": (
                TURN_EFFECT_REANALYSIS_PROMPT
                + "\nObservación semántica independiente: "
                + observation
            ),
        },
        *primary["messages"][1:],
    ]
    expected_recovery["response_format"]["json_schema"]["schema"]["properties"][
        "conversation_kind"
    ]["enum"] = ["", "unsupported"]
    expected_recovery["seed"] = 17
    assert recovery == expected_recovery


@pytest.mark.parametrize(
    ("effect_state", "effect_count"),
    [
        ("complete", "one"),
        ("complete", "multiple"),
        ("not_complete", "one"),
        ("not_complete", "multiple"),
    ],
)
def test_turn_reanalysis_payload_builder_is_pure_and_exact(
    effect_state: str,
    effect_count: str,
) -> None:
    primary = {
        "messages": [
            {"role": "system", "content": TURN_POLICY_PROMPT},
            {"role": "assistant", "content": "Contexto anterior."},
            {"role": "user", "content": "Realiza esos cambios."},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "baxy_turn_decision",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "conversation_kind": {
                            "type": "string",
                            "enum": [
                                "",
                                "social",
                                "knowledge",
                                "followup",
                                "unsupported",
                            ],
                        }
                    },
                },
            },
        },
        "temperature": 0.0,
        "max_tokens": 160,
        "seed": 0,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    primary_snapshot = copy.deepcopy(primary)

    first = _build_turn_reanalysis_payload(
        primary,
        effect_state,
        effect_count,
    )
    second = _build_turn_reanalysis_payload(
        primary,
        effect_state,
        effect_count,
    )

    observation = json.dumps(
        {
            "effect_state": effect_state,
            "effect_count": effect_count,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    expected = copy.deepcopy(primary_snapshot)
    expected["messages"] = [
        primary["messages"][0],
        {
            "role": "system",
            "content": (
                TURN_EFFECT_REANALYSIS_PROMPT
                + "\nObservación semántica independiente: "
                + observation
            ),
        },
        *primary["messages"][1:],
    ]
    expected["response_format"]["json_schema"]["schema"]["properties"][
        "conversation_kind"
    ]["enum"] = ["", "unsupported"]
    expected["seed"] = 17

    assert primary == primary_snapshot
    assert first == second == expected
    assert first is not second
    assert first["response_format"] is not primary["response_format"]


def test_turn_policy_receives_context_and_only_retrieved_candidates() -> None:
    runtime = object.__new__(LlmRuntime)
    captured: dict[str, object] = {}

    def constrained(payload: dict, label: str) -> dict:
        captured["payload"] = payload
        captured["label"] = label
        return {
            "mode": "clarify",
            "operation": None,
            "question": "¿A qué te refieres?",
            "conversation_kind": "",
            "effect_count": "zero",
            "effect_operations": [],
            "response_language": "es",
        }

    runtime._post_schema_object = constrained  # type: ignore[method-assign]
    result = runtime.decide_turn(
        "Porque",
        [turn_candidate("audio.volume", "Ajusta el volumen.")],
        history=[
            {"role": "assistant", "content": "La operación anterior no se completó."},
            {"role": "user", "content": "Necesitaba entender la causa."},
        ],
        evidence=[
            {
                "mode": "conversation",
                "families": [],
                "score": 0.91,
                "calibrated_conversation_probability": 0.97,
                "example": "El usuario pregunta por la causa del resultado anterior.",
            }
        ],
    )

    assert result["mode"] == "clarify"
    assert "reply" not in result
    payload = captured["payload"]
    assert isinstance(payload, dict)
    messages = payload["messages"]
    assert isinstance(messages, list)
    assert any(
        message.get("content") == "Necesitaba entender la causa."
        for message in messages
    )
    assert "Señales kNN" not in messages[-1]["content"]
    assert "El usuario pregunta por la causa" not in messages[-1]["content"]
    assert "calibrated_conversation_probability" not in messages[-1]["content"]
    schema = payload["response_format"]["json_schema"]["schema"]
    assert "oneOf" not in schema
    assert schema["properties"]["mode"]["enum"] == [
        "conversation",
        "clarify",
        "action",
        "plan",
    ]
    # `operation` and `effect_count` are deliberately not asked of the model.
    # Both are functions of what it already emits and BAXY derives them, which
    # removes about 21 emitted tokens per policy call.
    assert "operation" not in schema["properties"]
    assert "effect_count" not in schema["properties"]
    assert schema["properties"]["conversation_kind"]["enum"] == [
        "",
        "social",
        "knowledge",
        "followup",
        "unsupported",
    ]
    assert schema["properties"]["effect_operations"] == {
        "type": "array",
        "items": {"type": "string", "enum": ["audio.volume"]},
        "maxItems": 8,
    }
    assert schema["properties"]["response_language"]["enum"] == [
        "es",
        "en",
        "mixed",
    ]
    assert "reply" not in schema["properties"]


def test_turn_policy_primary_inference_is_identical_with_or_without_evidence() -> None:
    runtime = object.__new__(LlmRuntime)
    payloads: list[dict] = []

    def constrained(payload: dict, _label: str) -> dict:
        payloads.append(payload)
        return {
            "mode": "conversation",
            "operation": "",
            "question": "",
            "conversation_kind": "knowledge",
            "effect_count": "zero",
            "effect_operations": [],
            "response_language": "es",
        }

    runtime._post_schema_object = constrained  # type: ignore[method-assign]
    without_evidence = runtime.decide_turn(
        "Explica el resultado.",
        [turn_candidate("app.open", "Abre una aplicación.")],
    )
    with_evidence = runtime.decide_turn(
        "Explica el resultado.",
        [turn_candidate("app.open", "Abre una aplicación.")],
        evidence=[
            {
                "mode": "conversation",
                "families": [],
                "score": 0.82,
                "calibrated_conversation_probability": 0.93,
                "untrusted_operation": "app.open",
            }
        ],
    )

    assert payloads[0] == payloads[2]
    assert payloads[1] == payloads[3]
    assert without_evidence == with_evidence


def test_candidate_free_guard_payload_is_identical_with_or_without_evidence() -> None:
    runtime = object.__new__(LlmRuntime)
    payloads: list[dict] = []

    def constrained(payload: dict, label: str) -> dict:
        payloads.append(payload)
        if label == "la política de turno":
            return {
                "mode": "action",
                "operation": "device.activate",
                "question": "",
                "conversation_kind": "",
                "effect_count": "one",
                "effect_operations": ["device.activate"],
                "response_language": "es",
            }
        if label == "el veto semántico de efectos":
            return guard_response()
        if label == "la verificación independiente del conteo de efectos":
            return {"effect_count": "one"}
        assert label == "la verificación de compatibilidad de la operación"
        return {"compatible": True}

    runtime._post_schema_object = constrained  # type: ignore[method-assign]
    candidates = [
        turn_candidate(
            "device.activate",
            "Activa un recurso seleccionado por la persona.",
            required=("resourceId",),
        )
    ]
    history = [
        {"role": "assistant", "content": "Seleccionaste la lámpara norte."},
        {"role": "user", "content": "Actívalo ahora."},
    ]
    without_evidence = runtime.decide_turn(
        "Actívalo ahora.",
        candidates,
        history=history,
    )
    with_evidence = runtime.decide_turn(
        "Actívalo ahora.",
        candidates,
        history=history,
        evidence=[
            {
                "mode": "conversation",
                "families": [],
                "score": 0.8,
                "calibrated_conversation_probability": 0.95,
                "marker": "PRIVATE_EVIDENCE_MARKER",
            }
        ],
    )

    assert payloads[0] == payloads[4]
    assert payloads[1] == payloads[5]
    assert payloads[2] == payloads[6]
    assert payloads[3] == payloads[7]
    assert "PRIVATE_EVIDENCE_MARKER" not in repr(payloads)
    verifier_messages = payloads[1]["messages"]
    assert (
        sum(
            message.get("role") == "user"
            and "Mensaje actual:\nActívalo ahora." in str(message.get("content"))
            for message in verifier_messages
        )
        == 1
    )
    assert "device.activate" not in repr(payloads[1])
    assert "Seleccionaste la lámpara norte" not in repr(payloads[1])
    assert without_evidence["mode"] == "action"
    assert with_evidence["mode"] == "conversation"


def test_effect_observation_can_trigger_closed_catalog_reanalysis() -> None:
    runtime = object.__new__(LlmRuntime)
    payloads: dict[str, dict] = {}

    def constrained(payload: dict, label: str) -> dict:
        payloads[label] = payload
        if label == "la política de turno":
            return {
                "mode": "conversation",
                "operation": "",
                "question": "",
                "conversation_kind": "knowledge",
                "effect_count": "zero",
                "effect_operations": [],
                "response_language": "es",
            }
        if label == "el veto semántico de efectos":
            return guard_response()
        if label == "la selección cerrada de un efecto":
            return {"operation": "web.search"}
        if label == "la verificación independiente del conteo de efectos":
            return {"effect_count": "one"}
        assert label == "la verificación de compatibilidad de la operación"
        return {"compatible": True}

    runtime._post_schema_object = constrained  # type: ignore[method-assign]
    result = runtime.decide_turn(
        "Consulta el dato vigente en esa fuente.",
        [
            turn_candidate(
                "web.search",
                "Busca información actual en la web.",
                required=("query",),
            )
        ],
    )

    assert result["mode"] == "action"
    assert result["operation"] == "web.search"
    assert result["effect_verification"] == "recovered"
    guard_payload = payloads["el veto semántico de efectos"]
    assert "web.search" not in repr(guard_payload)
    selector = payloads["la selección cerrada de un efecto"]
    selector_schema = selector["response_format"]["json_schema"]["schema"]
    assert selector_schema["properties"]["operation"]["enum"] == [
        "",
        "web.search",
    ]
    compatibility = payloads["la verificación de compatibilidad de la operación"]
    assert "web.search" in repr(compatibility["messages"])
    assert "app.open" not in repr(compatibility["messages"])
    primary_schema = payloads["la política de turno"]["response_format"]["json_schema"][
        "schema"
    ]
    assert "knowledge" in primary_schema["properties"]["conversation_kind"]["enum"]


def test_effect_reanalysis_abstains_when_no_candidate_satisfies_scope() -> None:
    runtime = object.__new__(LlmRuntime)

    def constrained(_payload: dict, label: str) -> dict:
        if label == "el veto semántico de efectos":
            return guard_response()
        if label == "la selección cerrada de un efecto":
            return {"operation": "app.open"}
        if label == "la verificación de compatibilidad de la operación":
            return {"compatible": False}
        return {
            "mode": "conversation",
            "operation": "",
            "question": "",
            "conversation_kind": "knowledge",
            "effect_count": "zero",
            "effect_operations": [],
            "response_language": "es",
        }

    runtime._post_schema_object = constrained  # type: ignore[method-assign]
    result = runtime.decide_turn(
        "Realiza el efecto en un dispositivo remoto no compatible.",
        [turn_candidate("app.open", "Abre una aplicación en este equipo.")],
    )

    assert result["mode"] == "conversation"
    assert result["conversation_kind"] == "unsupported"
    assert result["effect_verification"] == "not_applicable"


def test_turn_policy_deduplicates_current_user_turn_from_shell_history() -> None:
    runtime = object.__new__(LlmRuntime)
    captured: dict[str, object] = {}

    def constrained(payload: dict, label: str) -> dict:
        if label == "el veto semántico de efectos":
            return guard_response(
                has_effect=False,
                effect_count="zero",
            )
        captured["payload"] = payload
        return {
            "mode": "conversation",
            "operation": "",
            "question": "se descarta",
            "conversation_kind": "followup",
            "effect_count": "zero",
            "effect_operations": [],
            "response_language": "es",
        }

    runtime._post_schema_object = constrained  # type: ignore[method-assign]
    runtime.decide_turn(
        "¿Por qué?",
        [],
        history=[
            {
                "role": "assistant",
                "content": "No pude completar la acción porque se agotó el tiempo.",
            },
            {"role": "user", "content": "¿Por qué?"},
        ],
    )

    payload = captured["payload"]
    assert isinstance(payload, dict)
    messages = payload["messages"]
    assert isinstance(messages, list)
    assert (
        sum(
            message.get("role") == "user"
            and "Mensaje actual:\n¿Por qué?" in str(message.get("content"))
            for message in messages
        )
        == 1
    )
    assert messages[-2]["role"] == "assistant"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            {
                "mode": "conversation",
                "operation": "audio.volume",
                "question": "texto impropio",
                "conversation_kind": "knowledge",
                "effect_count": "zero",
                "effect_operations": [],
                "effect_verification": "not_applicable",
                "response_language": "es",
                "extra": "ignorado sin autoridad",
            },
            {
                "mode": "conversation",
                "operation": None,
                "question": "",
                "conversation_kind": "knowledge",
                "effect_count": "zero",
                "effect_operations": [],
                "effect_verification": "not_applicable",
                "response_language": "es",
            },
        ),
        (
            {
                "mode": "clarify",
                "operation": "audio.volume",
                "question": "¿Qué volumen quieres?",
                "conversation_kind": "social",
                "effect_count": "zero",
                "effect_operations": [],
                "effect_verification": "not_applicable",
                "response_language": "es",
            },
            {
                "mode": "clarify",
                "operation": None,
                "question": "¿Qué volumen quieres?",
                "conversation_kind": "",
                "effect_count": "zero",
                "effect_operations": [],
                "effect_verification": "not_applicable",
                "response_language": "es",
            },
        ),
        (
            {
                "mode": "action",
                "operation": "invented.operation",
                "question": "texto impropio",
                "conversation_kind": "unsupported",
                "effect_count": "one",
                "effect_operations": ["invented.operation"],
                "effect_verification": "pending",
                "response_language": "es",
            },
            {
                "mode": "action",
                "operation": "invented.operation",
                "question": "",
                "conversation_kind": "",
                "effect_count": "one",
                "effect_operations": ["invented.operation"],
                "effect_verification": "pending",
                "response_language": "es",
            },
        ),
        (
            {
                "mode": "action",
                "operation": "audio.volume",
                "question": "texto impropio",
                "conversation_kind": "social",
                "effect_count": "one",
                "effect_operations": ["audio.volume", "audio.volume"],
                "response_language": "es",
            },
            {
                "mode": "plan",
                "operation": None,
                "question": "",
                "conversation_kind": "",
                "effect_count": "multiple",
                "effect_operations": ["audio.volume", "audio.volume"],
                "effect_verification": "pending",
                "response_language": "es",
            },
        ),
        (
            {
                "mode": "plan",
                "operation": "audio.volume",
                "question": "texto impropio",
                "conversation_kind": "social",
                "effect_count": "multiple",
                "effect_operations": ["audio.volume"],
                "response_language": "es",
            },
            {
                "mode": "action",
                "operation": "audio.volume",
                "question": "",
                "conversation_kind": "",
                "effect_count": "one",
                "effect_operations": ["audio.volume"],
                "effect_verification": "pending",
                "response_language": "es",
            },
        ),
    ],
)
def test_turn_canonicalization_discards_only_mode_inapplicable_fields(
    raw: dict[str, object],
    expected: dict[str, object],
) -> None:
    assert canonicalize_turn_decision(raw) == expected


def test_turn_canonicalization_never_repairs_action_authority() -> None:
    canonical = canonicalize_turn_decision(
        {
            "mode": "action",
            "operation": "invented.operation",
            "question": "",
            "conversation_kind": "",
            "effect_count": "one",
            "effect_operations": ["invented.operation"],
            "response_language": "es",
        }
    )
    with pytest.raises(PlannerContractError):
        validate_turn_decision(canonical, {"audio.volume"})


def test_live_protocol_does_not_call_legacy_phrase_deciders() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "src" / "baxy_mind" / "__main__.py"
    ).read_text(encoding="utf-8")
    protocol_start = source.index("def _run_sidecar(")
    protocol_end = source.index("\ndef main() -> int:", protocol_start)
    live_protocol = source[protocol_start:protocol_end]
    for legacy_decider in (
        "deterministic_bounded_plan(",
        "deterministic_conversation_plan(",
        "deterministic_single_step(",
        'elif kind == "route":',
    ):
        assert legacy_decider not in live_protocol


@pytest.mark.parametrize(
    ("raw", "candidates", "expected"),
    [
        (
            {
                "mode": "conversation",
                "operation": None,
                "question": "",
                "conversation_kind": "knowledge",
                "effect_count": "zero",
                "effect_operations": [],
                "effect_verification": "not_applicable",
                "response_language": "es",
            },
            set(),
            "conversation",
        ),
        (
            {
                "mode": "action",
                "operation": "audio.volume",
                "question": "",
                "conversation_kind": "",
                "effect_count": "one",
                "effect_operations": ["audio.volume"],
                "effect_verification": "agreed",
                "response_language": "es",
            },
            {"audio.volume"},
            "action",
        ),
        (
            {
                "mode": "action",
                "operation": "web.search",
                "question": "",
                "conversation_kind": "",
                "effect_count": "one",
                "effect_operations": ["web.search"],
                "effect_verification": "recovered",
                "response_language": "es",
            },
            {"web.search"},
            "action",
        ),
        (
            {
                "mode": "action",
                "operation": "audio.volume",
                "question": "",
                "conversation_kind": "",
                "effect_count": "one",
                "effect_operations": ["audio.volume"],
                "effect_verification": "grounding_required",
                "response_language": "es",
            },
            {"audio.volume"},
            "action",
        ),
        (
            {
                "mode": "plan",
                "operation": None,
                "question": "",
                "conversation_kind": "",
                "effect_count": "multiple",
                "effect_operations": ["audio.volume", "audio.volume"],
                "effect_verification": "multiple",
                "response_language": "es",
            },
            {"audio.volume"},
            "plan",
        ),
        (
            {
                "mode": "plan",
                "operation": None,
                "question": "",
                "conversation_kind": "",
                "effect_count": "one",
                "effect_operations": ["audio.volume"],
                "effect_verification": "disagreement",
                "response_language": "es",
            },
            {"audio.volume"},
            "plan",
        ),
    ],
)
def test_turn_contract_accepts_only_mode_and_catalog_evidence(
    raw: dict[str, object], candidates: set[str], expected: str
) -> None:
    assert validate_turn_decision(raw, candidates)["mode"] == expected


def test_relevance_check_can_only_remove_direct_action_authority() -> None:
    action = validate_turn_decision(
        {
            "mode": "action",
            "operation": "app.open",
            "question": "",
            "conversation_kind": "",
            "effect_count": "one",
            "effect_operations": ["app.open"],
            "effect_verification": "agreed",
            "response_language": "es",
        },
        {"app.open"},
    )

    class Catalog:
        def __init__(self, relevant: bool) -> None:
            self.relevant = relevant

        def operation_is_relevant(self, objective: str, operation: str) -> bool:
            assert objective == "Abre la calculadora"
            assert operation == "app.open"
            return self.relevant

    assert (
        apply_turn_action_relevance_veto(
            action,
            "Abre la calculadora",
            Catalog(True),  # type: ignore[arg-type]
        )
        is action
    )
    vetoed = apply_turn_action_relevance_veto(
        action,
        "Abre la calculadora",
        Catalog(False),  # type: ignore[arg-type]
    )
    assert vetoed["mode"] == "plan"
    assert vetoed["operation"] is None
    assert vetoed["effect_count"] == "one"
    assert vetoed["effect_operations"] == ["app.open"]
    assert vetoed["effect_verification"] == "disagreement"


def test_information_question_cannot_authorize_a_mutating_effect() -> None:
    close_tool = {
        "type": "function",
        "function": {
            "name": "app_close",
            "canonical_name": "app.close",
            "description": "Close one exact application.",
            "risk": "work_loss",
            "parameters": {
                "type": "object",
                "properties": {"process": {"type": "string"}},
                "required": ["process"],
                "additionalProperties": False,
            },
        },
    }
    decision = validate_turn_decision(
        {
            "mode": "action",
            "operation": "app.close",
            "question": "",
            "conversation_kind": "",
            "effect_count": "one",
            "effect_operations": ["app.close"],
            "effect_verification": "grounding_required",
            "response_language": "es",
        },
        {"app.close"},
    )

    vetoed = apply_information_question_effect_veto(
        decision,
        "¿Dónde dejaste el PowerPoint? ¿Qué me hiciste?",
        PlannerCatalog([close_tool]),
    )

    assert vetoed["mode"] == "conversation"
    assert vetoed["conversation_kind"] == "knowledge"
    assert vetoed["effect_operations"] == []


@pytest.mark.parametrize(
    "text",
    [
        "Tengo el Bluetooth encendido",
        "Estoy usando los altavoces",
        "I have Bluetooth enabled",
        "I see the app open",
    ],
)
def test_declarative_observation_never_grants_effect_authority(text: str) -> None:
    decision = validate_turn_decision(
        {
            "mode": "plan",
            "operation": None,
            "question": "",
            "conversation_kind": "",
            "effect_count": "one",
            "effect_operations": ["bluetooth.radio.set"],
            "effect_verification": "disagreement",
            "response_language": "es",
        },
        {"bluetooth.radio.set"},
    )

    vetoed = apply_declarative_observation_effect_veto(decision, text)

    assert vetoed["mode"] == "conversation"
    assert vetoed["conversation_kind"] == "followup"
    assert vetoed["effect_operations"] == []


def test_declarative_observation_veto_preserves_questions_and_explicit_requests() -> None:
    decision = validate_turn_decision(
        {
            "mode": "action",
            "operation": "bluetooth.radio.set",
            "question": "",
            "conversation_kind": "",
            "effect_count": "one",
            "effect_operations": ["bluetooth.radio.set"],
            "effect_verification": "grounding_required",
            "response_language": "es",
        },
        {"bluetooth.radio.set"},
    )
    explicit = EffectIntent(("bluetooth.radio.set",))

    assert (
        apply_declarative_observation_effect_veto(
            decision,
            "¿Tengo el Bluetooth encendido?",
        )
        is decision
    )
    assert (
        apply_declarative_observation_effect_veto(
            decision,
            "Tengo que encender Bluetooth",
            explicit,
        )
        is decision
    )


def test_self_contained_observation_uses_direct_ack_even_with_welcome_history() -> None:
    assert (
        llm_module._conversation_presentation_shape(
            "Tengo el Bluetooth encendido",
            conversation_kind="followup",
            has_history=True,
        )
        == "observation_ack"
    )
    assert _shaped_conversation_answer_violates_contract(
        "El usuario menciona que tiene el Bluetooth encendido.",
        "Tengo el Bluetooth encendido",
        "observation_ack",
        conversation_kind="followup",
    )
    assert not _shaped_conversation_answer_violates_contract(
        "Entiendo que tienes el Bluetooth encendido.",
        "Tengo el Bluetooth encendido",
        "observation_ack",
        conversation_kind="followup",
    )
    assert _direct_observation_address(
        "El usuario ha confirmado que tiene el Bluetooth encendido.",
        "observation_ack",
    ) == "Mencionas que tienes el Bluetooth encendido."
    assert _direct_observation_address(
        "The user confirms that they have Bluetooth enabled.",
        "observation_ack",
    ) == "You mention that you have Bluetooth enabled."
    assert _direct_observation_address(
        "El brillo está al máximo.",
        "observation_ack",
        "Tengo el brillo al máximo",
    ) == "Mencionas que el brillo está al máximo."
    assert _direct_observation_address(
        "Your Bluetooth is enabled.",
        "observation_ack",
        "I have Bluetooth enabled",
    ) == "You mention that your Bluetooth is enabled."
    assert _direct_observation_address(
        "La GPU dejó de usarse.",
        "observation_ack",
        "Tengo el brillo al máximo",
    ) == "La GPU dejó de usarse."
    assert not _shaped_conversation_answer_violates_contract(
        "Mencionas que tienes el Bluetooth encendido.",
        "Tengo el Bluetooth encendido",
        "observation_ack",
        conversation_kind="followup",
    )

    runtime = object.__new__(LlmRuntime)
    runtime._post = lambda _payload: {  # type: ignore[method-assign]
        "choices": [
            {
                "message": {
                    "content": (
                        "El usuario ha confirmado que tiene el Bluetooth encendido."
                    )
                }
            }
        ]
    }
    reply, calls = runtime.chat(
        "Tengo el Bluetooth encendido",
        history=[{"role": "assistant", "content": "Hola."}],
        conversation_kind="followup",
        response_language="es",
    )
    assert reply == "Mencionas que tienes el Bluetooth encendido."
    assert calls == []


@pytest.mark.parametrize(
    "text",
    [
        "no subas el volumen",
        "no abras Chrome",
        "no cierres Spotify",
        "no silencies el audio",
        "do not close Spotify",
    ],
)
def test_negative_instruction_uses_a_no_action_acknowledgement(text: str) -> None:
    assert effect_intent_module.no_action_constraint_request(text)
    shape = _conversation_presentation_shape(
        text,
        conversation_kind="unsupported",
        has_history=True,
    )

    assert shape == "no_action_constraint"
    assert _shaped_conversation_answer_violates_contract(
        "No puedo abrir Chrome.",
        "no abras Chrome",
        shape,
        conversation_kind="unsupported",
    )
    assert _shaped_conversation_answer_violates_contract(
        "¿Quieres que consulte el estado del audio?",
        "no silencies el audio",
        shape,
        conversation_kind="unsupported",
    )
    assert not _shaped_conversation_answer_violates_contract(
        "Entendido, no abriré Chrome.",
        "no abras Chrome",
        shape,
        conversation_kind="unsupported",
    )
    assert not _shaped_conversation_answer_violates_contract(
        "No cierro Spotify.",
        "no cierres Spotify",
        "no_action_constraint",
        conversation_kind="unsupported",
    )
    assert _shaped_conversation_answer_violates_contract(
        "no cierro Spotify.",
        "no cierres Spotify",
        "no_action_constraint",
        conversation_kind="unsupported",
    )
    assert _shaped_conversation_answer_violates_contract(
        "No reproduciré el audio.",
        "no silencies el audio",
        "no_action_constraint",
        conversation_kind="unsupported",
    )


@pytest.mark.parametrize(
    "text",
    [
        "no tengo Bluetooth",
        "no hay ventanas abiertas?",
        "I do not have Spotify installed",
    ],
)
def test_negative_facts_are_not_instruction_constraints(text: str) -> None:
    assert not effect_intent_module.no_action_constraint_request(text)


def test_negative_instruction_recovery_never_invents_a_clarification() -> None:
    class Runtime:
        def chat(self, *_args: object, **_kwargs: object) -> tuple[str, list[object]]:
            return "No cerraré Spotify.", []

    result = _recover_failed_turn(
        {"id": "constraint", "text": "no cierres Spotify", "history": []},
        Runtime(),
        attempts=2,
        failure_kinds=("contract",),
    )

    assert result["kind"] == "conversation"
    assert result["question"] == ""
    assert result["reply"] == "No cerraré Spotify."
    assert result["effectOperations"] == []


def test_capability_question_accepts_spanish_voseo() -> None:
    decision = _explicit_stable_no_effect_turn_decision("que podes hacer")

    assert decision is not None
    assert decision["mode"] == "conversation"
    assert decision["conversation_kind"] == "knowledge"
    assert (
        _conversation_presentation_shape(
            "que podes hacer",
            conversation_kind="knowledge",
            has_history=True,
        )
        == "assistant_capability"
    )
    assert _shaped_conversation_answer_violates_contract(
        "Sí, puedo explicar temas. ¿En qué puedo ayudarte?",
        "que podes hacer",
        "assistant_capability",
        conversation_kind="knowledge",
    )
    assert not _shaped_conversation_answer_violates_contract(
        "Puedo conversar, explicar y realizar tareas autorizadas en tu PC.",
        "que podes hacer",
        "assistant_capability",
        conversation_kind="knowledge",
    )


def test_observation_ack_must_attribute_every_unread_state() -> None:
    assert _shaped_conversation_answer_violates_contract(
        "El brillo está al máximo.",
        "tengo el brillo al máximo",
        "observation_ack",
        conversation_kind="followup",
    )
    assert not _shaped_conversation_answer_violates_contract(
        "Entiendo que observas que el brillo está al máximo.",
        "tengo el brillo al máximo",
        "observation_ack",
        conversation_kind="followup",
    )
    assert _shaped_conversation_answer_violates_contract(
        "Entiendo que observas que la GPU dejó de usarse.",
        "tengo el brillo al máximo",
        "observation_ack",
        conversation_kind="followup",
    )
    assert _shaped_conversation_answer_violates_contract(
        "Mencionas que el brillo está completamente activado.",
        "tengo el brillo al máximo",
        "observation_ack",
        conversation_kind="followup",
    )


def test_self_contained_effect_refusal_is_not_presented_as_a_followup() -> None:
    decision = validate_turn_decision(
        {
            "mode": "conversation",
            "operation": None,
            "question": "",
            "conversation_kind": "followup",
            "effect_count": "zero",
            "effect_operations": [],
            "effect_verification": "not_applicable",
            "response_language": "es",
        },
        set(),
    )

    result = apply_non_effect_conversation_classification(
        decision,
        "listá las ventanas y enfocá la mejor",
    )

    assert result["conversation_kind"] == "unsupported"
    assert not _explicit_contextual_followup("listá las ventanas y enfocá la mejor")
    assert _explicit_contextual_followup("¿Por qué?")


def test_information_question_veto_preserves_real_requests_and_read_only_queries() -> (
    None
):
    tools = [
        {
            "type": "function",
            "function": {
                "name": name.replace(".", "_"),
                "canonical_name": name,
                "description": name,
                "risk": risk,
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
            },
        }
        for name, risk in (
            ("app.close", "work_loss"),
            ("system.status", "read_only"),
        )
    ]
    catalog = PlannerCatalog(tools)

    close_request = validate_turn_decision(
        {
            "mode": "action",
            "operation": "app.close",
            "question": "",
            "conversation_kind": "",
            "effect_count": "one",
            "effect_operations": ["app.close"],
            "effect_verification": "grounding_required",
            "response_language": "es",
        },
        {"app.close"},
    )
    status_query = validate_turn_decision(
        {
            "mode": "action",
            "operation": "system.status",
            "question": "",
            "conversation_kind": "",
            "effect_count": "one",
            "effect_operations": ["system.status"],
            "effect_verification": "grounding_required",
            "response_language": "es",
        },
        {"system.status"},
    )

    assert (
        apply_information_question_effect_veto(
            close_request,
            "¿Puedes cerrar PowerPoint?",
            catalog,
        )
        is close_request
    )
    assert (
        apply_information_question_effect_veto(
            status_query,
            "¿Cómo está este equipo?",
            catalog,
        )
        is status_query
    )


def test_recovered_action_keeps_independently_verified_authority() -> None:
    recovered = validate_turn_decision(
        {
            "mode": "action",
            "operation": "web.search",
            "question": "",
            "conversation_kind": "",
            "effect_count": "one",
            "effect_operations": ["web.search"],
            "effect_verification": "recovered",
            "response_language": "es",
        },
        {"web.search"},
    )

    class VetoMustNotRun:
        def operation_is_relevant(self, _objective: str, _operation: str) -> bool:
            raise AssertionError("E5 veto must not override verified consensus")

    assert (
        apply_turn_action_relevance_veto(
            recovered,
            "Consulta una fuente vigente",
            VetoMustNotRun(),  # type: ignore[arg-type]
        )
        is recovered
    )


def test_action_grounding_gate_preserves_only_arguments_backed_by_user_text() -> None:
    decision = validate_turn_decision(
        {
            "mode": "action",
            "operation": "app.open",
            "question": "",
            "conversation_kind": "",
            "effect_count": "one",
            "effect_operations": ["app.open"],
            "effect_verification": "grounding_required",
            "response_language": "es",
        },
        {"app.open"},
    )
    tool = {
        "function": {
            "canonical_name": "app.open",
            "description": "Abre una aplicación por nombre.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appId": {
                        "type": "string",
                        "x-maxUtf8Bytes": 512,
                        "x-nonWhitespace": True,
                    }
                },
                "required": ["appId"],
                "additionalProperties": False,
            },
        }
    }

    class GroundedRuntime:
        @staticmethod
        def extract_direct_arguments(
            _objective: str,
            _tool: dict,
        ) -> DirectArgumentExtraction:
            return DirectArgumentExtraction(
                {"appId": "calculadora"},
                (("appId", "calculadora"),),
                "¿Qué aplicación quieres abrir?",
            )

    accepted = apply_turn_action_grounding_gate(
        decision,
        "Abre la calculadora.",
        {"app.open": tool},
        GroundedRuntime(),
    )

    assert accepted["mode"] == "action"
    assert accepted["operation"] == "app.open"
    assert accepted["effect_verification"] == "grounded"


def test_recovered_required_action_still_crosses_argument_grounding() -> None:
    decision = validate_turn_decision(
        {
            "mode": "action",
            "operation": "filesystem.move",
            "question": "",
            "conversation_kind": "",
            "effect_count": "one",
            "effect_operations": ["filesystem.move"],
            "effect_verification": "recovered",
            "response_language": "es",
        },
        {"filesystem.move"},
    )
    tool = {
        "function": {
            "canonical_name": "filesystem.move",
            "description": "Mueve un archivo identificado dentro del sandbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "resourceId": {"type": "string"},
                    "destinationRelativePath": {"type": "string"},
                    "expectedSha256": {"type": "string"},
                },
                "required": [
                    "resourceId",
                    "destinationRelativePath",
                    "expectedSha256",
                ],
                "additionalProperties": False,
            },
        }
    }

    class UngroundedRuntime:
        @staticmethod
        def extract_direct_arguments(
            _objective: str,
            _tool: dict,
        ) -> DirectArgumentExtraction:
            return DirectArgumentExtraction(
                None,
                (),
                "¿Qué archivo y destino exactos quieres usar?",
            )

    clarified = apply_turn_action_grounding_gate(
        decision,
        "Arrastra este archivo a esa ventana.",
        {"filesystem.move": tool},
        UngroundedRuntime(),
    )

    assert clarified["mode"] == "clarify"
    assert clarified["effect_operations"] == []
    assert clarified["effect_verification"] == "not_applicable"


def test_action_grounding_gate_skips_llm_for_complete_explicit_literals() -> None:
    decision = validate_turn_decision(
        {
            "mode": "action",
            "operation": "audio.volume",
            "question": "",
            "conversation_kind": "",
            "effect_count": "one",
            "effect_operations": ["audio.volume"],
            "effect_verification": "grounding_required",
            "response_language": "es",
        },
        {"audio.volume"},
    )
    tool = {
        "function": {
            "canonical_name": "audio.volume",
            "description": "Ajusta el volumen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                    }
                },
                "required": ["level"],
                "additionalProperties": False,
            },
        }
    }

    class LlmMustNotRun:
        @staticmethod
        def extract_direct_arguments(_objective: str, _tool: dict) -> None:
            raise AssertionError("literal grounding must not invoke the LLM")

    accepted = apply_turn_action_grounding_gate(
        decision,
        "Pon el volumen al 8 por ciento.",
        {"audio.volume": tool},
        LlmMustNotRun(),
    )

    assert accepted["mode"] == "action"
    assert accepted["effect_verification"] == "grounded"


def test_effect_guard_can_only_change_conversation_presentation_to_unsupported() -> (
    None
):
    conversation = validate_turn_decision(
        {
            "mode": "conversation",
            "operation": None,
            "question": "",
            "conversation_kind": "knowledge",
            "effect_count": "zero",
            "effect_operations": [],
            "effect_verification": "not_applicable",
            "response_language": "es",
        },
        set(),
    )

    class GuardRuntime:
        @staticmethod
        def _verify_semantic_effect_shape(_text: str) -> tuple[str, str]:
            return "not_complete", "one"

    result = apply_conversation_effect_presentation(
        conversation,
        "Pide un servicio externo.",
        GuardRuntime(),
    )

    assert result["mode"] == "conversation"
    assert result["operation"] is None
    assert result["effect_operations"] == []
    assert result["conversation_kind"] == "unsupported"


@pytest.mark.parametrize(
    "raw",
    [
        {
            "mode": "action",
            "operation": "unlisted.operation",
            "question": "",
            "conversation_kind": "",
            "effect_count": "one",
            "effect_operations": ["unlisted.operation"],
            "effect_verification": "agreed",
            "response_language": "es",
        },
        {
            "mode": "clarify",
            "operation": None,
            "question": "",
            "conversation_kind": "",
            "effect_count": "zero",
            "effect_operations": [],
            "effect_verification": "not_applicable",
            "response_language": "es",
        },
        {
            "mode": "conversation",
            "operation": "audio.volume",
            "question": "",
            "conversation_kind": "social",
            "effect_count": "zero",
            "effect_operations": [],
            "effect_verification": "not_applicable",
            "response_language": "es",
        },
        {
            "mode": "plan",
            "operation": None,
            "question": "una pregunta",
            "conversation_kind": "",
            "effect_count": "multiple",
            "effect_operations": ["audio.volume", "audio.volume"],
            "effect_verification": "multiple",
            "response_language": "es",
        },
        {
            "mode": "action",
            "operation": "audio.volume",
            "question": "",
            "conversation_kind": "",
            "effect_count": "multiple",
            "effect_operations": ["audio.volume", "audio.volume"],
            "effect_verification": "multiple",
            "response_language": "es",
        },
    ],
)
def test_turn_contract_fails_closed_on_invalid_semantics(
    raw: dict[str, object],
) -> None:
    with pytest.raises(PlannerContractError):
        validate_turn_decision(raw, {"audio.volume"})


def test_turn_chat_receives_closed_policy_without_catalog_or_evidence() -> None:
    runtime = object.__new__(LlmRuntime)
    captured: dict[str, object] = {}

    def post(payload: dict) -> dict:
        captured["payload"] = payload
        return {
            "choices": [
                {
                    "message": {"content": "No puedo pedir ese taxi."},
                    "finish_reason": "stop",
                }
            ]
        }

    runtime._post = post  # type: ignore[method-assign]
    answer, calls = runtime.chat(
        "Pide un taxi.",
        history=[],
        temperature=0.0,
        conversation_kind="unsupported",
        response_language="es",
    )

    assert answer == "No puedo pedir ese taxi."
    assert calls == []
    payload = captured["payload"]
    assert isinstance(payload, dict)
    messages = payload["messages"]
    assert isinstance(messages, list)
    assert "comprobación previa" in messages[0]["content"]
    assert "sustantivo concreto" in messages[1]["content"]
    assert "catálogos" not in messages[1]["content"]
    assert "exclusivamente en español" in messages[2]["content"]
    serialized = "\n".join(str(message["content"]) for message in messages)
    assert any("taxi" in str(message["content"]) for message in messages)
    # The prompt constrains the answer; it must never dictate it. A verbatim
    # sentence here would put a fixed visible reply on screen, which invariant 6
    # forbids outright.
    anchor_messages = [
        str(message["content"])
        for message in messages
        if "Nombra en la frase lo que se pidió" in str(message["content"])
    ]
    assert len(anchor_messages) == 1
    assert '"taxi"' in anchor_messages[0]
    assert "no puedes" in anchor_messages[0]
    assert "Devuelve exactamente" not in serialized
    assert "No puedo completar taxi tal como fue pedido" not in serialized
    assert "Operaciones candidatas" not in serialized
    assert "Señales kNN" not in serialized


@pytest.mark.parametrize(
    "text",
    [
        "instagram",
        "Vamos a jugar al Fall Guys modo multijugador.",
    ],
)
def test_unavailable_catalog_entity_is_closed_without_model_authority(
    text: str,
) -> None:
    decision = mind_main._catalog_unavailable_turn_decision(
        text,
        None,
        (),
        build_game_catalog_index(()),
    )

    assert decision is not None
    assert decision["mode"] == "conversation"
    assert decision["conversation_kind"] == "unsupported"
    assert decision["effect_operations"] == []


@pytest.mark.parametrize(
    ("text", "anchor"),
    [
        (
            "Get me vanilla, wait, cinnamon using my American Express card.",
            "card",
        ),
        ("Quitar, eh quiero decir, poner el Fortnite.", "fortnite"),
        ("Vamos a jugar al Fall Guys modo multijugador.", "fall guys"),
    ],
)
def test_unsupported_presentation_uses_one_inert_final_anchor(
    text: str,
    anchor: str,
) -> None:
    assert llm_module._unsupported_request_anchor_token(text) == anchor


def test_cpu_conversation_presentation_has_a_bounded_decode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = object.__new__(LlmRuntime)
    captured: dict[str, object] = {}

    def post(payload: dict) -> dict:
        captured["payload"] = payload
        return {
            "choices": [
                {
                    "message": {"content": "Pineapple is a matter of taste."},
                    "finish_reason": "stop",
                }
            ]
        }

    runtime._post = post  # type: ignore[method-assign]
    monkeypatch.setenv("BAXY_MIND_NGL", "0")
    answer, _ = runtime.chat(
        "What do you think about pineapple on pizza?",
        history=[],
        temperature=0.0,
        conversation_kind="knowledge",
        response_language="en",
    )

    assert answer
    assert captured["payload"]["max_tokens"] == 32
    messages = captured["payload"]["messages"]
    assert any("máximo 20 palabras" in message["content"] for message in messages)


@pytest.mark.parametrize("conversation_kind", ["knowledge", "unsupported"])
def test_roleplay_draft_presentation_requests_substantive_fictional_content(
    conversation_kind: str,
) -> None:
    runtime = object.__new__(LlmRuntime)
    captured: dict[str, object] = {}

    def post(payload: dict) -> dict:
        captured["payload"] = payload
        return {
            "choices": [
                {
                    "message": {
                        "content": "Solange: Hello, Tomás.\nTomás: Hi, Solange."
                    },
                    "finish_reason": "stop",
                }
            ]
        }

    runtime._post = post  # type: ignore[method-assign]
    answer, calls = runtime.chat(
        "Mira, Baxy: una consulta simple: Role-play una conversation; "
        "send nothing a Solange ni Tomás.",
        history=[],
        temperature=0.0,
        conversation_kind=conversation_kind,
        response_language="en",
    )

    assert answer.startswith("Solange:")
    assert calls == []
    payload = captured["payload"]
    assert isinstance(payload, dict)
    messages = payload["messages"]
    assert "diálogo ficticio" in messages[0]["content"]
    assert json.loads(messages[-1]["content"]) == {
        "draft_kind": "fictional_dialogue",
        "participant_names": ["Solange", "Tomás"],
        "external_send": False,
    }


def test_roleplay_draft_retries_a_system_policy_echo() -> None:
    runtime = object.__new__(LlmRuntime)
    payloads: list[dict] = []

    def post(payload: dict) -> dict:
        payloads.append(payload)
        content = (
            "Internal language policy: answer exclusively in English."
            if len(payloads) == 1
            else json.dumps({"answer": ("Solange: Hello, Tomás.\nTomás: Hi, Solange.")})
        )
        return {
            "choices": [
                {
                    "message": {"content": content},
                    "finish_reason": "stop",
                }
            ]
        }

    runtime._post = post  # type: ignore[method-assign]
    answer, calls = runtime.chat(
        "Mira, Baxy: una consulta simple: Role-play una conversation; "
        "send nothing a Solange ni Tomás.",
        history=[],
        temperature=0.0,
        conversation_kind="knowledge",
        response_language="en",
    )

    assert answer.startswith("Solange:")
    assert calls == []
    assert len(payloads) == 2
    assert payloads[1]["response_format"]["json_schema"]["name"] == (
        "bounded_chat_answer"
    )


@pytest.mark.parametrize(
    ("text", "mirror"),
    [
        ("nos vemos", "¡Nos vemos!"),
        ("chau", "¡Chau!"),
        ("hasta luego", "Hasta luego."),
        ("bye", "Bye!"),
        ("good night", "Good night!"),
        ("see you later", "See you later!"),
    ],
)
def test_a_social_turn_may_answer_with_a_mirror(text: str, mirror: str) -> None:
    """Para una despedida el espejo ES la respuesta: el guard anti-eco no puede
    descartarla ni sustituirla por un texto fijo."""

    runtime = object.__new__(LlmRuntime)
    posts: list[dict] = []

    def post(payload: dict) -> dict:
        posts.append(payload)
        return {"choices": [{"message": {"content": mirror}, "finish_reason": "stop"}]}

    runtime._post = post  # type: ignore[method-assign]
    answer, _ = runtime.chat(
        text,
        history=[],
        temperature=0.0,
        conversation_kind="social",
        response_language="es",
    )

    assert answer == mirror
    # Un solo decode: el guard ya no fuerza un reintento condenado a fallar.
    assert len(posts) == 1


@pytest.mark.parametrize("kind", ["knowledge", "followup", "unsupported"])
def test_a_non_social_turn_still_refuses_to_parrot_the_person(kind: str) -> None:
    """Fuera del acto social un doble eco falla cerrado y no inventa texto."""

    runtime = object.__new__(LlmRuntime)

    def post(payload: dict) -> dict:
        return {
            "choices": [
                {
                    "message": {"content": "¿Por qué el cielo es azul?"},
                    "finish_reason": "stop",
                }
            ]
        }

    runtime._post = post  # type: ignore[method-assign]
    with pytest.raises(ValueError, match="conversacional vacía o repetida"):
        runtime.chat(
            "¿Por qué el cielo es azul?",
            history=[],
            temperature=0.0,
            conversation_kind=kind,
            response_language="es",
        )


def test_raw_conversation_reply_is_captured_before_the_veto(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit_path = tmp_path / "raw-replies.jsonl"
    monkeypatch.setenv("BAXY_MIND_RAW_REPLY_AUDIT_PATH", str(audit_path))
    runtime = object.__new__(LlmRuntime)
    responses = iter(
        [
            "La hora actual es 14:30.",
            json.dumps({"answer": "La hora actual es 14:30."}, ensure_ascii=False),
        ]
    )

    def post(_payload: dict[str, object]) -> dict[str, object]:
        return {
            "choices": [
                {
                    "message": {"content": next(responses)},
                    "finish_reason": "stop",
                }
            ]
        }

    runtime._post = post  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="conversacional vacía o repetida"):
        runtime.chat(
            "que hora marca este cacharro",
            history=[],
            temperature=0.0,
            conversation_kind="knowledge",
            response_language="es",
        )

    records = [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [record["attempt"] for record in records] == [1, 2]
    assert records[0]["raw_reply"] == "La hora actual es 14:30."
    assert records[0]["stage"] == "pre_veto"


@pytest.mark.parametrize(
    "initial",
    [
        "Lo siento, no puedo pedir un taxi. ¿Quieres otra cosa?",
        ("No puedo arrastrar archivos a ventanas. Si necesitas otra cosa, avísame."),
        "No puedo hacerlo; puedes intentar moverlo manualmente.",
        "No tengo la capacidad de interactuar con la computadora.",
        "Este efecto no soportado no figura en el catálogo activo.",
        "No puedo activar nada que no esté en el catálogo activo.",
        "No hagas preguntas, no ofrezcas ayuda genérica.",
        (
            "I cannot set the printer because I don't have access to your "
            "computer's printer settings. You'll need to do it manually."
        ),
        "Asunto: Reunión. Estimado Juan, nos vemos.",
        (
            "No puedo tomar capturas de pantalla, guardar archivos en el "
            "escritorio ni abrir exploradores web."
        ),
        (
            "No puedo completar esa tarea. Mis funciones están limitadas a "
            "la conversación y la escritura."
        ),
        "No puedo completar exactamente la variante solicitada.",
        "No puedo abrirlo debido a la limitación sobre la variante exacta.",
    ],
)
def test_unsupported_chat_rewrites_non_declarative_closings(
    initial: str,
) -> None:
    runtime = object.__new__(LlmRuntime)
    payloads: list[dict[str, object]] = []

    def post(payload: dict[str, object]) -> dict[str, object]:
        payloads.append(payload)
        content = (
            initial
            if len(payloads) == 1
            else json.dumps(
                {"answer": "No puedo pedir un taxi desde este equipo."},
                ensure_ascii=False,
            )
        )
        return {
            "choices": [
                {
                    "message": {"content": content},
                    "finish_reason": "stop",
                }
            ]
        }

    runtime._post = post  # type: ignore[method-assign]

    answer, calls = runtime.chat(
        "Pide un taxi para que venga a mi casa",
        history=[],
        temperature=0.0,
        conversation_kind="unsupported",
        response_language="es",
    )

    assert answer == "No puedo pedir un taxi desde este equipo."
    assert calls == []
    assert len(payloads) == 2
    retry_messages = payloads[1]["messages"]
    assert "sustantivo concreto" in repr(retry_messages)
    assert initial not in repr(retry_messages)
    assert "catálogos, efectos" not in repr(retry_messages)


def test_unsupported_language_chat_requires_both_supported_languages() -> None:
    runtime = object.__new__(LlmRuntime)
    captured: dict[str, object] = {}

    def post(payload: dict) -> dict:
        captured["payload"] = payload
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            "Necesito que repitas el pedido en español o inglés "
                            "para interpretarlo con seguridad."
                        )
                    },
                    "finish_reason": "stop",
                }
            ]
        }

    runtime._post = post  # type: ignore[method-assign]
    answer, calls = runtime.chat(
        "Abre a loja do Steam",
        history=[],
        temperature=0.0,
        conversation_kind="unsupported_language",
        response_language="es",
    )

    assert "español" in answer
    assert "inglés" in answer
    assert calls == []
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert "idiomas de operación" in payload["messages"][1]["content"]
    assert payload["messages"][-1]["content"] == (
        "Redacta ahora el aviso de idioma solicitado."
    )
    assert "Abre a loja do Steam" not in repr(payload["messages"])


@pytest.mark.parametrize(
    ("text", "kind", "expected"),
    [
        (
            "En latencia quien gana? en consumo de recursos quien? ram?",
            "knowledge",
            "underspecified_comparison",
        ),
        (
            "Donde dejaste el Powerpoint? Que me hiciste",
            "knowledge",
            "missing_context",
        ),
        (
            "And which of those would you use for the required task?",
            "knowledge",
            "missing_context",
        ),
        (
            "Cierre de Word podía perder trabajo",
            "followup",
            "observation_ack",
        ),
        (
            "What pasaría si another computer lost su Wi-Fi",
            "knowledge",
            None,
        ),
        (
            "Mira, Baxy: una consulta simple: Role-play una conversation; "
            "send nothing a Solange ni Tomás.",
            "knowledge",
            "roleplay_draft",
        ),
        (
            "Just para conversar, una duda breve: Dame a gnocchi recipe para "
            "quiet harbor",
            "knowledge",
            "content_draft",
        ),
        ("Who are you?", "knowledge", "assistant_identity"),
        ("Resume en una frase que puedes hacer.", "knowledge", "assistant_capability"),
        ("Explica que es una nube en una frase.", "knowledge", "physical_cloud_definition"),
        ("Que sonido hace un perro?", "knowledge", "animal_sound"),
        ("Di una frase breve sobre la lluvia.", "knowledge", "complete_sentence"),
    ],
)
def test_no_history_conversation_shape_is_closed(
    text: str,
    kind: str,
    expected: str,
) -> None:
    assert (
        _conversation_presentation_shape(
            text,
            conversation_kind=kind,
            has_history=False,
        )
        == expected
    )
    assert (
        _conversation_presentation_shape(
            text,
            conversation_kind=kind,
            has_history=True,
        )
        != "missing_context"
    )


def test_addressed_roleplay_shape_overrides_a_generic_unsupported_label() -> None:
    text = (
        "Mira, Baxy: una consulta simple: Role-play una conversation; "
        "send nothing a Solange ni Tom\N{LATIN SMALL LETTER A WITH ACUTE}s."
    )
    assert (
        _conversation_presentation_shape(
            text,
            conversation_kind="unsupported",
            has_history=False,
        )
        == "roleplay_draft"
    )


@pytest.mark.parametrize(
    ("user_text", "shape", "good", "bad"),
    [
        (
            "Who are you?",
            "assistant_identity",
            "I am BAXY, a local companion on this PC.",
            "I couldn't answer who I am.",
        ),
        (
            "Resume en una frase que puedes hacer.",
            "assistant_capability",
            "Puedo conversar, explicar y responder preguntas.",
            "No puedo ayudarte con eso.",
        ),
        (
            "Explica que es una nube en una frase.",
            "physical_cloud_definition",
            "Una nube contiene gotas de agua suspendidas en la atmósfera.",
            "Una nube ofrece software y aplicaciones por internet.",
        ),
        (
            "Que sonido hace un perro?",
            "animal_sound",
            "Un perro ladra y también puede gruñir.",
            "Un perro muerde o lame.",
        ),
        (
            "Di una frase breve sobre la lluvia.",
            "complete_sentence",
            "La lluvia refresca las calles al caer.",
            "Lluvia de agua que cae de los cielos.",
        ),
    ],
)
def test_daily_use_presentation_shapes_reject_measured_semantic_faults(
    user_text: str,
    shape: str,
    good: str,
    bad: str,
) -> None:
    assert not _shaped_conversation_answer_violates_contract(good, user_text, shape)
    assert _shaped_conversation_answer_violates_contract(bad, user_text, shape)


def test_joke_request_is_not_shaped_as_an_observation() -> None:
    assert (
        _conversation_presentation_shape(
            "find me a joke related to baseball",
            conversation_kind="knowledge",
            has_history=False,
        )
        is None
    )


def test_missing_context_formatter_receives_only_bounded_anchors() -> None:
    payload = json.loads(
        _shaped_presentation_text(
            "Donde dejaste el Powerpoint? Que me hiciste",
            "missing_context",
        )
    )
    assert payload == {
        "reference_present": False,
        "literal_anchors": ["powerpoint"],
    }


def test_content_formatter_removes_only_bounded_assistant_envelopes() -> None:
    assert (
        _shaped_presentation_text(
            "Baxy — one thing: give me a soup recipe for a cold evening.",
            "content_draft",
        )
        == "give me a soup recipe for a cold evening."
    )
    assert (
        _shaped_presentation_text(
            "Write a story where Baxy is a city.",
            "content_draft",
        )
        == "Write a story where Baxy is a city."
    )
    assert (
        _shaped_presentation_text(
            "Baxy: a question: Rewrite the sentence close every tab more politely",
            "content_draft",
        )
        == "Rewrite the sentence close every tab more politely"
    )
    assert (
        _shaped_presentation_text(
            "Mira, Baxy: una consulta simple: Role-play una conversation; send nothing",
            "content_draft",
        )
        == "Role-play una conversation; send nothing"
    )
    assert (
        _shaped_presentation_text(
            "Listen, Baxy: one brief request: Translate instala Inkscape into English",
            "translation",
        )
        == "Translate instala Inkscape into English"
    )
    assert (
        _shaped_presentation_text(
            "Just para conversar, una duda breve: Dame a gnocchi recipe para quiet "
            "harbor",
            "content_draft",
        )
        == "Dame a gnocchi recipe para quiet harbor"
    )
    assert json.loads(
        _shaped_presentation_text(
            "Mira, Baxy: una consulta simple: Role-play una conversation; "
            "send nothing a Solange ni Tomás.",
            "roleplay_draft",
        )
    ) == {
        "draft_kind": "fictional_dialogue",
        "participant_names": ["Solange", "Tomás"],
        "external_send": False,
    }


@pytest.mark.parametrize(
    "answer",
    [
        "I cannot play a role or simulate a conversation.",
        "Solange and Tomás are the requested participants.",
        "Solange: Hello.",
    ],
)
def test_roleplay_draft_visible_answer_rejects_refusal_or_missing_dialogue(
    answer: str,
) -> None:
    assert (
        _shaped_conversation_answer_violates_contract(
            answer,
            "Role-play a conversation between Solange and Tomás; send nothing.",
            "roleplay_draft",
        )
        is True
    )


def test_roleplay_draft_visible_answer_accepts_named_exchange() -> None:
    assert (
        _shaped_conversation_answer_violates_contract(
            "Solange: Hello, Tomás.\nTomás: Hi, Solange.",
            "Role-play a conversation between Solange and Tomás; send nothing.",
            "roleplay_draft",
        )
        is False
    )


@pytest.mark.parametrize(
    "answer",
    [
        "Te dejé el PowerPoint en Google Drive.",
        "¿Dónde quieres que busque el PowerPoint?",
        "El literal_anchor disponible es PowerPoint.",
    ],
)
def test_missing_context_visible_answer_rejects_invention(answer: str) -> None:
    assert (
        _shaped_conversation_answer_violates_contract(
            answer,
            "Donde dejaste el Powerpoint? Que me hiciste",
            "missing_context",
        )
        is True
    )


def test_missing_context_visible_answer_accepts_bounded_model_prose() -> None:
    assert (
        _shaped_conversation_answer_violates_contract(
            "No tengo contexto de un PowerPoint creado o movido anteriormente.",
            "Donde dejaste el Powerpoint? Que me hiciste",
            "missing_context",
        )
        is False
    )


def test_unsupported_habit_answer_accepts_specific_model_prose() -> None:
    assert (
        llm_module._unsupported_answer_violates_contract(
            "No puedo crear y marcar ese hábito como se pidió.",
            "armá el hábito de salir a correr y marcá que ya lo hice",
        )
        is False
    )


def test_current_fact_limitation_accepts_updated_verification_anchor() -> None:
    request = "quien es el actual primer ministro de rusia"

    assert (
        llm_module._unsupported_answer_violates_contract(
            "No puedo verificar información actualizada.",
            request,
        )
        is False
    )
    assert (
        llm_module._unsupported_answer_violates_contract(
            "El primer ministro es una persona concreta.",
            request,
        )
        is True
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Listoo la gpu dejo de usarseee", "followup"),
        ("Ahora estoy poniendo música, ¿lo quieres probar?", "knowledge"),
        ("Elige el primer resultado de YouTube", "unsupported"),
        ("Hay algo mas que use gpu??", "unsupported"),
        ("Pide un taxi para que venga a mi casa", "unsupported"),
        ("Juega conmigo al ajedrez por favor", "unsupported"),
        ("Get rid of the five p. m. alarm", "unsupported"),
        ("Abrir Twitter en mi iPhone, no, en mi tablet", "unsupported"),
    ],
)
def test_non_effect_conversation_presentation_distinguishes_observations(
    text: str,
    expected: str,
) -> None:
    decision = {
        "mode": "conversation",
        "operation": None,
        "question": "",
        "conversation_kind": "unsupported",
        "effect_count": "zero",
        "effect_operations": [],
        "effect_verification": "not_applicable",
        "response_language": "es",
    }

    result = apply_non_effect_conversation_classification(decision, text)

    assert result["conversation_kind"] == expected


@pytest.mark.parametrize(
    "text",
    [
        "where is new zealand located on a map",
    ],
)
def test_unpunctuated_interrogatives_are_presented_as_knowledge(
    text: str,
) -> None:
    decision = {
        "mode": "conversation",
        "operation": None,
        "question": "",
        "conversation_kind": "unsupported",
        "effect_count": "zero",
        "effect_operations": [],
        "effect_verification": "not_applicable",
        "response_language": "es",
    }

    result = apply_non_effect_conversation_classification(decision, text)

    assert result["conversation_kind"] == "knowledge"


@pytest.mark.parametrize(
    "text",
    [
        "cual es mi direccion ip",
        "que fecha y hora tenemos",
        "como anda la maquina en general",
        "how bright is my screen right now",
    ],
)
def test_a_retired_catalog_effect_can_never_be_presented_as_knowledge(
    text: str,
) -> None:
    """BAXY must not answer a question about this machine from memory.

    Measured on the fresh paraphrase corpus of goal 03: when a veto retired the
    catalogue operation that would have observed the machine, presentation
    relabelled the turn as knowledge and the model invented the answer -- "Tu
    dirección IP es 192.168.1.100", a date in 2023, "la maquina está
    funcionando correctamente". Three fabricated machine states presented as
    observed, which is the one thing BAXY may never do. The decider had already
    said the answer needs an observation; presentation may not overrule that.
    """

    decision = {
        "mode": "conversation",
        "operation": None,
        "question": "",
        "conversation_kind": "unsupported",
        "effect_count": "zero",
        "effect_operations": [],
        "effect_verification": "not_applicable",
        "response_language": "es",
    }

    presented = apply_non_effect_conversation_classification(decision, text)
    guarded = apply_non_effect_conversation_classification(
        decision,
        text,
        retired_catalog_effect=True,
    )

    # Without the marker these read as ordinary questions, which is exactly how
    # the fabrication got in.
    assert presented["conversation_kind"] == "knowledge"
    assert guarded["conversation_kind"] == "unsupported"


@pytest.mark.parametrize(
    "text",
    [
        "tengo el bluetooth encendido",
        "tengo el brillo al máximo",
        "the screen brightness is at maximum",
    ],
)
def test_a_retired_catalog_effect_still_acknowledges_a_user_observation(
    text: str,
) -> None:
    decision = {
        "mode": "conversation",
        "operation": None,
        "question": "",
        "conversation_kind": "unsupported",
        "effect_count": "zero",
        "effect_operations": [],
        "effect_verification": "not_applicable",
        "response_language": "es",
    }

    result = apply_non_effect_conversation_classification(
        decision,
        text,
        retired_catalog_effect=True,
    )

    assert result["conversation_kind"] == "followup"


@pytest.mark.parametrize(
    "text",
    ["tengo el bluetooth encendido", "tengo el brillo al máximo"],
)
def test_authoritative_surface_does_not_turn_an_observation_into_unsupported(
    text: str,
) -> None:
    decision = {
        "mode": "conversation",
        "operation": None,
        "question": "",
        "conversation_kind": "followup",
        "effect_count": "zero",
        "effect_operations": [],
        "effect_verification": "not_applicable",
        "response_language": "es",
    }

    result = apply_non_effect_conversation_classification(decision, text)

    assert result["conversation_kind"] == "followup"


def test_current_office_holder_question_stays_honestly_unsupported() -> None:
    decision = {
        "mode": "conversation",
        "operation": None,
        "question": "",
        "conversation_kind": "unsupported",
        "effect_count": "zero",
        "effect_operations": [],
        "effect_verification": "not_applicable",
        "response_language": "es",
    }

    result = apply_non_effect_conversation_classification(
        decision,
        "quien es el actual primer ministro de rusia",
    )

    assert result["conversation_kind"] == "unsupported"


def test_turn_chat_rejects_unknown_internal_conversation_kind() -> None:
    runtime = object.__new__(LlmRuntime)
    with pytest.raises(ValueError, match="tipo de conversación"):
        runtime.chat("Hola", conversation_kind="invented")


def test_turn_chat_rejects_unknown_internal_response_language() -> None:
    runtime = object.__new__(LlmRuntime)
    with pytest.raises(ValueError, match="idioma de respuesta"):
        runtime.chat("Hola", response_language="invented")


def test_candidate_free_count_mismatch_never_rewrites_primary_effects() -> None:
    runtime = object.__new__(LlmRuntime)
    labels: list[str] = []
    responses = iter(
        [
            {
                "mode": "plan",
                "operation": "",
                "question": "",
                "conversation_kind": "",
                "effect_count": "multiple",
                "effect_operations": ["app.open", "app.open"],
                "response_language": "es",
            },
            guard_response(effect_count="one"),
        ]
    )

    def constrained(_payload: dict, label: str) -> dict:
        labels.append(label)
        return next(responses)

    runtime._post_schema_object = constrained  # type: ignore[method-assign]
    result = runtime.decide_turn(
        "Realiza dos aperturas distintas.",
        [turn_candidate("app.open", "Abre una aplicación.")],
    )

    assert labels == ["la política de turno", "el veto semántico de efectos"]
    assert result["mode"] == "plan"
    assert result["operation"] is None
    assert result["effect_count"] == "multiple"
    assert result["effect_operations"] == ["app.open", "app.open"]
    assert result["effect_verification"] == "disagreement"


def test_candidate_free_multiple_signal_only_forces_independent_replanning() -> None:
    runtime = object.__new__(LlmRuntime)
    responses = iter(
        [
            {
                "mode": "action",
                "operation": "app.open",
                "question": "",
                "conversation_kind": "",
                "effect_count": "one",
                "effect_operations": ["app.open"],
                "response_language": "es",
            },
            guard_response(effect_count="multiple"),
            {"effect_count": "multiple"},
        ]
    )
    runtime._post_schema_object = (  # type: ignore[method-assign]
        lambda _payload, _label: next(responses)
    )

    result = runtime.decide_turn(
        "Abre dos aplicaciones.",
        [turn_candidate("app.open", "Abre una aplicación.")],
    )

    assert result["mode"] == "plan"
    assert result["operation"] is None
    assert result["effect_count"] == "one"
    assert result["effect_operations"] == ["app.open"]
    assert result["effect_verification"] == "disagreement"


@pytest.mark.parametrize(
    ("confirmed_count", "expected_mode"),
    [("zero", "plan"), ("one", "action")],
)
def test_only_an_independent_one_can_reject_a_multiple_signal(
    confirmed_count: str,
    expected_mode: str,
) -> None:
    runtime = object.__new__(LlmRuntime)
    payloads: dict[str, dict] = {}

    def constrained(payload: dict, label: str) -> dict:
        payloads[label] = payload
        if label == "la política de turno":
            return {
                "mode": "action",
                "operation": "audio.mute",
                "question": "",
                "conversation_kind": "",
                "effect_count": "one",
                "effect_operations": ["audio.mute"],
                "response_language": "es",
            }
        if label == "el veto semántico de efectos":
            return guard_response(effect_count="multiple")
        if label == "la verificación independiente del conteo de efectos":
            return {"effect_count": confirmed_count}
        assert label == "la verificación de compatibilidad de la operación"
        return {"compatible": True}

    runtime._post_schema_object = constrained  # type: ignore[method-assign]
    result = runtime.decide_turn(
        "Silencia la configuración de audio.",
        [
            turn_candidate(
                "audio.mute",
                "Silencia o reactiva el audio.",
                required=("muted",),
            )
        ],
    )

    assert result["mode"] == expected_mode
    if expected_mode == "action":
        assert result["operation"] == "audio.mute"
        assert result["effect_verification"] == "agreed"
    else:
        assert result["operation"] is None
        assert result["effect_verification"] == "disagreement"
    count_payload = payloads["la verificación independiente del conteo de efectos"]
    assert "audio.mute" not in repr(count_payload)


def test_independent_multiple_count_vetoes_every_primary_action() -> None:
    runtime = object.__new__(LlmRuntime)
    labels: list[str] = []
    responses = iter(
        [
            {
                "mode": "action",
                "operation": "system.time",
                "question": "",
                "conversation_kind": "",
                "effect_count": "one",
                "effect_operations": ["system.time"],
                "response_language": "es",
            },
            guard_response(effect_count="one"),
            {"effect_count": "multiple"},
        ]
    )

    def constrained(_payload: dict, label: str) -> dict:
        labels.append(label)
        return next(responses)

    runtime._post_schema_object = constrained  # type: ignore[method-assign]
    result = runtime.decide_turn(
        "Dime la hora y revisa la CPU.",
        [
            turn_candidate("system.time", "Consulta la hora local."),
            turn_candidate("system.status", "Consulta el estado de CPU."),
        ],
    )

    assert labels == [
        "la política de turno",
        "el veto semántico de efectos",
        "la verificación independiente del conteo de efectos",
    ]
    assert result["mode"] == "plan"
    assert result["operation"] is None
    assert result["effect_count"] == "one"
    assert result["effect_operations"] == ["system.time"]
    assert result["effect_verification"] == "disagreement"


def test_unresolved_reference_beats_unreliable_guard_cardinality() -> None:
    runtime = object.__new__(LlmRuntime)
    responses = iter(
        [
            {
                "mode": "action",
                "operation": "app.open",
                "question": "",
                "conversation_kind": "",
                "effect_count": "one",
                "effect_operations": ["app.open"],
                "response_language": "es",
            },
            guard_response(unresolved=True, effect_count="multiple"),
            {"effect_count": "one"},
        ]
    )
    runtime._post_schema_object = (  # type: ignore[method-assign]
        lambda _payload, _label: next(responses)
    )

    result = runtime.decide_turn(
        "Abre eso.",
        [
            turn_candidate(
                "app.open",
                "Abre una aplicación por nombre.",
                required=("appId",),
            )
        ],
    )

    assert result["mode"] == "action"
    assert result["operation"] == "app.open"
    assert result["effect_verification"] == "grounding_required"


def test_required_argument_needs_independent_contract_compatibility() -> None:
    runtime = object.__new__(LlmRuntime)
    payloads: dict[str, dict] = {}

    def constrained(payload: dict, label: str) -> dict:
        payloads[label] = payload
        if label == "la política de turno":
            return {
                "mode": "action",
                "operation": "app.open",
                "question": "",
                "conversation_kind": "",
                "effect_count": "one",
                "effect_operations": ["app.open"],
                "response_language": "es",
            }
        if label == "el veto semántico de efectos":
            return guard_response(effect_count="one")
        if label == "la verificación independiente del conteo de efectos":
            return {"effect_count": "one"}
        assert label == "la verificación de compatibilidad de la operación"
        return {"compatible": False}

    runtime._post_schema_object = constrained  # type: ignore[method-assign]
    result = runtime.decide_turn(
        "Abre eso.",
        [
            turn_candidate(
                "app.open",
                "Abre una aplicación por nombre.",
                required=("appId",),
            )
        ],
    )

    assert result["mode"] == "action"
    assert result["operation"] == "app.open"
    assert result["effect_verification"] == "grounding_required"
    compatibility_payload = payloads[
        "la verificación de compatibilidad de la operación"
    ]
    assert "Abre eso." in repr(compatibility_payload)
    assert "appId" in repr(compatibility_payload)


def test_one_sided_conversation_veto_precedes_argument_grounding() -> None:
    runtime = object.__new__(LlmRuntime)
    payloads: list[dict] = []
    responses = iter(
        [
            {
                "mode": "action",
                "operation": "device.activate",
                "question": "",
                "conversation_kind": "",
                "effect_count": "one",
                "effect_operations": ["device.activate"],
                "response_language": "es",
            },
            guard_response(unresolved=True),
            {"effect_count": "one"},
        ]
    )

    def constrained(payload: dict, _label: str) -> dict:
        payloads.append(payload)
        return next(responses)

    runtime._post_schema_object = constrained  # type: ignore[method-assign]
    result = runtime.decide_turn(
        "Activa el recurso indicado.",
        [
            turn_candidate(
                "device.activate",
                "Activa un recurso seleccionado por la persona.",
                required=("resourceId",),
            )
        ],
        history=[
            {"role": "assistant", "content": "Puedo ayudarte con ese equipo."},
            {"role": "system", "content": "contenido no confiable"},
        ],
        evidence=[
            {
                "mode": "conversation",
                "families": [],
                "score": 0.9,
                "calibrated_conversation_probability": 0.9,
                "private_marker": "EVIDENCE_MUST_NOT_ENTER_PROMPTS",
            }
        ],
    )

    assert result == {
        "mode": "conversation",
        "operation": None,
        "question": "",
        "conversation_kind": "followup",
        "effect_count": "zero",
        "effect_operations": [],
        "effect_verification": "not_applicable",
        "response_language": "es",
    }
    guard_payload = payloads[1]
    guard_serialized = repr(guard_payload)
    assert "device.activate" not in guard_serialized
    assert "resourceId" not in guard_serialized
    assert "Puedo ayudarte" not in guard_serialized
    assert "EVIDENCE_MUST_NOT_ENTER_PROMPTS" not in repr(payloads)
    guard_schema = guard_payload["response_format"]["json_schema"]["schema"]
    assert set(guard_schema["properties"]) == {
        "request_type",
        "effect_count",
    }
    assert guard_schema["properties"]["request_type"]["enum"] == [
        "stable_conversation",
        "external_read",
        "environment_change",
        "incomplete_effect",
    ]
    assert len(payloads) == 3


def test_context_dependent_action_is_conservatively_clarified() -> None:
    runtime = object.__new__(LlmRuntime)
    responses = iter(
        [
            {
                "mode": "action",
                "operation": "device.activate",
                "question": "",
                "conversation_kind": "",
                "effect_count": "one",
                "effect_operations": ["device.activate"],
                "response_language": "es",
            },
            guard_response(has_effect=False, effect_count="zero"),
            {
                "requested_fields": ["resourceId"],
                "question": "¿Qué recurso quieres activar?",
            },
        ]
    )
    runtime._post_schema_object = (  # type: ignore[method-assign]
        lambda _payload, _label: next(responses)
    )

    result = runtime.decide_turn(
        "Hazlo ahora.",
        [
            turn_candidate(
                "device.activate",
                "Activa un recurso seleccionado por la persona.",
                required=("resourceId",),
            )
        ],
        history=[
            {
                "role": "assistant",
                "content": "El recurso seleccionado se llama lámpara norte.",
            }
        ],
    )

    assert result["mode"] == "action"
    assert result["effect_verification"] == "grounding_required"

    tool = {
        "function": {
            "canonical_name": "device.activate",
            "description": "Activa un recurso seleccionado por la persona.",
            "parameters": turn_candidate(
                "device.activate",
                "Activa un recurso seleccionado por la persona.",
                required=("resourceId",),
            )["arguments_schema"],
        }
    }

    class GroundingRuntime:
        @staticmethod
        def extract_direct_arguments(
            _objective: str,
            _tool: dict,
        ) -> DirectArgumentExtraction:
            return DirectArgumentExtraction(
                None,
                (),
                "¿Qué recurso quieres activar?",
            )

    clarified = apply_turn_action_grounding_gate(
        result,
        "Hazlo ahora.",
        {"device.activate": tool},
        GroundingRuntime(),
    )
    assert clarified["mode"] == "clarify"
    assert clarified["operation"] is None
    assert clarified["effect_operations"] == []


def test_incomplete_compound_plan_loses_all_effect_authority() -> None:
    runtime = object.__new__(LlmRuntime)
    responses = iter(
        [
            {
                "mode": "plan",
                "operation": "",
                "question": "",
                "conversation_kind": "",
                "effect_count": "multiple",
                "effect_operations": [
                    "source.inspect",
                    "destination.update",
                ],
                "response_language": "es",
            },
            guard_response(unresolved=True, effect_count="multiple"),
        ]
    )
    runtime._post_schema_object = (  # type: ignore[method-assign]
        lambda _payload, _label: next(responses)
    )

    result = runtime.decide_turn(
        "Inspecciona el origen y actualiza el destino.",
        [
            turn_candidate(
                "source.inspect",
                "Inspecciona el origen indicado.",
                required=("sourceId",),
            ),
            turn_candidate(
                "destination.update",
                "Actualiza el destino indicado.",
                required=("destinationId",),
            ),
        ],
    )

    assert result["mode"] == "conversation"
    assert result["operation"] is None
    assert result["effect_operations"] == []
    assert result["effect_verification"] == "not_applicable"


def test_complete_operation_without_arguments_preserves_primary_action() -> None:
    runtime = object.__new__(LlmRuntime)
    labels: list[str] = []
    responses = iter(
        [
            {
                "mode": "action",
                "operation": "system.refresh",
                "question": "",
                "conversation_kind": "",
                "effect_count": "one",
                "effect_operations": ["system.refresh"],
                "response_language": "es",
            },
            guard_response(),
            {"effect_count": "one"},
        ]
    )

    def constrained(_payload: dict, label: str) -> dict:
        labels.append(label)
        return next(responses)

    runtime._post_schema_object = constrained  # type: ignore[method-assign]
    result = runtime.decide_turn(
        "Actualiza el estado.",
        [turn_candidate("system.refresh", "Actualiza el estado local.")],
    )

    assert result["mode"] == "action"
    assert result["question"] == ""
    assert result["effect_verification"] == "agreed"
    assert labels == [
        "la política de turno",
        "el veto semántico de efectos",
        "la verificación independiente del conteo de efectos",
    ]


@pytest.mark.parametrize(
    "guard_raw",
    [
        None,
        {},
        {"has_effect_request": True},
        {
            **guard_response(),
            "unexpected": True,
        },
        {
            "has_effect_request": 1,
            "has_unresolved_required_information": False,
            "effect_count": "one",
        },
        {
            "has_effect_request": True,
            "has_unresolved_required_information": False,
            "effect_count": "many",
        },
    ],
)
def test_malformed_semantic_guard_never_preserves_effect_authority(
    guard_raw: object,
) -> None:
    assert derive_semantic_effect_state(guard_raw) == "invalid"

    runtime = object.__new__(LlmRuntime)
    responses = iter(
        [
            {
                "mode": "action",
                "operation": "system.refresh",
                "question": "",
                "conversation_kind": "",
                "effect_count": "one",
                "effect_operations": ["system.refresh"],
                "response_language": "es",
            },
            guard_raw,
        ]
    )
    runtime._post_schema_object = (  # type: ignore[method-assign]
        lambda _payload, _label: next(responses)
    )
    result = runtime.decide_turn(
        "Solicitud evaluada.",
        [turn_candidate("system.refresh", "Actualiza el estado local.")],
    )
    assert result["mode"] == "conversation"
    assert result["operation"] is None
    assert result["effect_operations"] == []


def test_turn_candidates_require_an_authenticated_argument_schema() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._post_schema_object = (  # type: ignore[method-assign]
        lambda _payload, _label: pytest.fail("no debe invocar al modelo")
    )

    with pytest.raises(ValueError, match="forma inválida"):
        runtime.decide_turn(
            "Solicitud cualquiera.",
            [{"name": "device.activate", "description": "Activa un recurso."}],
        )


def test_turn_candidate_field_contract_matches_sidecar_schema_names() -> None:
    runtime = object.__new__(LlmRuntime)
    payloads: list[dict] = []

    def constrained(payload: dict, label: str) -> dict:
        payloads.append(payload)
        if label == "la política de turno":
            return {
                "mode": "action",
                "operation": "device.inspect",
                "question": "",
                "conversation_kind": "",
                "effect_count": "one",
                "effect_operations": ["device.inspect"],
                "response_language": "es",
            }
        if label == "el veto semántico de efectos":
            return guard_response(unresolved=True)
        return {
            "requested_fields": ["Target_ID"],
            "question": "¿Qué dispositivo quieres inspeccionar?",
        }

    runtime._post_schema_object = constrained  # type: ignore[method-assign]
    result = runtime.decide_turn(
        "Inspecciona el dispositivo seleccionado.",
        [
            turn_candidate(
                "device.inspect",
                "Inspecciona un dispositivo.",
                required=("Target_ID",),
            )
        ],
    )

    assert result["mode"] == "action"
    assert result["effect_verification"] == "grounding_required"
    assert "Target_ID" not in repr(payloads[:2])


@pytest.mark.parametrize(
    ("primary", "history", "score", "expected_kind"),
    [
        (
            {
                "mode": "action",
                "operation": "app.open",
                "question": "",
                "conversation_kind": "",
                "effect_count": "one",
                "effect_operations": ["app.open"],
                "response_language": "es",
            },
            [],
            -0.25,
            "knowledge",
        ),
        (
            {
                "mode": "plan",
                "operation": "",
                "question": "",
                "conversation_kind": "",
                "effect_count": "multiple",
                "effect_operations": ["app.open", "app.open"],
                "response_language": "es",
            },
            [{"role": "assistant", "content": "Contexto previo."}],
            0.88,
            "followup",
        ),
    ],
)
def test_one_sided_evidence_only_vetoes_final_effect_modes(
    primary: dict[str, object],
    history: list[dict[str, str]],
    score: float,
    expected_kind: str,
) -> None:
    runtime = object.__new__(LlmRuntime)
    responses = iter(
        [
            primary,
            guard_response(
                effect_count=(
                    "multiple" if primary["effect_count"] == "multiple" else "one"
                )
            ),
            *([{"effect_count": "one"}] if primary["effect_count"] == "one" else []),
        ]
    )
    runtime._post_schema_object = (  # type: ignore[method-assign]
        lambda _payload, _label: next(responses)
    )

    result = runtime.decide_turn(
        "Petición evaluada semánticamente.",
        [turn_candidate("app.open", "Abre una aplicación.")],
        history=history,
        evidence=[
            {
                "mode": "conversation",
                "families": [],
                "score": score,
                "calibrated_conversation_probability": 0.96,
                "candidate_family_match": False,
                "operation": "invented.operation",
                "plan": ["invented.operation"],
            }
        ],
    )

    assert result == {
        "mode": "conversation",
        "operation": None,
        "question": "",
        "conversation_kind": expected_kind,
        "effect_count": "zero",
        "effect_operations": [],
        "effect_verification": "not_applicable",
        "response_language": "es",
    }


@pytest.mark.parametrize(
    "invalid_card",
    [
        {
            "mode": "action",
            "families": [],
            "score": 0.9,
            "calibrated_conversation_probability": 0.9,
        },
        {
            "mode": "conversation",
            "families": ["apps"],
            "score": 0.9,
            "calibrated_conversation_probability": 0.9,
        },
        {
            "mode": "conversation",
            "families": [],
            "calibrated_conversation_probability": 0.9,
        },
        {
            "mode": "conversation",
            "families": [],
            "score": float("nan"),
            "calibrated_conversation_probability": 0.9,
        },
        {
            "mode": "conversation",
            "families": [],
            "score": float("inf"),
            "calibrated_conversation_probability": 0.9,
        },
        {
            "mode": "conversation",
            "families": [],
            "score": -1.01,
            "calibrated_conversation_probability": 0.9,
        },
        {
            "mode": "conversation",
            "families": [],
            "score": 1.01,
            "calibrated_conversation_probability": 0.9,
        },
        {
            "mode": "conversation",
            "families": [],
            "score": True,
            "calibrated_conversation_probability": 0.9,
        },
        {
            "mode": "conversation",
            "families": [],
            "score": 0.9,
            "calibrated_conversation_probability": 0.9,
            "candidate_family_match": True,
        },
        {
            "mode": "conversation",
            "families": [],
            "score": 0.9,
            "calibrated_conversation_probability": float("nan"),
        },
        {
            "mode": "conversation",
            "families": [],
            "score": 0.9,
            "calibrated_conversation_probability": 1.01,
        },
        {
            "mode": "conversation",
            "families": [],
            "score": 0.9,
            "calibrated_conversation_probability": False,
        },
    ],
)
def test_invalid_conversation_evidence_abstains_fail_closed(
    invalid_card: dict[str, object],
) -> None:
    runtime = object.__new__(LlmRuntime)
    responses = iter(
        [
            {
                "mode": "action",
                "operation": "app.open",
                "question": "",
                "conversation_kind": "",
                "effect_count": "one",
                "effect_operations": ["app.open"],
                "response_language": "es",
            },
            guard_response(),
            {"effect_count": "one"},
        ]
    )
    runtime._post_schema_object = (  # type: ignore[method-assign]
        lambda _payload, _label: next(responses)
    )

    result = runtime.decide_turn(
        "Petición evaluada semánticamente.",
        [turn_candidate("app.open", "Abre una aplicación.")],
        evidence=[invalid_card],
    )

    assert result["mode"] == "action"
    assert result["operation"] == "app.open"
    assert result["effect_operations"] == ["app.open"]
    assert result["effect_verification"] == "agreed"


def test_one_sided_evidence_cannot_promote_a_non_effect_turn() -> None:
    runtime = object.__new__(LlmRuntime)
    calls = 0

    def constrained(_payload: dict, label: str) -> dict:
        nonlocal calls
        calls += 1
        if label == "el veto semántico de efectos":
            return guard_response(
                has_effect=False,
                effect_count="zero",
            )
        return {
            "mode": "conversation",
            "operation": "",
            "question": "",
            "conversation_kind": "social",
            "effect_count": "zero",
            "effect_operations": [],
            "response_language": "es",
        }

    runtime._post_schema_object = constrained  # type: ignore[method-assign]
    result = runtime.decide_turn(
        "Turno social.",
        [turn_candidate("app.open", "Abre una aplicación.")],
        evidence=[
            {
                "mode": "conversation",
                "families": [],
                "score": 0.8,
                "calibrated_conversation_probability": 0.95,
                "operation": "app.open",
                "families_to_select": ["apps"],
            }
        ],
    )

    assert calls == 2
    assert result["mode"] == "conversation"
    assert result["conversation_kind"] == "social"
    assert result["operation"] is None
    assert result["effect_operations"] == []


def test_candidate_free_guard_ignores_reported_cardinality() -> None:
    assert (
        derive_semantic_effect_state(guard_response(effect_count="zero")) == "complete"
    )
    assert (
        derive_semantic_effect_state(guard_response(effect_count="multiple"))
        == "complete"
    )
    assert (
        derive_semantic_effect_state(
            guard_response(has_effect=False, unresolved=True, effect_count="multiple")
        )
        == "no_effect"
    )
    assert (
        derive_semantic_effect_state(guard_response(unresolved=True)) == "not_complete"
    )


def test_candidate_free_guard_schema_contains_no_operation_authority() -> None:
    runtime = object.__new__(LlmRuntime)
    captured: dict[str, object] = {}

    def complete_response(payload: dict, _label: str) -> dict:
        captured["payload"] = payload
        return guard_response(effect_count="multiple")

    runtime._post_schema_object = complete_response  # type: ignore[method-assign]
    assert runtime._verify_semantic_effect_shape("Abre la calculadora.") == (
        "complete",
        "multiple",
    )
    payload = captured["payload"]
    assert isinstance(payload, dict)
    schema = payload["response_format"]["json_schema"]["schema"]
    assert set(schema["properties"]) == {
        "request_type",
        "effect_count",
    }
    serialized = repr(payload)
    assert "app.open" not in serialized
    assert "Operaciones candidatas" not in serialized
    assert "arguments_schema" not in serialized
    assert payload["max_tokens"] == 64
    assert payload["temperature"] == 0.0
    assert payload["seed"] == 0


def test_candidate_free_guard_is_reused_only_within_one_request_attempt() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._semantic_effect_cache = {}
    calls = 0

    def complete_response(_payload: dict, _label: str) -> dict:
        nonlocal calls
        calls += 1
        return guard_response(has_effect=False, effect_count="zero")

    runtime._post_schema_object = complete_response  # type: ignore[method-assign]

    first = runtime._verify_semantic_effect_shape("¿Por qué el cielo es azul?")
    repeated = runtime._verify_semantic_effect_shape("¿Por qué el cielo es azul?")
    runtime._semantic_effect_cache = {}
    next_attempt = runtime._verify_semantic_effect_shape("¿Por qué el cielo es azul?")

    assert first == repeated == next_attempt == ("no_effect", "zero")
    assert calls == 2


def test_owned_runtime_reuses_valid_guard_for_exact_text_across_requests() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._semantic_effect_cache = {}
    runtime._validated_classifier_reuse_enabled = True
    runtime._validated_classifier_reuse_lock = threading.Lock()
    runtime._semantic_effect_reuse_cache = OrderedDict()
    calls = 0

    def complete_response(_payload: dict, _label: str) -> dict:
        nonlocal calls
        calls += 1
        return guard_response(has_effect=False, effect_count="zero")

    runtime._post_schema_object = complete_response  # type: ignore[method-assign]
    text = "¿Por qué el cielo es azul?"

    assert runtime._verify_semantic_effect_shape(text) == ("no_effect", "zero")
    runtime._semantic_effect_cache = {}
    assert runtime._verify_semantic_effect_shape(text) == ("no_effect", "zero")
    assert calls == 1


def test_classifier_reuse_is_exact_bounded_and_cleared_with_model() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._validated_classifier_reuse_enabled = True
    runtime._validated_classifier_reuse_lock = threading.Lock()
    runtime._semantic_effect_reuse_cache = OrderedDict()
    runtime._response_language_reuse_cache = OrderedDict()
    runtime._effect_count_reuse_cache = OrderedDict()
    runtime._operation_compatibility_reuse_cache = OrderedDict()

    for index in range(llm_module.VALIDATED_CLASSIFIER_REUSE_CAPACITY + 1):
        runtime._validated_classifier_reuse_put(
            "_response_language_reuse_cache",
            f"mensaje-{index}",
            "es",
        )

    assert (
        runtime._validated_classifier_reuse_get(
            "_response_language_reuse_cache",
            "mensaje-0",
        )
        is None
    )
    assert (
        runtime._validated_classifier_reuse_get(
            "_response_language_reuse_cache",
            f"mensaje-{llm_module.VALIDATED_CLASSIFIER_REUSE_CAPACITY}",
        )
        == "es"
    )
    assert (
        runtime._validated_classifier_reuse_get(
            "_response_language_reuse_cache",
            f"mensaje-{llm_module.VALIDATED_CLASSIFIER_REUSE_CAPACITY} ",
        )
        is None
    )

    runtime._clear_validated_classifier_reuse()
    assert runtime._semantic_effect_reuse_cache == {}
    assert runtime._response_language_reuse_cache == {}
    assert runtime._effect_count_reuse_cache == {}
    assert runtime._operation_compatibility_reuse_cache == {}


def test_owned_runtime_reuses_valid_effect_count_for_exact_text() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._validated_classifier_reuse_enabled = True
    runtime._validated_classifier_reuse_lock = threading.Lock()
    runtime._effect_count_reuse_cache = OrderedDict()
    calls = 0

    def response(_payload: dict, _label: str) -> dict:
        nonlocal calls
        calls += 1
        return {"effect_count": "one"}

    runtime._post_schema_object = response  # type: ignore[method-assign]
    text = "Baja el volumen al 20 %."

    assert runtime._verify_effect_count(text) == "one"
    assert runtime._verify_effect_count(text) == "one"
    assert runtime._verify_effect_count(text + " ") == "one"
    assert calls == 2


def test_owned_runtime_reuses_valid_false_compatibility_for_exact_contract() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._validated_classifier_reuse_enabled = True
    runtime._validated_classifier_reuse_lock = threading.Lock()
    runtime._operation_compatibility_reuse_cache = OrderedDict()
    calls = 0

    def response(_payload: dict, _label: str) -> dict:
        nonlocal calls
        calls += 1
        return {"compatible": False}

    runtime._post_schema_object = response  # type: ignore[method-assign]
    text = "Abre el navegador."
    contract = {
        "description": "Abre una aplicación por nombre.",
        "arguments_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    }

    assert not runtime._operation_is_fully_compatible(
        text,
        "app.open",
        contract,
    )
    assert not runtime._operation_is_fully_compatible(
        text,
        "app.open",
        copy.deepcopy(contract),
    )
    changed_contract = copy.deepcopy(contract)
    changed_contract["description"] += " visible"
    assert not runtime._operation_is_fully_compatible(
        text,
        "app.open",
        changed_contract,
    )
    assert calls == 2


def test_language_detection_is_candidate_free_and_history_free() -> None:
    runtime = object.__new__(LlmRuntime)
    captured: dict[str, object] = {}

    def response(payload: dict, label: str) -> dict:
        captured["payload"] = payload
        captured["label"] = label
        return {"language": "es"}

    runtime._post_schema_object = response  # type: ignore[method-assign]

    assert runtime.detect_response_language("¿Por qué el cielo es azul?") == "es"
    assert captured["label"] == "la detección de idioma"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert len(payload["messages"]) == 12
    assert payload["messages"][-1] == {
        "role": "user",
        "content": "Mensaje actual:\n¿Por qué el cielo es azul?",
    }
    serialized = repr(payload)
    assert "Operaciones candidatas" not in serialized
    assert "context_anchor" not in serialized
    assert "calibrated_conversation_probability" not in serialized
    assert payload["max_tokens"] == 12
    assert "response_format" not in payload
    assert (
        payload["grammar"]
        == 'root ::= "{" "\\"language\\"" ":" "\\"" language "\\"" "}"\n'
        'language ::= "es" | "en" | "mixed"'
    )


def test_language_detection_is_reused_only_within_one_request() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._response_language_cache = {}
    calls = 0

    def response(_payload: dict, _label: str) -> dict:
        nonlocal calls
        calls += 1
        return {"language": "en"}

    runtime._post_schema_object = response  # type: ignore[method-assign]

    assert runtime.detect_response_language("Why is the sky blue?") == "en"
    assert runtime.detect_response_language("Why is the sky blue?") == "en"
    runtime._response_language_cache = {}
    assert runtime.detect_response_language("Why is the sky blue?") == "en"
    assert calls == 2


def test_owned_runtime_reuses_valid_language_for_exact_text_across_requests() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._response_language_cache = {}
    runtime._validated_classifier_reuse_enabled = True
    runtime._validated_classifier_reuse_lock = threading.Lock()
    runtime._response_language_reuse_cache = OrderedDict()
    calls = 0

    def response(_payload: dict, _label: str) -> dict:
        nonlocal calls
        calls += 1
        return {"language": "en"}

    runtime._post_schema_object = response  # type: ignore[method-assign]
    text = "Why is the sky blue?"

    assert runtime.detect_response_language(text) == "en"
    runtime._response_language_cache = {}
    assert runtime.detect_response_language(text) == "en"
    assert calls == 1


def test_successful_speculative_language_is_available_to_a_retry() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._response_language_cache = {}
    calls = 0

    def response(_payload: dict, _label: str) -> dict:
        nonlocal calls
        calls += 1
        return {"language": "en"}

    runtime._post_schema_object = response  # type: ignore[method-assign]
    cancellation = SimpleNamespace(raise_if_cancelled=lambda: None)
    text = "Why is the sky blue?"

    assert (
        runtime.detect_response_language(
            text,
            cancellation=cancellation,
            cache_result=False,
        )
        == "en"
    )
    assert runtime._response_language_cache == {text: "en"}
    assert runtime.detect_response_language(text) == "en"
    assert calls == 1


def test_turn_failure_clarification_is_candidate_free_and_schema_closed() -> None:
    runtime = object.__new__(LlmRuntime)
    captured: dict[str, object] = {}

    def response(payload: dict, timeout: float | None = None) -> dict:
        captured["payload"] = payload
        captured["timeout"] = timeout
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"question":"¿Puedes aclarar qué quieres conseguir?"}'
                        )
                    }
                }
            ]
        }

    runtime._post = response  # type: ignore[method-assign]

    question = runtime.clarify_after_turn_failure(
        "Haz eso",
        history=[
            {"role": "assistant", "content": "Puedo ayudarte."},
            {"role": "user", "content": "Haz eso"},
            {"role": "tool", "content": "app.open"},
        ],
    )

    assert question == "¿Puedes aclarar qué quieres conseguir?"
    assert captured["timeout"] == 2.5
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert [message["role"] for message in payload["messages"]] == [
        "system",
        "assistant",
        "user",
    ]
    schema = payload["response_format"]["json_schema"]["schema"]
    assert set(schema["properties"]) == {"question"}
    assert schema["required"] == ["question"]
    assert schema["additionalProperties"] is False
    serialized = repr(payload)
    assert "app.open" not in serialized
    assert "arguments_schema" not in serialized
    assert "calibrated_conversation_probability" not in serialized
    assert payload["max_tokens"] == 96
    assert payload["temperature"] == 0.0
    assert payload["seed"] == 0
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}


def test_explicit_clarification_is_model_authored_and_contract_closed() -> None:
    runtime = object.__new__(LlmRuntime)
    captured: dict[str, object] = {}

    def response(payload: dict, label: str) -> dict:
        captured["payload"] = payload
        captured["label"] = label
        return {
            "requested_fields": ["recipient", "message_text"],
            "question": "¿A quién quieres escribir y qué quieres decirle?",
        }

    runtime._post_schema_object = response  # type: ignore[method-assign]

    question = runtime.formulate_explicit_clarification_question(
        "Mándales ese mensaje",
        ("message.send",),
        ("recipient", "message_text"),
    )

    assert question == "¿A quién quieres escribir y qué quieres decirle?"
    assert captured["label"] == "la aclaración explícita"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    schema = payload["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["requested_fields"]["items"]["enum"] == [
        "recipient",
        "message_text",
    ]
    assert schema["properties"]["requested_fields"]["uniqueItems"] is True
    assert schema["properties"]["question"]["pattern"] == r"^[^?\r\n]{1,511}\?$"
    assert schema["additionalProperties"] is False
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert payload["temperature"] == 0.0
    assert payload["seed"] == 0
    assert payload["max_tokens"] == 64
    assert "¿A quién" not in repr(payload)


def test_explicit_clarification_prompt_forbids_reasking_known_information() -> None:
    runtime = object.__new__(LlmRuntime)
    captured: dict[str, object] = {}

    def response(payload: dict, _label: str) -> dict:
        captured["payload"] = payload
        return {
            "requested_fields": ["amount"],
            "question": "¿Cuánto quieres subir el volumen?",
        }

    runtime._post_schema_object = response  # type: ignore[method-assign]

    assert runtime.formulate_explicit_clarification_question(
        "subí el volumen",
        ("audio.volume.adjust",),
        ("amount",),
    ) == "¿Cuánto quieres subir el volumen?"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    prompt = payload["messages"][0]["content"]
    assert "información ya explícita" in prompt
    assert "fuera de missing_information" in prompt


@pytest.mark.parametrize(
    "question",
    [
        "¿Subí el volumen en 10%?",
        "¿Cuánto y en qué dirección quieres subir el volumen?",
        "¿cuánto bajá el brillo?",
    ],
)
def test_amount_clarification_rejects_invention_and_known_direction_reask(
    question: str,
) -> None:
    with pytest.raises(ValueError, match="aclaración"):
        llm_module.validate_missing_argument_clarification(
            {"requested_fields": ["amount"], "question": question},
            ("amount",),
            objective="subí el volumen",
        )


@pytest.mark.parametrize(
    "question",
    [
        "¿Cuál es una canción?",
        "¿Qué necesitas?",
        "¿Quieres una canción?",
    ],
)
def test_media_query_clarification_rejects_definition_or_binary_question(
    question: str,
) -> None:
    with pytest.raises(ValueError, match="multimedia"):
        llm_module.validate_missing_argument_clarification(
            {"requested_fields": ["query"], "question": question},
            ("query",),
            objective="poné una canción",
            operations=("media.play.query",),
        )


def test_media_query_clarification_accepts_the_missing_selection() -> None:
    assert llm_module.validate_missing_argument_clarification(
        {
            "requested_fields": ["query"],
            "question": "¿Qué canción quieres escuchar?",
        },
        ("query",),
        objective="poné una canción",
        operations=("media.play.query",),
    ) == "¿Qué canción quieres escuchar?"


def test_explicit_clarification_retries_one_semantically_invalid_question() -> None:
    runtime = object.__new__(LlmRuntime)
    replies = iter(
        [
            {
                "requested_fields": ["amount"],
                "question": "¿Cuánto y en qué dirección quieres subir el volumen?",
            },
            {
                "requested_fields": ["amount"],
                "question": "¿Cuánto quieres subir el volumen?",
            },
        ]
    )
    payloads: list[dict] = []

    def response(payload: dict, _label: str) -> dict:
        payloads.append(payload)
        return next(replies)

    runtime._post_schema_object = response  # type: ignore[method-assign]

    assert runtime.formulate_explicit_clarification_question(
        "subí el volumen",
        ("audio.volume.adjust",),
        ("amount",),
    ) == "¿Cuánto quieres subir el volumen?"
    assert len(payloads) == 2
    assert "respuesta anterior" in payloads[1]["messages"][-2]["content"]


def test_explicit_clarification_rejects_incomplete_model_field_echo() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._post_schema_object = (  # type: ignore[method-assign]
        lambda _payload, _label: {
            "requested_fields": ["recipient"],
            "question": "¿A quién?",
        }
    )

    with pytest.raises(ValueError):
        runtime.formulate_explicit_clarification_question(
            "Mándales ese mensaje",
            ("message.send",),
            ("recipient", "message_text"),
        )


@pytest.mark.parametrize(
    "question",
    [
        "",
        "No es una pregunta.",
        "¿Una? ¿Dos?",
        "x" * 512 + "?",
        " ¿Con espacio?",
        "¿Con salto?\n",
        "¿Con control\u0001?",
    ],
)
def test_turn_failure_clarification_rejects_non_question_shapes(
    question: str,
) -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._post = (  # type: ignore[method-assign]
        lambda _payload, timeout=None: {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"question": question},
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }
    )

    with pytest.raises(ValueError):
        runtime.clarify_after_turn_failure("Aclara esto")


def test_conversation_guard_abstains_and_followup_chat_anchors_context() -> None:
    runtime = object.__new__(LlmRuntime)
    decision_calls = 0

    def constrained(_payload: dict, label: str) -> dict:
        nonlocal decision_calls
        decision_calls += 1
        if label == "el veto semántico de efectos":
            return guard_response(
                has_effect=False,
                effect_count="zero",
            )
        return {
            "mode": "conversation",
            "operation": "",
            "question": "",
            "conversation_kind": "followup",
            "effect_count": "zero",
            "effect_operations": [],
            "response_language": "es",
        }

    runtime._post_schema_object = constrained  # type: ignore[method-assign]
    result = runtime.decide_turn("¿Por qué?", [])
    assert result["mode"] == "conversation"
    assert result["effect_verification"] == "not_applicable"
    assert decision_calls == 2

    captured: dict[str, object] = {}

    def contextual(payload: dict, label: str) -> dict:
        captured["payload"] = payload
        captured["label"] = label
        return {
            "resolved_meaning": ("La acción no terminó porque se agotó el tiempo."),
            "direct_answer": "Porque se agotó el tiempo disponible.",
        }

    runtime._post_schema_object = contextual  # type: ignore[method-assign]
    runtime.chat(
        "¿Por qué?",
        history=[
            {
                "role": "assistant",
                "content": "No pude completar la acción porque se agotó el tiempo.",
            }
        ],
        temperature=0.0,
        conversation_kind="followup",
        response_language="es",
    )
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert captured["label"] == "la resolución semántica de continuidad"
    assert payload["messages"][-1] == {
        "role": "user",
        "content": "¿Por qué?",
    }
    assert {
        "role": "assistant",
        "content": "No pude completar la acción porque se agotó el tiempo.",
    } in payload["messages"]
    serialized = repr(payload["messages"])
    assert "context_anchor" not in serialized
    assert "Datos de continuidad" not in serialized
    assert serialized.count("¿Por qué?") == 1


def test_capability_question_with_history_does_not_enter_context_resolver() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._post_schema_object = (  # type: ignore[method-assign]
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("a capability question is not a contextual reference")
        )
    )
    runtime._post = lambda _payload: {  # type: ignore[method-assign]
        "choices": [
            {
                "message": {
                    "content": (
                        "Puedo conversar, explicar y realizar tareas autorizadas "
                        "en tu PC."
                    )
                }
            }
        ]
    }

    reply, calls = runtime.chat(
        "¿Qué puedes hacer?",
        history=[{"role": "assistant", "content": "No entendí la pregunta anterior."}],
        temperature=0.0,
        conversation_kind="followup",
        response_language="es",
    )

    assert reply.startswith("Puedo conversar")
    assert calls == []


def test_followup_literal_recall_grounds_fact_without_exposing_it_to_model() -> None:
    runtime = object.__new__(LlmRuntime)
    nonce = "Nimbo7391"
    current = "¿Qué palabra inventada mencioné antes?"
    captured: dict[str, object] = {}

    def compose(payload: dict) -> dict:
        captured["payload"] = payload
        return {
            "choices": [
                {
                    "message": {
                        "content": "La palabra inventada era [[R1]].",
                    }
                }
            ]
        }

    runtime._post = compose  # type: ignore[method-assign]
    answer, calls = runtime.chat(
        current,
        history=[
            {
                "role": "user",
                "content": (
                    f"Explica por qué la palabra inventada «{nonce}» suena amistosa."
                ),
            },
            {
                "role": "assistant",
                "content": "Su combinación de sonidos resulta suave y cercana.",
            },
            {"role": "user", "content": current},
        ],
        temperature=0.0,
        conversation_kind="followup",
        response_language="es",
    )

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert answer == f"La palabra inventada era {nonce}."
    assert calls == []
    assert payload["messages"][-1] == {"role": "user", "content": current}
    serialized = repr(payload["messages"])
    assert nonce not in serialized
    assert "[[R1]]" in serialized


def test_context_resolver_retries_a_simpler_schema_before_turn_recovery() -> None:
    runtime = object.__new__(LlmRuntime)
    calls: list[tuple[dict, str]] = []

    def contextual(payload: dict, label: str) -> dict:
        calls.append((payload, label))
        if len(calls) == 1:
            raise ValueError("invalid two-field response")
        return {"answer": "Falló porque se agotó el tiempo disponible."}

    runtime._post_schema_object = contextual  # type: ignore[method-assign]
    answer = runtime._resolve_contextual_answer(
        history=[
            {
                "role": "assistant",
                "content": "No pude completar esa acción porque se agotó el tiempo.",
            }
        ],
        current="¿Por qué?",
    )

    assert answer == "Falló porque se agotó el tiempo disponible."
    assert [label for _, label in calls] == [
        "la resolución semántica de continuidad",
        "la respuesta contextual directa",
    ]
    retry_schema = calls[1][0]["response_format"]["json_schema"]["schema"]
    assert retry_schema["required"] == ["answer"]


def test_context_resolver_rejects_a_question_paraphrase_as_direct_answer() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._post_schema_object = (  # type: ignore[method-assign]
        lambda _payload, _label: {
            "resolved_meaning": "La palabra inventada era Nimbo7391.",
            "direct_answer": "¿Cuál era la palabra inventada?",
        }
    )

    answer = runtime._resolve_contextual_answer(
        history=[
            {
                "role": "user",
                "content": "Explica por qué Nimbo7391 suena amistosa.",
            }
        ],
        current="¿Qué palabra inventada mencioné antes?",
    )

    assert answer == "La palabra inventada era Nimbo7391."


def test_followup_offer_is_native_history_not_serialized_user_data() -> None:
    runtime = object.__new__(LlmRuntime)
    captured: dict[str, object] = {}

    def contextual(payload: dict, label: str) -> dict:
        captured["payload"] = payload
        return {
            "resolved_meaning": (
                "La pregunta anterior pedía saber qué necesita la persona."
            ),
            "direct_answer": (
                "Te estaba preguntando qué necesitas para saber cómo ayudarte."
            ),
        }

    runtime._post_schema_object = contextual  # type: ignore[method-assign]
    answer, _ = runtime.chat(
        "¿Qué?",
        history=[
            {
                "role": "assistant",
                "content": "Dime qué necesitas y te ayudo.",
            },
            {"role": "user", "content": "¿Qué?"},
        ],
        temperature=0.0,
        conversation_kind="followup",
        response_language="es",
    )

    assert "qué necesitas" in answer
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["messages"][-2:] == [
        {"role": "assistant", "content": "Dime qué necesitas y te ayudo."},
        {"role": "user", "content": "¿Qué?"},
    ]
    serialized = repr(payload["messages"])
    assert "context_anchor" not in serialized
    assert "mensaje_actual" not in serialized


def test_context_resolution_falls_back_from_an_exact_history_echo() -> None:
    runtime = object.__new__(LlmRuntime)
    payloads: list[dict] = []

    def contextual(payload: dict, label: str) -> dict:
        payloads.append(payload)
        assert label == "la resolución semántica de continuidad"
        return {
            "resolved_meaning": ("La acción falló al agotarse el tiempo disponible."),
            "direct_answer": ("No pude completar la acción porque se agotó el tiempo."),
        }

    runtime._post_schema_object = contextual  # type: ignore[method-assign]
    answer, _ = runtime.chat(
        "¿Por qué?",
        history=[
            {
                "role": "assistant",
                "content": "No pude completar la acción porque se agotó el tiempo.",
            }
        ],
        temperature=0.0,
        conversation_kind="followup",
        response_language="es",
    )

    assert answer == "La acción falló al agotarse el tiempo disponible."
    assert len(payloads) == 1


def test_context_resolution_can_answer_a_new_topic_without_forcing_anchor() -> None:
    runtime = object.__new__(LlmRuntime)
    payloads: list[dict] = []

    def normal_chat(payload: dict) -> dict:
        payloads.append(payload)
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            "El cielo se ve azul por la dispersión de la luz "
                            "solar en la atmósfera."
                        )
                    }
                }
            ]
        }

    runtime._post = normal_chat  # type: ignore[method-assign]
    answer, _ = runtime.chat(
        "¿Por qué el cielo se ve azul?",
        history=[
            {
                "role": "assistant",
                "content": "Dime qué necesitas y te ayudo.",
            }
        ],
        temperature=0.0,
        conversation_kind="knowledge",
        response_language="es",
    )

    assert answer.startswith("El cielo se ve azul")
    assert len(payloads) == 1
    assert payloads[0]["messages"][-2:] == [
        {"role": "assistant", "content": "Dime qué necesitas y te ayudo."},
        {"role": "user", "content": "¿Por qué el cielo se ve azul?"},
    ]


def test_social_greeting_after_welcome_does_not_enter_reference_resolution() -> None:
    runtime = object.__new__(LlmRuntime)
    payloads: list[dict] = []

    def normal_chat(payload: dict) -> dict:
        payloads.append(payload)
        return {"choices": [{"message": {"content": "¡Hola!"}}]}

    runtime._post = normal_chat  # type: ignore[method-assign]
    answer, _ = runtime.chat(
        "Hola",
        history=[
            {
                "role": "assistant",
                "content": "Hola. Estoy lista para ayudarte con este equipo.",
            }
        ],
        temperature=0.0,
        conversation_kind="social",
        response_language="es",
    )

    assert answer == "¡Hola!"
    assert payloads[0]["messages"][-1] == {"role": "user", "content": "Hola"}
    assert "Estoy lista" not in repr(payloads[0]["messages"])


@pytest.mark.parametrize(
    "answer",
    [
        "Sí, estoy aquí. ¿En qué puedo ayudarte?",
        "Hola. ¿En qué puedo ayudarte?",
        (
            "Puedo ayudarte con información, explicaciones y charla. "
            "¿En qué puedo ayudarte?"
        ),
        "Hello. How can I help you?",
    ],
)
def test_unshaped_conversation_rejects_generic_assistance_closing(
    answer: str,
) -> None:
    assert _shaped_conversation_answer_violates_contract(
        answer,
        "Hola.",
        None,
        conversation_kind="social",
    )


def test_social_chat_removes_only_generic_question_closing() -> None:
    runtime = object.__new__(LlmRuntime)
    payloads: list[dict[str, object]] = []

    def post(payload: dict[str, object]) -> dict[str, object]:
        payloads.append(payload)
        return {
            "choices": [
                {"message": {"content": "Hola. ¿En qué puedo ayudarte?"}}
            ]
        }

    runtime._post = post  # type: ignore[method-assign]

    answer, calls = runtime.chat(
        "Hola.",
        history=[
            {
                "role": "assistant",
                "content": "Sí, estoy aquí. ¿En qué puedo ayudarte?",
            }
        ],
        temperature=0.0,
        conversation_kind="social",
        response_language="es",
    )

    assert answer == "Hola."
    assert calls == []
    assert len(payloads) == 1


def test_knowledge_chat_rewrites_previous_assistant_echo() -> None:
    runtime = object.__new__(LlmRuntime)
    payloads: list[dict[str, object]] = []

    def post(payload: dict[str, object]) -> dict[str, object]:
        payloads.append(payload)
        content = (
            "Puedo ayudarte con información."
            if len(payloads) == 1
            else json.dumps(
                {"answer": "Puedo explicar conceptos y resolver dudas."},
                ensure_ascii=False,
            )
        )
        return {"choices": [{"message": {"content": content}}]}

    runtime._post = post  # type: ignore[method-assign]

    answer, calls = runtime.chat(
        "¿Qué puedes hacer?",
        history=[
            {"role": "assistant", "content": "Puedo ayudarte con información."}
        ],
        temperature=0.0,
        conversation_kind="knowledge",
        response_language="es",
    )

    assert answer == "Puedo explicar conceptos y resolver dudas."
    assert calls == []
    assert len(payloads) == 2
    assert "Puedo ayudarte con información." not in repr(payloads[1]["messages"])


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("Sí, aquí. ¿Qué necesitas?", "Sí, aquí."),
        ("Hola. ¿Qué te pasa?", "Hola."),
        (
            "Puedo ayudarte con información y explicaciones. "
            "¿En qué puedo asistirte?",
            "Puedo ayudarte con información y explicaciones.",
        ),
        ("Hello. How can I help you?", "Hello."),
    ],
)
def test_unrequested_closing_preserves_model_answer(
    answer: str,
    expected: str,
) -> None:
    assert (
        _without_unrequested_conversation_closing(
            answer,
            conversation_kind="social",
            shape=None,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("Hola, ¿En qué puedo ayudarte?", "Hola."),
        ("Claro: ¿Qué necesitas?", "Claro."),
    ],
)
def test_unrequested_closing_completes_dangling_separator(
    answer: str,
    expected: str,
) -> None:
    assert (
        _without_unrequested_conversation_closing(
            answer,
            conversation_kind="social",
            shape=None,
        )
        == expected
    )


@pytest.mark.parametrize("answer", ["Hola,", "Claro:", "Yes;"])
def test_unshaped_conversation_rejects_dangling_separator(answer: str) -> None:
    assert _shaped_conversation_answer_violates_contract(
        answer,
        "Hola.",
        None,
        conversation_kind="social",
    )


def test_unrequested_question_rule_rejects_a_question_only_answer() -> None:
    answer = "¿En qué puedo ayudarte?"

    assert _without_unrequested_conversation_closing(
        answer,
        conversation_kind="social",
        shape=None,
    ) == answer
    assert _shaped_conversation_answer_violates_contract(
        answer,
        "Hola.",
        None,
        conversation_kind="social",
    )


def test_generic_invitation_closing_preserves_capability_answer() -> None:
    answer = (
        "Puedo ayudarte con preguntas, explicaciones y charlas. "
        "Si necesitas algo específico, avísame."
    )

    assert _without_unrequested_conversation_closing(
        answer,
        conversation_kind="knowledge",
        shape=None,
    ) == "Puedo ayudarte con preguntas, explicaciones y charlas."
    assert _shaped_conversation_answer_violates_contract(
        "Si necesitas algo específico, avísame.",
        "¿Qué puedes hacer?",
        None,
        conversation_kind="knowledge",
    )


def test_capability_answer_without_generic_closing_remains_valid() -> None:
    assert not _shaped_conversation_answer_violates_contract(
        "Puedo ayudarte con información, explicaciones y charla.",
        "¿Qué puedes hacer?",
        None,
        conversation_kind="knowledge",
    )


def test_native_tool_selection_accepts_only_declared_parameterless_calls() -> None:
    runtime = object.__new__(LlmRuntime)
    payloads: list[dict[str, object]] = []

    def post(payload: dict[str, object]) -> dict[str, object]:
        payloads.append(payload)
        return {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "baxy_system__time",
                                    "arguments": "{}",
                                }
                            }
                        ],
                    }
                }
            ]
        }

    runtime._post = post  # type: ignore[method-assign]
    result = runtime._post_native_tool_selection(
        "Dime la hora",
        ["system.time"],
        {"system.time": {"description": "Read the current local time."}},
        [],
    )

    assert result["mode"] == "action"
    assert result["effect_operations"] == ["system.time"]
    assert payloads[0]["tool_choice"] == "required"
    assert payloads[0]["parallel_tool_calls"] is True


def test_native_tool_selection_accepts_no_call_as_zero_authority_conversation() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._post = (  # type: ignore[method-assign]
        lambda _payload: {
            "choices": [
                {
                    "message": {
                        "content": "El cielo es azul por dispersion.",
                    }
                }
            ]
        }
    )

    result = runtime._post_native_tool_selection(
        "Why is the sky blue?",
        ["web.search"],
        {"web.search": {"description": "Search the web."}},
        [],
    )

    assert result == {
        "mode": "conversation",
        "question": "",
        "conversation_kind": "knowledge",
        "effect_operations": [],
        "response_language": "es",
    }


def test_native_tool_selection_clarifies_only_measured_sibling_boundaries() -> None:
    assert "never play or search media" in llm_module._native_selection_description(
        "app.open",
        "Open an installed application.",
    )
    assert "absolute output level" in llm_module._native_selection_description(
        "audio.volume",
        "Set output volume.",
    )
    assert "relative amount" in llm_module._native_selection_description(
        "audio.volume.adjust",
        "Adjust output volume.",
    )
    assert "never append" in llm_module._native_selection_description(
        "filesystem.write.text",
        "Write text.",
    )
    assert "do not describe scenes" in llm_module._native_selection_description(
        "ocr.read",
        "Read text.",
    )
    assert "never merely open Spotify" in llm_module._native_selection_description(
        "media.play.query",
        "Search and play media.",
    )
    assert "interactive game" in llm_module._native_selection_description(
        "media.play.exact",
        "Play exact media.",
    )
    assert "never launch" in llm_module._native_selection_description(
        "media.control",
        "Control playback.",
    )
    assert (
        llm_module._native_selection_description(
            "system.time",
            "Read the current time.",
        )
        == "Read the current time."
    )


def test_native_effects_drop_planner_owned_technical_predecessors() -> None:
    raw = {
        "mode": "plan",
        "effect_operations": [
            "app.open",
            "message.recipient.resolve",
            "message.send",
        ],
    }

    assert llm_module._without_redundant_technical_predecessors(raw) == {
        "mode": "plan",
        "effect_operations": ["app.open", "message.send"],
    }
    assert raw["effect_operations"] == [
        "app.open",
        "message.recipient.resolve",
        "message.send",
    ]


def test_native_tool_selection_cannot_bypass_candidate_free_conversation_veto() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._native_tool_policy_enabled = True
    runtime._parallel_turn_verification = False
    runtime._semantic_effect_cache = {}

    def native_selection(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "mode": "action",
            "question": "",
            "conversation_kind": "",
            "effect_operations": ["web.search"],
            "response_language": "es",
        }

    runtime._post_native_tool_selection = native_selection  # type: ignore[method-assign]
    runtime._verify_semantic_effect_shape = (  # type: ignore[method-assign]
        lambda _text: ("no_effect", "zero")
    )

    result = runtime.decide_turn(
        "Explícame brevemente la fotosíntesis.",
        [turn_candidate("web.search", "Search the current web.", required=("query",))],
    )

    assert result["mode"] == "conversation"
    assert result["conversation_kind"] == "knowledge"
    assert result["operation"] is None
    assert result["effect_operations"] == []
    assert result["intent_operations"] == []


def test_native_verified_recovery_reports_the_recovered_intent_identity() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._native_tool_policy_enabled = True
    runtime._parallel_turn_verification = False
    runtime._semantic_effect_cache = {}
    runtime._post_native_tool_selection = (  # type: ignore[method-assign]
        lambda *_args, **_kwargs: {
            "mode": "conversation",
            "question": "",
            "conversation_kind": "knowledge",
            "effect_count": "zero",
            "effect_operations": [],
            "response_language": "es",
        }
    )
    runtime._verify_semantic_effect_shape = (  # type: ignore[method-assign]
        lambda _text: ("complete", "one")
    )
    runtime._select_single_effect_operation = (  # type: ignore[method-assign]
        lambda *_args, **_kwargs: "web.search"
    )
    runtime._operation_is_fully_compatible = (  # type: ignore[method-assign]
        lambda *_args, **_kwargs: True
    )

    result = runtime.decide_turn(
        "Busca el dato vigente en la web.",
        [turn_candidate("web.search", "Search the web.", required=("query",))],
    )

    assert result["mode"] == "action"
    assert result["effect_operations"] == ["web.search"]
    assert result["intent_operations"] == ["web.search"]
    assert result["effect_verification"] == "recovered"


def test_native_single_effect_agreement_does_not_repeat_model_count() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._native_tool_policy_enabled = True
    runtime._parallel_turn_verification = False
    runtime._semantic_effect_cache = {}
    runtime._post_native_tool_selection = (  # type: ignore[method-assign]
        lambda *_args, **_kwargs: {
            "mode": "action",
            "question": "",
            "conversation_kind": "",
            "effect_count": "one",
            "effect_operations": ["system.time"],
            "response_language": "es",
        }
    )
    runtime._verify_semantic_effect_shape = (  # type: ignore[method-assign]
        lambda _text: ("complete", "one")
    )
    runtime._verify_effect_count = (  # type: ignore[method-assign]
        lambda _text: (_ for _ in ()).throw(
            AssertionError("the redundant third count must not run")
        )
    )

    result = runtime.decide_turn(
        "¿Qué hora es?",
        [turn_candidate("system.time", "Read the current local time.")],
    )

    assert result["mode"] == "action"
    assert result["effect_operations"] == ["system.time"]
    assert result["effect_verification"] == "agreed"


def test_native_conversation_veto_uses_history_for_contextual_followup() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._native_tool_policy_enabled = True
    runtime._parallel_turn_verification = False
    runtime._semantic_effect_cache = {}
    runtime._post_native_tool_selection = (  # type: ignore[method-assign]
        lambda *_args, **_kwargs: {
            "mode": "action",
            "question": "",
            "conversation_kind": "",
            "effect_operations": ["web.search"],
            "response_language": "es",
        }
    )
    runtime._verify_semantic_effect_shape = (  # type: ignore[method-assign]
        lambda _text: ("no_effect", "zero")
    )

    result = runtime.decide_turn(
        "¿Qué palabra inventada mencioné en mi pregunta anterior?",
        [turn_candidate("web.search", "Search the current web.", required=("query",))],
        history=[
            {
                "role": "user",
                "content": "Explica por qué la palabra inventada «Nimbo7391» suena amistosa.",
            },
            {
                "role": "assistant",
                "content": "Su combinación de sonidos resulta suave y cercana.",
            },
        ],
    )

    assert result["mode"] == "conversation"
    assert result["conversation_kind"] == "followup"
    assert result["effect_operations"] == []


def test_vetoed_native_selection_preserves_intent_without_effect_authority() -> None:
    tool = {
        "type": "function",
        "function": {
            "name": "system_power",
            "canonical_name": "system.power",
            "description": "Control computer power.",
            "risk": "high_impact",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    }

    class Evidence:
        @staticmethod
        def candidate_families(*_args: object) -> tuple[str, ...]:
            return ()

        @staticmethod
        def retrieve(*_args: object) -> list[object]:
            return []

    class Runtime:
        @staticmethod
        def decide_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
            return {
                "mode": "conversation",
                "operation": None,
                "question": "",
                "conversation_kind": "unsupported",
                "effect_count": "zero",
                "effect_operations": [],
                "effect_verification": "not_applicable",
                "response_language": "es",
                "intent_operations": ["system.power"],
            }

        @staticmethod
        def clarify_after_turn_failure(*_args: object, **_kwargs: object) -> str:
            return "¿Qué cambio de energía quieres hacer en este equipo?"

        @staticmethod
        def chat(*_args: object, **_kwargs: object) -> tuple[str, list[object]]:
            raise AssertionError("a vetoed action must be presented as clarification")

        @staticmethod
        def retire_deferred_response_language(_text: str) -> None:
            return None

    result = _prepare_turn_result(
        {"id": "native-veto", "text": "haz algo con la energía"},
        llm=Runtime(),
        planner_catalog=PlannerCatalog([tool]),
        turn_evidence=Evidence(),
        encoder=lambda _texts: (),
        tool_by_name={"system.power": tool},
    )

    assert result["kind"] == "clarify"
    assert result["intentOperations"] == ["system.power"]
    assert result["effectOperations"] == []
    assert result["operation"] is None


@pytest.mark.parametrize(
    "operation",
    ["notification.schedule", "message.recipient.resolve"],
)
def test_domain_rejected_native_intent_becomes_unsupported_not_clarification(
    operation: str,
) -> None:
    tool = {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"),
            "canonical_name": operation,
            "description": "Exercise one domain-grounded operation.",
            "risk": "low_reversible",
            "parameters": {
                "type": "object",
                "properties": {
                    "dueUtc": {"type": "string"},
                    "kind": {"type": "string"},
                    "title": {"type": "string"},
                },
                "required": ["dueUtc", "kind", "title"],
                "additionalProperties": False,
            },
        },
    }

    class Evidence:
        @staticmethod
        def candidate_families(*_args: object) -> tuple[str, ...]:
            return ()

        @staticmethod
        def retrieve(*_args: object) -> list[object]:
            return []

    class Runtime:
        @staticmethod
        def decide_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
            return {
                "mode": "action",
                "operation": operation,
                "question": "",
                "conversation_kind": "",
                "effect_count": "one",
                "effect_operations": [operation],
                "effect_verification": "grounding_required",
                "response_language": "es",
                "intent_operations": [operation],
            }

        @staticmethod
        def detect_response_language(_text: str) -> str:
            return "es"

        @staticmethod
        def chat(*_args: object, **kwargs: object) -> tuple[str, list[object]]:
            assert kwargs["authenticated_operations"] == ()
            return "No puedo pedir un taxi desde este equipo.", []

        @staticmethod
        def clarify_after_turn_failure(*_args: object, **_kwargs: object) -> str:
            raise AssertionError("an unrelated capability must not ask for fields")

        @staticmethod
        def retire_deferred_response_language(_text: str) -> None:
            return None

    result = _prepare_turn_result(
        {
            "id": "taxi-domain-veto",
            "text": "Pide un taxi para que venga a mi casa",
        },
        llm=Runtime(),
        planner_catalog=PlannerCatalog([tool]),
        turn_evidence=Evidence(),
        encoder=lambda _texts: (),
        tool_by_name={operation: tool},
    )

    assert result["kind"] == "conversation"
    assert result["intentOperations"] == []
    assert result["effectOperations"] == []
    assert result["reply"] == "No puedo pedir un taxi desde este equipo."


def test_wake_alarm_arguments_are_grounded_without_power_authority() -> None:
    arguments = _explicit_arguments_from_evidence(
        "notification.schedule",
        "get me up at eight am",
    )

    assert arguments is not None
    assert arguments["kind"] == "alarm"
    assert arguments["dueUtc"] == "at eight am"


@pytest.mark.parametrize(
    ("operation", "text", "expected"),
    [
        (
            "media.play.query",
            "comfort my ears with arijit singh",
            {"provider": "spotify", "query": "arijit singh"},
        ),
        (
            "note.create",
            "Create a memo to buy chocolate.",
            {"title": "buy chocolate", "content": "buy chocolate"},
        ),
        (
            "note.search",
            "¿Puedes tomar mis notas familiares atrasadas del pasado?",
            {"query": "familiares atrasadas"},
        ),
    ],
)
def test_focal_effect_arguments_preserve_literal_user_content(
    operation: str,
    text: str,
    expected: dict[str, object],
) -> None:
    assert _explicit_arguments_from_evidence(operation, text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "rápido",
        "I want to play Mario on the switch I mean the Wii.",
        "Muestra las las apps instaladas.",
        "Enseñarme las apps.",
    ],
)
def test_requests_without_executable_local_authority_close_as_conversation(
    text: str,
) -> None:
    decision = _explicit_stable_no_effect_turn_decision(text)

    assert decision is not None
    assert decision["mode"] == "conversation"
    assert decision["effect_operations"] == []


def test_public_person_status_confirmation_is_stable_knowledge() -> None:
    decision = _explicit_stable_no_effect_turn_decision(
        "podrías confirmar si mario está casado"
    )

    assert decision is not None
    assert decision["mode"] == "conversation"
    assert decision["conversation_kind"] == "knowledge"


@pytest.mark.parametrize(
    "text",
    [
        "I need to know more about the parade this weekend",
        "Me puedes dar una receta casera de sopa de fideos con pollo",
        "Cual es la receta del pollo frito",
        "What all goes into a red velvet cake",
        "Necesito una receta con los ingredientes de mi lista de la compra",
    ],
)
def test_underspecified_information_requests_are_stable_knowledge(
    text: str,
) -> None:
    decision = _explicit_stable_no_effect_turn_decision(text)

    assert decision is not None
    assert decision["mode"] == "conversation"
    assert decision["conversation_kind"] == "knowledge"


@pytest.mark.parametrize(
    "text",
    [
        "Por favor mira lo que escribiste para esta pregunta",
        "Recordatorio de reunion",
        "Quiero jugar al Mario Kart en la play nivel 4, no mejor nivel 2",
        "Compra 2 barras de pan y paga con Paypal, no mejor con tarjeta de debito",
        "Alexa donde esta mi comida",
        "How is my order",
        "Can I get fish sticks with my credit card",
        "Quitar, quiero decir, poner el Fortnite",
        "Voy a echar una partida de parchis en solitario",
    ],
)
def test_ambiguous_or_external_requests_close_without_effect_authority(
    text: str,
) -> None:
    assert _closed_unsupported_request(text) is True
    decision = _explicit_stable_no_effect_turn_decision(text)

    assert decision is not None
    assert decision["mode"] == "conversation"
    assert decision["effect_operations"] == []


def test_nominal_reminder_with_due_keeps_exact_effect_authority() -> None:
    text = "recordatorio de tomar agua en 1 hora"

    assert _closed_unsupported_request(text) is False
    assert _explicit_stable_no_effect_turn_decision(text) is None
    intent = mind_main.resolve_explicit_effects(text, {"reminder.create"})

    assert intent is not None
    assert intent.operations == ("reminder.create",)
    assert intent.evidence == (text,)


def test_stored_note_search_arguments_preserve_the_literal_topic() -> None:
    assert _explicit_arguments_from_evidence(
        "note.search",
        "Sacar la nota receta de brioche que tengo guardada",
    ) == {"query": "receta de brioche"}


@pytest.mark.parametrize(
    "text",
    [
        "juegos abiertos",
        "Items to get are new razors, body wash, and toothpaste.",
        (
            "Necesito conseguir unos pantalones y que los pagues con mi tarjeta "
            "Visa, bueno mejor por Bizum."
        ),
        "Mostrar todas ah todas las aplicaciones descargadas hoy.",
        "Ver las aplicaciones instaladas, digo descargadas.",
    ],
)
def test_fresh_gate_requests_without_supported_authority_close_stably(
    text: str,
) -> None:
    assert _closed_unsupported_request(text) is True
    decision = _explicit_stable_no_effect_turn_decision(text)

    assert decision is not None
    assert decision["mode"] == "conversation"
    assert decision["effect_operations"] == []


@pytest.mark.parametrize(
    "text",
    [
        "Take me to the Instagram app.",
        "Ouverture de Booking.",
        "Start up It Takes 2, no play LittleBigPlanet.",
        "Get Fortnite started.",
        "Let's play Candy Crush.",
        "Let's start playing spades.",
    ],
)
def test_unavailable_app_and_game_requests_close_before_model_selection(
    text: str,
) -> None:
    decision = mind_main._catalog_unavailable_turn_decision(
        text,
        None,
        effect_intent_module.build_application_catalog_index(()),
        build_game_catalog_index(()),
    )

    assert decision is not None
    assert decision["mode"] == "conversation"


@pytest.mark.parametrize(
    ("operation", "text", "expected"),
    [
        (
            "browser.navigate",
            "go to the washington post website",
            {"url": "https://www.washingtonpost.com/"},
        ),
        ("audio.mute", "de ahora en adelante mudo", {"state": True}),
        (
            "note.create",
            "buy milk and eggs का memo create करो।",
            {"title": "buy milk and eggs", "content": "buy milk and eggs"},
        ),
    ],
)
def test_fresh_gate_effect_arguments_are_literal_and_grounded(
    operation: str,
    text: str,
    expected: dict[str, object],
) -> None:
    assert _explicit_arguments_from_evidence(operation, text) == expected


@pytest.mark.parametrize(
    ("text", "is_observation"),
    [
        # Commands. Acknowledging one invents a fact the person never stated.
        ("Compra un vuelo a Madrid para el viernes", False),
        ("Riega las plantas del balcon", False),
        ("Reserva una cita con el dentista el martes", False),
        ("Pide un taxi para las ocho", False),
        ("Book an uber to the airport", False),
        ("Order flowers for my mother", False),
        # Genuine observations, including noun-initial ones.
        ("Hoy hace mucho frio en la oficina", True),
        ("Estoy bastante cansado hoy", True),
        ("Me gusta mucho el cafe por la manana", True),
        ("Cierre de Word podia perder trabajo", True),
        ("The meeting was longer than expected", True),
        ("My laptop feels slow today", True),
    ],
)
def test_an_imperative_is_never_acknowledged_as_an_observation(
    text: str,
    is_observation: bool,
) -> None:
    """A command is not a statement.

    "Compra un vuelo a Madrid" once came back as "Mencionas que compraste un
    vuelo a Madrid", which asserts something the person never said. Falling
    through costs an abstention; acknowledging costs a fabrication.
    """
    folded = _strip_request_envelope(_fold(text))

    assert _reads_as_an_observation(folded) is is_observation


@pytest.mark.parametrize(
    ("text", "leaks"),
    [
        # The catalogue's own wording reached a visible clarification.
        ("¿Qué acción se debe realizar en la sesión SMTC seleccionada?", True),
        ("¿Qué operación audio.volume quieres?", True),
        ("El schema del payload es inválido.", True),
        ("Revisa el manifest y el sha256.", True),
        ("¿Quieres que inicie un AppID poseído?", True),
        ("¿Quieres que emita autoridad CAS?", True),
        # Ordinary prose must survive untouched, including sentence periods.
        ("¿Te refieres a la reunión del martes o la del jueves?", False),
        ("No puedo regar las plantas del balcón.", False),
        ("¿Qué acción quieres que haga con esa nota?", False),
        ("I cannot fold the towels in the bathroom.", False),
    ],
)
def test_visible_text_never_carries_machine_vocabulary(
    text: str,
    leaks: bool,
) -> None:
    """Internal detail may exist as diagnostics, never as the answer."""
    assert visible_text_leaks_internal_vocabulary(text) is leaks


@pytest.mark.parametrize(
    ("text", "is_observation"),
    [
        # Third-person narration about an event. The first-person list did not
        # cover these, so "El viaje del sabado fue muy tranquilo" was refused
        # as if it had been a request.
        ("El viaje del sabado fue muy tranquilo", True),
        ("La mudanza del mes pasado fue agotadora", True),
        ("La cena de anoche estuvo deliciosa", True),
        ("The delivery arrived earlier than expected", True),
        # A gerund or infinitive subject carries its predicate later.
        ("Pintar la reja nos llevo toda la tarde", True),
        ("Cleaning the garage took the whole morning", True),
        # Imperatives keep their verb in front and stay requests.
        ("Riega las plantas del balcon", False),
        ("Manda un package a mi hermana", False),
        ("Pinta la reja del patio de verde", False),
        ("Send a parcel to my cousin", False),
    ],
)
def test_third_person_narration_is_not_a_request(
    text: str,
    is_observation: bool,
) -> None:
    """Refusing what nobody asked for is its own kind of dishonesty."""
    assert _reads_as_an_observation(_strip_request_envelope(_fold(text))) is (
        is_observation
    )


@pytest.mark.parametrize(
    ("reply", "malformed"),
    [
        # Spanish needs an infinitive after the modal. Measured at 16 of 314
        # replies across the sealed campaigns before this guard existed.
        ("No puedo riega los helechos del pasillo.", True),
        ("No puedo cierra la ventana del coche.", True),
        ("No puedo cocina una tortilla para la cena.", True),
        ("No puedo a sacar al perro a pasear ahora.", True),
        ("No puedo de recoger a los ninos del colegio.", True),
        ("No puedo hacer pegar el tape en la box del garage.", True),
        ("No puedo hacer encender la chimenea del salon.", True),
        # Correct Spanish must survive, including the idiomatic auxiliary.
        ("No puedo regar los helechos del pasillo.", False),
        ("No puedo cerrar la ventana del coche.", False),
        ("No puedo hacer llegar un pastel de chocolate a Marta.", False),
        ("No puedo con eso.", False),
        ("I cannot water the ferns in the corridor.", False),
    ],
)
def test_broken_spanish_after_the_modal_is_retried_not_published(
    reply: str,
    malformed: bool,
) -> None:
    """BAXY talks to a person, so it may not speak broken Spanish."""
    assert _spanish_modal_is_malformed(reply) is malformed


# --- Goal 03B: a withdrawn effect is withheld for confirmation, not denied ---
#
# The identity says BAXY says no only to what he cannot do. Two stages used to
# break that from the inside: when ``information_question`` or
# ``domain_grounding`` removed a proposed effect, the turn was published as a
# ``conversation`` of kind ``unsupported``, and the presentation worded it as
# "No puedo apagar el bluetooth" about an operation sitting in the catalogue.
# On the goal 03 corpus that was 24 of the 27 rows those stages cost.
#
# The repair is not a new gate. It is that the verdict stopped being binary: an
# independent verifier is asked whether the operation *is* the effect the person
# named, and when it is, the authority is withheld until the person confirms the
# exact invocation instead of being deleted. Nothing is dispatched either way,
# so the invariant the gate exists for is untouched.


_NETWORK_STATUS_TOOL = {
    "type": "function",
    "function": {
        "name": "network_status",
        "canonical_name": "network.status",
        "description": "Read connectivity and active interfaces without changing them.",
        "risk": "read_only",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
}


class _NoEvidence:
    @staticmethod
    def candidate_families(_text: str, _encoder: object) -> tuple[str, ...]:
        return ()

    @staticmethod
    def retrieve(*_args: object, **_kwargs: object) -> list[object]:
        return []


class _WithheldEffectLlm:
    """A decider that proposes the right operation the curated gate refuses."""

    def __init__(
        self,
        *,
        identifies: bool,
        question: str = "¿Quieres que lo mire?",
    ) -> None:
        self._identifies = identifies
        self._question = question
        self.chats = 0
        self.confirmations = 0
        self.identity_calls: list[str] = []

    def decide_turn(self, *_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "mode": "action",
            "operation": "network.status",
            "question": "",
            "conversation_kind": "",
            "effect_count": "one",
            "effect_operations": ["network.status"],
            "effect_verification": "agreed",
            "response_language": "es",
        }

    def operation_is_the_requested_effect(
        self,
        _text: str,
        operation: str,
        _contract: dict[str, object],
    ) -> bool:
        self.identity_calls.append(operation)
        return self._identifies

    def confirm_operation_before_acting(
        self,
        _text: str,
        _effects: tuple[tuple[str, str], ...],
        **_kwargs: object,
    ) -> str:
        self.confirmations += 1
        return self._question

    @staticmethod
    def _verify_semantic_effect_shape(_text: str) -> tuple[str, str]:
        return "no_effect", "zero"

    @staticmethod
    def consume_deferred_response_language(_text: str) -> tuple[bool, str | None]:
        return True, "es"

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "es"

    def chat(self, *_args: object, **_kwargs: object) -> tuple[str, list[object]]:
        self.chats += 1
        return "No puedo verificar el estado de la red.", []


def _withheld_effect_turn(llm: _WithheldEffectLlm) -> dict[str, object]:
    return _prepare_turn_result(
        {"id": "turn-withheld", "text": "¿Cómo está la red neuronal?"},
        llm=llm,
        planner_catalog=PlannerCatalog([_NETWORK_STATUS_TOOL]),
        turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name={"network.status": _NETWORK_STATUS_TOOL},
    )


def test_a_withdrawn_effect_is_offered_for_confirmation_not_denied() -> None:
    llm = _WithheldEffectLlm(identifies=True)
    result = _withheld_effect_turn(llm)

    # The turn asks instead of claiming an inability, and the question is bound
    # to the exact invocation the person would be authorizing.
    assert result["kind"] == "clarify"
    assert result["question"] == "¿Quieres que lo mire?"
    assert result["intentOperations"] == ["network.status"]
    # Nothing may be dispatched by a confirmation: that is the whole reason the
    # withdrawal is allowed to survive as a question at all.
    assert result["effectOperations"] == []
    assert result["operation"] is None
    assert llm.confirmations == 1
    # No unsupported prose is even composed, so it cannot be published.
    assert llm.chats == 0


def test_the_read_only_exemption_stays_refuted_by_its_own_counterexample() -> None:
    """A confirmation may ask about the wrong domain; it may never answer it.

    Exempting ``read_only`` operations from the curated gate was measured and
    rejected in goal 03: "¿Cómo está la red neuronal?" proposes
    ``network.status``, and answering it reports the machine's connectivity to a
    question about neural networks. Withholding the same proposal for
    confirmation does not reopen that: the person is asked, and says no.
    """

    result = _withheld_effect_turn(_WithheldEffectLlm(identifies=True))
    assert result["kind"] != "action"
    assert result["effectOperations"] == []


def test_an_unidentified_proposal_keeps_the_honest_unsupported_answer() -> None:
    llm = _WithheldEffectLlm(identifies=False)
    result = _withheld_effect_turn(llm)

    assert result["kind"] == "conversation"
    assert result["intentOperations"] == []
    assert llm.confirmations == 0
    assert llm.chats == 1


def test_a_confirmation_question_the_model_will_not_write_is_not_invented() -> None:
    """Invariant 5 holds on both sides: no fixed visible reply, ever.

    A template would have made this branch deterministic and cheap. It would
    also have put a constant on screen, which is the same product defect whether
    the constant says "no puedo" or "¿lo hago?". When the model does not
    return one well-formed question, the turn keeps the honest refusal.
    """

    llm = _WithheldEffectLlm(identifies=True, question="claro que sí")
    result = _withheld_effect_turn(llm)

    assert result["kind"] == "conversation"
    assert result["intentOperations"] == []


def test_the_second_opinion_is_asked_only_about_what_was_withdrawn() -> None:
    llm = _WithheldEffectLlm(identifies=True)
    _withheld_effect_turn(llm)
    assert llm.identity_calls == ["network.status"]


def _goal03c_catalog_tool(operation: str) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"),
            "canonical_name": operation,
            "description": f"Authenticated catalog leaf {operation}.",
            "risk": "read_only",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    }


class _ProposedLeafLlm:
    """A decider that names one leaf and will identify it if asked."""

    def __init__(self, operation: str) -> None:
        self.operation = operation
        self.identity_calls: list[str] = []
        self.confirmations = 0

    def decide_turn(self, *_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "mode": "action",
            "operation": self.operation,
            "question": "",
            "conversation_kind": "",
            "effect_count": "one",
            "effect_operations": [self.operation],
            "effect_verification": "agreed",
            "response_language": "es",
        }

    def operation_is_the_requested_effect(
        self,
        _text: str,
        operation: str,
        _contract: dict[str, object],
    ) -> bool:
        self.identity_calls.append(operation)
        return True

    def confirm_operation_before_acting(
        self,
        _text: str,
        _effects: tuple[tuple[str, str], ...],
        **_kwargs: object,
    ) -> str:
        self.confirmations += 1
        return "¿Quieres que lo haga?"

    @staticmethod
    def _verify_semantic_effect_shape(_text: str) -> tuple[str, str]:
        return "no_effect", "zero"

    @staticmethod
    def consume_deferred_response_language(_text: str) -> tuple[bool, str | None]:
        return True, "es"

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "es"

    @staticmethod
    def chat(*_args: object, **_kwargs: object) -> tuple[str, list[object]]:
        return "Eso no lo hago.", []


def _goal03c_final_operations(result: dict[str, object]) -> list[str]:
    names: list[str] = []
    operation = result.get("operation")
    if isinstance(operation, str) and operation:
        names.append(operation)
    for key in ("effectOperations", "intentOperations"):
        for value in result.get(key) or []:
            if isinstance(value, str) and value and value not in names:
                names.append(value)
    return names


def _goal03c_prepare_turn(text: str, operation: str) -> dict[str, object]:
    tool = _goal03c_catalog_tool(operation)
    return _prepare_turn_result(
        {"id": f"goal03c-{operation}", "text": text},
        llm=_ProposedLeafLlm(operation),
        planner_catalog=PlannerCatalog([tool]),
        turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name={operation: tool},
    )


_GOAL03C_OOC_AND_COUNTERPARTS = (
    (
        "pide un taxi para las ocho",
        "agregame al pendiente revisar el contrato",
        "task.create",
    ),
    (
        "upload this video to youtube",
        "play the tiny desk concert on youtube",
        "media.play.youtube",
    ),
    (
        "grabame la pantalla en video",
        "captura de la ventana activa",
        "capture.active.window",
    ),
    (
        "connect to my work vpn",
        "connect to my home wifi",
        "wifi.connect.named",
    ),
    (
        "cloname el disco duro a otro",
        "copiame el archivo notas.txt a documentos",
        "filesystem.copy",
    ),
    (
        "editame el video y quitale los ultimos diez segundos",
        "retrocede diez segundos la cancion",
        "media.seek.relative",
    ),
    (
        "convierteme este pdf a word",
        "creame un documento de word en blanco",
        "office.document.create",
    ),
    (
        "unlock my phone for me",
        "apaga la compu",
        "system.power",
    ),
    (
        "imprimeme en 3d esta figura",
        "imprimime este documento en la impresora",
        "peripheral.print",
    ),
)


@pytest.mark.parametrize(
    ("ooc_text", "in_catalog_text", "operation"),
    _GOAL03C_OOC_AND_COUNTERPARTS,
)
def test_out_of_catalog_near_miss_turns_publish_no_catalog_leaf(
    ooc_text: str,
    in_catalog_text: str,
    operation: str,
) -> None:
    """Even a decider that identifies the substitute must not publish it.

    The scorer unions operation, effectOperations and intentOperations. A
    clarify that still names the leaf counts as acted. The in-catalog
    counterpart of the same leaf may still be published.
    """

    ooc = _goal03c_prepare_turn(ooc_text, operation)
    assert operation not in _goal03c_final_operations(ooc)
    assert ooc["effectOperations"] == []
    assert ooc["operation"] is None

    counterpart = _goal03c_prepare_turn(in_catalog_text, operation)
    assert operation in _goal03c_final_operations(counterpart)


def test_a_silent_verifier_never_revives_withdrawn_authority() -> None:
    """Every guard added here is one-sided; a failure keeps the stricter side."""

    class Exploding(_WithheldEffectLlm):
        def operation_is_the_requested_effect(
            self,
            _text: str,
            _operation: str,
            _contract: dict[str, object],
        ) -> bool:
            raise RuntimeError("verifier unavailable")

    result = _withheld_effect_turn(Exploding(identifies=True))
    assert result["kind"] == "conversation"
    assert result["intentOperations"] == []


def test_the_recogniser_declines_only_on_an_explicit_negative_verdict() -> None:
    """The deterministic path keeps every row it resolves unless told otherwise.

    It publishes the operations it resolved and ranks nothing, so a rule that
    fires on the wrong leaf hands that leaf to every stage below. Goal 03
    measured the cost (12 of 124) and measured that sending all 38 of its rows
    to the model instead is worse (24 served against 26). Declining only the
    ones an independent verifier refuses is the third option, and like every
    other guard here it may only withdraw a claim -- never move it elsewhere.
    """

    intent = EffectIntent(
        ("network.status",),
        ("¿Cómo está la red neuronal?",),
    )
    arguments = (
        intent,
        "¿Cómo está la red neuronal?",
        {"network.status": _NETWORK_STATUS_TOOL},
    )

    class Verdict:
        def __init__(self, value: bool) -> None:
            self.value = value

        def operation_is_the_requested_effect(self, *_args: object) -> bool:
            return self.value

    class Exploding:
        @staticmethod
        def operation_is_the_requested_effect(*_args: object) -> bool:
            raise RuntimeError("verifier unavailable")

    assert mind_main._recogniser_identity_holds(*arguments, Verdict(True), ()) is True
    assert mind_main._recogniser_identity_holds(*arguments, Verdict(False), ()) is False
    # No verifier, or one that fails, leaves the recogniser exactly as it was.
    assert mind_main._recogniser_identity_holds(*arguments, Exploding(), ()) is True
    assert mind_main._recogniser_identity_holds(*arguments, object(), ()) is True


def test_a_closed_refusal_asks_the_catalogue_before_it_speaks() -> None:
    """Named-variant lists deny capabilities as soon as the wording moves.

    ``open the last file I downloaded`` closes on the
    ``filesystem.file.open.named`` clause because its exemption lists
    ``ultimo``, ``latest``, ``reciente`` and ``newest`` but not ``last``, while
    ``filesystem.file.open.latest`` is in the catalogue doing exactly that. Five
    of 124 goal 03 rows died that way. The withdrawal names one operation as
    evidence and then stands aside: the ranked path decides the turn.
    """

    catalog = PlannerCatalog([_NETWORK_STATUS_TOOL])

    class Identifies:
        @staticmethod
        def operation_is_the_requested_effect(*_args: object) -> bool:
            return True

    class Refuses:
        @staticmethod
        def operation_is_the_requested_effect(*_args: object) -> bool:
            return False

    arguments = (
        "¿Cómo está la red?",
        "¿Cómo está la red?",
        catalog,
        {"network.status": _NETWORK_STATUS_TOOL},
    )
    assert (
        mind_main._catalog_answers_the_request(*arguments, Identifies(), ())
        == "network.status"
    )
    assert mind_main._catalog_answers_the_request(*arguments, Refuses(), ()) == ""
    assert mind_main._catalog_answers_the_request(*arguments, object(), ()) == ""


def test_a_social_offer_never_becomes_a_catalogue_confirmation() -> None:
    class SocialRuntime(_WithheldEffectLlm):
        def decide_turn(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            return {
                "mode": "conversation",
                "operation": None,
                "question": "",
                "conversation_kind": "social",
                "effect_count": "zero",
                "effect_operations": [],
                "effect_verification": "not_applicable",
                "response_language": "es",
            }

        def chat(self, *_args: object, **_kwargs: object) -> tuple[str, list[object]]:
            self.chats += 1
            return "Sí, te escucho.", []

    runtime = SocialRuntime(
        identifies=True,
        question="¿Quieres que emita autoridad CAS sin exponer detalles?",
    )
    result = _prepare_turn_result(
        {"id": "owner-social-offer", "text": "Me puedes ayudar en algo"},
        llm=runtime,
        planner_catalog=PlannerCatalog([_NETWORK_STATUS_TOOL]),
        turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name={"network.status": _NETWORK_STATUS_TOOL},
    )

    assert result["kind"] == "conversation"
    assert result["reply"] == "Sí, te escucho."
    assert result["intentOperations"] == []
    assert runtime.confirmations == 0


@pytest.mark.parametrize(
    "question",
    [
        "¿Quieres que inicie un AppID poseído?",
        "¿Quieres que emita autoridad CAS sin exponer detalles?",
    ],
)
def test_machine_vocabulary_cannot_escape_through_a_clarification(
    question: str,
) -> None:
    assert not mind_main._recovery_question_is_valid(question)
    with pytest.raises(ValueError, match="aclaración"):
        llm_module.validate_missing_argument_clarification(
            {"requested_fields": ["target"], "question": question},
            ("target",),
        )
