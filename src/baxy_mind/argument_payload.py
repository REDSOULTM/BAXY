"""The closed one-call extraction of arguments: its payload (BAXY's previous reply when that is the value),
the validation of a missing-argument clarification and the fields a question may ask the person.
"""

from __future__ import annotations

import copy
import functools
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .planner import fixed_arguments, validate_json_schema_instance
from .request_intents import _message_response_language
from .clarification_style import _CLARIFICATION_LANGUAGE


_TURN_ARGUMENT_FIELD = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,127}$")
_CLARIFICATION_OPERATION = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)+$")
class ArgumentGroundingAbstention(ValueError):
    """The model explicitly reported that required arguments are unsupported."""


@dataclass(frozen=True)
class DirectArgumentExtraction:
    """One inference result with deterministic literal provenance and fallback."""

    arguments: dict[str, Any] | None
    evidence: tuple[tuple[str, str], ...]
    fallback_question: str
    # M67: the field the model said takes BAXY's previous reply, copied there by code; "" when none did.
    previous_reply_field: str = ""


# M67 (FINAL F-w14-t3, F-w15-t4): a field whose declared size holds a text of its own (clipboard text, a note's
# content, a message body, a task's details), not a name, a query or a path; only such a field may take a reply.
_REPLY_CONTENT_MIN_SIZE = 4096
_REPLY_PROMPT_CHARACTERS = 1500


def _previous_reply_fields(
    schema: dict[str, Any], open_string_fields: tuple[str, ...], reply: str,
) -> tuple[str, ...]:
    """M67: the open-text fields of ``schema`` that can hold BAXY's whole previous ``reply``."""

    properties = schema.get("properties") if isinstance(schema, dict) else None
    if not isinstance(properties, dict) or not reply.strip():
        return ()
    fields = []
    for field in open_string_fields:
        contract = properties.get(field)
        if not isinstance(contract, dict):
            continue
        sizes = [contract[key] for key in ("maxLength", "x-maxUtf8Bytes") if isinstance(contract.get(key), int)]
        if (
            sizes
            and min(sizes) >= _REPLY_CONTENT_MIN_SIZE
            and len(reply) <= contract.get("maxLength", len(reply))
            and len(reply.encode("utf-8")) <= contract.get("x-maxUtf8Bytes", len(reply.encode("utf-8")))
        ):
            fields.append(field)
    return tuple(fields)


def _single_fenced_code(reply: str) -> str | None:
    """M67: the code inside the one ``` block of BAXY's reply, without its fences and language tag; None otherwise.

    «copy the query» after a reply with prose around a ```sql block copies the query, not the prose or the fences.
    With two blocks or none there is no single code to copy, and the reply goes whole or not at all.
    """

    lines = reply.splitlines()
    fences = [index for index, line in enumerate(lines) if line.strip().startswith("```")]
    if len(fences) != 2:
        return None
    code = "\n".join(lines[fences[0] + 1:fences[1]]).strip("\n")
    return code if code.strip() else None


def _with_previous_reply(
    arguments: object,
    schema: dict[str, Any],
    field: str,
    content: str,
    evidence_text: str,
    open_string_fields: tuple[str, ...],
) -> DirectArgumentExtraction:
    """M67: ``content`` (BAXY's reply, verbatim) in ``field``, beside the other values the model read.

    Another open string is kept only when it is a literal of the request or of the reply (``evidence_text``); a
    value that does not fit its contract is left out, and so is a required one nobody said, which the caller asks
    alone: the same-call fallback asked for every field, the content too, so it is not used.
    """

    properties = schema.get("properties") if isinstance(schema, dict) else {}
    kept: dict[str, Any] = {}
    evidence: list[tuple[str, str]] = []
    for name, value in (arguments.items() if isinstance(arguments, dict) else ()):
        contract = properties.get(name) if isinstance(properties, dict) else None
        if name == field or not isinstance(contract, dict):
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if name in open_string_fields and (not isinstance(value, str) or value not in evidence_text):
            continue
        single = {"type": "object", "properties": {name: contract}, "required": [name], "additionalProperties": False}
        if not validate_json_schema_instance({name: value}, single):
            continue
        kept[name] = value
        if name in open_string_fields:
            evidence.append((name, value))
    kept[field] = content
    evidence.append((field, content))
    return DirectArgumentExtraction(kept, tuple(evidence), "", field)


def _build_direct_argument_payload(
    *,
    text: str,
    canonical_name: str,
    description: str,
    schema: dict[str, Any],
    required_fields: tuple[str, ...],
    open_string_fields: tuple[str, ...],
    response_language: str | None = None,
    previous_reply: str | None = None,
    previous_reply_fields: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Build the closed one-call extraction contract without runtime effects.

    ``response_language`` is the turn's decided language (M47): the objective
    may be the decider's restatement in the other language, so the fallback
    question is bound to the person's language explicitly when it is known.

    ``previous_reply`` with ``previous_reply_fields`` (M67, FINAL F-w14-t3 «perfect, copialo al clipboard» after a
    ```sql answer was asked «¿Qué texto quieres copiar?»): BAXY's last reply travels beside the request, and the
    same decode says which of those fields takes it (``previous_reply_field``) and, when the reply has one code
    block, whether only its code (``previous_reply_part``). The model never writes the reply: those fields are
    optional in ``arguments`` and code copies the reply verbatim.
    """

    arguments_schema = copy.deepcopy(schema)
    offered = bool(previous_reply and previous_reply_fields)
    if offered:
        arguments_schema["required"] = [
            field for field in arguments_schema.get("required", []) if field not in previous_reply_fields
        ]
    reply_properties: dict[str, Any] = {}
    if offered:
        reply_properties["previous_reply_field"] = {"type": "string", "enum": ["none", *previous_reply_fields]}
        if _single_fenced_code(previous_reply or "") is not None:
            reply_properties["previous_reply_part"] = {"type": "string", "enum": ["whole", "code"]}
    envelope_schema = {
        "type": "object",
        "properties": {
            # M67: decoded first, so the decision that the reply is the content comes before the arguments.
            **reply_properties,
            "grounded": {"type": "boolean"},
            "arguments": {
                "anyOf": [arguments_schema, {"type": "null"}],
            },
            "fallback_question": {
                "type": "string",
                "minLength": 1,
                "maxLength": 160,
            },
        },
        "required": [
            *reply_properties,
            "grounded",
            "arguments",
            "fallback_question",
        ],
        "additionalProperties": False,
    }
    system_message = (
        f"La operación {canonical_name} ya está elegida. "
        f"Extrae sus argumentos del pedido; propósito: "
        f"{description.split(';', 1)[0].strip()}. "
        "No inventes ni uses datos implícitos. Estos strings "
        "abiertos deben copiar una subcadena contigua exacta, "
        "sin traducir, normalizar ni crear IDs: "
        + json.dumps(
            open_string_fields,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + ". Un campo opcional que el pedido no dice se omite. "
        "Si falta un dato obligatorio ("
        + json.dumps(
            required_fields,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + ") o su mención está negada, "
        "descartada, corregida, contrapuesta o ambigua, usa "
        "grounded=false y arguments=null; si los obligatorios están explícitos, "
        "usa grounded=true. Formula fallback_question como una "
        "pregunta natural y breve para obtener estos campos: "
        + json.dumps(
            required_fields,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + (
            ". Usa el idioma del pedido, sin nombres internos, "
            if response_language not in _CLARIFICATION_LANGUAGE
            else ". " + _CLARIFICATION_LANGUAGE[response_language] + " Sin nombres internos, "
        )
        + "y termina con un solo '?'. Devuelve JSON compacto."
        # Fase 3.5b DEV «Recuérdame pagar el recibo de la luz hoy a las 5 de la tarde»: the model abstained,
        # reading dueUtc as a UTC date to compute. The literal is what it copies; the mind converts it.
        + (
            " dueUtc es la hora tal como la dijo la persona («a las 5 de la tarde», «mañana a las 9:50», "
            "«en 10 minutos»): cópiala literal; la conversión a UTC la hace el sistema. Si falta, la pregunta pide "
            "cuándo, con palabras de la persona, sin nombrar UTC, zonas horarias ni formatos."
            if "dueUtc" in schema.get("properties", {})
            else ""
        )
        + (
            " Tras el pedido va la respuesta anterior de BAXY, que no es parte del pedido. Si el pedido la toma "
            "como el contenido (copiarla, guardarla, enviarla o escribirla: «cópialo», «guarda eso como nota», «el "
            "query de antes»), previous_reply_field es el campo que la recibe y ese campo NO se escribe en "
            "arguments: el sistema copia la respuesta literal; los demás campos salen del pedido o de esa "
            "respuesta. Si el pedido trae su propio contenido o no se refiere a ella, previous_reply_field=\"none\"."
            + (
                " previous_reply_part=\"code\" si lo pedido es sólo el código de su bloque ```, \"whole\" si es "
                "la respuesta entera."
                if "previous_reply_part" in reply_properties
                else ""
            )
            if offered
            else ""
        )
    )
    user_content = (
        f"{text}\n\nRespuesta anterior de BAXY:\n{(previous_reply or '')[:_REPLY_PROMPT_CHARACTERS]}"
        if offered
        else text
    )
    return {
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_content},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "direct_grounded_arguments",
                "strict": True,
                "schema": envelope_schema,
            },
        },
        "temperature": 0.0,
        "seed": 0,
        # M67: room for a model that writes the reply into arguments anyway, instead of JSON cut mid-string; the
        # copy that goes is still the reply itself. A well-behaved decode stops long before.
        "max_tokens": 768 if offered else 192,
        "chat_template_kwargs": {"enable_thinking": False},
    }


def validate_missing_argument_clarification(
    raw: object,
    expected_fields: tuple[str, ...],
) -> str:
    """Validate the closed clarification envelope before any text is displayed."""

    if (
        not isinstance(expected_fields, tuple)
        or not 1 <= len(expected_fields) <= 64
        or len(set(expected_fields)) != len(expected_fields)
        or any(not isinstance(field, str) or not field for field in expected_fields)
    ):
        raise ValueError("campos esperados de aclaración inválidos")
    if not isinstance(raw, dict) or set(raw) != {"question", "requested_fields"}:
        raise ValueError("respuesta de aclaración con forma inválida")
    requested_fields = raw.get("requested_fields")
    if (
        not isinstance(requested_fields, list)
        or len(requested_fields) != len(expected_fields)
        or len(set(requested_fields)) != len(requested_fields)
        or set(requested_fields) != set(expected_fields)
    ):
        raise ValueError("la aclaración no cubre exactamente los campos faltantes")
    question = raw.get("question")
    if (
        not isinstance(question, str)
        or question != question.strip()
        or not 1 <= len(question) <= 512
        or "\n" in question
        or "\r" in question
        or question.count("?") != 1
        or not question.endswith("?")
        or any(
            unicodedata.category(character) in {"Cc", "Cf", "Cs"}
            for character in question
        )
    ):
        raise ValueError("la aclaración no es una única pregunta acotada")
    # M54 (v3b-final F-w05-t3): the same-call question of the argument extraction asked the date «en formato UTC»,
    # read off the field dueUtc; the person says when in their words and the mind converts them.
    return _question_opening(_question_without_time_format(question))


def _question_opening(question: str) -> str:
    """Open a model-authored question as a sentence: capital first letter, «¿» in Spanish.

    Uso real 2026-09-23 «cuándo y qué es la cita que quieres recordar?», «¿cuál
    es el título de la nota…?»: the argument questions reached the screen in
    lower case and without the Spanish opening mark. Only the typography of
    the model's own words changes.
    """

    lead = re.match(r"[¿¡\"'«“(\s]*", question).group(0)
    body = question[len(lead):]
    if body[:1].islower():
        body = body[0].upper() + body[1:]
    if "¿" not in question and _message_response_language(question) == "es":
        lead = "¿" + lead
    return lead + body


# An identifier the PC assigns (windowId, taskId, noteId, eventId…): the person never knows it (M39).
_INTERNAL_IDENTIFIER_FIELD = re.compile(r"(?:Id|ID|Ids|_id)$")
# M54: a field whose name carries a machine time format (dueUtc): the person says when, the system converts.
_MACHINE_TIME_FIELD = re.compile(r"(?:Utc|UTC|Iso|ISO)$")
# M76 (DEV-D v3l D-w17-t2 «Which task ID and expected version should be marked as complete?», D-p08-t3 «¿Cuál es la
# fecha límite, la versión esperada y el nombre…?», D-s019 «¿Cuál es la revisión esperada…?»): a value the system
# checks against the stored item before writing it (expectedVersion, expectedRevision, expectedTitle,
# expectedPriceCents) is read from that item, never asked of the person; which item is asked through its identifier.
_WRITE_GUARD_FIELD = re.compile(r"^expected[A-Z]")


_CLARIFICATION_FIELDS = Path(__file__).resolve().parent / "data" / "clarification_fields.v1.json"


@functools.lru_cache(maxsize=1)
def _internal_fields() -> dict[str, frozenset[str]]:
    data = json.loads(_CLARIFICATION_FIELDS.read_text(encoding="utf-8"))
    return {operation: frozenset(fields) for operation, fields in data["internal"].items()}


def internal_fields(operation: object) -> frozenset[str]:
    """Estabilización M3 (live 2026-10-12 «¿Qué alcance deseas eliminar de tus memorias locales: todo, exacto, tipo o
    tema?»): the closed-value arguments of ``operation`` whose value the reader or the contract chooses, never the
    person (data ``clarification_fields.v1.json`` «internal»): no question asks them or names them."""

    return _internal_fields().get(str(operation or ""), frozenset())


def person_askable_fields(
    fields: tuple[str, ...], schema: object = None, operation: object = None,
) -> tuple[str, ...]:
    """The missing fields a question may ask the person: every one but the write guards (M76), or all of them when
    nothing else is missing (the question then still asks which item, never a version). Estabilización M2: a field
    the contract fixes (``fixed_arguments`` of ``schema``: a const, a payload version) is never asked at all.
    Estabilización M3: nor is a field internal to ``operation`` (``internal_fields``); with nothing else missing,
    nothing is left to ask (``()``)."""

    fixed = fixed_arguments(schema)
    fields = tuple(field for field in fields if field not in fixed) or fields
    internal = internal_fields(operation)
    fields = tuple(field for field in fields if field not in internal)
    askable = tuple(field for field in fields if not _WRITE_GUARD_FIELD.match(field))
    return askable or fields
# «en formato UTC», «(UTC)», «in ISO 8601 format», «hora UTC»: the format named in a question to the person.
_TIME_FORMAT_JARGON = re.compile(
    r"\s*\(\s*(?:UTC|ISO(?:[\s-]*8601)?)\s*\)"
    r"|\s*,?\s+(?:en|in)\s+(?:(?:el|the)\s+)?(?:formato\s+)?(?:UTC|ISO(?:[\s-]*8601)?)(?:\s+(?:format|time))?\b"
    r"|\s+(?:UTC|ISO[\s-]*8601)\b",
)


def _question_without_time_format(question: str) -> str:
    """The question without a machine time format: the person answers in their own words and the mind converts them
    (a person who said UTC is answered in UTC all the same)."""

    cleaned = _TIME_FORMAT_JARGON.sub("", question)
    return re.sub(r"\s+([?,.])", r"\1", cleaned)
