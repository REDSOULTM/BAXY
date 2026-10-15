"""Destino del pedido (pasada r15b): the engine never had the right place in t-file-1, t-menu-4 and v3-47.

- t-file-1 «guardá esto como baxy-nota1.txt en Documentos, en la carpeta baxy-prueba-v3»: the shell's welcome («Hola,
  soy BAXY…») was the only assistant turn of the history and counted as a reply of BAXY's, so the guard that hands a
  save of what the window shows to the engine never applied and a new file was about to be written with the request as
  its text. Only a reply after a turn of the person's is an antecedent of «esto» (``_baxy_replied``).
- t-menu-4 «Gira la imagen 90 grados a la derecha desde el menú Imagen > Girar»: the decider chose one
  ``input.visible.click`` {label: Imagen} for the two pieces of the route, on the window in front. A route the person
  says is the engine's order (``missions.clicks_a_route``).
- v3-47 «abre system information, copia el nombre del procesador y pégalo en una página nueva de onenote»: the second
  clause carried «Información del sistema» from the first; it names OneNote and happens there.

The payloads are the ones of the r15b run (turn_audit.jsonl of each case), frozen here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from baxy_mind import known_folders
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import missions
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind import turn_history
from baxy_mind import engine_handoff
from baxy_mind import context_decision

ROOT = Path(__file__).resolve().parents[1]
START_APPS = tuple(
    json.loads((ROOT / "tests" / "data" / "cu_v3_start_catalog.v1.json").read_text(encoding="utf-8"))["names"]
)
_DOCUMENTS = r"D:\Perfil\Documentos"
_WELCOME = {"role": "assistant", "content": "Hola, soy BAXY. ¿En qué te ayudo?"}


def _tool(operation: str) -> dict[str, Any]:
    schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    return {"type": "function", "function": {"name": operation.replace(".", "_"), "canonical_name": operation,
                                             "description": operation, "risk": "read_only", "parameters": schema}}


@pytest.fixture
def documents(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(known_folders, "known_folder", lambda folder: {"documents": _DOCUMENTS}.get(folder))
    monkeypatch.setattr(missions, "_file_taken", lambda _path: False)


# ------------------------------------------------------------------------------------------------------ t-file-1

T_FILE_1 = "guardá esto como baxy-nota1.txt en Documentos, en la carpeta baxy-prueba-v3"


def test_the_welcome_is_no_reply_of_baxys() -> None:
    assert not turn_history._baxy_replied([_WELCOME, {"role": "user", "content": T_FILE_1}])
    assert not turn_history._baxy_replied([_WELCOME])
    # Contracase: a reply after a turn of the person's is one.
    assert turn_history._baxy_replied([
        _WELCOME, {"role": "user", "content": "escribime un poema"},
        {"role": "assistant", "content": "El mar susurra azul…"}, {"role": "user", "content": "guardá esto"},
    ])


def test_a_reply_whose_turn_the_window_left_out_is_still_a_reply() -> None:
    # Revisión destino del pedido (hallazgo 6): the App sends the last twelve messages; eleven of BAXY's in a row
    # leave out the person's turn they answer, and they are still replies.
    window = [{"role": "assistant", "content": f"Parte {index} del poema…"} for index in range(11)]
    assert turn_history._baxy_replied([*window, {"role": "user", "content": T_FILE_1}])
    # Contracase: a short conversation headed by the welcome has no reply.
    assert not turn_history._baxy_replied([_WELCOME, _WELCOME, {"role": "user", "content": T_FILE_1}])


def test_t_file_1_with_the_welcome_saves_what_the_window_shows(documents: None) -> None:
    tools = {operation: _tool(operation) for operation in (
        "clipboard.read.text", "filesystem.write.text", "mission.computer.use")}
    # r15b turn_audit: the decider's plan, with the request rewritten as the text to write.
    decided = {
        "type": "turn.result", "id": "6", "kind": "plan", "operation": None,
        "intentOperations": ["clipboard.read.text", "filesystem.write.text"],
        "effectOperations": ["clipboard.read.text", "filesystem.write.text"],
        "question": "", "reply": "", "objective": "Guardá el texto actual en baxy-nota1.txt en Documentos/baxy-prueba-v3.",
    }
    history = [_WELCOME, {"role": "user", "content": T_FILE_1}]
    handed = engine_handoff._engine_for_an_unserved_order(
        decided, {"id": "6", "text": T_FILE_1, "history": history}, tools, START_APPS)
    assert handed["effectOperations"] == ["mission.computer.use"]
    assert handed["objective"] == T_FILE_1
    arguments = missions.free_form_arguments(T_FILE_1, START_APPS, turn_history._prior_user_requests(history))
    assert arguments is not None
    # Ronda 23: «esto» of a save is never the window in front named as the destination. Estabilización L: nor a window
    # the shell guesses among the open ones (the save referent is retired): with no application the mission acts in no
    # window and asks which (computer_use_no_application).
    assert "frontWindow" not in arguments and not any(key.startswith("referent") for key in arguments)
    assert arguments.get("successCheck") == (
        rf"file:{_DOCUMENTS}\baxy-prueba-v3\baxy-nota1.txt&title:baxy-nota1"
    )


def test_contracase_after_a_real_reply_the_save_stays_the_typed_write(documents: None) -> None:
    tools = {operation: _tool(operation) for operation in ("filesystem.write.text", "mission.computer.use")}
    said = "guardá esto como poema.txt en documentos"
    decided = {
        "type": "turn.result", "id": "8", "kind": "action", "operation": "filesystem.write.text",
        "intentOperations": ["filesystem.write.text"], "effectOperations": ["filesystem.write.text"],
        "question": "", "reply": "", "objective": "Guardar el poema en documentos/poema.txt",
    }
    history = [
        _WELCOME, {"role": "user", "content": "escribime un poema corto sobre el mar"},
        {"role": "assistant", "content": "El mar susurra azul, la espuma canta lenta…"},
        {"role": "user", "content": said},
    ]
    kept = engine_handoff._engine_for_an_unserved_order(decided, {"id": "8", "text": said, "history": history}, tools, START_APPS)
    assert kept["effectOperations"] == ["filesystem.write.text"]


# ------------------------------------------------------------------------------------------------------ t-menu-4

T_MENU_4 = "Gira la imagen 90 grados a la derecha desde el menú Imagen > Girar"
_PAINT_APPS = ("BAXY", "Bloc de notas", "Paint", "Mapa de caracteres", "Microsoft Word")


class _Decider:
    _native_tool_policy_enabled = False

    def __init__(self, decision: ContextDecision) -> None:
        self.decision = decision

    def decide_in_context(self, *_a, **_k):
        return self.decision

    def prepare_decision(self, *_a, **_k):
        return None

    def operation_is_the_requested_effect(self, *_a, **_k):
        return True

    def detect_response_language(self, _text):
        return "es"

    @staticmethod
    def chat(*_a, **_k):
        return "Hola.", []

    def __getattr__(self, name):
        def missing(*_a, **_k):
            raise RuntimeError(f"no {name} here")
        return missing


def _decided(text: str, decision: ContextDecision) -> dict[str, Any]:
    operations = ("input.visible.click", "app.open", "mission.computer.use")
    catalog = PlannerCatalog([_tool(name) for name in operations])
    return context_decision._context_decided_result(
        {"id": "menu", "text": text, "history": [_WELCOME, {"role": "user", "content": text}]},
        llm=_Decider(decision), planner_catalog=catalog, application_names=_PAINT_APPS,
    )


def test_t_menu_4_a_route_said_is_the_engines_never_one_click() -> None:
    assert missions.clicks_a_route(T_MENU_4)
    # r15b turn_audit: one click for the route, restated with two clicks in it.
    decision = ContextDecision(
        "En la ventana de Imagen, haz clic en «Imagen» y luego en «Girar».", "action", ("input.visible.click",), "",
    )
    result = _decided(T_MENU_4, decision)
    assert result.get("effectOperations") == ["mission.computer.use"], result


@pytest.mark.parametrize("text", ["hacé clic en Imagen", "abrí el menú Archivo", "click the OK button"])
def test_contracase_one_click_said_stays_one_click(text: str) -> None:
    assert not missions.clicks_a_route(text)


# Revisión destino del pedido: the route read the same in both languages, its pieces as said.
@pytest.mark.parametrize(("text", "pieces"), [
    ("haz clic en Archivo > Guardar como", ["archivo", "guardar como"]),
    ("click File > Save as", ["file", "save as"]),
    ("click on File > Save as", ["file", "save as"]),
    ("Rotate the image 90 degrees right from the Image > Rotate menu", ["image", "rotate"]),
])
def test_a_route_is_read_alike_in_spanish_and_english(text: str, pieces: list[str]) -> None:
    assert missions.clicks_a_route(text)
    route = missions._route(missions.fold(" ".join(text.split())))
    assert route is not None and route[1] == pieces


def test_english_rotate_keeps_which_way_as_its_sub_goal_like_spanish() -> None:
    for text, order in (
        ("Rotate the image 90 degrees right from the Image > Rotate menu", "rotate the image 90 degrees right"),
        (T_MENU_4, "gira la imagen 90 grados a la derecha"),
    ):
        reads = missions._compound_reads(missions.fold(text))
        assert reads is not None and (order, None, True) in reads, reads
    # Contracase: an order the route's last entry says whole is the route («Zoom in» twice).
    reads = missions._compound_reads(missions.fold("zoom in twice using View > Zoom > Zoom in"))
    assert reads is not None and not any(free for _, _, free in reads), reads


# ------------------------------------------------------------------------------------------------------ v3-47

V3_47 = "abre system information, copia el nombre del procesador y pégalo en una página nueva de onenote"


def test_v3_47_the_clause_that_names_onenote_happens_in_onenote() -> None:
    mission = missions.mission_request(V3_47, START_APPS)
    assert mission is not None
    assert [step.application for step in mission.steps] == ["Información del sistema", "OneNote"]


def test_contracase_a_clause_naming_no_application_keeps_the_one_before() -> None:
    mission = missions.mission_request(
        "abre system information, copia el nombre del procesador y pégalo en el portapapeles", START_APPS)
    assert mission is None or all(
        step.application in (None, "Información del sistema") for step in mission.steps
    )


@pytest.mark.parametrize("text", [
    "open system information, copy the processor name and paste it into a new page of onenote",
    "open system information, copy the processor name and paste it in a new onenote page",
])
def test_v3_47_in_english_the_place_said_is_onenote(text: str) -> None:
    mission = missions.mission_request(text, START_APPS)
    assert mission is not None
    assert [step.application for step in mission.steps] == ["Información del sistema", "OneNote"]


# Revisión destino del pedido: a name the clause only mentions is what it is about, never the place it happens in.
@pytest.mark.parametrize(("text", "elsewhere", "kept"), [
    ("abre la calculadora y calcula cuánto cuesta spotify por 12 meses", "Spotify", "Calculadora"),
    ("abre word, haz una tabla comparando excel y onenote", "Excel", "Word"),
    ("abre paint, dibuja el logo de google chrome", "Google Chrome", None),
])
def test_contracase_an_application_only_mentioned_is_no_destination(text: str, elsewhere: str, kept: str | None) -> None:
    mission = missions.mission_request(text, START_APPS)
    places = (
        [] if mission is None else [step.application for step in mission.steps] if mission.steps
        else [mission.application]
    )
    assert elsewhere not in places, places
    assert places == ([kept] if kept else []), places


def _places(text: str) -> list[str | None]:
    mission = missions.mission_request(text, START_APPS)
    return (
        [] if mission is None else [step.application for step in mission.steps] if mission.steps
        else [mission.application]
    )


# Revisión destino del pedido: the owner said after «de»/«of» is where the clause happens, never the place's own noun
# even when that noun names an installed application too («configuración» / «settings»).
@pytest.mark.parametrize("text", [
    "abre word, cambia la fuente predeterminada en la configuración de word",
    "open word, change the default font in the settings of word",
])
def test_contracase_the_owner_said_wins_over_the_places_noun(text: str) -> None:
    places = _places(text)
    assert "Configuración" not in places, places
    assert all(place == "Word" for place in places), places


def test_the_owner_in_spanish_keeps_the_application_said_first() -> None:
    assert _places("abre word, cambia la fuente predeterminada en la configuración de word") == ["Word"]


@pytest.mark.parametrize("text", [
    "abre word, cambia el brillo en la configuración de pantalla",
    "open word, change the brightness in the settings of the display",
])
def test_contracase_a_place_whose_owner_is_no_application_says_none(text: str) -> None:
    places = _places(text)
    assert "Configuración" not in places, places


@pytest.mark.parametrize(("text", "place"), [
    ("abre word y pégalo en el bloc de notas", "Bloc de notas"),
    ("abre word, pégalo en la configuración", "Configuración"),
])
def test_a_whole_name_said_as_the_place_is_still_the_place(text: str, place: str) -> None:
    assert _places(text) == ["Word", place]
