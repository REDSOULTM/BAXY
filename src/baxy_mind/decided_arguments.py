"""The contextual decider's values carried into an operation's arguments: what it read for this turn, checked
against the conversation like any model-proposed literal.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from . import argument_grounding
from . import effect_intent
from .semantic import decider as semantic_decider
from .semantic import dialogue as dialogue_slot
from .semantic.notes import note_title_given, pointed_note_content
from .semantic import temporal as semantic_temporal
from .argument_payload import _single_fenced_code
from .planner import (
    enum_member_named,
    normalize_grounded_arguments,
    required_predecessors,
    validate_argument_grounding,
    validate_json_schema_instance,
)
from .semantic.arguments import as_the_person_named
from .turn_history import (
    _conversation_exchanges,
    _conversation_grounding_source,
    _person_message,
    _previous_reply,
    _previous_reply_may_be_content,
    _prior_user_texts,
)
from .plan_dependencies import _DETERMINISTIC_DEPENDENCY_FIELDS


# Fase 3.5b M42 (D33): the values the decider read in the conversation reach the arguments step of the same turn,
# keyed by the restated request the App sends back. Spent FINAL: 12 well-decided actions asked again for a time, a
# name or a folder the person had given; the decider had read them (DEV-A: 55 of 57).
_DECIDED_ARGUMENTS: dict[str, tuple[tuple[str, ...], tuple[tuple[str, Any], ...]]] = {}
_DECIDED_ARGUMENTS_KEPT = 32


def _decided_arguments_of(objective: str, operations: tuple[str, ...]) -> tuple[tuple[str, Any], ...]:
    """The values the decider gave ``operations`` for ``objective`` this turn (``_remember_decided_arguments``); none
    when it gave none, or gave them for other operations."""

    remembered = _DECIDED_ARGUMENTS.get(" ".join(objective.split()))
    if remembered is None or not set(operations) & set(remembered[0]):
        return ()
    return remembered[1]


def _remember_decided_arguments(
    objective: str, operations: tuple[str, ...], arguments: tuple[tuple[str, Any], ...],
) -> None:
    key = " ".join(objective.split())
    if not key or not arguments:
        return
    _DECIDED_ARGUMENTS.pop(key, None)
    _DECIDED_ARGUMENTS[key] = (tuple(operations), tuple(arguments))
    while len(_DECIDED_ARGUMENTS) > _DECIDED_ARGUMENTS_KEPT:
        _DECIDED_ARGUMENTS.pop(next(iter(_DECIDED_ARGUMENTS)))


def _decided_value(value: Any, contract: dict[str, Any]) -> Any:
    """The decider's scalar in the field's JSON type, or None when it cannot be one."""

    declared = contract.get("type")
    types = set(declared if isinstance(declared, list) else [declared])
    enum = contract.get("enum")
    if isinstance(enum, list):
        # M118 (D58): the decider may name the member in the person's language («Descargas» → downloads).
        return enum_member_named(value, enum)
    if "integer" in types and not isinstance(value, bool):
        if isinstance(value, int):
            return value
        text = str(value).strip()
        return int(text) if re.fullmatch(r"-?\d{1,9}", text) else None
    if "number" in types and not isinstance(value, bool):
        try:
            number = float(str(value).strip().replace(",", "."))
        except ValueError:
            return None
        return number if math.isfinite(number) else None
    if "boolean" in types:
        return value if isinstance(value, bool) else None
    if "string" in types:
        if isinstance(value, (list, dict)):
            # M141: a list or an object is never one text; its rendering («['Spotify', 'Discord']») grounds by words.
            return None
        if isinstance(value, str) and (
            len(value) >= semantic_decider.ARGUMENT_VALUE_CHARACTERS
            # M118 (DEV-F F-w42-t3, code cut at «…dni[-1].upper()\n    if \n»): lines left open at the end are cut too.
            # M141 (DEV-G v4n G-w06-t3 «guárdalo en un archivo que se llame suma.py» → «def sumar(a, b):\n    return
            # a + b\n»): a closed last line followed by its line break is whole, not open.
            or ("\n" in value and value.rstrip("\r\n") != value.rstrip())
        ):
            # M67 (FINAL F-w14-t3): a text at the decider's bound is the start of a longer one (a query, a list BAXY
            # wrote), grounded but cut; the extraction reads it whole instead.
            return None
        text = " ".join(str(value).split())
        return text or None
    return None


def _with_decided_arguments(
    operation: str,
    request: str,
    arguments: object,
    schema: dict[str, object],
    trusted_source: str,
    *,
    serves: tuple[str, ...] = (),
    previous_reply: str | None = None,
) -> dict[str, Any] | None:
    """Fill what the extraction left out or could not ground with what the decider read.

    Each value must be grounded in the trusted text like any model-proposed literal; identifiers stay with the
    kernel's dependencies and times with ``temporal`` (the decider's own ISO dates are not trusted). None when the
    decider gave nothing new for this operation. ``serves`` and ``previous_reply``: see ``_decided_fields``.
    """

    decided = _decided_fields(
        operation, request, schema, trusted_source, serves=serves, previous_reply=previous_reply,
    )
    if decided is None:
        return None
    merged = dict(arguments) if isinstance(arguments, dict) else {}
    added = False
    for name, value, field_schema in decided:
        if name in merged and validate_argument_grounding({name: merged[name]}, field_schema, trusted_source):
            continue
        if not validate_argument_grounding({name: value}, field_schema, trusted_source):
            value = _said_part_of_a_name(name, value, field_schema, trusted_source) or (
                # M136: a folder the decider chose and nobody said is every known folder, when that grounds.
                "all_known" if "all_known" in (field_schema["properties"][name].get("enum") or []) else None
            )
        if value is not None and validate_argument_grounding({name: value}, field_schema, trusted_source):
            merged[name] = value
            added = True
    return merged if added else None


# M136 (DEV-G v4n G-s097 «baxy abreme el obs…» → the decider's «OBS Studio» → «¿Cuál es el nombre exacto de la
# aplicación…?»): an application's name the decider completed with words nobody said keeps the words the person said.
_SAID_NAME_FIELDS = frozenset({"appId", "name"})
# M147: the fields that carry a name to look up or play as the person wrote it, for the services whose own search
# forgives a typo of the person's. Web search sources forgive none (D-w08-t1). M157: an application's name is resolved
# in the catalog of installed applications, for which the readers already chose the name the person's spelling meant
# («abreme el exel» → Excel, M127), so it keeps that name.
_AS_SPELLED_FIELDS = frozenset({"query", "title", "artist"})
_AS_SPELLED_LOOKUPS = ("media.play", "streaming.play")


def _as_the_person_spelled(operation: str, arguments: Any, person: str, history: object) -> Any:
    """M147 (DEV-F F-w05-t5 «pone algo de javiera mena en spotify» → the decider's «Javier Mené», every round, and
    another artist played): a name a service looks up, respelled by the model a letter or two off from what the person
    wrote, is looked up as the person wrote it (``semantic.decider.as_the_person_spelled``).

    M157 (DEV-F v4u/v4v F-w05-t5, the same row: seen.query «Javier Mené» in both runs): M147 ran on the decider's values
    against the grounding source, whose first line is the objective — the decider's own restatement «Pon algo de Javier
    Mené en Spotify.» —, so the name was always «said as it is» there; and the readers had already read it from that
    restatement, so the decider's values were never looked at. The respelling now runs once, on the arguments the step
    returns whoever read them, against what the person and BAXY said in the conversation, never the restatement.
    """

    if not isinstance(arguments, dict) or not operation.startswith(_AS_SPELLED_LOOKUPS):
        return arguments
    said = _conversation_grounding_source(person, history).splitlines()
    # M166 (DEV-H v4w H-w22-t2 «esa no pone bailando solo» → query «otra canción de Los Bunkers»): the title and the
    # artist the person's message names go as the person said them (``semantic.arguments.as_the_person_named``).
    arguments = as_the_person_named(operation, arguments, person, said[1:], _prior_user_texts(history, person))
    respelled = dict(arguments)
    for name in _AS_SPELLED_FIELDS & set(arguments):
        if isinstance(arguments[name], str):
            respelled[name] = semantic_decider.as_the_person_spelled(arguments[name], said) or arguments[name]
    return respelled


def _said_part_of_a_name(name: str, value: Any, field_schema: dict[str, Any], trusted_source: str) -> Any:
    """The longest run of the decider's words for an application's name that grounds on its own; None when none does."""

    if name not in _SAID_NAME_FIELDS or not isinstance(value, str):
        return None
    words = value.split()
    for size in range(len(words) - 1, 0, -1):
        for start in range(len(words) - size + 1):
            part = " ".join(words[start:start + size])
            if len(part) >= 2 and validate_argument_grounding({name: part}, field_schema, trusted_source):
                return part
    return None


def _schema_field_of(name: str, operation: str, properties: dict[str, Any], required: list[Any]) -> str | None:
    """M136 (DEV-G v4n G-s040 «open Notepad and put it on the left half» → {"app": "Notepad"}; G-s116 «abrí spotify y
    ponime algo de jazz» → {"app.open": "Spotify", "media.play.query": "jazz tranquilo"}): the field of this
    operation's schema a decider's value names — the field itself, the operation's one free required text when the
    value is keyed by the operation, or the one field whose name begins with the decider's («app» → «appId»)."""

    if name in properties:
        return name
    if name == operation:
        free = [
            field for field in required
            if isinstance(properties.get(field), dict)
            and properties[field].get("type") == "string"
            and "enum" not in properties[field]
            and "const" not in properties[field]
        ]
        return free[0] if len(free) == 1 else None
    # Estabilización X5: an identifier is named by what it identifies («appId» is the application, «applicationName»).
    stem = name[:-2] if name.endswith("Id") else name
    if len(stem) < 3:
        return None
    named = [field for field in properties if field.casefold().startswith(stem.casefold())]
    return named[0] if len(named) == 1 else None


def _decided_fields(
    operation: str,
    request: str,
    schema: dict[str, object],
    trusted_source: str,
    *,
    serves: tuple[str, ...] = (),
    previous_reply: str | None = None,
) -> list[tuple[str, Any, dict[str, Any]]] | None:
    """The decider's values for ``operation`` that a field may take, each with its one-field schema; None when the
    decider gave none for this request. Identifiers stay with the kernel's dependencies and times with ``temporal``.

    ``serves``: the decided operations this one is the catalog's prerequisite of (M141, a plan's ``window.resolve``
    before the decided ``window.snap``), whose values it may take too. ``previous_reply``: BAXY's last reply, whole; a
    free text the decider wrote that is that reply (or its one code block) in the same words is the reply verbatim."""

    remembered = _DECIDED_ARGUMENTS.get(" ".join(request.split()))
    properties = schema.get("properties")
    if (
        remembered is None
        or not ({operation, *serves} & set(remembered[0]))
        or not isinstance(properties, dict)
    ):
        return None
    identities = set(_DETERMINISTIC_DEPENDENCY_FIELDS.get(operation, ()))
    required = schema.get("required") if isinstance(schema.get("required"), list) else []
    given = {name for name, _ in remembered[1]}
    fields: list[tuple[str, Any, dict[str, Any]]] = []
    for decided_name, raw in remembered[1]:
        name = _schema_field_of(decided_name, operation, properties, required)
        if name is None or (name != decided_name and name in given):
            continue
        contract = properties.get(name)
        if (
            not isinstance(contract, dict)
            or name in identities
            or (name.endswith("Id") and name != "appId")
            or name.endswith("Utc")
            or contract.get("format") in {"date-time", "date", "time"}
        ):
            continue
        if name == "due":
            raw = semantic_temporal.said_day_of(raw, trusted_source) or raw
        verbatim = (
            _reply_the_decider_wrote(raw, previous_reply)
            if previous_reply and _free_text_field(name, contract)
            else None
        )
        value = verbatim if verbatim is not None else _decided_value(raw, contract)
        if value is None:
            continue
        fields.append(
            (name, value, {"type": "object", "properties": {name: contract}, "required": [name], "additionalProperties": False})
        )
    return fields


def _reply_the_decider_wrote(value: Any, previous_reply: str) -> str | None:
    """M141 (DEV-G v4o G-w06-t3 «guárdalo en un archivo que se llame suma.py» after BAXY's ```python block → the
    decider's ``text`` «def sumar(a, b):\\n    return a + b\\n» → «¿Cuál es el código…?»): BAXY's previous reply, or its
    one code block, verbatim when the decider's free text is it in the same words (or, cut at the decider's bound, its
    start). The decider's values are whitespace-folded and bounded, so code and lists travel only through here (M67)."""

    if not isinstance(value, str) or not value.strip():
        return None
    written = " ".join(value.split())
    cut = len(value) >= semantic_decider.ARGUMENT_VALUE_CHARACTERS
    for candidate in (_single_fenced_code(previous_reply), previous_reply.strip()):
        if not candidate:
            continue
        said = " ".join(candidate.split())
        if said == written or (cut and said.startswith(written)):
            return candidate
    return None


def _decided_reply_field(operation: str, request: str, schema: dict[str, object], previous_reply: str | None) -> bool:
    """M141: the decider wrote BAXY's previous reply (``_reply_the_decider_wrote``) into one of this operation's fields."""

    if not previous_reply:
        return False
    reply = previous_reply.strip()
    candidates = {reply, _single_fenced_code(reply) or reply}
    return any(
        value in candidates
        for _, value, _ in _decided_fields(operation, request, schema, "", previous_reply=reply) or ()
    )


def _said_single_members(schema: dict[str, object], trusted_source: str) -> dict[str, Any]:
    """M141: each required field with one possible value (a one-member enum, a const) that was said — Spotify for
    ``media.play.query``'s provider. Nothing is chosen: the field can take no other value."""

    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    required = schema.get("required") if isinstance(schema.get("required"), list) else []
    said: dict[str, Any] = {}
    for field in required:
        contract = properties.get(field)
        if not isinstance(contract, dict):
            continue
        members = contract.get("enum") if isinstance(contract.get("enum"), list) else (
            [contract["const"]] if "const" in contract else []
        )
        if len(members) != 1:
            continue
        field_schema = {"type": "object", "properties": {field: contract}, "required": [field], "additionalProperties": False}
        if validate_argument_grounding({field: members[0]}, field_schema, trusted_source):
            said[field] = members[0]
    return said


def _plan_step_decided_arguments(
    operation: str,
    plan_operations: tuple[str, ...],
    objective: str,
    tool: dict,
    history: object,
    *,
    extracted: object = None,
    after_extraction: bool = False,
) -> dict[str, Any] | None:
    """M141 (DEV-G v4o G-s040 «open Notepad and put it on the left half of the screen please» → the decider's
    {"app": "Notepad", "side": "left"}; G-s116 «abrí spotify y ponime algo de jazz tranqui…» → {"app.open":
    "Spotify", "media.play.query": "jazz tranquilo"}; both → «¿Cuál es el nombre… de la aplicación…?»): a plan step
    takes what the decider read, as one operation does (M42b, M136), so the planner's extraction runs only for what
    is still missing and asks only for that.

    Before the extraction, only a step whose operation the decider decided, and only when its values (with each
    one-valued field that was said) fill the whole step. After the extraction failed, its values are completed with
    the decider's, and a catalog prerequisite of a decided effect (``window.resolve`` before ``window.snap``) may take
    them too. An operation that is two steps of the plan takes none: the decider's values cannot say which step is
    whose. Every value grounds in what was said in this conversation (M43); the arguments, or None."""

    if plan_operations.count(operation) != 1:
        return None
    schema = tool["function"]["parameters"]
    served: tuple[str, ...] = ()
    if after_extraction:
        served = tuple(dict.fromkeys(
            effect for effect in plan_operations if operation in required_predecessors(effect)
        ))
        if len(served) != 1 or plan_operations.count(served[0]) != 1:
            served = ()
    elif _previous_reply_may_be_content(tool, history):
        # As M42b: a content that may be BAXY's last reply is read by the extraction, not by the decider alone.
        return None
    said = _conversation_grounding_source(objective, history)
    said = _with_decided_restatements(operation, objective, schema, said)
    said = _with_every_known_folder_unsaid(operation, schema, said)
    read = dict(extracted) if isinstance(extracted, dict) else {}
    base = {**_said_single_members(schema, said), **read}
    decided = _with_decided_arguments(operation, objective, base, schema, said, serves=served)
    if decided is None:
        if not after_extraction or base == read:
            return None
        # The extraction's values completed with a one-valued field that was said.
        decided = base
    grounded = normalize_grounded_arguments(decided, schema, said)
    if grounded is None:
        return None
    normalized = argument_grounding._normalize_grounded_operation_arguments(operation, grounded, objective)
    if normalized is None or not validate_json_schema_instance(normalized, schema):
        return None
    # M147/M157: a plan step's name to look up goes as the person spelled it too (``_as_the_person_spelled``).
    return _as_the_person_spelled(operation, normalized, _person_message(history, objective), history)


# M136 (DEV-G v4n G-s123 «resúmeme el pdf ese que se llama contrato_arriendo_2026…», G-w40-t1 «busca un archivo que se
# llama cotizacion_mudanza» → the decider's folder «Documentos»/«Descargas», nobody's → «¿En qué carpeta…?»): a read of a
# named file where the person names no folder looks in every known folder, as the readers do (PDF1689); a write or a
# deletion keeps asking.
_EVERY_KNOWN_FOLDER_READS = frozenset({"document.pdf.read", "document.text.read", "filesystem.known.search"})


def _with_every_known_folder_unsaid(operation: str, schema: dict[str, object], trusted_source: str) -> str:
    """The trusted source with «all known» when this read's folder enum holds it and no member of it was said."""

    if operation not in _EVERY_KNOWN_FOLDER_READS:
        return trusted_source
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    for field, contract in properties.items():
        members = contract.get("enum") if isinstance(contract, dict) else None
        if not isinstance(members, list) or "all_known" not in members:
            continue
        field_schema = {"type": "object", "properties": {field: contract}, "required": [field], "additionalProperties": False}
        if not any(validate_argument_grounding({field: member}, field_schema, trusted_source) for member in members):
            return f"{trusted_source}\nall known"
    return trusted_source


# M118 (D58): the fields whose value is the person's words (a message, a note, a title, a search), where a restatement
# may say the same thing differently; names of people, places in the catalog, paths and addresses stay literal.
_LITERAL_ONLY_FIELDS = frozenset({"appId", "recipient", "url", "resourceUri", "relativePath", "path", "host", "name"})


def _free_text_field(name: str, contract: dict[str, Any]) -> bool:
    declared = contract.get("type")
    types = set(declared if isinstance(declared, list) else [declared])
    return (
        "string" in types
        and "enum" not in contract
        and "const" not in contract
        and name not in _LITERAL_ONLY_FIELDS
    )


def _with_decided_restatements(operation: str, request: str, schema: dict[str, object], trusted_source: str) -> str:
    """M118 (D58): the trusted source with each free text the decider wrote that says what was said in other words
    (``semantic.decider.said_in_other_words``): the literal grounding dropped them and the turn asked again for what the
    person gave. What the decider brought that nobody said (a number, a name) still grounds nothing."""

    decided = _decided_fields(operation, request, schema, trusted_source) or []
    lines = trusted_source.splitlines()
    restated = [
        value
        for name, value, field_schema in decided
        if (
            _free_text_field(name, field_schema["properties"][name])
            and semantic_decider.said_in_other_words(value, lines)
            # M143 (DEV-H v4o H-w21-t1 «che baxy, tirá algún tema de charly garcia de los ochenta, el que sea» → the
            # decider's media.play.query {"provider": "Spotify"} → «¿Qué proveedor de música debo usar…?»): a field
            # with one possible member is no choice of the person's; the decider that chose this operation and gave
            # that member said the only value the field can take (M141 ``_said_single_members`` needs it said).
            or field_schema["properties"][name].get("enum") == [value]
        )
        and not validate_argument_grounding({name: value}, field_schema, trusted_source)
    ]
    return "\n".join([trusted_source, *restated]) if restated else trusted_source


# M118 (D58): the fields whose words are what the operation delivers (a message, a note, what a reminder says); the
# decider's wording of them stands over the readers'. A task's title and details keep the list model (M113: the entry,
# the list it goes on), a search its query (D32, M53) and a song its title: there the readers' value is the operation's
# own shape, not a reading of the person's words.
_DECIDER_WORDING_FIELDS = frozenset({"text", "content", "body", "subject", "message"})
_DECIDER_TITLED_OPERATIONS = ("note.", "notification.schedule", "reminder.create", "calendar.event.")


def _with_decider_values_kept(
    operation: str, request: str, arguments: dict[str, Any], schema: dict[str, object], trusted_source: str,
) -> dict[str, Any]:
    """M118 (D58, DEV-F F-w55-t5 «eso mandalo a una nota, titulala dentista» → the readers' title ««Dentista»» with
    its quotes, F-w12-t1 «…una alarma pa las 6 y 40 mañana, que tengo que ir a buscar a la Trini al aeropuerto» → the
    readers' title «alarma mañana a las 6:40»): the words the decider gave for what the operation delivers, grounded
    in what was said, are never replaced by the readers' reading of the same field; what the decider left out keeps
    the readers' value. The readers' arguments when the result would not hold the schema."""

    decided = _decided_fields(operation, request, schema, trusted_source)
    if not decided:
        return arguments
    merged = dict(arguments)
    for name, value, field_schema in decided:
        if (
            name in merged
            and merged[name] != value
            and (
                name in _DECIDER_WORDING_FIELDS
                or (name == "title" and operation.startswith(_DECIDER_TITLED_OPERATIONS))
            )
            and _free_text_field(name, field_schema["properties"][name])
            and validate_argument_grounding({name: value}, field_schema, trusted_source)
        ):
            merged[name] = value
    if merged != arguments and validate_json_schema_instance(merged, schema):
        return merged
    return arguments


def _with_decided_part_of_day(operation: str, request: str, arguments: Any) -> Any:
    """M144 (D58; DEV-H v4p H-w45-t1 «tengo dentista el jueves a las 4:30, so ponme un reminder» → set at 04:30, where
    the isolated decider set 16:30): a clock written on the dial («a las 4:30», no part of the day said) is read as
    written, 04:30; the decider read its part of the day from what it is for (a dentist at 16:30, an alarm before a
    flight at 04:50). When the decider's own moment is that same clock twelve hours away, its part of the day is the
    one meant, on the day the readers read."""

    if operation not in _REMINDER_OPERATIONS or not isinstance(arguments, dict):
        return arguments
    due = arguments.get("dueUtc")
    clocks = semantic_temporal.spoken_clocks(effect_intent._fold(request))
    if not isinstance(due, str) or len(clocks) != 1 or not clocks[0].on_the_dial:
        return arguments
    remembered = _DECIDED_ARGUMENTS.get(" ".join(request.split()))
    decided_due = dict(remembered[1]).get("dueUtc") if remembered is not None else None
    written = re.search(r"T(?P<hour>\d{2}):(?P<minute>\d{2})", decided_due) if isinstance(decided_due, str) else None
    try:
        moment = datetime.fromisoformat(due.replace("Z", "+00:00")).astimezone()
    except ValueError:
        return arguments
    if written is None or int(written["minute"]) != moment.minute or int(written["hour"]) != (moment.hour + 12) % 24:
        return arguments
    shifted = moment + timedelta(hours=12 if moment.hour < 12 else -12)
    if shifted <= datetime.now().astimezone():
        return arguments
    return {**arguments, "dueUtc": shifted.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")}


def _with_pointed_reminder_title(operation: str, person: str, history: object, arguments: Any) -> Any:
    """M148 (DEV-F v4q F-w48-t4 «recuérdame eso el domingo a las 3 de la tarde» after «…; mejor lleva paraguas.» →
    titled «Voy a estar en Zapopan el domingo.»; DEV-D v4q D-w07-t4 «…que le devuelva eso a mi carnal» after
    «Redondeado hacia arriba, 265.» → «Devolverle eso a mi amigo.»): a reminder that points with «eso» is titled with
    what the conversation gave (``semantic.dialogue.pointed_reminder_title``); a title that already says it stays."""

    if operation not in _REMINDER_OPERATIONS or not isinstance(arguments, dict):
        return arguments
    title = arguments.get("title")
    if not isinstance(title, str) or not title.strip():
        return arguments
    said_before = _prior_user_texts(history, person)
    pointed = dialogue_slot.pointed_reminder_title(person, _previous_reply(history), title, said_before)
    return {**arguments, "title": pointed} if pointed else arguments


def _pointed_note_content(
    operation: str, request: str, person: str, history: object, schema: dict[str, object], said: str,
    arguments: object,
) -> tuple[str, str | None] | None:
    """M160 (DEV-H v4w H-w11-t3 «save that whole thing as a note called banana bread», DEV-I v4w I-w18-t3 «¿me la
    guardas en una nota con esas cantidades?», DEV-F v4w F-w34-t3, DEV-G v4w G-w29-t4): the content of a note that
    points at BAXY's words other than its last reply alone (``semantic.notes.pointed_note_content``), verbatim, with
    the note's title when one is known and said — the decider's, the readers', or the one the person wrote. None when
    the last reply is the one meant: M67 offers it to the extraction as before."""

    if operation != "note.create":
        return None
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    contract = properties.get("title")
    title_schema = {"type": "object", "properties": {"title": contract}, "required": ["title"], "additionalProperties": False}
    decided = [value for name, value, _ in _decided_fields(operation, request, schema, said) or () if name == "title"]
    read = [arguments["title"]] if isinstance(arguments, dict) and isinstance(arguments.get("title"), str) else []
    titles = [
        title for title in (*decided, *read, note_title_given(person))
        if isinstance(title, str) and title.strip() and isinstance(contract, dict)
        and validate_argument_grounding({"title": title}, title_schema, said)
    ]
    title = titles[0] if titles else None
    content = pointed_note_content(person, title or "", _conversation_exchanges(history))
    return (content, title) if content is not None else None


def _decided_arguments_alone(
    operation: str, request: str, tool: dict, trusted_source: str, *, previous_reply: str | None = None,
) -> dict[str, Any] | None:
    """The decider's values when they ground every required field and the operation's own normalization."""

    schema = tool["function"]["parameters"]
    decided = _with_decided_arguments(
        operation, request, {}, schema, trusted_source, previous_reply=previous_reply,
    )
    if decided is None:
        return None
    grounded = normalize_grounded_arguments(decided, schema, trusted_source)
    if grounded is None:
        return None
    return argument_grounding._normalize_grounded_operation_arguments(operation, grounded, request)


_REMINDER_OPERATIONS = frozenset({"notification.schedule", "reminder.create"})
