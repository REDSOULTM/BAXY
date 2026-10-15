"""Ronda 20b, palanca 3: las preguntas se responden leyendo la ventana de la misión.

v3-43 (pasada r18): el clic llegó a «Opciones de energía», el chequeo «stepDone:input.visible.click:opciones de energia»
se cumplió y la App negó el cierre por datum_unread (la barra «Cargando» quieta). La mente volvió a cazar el lugar ya
alcanzado por regla (buscador, «Atrás a…», «Actualizar…», la dirección) hasta computer_use_repeated_step (trace seq
179-257). Con la vista marcada questionPending ninguna regla caza el lugar: decide el modelo.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind import computer_use  # noqa: E402
from baxy_mind import cu_meaning
from baxy_mind import cu_model_calls
from baxy_mind.planner import PlannerCatalog  # noqa: E402
from baxy_mind.semantic import cu_tipos, missions  # noqa: E402
from baxy_mind.semantic.decider import ContextDecision  # noqa: E402
from baxy_mind import context_decision  # noqa: E402
from baxy_mind import compose_facts  # noqa: E402

GOAL = "hacer clic en opciones de energia; y responder: dime qué plan de energía está activo"
CHECK = "stepDone:input.visible.click:opciones de energia"

# La vista de v3-43 tras el clic, recortada (trace seq 180: 38 controles, sin texto).
POWER_OPTIONS = {
    "window": {"title": "Opciones de energía", "process": "explorer", "requested": True},
    "controls": [
        {"i": 0, "kind": "Button", "name": "Atrás a «Sistema y seguridad» (Alt + Flecha izquierda)"},
        {"i": 1, "kind": "Button", "name": "Actualizar «Opciones de energía» (F5)"},
        {"i": 2, "kind": "Edit", "name": "Dirección", "value": "Panel de control > Sistema y seguridad > Opciones de energía"},
        {"i": 3, "kind": "Edit", "name": "Buscar en el Panel de control"},
        {"i": 4, "kind": "ProgressBar", "name": "Cargando", "value": "0"},
        {"i": 5, "kind": "Hyperlink", "name": "Elegir el comportamiento de los botones de inicio/apagado"},
        {"i": 6, "kind": "Hyperlink", "name": "Cambiar la configuración del plan Equilibrado"},
    ],
    "newTextAfterClick": [],
}

SYSTEM_AND_SECURITY = {
    "window": {"title": "Sistema y seguridad", "process": "explorer", "requested": True},
    "controls": [
        {"i": 0, "kind": "Edit", "name": "Buscar en el Panel de control"},
        {"i": 1, "kind": "Hyperlink", "name": "Opciones de energía"},
        {"i": 2, "kind": "Hyperlink", "name": "Sistema"},
    ],
    "newTextAfterClick": [],
}

HISTORY = [
    {"step": 1, "operation": "app.open", "appId": "Panel de control", "ok": True, "changed": True},
    {"step": 2, "operation": "input.visible.click", "label": "Opciones de energía", "ok": True, "changed": True,
     "surfaceChanged": True},
]


class _Model:
    """Un modelo local que registra cada paso que se le pide y responde siempre el mismo."""

    def __init__(self, step: dict) -> None:
        self.step = step
        self.step_payloads: list[dict] = []

    def _post_schema_object(self, payload: dict, label: str) -> object:
        if payload["messages"][0]["content"] == cu_model_calls.TRANSLATE_PROMPT:
            return {"es": [], "en": []}
        self.step_payloads.append(payload)
        return self.step


def _decide(view: dict, model: _Model, history: list[dict] | None = None) -> dict:
    return computer_use.decide_step(
        model, objective="en el panel de control dime qué plan de energía está activo", goal=GOAL,
        application="Panel de control", success_check=CHECK, view=view, history=list(history or HISTORY),
        budget_left=8, application_names=["Panel de control"],
    )


def test_a_pending_question_on_the_reached_place_is_the_models_never_a_rule() -> None:
    view = {**copy.deepcopy(POWER_OPTIONS), "questionPending": True}
    model = _Model({"act": "none", "reason": "x"})
    decision = _decide(view, model)
    assert model.step_payloads, "the model was asked"
    assert decision.get("source") == cu_meaning.SOURCE_MODEL
    # Ningún paso de regla que vuelva a cazar el lugar: ni el buscador ni «Atrás» ni «Actualizar» ni la dirección.
    assert decision.get("operation") == "none"


def test_without_a_pending_question_the_rules_still_decide_first() -> None:
    # Contracaso (y la reproducción de v3-43): sin questionPending la mente sigue como antes, la regla dicta sin el
    # modelo (en la pasada r18, «Actualizar…» y los demás hasta el paso repetido).
    model = _Model({"act": "none", "reason": "x"})
    decision = _decide(copy.deepcopy(POWER_OPTIONS), model)
    assert computer_use.question_pending(POWER_OPTIONS, HISTORY) is False
    assert decision.get("source") == cu_meaning.SOURCE_RULE and not model.step_payloads


def test_a_pending_mark_without_a_verified_act_is_no_pending_question() -> None:
    view = {**copy.deepcopy(POWER_OPTIONS), "questionPending": True}
    assert computer_use.question_pending(view, HISTORY) is True
    assert computer_use.question_pending(view, []) is False
    assert computer_use.question_pending(view, [{"step": 1, "operation": "input.visible.click", "ok": False}]) is False


def test_where_the_datum_is_not_the_model_takes_the_step_to_the_page() -> None:
    # Contracaso: «¿qué plan está activo?» en «Sistema y seguridad»: el modelo da el paso a «Opciones de energía».
    view = {**copy.deepcopy(SYSTEM_AND_SECURITY), "questionPending": True}
    model = _Model({"act": "click", "i": 1})
    decision = _decide(view, model)
    assert model.step_payloads
    assert decision.get("operation") == "input.visible.click"
    assert (decision.get("arguments") or {}).get("index") == 1


# ---------------------------------------------------------------- v3-50, lector de abrir archivo: «que está en
# baxy-prueba-v3» (un lugar de una palabra, sin «carpeta») caía a un «ir a prueba.zip…» cerrado por una selección.


@pytest.fixture()
def _person_folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from baxy_mind import known_folders

    documents = tmp_path / "Documentos"
    (documents / "baxy-prueba-v3").mkdir(parents=True)
    (documents / "baxy-prueba-v3" / "prueba.zip").write_bytes(b"x")
    (documents / "otra").mkdir()
    (documents / "otra" / "notas.txt").write_bytes(b"x")
    monkeypatch.setattr(known_folders, "known_folder", lambda folder: {"documents": str(documents)}.get(folder))
    return documents


def test_a_file_in_a_folder_said_by_its_name_alone_is_opened_by_the_shell(_person_folders: Path) -> None:
    located = _person_folders / "baxy-prueba-v3" / "prueba.zip"
    assert missions._file_reads("abri el prueba.zip que esta en baxy-prueba-v3") == [
        (f"{cu_tipos.OPEN_FILE_GOAL}{located}", f"title:prueba&{cu_tipos.FILE_OPENED}", False)]


def test_a_one_word_place_that_is_no_folder_or_holds_two_files_is_not_guessed(_person_folders: Path) -> None:
    # Contracaso: «Drive» no es ninguna carpeta de la persona: sigue en None.
    assert missions._file_reads("abri notas.txt que esta en Drive") is None
    # Contracaso: dos prueba.zip en carpetas homónimas: ambigüedad, sigue en None.
    twin = _person_folders / "copia" / "baxy-prueba-v3"
    twin.mkdir(parents=True)
    (twin / "prueba.zip").write_bytes(b"x")
    assert missions._file_reads("abri el prueba.zip que esta en baxy-prueba-v3") is None


# ---------------------------------------------------------------- v3-50 turno 2: «decime cuántos archivos tiene adentro»
# tras la misión en 7-Zip. El decisor eligió filesystem.explorer.count con [extension, folder] (turn_audit request 12);
# el esquema sólo declara extension, el adaptador contó el Escritorio y se publicó «cero archivos zip en la carpeta
# Escritorio».

SEVEN_ZIP_APPS = ("7-Zip File Manager", "Bloc de notas", "Calculadora", "Explorador de archivos")
FOLLOW_OPERATIONS = tuple(
    json.loads((ROOT / "src/baxy_mind/data/decider_catalog.es.v1.json").read_text(encoding="utf-8"))["operations"]
) + ("mission.computer.use",)
SEVEN_ZIP_TURN = "en 7zip abrí el prueba.zip que está en baxy-prueba-v3"
SEVEN_ZIP_HISTORY = [
    {"role": "user", "content": SEVEN_ZIP_TURN},
    {"role": "assistant", "content": "Abrí prueba.zip en 7-Zip File Manager."},
]


def _tool(operation: str) -> dict[str, Any]:
    properties = {"extension": {"type": "string"}} if operation == "filesystem.explorer.count" else {}
    schema = {"type": "object", "properties": properties, "required": [], "additionalProperties": False}
    return {"type": "function", "function": {"name": operation.replace(".", "_"), "canonical_name": operation,
                                             "description": operation, "risk": "read_only", "parameters": schema}}


class _Decider:
    """El decisor responde lo que se le da; cualquier otra llamada al modelo es neutra."""

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

    def chat(self, *_a, **_k):
        return "Eso no lo puedo hacer.", None

    def clarify_after_turn_failure(self, *_a, **_k):
        return "¿En qué carpeta querés que cuente?"

    def __getattr__(self, name):
        def missing(*_a, **_k):
            raise RuntimeError(f"no {name} here")
        return missing


def _decided(text: str, decision: ContextDecision, history: list[dict] | None = None) -> dict[str, Any]:
    catalog = PlannerCatalog([_tool(name) for name in FOLLOW_OPERATIONS])
    said = [*(SEVEN_ZIP_HISTORY if history is None else history), {"role": "user", "content": text}]
    return context_decision._context_decided_result(
        {"id": "v3-50", "text": text, "history": said},
        llm=_Decider(decision), planner_catalog=catalog, application_names=SEVEN_ZIP_APPS,
    )


def test_an_anaphoric_question_after_a_mission_is_read_in_its_application() -> None:
    asked = missions.follow_up_in_application(
        "decime cuántos archivos tiene adentro", [SEVEN_ZIP_TURN], FOLLOW_OPERATIONS, SEVEN_ZIP_APPS,
    )
    assert asked == "en 7-Zip File Manager, decime cuántos archivos tiene adentro"
    mission = missions.mission_request(asked, SEVEN_ZIP_APPS)
    assert mission is not None and mission.looks_only and missions.QUESTION_MARK in mission.goal
    assert missions.follow_up_in_application("y qué dice", [SEVEN_ZIP_TURN], FOLLOW_OPERATIONS, SEVEN_ZIP_APPS) == (
        "en 7-Zip File Manager, decime qué dice")


@pytest.mark.parametrize("said", ["¿qué hora es?", "cuántos archivos hay dentro de la carpeta Documentos",
                                  "¿cuántos .py hay en el directorio actual?"])
def test_a_question_that_points_at_nothing_shown_is_not_rerouted(said: str) -> None:
    # Contracaso: «¿qué hora es?» tras una misión no es anafórica; un lugar propio tampoco.
    assert missions.follow_up_in_application(said, [SEVEN_ZIP_TURN], FOLLOW_OPERATIONS, SEVEN_ZIP_APPS) is None


def test_an_argument_the_count_does_not_declare_sends_the_follow_up_to_the_mission() -> None:
    restated = "Contá cuántos archivos hay en prueba.zip de baxy-prueba-v3."
    decision = ContextDecision(
        restated, "action", ("filesystem.explorer.count",), "",
        (("extension", ".zip"), ("folder", "baxy-prueba-v3")),
    )
    result = _decided("decime cuántos archivos tiene adentro", decision)
    assert result["operation"] == "mission.computer.use"
    # Ronda 23 (r21 v3-50 t2, falso éxito «hay 7 archivos en la carpeta»): el objetivo conserva el objeto del turno
    # anterior; sin él la misión contaba la carpeta.
    assert result["objective"] == "en 7-Zip File Manager, decime cuántos archivos tiene adentro (prueba.zip)"
    # Revisión 1: sin el campo de más la pregunta sigue apuntando a lo que mostró la misión; una lectura tipada de otro
    # lugar (el Escritorio, el Explorador delante) no es la respuesta y no depende de que el decisor agregue un campo.
    declared = ContextDecision(restated, "action", ("filesystem.explorer.count",), "", (("extension", ".zip"),))
    result = _decided("decime cuántos archivos tiene adentro", declared)
    assert result["operation"] == "mission.computer.use"
    assert result["objective"] == "en 7-Zip File Manager, decime cuántos archivos tiene adentro (prueba.zip)"


def test_a_typed_count_with_a_place_of_its_own_after_the_mission_stays_typed() -> None:
    # Contracaso (D21): tras la misión, una cuenta con lugar propio no apunta a la vista; la operación tipada queda.
    decision = ContextDecision(
        "Contá los archivos .py del directorio actual.", "action", ("filesystem.explorer.count",), "",
        (("extension", ".py"),),
    )
    assert _decided("¿cuántos .py hay en el directorio actual?", decision)["operation"] == "filesystem.explorer.count"


def test_an_undeclared_argument_with_no_conversation_is_asked_not_dropped() -> None:
    # Revisión 1, escenario 1: primer turno, el decisor llena folder, que la cuenta no declara; el Escritorio no se cuenta.
    decision = ContextDecision(
        "Contá los .zip de baxy-prueba-v3.", "action", ("filesystem.explorer.count",), "",
        (("extension", ".zip"), ("folder", "baxy-prueba-v3")),
    )
    result = _decided("¿cuántos zip hay en baxy-prueba-v3?", decision, history=[])
    assert result.get("kind") == "clarify" and result.get("operation") != "filesystem.explorer.count"
    assert "filesystem.explorer.count" not in json.dumps(result.get("steps") or [])


def test_the_count_in_the_current_folder_without_a_mission_before_stays_typed() -> None:
    # Contracaso: «¿cuántos .py hay en el directorio actual?» con el Explorador delante y sin misión previa.
    decision = ContextDecision(
        "Contá los archivos .py del directorio actual.", "action", ("filesystem.explorer.count",), "",
        (("extension", ".py"),),
    )
    result = _decided("¿cuántos .py hay en el directorio actual?", decision, history=[])
    assert result["operation"] == "filesystem.explorer.count"


# ---------------------------------------------------------------- revisión 1, bloqueante 2: preguntas con sujeto propio
OWN_SUBJECT_QUESTIONS = (
    "¿qué contiene la vitamina C?", "cuántas calorías contiene una manzana", "¿qué incluye una dieta keto?",
    "¿qué tiene adentro un huevo?", "¿qué tiene una manzana adentro?", "what does a banana contain inside of it?",
)


@pytest.mark.parametrize("prior", ["abrí la calculadora", "abrí Spotify", SEVEN_ZIP_TURN])
@pytest.mark.parametrize("said", OWN_SUBJECT_QUESTIONS)
def test_a_question_with_its_own_subject_is_not_read_in_the_application(prior: str, said: str) -> None:
    # Contracaso de ANAPHORIC_QUESTION: «contiene», «incluye» o «adentro» con su propio sujeto no apuntan a la vista.
    apps = (*SEVEN_ZIP_APPS, "Spotify")
    assert not missions.anaphoric_question(said)
    assert missions.follow_up_in_application(said, [prior], FOLLOW_OPERATIONS, apps) is None
    assert missions.application_question(said, apps, "Spotify") is None


@pytest.mark.parametrize("said", ["¿qué contiene?", "y qué hay adentro", "what's inside?", "what does it say?"])
def test_a_bare_anaphoric_question_still_points_at_the_view(said: str) -> None:
    assert missions.anaphoric_question(said)


def test_a_question_with_its_own_subject_keeps_the_decider_limit() -> None:
    # En la base se respetaba el límite sin pregunta del decisor; la pregunta no se vuelve misión en la Calculadora.
    history = [{"role": "user", "content": "abrí la calculadora"}, {"role": "assistant", "content": "Abrí Calculadora."}]
    limit = ContextDecision("¿Qué contiene la vitamina C?", "limit", (), "")
    result = _decided("¿qué contiene la vitamina C?", limit, history=history)
    assert result.get("operation") != "mission.computer.use" and result.get("kind") != "clarify"
    assert "Calculadora" not in str(result.get("objective") or "")


# ---------------------------------------------------------------- revisión 1, bloqueante 1: la cuenta del Escritorio
def _count_situation(source: str) -> dict[str, Any]:
    return {
        "operation": "filesystem.explorer.count", "succeeded": True, "verified": True,
        "observed": {"folderName": "Escritorio", "source": source, "extension": ".zip", "count": 0, "filesInFolder": 3},
    }


@pytest.fixture()
def _counted_folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Las carpetas de la persona: baxy-prueba-v3 en Documentos, proyectos en el Escritorio."""

    from baxy_mind import known_folders

    documents, desktop = tmp_path / "Documentos", tmp_path / "Escritorio"
    (documents / "baxy-prueba-v3").mkdir(parents=True)
    (desktop / "proyectos").mkdir(parents=True)
    roots = {"documents": str(documents), "desktop": str(desktop)}
    monkeypatch.setattr(known_folders, "known_folder", lambda folder: roots.get(folder))
    return tmp_path


@pytest.mark.parametrize("said", ["¿cuántos zip hay en baxy-prueba-v3?", "decime cuántos archivos tiene adentro",
                                  "cuantos txt hay en Documentos", "cuántos zip hay en la carpeta fotos del escritorio",
                                  "¿cuántos pdf hay en proyectos del escritorio?", "how many files are in my downloads"])
def test_a_desktop_count_is_not_published_for_another_named_place(said: str, _counted_folders: Path) -> None:
    assert compose_facts._count_read_beside_the_named_place(_count_situation("desktop"), said)


# Revisión 2, bloqueante 2: «en X» que no es un lugar (un tiempo, un formato, la máquina) no tapa al Escritorio nombrado.
DESKTOP_COUNTS_WITH_OTHER_COMPLEMENTS = (
    "¿cuántos archivos hay en el escritorio en este momento?", "¿cuántos archivos en PDF tengo en el escritorio?",
    "cuántos archivos hay en mi escritorio en formato pdf", "cuántas carpetas hay en el escritorio en este instante",
    "cuántos archivos tengo en el escritorio en este pc", "cuantos archivos hay en el escritorio en este computador",
    "contá los archivos que hay en el escritorio en este momento",
    "how many pdf files are there in PDF format on my desktop",
)


@pytest.mark.parametrize("said", ["¿cuántos .py hay en el directorio actual?", "cuántos pdf tengo en el escritorio",
                                  "¿cuántos zip hay?", "cuántos archivos hay en total",
                                  "¿cuántos zip hay en baxy-prueba-v3 del escritorio?", "¿cuántos pdf hay en este momento?",
                                  *DESKTOP_COUNTS_WITH_OTHER_COMPLEMENTS])
def test_a_desktop_count_for_the_current_folder_or_the_desktop_is_published(said: str, _counted_folders: Path) -> None:
    # Contracaso (D24): sin Explorador delante, el directorio actual es el Escritorio.
    assert not compose_facts._count_read_beside_the_named_place(_count_situation("desktop"), said)


def test_a_count_from_the_explorer_in_front_is_not_held_by_the_desktop_guard() -> None:
    assert not compose_facts._count_read_beside_the_named_place(
        _count_situation("explorer_foreground"), "¿cuántos zip hay en baxy-prueba-v3?",
    )


# ---------------------------------------------------------------- revisión 2, bloqueante 1: los alias del decisor
# Esquemas reales de tests/test_c03_m141_argumentos_en_planes.py (G-s040, G-s116).
APP_OPEN = {"type": "object", "properties": {"appId": {"type": "string", "x-maxUtf8Bytes": 512}},
            "required": ["appId"], "additionalProperties": False}
SNAP = {"type": "object", "properties": {"side": {"type": "string", "enum": ["left", "right"]},
                                         "windowId": {"type": "string", "maxLength": 36}},
        "required": ["side", "windowId"], "additionalProperties": False}
PLAY_QUERY = {"type": "object", "properties": {"provider": {"type": "string", "enum": ["spotify"]},
                                               "query": {"type": "string", "x-maxUtf8Bytes": 1024}},
              "required": ["provider", "query"], "additionalProperties": False}
WEB_SEARCH = {"type": "object", "properties": {"query": {"type": "string", "x-maxUtf8Bytes": 512}},
              "required": ["query"], "additionalProperties": False}
COUNT = {"type": "object", "properties": {"extension": {"type": "string", "maxLength": 16}},
         "required": ["extension"], "additionalProperties": False}
REAL_SCHEMAS = {"app.open": APP_OPEN, "window.snap": SNAP, "media.play.query": PLAY_QUERY, "web.search": WEB_SEARCH,
                "filesystem.explorer.count": COUNT}

G_ROWS = (
    ("open Notepad and put it on the left half of the screen please", ("app.open", "window.snap"),
     (("app", "Notepad"), ("side", "left"))),
    ("abrí spotify y ponime algo de jazz tranqui", ("app.open", "media.play.query"),
     (("app.open", "Spotify"), ("media.play.query", "jazz tranquilo"))),
)


def _real_catalog() -> PlannerCatalog:
    return PlannerCatalog([
        {"type": "function", "function": {"name": name.replace(".", "_"), "canonical_name": name, "description": name,
                                          "risk": "read_only", "parameters": schema}}
        for name, schema in REAL_SCHEMAS.items()
    ])


@pytest.mark.parametrize(("said", "operations", "arguments"), G_ROWS)
def test_the_decider_s_aliases_are_declared_fields(said: str, operations: tuple[str, ...],
                                                     arguments: tuple[tuple[str, str], ...]) -> None:
    # Contracaso: «app» → appId, el valor bajo el nombre de la operación → su texto libre (M136/M141).
    decision = ContextDecision(said, "action", operations, "", arguments)
    assert not context_decision._fills_an_undeclared_argument(decision, _real_catalog())
    for before in ([], SEVEN_ZIP_HISTORY):
        # Sin conversación no se pregunta; tras la misión en 7-Zip no se reenvía a mission.computer.use.
        result = context_decision._context_decided_result(
            {"id": "G", "text": said, "history": [*before, {"role": "user", "content": said}]},
            llm=_Decider(decision), planner_catalog=_real_catalog(), application_names=SEVEN_ZIP_APPS,
        )
        assert result.get("kind") == "plan" and result.get("operation") != "mission.computer.use"


def test_a_value_keyed_by_the_chosen_operation_is_declared() -> None:
    decision = ContextDecision("Buscá el clima en Ñuñoa.", "action", ("web.search",), "",
                               (("web.search", "clima en Ñuñoa"),))
    assert not context_decision._fills_an_undeclared_argument(decision, _real_catalog())


def test_a_field_no_chosen_operation_declares_is_still_undeclared() -> None:
    # La regla de la revisión 1 sigue: folder no es de la cuenta (ni por prefijo ni por operación).
    decision = ContextDecision("Contá los .zip de baxy-prueba-v3.", "action", ("filesystem.explorer.count",), "",
                               (("extension", ".zip"), ("folder", "baxy-prueba-v3")))
    assert context_decision._fills_an_undeclared_argument(decision, _real_catalog())


# ---------------------------------------------------------------- revisión 3: el sujeto dicho ANTES de la pregunta
PAINT_HISTORY = [{"role": "user", "content": "en paint seleccioná el lápiz"},
                 {"role": "assistant", "content": "Seleccioné el lápiz en Paint."}]
SPOTIFY_HISTORY = [{"role": "user", "content": "abrí spotify"}, {"role": "assistant", "content": "Abrí Spotify."}]
CALCULATOR_HISTORY = [{"role": "user", "content": "abrí la calculadora"},
                      {"role": "assistant", "content": "Abrí Calculadora."}]
ENGLISH_SPOTIFY_HISTORY = [{"role": "user", "content": "open spotify"}, {"role": "assistant", "content": "Opened Spotify."}]
ANTEPOSED_SUBJECT_ROWS = (
    (SPOTIFY_HISTORY, "¿el último correo qué dice?", "email.latest.read"),
    (SPOTIFY_HISTORY, "¿el clima de mañana qué dice?", "weather.current"),
    (SPOTIFY_HISTORY, "¿las noticias qué dicen?", "web.news.headlines"),
    (SPOTIFY_HISTORY, "¿las noticias de hoy qué dicen?", "web.news.headlines"),
    (CALCULATOR_HISTORY, "¿el portapapeles qué tiene adentro?", "clipboard.read.text"),
    (CALCULATOR_HISTORY, "el correo de Ana, ¿qué dice?", "email.latest.read"),
    (PAINT_HISTORY, "¿el pronóstico qué dice?", "weather.current"),
    (ENGLISH_SPOTIFY_HISTORY, "and my last email, what does it say?", "email.latest.read"),
    (ENGLISH_SPOTIFY_HISTORY, "the clipboard, what is in it?", "clipboard.read.text"),
)
SUBJECT_APPS = (*SEVEN_ZIP_APPS, "Spotify", "Paint")


@pytest.mark.parametrize(("history", "said", "operation"), ANTEPOSED_SUBJECT_ROWS)
def test_a_subject_said_before_the_question_keeps_the_typed_read(history: list[dict], said: str,
                                                                  operation: str) -> None:
    # Contracaso de ANAPHORIC_QUESTION: «¿el último correo qué dice?» tras «abrí spotify» pregunta por el correo, no por
    # la ventana de Spotify; la lectura tipada que eligió el decisor queda.
    assert not missions.anaphoric_question(said)
    prior = [turn["content"] for turn in history if turn["role"] == "user"]
    assert missions.follow_up_in_application(said, prior, FOLLOW_OPERATIONS, SUBJECT_APPS) is None
    catalog = PlannerCatalog([_tool(name) for name in FOLLOW_OPERATIONS])
    result = context_decision._context_decided_result(
        {"id": "r3", "text": said, "history": [*history, {"role": "user", "content": said}]},
        llm=_Decider(ContextDecision(said, "action", (operation,), "")), planner_catalog=catalog,
        application_names=SUBJECT_APPS,
    )
    assert result.get("operation") == operation


@pytest.mark.parametrize("said", ["decime lo que dice", "a ver, ¿qué dice?", "y ahora qué contiene",
                                  "tell me, what does it say?", "and what's in it?", "¿y eso qué dice?"])
def test_a_lead_with_no_subject_still_points_at_the_view(said: str) -> None:
    assert missions.anaphoric_question(said)
