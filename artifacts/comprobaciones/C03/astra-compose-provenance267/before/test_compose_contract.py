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
    assert llm_mod.json.loads(situation_line.removeprefix("situation: "))["previousResponse"] == facts["context"]


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
