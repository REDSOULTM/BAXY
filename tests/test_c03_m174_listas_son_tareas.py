"""M174 (2026-10-05, App run v5c; owner D59 and the decider's catalog «anotar algo en una lista (la del súper…)»): a
list of the super, of the market or for a trip is a list of tasks, and «agrégale X» puts X on it.

1. DEV-D D-w03-t1 «lista del super: pan, palta y lece» → the decider made a note «Lista del súper». The list named with
   no verb and its entries after a colon is now read as those entries on that list (``notes._LIST_HEADING``).
2. DEV-D D-w03-t2 «agrega tomates tmb» → note.update failed; DEV-H H-w10-t2 «Agrégale bloqueador, gafas y el cargador del
   parlante» right after «Crea una lista para el paseo a Santa Marta» → task.update asking «¿Qué nombre o título deseas
   cambiar…?». Entries added with no list named, right after the person made or filled a list, go on that list, one
   task each (``notes.entries_on_a_list``; the decider's task.update / note.* is corrected in ``_context_decided_result``).
3. DEV-H H-s116 «Ey, anótame en la lista del mercado plátano maduro, arepas de chócolo y queso costeño, ¿sí?» → three
   task.create decided by the readers, then the plan asked «¿Qué título le darías a esta lista…?»: the plan re-read the
   objective without the address and the tag the decision read around (``_plan_effects_read``).
4. DEV-H H-w04-t3 «espera, el jamón no, mejor queso» after «apunta ahí pan, leche y jamón» → task.update of the list's
   own task with nothing changed (final «Lista para la compra del finde»). The entries a plan put on the list are now
   known as verified (``DialogueState._keep_entry``), and the change of one for another names the one changed
   (``DialogueState.changed_entry``, ``notes._TITLE_INSTEAD``).
5. DEV-H H-w30-t1 «anota en mis pendientes pagar la luz» → a note beside the task: the person's pendientes are tasks.

Diagnosed, not changed: G-w15-t3 «no era ese, era el de la lus» (the task completed by mistake reopened and another
completed) is a correction of a completion, not a list; the lived store has no task of «luz» at all.
Rows are quoted with their real text and the history the App lived; every other phrasing is our own.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind.semantic.notes import entries_on_a_list, list_entries, task_change
from baxy_mind.semantic.patterns import resolve_explicit_effects

OPERATIONS = tuple(
    json.loads(
        (pathlib.Path(sidecar.__file__).parent / "data" / "decider_catalog.es.v1.json").read_text(encoding="utf-8")
    )["operations"]
)
TASK_CREATE = {"type": "object", "properties": {
    "details": {"type": "string", "x-maxUtf8Bytes": 65536},
    "due": {"type": ["null", "string"], "maxLength": 64},
    "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
}, "required": ["title"], "additionalProperties": False}
TASK_UPDATE = {"type": "object", "properties": {
    "details": {"type": "string", "x-maxUtf8Bytes": 65536},
    "due": {"type": ["null", "string"], "maxLength": 64},
    "expectedVersion": {"type": "integer", "minimum": 1},
    "taskId": {"type": "string", "maxLength": 36, "x-nonWhitespace": True},
    "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
}, "required": ["details", "due", "expectedVersion", "taskId", "title"], "additionalProperties": False}


class _Decider:
    """The model of a whole turn: the decider answers what it is given; every other call is neutral."""

    _native_tool_policy_enabled = False

    def __init__(self, decision: ContextDecision | None = None) -> None:
        self.decision = decision
        self.decisions = 0

    def decide_in_context(self, *_a, **_k):
        self.decisions += 1
        if self.decision is None:
            raise AssertionError("the decider was not to be asked")
        return self.decision

    def formulate_explicit_clarification_question(self, *_a, **_k):
        return "¿Qué?"

    def formulate_missing_argument_question(self, *_a, **_k):
        return "¿Qué cambio?"

    def clarify_after_turn_failure(self, *_a, **_k):
        return "¿Qué necesitas?"

    def public_lookup_requested(self, _text):
        return False

    def operation_is_the_requested_effect(self, *_a, **_k):
        return True

    def _verify_semantic_effect_shape(self, _text):
        return "no_effect", "zero"

    def chat(self, *_a, **_k):
        return "Respuesta.", []

    def prepare_chat(self, *_a, **_k):
        return None

    def prepare_decision(self, *_a, **_k):
        return None

    def detect_response_language(self, _text):
        return "es"

    def consume_deferred_response_language(self, _text):
        return True, None

    def retire_deferred_response_language(self, _text):
        return None

    def __getattr__(self, name):
        def missing(*_a, **_k):
            raise RuntimeError(f"no {name} here")
        return missing


def _tool(name: str) -> dict:
    schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    return {"type": "function", "function": {"name": name.replace(".", "_"), "canonical_name": name,
                                             "description": name, "risk": "read_only", "parameters": schema}}


def _turn(text: str, said: list[str], decision: tuple[str, tuple[str, ...], str] | None = None) -> tuple[dict, int]:
    """The turn as the App asks it: ``said`` alternates the person and BAXY before ``text``; ``decision`` is what the
    contextual decider answers (mode, operations, restatement)."""

    model = _Decider(None if decision is None else ContextDecision(
        request=decision[2], decision=decision[0], operations=decision[1], question="",
    ))
    history = [{"role": "user" if index % 2 == 0 else "assistant", "content": item} for index, item in enumerate(said)]
    tools = {name: _tool(name) for name in OPERATIONS}
    result = sidecar._prepare_turn_result(
        {"id": "m174", "text": text, "history": [*history, {"role": "user", "content": text}]},
        llm=model, planner_catalog=PlannerCatalog(list(tools.values())), encoder=lambda _t: (), tool_by_name=tools,
        dialogue_state=DialogueState(),
    )
    return result, model.decisions


def _read(text: str) -> tuple[str, ...] | None:
    found = resolve_explicit_effects(text, OPERATIONS)
    return None if found is None else tuple(found.operations)


def _planned_entries(objective: str, count: int) -> list[dict | None]:
    """Each task.create step of the plan the App asks for, grounded as the plan request grounds a literal step."""

    expected = ("task.create",) * count
    found = sidecar._plan_effects_read(objective, expected, OPERATIONS, [{"role": "user", "content": objective}])
    assert found is not None
    evidence = sidecar._restore_evidence_surfaces(
        objective, sidecar._evidence_of_expected_operations(expected, found.operations, found.evidence),
    )
    return [sidecar._ground_explicit_arguments("task.create", clause, TASK_CREATE) for clause in evidence]


# ------------------------------------------------------------------ 1. a list written down with a colon


def test_d_w03_t1_a_list_with_its_entries_after_a_colon_is_tasks() -> None:
    text = "lista del super: pan, palta y lece"  # D-w03-t1
    result, decisions = _turn(text, [])
    assert decisions == 0 and result["effectOperations"] == ["task.create"] * 3
    assert list_entries(text) == (("pan", "palta", "lece"), "lista del super")
    assert _planned_entries(text, 3) == [
        {"title": "pan", "details": "lista del super"},
        {"title": "palta", "details": "lista del super"},
        {"title": "lece", "details": "lista del super"},
    ]


@pytest.mark.parametrize(
    ("text", "entries", "listed"),
    [
        ("lista del mercado: arroz, frijoles y panela", ("arroz", "frijoles", "panela"), "lista del mercado"),
        ("pa la lista del super: dos paltas hass, marraqueta y queso", ("dos paltas hass", "marraqueta", "queso"),
         "lista del super"),
        ("shopping list: eggs, oat milk and bread", ("eggs", "oat milk", "bread"), "shopping list"),
        ("lista del super: pan", ("pan",), "lista del super"),
    ],
)
def test_variants_of_a_list_written_down(text: str, entries: tuple[str, ...], listed: str) -> None:
    assert list_entries(text) == (entries, listed)
    assert _read(text) == ("task.create",) * len(entries)


@pytest.mark.parametrize(
    ("text", "operations"),
    [
        # A note asked for by its word stays a note, whatever list it holds.
        ("crea una nota con la lista de invitados: Ana, Pedro y Luis", ("note.create",)),
        # Songs are music, never tasks; a list named as content to write is the decider's.
        ("lista de canciones: Despacito y Bailando", None),
        ("lista de las mejores películas: Alien y Titanic", None),
    ],
)
def test_what_is_not_a_list_of_tasks_is_unchanged(text: str, operations: tuple[str, ...] | None) -> None:
    assert _read(text) == operations


# ------------------------------------------------------------------ 2. «agrégale X» to the list just made


H_W10 = ["Crea una lista para el paseo a Santa Marta",
         "He creado la lista «Lista para el paseo a Santa Marta» que está vacía, ¿te gustaría añadir algo?"]
D_W03 = ["lista del super: pan, palta y lece", "He añadido pan, palta y leche a la lista del súper."]


def test_h_w10_t2_entries_added_to_the_list_just_made() -> None:
    text = "Agrégale bloqueador, gafas y el cargador del parlante"  # H-w10-t2, decided task.update in v5c
    restated = "Agrega bloqueador, gafas y el cargador del parlante a la lista «Lista para el paseo a Santa Marta»."
    result, _ = _turn(text, H_W10, ("action", ("task.update",), restated))
    assert result["effectOperations"] == ["task.create"] * 3
    assert result["objective"] == "añade bloqueador, gafas y el cargador del parlante a la lista para el paseo a Santa Marta"
    assert _planned_entries(result["objective"], 3) == [
        {"title": "bloqueador", "details": "lista para el paseo a Santa Marta"},
        {"title": "gafas", "details": "lista para el paseo a Santa Marta"},
        {"title": "cargador del parlante", "details": "lista para el paseo a Santa Marta"},
    ]


def test_d_w03_t2_one_more_entry_to_the_list_written_before() -> None:
    text = "agrega tomates tmb"  # D-w03-t2, decided note.update in v5c
    result, _ = _turn(text, D_W03, ("action", ("note.update",), "Agrega tomates a la nota «Lista del súper»."))
    assert result["kind"] == "action" and result["operation"] == "task.create"
    assert result["objective"] == "añade tomates a la lista del super"
    assert sidecar._ground_explicit_arguments("task.create", result["objective"], TASK_CREATE) == {
        "title": "tomates", "details": "lista del super",
    }


@pytest.mark.parametrize(
    ("said", "text", "restated", "count"),
    [
        (["creame una lista para el asado del domingo"], "súmale carbón y chorizos también",
         "añade carbón y chorizos a la lista para el asado del domingo", 2),
        (["make a packing list"], "add sunscreen and towels too", "add sunscreen and towels to the packing list", 2),
        # Two additions in a row: the list is the one made before the first.
        (["anota en la lista del mercado arroz y panela", "agrégale café"], "y agrégale papas",
         "añade papas a la lista del mercado", 1),
    ],
)
def test_variants_of_entries_added_after_the_list(said: list[str], text: str, restated: str, count: int) -> None:
    assert entries_on_a_list(text, said[::-1]) == (restated, count)


@pytest.mark.parametrize(
    ("said", "text", "decision"),
    [
        # M160: the note just made takes the addition; no list was made.
        (["crea una nota que diga ideas para el cumpleaños de juliana",
          "He guardado la nota con el título \"ideas para el cumpleaños de juliana\"."],
         "agrégale que quiero comprarle un ramo de flores",
         ("action", ("note.update",),
          "Agrega «quiero comprarle un ramo de flores» a la nota «ideas para el cumpleaños de juliana».")),
        # The same addition with no list before it is the decider's.
        (["¿qué tiempo hace hoy?", "Hoy hace sol."], "agrega tomates tmb",
         ("action", ("note.update",), "Agrega tomates a la nota.")),
        # A note named by its word stays a note even right after a list.
        (D_W03, "agrega tomates a la nota de la compra",
         ("action", ("note.update",), "Agrega tomates a la nota de la compra.")),
        # The decider that already put the entries on the list is kept as it said it.
        (H_W10, "Agrégale bloqueador", ("action", ("task.create",), "Añade bloqueador a la lista para el paseo.")),
        # «cámbiale el nombre» is a change of the list itself (M80), not an entry.
        (H_W10, "cámbiale el nombre a paseo a Taganga",
         ("action", ("task.update",), "Cambia el nombre de la lista a «paseo a Taganga».")),
    ],
)
def test_what_is_no_entry_of_the_list_just_made_keeps_its_decision(
    said: list[str], text: str, decision: tuple[str, tuple[str, ...], str],
) -> None:
    result, decisions = _turn(text, said, decision)
    assert decisions == 1
    assert result["effectOperations"] == list(decision[1]) and result["objective"] == decision[2]


# ------------------------------------------------------------------ 3. the plan reads the order the decision read


def test_h_s116_the_plan_reads_the_entries_inside_the_address_and_the_tag() -> None:
    text = "Ey, anótame en la lista del mercado plátano maduro, arepas de chócolo y queso costeño, ¿sí?"  # H-s116
    assert resolve_explicit_effects(text, OPERATIONS) is None  # what the plan read before: nothing, so it asked
    assert _planned_entries(text, 3) == [
        {"title": "plátano maduro", "details": "lista del mercado"},
        {"title": "arepas de chócolo", "details": "lista del mercado"},
        {"title": "queso costeño", "details": "lista del mercado"},
    ]


@pytest.mark.parametrize(
    ("text", "entries"),
    [
        ("oye, apúntame en la lista de la compra leche, pan y huevos, ¿vale?",
         [("leche", "lista de la compra"), ("pan", "lista de la compra"), ("huevos", "lista de la compra")]),
        ("hey, add eggs and milk to my shopping list, please", [("eggs", "shopping list"), ("milk", "shopping list")]),
    ],
)
def test_variants_of_a_plan_inside_an_address(text: str, entries: list[tuple[str, str]]) -> None:
    assert [(found["title"], found["details"]) for found in _planned_entries(text, len(entries))] == entries


def test_a_plan_read_on_its_own_is_read_as_before() -> None:
    text = "añade pan y leche a la lista de la compra"
    found = sidecar._plan_effects_read(text, ("task.create",) * 2, OPERATIONS, [])
    assert found == resolve_explicit_effects(text, OPERATIONS)
    # One operation keeps the whole objective as its evidence (the argument binder reads the forms itself).
    assert sidecar._plan_effects_read("oye, qué tal", ("task.create",), OPERATIONS, []) is None


# ------------------------------------------------------------------ 4. one entry changed for another


def _state_after_the_entries(entries: tuple[str, ...], details: str) -> DialogueState:
    """«crea una lista para la compra del finde» and then a plan of one task.create per entry, as the App composes."""

    state = DialogueState()
    state.expect("crea una lista para la compra del finde", ["task.create"])
    state.record({"kind": "operation", "operation": "task.create", "polarity": "success", "verified": True,
                  "succeeded": True, "observed": {"taskId": "list", "title": "Lista para la compra del finde",
                                                  "details": "", "completed": False, "deleted": False, "version": 1}})
    state.expect("Añade pan, leche y jamón a la lista de la compra.", ["task.create"] * len(entries))
    state.record({"kind": "status", "polarity": "success", "cause": "mission_completed", "steps": [json.dumps({
        "kind": "operation", "operation": "task.create", "polarity": "success", "verified": True, "succeeded": True,
        "observed": {"taskId": f"t{index}", "title": entry, "details": details, "completed": False, "deleted": False,
                     "version": 1}}) for index, entry in enumerate(entries)]})
    return state


def test_h_w04_t3_the_entry_taken_back_is_the_one_changed() -> None:
    state = _state_after_the_entries(("pan", "leche", "jamón"), "lista de la compra")
    person = "espera, el jamón no, mejor queso"  # H-w04-t3
    objective = "Cambia jamón por queso en la lista de la compra."  # its v5c restatement
    edited = state.changed_entry(person, objective)
    assert edited == {"taskId": "t2", "expectedVersion": 1, "title": "jamón", "details": "lista de la compra",
                      "due": None}
    arguments, question = sidecar._edited_task_arguments(
        _Decider(), objective, person, {"type": "function", "function": {"parameters": TASK_UPDATE}}, edited,
        person, "es",
    )
    assert question == "" and arguments == {
        "taskId": "t2", "expectedVersion": 1, "title": "queso", "details": "lista de la compra", "due": None,
    }


@pytest.mark.parametrize(
    ("text", "old", "new"),
    [
        ("no el jamón, mejor queso", "jamón", "queso"),
        ("la leche no, sino leche de avena", "leche", "leche de avena"),
        ("not the ham, cheese instead", "ham", "cheese"),
        ("no ham, make it cheese", "ham", "cheese"),
    ],
)
def test_variants_of_one_entry_for_another(text: str, old: str, new: str) -> None:
    state = _state_after_the_entries(("pan", old, "huevos"), "lista de la compra")
    assert state.changed_entry(text)["title"] == old
    assert task_change(text, old) == {"title": new}


def test_a_change_that_names_no_entry_keeps_the_task_just_made() -> None:
    state = _state_after_the_entries(("pan", "leche"), "lista de la compra")
    # No entry is called «jamón»: the change is of the task this conversation last made or changed (M80), as before.
    assert state.changed_entry("el jamón no, mejor queso") is None
    assert state.edited_task()["taskId"] == "list"
    # «No, cámbialo a la lista Comida» (M80, D-p08-t3) still moves the task, and names no entry.
    assert state.changed_entry("No, cámbialo a la lista Comida") is None
    # Two entries by the same name: none is guessed.
    assert _state_after_the_entries(("pan", "pan"), "lista").changed_entry("el pan no, mejor marraqueta") is None


# ------------------------------------------------------------------ 5. the person's pendientes are tasks


@pytest.mark.parametrize(
    "text",
    [
        "anota en mis pendientes pagar la luz",  # H-w30-t1
        "apúntame en pendientes llamar al banco",
        "anótame en los pendientes renovar el carnet",
    ],
)
def test_h_w30_t1_what_goes_on_the_pendientes_is_a_task(text: str) -> None:
    assert _read(text) == ("task.create",)


@pytest.mark.parametrize(
    ("text", "operations"),
    [
        ("anota que mañana llamo al banco", ("note.create",)),
        ("anota en una nota mis pendientes de la semana", ("note.create",)),
        ("lee mi lista", ("task.list",)),
    ],
)
def test_notes_and_reads_are_unchanged(text: str, operations: tuple[str, ...]) -> None:
    assert _read(text) == operations
