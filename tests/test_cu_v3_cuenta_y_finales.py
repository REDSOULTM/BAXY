"""Pasada v3 r9: seguridad de cuenta y finales sin pasos.

v3-34 (vivo 2026-10-08, «abre notas rápidas y crea una nota que diga llamar al dentista el martes»): la app de notas
abrió en su pantalla «Haz una copia de seguridad de tus notas… Solo tienes que iniciar sesión» con su botón «Iniciar
sesión». La puerta no se vio por dos motivos medidos: el menú de sistema de la ventana («Sistema» dentro de «Barra de
menús del sistema», en la barra de título) contó como navegación, y la frase que el OCR partió en cuatro renglones
contó como cuatro líneas de contenido. El modelo pulsó «Sistema», luego «Iniciar sesión», y citó «Iniciando sesión...»
como prueba de la nota: «iniciar sesión» no estaba entre los actos de cuenta. Gemelos con las vistas reales del journal
y contracasos (el Reloj con «Iniciar sesión de concentración», una barra de título con los menús propios de la ventana,
un objetivo que pide iniciar sesión).
"""

from __future__ import annotations

from baxy_mind import computer_use
from baxy_mind import cu_window
from baxy_mind import cu_gates
from baxy_mind import cu_validate
from baxy_mind.semantic.account_acts import account_act, goal_asks_for


class _NoModel:
    """A gate is decided without the model: any call to it fails the test."""

    def __getattr__(self, name: str):
        raise AssertionError(f"el modelo no se consulta en una puerta ({name})")


def _c(i: int, kind: str, name: str, x: int, y: int, w: int, h: int, state: str = "") -> dict:
    return {"i": i, "kind": kind, "name": name, "state": state, "rect": {"x": x, "y": y, "w": w, "h": h}}


# The journal's view at 17:37:01 (v3-34, step 2), controls and OCR zones as read.
_SIGN_IN_CONTROLS = [
    _c(0, "Button", "Cerrar", 1119, 111, 50, 50),
    _c(1, "Hyperlink", "Directiva de privacidad", 900, 320, 139, 34),
    _c(2, "Button", "Iniciar sesión", 839, 659, 260, 55, "focused"),
    _c(3, "MenuItem", "Sistema", 769, 119, 28, 28, "collapsed"),
    _c(4, "Pane", "Title", 769, 111, 400, 790),
    _c(5, "Text", "Haz una copia de seguridad de tus notas y sincroniza en todo ... iniciar sesión.", 820, 211, 297, 100),
    _c(6, "Text", "Iniciar sesión", 917, 673, 102, 24),
    _c(7, "TitleBar", "Notas rápidas", 769, 119, 400, 29),
    _c(8, "MenuBar", "Barra de menús del sistema", 769, 119, 28, 28),
]
_SIGN_IN_TEXT = {
    "T": ["Haz una copia de seguridad de tus", "notas y sincroniza en todos los",
          "dispositivos. Solo tienes que iniciar", "sesión.", "Directiva de privacidad"],
    "TR": ["x"],
    "B": ["Iniciar sesión"],
}


def _view(controls: list[dict], text: dict | None, title: str = "Notas rápidas") -> dict:
    return {
        "window": {"title": title, "process": "Notes", "requested": True, "foreground": False,
                   "rect": {"x": 768, "y": 110, "w": 402, "h": 792}},
        "controls": controls,
        "controlCount": len(controls),
        "text": text,
    }


SIGN_IN_SCREEN = _view(_SIGN_IN_CONTROLS, _SIGN_IN_TEXT)
# 17:37:07, after the click: «Iniciar sesión» gone, «Iniciando sesión...» in its place, no OCR.
SIGNING_IN = _view(
    [c for c in _SIGN_IN_CONTROLS if c["name"] != "Iniciar sesión"]
    + [_c(9, "Text", "Iniciando sesión...", 900, 673, 140, 24)],
    None,
)
OBJECTIVE = "abre notas rápidas y crea una nota que diga llamar al dentista el martes"
GOAL = "crea una nota que diga llamar al dentista el martes"
OPENED = [{"step": 1, "operation": "app.open", "ok": True}]


def _decide(view: dict, *, objective: str = OBJECTIVE, goal: str = GOAL) -> dict:
    return computer_use.decide_step(
        _NoModel(), objective=objective, goal=goal, application="Notas rápidas", success_check=None, view=view,
        history=list(OPENED), budget_left=12, application_names=["Notas rápidas"],
    )


def test_the_sign_in_screen_of_the_live_case_is_a_gate() -> None:
    gate = cu_gates.app_gate(SIGN_IN_SCREEN)
    assert gate is not None and gate["kind"] == "account"
    decision = _decide(SIGN_IN_SCREEN)
    assert decision["operation"] == "none" and decision["code"] == cu_gates.APP_GATE
    # The quoted text is one the view holds, never the sentence the OCR wrapped.
    assert decision["arguments"]["evidence"] in {"Iniciar sesión", *_SIGN_IN_TEXT["T"]} | {
        c["name"] for c in _SIGN_IN_CONTROLS}


def test_the_same_screen_without_its_ocr_is_a_gate_too() -> None:
    assert cu_gates.app_gate(_view(_SIGN_IN_CONTROLS, None)) is not None


def test_signing_in_is_never_the_proof_of_the_note() -> None:
    history = OPENED + [{"step": 2, "operation": "input.visible.click", "ok": True, "label": "Iniciar sesión"}]
    done = cu_validate.validate_decision(
        {"act": "done", "evidence": "Iniciando sesión..."}, view=SIGNING_IN, last_failed=None,
        application_names=["Notas rápidas"], goal=GOAL, history=history, objective=OBJECTIVE)
    assert done["operation"] == "none"
    assert done["code"] == cu_gates.APP_GATE


def test_signing_in_is_never_the_proof_of_the_note_on_a_working_window_either() -> None:
    # Review of r9, finding 7: the same «done» on a window with content of its own (no gate) is refused by the
    # citation itself, never only by the gate.
    controls = SIGNING_IN["controls"] + [_c(20 + n, "ListItem", f"Nota {n}", 780, 300 + 40 * n, 380, 36)
                                         for n in range(4)]
    view = _view(controls, {"C": ["Nota 0", "Nota 1", "Nota 2", "Nota 3", "Iniciando sesión..."]})
    assert cu_gates.app_gate(view) is None
    history = OPENED + [{"step": 2, "operation": "input.visible.click", "ok": True, "label": "Iniciar sesión"}]
    for evidence in ("Iniciando sesión...", "Signing in..."):
        done = cu_validate.validate_decision(
            {"act": "done", "evidence": evidence}, view=_view(controls, {"C": ["Nota 0", evidence]}),
            last_failed=None, application_names=["Notas rápidas"], goal=GOAL, history=history, objective=OBJECTIVE)
        assert done["operation"] == "none" and done["code"] == "evidence_not_visible", evidence
    # Counter-case: a goal that asks to sign in is proved by it.
    asked = cu_validate.validate_decision(
        {"act": "done", "evidence": "Iniciando sesión..."}, view=view, last_failed=None,
        application_names=["Notas rápidas"], goal="iniciar sesión en notas rápidas", history=history,
        objective="inicia sesión en notas rápidas")
    assert asked["operation"] == "done"


def test_the_engine_never_presses_sign_in_unless_the_goal_asks() -> None:
    raw = {"act": "click", "label": "Iniciar sesión", "i": 2, "why": "para crear la nota"}
    step = cu_validate.validate_decision(raw, view=SIGN_IN_SCREEN, last_failed=None, application_names=[],
                                          goal=GOAL, history=list(OPENED))
    assert step["operation"] == "none" and step.get("code") == "changes_the_account"
    asked = cu_validate.validate_decision(raw, view=SIGN_IN_SCREEN, last_failed=None, application_names=[],
                                           goal="iniciar sesión en notas rápidas", history=list(OPENED))
    assert asked["operation"] == "input.visible.click"


def test_account_acts_include_signing_in_out_and_the_account_itself() -> None:
    acts = {
        "sign_in": ("Iniciar sesión", "Sign in", "Log in", "Iniciar sesión de nuevo", "Iniciar sesión de Microsoft"),
        "sign_out": ("Cerrar sesión", "Sign out", "Log out", "Cerrar sesión de Windows",
                     "Cerrar sesión de todos los dispositivos"),
        "create_account": ("Crear una cuenta", "Registrarse", "Sign up", "Create account"),
        "switch_account": ("Cambiar de cuenta", "Switch account", "Cambiar de usuario", "Switch user",
                           "Usar otra cuenta", "Agregar cuenta", "Add an account"),
    }
    for act, names in acts.items():
        for name in names:
            assert account_act(name) == act, name
    assert goal_asks_for("inicia sesión en el correo", "sign_in")
    assert goal_asks_for("sign out of the store", "sign_out")
    assert not goal_asks_for(GOAL, "sign_in")


def test_asking_to_sign_in_never_lets_the_engine_sign_out_or_create_an_account() -> None:
    # Review of r9, finding 6: each act of the session is its own.
    for act in ("sign_out", "create_account", "switch_account"):
        assert not goal_asks_for("inicia sesión en notas rápidas", act), act
    for label in ("Cerrar sesión", "Crear una cuenta"):
        raw = {"act": "click", "label": label, "why": "x"}
        view = _view(_SIGN_IN_CONTROLS + [_c(10, "Button", label, 839, 720, 260, 40)], _SIGN_IN_TEXT)
        step = cu_validate.validate_decision(raw, view=view, last_failed=None, application_names=[],
                                              goal="iniciar sesión en notas rápidas", history=list(OPENED))
        assert step["operation"] == "none" and step.get("code") == "changes_the_account", label


def test_a_session_of_something_is_no_account_act() -> None:
    # Counter-case: the Clock's «Iniciar sesión de concentración» is a page of its own, pressed as asked.
    assert account_act("Iniciar sesión de concentración") is None
    assert account_act("Sesiones de concentración") is None
    # Nor a place named after the act: the settings page «Opciones de inicio de sesión», «Sign-in options».
    assert account_act("Opciones de inicio de sesión") is None
    assert account_act("Sign-in options") is None
    assert account_act("Login settings") is None
    assert not goal_asks_for("ve a las opciones de login", "sign_in")


def test_a_goal_that_says_not_to_sign_in_never_lets_the_engine_sign_in() -> None:
    # Review of r9, finding 4 (v3-34 said with «sin iniciar sesión»): the gate is not the request's, and its
    # «Iniciar sesión» is never pressed.
    from baxy_mind.semantic.app_gates import asks_about_the_gate

    raw = {"act": "click", "label": "Iniciar sesión", "i": 2, "why": "x"}
    for goal in ("crea una nota sin iniciar sesión", "crea una nota sin login", "crea una nota, no inicies sesión",
                 "create a note without signing in", "create a note and don't sign in"):
        assert not goal_asks_for(goal, "sign_in"), goal
        assert not asks_about_the_gate(goal), goal
        step = cu_validate.validate_decision(raw, view=SIGN_IN_SCREEN, last_failed=None, application_names=[],
                                              goal=goal, history=list(OPENED))
        assert step["operation"] == "none" and step.get("code") == "changes_the_account", goal
        assert _decide(SIGN_IN_SCREEN, goal=goal)["code"] == cu_gates.APP_GATE, goal
    # Counter-cases: a request about the gate said with a «no» that is no refusal of it.
    assert asks_about_the_gate("no puedo iniciar sesión en notas")
    assert asks_about_the_gate("no me deja iniciar sesión")
    assert goal_asks_for("no olvides guardar la nota", "save")
    assert goal_asks_for("inicia sesión, no la cierres", "sign_in")


def test_the_system_menu_is_no_navigation_but_a_title_bar_of_menus_is() -> None:
    menu = next(c for c in _SIGN_IN_CONTROLS if c["name"] == "Sistema")
    assert cu_window._system_menu(SIGN_IN_SCREEN, menu)
    # Counter-case: a window whose own menus («Archivo», «Editar», «Ver») live in its title bar is a working window.
    menus = [_c(0, "TitleBar", "Editor", 0, 0, 800, 40), _c(1, "MenuItem", "Archivo", 50, 5, 60, 30),
             _c(2, "MenuItem", "Editar", 110, 5, 60, 30), _c(3, "MenuItem", "Ver", 170, 5, 60, 30),
             _c(4, "Button", "Iniciar sesión", 600, 5, 100, 30)]
    view = _view(menus, {"C": ["Iniciar sesión"]}, title="Editor")
    assert not cu_window._system_menu(view, menus[1])
    assert cu_gates.app_gate(view) is None


def test_tabs_or_entries_are_never_the_system_menu() -> None:
    # Review of r9, finding 2: an editor's open files as tabs in its title bar, and list entries read without a
    # rectangle, are places of a working window wherever they are.
    tabs = [_c(0, "TitleBar", "Bloc de notas", 0, 0, 800, 40), _c(1, "TabItem", "notas.txt", 60, 5, 150, 30),
            _c(2, "TabItem", "lista.txt", 210, 5, 150, 30), _c(3, "Button", "Iniciar sesión", 600, 5, 100, 30),
            _c(4, "Button", "Ahora no", 600, 300, 100, 30)]
    view = _view(tabs, {"C": ["Inicia sesión para guardar en la nube"]}, title="Bloc de notas")
    assert not any(cu_window._system_menu(view, tab) for tab in tabs[1:3])
    assert cu_gates.app_gate(view) is None
    entries = [_c(0, "Button", "Iniciar sesión", 300, 60, 120, 30),
               {"i": 1, "kind": "ListItem", "name": "Mi nota", "state": "", "rect": {"x": 0, "y": 0, "w": 0, "h": 0}},
               {"i": 2, "kind": "ListItem", "name": "Otra", "state": "", "rect": None}]
    assert cu_gates.app_gate(_view(entries, {"C": ["Inicia sesión para sincronizar"]}, title="Notas")) is None


def test_lines_of_content_are_not_joined_into_one() -> None:
    # Counter-case: an album's list, each entry in capitals, stays five lines of content (no gate).
    view = _view([], {"C": ["Fotos", "Álbum de verano", "Playa", "Montaña", "Cumpleaños", "Viaje", "Actualizando"]},
                 title="Fotos")
    assert cu_gates.app_gate(view) is None
    assert cu_gates._unwrapped_lines(SIGN_IN_SCREEN)[0].endswith("Solo tienes que iniciar sesión.")


class _Consulted(Exception):
    pass


class _Model:
    """The model is consulted: the step is not decided by a gate rule."""

    def __getattr__(self, name: str):
        raise _Consulted(name)


def test_entries_in_lower_case_are_content_never_a_wrapped_sentence() -> None:
    # Review of r9, finding 1: a list of notes written in lower case under a sign-in banner is a working window: the
    # engine never presses «Ahora no» on it by itself, the model decides.
    controls = [_c(0, "Button", "Cerrar", 700, 0, 50, 30), _c(1, "Button", "Iniciar sesión", 300, 60, 120, 30),
                _c(2, "Button", "Nueva nota", 10, 60, 80, 30), _c(3, "Button", "Ahora no", 450, 60, 80, 30)]
    notes = ["comprar pan", "pagar la luz", "llamar al dentista", "revisar el correo", "sacar la basura"]
    for entries in (notes, [*notes, "regar las plantas"], [f"{note}." for note in notes]):
        view = _view(controls, {"C": ["Inicia sesión para sincronizar tus notas", *entries]}, title="Notas")
        assert cu_gates._unwrapped_lines(view) == ["Inicia sesión para sincronizar tus notas", *entries]
        assert cu_gates.app_gate(view) is None
        try:
            decision = computer_use.decide_step(
                _Model(), objective="crea una nota que diga hola", goal="crea una nota que diga hola",
                application="Notas", success_check=None, view=view, history=list(OPENED), budget_left=12,
                application_names=["Notas"])
        except _Consulted:
            continue
        assert decision.get("arguments", {}).get("label") != "Ahora no", decision
