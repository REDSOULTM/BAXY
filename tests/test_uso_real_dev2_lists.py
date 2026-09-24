"""Dev set 2 (2026-09-24, MASSIVE lists_query / lists_createoradd / lists_remove, es-ES and en-US): the person's
lists read, filled and emptied. Measured on the whole turn with no model: 0/40 decided before, the model then
chose a clarification, a limit, a web search or the list read where an entry was taken off.

1. A list asked for is read, however it is asked: a verb as said to a friend or with «usted» («comprueba mi
   lista», «abrir mi lista»), the lists the person keeps («dime qué listas tengo», «display available lists»),
   the list pointed at («what is on this specific list»), the day it is for («what is on the list for today»),
   and whether a named list exists («did i make a shopping list»). Owner: semantic/notes.list_read_request
   (_LIST_READ_VERB, _LIST_INVENTORY, _OWN_LIST, _LIST_DAY).
2. An entry put on a list, a new one included («put pencil on a new grocery list», «add buy groceries to my to do
   list for today», «por favor agregue pan a la lista»), is a task on it; an entry only pointed at or unnamed
   («añade esto a la lista», «incluir un elemento en una lista») asks what goes on it. Owner: notes._LIST_ENTRY,
   _UNNAMED_LIST_ENTRY, list_creation_without_items; the request whatever the verb's person:
   patterns._is_direct_request.
3. An entry taken off a list is its task sent to the recoverable trash: task.resolve.exact finds it by the title
   it was added with and task.delete consumes the identity it returned («we're out of paint so take bathroom
   painting off the list» read the list). Owner: notes.list_removal_request; planner._required_predecessors;
   __main__._IDENTITY_CONSUMERS / _DETERMINISTIC_DEPENDENCY_FIELDS; the task.delete domain gate.
4. A whole list removed («eliminar mi lista de tareas pendientes», «i don't want this list any more») is every
   entry at once, which no operation does: a plain limit, never a read of the list. Owner:
   patterns.known_unsupported_effect_request.

Every list mixes Spanish, English and Spanglish and holds phrasings never seen in the dev set.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.effect_intent import operation_domain_is_grounded
from baxy_mind.planner import PlannerCatalog, validate_skeleton
from baxy_mind.semantic.notes import list_creation_without_items, list_read_request, list_removal_request
from baxy_mind.semantic.normalize import fold
from baxy_mind.semantic.patterns import known_unsupported_effect_request, resolve_explicit_effects

SCHEMAS = {
    "task.create": {
        "type": "object",
        "properties": {
            "details": {"type": "string", "x-maxUtf8Bytes": 65536},
            "due": {"type": ["null", "string"], "maxLength": 64},
            "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
        },
        "required": ["title"], "additionalProperties": False,
    },
    "task.delete": {
        "type": "object",
        "properties": {
            "expectedVersion": {"type": "integer", "minimum": 1},
            "reviewLabel": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
            "taskId": {"type": "string", "maxLength": 36, "x-nonWhitespace": True},
        },
        "required": ["expectedVersion", "reviewLabel", "taskId"], "additionalProperties": False,
    },
    "task.list": {
        "type": "object",
        "properties": {
            "includeDeleted": {"type": "boolean"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            "status": {"type": "string", "enum": ["all", "completed", "open"]},
        },
        "required": [], "additionalProperties": False,
    },
    "task.resolve.exact": {
        "type": "object",
        "properties": {
            "includeDeleted": {"type": "boolean"},
            "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
        },
        "required": ["title"], "additionalProperties": False,
    },
    "task.search": {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            "query": {"type": "string", "x-maxUtf8Bytes": 2000, "x-nonWhitespace": True},
            "status": {"type": "string", "enum": ["all", "completed", "open"]},
        },
        "required": ["query"], "additionalProperties": False,
    },
}
RISKS = {"task.delete": "recoverable_delete", "task.list": "read_only", "task.search": "read_only",
         "task.resolve.exact": "read_only"}
OPERATIONS = (
    "task.create", "task.list", "task.search", "task.resolve.exact", "task.delete", "task.complete",
    "note.list", "note.search", "reminder.list", "media.play.youtube", "media.status", "web.search",
    "filesystem.list", "system.time",
)


def _tool(operation: str) -> dict:
    schema = SCHEMAS.get(operation, {"type": "object", "properties": {}, "required": [], "additionalProperties": False})
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"), "canonical_name": operation,
            "description": f"Authenticated catalog leaf {operation}.",
            "risk": RISKS.get(operation, "low_reversible"), "parameters": schema,
        },
    }


TOOLS = [_tool(name) for name in OPERATIONS]


class _NoEvidence:
    @staticmethod
    def candidate_families(*_args: object) -> tuple[str, ...]:
        return ()

    @staticmethod
    def retrieve(*_args: object, **_kwargs: object) -> list[object]:
        return []


class _NoModel:
    """The readers own these turns: the model never decides them; it only words a question or a limit."""

    @staticmethod
    def decide_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("a deterministic reading owns this turn")

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None

    @staticmethod
    def formulate_explicit_clarification_question(_objective: str, operations: tuple, missing: tuple) -> str:
        return f"¿{'/'.join(operations)} {'/'.join(missing)}?"

    @staticmethod
    def chat(_text: str, *_args: object, conversation_kind: str | None = None, **_kwargs: object) -> tuple[str, list]:
        assert conversation_kind == "unsupported"
        return "Eso no lo hago.", []


def _turn(text: str) -> dict:
    return sidecar._prepare_turn_result(
        {"id": "dev2-lists", "text": text, "history": []},
        llm=_NoModel(),
        planner_catalog=PlannerCatalog(TOOLS),
        turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name={tool["function"]["canonical_name"]: tool for tool in TOOLS},
    )


def _decision(text: str) -> tuple[str, str]:
    result = _turn(text)
    if result["kind"] == "clarify":
        return "clarify", "/".join(result["intentOperations"])
    if result["kind"] == "conversation":
        return "conversation", str(result.get("conversationKind"))
    return result["kind"], "/".join(result["effectOperations"])


# ---------------------------------------------------------------- the dev set, whole turn


@pytest.mark.parametrize(
    ("text", "decision"),
    [
        ("que esta en esta lista especifica", ("action", "task.list")),
        ("dime que listas tengo", ("action", "task.list")),
        ("cuáles fueron las últimas cinco listas que hice", ("action", "task.list")),
        ("por favor dime que listas he hecho", ("action", "task.list")),
        ("qué es esto en la lista", ("action", "task.list")),
        ("que listas están disponibles ahora", ("action", "task.list")),
        ("comprueba mi lista", ("action", "task.list")),
        ("reúne mi lista", ("action", "task.list")),
        ("puedo comprobar mis listas", ("action", "task.list")),
        ("abrir mi lista", ("action", "task.list")),
        ("hice una lista de compra", ("action", "task.search")),
        ("olly qué más tengo en la lista", ("action", "task.list")),
        ("what is on this specific list", ("action", "task.list")),
        ("did i make a shopping list", ("action", "task.search")),
        ("bing up my list", ("action", "task.list")),
        ("what is on the list for today", ("action", "task.list")),
        ("check list", ("action", "task.list")),
        ("display available lists", ("action", "task.list")),
        ("add buy groceries to my to do list for today", ("action", "task.create")),
        ("put pencil on a new grocery list", ("action", "task.create")),
        ("añade esto a la lista", ("clarify", "task.create")),
        ("incluir un elemento en una lista", ("clarify", "task.create")),
        ("por favor agregue este artículo a la lista", ("clarify", "task.create")),
        ("we're out of paint so take bathroom painting off the list", ("plan", "task.delete")),
        ("remove the excel file from the list", ("plan", "task.delete")),
        ("eliminar la lista de cosas por hacer", ("conversation", "unsupported")),
        ("eliminar mi lista de tareas pendientes", ("conversation", "unsupported")),
        ("por favor elimine mi lista de tareas pendientes de hoy", ("conversation", "unsupported")),
        ("i don't want this list any more", ("conversation", "unsupported")),
        ("please remove my to do list from today", ("conversation", "unsupported")),
        ("remove the list of things to do", ("conversation", "unsupported")),
    ],
)
def test_the_dev_set_turns_are_decided_without_the_model(text, decision):
    assert _decision(text) == decision


# ---------------------------------------------------------------- 1. a list asked for is read


@pytest.mark.parametrize(
    ("text", "operation", "query"),
    [
        ("chequea mi lista de tareas", "task.list", None),
        ("ábreme mi lista", "task.list", None),
        ("tráeme mi lista, porfa", "task.list", None),
        ("muéstrame todas mis listas", "task.list", None),
        ("enséñame las listas que tengo", "task.list", None),
        ("qué listas hay", "task.list", None),
        ("cuáles son mis últimas listas que guardé", "task.list", None),
        ("what lists do i have", "task.list", None),
        ("which lists have i made", "task.list", None),
        ("show me all my lists", "task.list", None),
        ("what were the last three lists i made", "task.list", None),
        ("what else is on my to-do list", "task.list", None),
        ("what's on that list", "task.list", None),
        ("pull up my list for tomorrow", "task.list", None),
        ("qué hay en mi lista para hoy", "task.list", None),
        ("muéstrame el contenido de la lista", "task.list", None),
        ("cuántas listas tengo", "task.list", None),
        ("how many lists do i have", "task.list", None),
        ("show me the contents of my shopping list", "task.search", "shopping list"),
        ("pull up my grocery list", "task.search", "grocery list"),
        ("abre la lista de la compra", "task.search", "lista de la compra"),
        ("qué más hay en mi lista de la compra", "task.search", "lista de la compra"),
        ("what else is on my shopping list", "task.search", "shopping list"),
        ("have i got a packing list", "task.search", "packing list"),
        ("¿tengo una lista de regalos?", "task.search", "lista de regalos"),
    ],
)
def test_a_list_asked_for_is_read(text, operation, query):
    assert _decision(text) == ("action", operation)
    read = list_read_request(text)
    assert read is not None and read.operation == operation and read.query == query


@pytest.mark.parametrize(
    "text",
    [
        "dime la lista de los planetas",  # public knowledge
        "abre mi lista de reproducción",  # music
        "muestra mis listas de reproducción",
        "open my list of reminders",  # another store reads itself
        "show me the list of countries in europe",
        "tengo una lista de contactos para la fiesta que estoy planeando",
    ],
)
def test_what_is_not_the_persons_list_is_not_read_as_one(text):
    read = list_read_request(text)
    assert read is None
    effects = resolve_explicit_effects(text, OPERATIONS)
    assert effects is None or not {"task.list", "task.search"} & set(effects.operations)


# ---------------------------------------------------------------- 2. an entry put on a list


@pytest.mark.parametrize(
    ("text", "title", "details"),
    [
        ("add buy groceries to my to do list for today", "buy groceries", "to do list for today"),
        ("put pencil on a new grocery list", "pencil", "grocery list"),
        ("por favor agregue pan a mi lista de la compra", "pan", "lista de la compra"),
        ("añada huevos a la lista de la compra", "huevos", "lista de la compra"),
        ("include batteries on my shopping list", "batteries", "shopping list"),
        ("put tomatoes on a new shopping list", "tomatoes", "shopping list"),
        ("apunte la cita del dentista en una nueva lista de pendientes", "cita del dentista", "lista de pendientes"),
    ],
)
def test_an_entry_put_on_a_list_is_a_task_on_it(text, title, details):
    effects = resolve_explicit_effects(text, OPERATIONS)
    assert effects is not None and effects.operations == ("task.create",)
    arguments = sidecar._ground_explicit_arguments("task.create", effects.evidence[0], SCHEMAS["task.create"])
    assert arguments == {"title": title, "details": details}


@pytest.mark.parametrize(
    "text",
    [
        "añade esto a la lista", "mete eso en mi lista", "add that to my list", "put this on my shopping list",
        "incluir un elemento en una lista", "apunte algo en una lista", "por favor agregue este artículo a la lista",
        "add something to a new list",
    ],
)
def test_an_entry_only_pointed_at_or_unnamed_asks_what_goes_on_the_list(text):
    assert list_creation_without_items(fold(text)) is not None
    assert _decision(text) == ("clarify", "task.create")


def test_a_list_opened_new_is_still_asked_what_goes_on_it():
    assert _decision("abre una lista nueva") == ("clarify", "task.create")
    assert list_creation_without_items(fold("abre la lista de la compra")) is None


def test_a_song_pointed_at_is_still_not_an_entry():
    assert list_creation_without_items(fold("añade esta canción a mi lista de reproducción")) is None


# ---------------------------------------------------------------- 3. an entry taken off a list


@pytest.mark.parametrize(
    ("text", "entry", "list_name"),
    [
        ("we're out of paint so take bathroom painting off the list", "bathroom painting", "list"),
        ("remove the excel file from the list", "excel file", "list"),
        ("quita la leche de mi lista de la compra", "leche", "lista de la compra"),
        ("quítame el arroz de la lista", "arroz", "lista"),
        ("tacha el pan de mi lista", "pan", "lista"),
        ("cross eggs off my grocery list", "eggs", "grocery list"),
        ("scratch bread off the shopping list please", "bread", "shopping list"),
        ("we're out of milk, so remove milk from my shopping list", "milk", "shopping list"),
        ("ya compré el pan así que borra el pan de la lista de la compra", "pan", "lista de la compra"),
        ("delete Call Mom from my to-do list", "Call Mom", "to-do list"),
    ],
)
def test_an_entry_taken_off_a_list_is_resolved_then_sent_to_the_trash(text, entry, list_name):
    removal = list_removal_request(text)
    assert removal is not None and (removal.entry, removal.list_name) == (entry, list_name)
    assert _decision(text) == ("plan", "task.delete")
    assert operation_domain_is_grounded(text, "task.delete") is True
    skeleton = sidecar._explicit_plan_skeleton(("task.delete",), (text,))
    assert [(step["operation"], step["dependsOn"], step["argumentsMode"]) for step in skeleton["steps"]] == [
        ("task.resolve.exact", [], "literal"),
        ("task.delete", ["step_1"], "after_dependencies"),
    ]
    catalog = PlannerCatalog(TOOLS)
    shortlist = [tool for tool in catalog.tools if tool.name in {"task.resolve.exact", "task.delete"}]
    assert validate_skeleton(skeleton, catalog, shortlist, text).kind == "plan"
    assert sidecar._ground_explicit_arguments("task.resolve.exact", text, SCHEMAS["task.resolve.exact"]) == {
        "title": entry,
    }


def test_the_trash_takes_the_identity_the_resolve_returned():
    observations = [{
        "operation": "task.resolve.exact", "verified": True, "status": "completed",
        "result": {"taskId": "5f0c3a8e-1b2c-4d3e-8f40-000000000007", "expectedVersion": 3, "reviewLabel": "leche",
                   "deleted": False, "status": "open"},
    }]
    tool = {"function": {"parameters": SCHEMAS["task.delete"]}}
    assert sidecar._verified_dependency_identity_arguments(
        "task.delete", "quita la leche de mi lista de la compra", observations, tool,
    ) == {"taskId": "5f0c3a8e-1b2c-4d3e-8f40-000000000007", "expectedVersion": 3, "reviewLabel": "leche"}
    # Nothing resolved: no identity is made up.
    assert sidecar._verified_dependency_identity_arguments(
        "task.delete", "quita la leche de mi lista de la compra", [], tool,
    ) is None


@pytest.mark.parametrize(
    "text",
    [
        "no borres la leche de mi lista de la compra",
        "don't remove milk from my shopping list",
        "quita esta canción de mi lista de reproducción",
        "si ya no hay leche entonces quita la leche de la lista",
        "if it's done then delete it from my list",
        "quita esto de la lista",
        "borra la alarma de mi lista de alarmas",
    ],
)
def test_what_is_not_an_entry_taken_off_is_not_deleted(text):
    effects = resolve_explicit_effects(text, OPERATIONS)
    assert effects is None or "task.delete" not in effects.operations
    assert known_unsupported_effect_request(text, OPERATIONS) is False


# ---------------------------------------------------------------- 4. a whole list removed


@pytest.mark.parametrize(
    "text",
    [
        "vacía mi lista de la compra",
        "clear my to-do list",
        "borra la lista de la compra entera",
        "get rid of my packing list",
        "ya no necesito mi lista de la compra",
        "elimina esa lista",
        "delete this list please",
        "remove all of my lists",
        "clear out the shopping list",
        "limpiar mi lista de actividades para hoy",
        "deshazte de mi lista de tareas",
    ],
)
def test_a_whole_list_removed_is_a_plain_limit_never_a_read(text):
    removal = list_removal_request(text)
    assert removal is not None and removal.entry is None
    assert known_unsupported_effect_request(text, OPERATIONS) is True
    assert _decision(text) == ("conversation", "unsupported")
