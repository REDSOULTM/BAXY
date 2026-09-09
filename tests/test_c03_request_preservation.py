"""Regressions at the user_text-to-composition boundary (C03 panel-opus-13)."""

import json

import pytest

from baxy_mind import llm
from baxy_mind.request_reading import read_request


@pytest.mark.parametrize("text", ["no subas el volumen", "no silencies el audio"])
def test_negative_real_log_request_is_conversation_not_a_capability_refusal(text: str) -> None:
    from baxy_mind.__main__ import _explicit_stable_no_effect_turn_decision

    decision = _explicit_stable_no_effect_turn_decision(text)
    assert decision is not None
    assert decision["mode"] == "conversation"
    assert decision["conversation_kind"] == "knowledge"
    assert decision["effect_operations"] == []


class Recorder(llm.LlmRuntime):
    def __init__(self, replies: list[str]) -> None:
        self._gguf = "granite-4.2-3b-Q4_K_M.gguf"
        self.replies = iter(replies)
        self.payloads: list[dict] = []

    def _post(self, payload: dict) -> dict:
        self.payloads.append(payload)
        return {
            "choices": [
                {"message": {"content": next(self.replies)}, "finish_reason": "stop"}
            ]
        }


def test_optional_compose_budget_covers_retries_without_resetting_the_turn(monkeypatch) -> None:
    now = [100.0]
    monkeypatch.setattr(llm.time, "monotonic", lambda: now[0])

    class TimedRecorder(Recorder):
        def _post(self, payload: dict, **kwargs: object) -> dict:
            self.options.append(kwargs)
            now[0] += 3.0
            return super()._post(payload)

    runtime = TimedRecorder(["Listo.", "Estoy revisando tu solicitud."])
    runtime.options = []
    runtime._request_deadline = 117.0
    runtime._request_total_deadline = 122.0
    facts = {"situation": {"kind": "status", "cause": "acting", "phase": "understanding"}}
    with pytest.raises(TimeoutError, match="composición opcional"):
        runtime.compose_user_message("Lee el archivo.", "status", facts, timeout=2.5)
    assert len(runtime.payloads) == 1
    assert runtime.options == [{"timeout": 2.5, "max_attempts": 1}]
    assert runtime._request_deadline == 117.0
    assert runtime._request_total_deadline == 122.0
    assert runtime.compose_user_message("Lee el archivo.", "status", facts) == (
        "Estoy revisando tu solicitud."
    )
    assert runtime.options[-1] == {}


@pytest.mark.parametrize("user_text,reply", [
    ("what is a time zone", "I don't do that."),
    ("what is a time zone", "I can't."),
    ("qué es una zona horaria", "No puedo."),
])
def test_bare_failure_is_not_an_explanation(user_text: str, reply: str) -> None:
    assert llm.compose_visible_defect(
        reply, "conversation", user_text,
        {"situation": {"kind": "conversation", "polarity": "success"}},
    ) == "asserted_failure"


@pytest.mark.parametrize("reply", [
    "I couldn't read the file because it wasn't found in the sandbox.",
    "I couldn't read the file because it contained invalid UTF-8 characters.",
])
def test_explanation_of_a_prior_failure_is_not_a_bare_refusal(reply: str) -> None:
    assert llm.compose_visible_defect(
        reply, "conversation", "Why couldn't you read that file?",
        {"situation": {"kind": "conversation", "polarity": "success"}},
    ) == ""


@pytest.mark.parametrize("language", ["es", "en", "mixed"])
@pytest.mark.parametrize(
    "choices,spanish,english",
    [
        (
            ["continuar", "continue", "cancelar", "cancel"],
            ["continuar", "cancelar"],
            ["continue", "cancel"],
        ),
        (
            ["continuar", "continue", "retry"],
            ["continuar", "retry"],
            ["continue", "retry"],
        ),
        (["confirmar", "confirm"], ["confirmar"], ["confirm"]),
    ],
)
def test_recovery_projection_keeps_all_and_only_available_decisions(
    language: str, choices: list[str], spanish: list[str], english: list[str]
) -> None:
    situation = {
        "kind": "confirmation",
        "polarity": "pending",
        "cause": "memory_recovery_pending",
        "choices": choices,
    }
    payload = llm._compose_situation_payload(situation, language)
    assert payload["choices"] == (english if language == "en" else spanish)
    assert situation["choices"] == choices


def test_verified_audio_transition_is_not_rejected_as_a_read_or_truncated_key() -> None:
    situation = {
        "kind": "operation",
        "operation": "audio.volume",
        "polarity": "success",
        "verified": True,
        "succeeded": True,
        "observed": {
            "baseline": {"volumePercent": 80, "muted": False},
            "final": {"volumePercent": 60, "muted": False},
            "applied": True,
            "reconciled": False,
        },
    }
    reply = "I set the volume to 60%."
    facts = {"situation": json.dumps(situation)}
    payload = llm._compose_situation_payload(situation, "en")
    assert payload["effect"] == "applied"
    assert payload["seen"]["level"] == 60
    assert not llm._truncated_fact_word(reply, payload)
    assert not llm._payload_fact_defect(reply, payload)
    assert llm._payload_fact_defect("I set the volume to 80%.", payload)
    recorder = Recorder([reply])
    assert recorder.compose_user_message("Set it to 60%.", "status", facts) == reply
    assert len(recorder.payloads) == 1


@pytest.mark.parametrize("verified,applied", [(False, True), (True, False)])
def test_unverified_or_unapplied_transition_cannot_claim_a_change(
    verified: bool, applied: bool
) -> None:
    payload = llm._compose_situation_payload(
        {
            "kind": "operation",
            "operation": "audio.volume",
            "polarity": "success",
            "verified": verified,
            "succeeded": True,
            "observed": {"final": {"volumePercent": 60}, "applied": applied},
        },
        "en",
    )
    assert "effect" not in payload
    assert llm._payload_fact_defect("I set the volume to 60%.", payload)


@pytest.mark.parametrize(
    "user_text,intent,situation,reply",
    [
        (
            "Hey, buenas; responde en spanglish.",
            "welcome",
            {"kind": "welcome", "polarity": "success"},
            "¡Hey! Buenas, ¿cómo estás?",
        ),
        (
            "Close the window titled Panel local C03.",
            "confirmation",
            {
                "kind": "confirmation",
                "polarity": "pending",
                "choices": ["confirm", "cancel"],
            },
            "Would you like to confirm closing the window titled Panel local C03? Or cancel the action?",
        ),
        (
            "Close the window titled Panel local C03.",
            "confirmation",
            {
                "kind": "confirmation",
                "polarity": "pending",
                "choices": ["confirm", "cancel"],
            },
            "Please confirm or cancel: Close the window titled Panel local C03.",
        ),
        (
            "Find the installed applications.",
            "status",
            {"kind": "status", "polarity": "success", "cause": "acting"},
            "I'm looking into the installed applications right now.",
        ),
        (
            "Find the installed applications.",
            "status",
            {"kind": "status", "polarity": "success", "cause": "acting"},
            "Still working on finding the installed applications.",
        ),
        (
            "Revisa las aplicaciones instaladas.",
            "status",
            {"kind": "status", "polarity": "success", "cause": "acting"},
            "Estoy revisando las aplicaciones instaladas.",
        ),
    ],
)
def test_useful_captured_drafts_survive_presentation_without_retries(
    user_text: str, intent: str, situation: dict, reply: str
) -> None:
    client = Recorder([reply])
    assert (
        client.compose_user_message(
            user_text, intent, {"situation": json.dumps(situation)}
        )
        == reply
    )
    assert len(client.payloads) == 1


def test_later_gerund_does_not_turn_a_completed_claim_into_progress() -> None:
    assert (
        llm.compose_visible_defect(
            "Encontré las aplicaciones instaladas. Puedo explicarlo manteniendo la claridad.",
            "status",
            "Find las aplicaciones instaladas; responde en spanglish.",
            {
                "situation": json.dumps(
                    {"kind": "status", "cause": "acting", "polarity": "success"}
                )
            },
        )
        == "acting_asserted"
    )


@pytest.mark.parametrize("user_text,reply", [
    ("Dime la hora y el uso de CPU.",
     "La hora es 14:30, el audio está en curso y el uso de CPU es del 45%."),
    ("Dime la hora.", "Sigo trabajando. Son las 14:30."),
    ("Read the CPU usage.", "Still working, CPU usage is 45%."),
    ("Pon el volumen al 20%.", "Sigo trabajando. El volumen está al 20%."),
    ("Set the volume to 20%.", "Still working. The volume is at 20%."),
])
def test_progress_cannot_publish_invented_or_requested_measurements(
    user_text: str, reply: str,
) -> None:
    facts = {"situation": json.dumps({"kind": "status", "cause": "acting", "polarity": "success"})}
    assert llm.compose_visible_defect(reply, "status", user_text, facts) == "acting_asserted"


@pytest.mark.parametrize("user_text,reply", [
    ("Programa un recordatorio a las 14:30.", "Estoy preparando el recordatorio de las 14:30."),
    ("Pon el volumen al 20%.", "Estoy preparando el ajuste al 20%."),
    ("Read the file report14:30.txt", "I'm working on reading report14:30.txt."),
])
def test_progress_may_refer_to_literal_targets_without_claiming_results(
    user_text: str, reply: str,
) -> None:
    facts = {"situation": json.dumps({"kind": "status", "cause": "acting", "polarity": "success"})}
    assert llm.compose_visible_defect(reply, "status", user_text, facts) == ""


def test_progress_retry_keeps_narration_role_and_does_not_prescribe_visible_words() -> None:
    corrected = "Estoy consultando la hora y el uso de CPU."
    client = Recorder([
        "La hora es 14:30, el audio está en curso y el uso de CPU es del 45%.",
        corrected,
    ])
    client._gguf = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
    request = "Dime la hora y el uso de CPU."
    result = client.compose_user_message(request, "status", {
        "situation": json.dumps({"kind": "status", "cause": "acting", "polarity": "success"}),
    })
    assert result == corrected
    assert len(client.payloads) == 2
    for payload in client.payloads:
        assert llm._PROGRESS_MESSAGE_INSTRUCTION in payload["messages"][0]["content"]
        assert request not in payload["messages"][-1]["content"]
        assert "Sigo." not in payload["messages"][0]["content"]
        assert "Still working." not in payload["messages"][0]["content"]


@pytest.mark.parametrize("phase,state", [
    ("understanding", "reviewing the person's request"),
    ("preparing_steps", "preparing the steps for the request"),
    ("acting", "working on the current step"),
])
def test_progress_projects_actual_phase_instead_of_the_future_goal(phase: str, state: str) -> None:
    client = Recorder(["Estoy trabajando en los detalles de tu petición."])
    request = 'Lee el archivo "informe-corrupto.txt" del sandbox.'
    client.compose_user_message(request, "status", {
        "situation": {"kind": "status", "cause": "acting", "polarity": "success",
                      "phase": phase, "step": 2, "totalSteps": 3},
    })
    content = client.payloads[0]["messages"][-1]["content"]
    assert request not in content
    line = next(line for line in content.splitlines() if line.startswith("situation: "))
    projected = json.loads(line.removeprefix("situation: "))
    assert projected["state"] == state
    assert projected.get("step") == (2 if phase == "acting" else None)
    assert projected.get("totalSteps") == (3 if phase == "acting" else None)
    assert "Idioma obligatorio: español" in content


def test_uncertain_effect_is_not_projected_as_completed_or_absent() -> None:
    payload = llm._compose_situation_payload(
        {
            "kind": "failure",
            "polarity": "failure",
            "cause": "result_unverified",
            "pendingRequest": "abre la calculadora",
            "effectUncertain": True,
            "verified": False,
            "pending": True,
            "canRepeat": False,
            "evidenceRetained": True,
        },
        "es",
        "cierra la calculadora",
    )
    assert payload["outcome"] == "unverified"
    assert payload["effect"] == "unknown"
    assert payload["pendingRequest"] == "abre la calculadora"
    assert payload["pending"] is True
    assert payload["canRepeat"] is False
    assert payload["evidenceRetained"] is True
    assert "seen" not in payload


@pytest.mark.parametrize(
    "user_text",
    [
        "responde en spanglish: qué es una copia de seguridad",
        "Answer in Spanish: what is a backup?",
        "Hola, contesta en inglés: qué es el cifrado",
    ],
)
def test_response_language_wrapper_preserves_the_question(user_text: str) -> None:
    from baxy_mind.__main__ import _explicit_stable_no_effect_turn_decision

    decision = _explicit_stable_no_effect_turn_decision(user_text)
    assert decision is not None
    assert decision["conversation_kind"] == "knowledge"
    assert decision["effect_operations"] == []


def test_language_wrapper_does_not_hide_actions_or_rewrite_literal_content() -> None:
    from baxy_mind.effect_intent import _strip_request_envelope

    assert _strip_request_envelope("Answer in English: open Paint") == "open Paint"
    literal = 'escribe "responde en spanglish: qué es una copia de seguridad"'
    assert _strip_request_envelope(literal) == literal


@pytest.mark.parametrize(
    "user_text",
    [
        "responde en spanglish: qué es una copia de seguridad",
        "Answer in Spanish: what is a backup",
        "Hola, contesta en inglés: qué es el cifrado",
    ],
)
def test_language_wrapper_keeps_explanation_prompt_and_literal_request(
    user_text: str,
) -> None:
    client = Recorder(["A backup keeps a copy of your data for recovery."])
    client.chat(user_text, conversation_kind="knowledge", response_language="mixed")
    assert len(client.payloads) == 1
    messages = client.payloads[0]["messages"]
    assert messages[0]["content"] == (
        llm.SYSTEM_PROMPT + " " + llm.CONVERSATION_FACT_PROVENANCE_PROMPT
    )
    assert messages[-1]["content"] == user_text


def test_truncated_structured_chat_retry_cannot_be_published_as_prose() -> None:
    request = "Explain caching, pero sencillo"
    client = Recorder(
        [
            request,
            '{"answer":"La caché guarda datos temporales so you can access them quickly',
        ]
    )
    with pytest.raises(llm.ConversationReplyContractError):
        client.chat(request, conversation_kind="knowledge", response_language="mixed")


def test_clock_instruction_echo_is_recomposed_instead_of_hidden_by_a_crop() -> None:
    corrected = "Son las 14:25."
    client = Recorder(["Son las 14:25. Do not introduce yourself.", corrected])
    answer = client.compose_user_message(
        "¿Qué hora es?",
        "status",
        {
            "situation": json.dumps(
                {
                    "kind": "operation",
                    "operation": "system.time",
                    "polarity": "success",
                    "verified": True,
                    "succeeded": True,
                    "observed": {
                        "utc": "2026-09-06T17:25:00Z",
                        "localUtcOffsetMinutes": -180,
                    },
                }
            ),
        },
    )
    assert answer == corrected
    assert len(client.payloads) == 2


def test_query_mission_does_not_instruct_the_model_to_claim_a_state_change() -> None:
    client = Recorder(
        ["Son las 14:25. El volumen está al 40 y el audio está silenciado."]
    )
    client.compose_user_message(
        "Dime la hora y el estado del audio",
        "status",
        {
            "situation": json.dumps(
                {
                    "kind": "status",
                    "cause": "mission_completed",
                    "polarity": "success",
                    "observed": {
                        "utc": "2026-09-06T17:25:00Z",
                        "localUtcOffsetMinutes": -180,
                        "muted": True,
                        "level": 40,
                    },
                }
            ),
        },
    )
    content = client.payloads[0]["messages"][-1]["content"]
    assert '"clock": "14:25"' in content
    assert '"muted": true' in content
    assert "Report the completed state change" not in content


def test_mixed_request_does_not_mark_a_useful_spanish_answer_as_deficient(
    tmp_path,
    monkeypatch,
) -> None:
    audit = tmp_path / "raw.jsonl"
    monkeypatch.setenv("BAXY_MIND_RAW_REPLY_AUDIT_PATH", str(audit))
    reply = "Encryption es una transformación que protege los datos con una clave."
    client = Recorder([reply])
    answer, calls = client.chat(
        "Explain encryption, pero en simple",
        conversation_kind="knowledge",
        response_language="mixed",
    )
    assert (answer, calls) == (reply, [])
    assert len(client.payloads) == 1
    rows = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
    assert "mixed_language_needs_review" not in rows[0]


@pytest.mark.parametrize(
    "user_text, response",
    [
        (
            "What time is it y cómo está el audio?",
            "Son las 13:23; el volumen está al 100% y el audio no está silenciado.",
        ),
        ("Hey, buenas", "¡Hola! Bienvenido; welcome to the chat."),
    ],
)
def test_owner_approved_mixed_responses_do_not_require_language_alternation(
    user_text: str, response: str
) -> None:
    client = Recorder([response])
    situation = (
        {"kind": "welcome", "polarity": "success"}
        if user_text == "Hey, buenas"
        else {
            "kind": "operation",
            "operation": "audio.status",
            "polarity": "success",
            "verified": True,
            "observed": {
                "utc": "2026-01-01T13:23:00+00:00",
                "localUtcOffsetMinutes": 0,
                "muted": False,
                "level": 100,
            },
        }
    )
    assert (
        client.compose_user_message(
            user_text,
            "welcome" if user_text == "Hey, buenas" else "status",
            {"situation": json.dumps(situation)},
        )
        == response
    )
    assert len(client.payloads) == 1
    sent = client.payloads[0]["messages"][-1]["content"]
    assert llm.MIXED_RESPONSE_LANGUAGE_POLICY in sent
    assert "No lo conviertas por completo a un solo idioma" not in sent


@pytest.mark.parametrize(
    "user_text, reply, expected",
    [
        (
            "Explain encryption, pero en simple",
            "Encryption protects your data by making it unreadable without a key.",
            "",
        ),
        (
            "Explain encryption, pero en simple",
            "El cifrado protege tus datos para que nadie los lea sin una clave.",
            "",
        ),
        (
            "Explain encryption, pero en simple",
            "El cifrado protege tus datos so only someone with the key can read them.",
            "",
        ),
        ("Hey, buenas", "Hello! How can I help you today?", ""),
        ("Hey, buenas", "¡Buenas! What can I help you with?", ""),
        ("What is 14 por 6", "84.", ""),
    ],
)
def test_mixed_style_does_not_gate_publication_or_neutral_facts(
    user_text: str,
    reply: str,
    expected: str,
) -> None:
    intent = "welcome" if read_request(user_text).greeting_only else "conversation"
    assert (
        llm.compose_visible_defect(
            reply,
            intent,
            user_text,
            {
                "situation": json.dumps({"kind": intent, "polarity": "success"}),
            },
        )
        == expected
    )


def test_chat_keeps_language_policy_without_redecoding_for_vocabulary() -> None:
    reply = "Encryption protects your data by making it unreadable without a key."
    client = Recorder([reply])
    answer, calls = client.chat(
        "Explain encryption, pero en simple",
        conversation_kind="knowledge",
        response_language="mixed",
    )
    assert answer == reply
    assert calls == []
    assert len(client.payloads) == 1
    assert any(
        "spanglish" in m["content"]
        for m in client.payloads[0]["messages"]
        if m["role"] == "system"
    )


def test_chat_retains_echo_retry_without_a_second_language_vocabulary_veto() -> None:
    client = Recorder(
        [
            "Explain encryption, pero en simple",
            "Encryption makes data unreadable without the key.",
        ]
    )
    answer, _ = client.chat(
        "Explain encryption, pero en simple",
        conversation_kind="knowledge",
        response_language="mixed",
    )
    assert answer == "Encryption makes data unreadable without the key."
    assert len(client.payloads) == 2


def test_contextual_answer_is_not_redecoded_for_language_vocabulary(
    monkeypatch,
) -> None:
    reply = "El cifrado protege tus datos para que nadie los lea sin una clave."
    client = Recorder([])
    monkeypatch.setattr(client, "_resolve_contextual_answer", lambda **kwargs: reply)
    answer, calls = client.chat(
        "responde en spanglish: qué es el cifrado",
        conversation_kind="followup",
        response_language="mixed",
        history=[{"role": "assistant", "content": "Hola."}],
    )
    assert answer == reply
    assert calls == []
    assert len(client.payloads) == 0


@pytest.mark.parametrize(
    "user_text, response",
    [
        ("cancelar", "He cancelado la aclaración pendiente."),
        ("cancel that", "The pending clarification is cancelled."),
    ],
)
def test_status_composition_preserves_that_the_transition_already_happened(
    user_text: str,
    response: str,
) -> None:
    client = Recorder([response])
    assert (
        client.compose_user_message(
            user_text,
            "status",
            {
                "situation": json.dumps(
                    {
                        "kind": "status",
                        "polarity": "success",
                        "cause": "clarification_cancelled",
                    }
                ),
            },
        )
        == response
    )
    content = client.payloads[0]["messages"][-1]["content"]
    assert '"outcome": "completed"' in content
    assert '"state": "clarification cancelled"' in content
    assert '"cause":' not in content


def test_progress_is_not_projected_as_a_completed_transition() -> None:
    payload = llm._compose_situation_payload(
        {
            "kind": "status",
            "polarity": "success",
            "cause": "acting",
        },
        "es",
        "haz eso",
    )
    assert "outcome" not in payload
    assert payload["kind"] == "status"
    assert payload["state"] == "in progress"


@pytest.mark.parametrize(
    "user_text, reply, language_hint",
    [
        ("cuánto es doce por ocho", "Sigo calculando el resultado.", "Idioma obligatorio: español"),
        (
            "Explain encryption, pero en simple",
            "Sigo preparando la explicación, keeping it simple.",
            "spanglish",
        ),
    ],
)
def test_progress_composition_preserves_language_without_replaying_the_goal(
    user_text: str, reply: str, language_hint: str
) -> None:
    client = Recorder([reply])
    assert (
        client.compose_user_message(
            user_text,
            "status",
            {
                "situation": json.dumps(
                    {"kind": "status", "cause": "acting", "polarity": "success"}
                ),
            },
        )
        == reply
    )
    content = client.payloads[0]["messages"][-1]["content"]
    assert user_text not in content
    assert language_hint in content


@pytest.mark.parametrize(
    "kind", ["welcome", "conversation", "clarification", "confirmation", "error"]
)
def test_message_purpose_survives_projection_without_observed_facts(kind: str) -> None:
    # Empty observations do not mean the message has no purpose. Losing this
    # discriminator made welcome acknowledge the language instruction instead.
    payload = llm._compose_situation_payload({"kind": kind}, "es", "")
    assert payload["kind"] == kind
    assert "seen" not in payload
    assert "outcome" not in payload


@pytest.mark.parametrize(
    "user_text, answer, intent",
    [
        ("hola", "¡Hola! Soy Baxy, tu compañero. ¿En qué puedo ayudarte?", "welcome"),
        ("Hello", "Hello! I'm Baxy. What can I help you with?", "welcome"),
        (
            "explica qué es DNS en dos frases",
            "DNS traduce nombres de dominio a direcciones IP. Así puedes usar un nombre fácil de recordar.",
            "conversation",
        ),
        (
            "Explain encryption, pero en simple",
            "El cifrado transforma tus datos para protegerlos. You need the key to read them.",
            "conversation",
        ),
    ],
)
def test_equivalent_useful_prose_is_not_rejected_for_sentence_count(
    user_text: str,
    answer: str,
    intent: str,
) -> None:
    assert (
        llm.compose_visible_defect(
            answer,
            intent,
            user_text,
            {
                "situation": json.dumps({"kind": intent, "polarity": "success"}),
            },
        )
        == ""
    )


@pytest.mark.parametrize(
    "answer, intent, situation",
    [
        (
            "¡Hola! Chrome is open.",
            "welcome",
            {"kind": "welcome", "polarity": "success"},
        ),
        ("¿Qué archivo? ¿Dónde está?", "clarification", {"kind": "clarification"}),
        (
            "Listo. ¿Confirmar o cancelar?",
            "confirmation",
            {"kind": "confirmation", "polarity": "pending"},
        ),
        (
            "Listo. Chrome no responde.",
            "error",
            {
                "kind": "error",
                "polarity": "failure",
                "cause": "provider_down",
                "target": "Chrome",
            },
        ),
    ],
)
def test_sentence_count_does_not_replace_fact_and_question_contracts(
    answer: str,
    intent: str,
    situation: dict,
) -> None:
    assert llm.compose_visible_defect(
        answer,
        intent,
        "hola" if intent == "welcome" else "borra el archivo",
        {
            "situation": json.dumps(situation),
        },
    )


@pytest.mark.parametrize(
    "question, answer",
    [
        ("What is fourteen times six?", "Eighty-four."),
        ("What is the capital of Peru?", "Lima."),
        (
            "define DNS in one sentence",
            "DNS translates domain names into IP addresses.",
        ),
    ],
)
def test_knowledge_composition_preserves_the_kind_of_answer_requested(
    question: str,
    answer: str,
) -> None:
    client = Recorder([answer])
    assert (
        client.compose_user_message(
            question,
            "conversation",
            {
                "situation": '{"kind":"conversation","polarity":"success"}',
            },
        )
        == answer
    )
    content = client.payloads[0]["messages"][-1]["content"]
    assert question in content
    # INTENT_KNOWLEDGE includes quantities and entities, not only definitions.
    # The previous instruction made the real model define multiplication
    # instead of answering the requested calculation.
    assert "Explain the concept" not in content


@pytest.mark.parametrize(
    "user_text, reply",
    [
        ("", "Hola, ¿en qué puedo ayudarte hoy?"),
        ("Good afternoon", "Hi! How can I help you today?"),
        ("Good evening", "Good evening! What can I help you with?"),
        ("Buenos días", "¡Buenos días! ¿En qué te ayudo?"),
    ],
)
def test_a_social_greeting_survives_without_rewriting(
    user_text: str, reply: str
) -> None:
    client = Recorder([reply])
    assert (
        client.compose_user_message(
            user_text,
            "welcome",
            {
                "situation": '{"kind":"welcome","polarity":"success"}',
            },
        )
        == reply
    )
    assert len(client.payloads) == 1
    user = client.payloads[0]["messages"][-1]["content"]
    assert user_text in user
    assert '"greeting":' not in user


def test_a_followup_keeps_its_topic_on_every_retry() -> None:
    client = Recorder(
        [
            "¿Por qué importa?",
            "¿Para qué sirve?",
            "La caché importa porque evita volver a buscar los mismos datos.",
        ]
    )
    result = client.compose_user_message(
        "¿por qué importa?",
        "conversation",
        {
            "situation": '{"kind":"conversation","polarity":"success"}',
            "priorRequests": ["explícame qué es la caché, una frase"],
        },
    )
    assert "caché" in result
    assert len(client.payloads) == 3
    for payload in client.payloads:
        content = "\n".join(message["content"] for message in payload["messages"])
        assert "«caché»" in content
        assert "Explain the concept" not in content


def test_a_failed_contract_cannot_escape_before_retry() -> None:
    client = Recorder(
        [
            "El glorp conecta redes.",
            "Un conmutador conecta dispositivos dentro de una red.",
        ]
    )
    result = client.compose_user_message(
        "qué es un conmutador",
        "conversation",
        {
            "situation": '{"kind":"conversation","polarity":"success"}',
            "forbiddenResponseTerms": ["glorp"],
        },
    )
    assert "glorp" not in result
    assert len(client.payloads) == 2


@pytest.mark.parametrize(
    "user_text, reply",
    [
        ("", "Hello! What can I help you with?"),
        ("Good afternoon", "Hola, ¿en qué te ayudo?"),
        ("Good afternoon, what is DNS?", "Good afternoon! How can I help you?"),
        ("Good afternoon", "Hi! Paint is open."),
    ],
)
def test_greeting_does_not_exempt_language_claims_or_the_actual_question(
    user_text: str,
    reply: str,
) -> None:
    assert llm.compose_visible_defect(
        reply,
        "welcome",
        user_text,
        {
            "situation": '{"kind":"welcome","polarity":"success"}',
        },
    )


@pytest.mark.parametrize(
    "reply, expected",
    [
        ("The time is 4:12 PM.", True),
        ("The time is 04:12 p. m.", True),
        ("Son las 16:12.", True),
        ("Son las 16 y 12.", True),
        ("Son las 16 horas y 12 minutos.", True),
        ("The time is sixteen hours and twelve minutes.", True),
        ("Son las 16 horas y 13 minutos.", False),
        ("Son las 16:12, o son las 16 horas y 13 minutos.", False),
        ("Son las 4 y 12 PM.", True),
        ("Son las dieciséis y doce.", True),
        ("Son las cuatro y doce PM.", True),
        ("The time is four twelve PM.", True),
        ("The time is sixteen twelve.", True),
        ("Son las dieciséis y trece; it is 16:12.", False),
        ("The time is four thirteen PM; son las 16:12.", False),
        ("Son las 16 y 13.", False),
        ("Son las 4 y 12 AM.", False),
        ("Son las 16:12, o son las 16 y 13.", False),
        ("Hay 16 y 12 archivos.", False),
        ("Hay dieciséis y doce archivos.", False),
        ("The time is 4:12 AM.", False),
        ("The time is 4:12.", False),
        ("The time is 16:12 AM.", False),
        ("The time is 16:12, or 4:12 AM.", False),
    ],
)
def test_clock_equivalence_preserves_the_actual_half_of_the_day(
    reply: str,
    expected: bool,
) -> None:
    payload = llm._compose_situation_payload(
        {
            "kind": "status",
            "polarity": "success",
            "operation": "system.time",
            "observed": {"utc": "2026-09-06T20:12:00Z", "localUtcOffsetMinutes": -240},
        },
        "en",
    )
    assert (not llm._payload_fact_defect(reply, payload)) is expected


def test_observed_spoken_clock_draft_does_not_exhaust_valid_composition() -> None:
    client = Recorder(["Son las 10 y 10."])
    reply = client.compose_user_message(
        "¿Qué hora es?",
        "status",
        {
            "situation": '{"kind":"operation","operation":"system.time","polarity":"success",'
            '"verified":true,"observed":{"utc":"2026-09-06T13:10:28Z",'
            '"localUtcOffsetMinutes":-180}}',
        },
    )
    assert reply == "Son las 10 y 10."
    assert len(client.payloads) == 1


@pytest.mark.parametrize(
    "draft",
    [
        "Son las tres y veintitres; it’s 13:23.",
        "Son las trece y veinticuatro; it is 13:23.",
        "The time is one twenty-four PM; son las 13:23.",
    ],
)
def test_a_correct_numeric_clock_does_not_hide_a_contradictory_word_clock(
    draft: str,
) -> None:
    assert llm._payload_fact_defect(draft, {"clock": "13:23"}) == "reversed_result"


@pytest.mark.parametrize(
    "draft",
    [
        "Son las trece y veintitrés; it’s 13:23.",
        "The time is one twenty-three PM.",
        "Son las una y veintitrés PM.",
        "Son las 13:23 y hay tres y veintitrés archivos.",
        "It is twenty three files; the time is 13:23.",
    ],
)
def test_word_clock_equivalence_does_not_turn_unframed_counts_into_clocks(
    draft: str,
) -> None:
    assert llm._payload_fact_defect(draft, {"clock": "13:23"}) == ""


def test_contradictory_word_clock_is_recomposed_without_cropping_the_draft() -> None:
    invalid = "Son las tres y veintitres; it’s 13:23."
    valid = "Son las 13:23."
    client = Recorder([invalid, valid])
    reply = client.compose_user_message(
        "¿Qué hora es?",
        "status",
        {
            "situation": '{"kind":"operation","operation":"system.time",'
            '"polarity":"success","verified":true,"observed":'
            '{"utc":"2026-09-06T16:23:00Z","localUtcOffsetMinutes":-180}}'
        },
    )
    assert reply == valid
    assert len(client.payloads) == 2


def test_a_followup_can_name_the_topic_without_exempting_unrelated_internal_terms() -> (
    None
):
    client = Recorder(
        [
            "El planner elige una tool para el router.",
            "El router permite comunicar tu red con otras redes.",
        ]
    )
    reply = client.compose_user_message(
        "¿para qué sirve?",
        "conversation",
        {
            "situation": '{"kind":"conversation","polarity":"success"}',
            "priorRequests": ["explícame qué es un router"],
            "forbiddenResponseTerms": ["router", "planner", "tool"],
        },
    )
    assert reply == "El router permite comunicar tu red con otras redes."
    assert len(client.payloads) == 2


@pytest.mark.parametrize(
    "user_text, expected",
    [
        ("Explain encryption, pero en simple", "mixed"),
        ("Explain encryption", "en"),
        ("Explain encryption in simple terms", "en"),
        ("Explica el cifrado", "es"),
        ("Explica el cifrado, but keep it simple", "mixed"),
    ],
)
def test_instruction_verbs_are_language_evidence(user_text: str, expected: str) -> None:
    assert read_request(user_text).language == expected


@pytest.mark.parametrize("language", ["es", "en", "mixed"])
def test_mission_failure_keeps_the_nested_step_cause(language: str) -> None:
    # Shape emitted by MindPlanSession -> MissionNarration.CreateFailureMessage.
    payload = llm._compose_situation_payload(
        {
            "kind": "failure",
            "polarity": "failure",
            "cause": "mission_failed",
            "steps": [],
            "stepCount": 0,
            "reason": json.dumps(
                {
                    "kind": "failure",
                    "polarity": "failure",
                    "cause": "step_failed",
                    "step": 2,
                }
            ),
        },
        language,
    )
    assert payload == {
        "outcome": "failed",
        "reason": {"outcome": "failed", "cause": "step failed", "step": 2},
    }


@pytest.mark.parametrize("reason", ['{"cause":', "[]"])
def test_a_malformed_failure_reason_does_not_become_a_success_or_raw_prose(
    reason: str,
) -> None:
    payload = llm._compose_situation_payload(
        {
            "kind": "failure",
            "polarity": "failure",
            "reason": reason,
        },
        "es",
    )
    assert payload == {"outcome": "failed"}


@pytest.mark.parametrize("language", ["es", "en", "mixed"])
@pytest.mark.parametrize("error", ["invalid_utf8", "file_too_large", "invalid_resource_id"])
def test_typed_operation_error_survives_nested_mission_projection(language: str, error: str) -> None:
    operation_result = {"kind": "operation", "operation": "filesystem.read.text",
                        "polarity": "failure", "verified": False, "succeeded": False,
                        "error": error}
    projected = llm._compose_situation_payload(
        {"kind": "failure", "cause": "mission_failed", "polarity": "failure",
         "reason": operation_result}, language)
    assert projected["reason"] == {
        "outcome": "failed",
        "cause": error.replace("_", " "),
        "operation": "filesystem.read.text",
    }
    assert operation_result["error"] == error


def test_operation_error_cannot_override_a_cause_or_turn_success_into_failure() -> None:
    for kind, polarity, error in (("operation", "success", "invalid_utf8"),
                                  ("status", "failure", "invalid_utf8"),
                                  ("operation", "failure", {"private": "value"})):
        projected = llm._compose_situation_payload(
            {"kind": kind, "polarity": polarity, "error": error}, "en")
        assert "cause" not in projected
    projected = llm._compose_situation_payload(
        {"kind": "operation", "polarity": "failure", "cause": "timeout",
         "error": "invalid_utf8"}, "en")
    assert projected["cause"] == llm._cause_in_prose("timeout", "en")


@pytest.mark.parametrize(
    "intro",
    [
        "Ya [[A1]] los [[COUNT]] pasos.",
        "Los [[COUNT]] pasos quedaron completos y los [[A1]].",
    ],
)
def test_verified_mission_prose_is_not_a_prescribed_sentence(intro: str) -> None:
    client = Recorder([intro])
    facts = ["La hora local es 16:12.", "El volumen observado es 35 %."]
    reply = client.compose_user_message(
        "dime la hora y el volumen",
        "status",
        {
            "situation": '{"kind":"status","cause":"mission_completed","polarity":"success"}',
            "requiredActions": ["verifiqué"],
            "requiredFacts": facts,
        },
    )
    assert intro.replace("[[A1]]", "verifiqué").replace("[[COUNT]]", "2") in reply
    assert all(fact in reply for fact in facts)
    assert len(client.payloads) == 1


@pytest.mark.parametrize("language", ["es", "en", "mixed"])
def test_confirmation_keeps_original_request_and_exact_pending_action(
    language: str,
) -> None:
    from baxy_mind.llm import _compose_situation_payload

    action = {
        "operation": "app.close",
        "purpose": "Cerrar la ventana de prueba.",
        "arguments": {"windowId": "12345", "processId": 678},
    }
    situation = {
        "kind": "confirmation",
        "polarity": "pending",
        "cause": "step_confirm_or_cancel",
        "step": 2,
        "pendingRequest": "cierra la ventana de prueba",
        "pendingAction": action,
        "choices": ["confirmar", "confirm", "cancelar", "cancel"],
    }
    payload = _compose_situation_payload(situation, language, "tal vez")
    assert payload["pendingRequest"] == situation["pendingRequest"]
    assert payload["pendingAction"] == {
        **action,
        "arguments": {"processId": 678},
    }
    assert "seen" not in payload
    assert payload.get("outcome") != "completed"
    payload["pendingAction"]["arguments"]["windowId"] = "different"
    assert action["arguments"]["windowId"] == "12345"


@pytest.mark.parametrize("language", ["es", "en", "mixed"])
def test_cancellation_preserves_what_was_stopped_without_turning_it_into_an_effect(
    language: str,
) -> None:
    from baxy_mind.llm import _compose_situation_payload

    action = {"operation": "app.close", "arguments": {"windowId": "12345"}}
    payload = _compose_situation_payload(
        {
            "kind": "status",
            "polarity": "success",
            "cause": "remaining_steps_cancelled",
            "cancelledRequest": "cierra la ventana de prueba",
            "cancelledAction": action,
            "steps": [
                {
                    "kind": "operation",
                    "operation": "window.resolve",
                    "readOnly": True,
                    "observed": {"windows": [{"state": "maximized"}]},
                }
            ],
        },
        language,
        "cancelar",
    )
    assert payload["cancelledRequest"] == "cierra la ventana de prueba"
    assert payload["cancelledAction"] == {"operation": "app.close", "arguments": {}}
    assert payload["outcome"] == "cancelled"
    assert "pendingAction" not in payload
    assert "effect" not in payload
    assert "seen" not in payload
    assert payload["completedStepsInOrder"][0]["resultAtThisStep"]["readOnly"] is True
    payload["cancelledAction"]["arguments"]["windowId"] = "different"
    assert action["arguments"]["windowId"] == "12345"


@pytest.mark.parametrize("language", ["es", "en", "mixed"])
def test_cancelled_mission_keeps_prior_effects_and_removes_opaque_window_capabilities(
    language: str,
) -> None:
    situation = {
        "kind": "status",
        "polarity": "success",
        "cause": "remaining_steps_cancelled",
        "cancelledAction": {
            "operation": "app.close",
            "arguments": {"windowId": "win_secret"},
        },
        "steps": [
            {
                "kind": "operation",
                "operation": "audio.set_volume",
                "readOnly": False,
                "observed": {"level": 35},
            },
            {
                "kind": "operation",
                "operation": "window.resolve",
                "readOnly": True,
                "observed": {
                    "windows": [
                        {
                            "windowId": "win_secret",
                            "processName": "Example",
                            "state": "maximized",
                        }
                    ]
                },
            },
        ],
    }
    payload = llm._compose_situation_payload(situation, language, "cancelar")
    assert payload["outcome"] == "cancelled"
    steps = payload["completedStepsInOrder"]
    assert steps[0]["resultAtThisStep"] == {
        "readOnly": False,
        "seen": {"level": 35},
        "operation": "audio.set_volume",
    }
    assert steps[1]["resultAtThisStep"]["seen"]["windows"] == [
        {"processName": "Example", "state": "maximized"}
    ]
    assert "win_secret" not in json.dumps(payload)
    assert "win_secret" in json.dumps(situation)


@pytest.mark.parametrize("language", ["es", "en", "mixed"])
def test_mission_keeps_observations_at_the_step_that_verified_them(
    language: str,
) -> None:
    import json
    from baxy_mind.llm import _compose_situation_payload

    def result(operation, observed):
        return json.dumps(
            {
                "kind": "operation",
                "operation": operation,
                "polarity": "success",
                "verified": True,
                "observed": observed,
            }
        )

    payload = _compose_situation_payload(
        {
            "kind": "status",
            "polarity": "success",
            "cause": "mission_completed",
            "completedRequest": "Cierra la ventana titulada 'Proyecto Ámbar'",
            "steps": [
                result(
                    "window.resolve",
                    {
                        "windows": [
                            {
                                "processName": "Example",
                                "state": "maximized",
                                "foreground": False,
                            }
                        ]
                    },
                ),
                result("app.close", {"windowClosed": True}),
            ],
        },
        language,
    )
    assert "seen" not in payload
    assert payload["completedRequest"] == "Cierra la ventana titulada 'Proyecto Ámbar'"
    steps = payload["completedStepsInOrder"]
    assert steps[0]["operation"] == "window.resolve"
    assert steps[0]["resultAtThisStep"]["seen"]["windows"][0]["state"] == "maximized"
    assert steps[1]["operation"] == "app.close"
    assert steps[1]["resultAtThisStep"]["seen"] == {"windowClosed": True}

    reads = _compose_situation_payload(
        {
            "kind": "status",
            "polarity": "success",
            "cause": "mission_completed",
            "steps": [
                result(
                    "system.time",
                    {"utc": "2026-09-06T12:00:00Z", "localUtcOffsetMinutes": -180},
                ),
                result("audio.status", {"level": 20, "muted": False}),
            ],
        },
        language,
    )
    assert reads["completedStepsInOrder"][0]["resultAtThisStep"]["clock"] == "09:00"
    assert reads["completedStepsInOrder"][1]["resultAtThisStep"]["seen"] == {
        "level": 20,
        "muted": False,
    }


def test_a_verified_window_name_is_not_an_invented_word() -> None:
    from baxy_mind.llm import compose_visible_defect

    facts = {
        "situation": {
            "kind": "status",
            "polarity": "success",
            "observed": {"processName": "C03WindowFixture", "windowClosed": True},
        }
    }
    assert (
        compose_visible_defect(
            "La ventana C03WindowFixture se cerró correctamente.",
            "status",
            "confirmar",
            facts,
        )
        == ""
    )
    assert (
        compose_visible_defect(
            "La ventanaien la ventana.", "status", "confirmar", facts
        )
        == "invented"
    )


def test_read_only_observation_remains_a_read_in_the_compose_payload() -> None:
    from baxy_mind.llm import _compose_situation_payload

    payload = _compose_situation_payload(
        {
            "kind": "operation",
            "operation": "window.resolve",
            "readOnly": True,
            "observed": {"windows": [{"state": "maximized"}]},
        },
        "es",
    )
    assert payload["readOnly"] is True
    assert "effect" not in payload


def test_direct_answer_retries_the_same_wrong_language_that_compose_rejects() -> None:
    question = "what is the capital of Peru"
    incorrect = "La capital de Perú es Lima."
    correct = "The capital of Peru is Lima."
    runtime = Recorder([incorrect, json.dumps({"answer": correct})])
    answer, actions = runtime.chat(
        question, conversation_kind="knowledge", response_language="en"
    )
    assert answer == correct
    assert actions == []
    assert len(runtime.payloads) == 2
    assert (
        llm.compose_visible_defect(
            incorrect, "conversation", question, {"situation": {"kind": "conversation"}}
        )
        == "wrong_language"
    )


def test_direct_answer_cannot_publish_a_second_opposite_language_reply() -> None:
    incorrect = "La capital de Perú es Lima."
    runtime = Recorder([incorrect, json.dumps({"answer": incorrect})])
    with pytest.raises(llm.ConversationReplyContractError) as error:
        runtime.chat(
            "what is the capital of Peru",
            conversation_kind="knowledge",
            response_language="en",
        )
    assert error.value.audit_reason == "wrong_language"


def test_a_neutral_proper_name_is_a_complete_answer_in_either_language() -> None:
    for language in ("es", "en"):
        assert not llm._reply_uses_opposite_language("Lima", language)


def test_recovery_failure_keeps_cause_and_absence_of_attempted_operations() -> None:
    payload = llm._compose_situation_payload(
        {
            "kind": "failure",
            "polarity": "failure",
            "cause": "turn_runtime_failure",
            "operationAttempted": False,
            "retryable": True,
        },
        "en",
        "What is on my to do list?",
    )
    assert payload["outcome"] == "failed"
    assert payload["cause"] == "request interpretation failed"
    assert payload["operationAttempted"] is False
    assert payload["retryable"] is True
    assert "seen" not in payload
