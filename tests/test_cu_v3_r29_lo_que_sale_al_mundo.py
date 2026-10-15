"""Ronda 29, «lo que sale al mundo se confirma» (pasada r27 en vivo, 2026-10-10).

v3-53 («en obs silencia el audio del escritorio» → «vale, vuelve a activarlo»): la línea «Parecidos al objetivo» nombró
«Iniciar Transmisión» y el modelo lo pulsó; RiskPolicy no tenía la palabra y no preguntó. v3-08 y v3-09 (OneNote): el
despliegue a ciegas abrió la lista de «Compartir», que sí pregunta, después de haber actuado y para algo que nadie pidió.

Las palabras de lo que un clic saca al mundo son un solo dato (data/world_acts.v1.json) que leen el Kernel (RiskPolicy:
pregunta antes del clic) y la mente (aquí): una regla nunca abre a ciegas, sugiere ni pulsa por parecido un control así
si el objetivo no lo nombra. Los ejemplos del propio dato atan a los dos lectores (RiskPolicyWorldActsTests en C#).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from baxy_mind import computer_use as cu
from baxy_mind import cu_fields
from baxy_mind import cu_unasked
from baxy_mind import cu_languages
from baxy_mind import cu_meaning
from baxy_mind import cu_validate
from baxy_mind import cu_unfold
from baxy_mind import cu_step_prompt
from baxy_mind.semantic import account_acts

_DATA = json.loads(
    (Path(cu.__file__).resolve().parent / "data" / "world_acts.v1.json").read_text(encoding="utf-8")
)


class _Scores:
    """An encoder ready that finds every name of the view like the goal (the worst case for the hint line)."""

    state = cu_meaning.ENCODER_READY

    def scored(self, label, view, other_labels=(), *, wait=False):
        names = [str(control.get("name") or "").strip() for control in view.get("controls", [])]
        return tuple((name, 0.9) for name in names if name)


def _obs() -> dict:
    """v3-53, turno 2, paso 2 (model_calls.jsonl): la ventana de OBS como la vio el modelo, con sus nombres reales,
    reducida a los botones que la línea «Parecidos al objetivo» nombró y a sus vecinos."""

    return {
        "window": {"title": "OBS 32.0.2 - Perfil: Sin Título - Escenas: Sin Título", "process": "obs64"},
        "controls": [
            {"i": 2, "kind": "CheckBox", "name": "Sólo fuentes activas", "state": "on", "zone": "BL"},
            {"i": 32, "kind": "Button", "name": "Abrir filtros de la escena", "zone": "BL"},
            {"i": 33, "kind": "Button", "name": "Mover arriba", "zone": "BL"},
            {"i": 45, "kind": "Button", "name": "Añadir transición configurable", "zone": "BR"},
            {"i": 46, "kind": "Button", "name": "Iniciar Transmisión", "zone": "BR"},
            {"i": 47, "kind": "Button", "name": "Iniciar Grabación", "zone": "BR"},
            {"i": 48, "kind": "Button", "name": "Iniciar Cámara Virtual", "zone": "BR"},
        ],
        "text": {"BR": ["Iniciar Transmisión", "300 ms", "Iniciar Grabación"]},
    }


def _onenote() -> dict:
    """v3-08 y v3-09: OneNote, con «Compartir» plegado en la cinta, reducido a los controles que deciden."""

    return {
        "window": {"title": "Sin título - OneNote", "process": "ONENOTE"},
        "controls": [
            {"i": 8, "kind": "TabItem", "name": "Inicio", "zone": "TL"},
            {"i": 10, "kind": "TabItem", "name": "Dibujar", "state": "selected focused", "zone": "TL"},
            {"i": 16, "kind": "MenuItem", "name": "Compartir", "state": "collapsed", "zone": "TR"},
            {"i": 17, "kind": "Button", "name": "Comentarios", "zone": "TR"},
            {"i": 40, "kind": "Button", "name": "Agregar página", "zone": "T"},
            {"i": 42, "kind": "ListItem", "name": "Sin título", "state": "selected", "zone": "B"},
        ],
    }


def _opened(app: str) -> dict:
    return {"step": 1, "operation": "app.open", "appId": app, "ok": True, "changed": True}


# ------------------------------------------------ (1) un solo dato, dos lectores


@pytest.mark.parametrize("label", _DATA["examples"]["asks"])
def test_a_control_that_goes_out_to_the_world_is_read_as_one(label: str) -> None:
    assert account_acts.world_act(label) is not None, label


@pytest.mark.parametrize("label", _DATA["examples"]["free"])
def test_contracase_a_control_that_stays_in_the_computer_is_not(label: str) -> None:
    assert account_acts.world_act(label) is None, label


def test_the_real_controls_of_v3_53_and_of_the_assignment() -> None:
    asks = ("Iniciar Transmisión", "Compartir pantalla", "Transmitir", "Publicar", "Enviar comentarios",
            "Unirse a la reunión", "Go live", "Start streaming", "Share", "Post", "Llamar", "Unirse")
    free = ("Reproducir", "Play", "Grabar macro", "Agregar página", "Nueva pestaña", "Iniciar Grabación",
            "Iniciar Cámara Virtual", "Añadir transición configurable", "Abrir filtros de la escena", "Mover abajo",
            "Abrir Ajustes", "Aceptar", "Dibujar")
    assert [label for label in asks if account_acts.world_act(label) is None] == []
    assert [label for label in free if account_acts.world_act(label) is not None] == []
    # «Iniciar sesión» is the account's (its own veto, changes_the_account), never a world act.
    assert account_acts.world_act("Iniciar sesión") is None and account_acts.account_act("Iniciar sesión") == "sign_in"


def test_the_form_send_button_knows_every_verb_the_policy_asks_for() -> None:
    """One list, not two: the pattern of a form's send button lives beside the families and holds each of their verbs."""

    button = account_acts.form_send_button()
    assert cu_fields._SEND_BUTTON_NAME.pattern == _DATA["formSendButton"]
    verbs = [
        word for family in _DATA["families"] if family["name"] in _DATA["formSendFamilies"] for word in family["words"]
    ]
    missing = [word for word in verbs if button.search(word) is None]
    # Forwarding and inviting hand something to someone by a click of their own, never by a form's Enter; the pattern
    # is the one the mind had (its behaviour is not this round's to change), and what it leaves out is pinned here.
    assert sorted(set(missing)) == ["forward", "invita", "invitar", "invite", "reenvia", "reenviar", "twittear"]


def test_every_family_says_where_its_words_count() -> None:
    assert {family["where"] for family in _DATA["families"]} <= set(_DATA["where"])
    assert set(_DATA["joins"]) | set(_DATA["formSendFamilies"]) <= {family["name"] for family in _DATA["families"]}
    for family in _DATA["families"]:
        assert all(word == account_acts._world_fold(word) for word in family["words"]), family["name"]


# ------------------------------------------------ (2) v3-53: nunca sugerido ni pulsado por parecido


def test_v3_53_going_live_is_never_named_as_like_a_goal_that_does_not_say_it() -> None:
    names = [control["name"] for control in cu_step_prompt._similar_controls("vale, vuelve a activarlo", _obs(), (), _Scores())]
    assert "Iniciar Transmisión" not in names
    # Contracase: what stays in the computer is still offered.
    assert "Abrir filtros de la escena" in names and "Iniciar Grabación" in names


def test_contracase_a_goal_that_names_the_broadcast_still_sees_it() -> None:
    names = [control["name"] for control in cu_step_prompt._similar_controls("inicia la transmisión", _obs(), (), _Scores())]
    assert "Iniciar Transmisión" in names


@pytest.mark.parametrize(("goal", "name", "clickable"), [
    ("vale, vuelve a activarlo", "Iniciar Transmisión", False),
    ("creá una página nueva", "Compartir", False),
    ("seleccionar marcador amarillo", "Compartir", False),
    ("ir a general", "Unirse a la llamada", False),
    # The goal names it: the rule may press it, and the Kernel asks the person before the click.
    ("iniciar la transmisión", "Iniciar Transmisión", True),
    ("compartí la página", "Compartir", True),
    ("share this page", "Share", True),
    # Said in the other language than the window's: a word of the same family names it.
    ("share this page", "Compartir", True),
    ("go live", "Iniciar Transmisión", True),
    # Banco s11 / c7: the voice channel the goal goes to is still the rule's to press (and still asks).
    ("ir a canal cotele", "Cotele!!!😎, Canal de voz, Choche", True),
    ("ir a cotele", "Cotele (canal de voz)", True),
    ("ir a gym", "Gym (canal de voz)", True),
    # Banco n1, s07, v5, v6, y12, u8, e3 and playing music: ordinary controls are untouched.
    ("elegir el lápiz", "Lápiz", True),
    ("ir a insertar", "Insertar", True),
    ("ir a pantalla", "Pantalla", True),
    ("go to stopwatch", "Cronómetro", True),
    ("reproducir la playlist", "Reproducir", True),
    ("play the song", "Play", True),
])
def test_a_rule_presses_what_goes_out_only_when_the_goal_names_it(goal: str, name: str, clickable: bool) -> None:
    assert cu_languages._translation_clickable(goal, name) is clickable


def test_the_goal_names_an_act_by_a_shared_stem_never_by_a_function_word() -> None:
    assert account_acts.goal_names_act("comparte esto con Ana", "Compartir")
    assert account_acts.goal_names_act("enviale el archivo", "Enviar")
    assert not account_acts.goal_names_act("andá a la pestaña de inicio", "Unirse a la reunión")
    assert not account_acts.goal_names_act("vale, vuelve a activarlo", "Iniciar Transmisión")


# ------------------------------------------------ (3) v3-08, v3-09: nunca abierto a ciegas


@pytest.mark.parametrize("goal", ["creá una página nueva", "seleccionar marcador amarillo", "ir a configuracion"])
def test_v3_08_v3_09_the_list_of_share_is_never_opened_blind(goal: str) -> None:
    step = cu_unfold._unfold_before_giving_up(_onenote(), [_opened("OneNote")], goal, None, None)
    assert step is None or step["arguments"].get("label") != "Compartir", step
    assert not cu_unasked._safe_to_unfold({"kind": "MenuItem", "name": "Compartir", "state": "collapsed"})
    assert not cu_unasked._safe_to_unfold({"kind": "SplitButton", "name": "Iniciar Transmisión", "state": "collapsed"})


def test_contracase_an_ordinary_closed_list_is_still_opened_before_giving_up() -> None:
    terminal = {
        "window": {"title": "Windows PowerShell", "process": "WindowsTerminal"},
        "controls": [
            {"i": 0, "kind": "TabItem", "name": "Windows PowerShell", "state": "selected", "zone": "TL"},
            {"i": 2, "kind": "SplitButton", "name": "Nueva pestaña", "state": "collapsed", "zone": "TL"},
        ],
    }
    step = cu_unfold._unfold_before_giving_up(terminal, [_opened("Terminal")], "ir a configuracion", None, None)
    assert step is not None and step["arguments"] == {"label": "Nueva pestaña", "index": 2, "manner": "open"}
    assert cu_unasked._safe_to_unfold({"kind": "MenuItem", "name": "Archivo (F)", "state": "collapsed"})


def test_the_models_own_click_on_a_broadcast_reaches_the_kernel_which_asks() -> None:
    """The mind does not veto the model's click on «Iniciar Transmisión»: it hands the control's real name to the
    Kernel, whose policy asks before the click (RiskPolicyWorldActsTests, ComputerUseLoopTests.R29)."""

    step = cu_validate._checked_act(
        {"act": "click", "i": 46}, view=_index_view(_obs()), last_failed=None, application_names=(), history=[],
        goal="vale, vuelve a activarlo", objective="vale, vuelve a activarlo", application="OBS Studio (64bit)",
        semantic=None,
    )
    assert step["operation"] == "input.visible.click"
    assert step["arguments"] == {"label": "Iniciar Transmisión", "index": 46}


def _index_view(view: dict) -> dict:
    """The view as the model indexes it: ``controls[i]`` is the control of index i (padded with unnamed panes)."""

    by_index = {control["i"]: control for control in view["controls"]}
    padded = [by_index.get(i, {"i": i, "kind": "Pane", "name": ""}) for i in range(max(by_index) + 1)]
    return {**view, "controls": padded}


def test_the_twin_fold_drops_what_hides_a_verb() -> None:
    assert account_acts.world_act("En\u200bviar") == "send"
    assert account_acts.world_act("Enviar (Ctrl+Enter)") == "send"
    assert account_acts.world_act("INICIAR TRANSMISIÓN") == "broadcast"
    assert re.fullmatch(r"[a-z ]+", account_acts._world_fold("Iniciar  Transmisión"))
