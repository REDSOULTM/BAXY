"""Computer use v3, límites del PC (M2): pantallas de puerta.

Vivo 2026-10-07 (v3-05, v3-06, v3-07): Outlook abrió en su asistente de cuenta («Configuración de cuenta de correo
electrónico», «¿No tiene ninguna cuenta?») y BAXY pulsó teclas y «Opciones avanzadas» sin decir la causa. Otras
puertas medidas: unas notas que piden iniciar sesión o se están actualizando, un cliente de repositorios que «Can't
find» una carpeta borrada. La mente lo detecta de forma general en la vista (palabras en semantic/app_gates.py), no
pulsa nada en la puerta y la misión lo dice con el texto de la pantalla. Contracasos: Word con un documento y su botón
«Iniciar sesión», la Tienda de Steam con su enlace «iniciar sesión», un objetivo que nombra un control de la puerta y
un pedido que es justamente iniciar sesión.
"""

from __future__ import annotations

import pytest

from baxy_mind import computer_use
from baxy_mind import cu_view
from baxy_mind import cu_gates
from baxy_mind import cu_validate
from baxy_mind import cu_projection
from baxy_mind import cu_finals
from baxy_mind.semantic import app_gates


class _NoModel:
    """A gate is decided without the model: any call to it fails the test."""

    def __getattr__(self, name: str):
        raise AssertionError(f"el modelo no se consulta en una puerta ({name})")


def _control(i: int, kind: str, name: str, value: str | None = None) -> dict:
    return {"i": i, "kind": kind, "name": name, "state": "", "value": value,
            "rect": {"x": 100, "y": 100 + 40 * i, "w": 120, "h": 30}}


def _view(title: str, controls: list[dict], lines: list[str], process: str = "APP") -> dict:
    return {
        "window": {"title": title, "process": process, "processId": 77, "hwnd": 5, "requested": True,
                   "rect": {"x": 0, "y": 0, "w": 800, "h": 600}, "focused": None},
        "controls": controls,
        "controlCount": len(controls),
        "text": {"C": lines},
    }


def _decide(view: dict, *, objective: str, goal: str, history: list[dict] | None = None,
            application: str | None = "Correo") -> dict:
    return computer_use.decide_step(
        _NoModel(), objective=objective, goal=goal, application=application, success_check=None, view=view,
        history=history if history is not None else [{"step": 1, "operation": "app.open", "ok": True}],
        budget_left=20, application_names=["Correo"],
    )


# The account wizard as the live view read it: no tree, its title and a few lines.
WIZARD = _view("Configuración de cuenta de correo electrónico", [],
               ["Outlook", "¿No tiene ninguna cuenta?", "Opciones avanzadas"], process="OUTLOOK")
# v3-05 as the mission saw it: bound to the splash («Abriendo - Outlook»), the wizard's field read by OCR beside the
# address the person had written in it.
SPLASH = _view("Abriendo - Outlook", [],
               ["Outlook", "correo electrónico", "persona@ejemplo.cl", "Opciones avanzadas v", "Opciones avanzadas"],
               process="OUTLOOK")
SIGN_IN = _view("Notas", [_control(0, "Button", "Iniciar sesión"), _control(1, "Button", "Cerrar")],
                ["Notas", "Inicia sesión para sincronizar tus notas"])
UPDATING = _view("Notas", [], ["Notas", "Actualizando…"])
MISSING = _view("Repositorios", [_control(0, "Button", "Locate…"), _control(1, "Button", "Remove")],
                ["Can't find \"proyecto\"", "It was last seen at C:\\Users\\persona\\proyecto"])


@pytest.mark.parametrize(
    ("view", "kind", "text"),
    [
        (WIZARD, "account", "Configuración de cuenta de correo electrónico"),
        (SPLASH, "account", "correo electrónico"),
        (SIGN_IN, "account", "Inicia sesión para sincronizar tus notas"),
        (UPDATING, "updating", "Actualizando…"),
        (MISSING, "missing", "Can't find \"proyecto\""),
    ],
)
def test_a_gate_screen_is_said_with_its_text_and_nothing_is_pressed(view: dict, kind: str, text: str) -> None:
    decision = _decide(view, objective="en el correo cambiate al calendario", goal="ir a calendario")
    assert decision["operation"] == "none"
    assert decision["code"] == cu_gates.APP_GATE
    assert decision["arguments"] == {"evidence": text, "gate": kind}
    assert cu_view.view_contains(view, text)


def test_the_persons_address_is_never_the_quoted_text() -> None:
    gate = cu_gates.app_gate(SPLASH)
    assert gate is not None and "@" not in gate["text"]


def test_a_control_to_pass_the_gate_without_giving_anything_is_pressed_once() -> None:
    view = _view("Notas", [_control(0, "Button", "Iniciar sesión"), _control(1, "Button", "Ahora no")],
                 ["Notas", "Inicia sesión para sincronizar tus notas"])
    first = _decide(view, objective="abre notas y crea una nota", goal="hacer clic en nueva nota")
    assert first["operation"] == "input.visible.click"
    assert first["arguments"]["label"] == "Ahora no"
    history = [{"step": 1, "operation": "app.open", "ok": True},
               {"step": 2, "operation": "input.visible.click", "label": "Ahora no", "ok": True}]
    again = _decide(view, objective="abre notas y crea una nota", goal="hacer clic en nueva nota", history=history)
    assert again["operation"] == "none" and again["code"] == cu_gates.APP_GATE


def _word_with_document() -> dict:
    controls = [_control(i, "TabItem", name) for i, name in enumerate(
        ["Archivo", "Inicio", "Insertar", "Dibujar", "Diseño", "Disposición", "Referencias", "Correspondencia",
         "Revisar", "Vista", "Ayuda"])]
    controls += [_control(11, "Button", "Iniciar sesión"), _control(12, "Document", "Documento1"),
                 _control(13, "Button", "Compartir")]
    return _view("Documento1 - Word", controls, ["Documento1 - Word", "Iniciar sesión"], process="WINWORD")


def _store_with_sign_in_link() -> dict:
    lines = ["TIENDA", "BIBLIOTECA", "COMUNIDAD", "iniciar sesión", "Destacados y recomendados", "Ofertas especiales",
             "Explorar por categoría", "Novedades populares", "Más vendidos", "Próximos lanzamientos",
             "Juegos gratuitos", "Acción", "Aventura", "Estrategia", "Simulación", "Deportes", "Carreras"]
    # A window without a tree: one control, the store read by OCR.
    return _view("Steam", [_control(0, "Pane", "Steam")], lines, process="steamwebhelper")


def _downloads_with_a_game_updating(lines: list[str] | None = None) -> dict:
    # Revisión: Steam's downloads read by OCR (one Pane, 8 lines); what updates is a game of the list, not Steam.
    lines = lines or ["Steam", "TIENDA", "BIBLIOTECA", "COMUNIDAD", "DESCARGAS", "Counter-Strike 2", "Actualizando",
                      "45%"]
    return _view("Steam", [_control(0, "Pane", "Steam")], lines, process="steamwebhelper")


def _short_store_with_sign_in_link() -> dict:
    # The store with fewer lines than the bound (15): still its bar of places.
    lines = ["TIENDA", "BIBLIOTECA", "COMUNIDAD", "iniciar sesión", "Destacados y recomendados", "Ofertas especiales"]
    return _view("Steam", [_control(0, "Pane", "Steam")], lines, process="steamwebhelper")


def _clock_focus_sessions() -> dict:
    # «Iniciar sesión de concentración» is a page of the Clock among its places, never a sign-in.
    controls = [_control(i, "ListItem", name) for i, name in enumerate(
        ["Sesiones de concentración", "Temporizador", "Alarma", "Reloj mundial", "Cronómetro"])]
    controls += [_control(5, "Button", "Iniciar sesión de concentración")]
    return _view("Reloj", controls, ["Reloj", "Sesiones de concentración", "Iniciar sesión de concentración"])


@pytest.mark.parametrize("view", [
    _word_with_document(), _store_with_sign_in_link(), _downloads_with_a_game_updating(),
    _downloads_with_a_game_updating(["Steam", "DESCARGAS", "BIBLIOTECA", "Counter-Strike 2", "Actualizando", "45%"]),
    _short_store_with_sign_in_link(), _clock_focus_sessions(),
])
def test_a_working_window_that_offers_to_sign_in_is_no_gate(view: dict) -> None:
    assert cu_gates.app_gate(view) is None
    assert cu_gates._gate_step(view, [], "andá a Vista", "ir a vista") is None


def test_a_working_window_with_a_line_saying_updating_lets_a_success_through() -> None:
    # Revisión: «ir a descargas» on Steam reached, proved by the game listed, never vetoed as the app updating.
    done = cu_validate.validate_decision(
        {"act": "done", "evidence": "Counter-Strike 2"}, view=_downloads_with_a_game_updating(), last_failed=None,
        application_names=[], history=[], goal="ir a descargas")
    assert done["operation"] == "done"


def test_a_window_with_a_document_of_the_persons_is_no_gate() -> None:
    # Revisión: the gate's own «Document» kinds were shadowed by another constant of the module; a short window with
    # the person's document and a sign-in button is still a working window.
    view = _view("Nota.txt - Editor", [_control(0, "Document", "Texto"), _control(1, "Button", "Iniciar sesión")],
                 ["Nota.txt - Editor", "Iniciar sesión"])
    assert cu_gates.app_gate(view) is None


def test_a_line_saying_the_gate_among_much_content_is_no_gate() -> None:
    # No tree and no bar of places, but the phrase is one line among the window's content.
    view = _view("Fotos", [], ["Fotos", "Álbum de verano", "Playa", "Montaña", "Cumpleaños", "Viaje", "Actualizando"])
    assert cu_gates.app_gate(view) is None


def test_a_goal_that_names_a_control_of_the_gate_takes_its_own_step() -> None:
    assert cu_gates._gate_step(WIZARD, [], "en outlook abrí opciones avanzadas",
                                   "hacer clic en Opciones avanzadas") is None


@pytest.mark.parametrize("objective", ["iniciá sesión en notas", "sign in to my notes", "agregá mi cuenta al correo",
                                       "actualizá las notas",
                                       # Plurals and conjugations (revisión: the exact word let them pass).
                                       "busca actualizaciones", "instala las actualizaciones pendientes",
                                       "check for updates", "abre mis cuentas", "ve a sesiones de concentración",
                                       "logging in to my notes", "log into the mail"])
def test_a_request_about_the_gate_itself_is_never_stopped_by_it(objective: str) -> None:
    assert app_gates.asks_about_the_gate(objective)
    assert cu_gates._gate_step(SIGN_IN, [], objective, "hacer clic en iniciar sesión") is None


@pytest.mark.parametrize("objective", ["sin darte cuenta abrí las notas", "me di cuenta de que el correo no abre",
                                       "tené en cuenta el calendario", "cuéntame qué dice el correo",
                                       "abre el blog de notas", "en el correo cambiate al calendario"])
def test_a_request_that_only_looks_like_one_about_the_gate_is_not(objective: str) -> None:
    # Counter-case: «cuenta» in a saying, a word that only begins alike, an unrelated «log».
    assert not app_gates.asks_about_the_gate(objective)


def test_a_sparse_window_without_gate_words_is_no_gate() -> None:
    view = _view("Reloj", [_control(0, "Button", "Iniciar"), _control(1, "Button", "Restablecer")],
                 ["Reloj", "00:00:00", "Cronómetro"])
    assert cu_gates.app_gate(view) is None


def test_a_success_over_a_gate_is_vetoed() -> None:
    # Live v3-34: a success told over a notes app updating itself.
    vetoed = cu_validate.validate_decision(
        {"act": "done", "evidence": "Actualizando…"}, view=UPDATING, last_failed=None, application_names=[],
        history=[], goal="ir a notas")
    assert vetoed["operation"] == "none" and vetoed["code"] == cu_gates.APP_GATE
    # Counter-case: the same proof on a working window is a success.
    working = _view("Reloj", [_control(0, "Button", "Iniciar"), _control(1, "TabItem", "Cronómetro")],
                    ["Reloj", "Cronómetro", "00:00:00"])
    done = cu_validate.validate_decision(
        {"act": "done", "evidence": "00:00:00"}, view=working, last_failed=None, application_names=[], history=[],
        goal="ir a cronómetro")
    assert done["operation"] == "done"


def test_a_success_after_pressing_the_control_the_goal_names_on_the_gate_holds() -> None:
    # Revisión: the step and the success share one rule. The goal names «Opciones avanzadas» of the wizard: pressing it
    # was the goal's, and so is the success after it, while it shows and once it is gone from the view.
    # The click carries the receipt the App gives a press that changed the window («changed», HistoryForMind): the
    # one judge of a done (llegada-evidencia M1) asks the goal for an act with an effect, on a gate or not.
    history = [{"step": 1, "operation": "app.open", "ok": True},
               {"step": 2, "operation": "input.visible.click", "label": "Opciones avanzadas", "ok": True,
                "changed": True}]
    after = _view("Configuración de cuenta de correo electrónico", [],
                  ["Outlook", "Permitirme configurar mi cuenta manualmente"], process="OUTLOOK")
    for view in (WIZARD, after):
        done = cu_validate.validate_decision(
            {"act": "done", "evidence": view["text"]["C"][-1]}, view=view, last_failed=None, application_names=[],
            history=history, goal="hacer clic en Opciones avanzadas", objective="en outlook abrí opciones avanzadas")
        assert done["operation"] == "done"
        assert cu_gates._gate_step(view, history, "en outlook abrí opciones avanzadas",
                                       "hacer clic en Opciones avanzadas") is None
    # Counter-case: a click on something else of the gate does not make the gate the goal's.
    other = [{"step": 1, "operation": "app.open", "ok": True},
             {"step": 2, "operation": "input.visible.click", "label": "Siguiente", "ok": True}]
    vetoed = cu_validate.validate_decision(
        {"act": "done", "evidence": "Permitirme configurar mi cuenta manualmente"}, view=after, last_failed=None,
        application_names=[], history=other, goal="ir a calendario", objective="en el correo cambiate al calendario")
    assert vetoed["operation"] == "none" and vetoed["code"] == cu_gates.APP_GATE


def test_a_success_of_a_subgoal_of_a_request_about_the_gate_holds() -> None:
    # Revisión: «inicia sesión en Notas y abre mis notas», sub-goal «ir a notas»: the request is about the gate, for
    # its step as for its success.
    objective = "inicia sesión en Notas y abre mis notas"
    assert cu_gates._gate_step(SIGN_IN, [], objective, "ir a notas") is None
    done = cu_validate.validate_decision(
        {"act": "done", "evidence": "Inicia sesión para sincronizar tus notas"}, view=SIGN_IN, last_failed=None,
        application_names=[], history=[], goal="ir a notas", objective=objective)
    assert done["operation"] == "done"
    # Counter-case: the same sub-goal of a request that is not about the gate is stopped by it; the application's
    # name on the gate and the gate's own phrase («…tus notas») are not the goal's place.
    stopped = cu_gates._gate_step(SIGN_IN, [], "abre notas y crea una nota", "ir a notas")
    assert stopped is not None and stopped["code"] == cu_gates.APP_GATE
    vetoed = cu_validate.validate_decision(
        {"act": "done", "evidence": "Inicia sesión para sincronizar tus notas"}, view=SIGN_IN, last_failed=None,
        application_names=[], history=[], goal="ir a notas", objective="abre notas y crea una nota")
    assert vetoed["operation"] == "none" and vetoed["code"] == cu_gates.APP_GATE


def test_a_gate_that_stayed_after_its_skip_says_it_was_pressed() -> None:
    # Revisión: after «Ahora no» the gate stayed; the stop carries it and the final never says nothing was pressed.
    view = _view("Notas", [_control(0, "Button", "Iniciar sesión"), _control(1, "Button", "Ahora no")],
                 ["Notas", "Inicia sesión para sincronizar tus notas"])
    history = [{"step": 1, "operation": "app.open", "ok": True},
               {"step": 2, "operation": "input.visible.click", "label": "Ahora no", "ok": True}]
    stop = _decide(view, objective="abre notas y crea una nota", goal="hacer clic en nueva nota", history=history)
    assert stop["arguments"] == {"evidence": "Inicia sesión para sincronizar tus notas", "gate": "account",
                                 "pressed": "Ahora no"}
    observed = {"goal": "ir a notas", "reached": False, "steps": [], "window": {"title": "Notas"},
                "stoppedBy": "computer_use_app_gate",
                "gate": {"kind": "account", "text": "Inicia sesión para sincronizar tus notas", "pressed": "Ahora no"}}
    seen = cu_projection.project_seen(observed, "es")
    assert "pulsé «Ahora no» y siguió ahí" in seen["stoppedBecause"]
    assert "no pulsé nada" not in seen["stoppedBecause"]
    assert "I pressed «Ahora no» and it stayed there" in cu_projection.project_seen(observed, "en")["stoppedBecause"]
    # Counter-case: a skip that failed was not pressed.
    failed = history[:-1] + [{**history[-1], "ok": False}]
    assert "pressed" not in _decide(view, objective="abre notas y crea una nota", goal="hacer clic en nueva nota",
                                    history=failed)["arguments"]


def test_the_final_says_the_gate_with_the_text_of_the_screen() -> None:
    observed = {
        "goal": "ir a calendario", "application": "Outlook (classic)", "reached": False, "steps": [],
        "window": {"title": "Configuración de cuenta de correo electrónico"},
        "stoppedBy": "computer_use_app_gate",
        "gate": {"kind": "account", "text": "Configuración de cuenta de correo electrónico"},
    }
    seen = cu_projection.project_seen(observed, "es")
    assert seen["gate"] == "Configuración de cuenta de correo electrónico"
    assert "«Configuración de cuenta de correo electrónico»" in seen["stoppedBecause"]
    assert "cuenta" in seen["stoppedBecause"]
    sentence = cu_finals.floor_sentence(observed, english=False, succeeded=False)
    assert "«Configuración de cuenta de correo electrónico»" in sentence and "no pulsé nada" in sentence
    english = cu_projection.project_seen(observed, "en")
    assert "sign-in" in english["stoppedBecause"]


def test_a_gate_stop_without_its_text_keeps_the_generic_cause() -> None:
    observed = {"goal": "ir a calendario", "reached": False, "steps": [], "window": {"title": "Outlook"},
                "stoppedBy": "computer_use_app_gate"}
    seen = cu_projection.project_seen(observed, "es")
    assert "gate" not in seen
    assert "no pulsé nada" in seen["stoppedBecause"]
