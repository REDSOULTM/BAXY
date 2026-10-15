"""v3 ronda 5 (cu-v3/r5a/lectura.md M1, M2, M3, M6 and «Diseño general» 3–6; falsos.md M1): the one coverage gate
after every typed decision, questions about an application read as a look at it, and the decomposition of a request
into sub-goals.

The rows are the requests and follow-up turns of the r3 pass (cu-v3/v3_pasada_r3_veredictos.json; packages in
cu-v3/r5/<case>.json, turn audits in cu-universal-evidencia/v2-<case>/) whose reading this branch decides, with the
decision each route took there:

- v3-24 «en el visor de eventos filtra…» → explicit_effects web.search; v3-53 t1 «en obs silencia el audio del
  escritorio» → explicit_effects audio.mute (the PC's sound was muted);
- v3-61 «en seguridad de windows decime cuándo…» → the recovery's clarify; t-drag-4 «en Paint draw una línea…» → an
  unresolved-input clarify; v3-35-like «creá una nota rápida nueva» said inside Notas rápidas → the question for a title;
- v3-27 «abre el mapa de caracteres y copia el símbolo del euro» → talk with an unasked typing;
- v3-22 t3 «¿cuáles tienen impacto alto?» after the Task Manager was opened → no look at it;
- v3-49 «en 7-zip cambia la vista a detalles y ordena por tamaño» → one sentence for the engine (the chain was dropped).

Rows that need the single application resolver (typing slips «visr», «adminsitrador», a name said by one word,
another language) or the destination precedence (diseño 1–2) are other branches' and are not pinned here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from baxy_mind import computer_use
from baxy_mind import cu_model_calls
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import decider, missions, patterns
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind import engine_handoff
from baxy_mind import context_decision
from baxy_mind import plan_shape

ROOT = Path(__file__).resolve().parents[1]
CATALOG = tuple(
    json.loads((ROOT / "src/baxy_mind/data/decider_catalog.es.v1.json").read_text(encoding="utf-8"))["operations"]
)
OPERATIONS = tuple(dict.fromkeys((*CATALOG, "mission.computer.use")))
TOOLS = {operation: {} for operation in OPERATIONS}
APPS = (
    "7-Zip File Manager", "Administrador de tareas", "BAXY", "Bloc de notas", "Discord", "Google Chrome",
    "Información del sistema", "Mapa de caracteres", "Microsoft Edge", "Notas rápidas", "OBS Studio", "OneNote",
    "Paint", "Seguridad de Windows", "Spotify", "Steam", "Terminal", "Visor de eventos",
)


def _turn(kind: str, operations: tuple[str, ...] = (), **extra: Any) -> dict[str, Any]:
    acting = kind in {"action", "plan"}
    return {
        "type": "turn.result", "id": "r5", "kind": kind, "operation": operations[0] if kind == "action" else None,
        "intentOperations": list(operations), "effectOperations": list(operations) if acting else [],
        "question": "¿Qué?" if kind == "clarify" else "", "reply": "", **extra,
    }


def _gate(text: str, turn: dict[str, Any], history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    said = [*(history or []), {"role": "user", "content": text}]
    return engine_handoff._engine_for_an_unserved_order(turn, {"id": "r5", "text": text, "history": said}, TOOLS, APPS)


def _engine(result: dict[str, Any]) -> bool:
    return result["effectOperations"] == ["mission.computer.use"]


V3_24 = "en el visor de eventos filtra el registro de aplicación para que solo salgan los errores"
V3_53 = "en obs silencia el audio del escritorio"
V3_61 = "en seguridad de windows decime cuándo fue el último examen de virus"
T_DRAG_4 = "en Paint draw una línea recta arrastrando el mouse de la izquierda a la derecha del lienzo, más o menos por la mitad"
PAINT_ORDER = "en Paint girá la imagen a la derecha, más o menos un cuarto de vuelta"
V3_27 = "abre el mapa de caracteres y copia el simbolo del euro"
V3_49 = "en 7-zip cambia la vista a detalles y ordena por tamaño"


# ------------------------------------------------------------ la puerta única (M1, M2, M3)


@pytest.mark.parametrize(
    ("text", "turn", "objective"),
    [
        # M1: a typed operation on another object never wins over the application named, whatever route chose it
        (V3_24, _turn("action", ("web.search",)), V3_24),
        (V3_53, _turn("action", ("audio.mute",)), V3_53),
        ("en notas rápidas anotá llamar al dentista", _turn("action", ("note.create",)),
         "en notas rápidas anotá llamar al dentista"),
        # M2: the question for a value the order did not say is no question the engine needs
        ("en notas rápidas creá una nota nueva", _turn("clarify", ("note.create",), missingFields=["title"]),
         "en notas rápidas creá una nota nueva"),
        # M3: the unresolved-input question about an order said inside Paint (t-drag-4 itself is the drag limit since
        # the estabilización L: test_t_drag_4_is_the_drag_limit_never_the_engines)
        (PAINT_ORDER, _turn("clarify"), PAINT_ORDER),
        # M3/diseño 4: the recovery's clarify about a question framed in an application is a look at it
        (V3_61, _turn("clarify"), "en Seguridad de Windows, decime cuándo fue el último examen de virus"),
        (V3_61, _turn("conversation", conversationKind="unsupported"),
         "en Seguridad de Windows, decime cuándo fue el último examen de virus"),
    ],
)
def test_every_route_passes_the_one_coverage_gate(text: str, turn: dict[str, Any], objective: str) -> None:
    result = _gate(text, turn)
    assert _engine(result), result
    assert result["objective"] == objective
    assert result["kind"] == "plan" and result["question"] == ""


@pytest.mark.parametrize(
    ("text", "turn"),
    [
        # the search engine named is the place of a search
        ("busca en google un top 3 de peliculas de suspenso", _turn("action", ("web.search",))),
        # no application named: the typed operation is the request
        ("silenciá el audio", _turn("action", ("audio.mute",))),
        ("creá una nota que diga comprar pan", _turn("action", ("note.create",))),
        ("creá una nota nueva", _turn("clarify", ("note.create",), missingFields=["title"])),
        # the application's own service asks its own value (owner rule: a relative volume asks how much)
        ("en spotify subí el volumen", _turn("clarify", ("audio.app.volume.adjust",), missingFields=["amount"])),
        ("en spotify baja el volumen", _turn("action", ("audio.app.volume.adjust",))),
        # a request of its own read apart in an order of two clauses
        ("abre discord y recordame en 10 minutos llamar a pedro", _turn("plan", ("app.open", "reminder.create"))),
        ("abrime steam porfa y de paso fijate que hora es", _turn("plan", ("app.open", "system.time"))),
        # an application only opened, and talk that names one, are no order inside it
        ("abrí spotify", _turn("clarify", ("app.open",), missingFields=["application"])),
        ("en spotify me encanta esta canción", _turn("clarify")),
        # what the engine never tries alone
        ("en Spotify borrá la playlist Gym", _turn("clarify", ("input.visible.click",))),
        # a question about the PC that is not about an application
        ("¿qué hora es?", _turn("clarify")),
    ],
)
def test_the_gate_keeps_what_serves_the_order(text: str, turn: dict[str, Any]) -> None:
    assert _gate(text, turn) is turn


def test_a_knowledge_answer_is_never_taken_for_a_look_at_an_application() -> None:
    history = [{"role": "user", "content": "abre el administrador de tareas"}, {"role": "assistant", "content": "Listo."}]
    talk = _turn("conversation", conversationKind="knowledge")
    assert _gate("¿cuál es la capital de Francia?", talk, history) is talk


# ------------------------------------------------------------ preguntas sobre una app (diseño 4)

TASK_MANAGER = [
    {"role": "user", "content": "abre el administrador de tareas"},
    {"role": "assistant", "content": "Abrí el Administrador de tareas."},
    {"role": "user", "content": "ve a aplicaciones de arranque"},
    {"role": "assistant", "content": "Listo, estás en Aplicaciones de arranque."},
]


def test_a_question_about_the_application_of_the_conversation_is_a_look_at_it() -> None:
    """v3-22 t3: the question names no application; the conversation is in the Task Manager."""

    result = _gate("¿cuáles tienen impacto alto?", _turn("clarify"), TASK_MANAGER)
    assert _engine(result)
    assert result["objective"] == "en Administrador de tareas, decime cuáles tienen impacto alto"
    mission = missions.mission_request(result["objective"], APPS)
    assert mission is not None and mission.application == "Administrador de tareas"
    assert mission.goal.endswith(missions.QUESTION_MARK + "decime cuáles tienen impacto alto")


def test_a_turn_about_something_else_in_between_ends_the_conversation_application() -> None:
    history = [*TASK_MANAGER, {"role": "user", "content": "cuál es la capital de Francia"},
               {"role": "assistant", "content": "París."}]
    asked = _turn("clarify")
    assert _gate("¿cuáles tienen impacto alto?", asked, history) is asked
    assert missions.conversation_application(
        [item["content"] for item in history if item["role"] == "user"], APPS, OPERATIONS,
    ) is None


@pytest.mark.parametrize(
    ("text", "conversation", "rewritten"),
    [
        (V3_61, None, "en Seguridad de Windows, decime cuándo fue el último examen de virus"),
        ("en Seguridad de Windows, ¿cuándo fue el último examen?", None,
         "en Seguridad de Windows, decime cuándo fue el último examen"),
        ("¿cuáles tienen impacto alto?", "Administrador de tareas",
         "en Administrador de tareas, decime cuáles tienen impacto alto"),
        ("y ahora decime cuántos procesos hay", "Administrador de tareas",
         "en Administrador de tareas, decime cuántos procesos hay"),
        # no question, a question that names another application, or no application at all
        ("en Seguridad de Windows activá la protección en tiempo real", None, None),
        ("¿qué canción suena en Spotify?", "Administrador de tareas", None),
        ("¿cuáles tienen impacto alto?", None, None),
        ("gracias", "Administrador de tareas", None),
    ],
)
def test_application_question(text: str, conversation: str | None, rewritten: str | None) -> None:
    assert missions.application_question(text, APPS, conversation) == rewritten


@pytest.mark.parametrize(
    "text",
    [V3_61, "en Seguridad de Windows, decime cuándo fue el último examen de virus"],
)
def test_a_question_said_inside_an_application_is_a_mission_of_reading(text: str) -> None:
    mission = missions.mission_request(text, APPS)
    assert mission is not None
    assert mission.application == "Seguridad de Windows"
    assert mission.goal == "abrir Seguridad de Windows" + missions.QUESTION_MARK + (
        "decime cuándo fue el último examen de virus"
    )
    assert mission.success_check == "title:Seguridad de Windows|process:Seguridad de Windows"


def test_opening_an_application_and_asking_something_else_is_still_no_mission() -> None:
    """Contracase: «abre Steam y decime la hora» asks a request of its own (the clock), as before."""

    assert missions.mission_request("abre steam y decime la hora", APPS) is None
    assert missions.mission_request("abrime steam porfa y de paso fijate que hora es", APPS) is None


# ------------------------------------------------------------ talk con acción no pedida (M3)


def _decided(text: str, decision: ContextDecision) -> dict[str, Any]:
    from test_cu_v3_cobertura import _Decider, _tool

    catalog = PlannerCatalog([_tool(name) for name in OPERATIONS])
    return context_decision._context_decided_result(
        {"id": "r5", "text": text, "history": [{"role": "user", "content": text}]},
        llm=_Decider(decision), planner_catalog=catalog, application_names=APPS,
    )


def test_typing_nobody_asked_for_in_an_order_inside_an_application_is_the_engines() -> None:
    result = _decided(V3_27, ContextDecision(
        "Abre el mapa de caracteres y copia el símbolo del euro.", "action", ("input.keyboard.open", "input.text.type"), "",
    ))
    assert _engine(result)
    assert result["objective"] == V3_27


def test_typing_nobody_asked_for_without_an_application_is_still_talk() -> None:
    result = _decided("Di la palabra algo", ContextDecision("Escribe la palabra «algo».", "action", ("input.text.type",), ""))
    assert result["kind"] != "action" or not _engine(result)


@pytest.mark.parametrize(
    ("text", "application"),
    [
        (PAINT_ORDER, "Paint"),
        (V3_27, "Mapa de caracteres"),
        (V3_49, "7-Zip File Manager"),
        (V3_24, "Visor de eventos"),
        ("abrí spotify", None),
        ("en spotify me encanta esta canción", None),
        ("en Spotify borrá la playlist Gym", None),
        ("crea una nota que diga comprar pan", None),
    ],
)
def test_ordered_in_application(text: str, application: str | None) -> None:
    assert missions.ordered_in_application(text, APPS) == application


def test_the_question_of_the_applications_own_service() -> None:
    assert decider.asks_for_the_application_itself(("audio.app.volume.adjust",), 1)
    assert not decider.asks_for_the_application_itself(("audio.app.volume.adjust",), 2)
    assert not decider.asks_for_the_application_itself(("note.create",), 1)
    assert not decider.asks_for_the_application_itself(("input.pointer.control",), 1)
    assert not decider.asks_for_the_application_itself((), 1)


def test_one_clause_read_alone_as_another_operation_is_no_request_apart() -> None:
    """L3 guard (lectura M1): the framed clause also reads alone as web.search; with one clause there is nothing
    apart from it. Two clauses keep what was read apart (contracase)."""

    assert decider.order_served_elsewhere(("web.search",), 1, doing_in_place=True, read_apart=("web.search",)) == (
        "elsewhere"
    )
    assert decider.order_served_elsewhere(("app.open", "note.create"), 2, read_apart=("app.open", "note.create")) is None


# ------------------------------------------------------------ descomposición (M6, diseño 5)


def test_clauses_with_the_application_resolved_are_all_sub_goals() -> None:
    mission = missions.mission_request(V3_49, APPS)
    assert mission is not None and mission.application == "7-Zip File Manager"
    assert [(step.application, step.free) for step in mission.steps] == [
        ("7-Zip File Manager", True), ("7-Zip File Manager", True),
    ]
    assert [step.goal for step in mission.steps] == ["cambia la vista a detalles", "ordena por tamaño"]


def test_without_an_application_free_clauses_still_need_checked_ones() -> None:
    assert missions.mission_request("cambia la vista a detalles y ordena por tamaño", APPS) is None
    # and a prohibition beside free sub-goals keeps the chain out
    assert missions.mission_request(V3_49 + ", pero no cierres nada", APPS) is None


SAID = "en Paint dibujá un gato guardalo como gato.png en Documentos"


@pytest.mark.parametrize(
    ("clauses", "fits"),
    [
        (["en Paint dibujá un gato", "guardalo como gato.png en Documentos"], True),
        # an invented word
        (["en Paint dibujá un gato", "y borralo"], False),
        # an order left out («guardalo…» dropped): fewer than nine in ten content words kept
        (["en Paint dibujá un gato"], False),
        # a clause that is no order
        (["en Paint dibujá", "un gato guardalo como gato.png en Documentos"], False),
        ([], False),
    ],
)
def test_a_model_split_is_validated(clauses: list[str], fits: bool) -> None:
    assert (missions.model_clauses_fit(SAID, clauses) is not None) is fits


@pytest.mark.parametrize(
    ("text", "asks"),
    [
        ("abrí Paint cambiá el tamaño a 500 por 500 dibujá un rectángulo guardalo como caja", True),
        ("en Paint dibujá un gato guardalo como gato.png en Documentos", True),
        # the segments already split it, or one order with its modifiers
        ("en 7-zip cambia la vista a detalles y ordena por tamaño", False),
        ("Ponme el texto seleccionado en Arial, tamaño 20 y en cursiva, desde el cuadro de diálogo de Fuente", False),
        ("en el visor de eventos filtra el registro de aplicación para que solo salgan los errores", False),
    ],
)
def test_the_model_is_asked_to_split_only_a_segment_of_several_orders(text: str, asks: bool) -> None:
    assert missions.asks_for_a_model_split(text, APPS) is asks


class _Splitter:
    def __init__(self, clauses: list[str]) -> None:
        self.clauses = clauses
        self.calls = 0

    def _post_schema_object(self, _payload, _what):
        self.calls += 1
        return {"clauses": self.clauses}


def test_the_split_reaches_the_mission_only_with_the_persons_words() -> None:
    honest = _Splitter(["en Paint dibujá un gato", "guardalo como gato.png en Documentos"])
    arguments = plan_shape._mission_split_by_the_model(honest, SAID, APPS)
    assert honest.calls == 1
    assert arguments is not None and arguments["application"] == "Paint"
    assert [step["goal"] for step in arguments["steps"]][0].startswith("dibuj")
    inventing = _Splitter(["en Paint dibujá un gato", "y borralo"])
    assert plan_shape._mission_split_by_the_model(inventing, SAID, APPS) is None
    # a request the segments already split never calls the model
    joined = _Splitter(["x"])
    assert plan_shape._mission_split_by_the_model(joined, V3_49, APPS) is None
    # one order with its modifiers never calls it either
    assert plan_shape._mission_split_by_the_model(joined, "en Paint dibujá un gato grande", APPS) is None
    assert joined.calls == 0
    assert cu_model_calls.split_request_clauses(None, SAID) == ()


# ------------------------------------------------------------ pistas de ruta (diseño 6)


@pytest.mark.parametrize(
    ("goal", "value"),
    [
        ("cambia la vista a detalles", "detalles"),
        ("ordena por tamaño", "tamano"),
        ("filtra el registro de aplicación para que solo salgan los errores", "errores"),
        ("change the theme to dark", "dark"),
        # no state changed by menus, a chain, a question
        ("dibujá un círculo", None),
        ("cambia la vista a detalles; luego ordena por tamaño", None),
        ("abrir Seguridad de Windows" + missions.QUESTION_MARK + "decime cuándo", None),
    ],
)
def test_state_change_value(goal: str, value: str | None) -> None:
    assert missions.state_change_value(goal) == value


class _Router:
    """The route call answers labels; the step call answers none."""

    def __init__(self, route: list[str]) -> None:
        self.route = route
        self.payloads: list[dict[str, Any]] = []

    def _post_schema_object(self, payload, _what):
        self.payloads.append(payload)
        if payload["grammar"] == cu_model_calls.ROUTE_GRAMMAR:
            return {"route": self.route}
        return {"operation": "none", "arguments": {}, "reason": "prueba"}


def _view(*names: str) -> dict[str, Any]:
    return {
        "window": {"title": "7-Zip File Manager", "process": "7zFM"},
        "controls": [{"kind": "MenuItem", "name": name} for name in names],
        "text": {},
    }


def test_the_route_is_asked_once_and_only_as_hints(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cu_model_calls, "_ROUTE_CACHE", {})
    router = _Router(["Ver", "Detalles", "un rótulo demasiado largo para ser una etiqueta de menú de verdad"])
    view = _view("Archivo", "Editar", "Ver", "Favoritos")
    for _ in range(2):
        computer_use.decide_step(
            router, objective=V3_49, goal="cambia la vista a detalles", application="7-Zip File Manager",
            success_check=None, view=view, history=[], budget_left=8, application_names=APPS,
        )
    routes = [payload for payload in router.payloads if payload["grammar"] == cu_model_calls.ROUTE_GRAMMAR]
    assert len(routes) == 1
    steps = [payload for payload in router.payloads if payload["grammar"] != cu_model_calls.ROUTE_GRAMMAR]
    told = steps[0]["messages"][1]["content"]
    assert "Ruta probable (pistas, no actos): Ver > Detalles" in told
    assert "demasiado largo" not in told


def test_no_route_when_the_view_shows_the_value_or_the_goal_is_checked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cu_model_calls, "_ROUTE_CACHE", {})
    shows = _view("Archivo", "Ver", "Detalles")
    assert not cu_model_calls.route_wanted("cambia la vista a detalles", None, shows, [])
    assert not cu_model_calls.route_wanted("cambia la vista a detalles", "text:detalles", _view("Ver"), [])
    assert not cu_model_calls.route_wanted("dibujá un círculo", None, _view("Ver"), [])
    assert cu_model_calls.route_wanted("cambia la vista a detalles", None, _view("Ver"), [])
    stalled = [{"ok": True, "changed": False}] * cu_model_calls.ROUTE_STALL_STEPS
    assert cu_model_calls.route_wanted("cambia la vista a detalles", None, shows, stalled)
    moved = stalled[:-1] + [{"ok": True, "changed": True}]
    assert not cu_model_calls.route_wanted("cambia la vista a detalles", None, shows, moved)
    assert cu_model_calls.route_hints(None, "7-Zip File Manager", "cambia la vista a detalles") == ()


# ------------------------------------------------------------ corrección de la revisión adversarial

APPS_AND_SERVICES = (*APPS, "Calculadora")


@pytest.mark.parametrize(
    "text",
    [
        "en Chrome decime el clima de mañana",
        "en la calculadora decime cuánto es 12 por 12",
        "en Chrome decime qué pestañas tengo abiertas",
        "en Edge decime qué pestañas tengo abiertas",
        "en Spotify decime qué canción está sonando",
        "en Steam decime si tengo instalado Portal 2",
        "en Steam, decime qué juegos tengo",
        "en el administrador de tareas decime cuánta memoria uso",
        V3_61,
    ],
)
def test_a_question_said_inside_an_application_never_reads_ahead_of_the_typed_readers(text: str) -> None:
    """Review 1: the look at an application (``_looking_in``) is read for the engine's goal only; the typed readers and
    the decider read the question first (weather.current, calculator.expression.evaluate, browser.tabs.list,
    media.status, game.installed.named), and only a turn they ask about or close as a limit is a look (the gate)."""

    mission = missions.mission_request(text, APPS_AND_SERVICES)
    assert mission is not None and mission.looks_only
    read = patterns.resolve_explicit_effects(text, OPERATIONS, APPS_AND_SERVICES)
    assert read is None or "mission.computer.use" not in read.operations


def test_a_look_inside_an_order_of_doing_still_reads_ahead() -> None:
    """Contracase: an order of doing with its closing question is a mission as before (not only a look)."""

    text = "en Terminal andá a configuración y decime qué tema está activo"
    mission = missions.mission_request(text, APPS)
    assert mission is not None and not mission.looks_only


@pytest.mark.parametrize(
    ("text", "turn"),
    [
        # the turn asked about a typed operation: its question stands
        ("en Chrome decime el clima de mañana", _turn("clarify", ("weather.current",), missingFields=["location"])),
        # a typed reader reads the question alone: its answer is not on that screen
        ("en Chrome decime el clima de mañana", _turn("conversation", conversationKind="unsupported")),
        ("en el administrador de tareas decime cuánta memoria uso", _turn("clarify")),
    ],
)
def test_a_question_a_typed_operation_serves_is_no_look_at_the_application(text: str, turn: dict[str, Any]) -> None:
    assert _gate(text, turn) is turn


AFTER_SPOTIFY = [{"role": "user", "content": "abrí Spotify"}, {"role": "assistant", "content": "Abrí Spotify."}]
AFTER_STEAM = [{"role": "user", "content": "abrí Steam"}, {"role": "assistant", "content": "Abrí Steam."}]


@pytest.mark.parametrize(
    ("text", "history", "turn"),
    [
        ("¿cuál es la capital de Francia?", AFTER_SPOTIFY, _turn("clarify")),
        ("¿cómo estás?", AFTER_SPOTIFY, _turn("clarify")),
        ("¿qué opinás?", AFTER_SPOTIFY, _turn("clarify")),
        ("¿cuál es mi contraseña?", AFTER_SPOTIFY, _turn("clarify")),
        ("¿cuál es la capital de Francia?", AFTER_SPOTIFY, _turn("conversation", conversationKind="unsupported")),
        ("¿qué hora es?", AFTER_STEAM, _turn("clarify")),
    ],
)
def test_a_question_about_anything_after_an_application_was_opened_is_no_look_at_it(
    text: str, history: list[dict[str, str]], turn: dict[str, Any],
) -> None:
    """Review 2: the conversation's application is the question's only when the question points at what it shows."""

    assert _gate(text, turn, history) is turn


def test_a_question_that_points_at_the_view_after_an_application_was_opened_is_a_look_at_it() -> None:
    result = _gate("¿cuántas canciones hay?", _turn("clarify"), AFTER_SPOTIFY)
    assert _engine(result)
    assert result["objective"] == "en Spotify, decime cuántas canciones hay"


@pytest.mark.parametrize(
    ("text", "rewritten"),
    [
        ("¿cuáles tienen impacto alto?", "en Spotify, decime cuáles tienen impacto alto"),
        ("¿cuántas canciones hay?", "en Spotify, decime cuántas canciones hay"),
        ("¿qué dice ese botón?", "en Spotify, decime qué dice ese botón"),
        ("¿cuál es la capital de Francia?", None),
        ("¿cómo estás?", None),
        ("¿cuáles son tus favoritas?", None),
    ],
)
def test_a_question_of_the_conversation_points_at_the_view(text: str, rewritten: str | None) -> None:
    assert missions.application_question(text, APPS, "Spotify") == rewritten


@pytest.mark.parametrize(
    ("text", "turn"),
    [
        ("en spotify subí el volumen", _turn("clarify", ("audio.volume.adjust",), missingFields=["amount"])),
        ("en spotify subí el volumen", _turn("clarify")),
        ("en spotify subí el volumen y pasá a la siguiente",
         _turn("clarify", ("audio.app.volume.adjust",), missingFields=["amount"])),
        ("en Discord bajá el volumen", _turn("clarify")),
        ("en Chrome subí el volumen", _turn("conversation", conversationKind="unsupported")),
        ("en Chrome subí el brillo", _turn("clarify")),
    ],
)
def test_a_relative_level_without_its_amount_always_asks_how_much(text: str, turn: dict[str, Any]) -> None:
    """Review 3 (owner rule: a relative volume or brightness without a quantity asks the amount, no default step),
    whatever operation the turn chose, or none, and in an order of several clauses."""

    assert _gate(text, turn) is turn


def test_a_relative_level_with_its_amount_is_no_question_of_how_much() -> None:
    assert missions.level_amount_unsaid("en spotify subí el volumen", APPS)
    assert not missions.level_amount_unsaid("en spotify subí el volumen un 10", APPS)
    assert not missions.level_amount_unsaid("en Paint subí el grosor del pincel", APPS)
    # contracase: a question for another value said inside an application is still the engine's
    result = _gate("en notas rápidas creá una nota nueva", _turn("clarify", ("note.create",), missingFields=["title"]))
    assert _engine(result)


@pytest.mark.parametrize(
    ("text", "turn"),
    [
        ("en la terminal ejecutá shutdown /s /t 0", _turn("action", ("shell.command.run",))),
        ("en la terminal apagá la computadora", _turn("action", ("system.power",))),
        ("en la terminal escribí shutdown /s y dale enter", _turn("clarify")),
        ("en la terminal escribí shutdown /s y dale enter", _turn("clarify", ("input.text.type",))),
        ("en la terminal reiniciá la computadora", _turn("conversation", conversationKind="unsupported")),
        ("en Discord cerrá sesión", _turn("clarify")),
        ("en Steam desinstalá Portal 2", _turn("clarify", ("package.uninstall",))),
    ],
)
def test_what_confirms_on_its_own_route_is_never_the_engines(text: str, turn: dict[str, Any]) -> None:
    """Review 4 (owner rule: never restart, shut down or sign out; RiskPolicy only confirms Enter in a composer)."""

    assert _gate(text, turn) is turn


def test_an_operation_whose_catalog_risk_is_confirmed_keeps_its_route() -> None:
    turn = _turn("action", ("audio.mute",))
    said = [{"role": "user", "content": V3_53}]
    message = {"id": "r5", "text": V3_53, "history": said}
    risky = {**TOOLS, "audio.mute": {"function": {"risk": "work_loss"}}}
    assert engine_handoff._engine_for_an_unserved_order(turn, message, risky, APPS) is turn
    # contracase: the same operation with a reversible risk is still taken from an order said inside OBS
    reversible = {**TOOLS, "audio.mute": {"function": {"risk": "low_reversible"}}}
    assert _engine(engine_handoff._engine_for_an_unserved_order(turn, message, reversible, APPS))


def test_order_served_elsewhere_never_takes_what_keeps_its_route() -> None:
    assert decider.order_served_elsewhere(("shell.command.run",), 1, doing_in_place=True) is None
    assert decider.order_served_elsewhere(("system.power",), 1, doing_in_place=True) is None
    assert decider.order_served_elsewhere(("audio.mute",), 1, doing_in_place=True, kept=("audio.mute",)) is None
    # contracase: the PC's sound, said inside OBS, is still served elsewhere
    assert decider.order_served_elsewhere(("audio.mute",), 1, doing_in_place=True) == "elsewhere"


@pytest.mark.parametrize(
    ("text", "tries"),
    [
        ("en la terminal apagá la computadora", False),
        ("en la terminal escribí shutdown /s", False),
        ("en Discord cerrá sesión", False),
        ("in the terminal turn off the computer", False),
        # contracases: switching something off inside an application
        ("en Discord apagá el micrófono", True),
        ("en OBS Studio apagá la cámara", True),
    ],
)
def test_the_engine_never_tries_the_power_of_the_pc(text: str, tries: bool) -> None:
    assert missions.engine_can_try(text, APPS) is tries


def test_t_drag_4_is_the_drag_limit_never_the_engines() -> None:
    # Estabilización L: a stroke drawn with the mouse is a declared limit; the unresolved-input question about it is
    # not handed to the engine (it has no act for it).
    assert _gate(T_DRAG_4, _turn("clarify"))["effectOperations"] != ["mission.computer.use"]
    assert missions.ordered_in_application(T_DRAG_4, APPS) is None
