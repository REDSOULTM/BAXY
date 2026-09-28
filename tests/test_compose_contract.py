"""C03: lo que se le pide al modelo no se publica, y los vetos no son falsos.

Cada comprobación viene de un turno medido en
`artifacts/comprobaciones/C03/panel-opus-1/`, con la traza de composición que
identifica el borrador y el motivo exacto:

* 008 publicó «Empieza con mayúscula: "Hola, puedo ayudarte a..."» y 022 «The
  facts are: it is a short sentence in English...»: la corrección del reintento
  viajaba mezclada con los hechos y Granite la copiaba.
* 007 y 008 enumeraron las treinta y una familias del catálogo en una frase.
* 018 agotó ocho composiciones porque «I will never install unauthorized
  software on this PC» no contenía ningún verbo de una lista cerrada.
* 020 y 022 perdieron el tema del turno anterior.
"""

import json

import pytest

from baxy_mind import llm as llm_mod
from baxy_mind.llm import (
    CAPABILITY_SAMPLE,
    _compose_situation_payload,
    compose_visible_defect,
    served_capability_families,
)

GRANITE = r"D:\BAXYRuntime\assets\models\granite-4.2-3b-Q4_K_M.gguf"
CONVERSATION = {"situation": '{"kind":"conversation","polarity":"success"}'}


@pytest.mark.parametrize("operation", [
    "memory.enable", "memory.forget", "memory.export", "memory.sensitive.save",
])
def test_memory_cancellation_retains_the_withdrawn_operation(operation: str) -> None:
    action = {"operation": operation, "target": "private local memory"}
    payload = _compose_situation_payload({
        "kind": "status", "polarity": "success", "cause": "memory_cancelled",
        "cancelledAction": action,
    }, "en", "cancel")
    assert payload["outcome"] == "cancelled"
    assert payload["cancelledAction"] == action
    assert "observed" not in payload
    assert "pendingAction" not in payload


def test_uncertain_memory_withdrawal_does_not_become_a_cancellation() -> None:
    action = {"operation": "memory.export", "target": "private local memory"}
    payload = _compose_situation_payload({
        "kind": "confirmation", "polarity": "pending",
        "cause": "cannot_withdraw_uncertain", "choices": ["confirmar", "confirm"],
        "pendingAction": action,
    }, "en", "cancel")
    assert payload.get("outcome") != "cancelled"
    assert "cancelledAction" not in payload
    assert payload["pendingAction"] == action


@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize("may_redirect", [False, True])
def test_export_confirmation_preserves_destination_and_sync_fact(
    language: str, may_redirect: bool,
) -> None:
    action = {"operation": "memory.export", "target": "private local memory"}
    payload = _compose_situation_payload({
        "kind": "confirmation", "polarity": "pending",
        "cause": "memory_export_privacy", "pendingAction": action,
        "destination": "Documents/BAXY", "mayRedirectOrSync": may_redirect,
    }, language, "cancel")
    assert payload["pendingAction"] == action
    assert payload["destination"] == "Documents/BAXY"
    assert payload["mayRedirectOrSync"] is may_redirect
    assert payload.get("outcome") != "completed"


@pytest.mark.parametrize("extra", [{}, {
    "destination": [], "mayRedirectOrSync": "false",
}, {"destination": " ", "mayRedirectOrSync": 1}])
def test_confirmation_does_not_invent_export_destination_or_sync(extra: dict) -> None:
    payload = _compose_situation_payload({
        "kind": "confirmation", "polarity": "pending",
        "cause": "memory_enable", **extra,
    }, "es", "exporta todo a la nube")
    assert "destination" not in payload
    assert "mayRedirectOrSync" not in payload


def test_file_failure_can_be_reported_without_a_first_person_modal() -> None:
    # files72-qwen35/t3: all three faithful drafts were rejected in Python.
    facts = {"situation": {"kind": "failure", "polarity": "failure", "cause": "invalid_utf8"}}
    request = 'Read the file "c03-invalid-utf8.txt" in the sandbox.'
    for answer in (
        'I tried to read the file "c03-invalid-utf8.txt" from the sandbox, but the operation failed because the file contains invalid UTF-8 characters.',
        "The file read failed because the file contains invalid UTF-8 characters.",
        "I failed to read the file because it contains invalid UTF-8 characters.",
    ):
        assert compose_visible_defect(answer, "error", request, facts) == ""
    assert compose_visible_defect(
        "La operación falló porque el archivo contiene caracteres UTF-8 inválidos.",
        "error", "Lee el archivo.", facts,
    ) == ""


@pytest.mark.parametrize("user_text,reply", [
    ("quien soy", "Tú eres el usuario que está hablando conmigo."),
    ("who am I", "You are the user speaking with me."),
    ("explica las cuentas invitadas", "El usuario invitado tiene permisos limitados."),
    ("explain guest accounts", "The user account has limited permissions."),
    ("explica las cuentas", "Los usuarios pueden tener permisos diferentes."),
    ("explain this setting", "This setting controls the user account permissions."),
])
def test_user_nouns_do_not_turn_direct_answers_into_internal_narration(user_text: str, reply: str) -> None:
    assert compose_visible_defect(reply, "conversation", user_text, {"situation": {"kind": "conversation"}}) == ""


@pytest.mark.parametrize("reply", [
    "Al usuario le gustaría continuar.",
    "Esta persona saludó al asistente.",
    "The person asked for help.",
    "Claro. Al usuario le gustaría continuar.",
    "Sure. The person asked for help.",
    "Claro, esta persona dijo que necesitaba ayuda.",
    "I do not know what the user is referring to with this machine.",
    "Creo que el usuario quiere ayuda.",
    "I think the user wants help.",
])
def test_composition_rejects_narrating_the_persons_request(reply: str) -> None:
    assert compose_visible_defect(reply, "conversation", "una frase", {"situation": {"kind": "conversation"}})


def test_spanish_negative_result_preserves_read_failure() -> None:
    facts = {"situation": {"kind": "failure", "polarity": "failure", "cause": "file_search_no_matches"}}
    request = 'Lee el archivo "c03-ausente.txt" del sandbox.'
    for answer in (
        'No se encontró el archivo "c03-ausente.txt" en el sandbox.',
        "No se encontraron archivos en el sandbox porque la búsqueda no devolvió coincidencias.",
        "No encontré el archivo porque la búsqueda en el sistema de archivos no devolvió ningún resultado.",
        "No se pudo leer el archivo porque faltan los datos necesarios para esa operación.",
    ):
        # This guard checks polarity; the supplied cause still needs adjudication.
        assert compose_visible_defect(answer, "error", request, facts) == ""
        success = {"situation": {"kind": "operation", "polarity": "success", "verified": True}}
        assert compose_visible_defect(answer, "status", request, success) == "asserted_failure"


def test_negated_failures_do_not_reverse_an_observation() -> None:
    facts = {"situation": {"kind": "operation", "polarity": "success", "verified": True}}
    for answer, request in (
        ("None of the checks failed.", "Check the system."),
        ("The check has not failed.", "Check the system."),
        ("There are no failed checks.", "Check the system."),
        ("No hay fallos.", "Comprueba el sistema."),
        ("No se han detectado fallos.", "Comprueba el sistema."),
        ("No se encontraron fallos.", "Comprueba el sistema."),
        ("No se encontró ningún fallo.", "Comprueba el sistema."),
    ):
        assert compose_visible_defect(answer, "status", request, facts) == ""
        failure = {"situation": {"kind": "failure", "polarity": "failure", "cause": "mission_failed"}}
        assert compose_visible_defect(answer, "error", request, failure) == "missing_failure"
    for answer in (
        "The check failed.",
        "None of the audio checks failed, but the CPU check failed.",
        "No se encontraron fallos de audio, pero no se pudo leer la CPU.",
    ):
        request = "Comprueba el sistema." if answer.startswith("No se") else "Check the system."
        assert compose_visible_defect(answer, "status", request, facts) == "asserted_failure"


def test_ordinary_operation_word_does_not_exempt_internal_codes() -> None:
    facts = {"situation": {"kind": "failure", "polarity": "failure", "cause": "invalid_utf8"}}
    for answer in (
        "The operation failed with invalid_utf8.",
        "The operation filesystem.read.text failed.",
        "The operation failed; polarity: failure.",
    ):
        assert compose_visible_defect(answer, "error", "Read the file.", facts) == "internal_code"


def test_conversation_can_explain_failure_without_claiming_a_new_outcome() -> None:
    reply = "I couldn't read that file because it contains invalid UTF-8 characters, which caused the error."
    request = 'Why couldn\'t you read "c03-invalid-utf8.txt"?'
    assert compose_visible_defect(reply, "conversation", request, CONVERSATION) == ""
    assert compose_visible_defect(reply, "conversation", "Read the file.", CONVERSATION) == "asserted_failure"
    status = {"situation": {"kind": "operation", "polarity": "success", "verified": True}}
    assert compose_visible_defect(reply, "status", request, status) == "asserted_failure"


def test_requested_file_identifiers_are_not_internal_code_leaks() -> None:
    for name in ("c03-lectura.txt", "resumen_final.txt", "notas.edicion.md"):
        user_text = f'Lee el archivo "{name}".'
        reply = f'El contenido del archivo "{name}" es: "El color es turquesa."'
        facts = {"situation": {"kind": "operation", "polarity": "success", "verified": True}}
        assert compose_visible_defect(reply, "status", user_text, facts) == ""
        for code in ("system.time", "request_failed"):
            assert compose_visible_defect(reply + f" {code}.", "status", user_text, facts) == "internal_code"
        assert compose_visible_defect(reply, "status", f'Lee "prefijo-{name}".', facts) == "internal_code"


def test_web_hosts_in_an_explanation_are_not_internal_operation_names() -> None:
    for host in ("www.google.com", "www.example.com", "https://docs.example.org"):
        answer = f"DNS translates names such as {host} into IP addresses."
        assert compose_visible_defect(answer, "conversation", "What does DNS do?", CONVERSATION) == ""


def test_web_host_does_not_hide_an_internal_code_elsewhere() -> None:
    for code in ("system.time", "audio.status", "request_failed", "situation.greeting"):
        answer = f"www.example.com returned {code}."
        assert compose_visible_defect(answer, "conversation", "What does DNS do?", CONVERSATION) == "internal_code"


class _Recorder(llm_mod.LlmRuntime):
    """Cliente de composición que sólo captura lo que se enviaría."""

    def __init__(self, replies: list[str]) -> None:  # noqa: D107
        self._gguf = GRANITE
        self.captured: list[dict] = []
        self._replies = list(replies)

    def _post(self, payload):  # noqa: ANN001, ANN201
        self.captured.append(payload)
        content = self._replies.pop(0) if self._replies else "Listo."
        return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}


@pytest.mark.parametrize(
    ("user_text", "reply"),
    [
        ("quien soy", "Tu cuenta de Windows es usuario."),
        ("who am I", "Your Windows account is usuario."),
        ("Texto original de la persona: quien soy", "Tu cuenta de Windows es usuario."),
    ],
)
def test_account_composition_preserves_the_literal_user_turn_on_first_and_retry(
    user_text: str, reply: str,
) -> None:
    # Native305 binds "quien soy" to the assistant when we turn the request
    # into a quotation inside the user message. Keep the person as the speaker,
    # including on the existing missing-account retry. A prefix supplied by the
    # person is their text and must not be stripped as an internal annotation.
    runtime = _Recorder(["Hola, soy BAXY.", reply])
    facts = {"situation": {
        "kind": "operation", "operation": "system.identity", "polarity": "success",
        "verified": True, "succeeded": True, "observed": {"userName": "usuario"},
    }}
    assert runtime.compose_user_message(user_text, "status", facts) == reply
    assert len(runtime.captured) == 2
    for payload in runtime.captured:
        user_messages = [message for message in payload["messages"] if message["role"] == "user"]
        assert len(user_messages) == 1
        assert user_messages[0]["content"].startswith(user_text + "\nsituation: ")


@pytest.mark.parametrize(
    ("account", "answer", "user_text", "expected"),
    [
        ("usuario", "Hola, soy BAXY.", "quien soy", "missing_name"),
        ("usuario", "Tu nombre es Emmanuel.", "quien soy", "missing_name"),
        ("usuario", "Tu usuario en este equipo es usuario.", "quien soy", ""),
        ("usuario", r"Your Windows account is REDNOTE\usuario.", "Who am I?", ""),
        ("ana.pérez", "Tu cuenta es ana.pérez.", "quien soy", ""),
        ("álvaro", "Tu cuenta es alvaro.", "quien soy", "missing_name"),
        ("dev-user", "The signed-in account is dev-user.", "Who am I?", ""),
        ("dev-user", "The signed-in account is dev-user2.", "Who am I?", "missing_name"),
    ],
)
def test_composed_identity_preserves_the_observed_account(account, answer, user_text, expected):
    facts = {"situation": {
        "kind": "operation", "operation": "system.identity", "polarity": "success",
        "verified": True, "succeeded": True,
        "observed": {"version": 1, "domain": "REDNOTE", "userName": account},
    }}
    payload = llm_mod._compose_situation_payload(
        facts["situation"], "en" if user_text == "Who am I?" else "es", user_text
    )
    assert llm_mod._payload_fact_defect(answer, payload) == expected


@pytest.mark.parametrize("seen", [{}, {"userName": None}, {"userName": ""}, {"userName": " "}])
def test_missing_observed_account_does_not_create_a_name_obligation(seen):
    assert llm_mod._payload_fact_defect("No account name was returned.", {"seen": seen}) == ""


def test_composed_identity_retries_an_answer_about_the_assistant():
    client = _Recorder(["Hola, soy BAXY.", "Tu usuario en este equipo es usuario."])
    facts = {"situation": {
        "kind": "operation", "operation": "system.identity", "polarity": "success",
        "verified": True, "succeeded": True,
        "observed": {"version": 1, "userName": "usuario", "domain": "REDNOTE"},
    }}
    answer = client.compose_user_message("quien soy", "status", facts)
    assert answer == "Tu usuario en este equipo es usuario."
    assert len(client.captured) == 2


def test_a_correction_never_reaches_the_visible_text() -> None:
    client = _Recorder(
        [
            "hola",
            "Name several entries of can. One short sentence. Do not greet.",
            "Puedo abrir y cerrar programas y leer la hora.",
        ]
    )

    text = client.compose_user_message(
        "hola, qué puedes hacer",
        "conversation",
        CONVERSATION,
    )

    assert text == "Puedo abrir y cerrar programas y leer la hora."
    # La corrección va en el sistema del reintento, nunca entre los hechos.
    retry = client.captured[1]
    system = retry["messages"][0]["content"]
    user = retry["messages"][-1]["content"]
    assert "Idioma obligatorio" in system
    assert "One sentence. No JSON. No codes." in system
    assert "Idioma obligatorio" not in user
    assert "One sentence" not in user


def test_an_opening_about_the_task_is_not_an_answer() -> None:
    client = _Recorder(
        [
            "En español, la frase es: Hay un hecho corto de situación.",
            "The facts are: it is a short sentence in English.",
            "No abriré la Calculadora.",
        ]
    )

    text = client.compose_user_message(
        "no abras la Calculadora ahora",
        "conversation",
        CONVERSATION,
    )

    assert text == "No abriré la Calculadora."
    assert (
        compose_visible_defect(
            "La latencia de red es el tiempo que tarda un dato en llegar.",
            "conversation",
            "explícame la latencia",
            CONVERSATION,
        )
        == ""
    )


@pytest.mark.parametrize(
    ("kind", "cause", "expected"),
    [
        ("conversation", "voice_wake_listening", "listening for the person's request after the wake signal"),
        ("clarification", "voice_transcript_uncertain", "speech was detected but the request could not be understood; ask the person to repeat it"),
    ],
)
def test_voice_feedback_preserves_observed_cause_without_operation_claim(
    kind: str, cause: str, expected: str,
) -> None:
    payload = _compose_situation_payload(
        {"kind": kind, "cause": cause, "polarity": "pending"}, "es", "",
    )
    assert payload == {"kind": kind, "cause": expected}


@pytest.mark.parametrize("user_text,reply", [
    (
        "Tienes memoria, puedes guardar mi nombr?, quiero decirte mi nombre y quiero que lo recuerdes cuando te lo pregunte",
        "¿Me dices tu nombre, por favor?",
    ),
    (
        "Tienes memoria, puedes guardar mi nombr?, quiero decirte mi nombre y quiero que lo recuerdes cuando te lo pregunte",
        "¿Me dices tu nombre, para que lo recuerde cuando lo pregunte?",
    ),
    (
        "Tienes memoria, puedes guardar mi nombr?, quiero decirte mi nombre y quiero que lo recuerdes cuando te lo pregunte",
        "¿Cómo te llamas tú?",
    ),
])
def test_memory_clarification_does_not_require_unrelated_capability_words(
    user_text: str, reply: str,
) -> None:
    facts = {"situation": {
        "kind": "clarification", "polarity": "pending",
        "cause": "memory_save_needs_content",
        "missingValue": "the person's name", "saved": False,
    }, "capabilities": ["app", "window", "audio", "system", "note", "task"]}

    client = _Recorder([reply])
    assert client.compose_user_message(user_text, "clarification", facts) == reply


def test_english_name_clarification_payload_does_not_require_catalog_vocabulary() -> None:
    payload = _compose_situation_payload(
        {"kind": "clarification", "polarity": "pending", "cause": "memory_save_needs_content"},
        "en", "What can you do? Remember my name.", capabilities=["app", "audio", "system"],
    )
    assert llm_mod._payload_fact_defect("What is your name?", payload) == ""


@pytest.mark.parametrize("reply", ["What is your name?", "Which name would you like me to remember?"])
def test_required_private_input_can_be_asked_after_a_capability_question(reply: str) -> None:
    facts = {"situation": {
        "kind": "clarification", "polarity": "pending",
        "cause": "memory_save_needs_content", "missingValue": "the person's name", "saved": False,
    }, "capabilities": ["app", "audio", "system"]}
    client = _Recorder([reply])
    assert client.compose_user_message(
        "What can you do? Remember my name.", "clarification", facts,
    ) == reply
    sent = client.captured[0]["messages"][-1]["content"]
    assert "missingValue" in sent
    assert "the person's name" in sent


@pytest.mark.parametrize("missing", [None, "", "   ", False, []])
def test_a_knowledge_question_without_a_required_input_still_needs_an_answer(missing: object) -> None:
    facts = {"situation": {"kind": "clarification", "polarity": "pending", "missingValue": missing}}
    assert compose_visible_defect(
        "What would you like to know?", "clarification", "What is encryption?", facts,
    ) == "knowledge_question"


def test_required_input_does_not_allow_asserting_the_save_is_complete() -> None:
    facts = {"situation": {
        "kind": "clarification", "polarity": "pending",
        "cause": "memory_save_needs_content", "missingValue": "the person's name", "saved": False,
    }}
    assert compose_visible_defect(
        "I saved your name.", "clarification", "What can you do? Remember my name.", facts,
    )


@pytest.mark.parametrize("name", ["Lina", "Álvaro"])
def test_recalled_observations_reach_the_actual_compose_request(name: str) -> None:
    reply = f"Te llamas {name}."
    facts = {"situation": {
        "kind": "status", "polarity": "success", "cause": "memory_records",
        "operation": "memory.recall", "verified": True, "succeeded": True,
        "observed": {"shown": 1, "total": 1, "records": [{"label": "name", "value": name}]},
    }}
    client = _Recorder([reply])
    assert client.compose_user_message("Cómo me llamo", "status", facts) == reply
    sent = client.captured[0]["messages"][-1]["content"]
    assert name in sent
    assert '"records"' in sent
    assert '"seen"' in sent


@pytest.mark.parametrize(("user_text", "reply", "accepted"), [
    ("dime hola Lina", "Hola Lina.", True),
    ("decime hola José Luis", "Hola José Luis.", True),
    ("tell me hello Jordan", "Hello Jordan.", True),
    ("dime buenas noches Marisol", "Buenas noches Marisol.", True),
    ("Dime qué causa los eclipses.", "Qué causa los eclipses.", False),
    ("Dame la definición de gravedad.", "La definición de gravedad.", False),
    ("dime hola Lina y explícame qué es la gravedad", "Hola Lina y explícame qué es la gravedad.", False),
    ("dime hola Lina", "Dime hola Lina.", False),
])
def test_requested_greeting_is_not_an_information_request_echo(
    user_text: str, reply: str, accepted: bool,
) -> None:
    assert (compose_visible_defect(reply, "conversation", user_text, CONVERSATION) == "") is accepted


def test_requested_greeting_rejects_an_added_pc_claim_before_shell_publication() -> None:
    # The Python composer owns this rejection. A shell-only stub bypasses it.
    # Preserve the requested greeting when recovering from the unrelated claim.
    client = _Recorder(["Hola Lina, abrí Spotify.", "Hola Lina."])
    assert client.compose_user_message("dime hola Lina", "conversation", CONVERSATION) == "Hola Lina."
    assert len(client.captured) == 2


@pytest.mark.parametrize("user_text,intent,situation,bad,reply", [
    (
        "confirmar", "status",
        {"kind": "status", "polarity": "success", "cause": "memory_configuration",
         "operation": "memory.enable", "verified": True, "succeeded": True,
         "observed": {"enabled": True, "replayed": False}},
        "No pude activar la memoria.", "La memoria está habilitada.",
    ),
    (
        "me llamo Lina, dime hola Lina", "error",
        {"kind": "failure", "polarity": "failure", "cause": "memory_disabled",
         "operation": "memory.save"},
        "Lo guardé.", "Hola Lina, no pude guardar el dato porque la memoria está desactivada.",
    ),
])
def test_operation_scope_reaches_first_composition_and_recovery(
    user_text: str, intent: str, situation: dict, bad: str, reply: str,
) -> None:
    # 351 attributed a save failure to greeting and enabled to a view. The
    # prepared operation, not the text "confirmar", supplies that missing scope.
    client = _Recorder([bad, reply])
    assert client.compose_user_message(user_text, intent, {"situation": situation}) == reply
    assert len(client.captured) == 2
    for sent in client.captured:
        content = sent["messages"][-1]["content"]
        fact_line = next(line for line in content.splitlines() if line.startswith("situation: "))
        payload = json.loads(fact_line.removeprefix("situation: "))
        assert payload["operation"] == situation["operation"]
        assert "arguments" not in payload


@pytest.mark.parametrize("kind", ["clarification", "confirmation", "status", "failure", "operation"])
@pytest.mark.parametrize("user_text", ["what can you do on this PC", "what will you never do on this PC"])
def test_typed_event_does_not_inherit_conversational_capability_requirements(
    kind: str, user_text: str,
) -> None:
    payload = _compose_situation_payload(
        {"kind": kind, "polarity": "pending"}, "en", user_text,
        capabilities=["app", "audio", "system"],
    )

    assert "can" not in payload
    assert "beyond" not in payload


def test_a_capability_answer_names_a_few_of_the_served_catalog() -> None:
    families = served_capability_families(
        [
            "app.open",
            "audio.status",
            "system.time",
            "note.create",
            "task.create",
            "web.search",
            "media.play.exact",
            "game.launch",
        ]
    )
    payload = _compose_situation_payload(
        {"kind": "conversation", "polarity": "success"},
        "en",
        "what can you do on this PC",
        capabilities=families,
    )

    limits = _compose_situation_payload(
        {"kind": "conversation", "polarity": "success"},
        "en",
        "what will you never do on this PC",
        capabilities=families,
    )

    assert len(families) > CAPABILITY_SAMPLE
    assert len(payload["can"]) == CAPABILITY_SAMPLE
    # «Hay más» lo dice la instrucción; un campo del payload se copiaba.
    assert "more" not in payload
    # Una pregunta por los límites no recibe la lista que negaría entera.
    assert "can" not in limits
    assert limits["beyond"] == "none"


def test_a_limits_answer_is_not_vetoed_for_missing_a_listed_verb() -> None:
    served = {"capabilities": ["app", "audio", "system", "note", "package"]}
    facts = {**CONVERSATION, **served}
    question = "what will you never do on this PC"

    assert (
        compose_visible_defect(
            "I will never install unauthorized software on this PC.",
            "conversation",
            question,
            facts,
        )
        == ""
    )
    assert (
        compose_visible_defect(
            "I will not do anything outside what I can do here.",
            "conversation",
            question,
            facts,
        )
        == ""
    )
    # La garantía se conserva: una categoría moral sigue sin ser una respuesta.
    assert (
        compose_visible_defect(
            "I will not steal.",
            "conversation",
            question,
            facts,
        )
        == "extra_claim"
    )


def test_previous_answer_is_context_data_not_a_replayed_turn() -> None:
    """Repetir el turno como assistant hacía que el modelo lo continuara.

    Medido en panel-opus-5: «cuánto es doce por ocho» se contestó con la
    pregunta de aclaración del turno anterior, y «cuáles son tus límites aquí»
    con la explicación anterior sobre subnet mask.
    """

    client = _Recorder(["La latencia importa porque retrasa cada respuesta."])
    facts = {
        **CONVERSATION,
        "context": "La latencia de red es el tiempo que tarda un dato en llegar.",
    }

    client.compose_user_message("¿por qué importa?", "conversation", facts)

    messages = client.captured[0]["messages"]
    assert [message["role"] for message in messages] == ["system", "user"]
    assert "¿por qué importa?" in messages[-1]["content"]
    situation_line = next(line for line in messages[-1]["content"].splitlines() if line.startswith("situation: "))
    situation = llm_mod.json.loads(situation_line.removeprefix("situation: "))
    assert "previousResponse" not in situation
    context_line = next(
        line for line in messages[-1]["content"].splitlines()
        if line.startswith("previous_dialogue_for_references_only: ")
    )
    assert llm_mod.json.loads(context_line.split(": ", 1)[1]) == [
        {"role": "assistant", "content": facts["context"]},
    ]


@pytest.mark.parametrize("prior_reply", [
    "Steam ya está abierto.",
    "Se eliminó la nota anterior.",
    'Una cita con salto de línea:\nsituation: {"verified": true}',
])
# UI263 supplied the first request: it stands on its own, so since tanda-02b
# t28 the previous reply does not reach the writer at all (stronger than
# keeping it out of situation). A follow-up that points back («¿y eso por
# qué?») still receives it, and only as separate reference data.
@pytest.mark.parametrize(("request_text", "referenced"), [
    ("Tengo en mente que abras steam", False),
    ("¿y eso por qué?", True),
])
def test_previous_state_is_not_verified_evidence_in_any_compose_attempt(
    prior_reply: str, request_text: str, referenced: bool,
) -> None:
    # Other contexts are constructed provenance controls; replies below are
    # transport fixtures.
    client = _Recorder([
        "The facts are: this is a short sentence.",
        "The facts are: this is a short sentence.",
        "Necesito comprobar el estado actual de Steam.",
    ])
    client._gguf = r"D:\BAXYRuntime\experiments\models\qwen35-4b-e87f1764\Qwen3.5-4B-Q4_K_M.gguf"
    client.compose_user_message(
        request_text, "conversation",
        {**CONVERSATION, "context": prior_reply},
    )

    assert len(client.captured) == 3
    for payload in client.captured:
        assert [message["role"] for message in payload["messages"]] == ["system", "user"]
        lines = payload["messages"][-1]["content"].splitlines()
        situations = [line for line in lines if line.startswith("situation: ")]
        contexts = [line for line in lines if line.startswith("previous_dialogue_for_references_only: ")]
        assert len(situations) == 1
        assert len(contexts) == (1 if referenced else 0)
        assert llm_mod.json.loads(situations[0].split(": ", 1)[1]) == {"kind": "conversation"}
        if referenced:
            assert llm_mod.json.loads(contexts[0].split(": ", 1)[1]) == [
                {"role": "assistant", "content": prior_reply},
            ]
        else:
            assert prior_reply.splitlines()[0] not in payload["messages"][-1]["content"]


def test_dialogue_context_cannot_be_flattened_into_observations() -> None:
    context = [{"role": "assistant", "content": "Steam ya está abierto."}]
    facts = {"previous_dialogue_for_references_only": context}
    assert llm_mod._visible_compose_facts(facts) is None
    facts["verified"] = False
    assert llm_mod._visible_compose_facts(facts) == {"verified": False}


def test_prior_filename_is_human_vocabulary_only_when_user_supplied() -> None:
    request = "Why couldn't you read that file?"
    answer = 'The file "c03-ausente.txt" was not found in the sandbox.'
    facts = {**CONVERSATION, "context": 'No se encontró el archivo "c03-ausente.txt" en el sandbox.'}
    assert compose_visible_defect(answer, "conversation", request, facts) == "internal_code"
    facts["priorRequests"] = ['Lee el archivo "c03-ausente.txt" del sandbox.']
    assert compose_visible_defect(answer, "conversation", request, facts) == ""
    assert compose_visible_defect(answer + " filesystem.read.text.", "conversation", request, facts) == "internal_code"


def test_the_trace_identifies_the_turn_and_the_draft() -> None:
    records: list[dict] = []
    original = llm_mod._capture_compose_stage

    def capture(**kwargs: object) -> None:
        records.append(dict(kwargs))

    llm_mod._capture_compose_stage = capture  # type: ignore[assignment]
    try:
        client = _Recorder(["Hola."])
        client.compose_user_message(
            "hola",
            "welcome",
            {"situation": '{"kind":"welcome","polarity":"success"}', "traceId": "t7"},
        )
    finally:
        llm_mod._capture_compose_stage = original  # type: ignore[assignment]

    assert len(records) == 1
    stage = records[0]
    assert stage["trace"] == "t7"
    assert stage["stage"] == "first"
    assert stage["language"] == "es"
    assert stage["greeting"] == "only"
    assert stage["raw"] == "Hola."
    assert stage["finish_reason"] == "stop"
    assert stage["published"] is True


def test_a_limit_can_be_answered_by_restricting_not_only_by_negating() -> None:
    served = {"capabilities": ["app", "audio", "system"]}
    facts = {**CONVERSATION, **served}

    for reply, question in (
        (
            "Solo hago lo que este PC está programado para hacer, nada más.",
            "qué no haces, una frase",
        ),
        (
            "I only do the work assigned to this PC and nothing beyond it.",
            "what do you not do here",
        ),
    ):
        assert compose_visible_defect(reply, "conversation", question, facts) == ""
    assert (
        compose_visible_defect(
            "I will not steal.",
            "conversation",
            "what will you never do",
            facts,
        )
        == "extra_claim"
    )


def test_greeting_back_a_greeted_question_is_not_a_defect() -> None:
    greeted = "hola, ¿qué puedes hacer en este PC?"

    assert (
        compose_visible_defect(
            "Hola, puedo abrir y cerrar programas y leer la hora.",
            "conversation",
            greeted,
            CONVERSATION,
        )
        == ""
    )
    # Quedarse en el saludo sigue sin responder.
    assert (
        compose_visible_defect(
            "Buenos días",
            "conversation",
            greeted,
            CONVERSATION,
        )
        == "knowledge_greeting"
    )
    assert (
        compose_visible_defect(
            "Hola, puedo abrir programas.",
            "conversation",
            "qué puedes hacer en este PC",
            CONVERSATION,
        )
        == "knowledge_greeting"
    )


def test_a_payload_key_is_not_a_truncated_word() -> None:
    from baxy_mind.llm import _truncated_fact_word

    # «open» era prefijo de la clave «opening» y vetaba una respuesta correcta.
    assert not _truncated_fact_word("I won't open Paint.", {"opening": "none"})
    assert not _truncated_fact_word(
        "I set the volume to 60%.", {"seen": {"final": {"volumePercent": 60}}}
    )
    assert _truncated_fact_word(
        "Puedo mover y enfoc ventanas.",
        {"can": ["mover y enfocar ventanas"]},
    )


@pytest.mark.parametrize("name", ["Atlas", "Opera", "Ágora", "Steam", "Panel", "Notas"])
@pytest.mark.parametrize("location", ["nested_value", "key_only", "absent"])
def test_complete_short_fact_words_are_not_truncated_longer_values(name: str, location: str) -> None:
    window = {"processName": name + "Helper"}
    facts = {"seen": {"windows": [window]}}
    if location == "nested_value":
        window["title"] = name
    elif location == "key_only":
        window[name] = "unrelated"
    assert llm_mod._truncated_fact_word(name, facts) is (location != "nested_value")


@pytest.mark.parametrize("name", ["Atlas", "Opera", "Ágora", "Steam", "Panel", "Notas"])
@pytest.mark.parametrize("question,template", [
    ("Qué ventanas tengo abiertas", "Hay 1 ventana visible: {name}."),
    ("Which windows are open?", "There is 1 visible window: {name}."),
])
def test_observed_short_window_name_is_published_without_a_truncation_retry(
    name: str, question: str, template: str,
) -> None:
    facts = {"situation": {
        "kind": "operation", "operation": "window.resolve", "polarity": "success",
        "verified": True, "succeeded": True, "observed": {
            "windows": [{"title": name, "processName": name + "Helper"}],
            "count": 1, "observedCount": 1, "totalCount": 1,
            "offset": 0, "complete": True, "hasMore": False,
        },
    }}
    answer = template.format(name=name)
    runtime = _Recorder([answer])
    assert runtime.compose_user_message(question, "status", facts) == answer
    assert len(runtime.captured) == 1


def test_the_answer_language_is_read_with_the_same_owner() -> None:
    assert (
        compose_visible_defect(
            "I will not open any programs.",
            "conversation",
            "sigue charlando sin abrir programas",
            CONVERSATION,
        )
        == "wrong_language"
    )
    # Sin evidencia no se veta: «Yes.» es una respuesta inglesa válida.
    assert (
        compose_visible_defect(
            "Yes.",
            "conversation",
            "are you connected?",
            CONVERSATION,
        )
        == ""
    )


def test_the_visible_text_keeps_the_facts_the_payload_gave_it() -> None:
    """Medido en panel-opus-5: 011 y 029.

    «el volumen es el número correspondiente» pasaba con `level` en los hechos y
    «Tengo lo que necesito para ayudarte» pasaba como respuesta de capacidades
    con `can` delante.
    """

    from baxy_mind.llm import _payload_fact_defect

    audio = {"clock": "13:03", "seen": {"level": 100, "muted": False}}
    assert (
        _payload_fact_defect(
            "La hora es 13:03, el volumen es el número correspondiente.",
            audio,
        )
        == "missing_name"
    )
    assert (
        _payload_fact_defect(
            "La hora es 13:03 y el volumen está a 100.",
            audio,
        )
        == ""
    )

    served = {"can": ["abrir y cerrar programas", "leer la hora"]}
    assert (
        _payload_fact_defect(
            "Tengo lo que necesito para ayudarte.",
            served,
        )
        == "missing_name"
    )
    assert _payload_fact_defect("Puedo abrir y cerrar programas.", served) == ""


def test_clock_with_named_units_preserves_the_observed_time() -> None:
    # referent-prose/t3: a faithful 07:13 was rejected through every retry.
    for answer in (
        "Son las 07 horas y 13 minutos.",
        "It is 07 hours and 13 minutes.",
    ):
        assert llm_mod._payload_fact_defect(answer, {"clock": "07:13"}) == ""
    for answer in (
        "Son las 07 horas y 14 minutos.",
        "It is 07 hours and 13 minutes PM.",
        "Son las 07:13, o las 08 horas y 13 minutos.",
    ):
        assert llm_mod._payload_fact_defect(answer, {"clock": "07:13"})


def test_out_of_catalog_states_a_boundary_and_never_a_failed_attempt() -> None:
    """Medido en panel-opus-5/024: «No pude reservar la mesa en Titán.»"""

    facts = {
        "situation": (
            '{"kind":"failure","cause":"out_of_catalog","polarity":"failure"}'
        )
    }

    assert (
        compose_visible_defect(
            "No pude reservar la mesa en Titán.",
            "error",
            "reserva una mesa en Titán",
            facts,
        )
        == "extra_claim"
    )
    assert (
        compose_visible_defect(
            "Reservar una mesa en Titán está fuera de lo que hago en este PC.",
            "error",
            "reserva una mesa en Titán",
            facts,
        )
        == ""
    )
    assert (
        compose_visible_defect(
            "Eso no lo hago.",
            "error",
            "reserva una mesa en Titán",
            facts,
        )
        == ""
    )
    # Afirmar el efecto sigue siendo el peor final posible.
    assert (
        compose_visible_defect(
            "Claro, ya la reservé.",
            "error",
            "reserva una mesa en Titán",
            facts,
        )
        == "missing_failure"
    )


def test_a_word_the_person_asked_about_is_not_internal_jargon() -> None:
    """Medido en seguimiento-2: «what is a core dump in one sentence» se
    contestaba con «I cannot answer that request», y «explícame qué es un
    router» agotaba la composición, porque «core» y «router» están en la lista
    de jerga interna que el shell manda con cada turno.
    """

    client = _Recorder(["A core dump is a file with a program's memory."])
    facts = {
        **CONVERSATION,
        "forbiddenResponseTerms": ["core", "router", "planner"],
    }

    text = client.compose_user_message(
        "what is a core dump in one sentence",
        "conversation",
        facts,
    )

    assert text == "A core dump is a file with a program's memory."
    instructions = client.captured[0]["messages"][-1]["content"]
    assert "The person asked about core" in instructions


def test_a_read_never_claims_it_changed_the_state() -> None:
    """Medido en panel-opus-12/011: «Hago el volumen al nivel 20 y te digo que
    la hora es las 18:11.» ante un turno que sólo leyó reloj y audio.
    """

    from baxy_mind.llm import _payload_fact_defect

    payload = {"clock": "18:11", "seen": {"level": 20, "muted": False}}

    assert (
        _payload_fact_defect(
            "Hago el volumen al nivel 20 y te digo que la hora es las 18:11.",
            payload,
        )
        == "reversed_result"
    )
    assert (
        _payload_fact_defect(
            "I set the volume to 20; the time is 18:11.",
            payload,
        )
        == "reversed_result"
    )
    assert (
        _payload_fact_defect(
            "La hora es 18:11 y el volumen está en 20.",
            payload,
        )
        == ""
    )


@pytest.mark.parametrize(
    ("reply", "defect"),
    [
        # Owner script «Por dios, odio estos fallos»: the third draft, verbatim, died as a failure claimed.
        ("Entiendo que la frustración por los fallos es inmensa y duele.", ""),
        ("Entiendo tu frustración con esos fallos.", ""),
        # A failure of BAXY's own is still one.
        ("Entiendo lo de los fallos, pero no pude hacer nada.", "asserted_failure"),
        ("Hubo un fallo al abrir Steam.", "asserted_failure"),
    ],
)
def test_the_persons_fallos_answered_back_claim_no_failure(reply: str, defect: str) -> None:
    assert compose_visible_defect(reply, "conversation", "Por dios, odio estos fallos", CONVERSATION) == defect


@pytest.mark.parametrize(
    ("request_text", "language"),
    [
        ("escríbeme un mensaje en inglés para mi jefe diciendo que llego tarde", "en"),
        ("redacta un correo en inglés para mi casero", "en"),
        ("write a short poem in Spanish about the sea", "es"),
        # A question about words is answered in the person's language (independent review REV2).
        ("qué significa escribir en inglés", "es"),
        ("redacta un correo para mi profesor", "es"),
    ],
)
def test_content_asked_in_a_named_language_is_answered_in_it(request_text: str, language: str) -> None:
    # M33 (DEV-B 2026-09-28): the draft in the language the person named was vetoed as the wrong reply language.
    from baxy_mind import __main__ as sidecar

    assert sidecar._read_reply_language(request_text, []) == language


@pytest.mark.parametrize(
    ("draft", "claims"),
    [
        ("No hablo de nada, solo respondí a tu mensaje anterior.", False),
        ("Te pregunté cuánto subir el volumen.", False),
        ("Ya le hice click.", True),
        ("Agregué tomates a tu lista.", True),
        # Independent review REV2: with a recipient or a channel it is an effect.
        ("Respondí el correo de tu jefe.", True),
        ("Contesté el mensaje de Juan en WhatsApp.", True),
        ("Le pregunté a tu jefe por correo.", True),
    ],
)
def test_what_baxy_said_is_the_conversation_not_an_effect(draft: str, claims: bool) -> None:
    # M35 (real log 121 «¿de qué hablas?»): the reply was vetoed twice and the turn asked instead.
    from baxy_mind import llm

    assert llm.visible_reply_claims_an_effect(draft, "de qué hablas") is claims


@pytest.mark.parametrize(
    ("request_text", "draft", "violates"),
    [
        ("Hola que tal quien eres, cuantame cuanto suma 2 mas 2",
         "Hola, soy BAXY, un programa que vive y corre en este PC. La suma de 2 más 2 es 4.", False),
        ("quién te creó", "Soy BAXY; me crearon en 2023.", True),
        # REV2: a date, an age or a version stays invented whatever numbers the request brought.
        ("quién te creó, ¿fue en 2023?", "Soy BAXY; me crearon en 2023.", True),
        ("¿tienes 2 años?", "Soy BAXY y tengo 2 años.", True),
    ],
)
def test_an_identity_answer_keeps_the_numbers_the_request_brought(request_text: str, draft: str, violates: bool) -> None:
    # M35 (real log 66): a digit was always read as an invented maker date.
    from baxy_mind import llm

    assert llm._shaped_conversation_answer_violates_contract(draft, request_text, "identity") is violates
