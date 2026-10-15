"""Lectura del pedido y ruta (pasada r9): v3-61 and v3-47 on their real views, with counter-cases.

- v3-61 «en seguridad de windows decime cuándo fue el último examen de virus»: the mission «abrir Seguridad de Windows;
  y responder: …» ended reached with 0 steps on the start page, where the datum is not. The step's goal is now the
  question itself (``question_step_goal``), and the shell no longer ends such a goal on the window's title alone
  (``ComputerUseMission.QuestionUnlookedFor``, its loop tests).
- v3-47 «abre system information, copia el nombre del procesador…»: the model asked to reveal «AMD Ryzen 7 5800H…»
  while the view already showed it; the reveal scrolled it away twice and the mission stopped. A reveal of what the
  view shows is refused with that reason and the model is asked again (``already_in_view``).

The views are the ones the model was shown in the r9 run (model_calls.jsonl of each case: window, the controls listed
and the text by zone), frozen here.
"""

from __future__ import annotations

import json

from typing import Any

import pytest

from baxy_mind import computer_use as cu
from baxy_mind import cu_goals
from baxy_mind import cu_validate
from baxy_mind import known_folders
from baxy_mind import compose_situation
from baxy_mind.semantic import decider, missions
from baxy_mind.semantic.missions import QUESTION_MARK
from baxy_mind import engine_handoff

_APPS = ("Seguridad de Windows", "Información del sistema", "OneNote")


def _tool(operation: str) -> dict[str, Any]:
    schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    return {"type": "function", "function": {"name": operation.replace(".", "_"), "canonical_name": operation,
                                             "description": operation, "risk": "read_only", "parameters": schema}}


def _control(index: int, kind: str, name: str, state: str = "", zone: str = "C") -> dict:
    return {"i": index, "kind": kind, "name": name, "state": state, "zone": zone}


# v3-61, first look (the frozen view of the case: «Inicio» selected, the sections and their summaries).
_SECURITY_START = {
    "window": {"title": "Seguridad de Windows", "process": "SecHealthUI", "requested": True, "foreground": False},
    "controls": [
        _control(0, "ListItem", "Inicio", "selected", "TL"),
        _control(1, "ListItem", "Protección contra virus y amenazas", "", "TL"),
        _control(2, "ListItem", "Protección de cuentas", "", "TL"),
        _control(3, "ListItem", "Firewall y protección de red", "", "TL"),
        _control(4, "ListItem", "Historial de protección", "", "L"),
        _control(5, "ListItem", "Protección contra virus y amenazas, No se requiere ninguna acción.", "", "C"),
    ],
    "text": {"C": ["Seguridad de un vistazo", "Protección contra virus y amenazas", "No se requiere ninguna acción."]},
}
_SECURITY_VIRUS = {
    **_SECURITY_START,
    "controls": [
        _control(0, "ListItem", "Inicio", "", "TL"),
        _control(1, "ListItem", "Protección contra virus y amenazas", "selected", "TL"),
        _control(2, "ListItem", "Protección de cuentas", "", "TL"),
    ],
    "text": {"C": ["Amenazas actuales", "Último examen: 08-10-2026 10:28 (examen rápido)"]},
}
_V3_61_GOAL = "abrir Seguridad de Windows" + QUESTION_MARK + "decime cuándo fue el último examen de virus"

# v3-47, the view after app.open (model call 14 of the r9 run): the row «Procesador» listed and its value written in
# the centre zone.
_MSINFO = {
    "window": {"title": "Información del sistema", "process": "msinfo32", "requested": True},
    "controls": [
        _control(0, "TreeItem", "Resumen del sistema", "selected expanded", "TL"),
        _control(1, "TreeItem", "Recursos de hardware", "collapsed", "TL"),
        _control(2, "TreeItem", "Componentes", "collapsed", "TL"),
        _control(8, "Edit", "Buscar esto:", "", "B"),
        _control(21, "DataGrid", "Resumen del sistema", "", "C"),
        _control(27, "DataItem", "Nombre del SO", "selected", "T"),
        _control(28, "Text", "Nombre del SO", "", "T"),
        _control(29, "Text", "Microsoft Windows 11 Home Single Language", "", "T"),
        _control(53, "DataItem", "Procesador", "", "C"),
        _control(54, "Text", "Procesador", "", "C"),
    ],
    "text": {
        "T": ["Elemento", "Valor", "Nombre del SO", "Microsoft Windows 11 Home Single Language"],
        "C": ["Tipo de sistema", "x64-based PC", "Procesador",
              "AMD Ryzen 7 5800H with Radeon Graphics, 3201 Mhz, 8 procesadores prin...",
              "Versión y fecha de BIOS"],
    },
}
_OPENED = [{"step": 1, "operation": "app.open", "ok": True, "appId": "Información del sistema"}]


class _ScriptedModel:
    """The model's replies in order; every payload it was sent is kept."""

    def __init__(self, *replies: dict) -> None:
        self.replies = list(replies)
        self.payloads: list[dict] = []

    def _post_schema_object(self, payload: dict, _what: str) -> dict:
        self.payloads.append(json.loads(json.dumps(payload)))
        return self.replies.pop(0)


def _decide(model: _ScriptedModel, *, objective: str, goal: str, application: str, view: dict, history: list[dict],
            success_check: str | None = None) -> dict:
    return cu.decide_step(
        model, objective=objective, goal=goal, application=application, success_check=success_check, view=view,
        history=history, budget_left=9, application_names=_APPS,
    )


# ------------------------------------------------------------------ v3-61: the question is the step's goal


def test_a_goal_that_only_opens_the_application_works_on_its_question() -> None:
    assert cu_goals.question_step_goal(_V3_61_GOAL, "Seguridad de Windows") == (
        cu_goals.QUESTION_LOOK + "decime cuándo fue el último examen de virus")
    assert cu_goals.question_step_goal("open Task Manager" + QUESTION_MARK + "which ones have high impact", "Task Manager") == (
        cu_goals.QUESTION_LOOK + "which ones have high impact")


def test_contracase_a_goal_that_does_something_keeps_its_own_steps() -> None:
    # «escribir hola; y responder: …» types «hola»; a place goes to the place; a file is opened (v3-18); opening
    # another application than the mission's is no look at it; a goal without a question is itself.
    app = "Seguridad de Windows"
    assert cu_goals.question_step_goal("escribir hola" + QUESTION_MARK + "decime si quedó", app) == "escribir hola"
    assert cu_goals.question_step_goal("ir a hora e idioma" + QUESTION_MARK + "qué zona horaria", app) == "ir a hora e idioma"
    opening = "abrir el archivo D:\\x\\paisaje.jpg"
    assert cu_goals.question_step_goal(opening + QUESTION_MARK + "tell me the dimensions", "Fotos") == opening
    assert cu_goals.question_step_goal("abrir Paint" + QUESTION_MARK + "qué color está elegido", app) == "abrir Paint"
    assert cu_goals.question_step_goal(_V3_61_GOAL, None) == "abrir Seguridad de Windows"
    assert cu_goals.question_step_goal("abrir Seguridad de Windows", app) == "abrir Seguridad de Windows"


def test_v3_61_the_model_is_asked_the_question_and_goes_to_the_page_that_shows_it() -> None:
    model = _ScriptedModel({"act": "click", "i": 1})
    decision = _decide(
        model, objective="en Seguridad de Windows, decime cuándo fue el último examen de virus", goal=_V3_61_GOAL,
        application="Seguridad de Windows", view=_SECURITY_START, history=[],
        success_check="title:Seguridad de Windows|process:Seguridad de Windows",
    )
    prompt = model.payloads[0]["messages"][1]["content"]
    assert "Objetivo: ver en la ventana: decime cuándo fue el último examen de virus" in prompt
    assert decision["operation"] == "input.visible.click"
    assert decision["arguments"]["label"] == "Protección contra virus y amenazas"


def test_v3_61_the_answer_on_screen_is_cited_without_an_act() -> None:
    # A question is a reading: its citation needs no act of the mission (the datum may be on the first look).
    model = _ScriptedModel({"act": "done", "evidence": "Último examen: 08-10-2026 10:28 (examen rápido)"})
    decision = _decide(
        model, objective="en Seguridad de Windows, decime cuándo fue el último examen de virus", goal=_V3_61_GOAL,
        application="Seguridad de Windows", view=_SECURITY_VIRUS, history=[],
    )
    assert decision["operation"] == "done"
    assert decision["arguments"]["evidence"] == "Último examen: 08-10-2026 10:28 (examen rápido)"


# ------------------------------------------------------------------ v3-47: what the view shows needs no reveal


def test_v3_47_a_reveal_of_the_value_already_on_screen_is_refused_and_asked_again() -> None:
    model = _ScriptedModel(
        {"act": "reveal", "text": "AMD Ryzen 7 5800H with Radeon Graphics, 3201 Mhz, 8 procesadores prin..."},
        {"act": "click", "text": "Procesador"},
    )
    decision = _decide(
        model, objective="abre system information, copia el nombre del procesador y pégalo en una página nueva de onenote",
        goal="copia el nombre del procesador", application="Información del sistema", view=_MSINFO, history=_OPENED,
    )
    assert len(model.payloads) == 2
    assert "ya está en la vista" in model.payloads[1]["messages"][-1]["content"]
    assert decision["operation"] == "input.visible.click"
    assert decision["arguments"]["label"] == "Procesador"


def test_v3_47_the_shorter_reveal_of_the_same_value_is_refused_too() -> None:
    refused = cu_validate.validate_decision(
        {"act": "reveal", "text": "AMD Ryzen 7 5800H with Radeon Graphics"}, view=_MSINFO, history=_OPENED,
        last_failed=None, application_names=_APPS, goal="copia el nombre del procesador",
    )
    assert refused["operation"] == "none" and refused["code"] == "already_in_view"


def test_contracase_a_reveal_of_what_the_view_does_not_show_still_brings_it_by_name() -> None:
    for name in ("Pantalla", "Versión de la placa base"):
        decided = cu_validate.validate_decision(
            {"act": "reveal", "text": name}, view=_MSINFO, history=_OPENED, last_failed=None,
            application_names=_APPS, goal="copia el nombre de la tarjeta de video",
        )
        assert decided["operation"] == "input.scroll", name
        assert decided["arguments"]["label"] == name, name


# ------------------------------------------------------------------ t-drag-1: the file said, and a measured cause

_T_DRAG_1 = "arrastrá lista.txt adentro de la carpeta archivo, en baxy-prueba-v3"


def test_t_drag_1_a_file_name_nobody_said_does_not_travel_as_the_objective() -> None:
    # r9: the decider restated «Mueve archivo.txt de la carpeta de trabajo a archivo/ en baxy-prueba-v3.» and the
    # move looked for «archivo.txt»; «archivo» and «.txt» were said, the file «archivo.txt» never was.
    fidelity = decider.faithful_request(
        "Mueve archivo.txt de la carpeta de trabajo a archivo/ en baxy-prueba-v3.", _T_DRAG_1, [])
    assert "archivo.txt" in fidelity.introduced
    assert "archivo.txt" not in fidelity.request
    assert "lista.txt" in fidelity.request


def test_contracase_the_file_said_and_a_web_address_keep_the_restatement() -> None:
    kept = decider.faithful_request("Mueve lista.txt a la carpeta archivo en baxy-prueba-v3.", _T_DRAG_1, [])
    assert (kept.kind, kept.request) == ("kept", "Mueve lista.txt a la carpeta archivo en baxy-prueba-v3.")
    # A file said earlier in the conversation is said; an address is no file.
    assert decider.faithful_request("Abre notas.txt.", "abrilo", ["creá notas.txt en documentos"]).kind == "kept"
    web = decider.faithful_request("Abre youtube.com en el navegador.", "abrí youtube en el navegador", [])
    assert "youtube.com" not in web.introduced


_DOCUMENTS = r"D:\Perfil\Documentos"
_SAVED_PATH = _DOCUMENTS + r"\baxy-prueba-v3\baxy-nota1.txt"


@pytest.fixture
def documents(monkeypatch: pytest.MonkeyPatch) -> None:
    # The case's known folder, and no file at the path yet (the live batch may have left one on this PC).
    monkeypatch.setattr(known_folders, "known_folder", lambda folder: {"documents": _DOCUMENTS}.get(folder))
    monkeypatch.setattr(missions, "_file_taken", lambda _path: False)


def test_t_file_1_saving_what_the_window_shows_is_its_save_as_on_the_window_in_front(documents: None) -> None:
    # r9: the decider chose clipboard.read.text + filesystem.write.text, with the request as the text and another
    # path. «guardá esto como N en C» is the window's own Save As: the engine, on the window «esto» points at.
    said = "guardá esto como baxy-nota1.txt en Documentos, en la carpeta baxy-prueba-v3"
    assert missions.saves_what_is_shown(said)
    assert missions.saves_what_is_shown("Save this drawing as baxy-dibujo.png in Documents\\baxy-prueba-v3")
    tools = {operation: _tool(operation) for operation in (
        "clipboard.read.text", "filesystem.write.text", "mission.computer.use")}
    decided = {
        "type": "turn.result", "id": "6", "kind": "plan", "operation": None,
        "intentOperations": ["clipboard.read.text", "filesystem.write.text"],
        "effectOperations": ["clipboard.read.text", "filesystem.write.text"],
        "question": "", "reply": "", "objective": "Guardá el texto actual en baxy-nota1.txt en Documentos/baxy-prueba-v3.",
    }
    handed = engine_handoff._engine_for_an_unserved_order(
        decided, {"id": "6", "text": said, "history": []}, tools, _APPS)
    assert handed["effectOperations"] == ["mission.computer.use"]
    assert handed["objective"] == said
    arguments = missions.free_form_arguments(said, _APPS)
    # Review of the branch (finding 5): the save is proved by the file at the path said, never by a title. Ronda 21
    # (destino por contenido): what is shown is a document with something to save, which the shell looks for. Ronda 23:
    # «esto» is that referent, never the window in front named as the destination (no frontWindow).
    # Estabilización L: no window is guessed among the open ones (the save referent is retired).
    assert arguments == {"goal": said, "successCheck": f"file:{_SAVED_PATH}&title:baxy-nota1"}
    # Contracase: a conversation already in an application saves there, not on whatever window is in front.
    follow_up = missions.free_form_arguments(
        "guardalo como prueba.txt", ("Bloc de notas", *_APPS), ["en el bloc de notas escribí hola"])
    assert follow_up == {"goal": "guardalo como prueba.txt", "application": "Bloc de notas"}


# ------------------------------------------------------------------ review of the branch, finding 1

_POEM_HISTORY = [
    {"role": "user", "content": "escribime un poema corto sobre el mar"},
    {"role": "assistant", "content": "El mar susurra azul, la espuma canta lenta…"},
]


def test_review_1_a_save_of_baxys_reply_is_never_the_window_in_front(documents: None) -> None:
    # The review's repro: after a poem, «guardalo como poema.txt en documentos» is M67's typed write of that reply;
    # neither the engine nor the person's window in front.
    tools = {operation: _tool(operation) for operation in ("filesystem.write.text", "mission.computer.use")}
    for said in ("guardalo como poema.txt en documentos", "guardá esto como poema.txt en documentos"):
        decided = {
            "type": "turn.result", "id": "8", "kind": "action", "operation": "filesystem.write.text",
            "intentOperations": ["filesystem.write.text"], "effectOperations": ["filesystem.write.text"],
            "question": "", "reply": "", "objective": "Guardar el poema en documentos/poema.txt",
        }
        kept = engine_handoff._engine_for_an_unserved_order(
            decided, {"id": "8", "text": said, "history": [*_POEM_HISTORY, {"role": "user", "content": said}]},
            tools, _APPS)
        assert kept["effectOperations"] == ["filesystem.write.text"], said
        # Were the engine chosen anyway, a reply of BAXY's before it leaves the window in front out.
        arguments = missions.free_form_arguments(said, _APPS)
        assert arguments is not None and "frontWindow" not in arguments, said


def test_review_1_only_a_word_pointing_at_the_screen_and_a_known_path_save_the_window(documents: None) -> None:
    # A pronoun or an article takes its antecedent from the conversation; another clause or a folder no reader knows
    # is no save the dialog reader resolves. None of them is the window in front.
    for said in (
        "guardalo como poema.txt",
        "guardalo como poema.txt en documentos",
        "save it as poem.txt in Documents",
        "guarda el texto como nota.txt en documentos",
        "guarda la receta como receta.txt en documentos",
        "guarda esto como x.txt y mandalo en whatsapp a Ana",
        "guardá esto como resumen.txt",
        "guardá esto como resumen.txt en la carpeta de Ana",
    ):
        assert not missions.saves_what_is_shown(said), said
        arguments = missions.free_form_arguments(said, _APPS)
        assert arguments is None or "frontWindow" not in arguments, said
    assert missions.saves_what_is_shown("guardame esto como resumen.txt en documentos")
    assert missions.saves_what_is_shown("Save this drawing as baxy-dibujo.png in Documents\\baxy-prueba-v3")


def test_review_1_a_file_already_there_is_no_save_on_the_window(monkeypatch: pytest.MonkeyPatch) -> None:
    # Over a file that exists the dialog asks «¿Desea reemplazarlo?»; the reader never reads that save.
    monkeypatch.setattr(known_folders, "known_folder", lambda folder: {"documents": _DOCUMENTS}.get(folder))
    monkeypatch.setattr(missions, "_file_taken", lambda _path: True)
    assert not missions.saves_what_is_shown("guardá esto como baxy-nota1.txt en Documentos, en la carpeta baxy-prueba-v3")


# ------------------------------------------------------------------ review of the branch, finding 5


def test_review_5_a_save_proved_on_disk_is_never_done_by_a_title() -> None:
    # The dialog saved in its own folder: the title names the file, the file is not at the path said (the shell asks
    # the model only while the check does not hold). The done is refused and the model asked again.
    view = {
        "window": {"title": "baxy-nota1.txt - Bloc de notas", "process": "Notepad", "requested": False},
        "controls": [_control(0, "TabItem", "baxy-nota1.txt", "selected", "T")],
        "text": {"T": ["baxy-nota1.txt - Bloc de notas"], "C": ["prueba de guardado v3"]},
    }
    history = [{"step": 1, "operation": "input.key.press", "ok": True, "changed": True, "key": "ctrl+shift+s"}]
    check = f"file:{_SAVED_PATH}&title:baxy-nota1"
    refused = cu_validate.validate_decision(
        {"act": "done", "evidence": "baxy-nota1.txt - Bloc de notas"}, view=view, history=history, last_failed=None,
        application_names=_APPS, goal="guardá esto como baxy-nota1.txt en Documentos", success_check=check,
    )
    assert refused["operation"] == "none" and refused["code"] == "file_not_written"
    assert "file_not_written" in cu._RETRIED
    assert cu_goals.proved_on_disk(check)
    # Contracases: a check with a term the screen proves, or none, leaves the done to the screen.
    assert not cu_goals.proved_on_disk(check + "|title:baxy-nota1")
    assert not cu_goals.proved_on_disk("title:baxy-nota1")
    assert not cu_goals.proved_on_disk(None)


# ------------------------------------------------------------------ review of the branch, finding 2

# The review's views: a reading goal's window with a switch on (Settings' Bluetooth, the security window's real-time
# protection and its cloud check box).
_SETTINGS_BLUETOOTH = {
    "window": {"title": "Configuración", "process": "SystemSettings", "requested": True},
    "controls": [
        _control(0, "ListItem", "Dispositivos", "", "L"),
        _control(1, "Button", "Bluetooth", "on", "C"),
    ],
    "text": {"C": ["Bluetooth y dispositivos", "Bluetooth", "Activado"]},
}
_SECURITY_SWITCHES = {
    "window": {"title": "Seguridad de Windows", "process": "SecHealthUI", "requested": True},
    "controls": [
        _control(0, "ListItem", "Protección contra virus y amenazas", "selected", "TL"),
        _control(1, "Button", "Protección en tiempo real", "on", "C"),
        _control(2, "CheckBox", "Protección basada en la nube", "checked", "C"),
    ],
    "text": {"C": ["Configuración de antivirus", "Protección en tiempo real", "Activado"]},
}
_SETTINGS_OPENED = [{"step": 1, "operation": "app.open", "ok": True, "changed": True, "appId": "Configuración"}]


def test_review_2_a_question_never_presses_a_switch_on_the_way() -> None:
    model = _ScriptedModel({"act": "click", "text": "Bluetooth"}, {"act": "done", "evidence": "Activado"})
    decision = _decide(
        model, objective="en configuración decime si el bluetooth está activado",
        goal="abrir Configuración" + QUESTION_MARK + "decime si el bluetooth está activado",
        application="Configuración", view=_SETTINGS_BLUETOOTH, history=_SETTINGS_OPENED,
    )
    assert len(model.payloads) == 2
    assert "cambia un ajuste" in model.payloads[1]["messages"][-1]["content"]
    assert decision["operation"] == "done"
    for goal in (cu_goals.QUESTION_LOOK + "decime si la protección en tiempo real está activada", "ver si está activada"):
        for label in ("Protección en tiempo real", "Protección basada en la nube"):
            refused = cu_validate.validate_decision(
                {"act": "click", "text": label}, view=_SECURITY_SWITCHES, history=_SETTINGS_OPENED, last_failed=None,
                application_names=_APPS, goal=goal,
            )
            assert refused["operation"] == "none" and refused["code"] == "changes_a_setting", (goal, label)


def test_contracase_a_reading_goes_to_its_page_and_a_setting_goal_presses_its_switch() -> None:
    went = cu_validate.validate_decision(
        {"act": "click", "text": "Dispositivos"}, view=_SETTINGS_BLUETOOTH, history=_SETTINGS_OPENED, last_failed=None,
        application_names=_APPS, goal=cu_goals.QUESTION_LOOK + "decime si el bluetooth está activado",
    )
    assert went["operation"] == "input.visible.click" and went["arguments"]["label"] == "Dispositivos"
    for goal in ("desactivar bluetooth", "hacer clic en Bluetooth"):
        pressed = cu_validate.validate_decision(
            {"act": "click", "text": "Bluetooth"}, view=_SETTINGS_BLUETOOTH, history=_SETTINGS_OPENED, last_failed=None,
            application_names=_APPS, goal=goal,
        )
        assert pressed["operation"] == "input.visible.click", goal
    # «check X» ticks a box in English: no reading.
    assert cu_goals.reading_goal("ver si está activado") and cu_goals.reading_goal(cu_goals.QUESTION_LOOK + "tell me if it is on")
    assert not cu_goals.reading_goal("check Word wrap") and not cu_goals.reading_goal("activar bluetooth")


# ------------------------------------------------------------------ review of the branch, finding 4

_PROXY_VIEW = {
    "window": {"title": "Configuración", "process": "SystemSettings", "requested": True},
    "controls": [_control(0, "ListItem", "Red e Internet", "selected", "L")],
    "text": {"C": ["Proxy", "Usa un servidor proxy para conexiones Ethernet o Wi-Fi"]},
}


def test_review_4_a_word_inside_a_phrase_is_no_item_in_view() -> None:
    for name in ("Wi-Fi", "Red", "Ethernet", "Internet"):
        decided = cu_validate.validate_decision(
            {"act": "reveal", "text": name}, view=_PROXY_VIEW, history=_SETTINGS_OPENED, last_failed=None,
            application_names=_APPS, goal="ir a " + name,
        )
        assert decided["operation"] == "input.scroll", name
        assert decided["arguments"]["label"] == name, name
    # Contracase: the item itself, and the phrase named whole, are in view.
    for name in ("Red e Internet", "Proxy", "Usa un servidor proxy para conexiones Ethernet o Wi-Fi"):
        refused = cu_validate.validate_decision(
            {"act": "reveal", "text": name}, view=_PROXY_VIEW, history=_SETTINGS_OPENED, last_failed=None,
            application_names=_APPS, goal="ir a proxy",
        )
        assert refused["operation"] == "none" and refused["code"] == "already_in_view", name


def test_contracase_a_file_written_with_the_persons_text_stays_a_typed_write() -> None:
    for said in (
        "escribí un archivo notas.txt que diga hola",
        "creá notas.txt en documentos con el texto hola",
        'guardá "hola mundo" como notas.txt en documentos',
        "guardá en documentos un archivo notas.txt que diga: hola",
    ):
        assert not missions.saves_what_is_shown(said), said
    tools = {operation: _tool(operation) for operation in ("filesystem.write.text", "mission.computer.use")}
    decided = {
        "type": "turn.result", "id": "7", "kind": "action", "operation": "filesystem.write.text",
        "intentOperations": ["filesystem.write.text"], "effectOperations": ["filesystem.write.text"],
        "question": "", "reply": "", "objective": "escribí un archivo notas.txt que diga hola",
    }
    kept = engine_handoff._engine_for_an_unserved_order(
        dict(decided), {"id": "7", "text": "escribí un archivo notas.txt que diga hola", "history": []}, tools, _APPS)
    assert kept["effectOperations"] == ["filesystem.write.text"]


def test_t_drag_1_the_missing_file_is_told_by_its_measured_cause() -> None:
    told = compose_situation._cause_in_prose("sandbox_named_file_not_found", "es")
    assert "sandbox" not in told and "contenedor" not in told
    assert "no file with that name is in that folder" in told
    # Review of the branch (finding 7): the adapter's other measured causes, said for any of its operations (a
    # comparison moves nothing, so no cause says «moved»).
    for cause in ("sandbox_named_file_ambiguous", "sandbox_named_root_not_found", "sandbox_named_file_name_invalid",
                  "sandbox_named_file_not_found"):
        told = compose_situation._cause_in_prose(cause, "es")
        assert "sandbox" not in told and "_" not in told and "moved" not in told, cause
