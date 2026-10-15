"""Computer use: una consola que quedó como administrador (pasada v3 r9, v3-23 y v3-65).

«abre servicios» abrió la consola por el shell y Windows la elevó sola; el turno siguiente («cambiala a la vista
estándar») vio la ventana elevada (sin árbol, sin clics) y se rindió. Medido en vivo (2026-10-08): la misma consola
abierta con los derechos de la persona (mmc.exe con RunAsInvoker) queda sin elevar y legible; el Administrador de tareas
y el Monitor de recursos se elevan solos desde su código aunque se abran así. La vista lo dice (window.elevated, por el
token del proceso; window.reopensUnraised, por el manifiesto del programa): la consola se abre otra vez con los
derechos de la persona antes de cualquier otro paso; el programa que se eleva solo sigue siendo un límite.
"""

from __future__ import annotations

from baxy_mind import computer_use
from baxy_mind import cu_window


class _NoModel:
    def _post_schema_object(self, payload, label):  # pragma: no cover - the test fails if the model is asked
        raise AssertionError("reopening a raised console needs no model")


_APPS = ("Servicios", "Visor de eventos", "Administrador de tareas", "Monitor de recursos", "Bloc de notas")


def _raised_view(title: str, process: str, reopens: bool | None) -> dict:
    """The view r9 read on the raised window: the window found for the application, in front, with an empty tree."""

    window: dict = {"title": title, "process": process, "requested": True, "foreground": True, "elevated": True}
    if reopens is not None:
        window["reopensUnraised"] = reopens
    return {"window": window, "controls": [], "text": []}


def _step(view: dict, application: str, objective: str, goal: str, history: list[dict] | None = None) -> dict:
    return computer_use.decide_step(
        _NoModel(), objective=objective, goal=goal, application=application, success_check=None, view=view,
        history=history or [], budget_left=12, application_names=_APPS,
    )


def test_v3_65_the_raised_services_console_is_opened_again_first() -> None:
    decision = _step(_raised_view("Servicios", "mmc", True), "Servicios", "cambiala a la vista estandar",
                     "cambiar a la vista estándar")

    assert decision["operation"] == "app.open"
    assert decision["arguments"]["appId"] == "Servicios"
    assert decision.get("arguments", {}).get("foreground") is None


def test_v3_23_the_raised_event_viewer_is_opened_again_first() -> None:
    decision = _step(_raised_view("Visor de eventos", "mmc", True), "Visor de eventos",
                     "en el visor de eventos andá a registros de windows, sistema", "ir a sistema")

    assert decision["operation"] == "app.open"
    assert decision["arguments"]["appId"] == "Visor de eventos"


def test_reopens_unraised_reads_the_view_only() -> None:
    assert cu_window.reopens_unraised(_raised_view("Servicios", "mmc", True)) is True
    assert cu_window.reopens_unraised(_raised_view("Servicios", "mmc", False)) is False
    assert cu_window.reopens_unraised(_raised_view("Servicios", "mmc", None)) is False
    assert cu_window.reopens_unraised({"window": {"reopensUnraised": True}}) is False
    assert cu_window.reopens_unraised({}) is False


class _AskedModel:
    """Records that the mind went past its deterministic rules and asked the model."""

    asked = False

    def _post_schema_object(self, payload, label):
        type(self).asked = True
        raise _Asked()


class _Asked(Exception):
    pass


def test_counter_case_the_task_manager_raises_itself_and_is_not_reopened() -> None:
    # v3-20..22, v3-72: Taskmgr starts again as administrator by itself (measured with RunAsInvoker): the view carries
    # no reopensUnraised, so the mind's reopening rule does not fire (the model would be asked). The App stops with
    # computer_use_window_elevated before asking the mind at all: its twin is
    # ComputerUseMissionTests.OnARaisedWindowOnlyTheReopeningIsCarriedOut (C#).
    view = _raised_view("Administrador de tareas", "Taskmgr", None)

    assert cu_window.application_is_in_front(view, "Administrador de tareas")
    assert cu_window.reopens_unraised(view) is False
    _AskedModel.asked = False
    try:
        decision = computer_use.decide_step(
            _AskedModel(), objective="fijate cuánta CPU usa", goal="ver la CPU", application="Administrador de tareas",
            success_check=None, view=view, history=[], budget_left=12, application_names=_APPS,
        )
    except _Asked:
        decision = None
    assert _AskedModel.asked is True
    assert decision is None or decision.get("operation") != "app.open"


def test_counter_case_a_raised_console_after_a_step_is_not_reopened_again() -> None:
    # The reopening happens once, before any step; with history the rule does not fire again (the model is asked; the
    # App stops on the raised window before that, ComputerUseMissionTests.OnARaisedWindowOnlyTheReopeningIsCarriedOut).
    view = _raised_view("Servicios", "mmc", True)
    _AskedModel.asked = False
    try:
        decision = computer_use.decide_step(
            _AskedModel(), objective="cambiala a la vista estandar", goal="cambiar a la vista estándar",
            application="Servicios", success_check=None, view=view,
            history=[{"operation": "app.open", "arguments": {"appId": "Servicios"}, "ok": True}],
            budget_left=11, application_names=_APPS,
        )
    except _Asked:
        decision = None
    assert _AskedModel.asked is True
    assert decision is None
