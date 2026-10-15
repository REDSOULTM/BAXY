"""Live z7 (2026-10-07): going to «Tu biblioteca» the model followed a profile and saved a playlist in the account."""

from baxy_mind import cu_validate
from baxy_mind.semantic.account_acts import account_act, goal_asks_for


def _view(*names: str) -> dict:
    controls = [{"i": i, "kind": "Button", "name": name, "state": ""} for i, name in enumerate(names)]
    return {"window": {"title": "Música", "process": "musica"}, "controls": controls, "text": {}}


def _click(goal: str, label: str, *names: str) -> dict:
    view = _view(*names)
    index = next(i for i, name in enumerate(names) if name == label)
    raw = {"act": "click", "label": label, "i": index, "why": "probar"}
    return cu_validate.validate_decision(raw, view=view, last_failed=None, application_names=[], goal=goal, history=[])


def test_account_acts_are_read_from_the_control_name() -> None:
    assert account_act("Seguir a Tu biblioteca") == "follow"
    assert account_act("Siguiendo a Tu biblioteca") == "follow"
    assert account_act("Guardar La biblioteca de media noche en Tu Biblioteca") == "save"
    assert account_act("Obtener") == "install"
    assert account_act("Tu biblioteca") is None
    assert account_act("Abre Tu biblioteca") is None


def test_going_somewhere_never_follows_or_saves() -> None:
    names = ("Abre Tu biblioteca", "Seguir a Tu biblioteca", "Guardar La biblioteca de media noche en Tu Biblioteca")
    for label in names[1:]:
        step = _click("ir a tu biblioteca", label, *names)
        assert step["operation"] == "none" and step.get("code") == "changes_the_account"
    assert _click("ir a tu biblioteca", "Abre Tu biblioteca", *names)["operation"] == "input.visible.click"


def test_a_goal_that_asks_for_the_act_may_press_it() -> None:
    assert goal_asks_for("seguir a Ron92", "follow")
    assert goal_asks_for("instalar Spotify", "install")
    step = _click("hacer clic en seguir", "Seguir a Tu biblioteca", "Seguir a Tu biblioteca")
    assert step["operation"] == "input.visible.click"


def test_a_place_named_like_an_act_is_still_the_place() -> None:
    names = ("Tus me gusta", "Liked Songs", "Seguir a Ron92")
    assert _click("ir a tus me gusta", "Tus me gusta", *names)["operation"] == "input.visible.click"
    assert _click("ir a liked songs", "Liked Songs", *names)["operation"] == "input.visible.click"
    assert _click("ir a tus me gusta", "Seguir a Ron92", *names)["operation"] == "none"


def test_deleting_the_account_is_an_act_never_pressed_unasked() -> None:
    # Live s13 (banco fp, 2026-10-14): going to Discord's settings, the mission wandered and left the focus on «Eliminar
    # cuenta». In bypass the Kernel asks nothing, so the mind's own guard must refuse it unless the goal asks for it.
    assert account_act("Eliminar cuenta") == "delete_account"
    assert account_act("Delete Account") == "delete_account"
    assert account_act("Desactivar cuenta") == "delete_account"
    assert account_act("Eliminar de la lista") != "delete_account"
    names = ("Mi cuenta", "Eliminar cuenta", "Desactivar cuenta")
    for label in names[1:]:
        step = _click("ir a configuracion", label, *names)
        assert step["operation"] == "none" and step.get("code") == "changes_the_account", label
    assert goal_asks_for("eliminar mi cuenta", "delete_account")
