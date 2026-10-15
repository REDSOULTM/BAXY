"""Unneeded confirmations (pass r9): Enter in a search, filter, name or value field never asks; Enter that may hand a
text to a person (a message box, a mail body, a form with a send button) still asks, read behind or in front.

Twins of v3-29, t-scroll-2 and v3-30 on their real Character Map views (journal, frozen in
tests/data/cu_v3_confirmar_vistas.json): the window read behind the person's (no keyboard focus reported), «Buscar:»
clicked, the name typed, and Enter was marked ``message_composer`` because the focus could not be read right after a
text. Counter-cases keep the seg-input fix (r10a): a chat read behind still asks."""

import copy
import json
from pathlib import Path

from baxy_mind import cu_fields
from baxy_mind import cu_rules
from baxy_mind import cu_validate

_DATA = json.loads((Path(__file__).parent / "data" / "cu_v3_confirmar_vistas.json").read_text(encoding="utf-8"))
_CASES = {case["caso"]: case for case in _DATA["casos"]}


def _ok(step: int, operation: str, **fields: object) -> dict:
    return {"step": step, "operation": operation, "ok": True, **fields}


def _history(case: dict) -> list[dict]:
    return [
        _ok(1, "input.visible.click", label=case["clic"]["label"], index=case["clic"]["index"]),
        _ok(2, "input.text.type", text=case["escrito"]),
    ]


# ------------------------------------------------------------------ twins of the three r9 cases


def test_the_r9_views_are_read_behind_with_no_focus() -> None:
    for case in _CASES.values():
        window = case["vista_tras_escribir"]["window"]
        assert window["foreground"] is False and window.get("focused") is None, case["caso"]


def test_enter_after_typing_in_the_character_maps_search_does_not_ask() -> None:
    for name, case in _CASES.items():
        view, history = case["vista_tras_escribir"], _history(case)
        # The search goal's own Enter (the rule that asked in r9).
        step = cu_rules.deterministic_step(goal=f"buscar {case['escrito']}", view=view, history=history)
        assert step is not None and step["operation"] == "input.key.press", name
        assert step["arguments"] == {"key": "enter"}, name
        # A model's Enter, or any other rule's, on the same view.
        assert cu_fields.key_arguments("enter", view, history) == {"key": "enter"}, name
        act = {"act": "key", "key": "enter"}
        decided = cu_validate.validate_decision(act, view=view, last_failed=None, application_names=(), history=history,
                                                 goal=f"buscar {case['escrito']}")
        assert decided["arguments"] == {"key": "enter"}, name


def test_without_the_click_right_before_the_text_the_enter_still_asks() -> None:
    # Where the text went is known only from the click right before it (the view shows no value for «Buscar:»):
    # a text with no click before it, a failed click, or a click on a name the view does not list as a field asks.
    case = _CASES["v3-30"]
    view = case["vista_tras_escribir"]
    typed = _ok(2, "input.text.type", text=case["escrito"])
    for history in (
        [typed],
        [{"step": 1, "operation": "input.visible.click", "ok": False, "label": "Buscar:"}, typed],
        [_ok(1, "input.visible.click", label="Seleccionar"), typed],
        [_ok(1, "input.visible.click", label="Buscar"), typed],  # the button, not the field
    ):
        assert cu_fields.key_arguments("enter", view, history) == {"key": "enter", "target": "message_composer"}, history


# ------------------------------------------------------------------ fields of a form: free; a send button: asks


def _behind(controls: list[dict], title: str = "Formulario") -> dict:
    return {"window": {"title": title, "process": "app", "foreground": False, "focused": None},
            "controls": controls, "text": {}}


def test_enter_in_a_named_form_field_read_behind_does_not_ask() -> None:
    view = _behind([{"i": 0, "kind": "Edit", "name": "Nombre"}, {"i": 1, "kind": "Edit", "name": "Valor"},
                    {"i": 2, "kind": "Button", "name": "Aceptar"}])
    for label in ("Nombre", "Valor"):
        history = [_ok(1, "input.visible.click", label=label, index=0), _ok(2, "input.text.type", text="abc")]
        assert cu_fields.key_arguments("enter", view, history) == {"key": "enter"}, label
    # A filter field shown holding the text, with no click before it.
    view = _behind([{"i": 0, "kind": "Edit", "name": "Filtrar", "value": "rojo"}])
    assert cu_fields.key_arguments("enter", view, [_ok(1, "input.text.type", text="rojo")]) == {"key": "enter"}


def test_a_form_with_a_send_button_still_asks() -> None:
    # Outlook-like: the subject field of a message with «Enviar»; a web form with «Send».
    for button in ("Enviar", "Send", "Publicar", "Responder"):
        view = _behind([{"i": 0, "kind": "Edit", "name": "Asunto"}, {"i": 1, "kind": "Button", "name": button}],
                       title="Mensaje")
        history = [_ok(1, "input.visible.click", label="Asunto", index=0), _ok(2, "input.text.type", text="hola")]
        assert cu_fields.key_arguments("enter", view, history) == {"key": "enter", "target": "message_composer"}, button


# ------------------------------------------------------------------ counter-cases: a text that may go to a person


def test_discord_message_box_read_behind_still_asks() -> None:
    view = _behind([
        {"i": 0, "kind": "Document", "name": "Buscar", "rect": {"x": 900, "y": 10, "w": 200, "h": 30}},
        {"i": 1, "kind": "Document", "name": "Escribe un mensaje a #general", "rect": {"x": 300, "y": 900, "w": 900, "h": 44}},
    ], title="#general | Servidor - Discord")
    view["window"]["rect"] = {"x": 0, "y": 0, "w": 1600, "h": 1000}
    typed_message = [_ok(1, "input.visible.click", label="Escribe un mensaje a #general", index=1),
                     _ok(2, "input.text.type", text="hola")]
    assert cu_fields.key_arguments("enter", view, typed_message) == {"key": "enter", "target": "message_composer"}
    # The search clicked right before the text: the message box may still hold a draft of the person's (value not
    # shown), and only the click says where the text went, so Enter keeps asking (seg-input, r10a).
    typed_search = [_ok(1, "input.visible.click", label="Buscar", index=0), _ok(2, "input.text.type", text="hola")]
    assert cu_fields.key_arguments("enter", view, typed_search) == {"key": "enter", "target": "message_composer"}
    step = cu_rules.deterministic_step(goal="buscar hola", view=view, history=typed_search)
    assert step is not None and step["arguments"] == {"key": "enter", "target": "message_composer"}
    # The search shown holding the text and the message box shown empty: the search is where Enter goes.
    shown = copy.deepcopy(view)
    shown["controls"][0]["value"] = "hola"
    shown["controls"][1]["value"] = ""
    assert cu_fields.key_arguments("enter", shown, typed_search) == {"key": "enter"}
    # The text shown in the message box although the search was clicked: it went there, Enter would send it.
    landed = copy.deepcopy(view)
    landed["controls"][1]["value"] = "hola"
    assert cu_fields.key_arguments("enter", landed, typed_search) == {"key": "enter", "target": "message_composer"}
    # Read in front with the message box focused, unchanged.
    front = copy.deepcopy(landed)
    front["window"]["foreground"] = True
    front["window"]["focused"] = {**front["controls"][1]}
    assert cu_fields.key_arguments("enter", front, typed_search) == {"key": "enter", "target": "message_composer"}


def test_outlook_mail_body_still_asks() -> None:
    for body in ({"i": 1, "kind": "Document", "name": "Cuerpo del mensaje"},
                 {"i": 1, "kind": "Document", "name": "", "rect": {"x": 0, "y": 300, "w": 1200, "h": 600}},
                 {"i": 1, "kind": "Document", "name": "Cuerpo", "rect": {"x": 0, "y": 300, "w": 1200, "h": 600}}):
        view = _behind([{"i": 0, "kind": "Edit", "name": "Para"}, body], title="Sin título - Mensaje")
        view["window"]["rect"] = {"x": 0, "y": 0, "w": 1200, "h": 900}
        history = [_ok(1, "input.visible.click", label=body["name"] or "(document)", index=1),
                   _ok(2, "input.text.type", text="Hola Ana, te escribo")]
        assert cu_fields.key_arguments("enter", view, history) == {"key": "enter", "target": "message_composer"}, body


def test_whatsapp_message_box_drawn_without_a_tree_still_asks() -> None:
    view = {"window": {"title": "WhatsApp", "process": "WhatsApp", "foreground": False, "focused": None},
            "controls": [], "text": {"L": ["Buscar un chat o iniciar uno nuevo", "Ana"], "C": ["Ana", "Escribe un mensaje"]}}
    for label in ("Escribe un mensaje", "Buscar un chat o iniciar uno nuevo"):
        history = [_ok(1, "input.visible.click", label=label), _ok(2, "input.text.type", text="Ana")]
        assert cu_fields.key_arguments("enter", view, history) == {"key": "enter", "target": "message_composer"}, label
    step = cu_rules.deterministic_step(goal="buscar Ana", view=view,
                                           history=[_ok(1, "input.visible.click", label="Buscar un chat o iniciar uno nuevo"),
                                                    _ok(2, "input.text.type", text="Ana")])
    assert step is not None and step["arguments"] == {"key": "enter", "target": "message_composer"}


def test_a_message_box_named_field_or_a_fallback_name_never_frees_enter() -> None:
    for field in ({"i": 0, "kind": "Edit", "name": "Escribe un mensaje"},
                  {"i": 0, "kind": "Edit", "name": "Responder"},
                  {"i": 0, "kind": "Edit", "name": "Nombre", "nameSource": "helpText"},
                  {"i": 0, "kind": "Edit", "name": "Clave", "state": "password"}):
        history = [_ok(1, "input.visible.click", label=field["name"], index=0), _ok(2, "input.text.type", text="x")]
        assert cu_fields.key_arguments("enter", _behind([field]), history) == {"key": "enter", "target": "message_composer"}, field


# ------------------------------------------------------------------ adversarial review of r9: holes that freed a send


_ASKS = {"key": "enter", "target": "message_composer"}


def test_the_real_views_with_the_clicks_receipt_kind() -> None:
    # The click's receipt says what it pressed: the field frees, a button of the same name does not.
    for name, case in _CASES.items():
        view = case["vista_tras_escribir"]
        typed = _ok(2, "input.text.type", text=case["escrito"])
        on_field = [_ok(1, "input.visible.click", label="Buscar:", index=7, kind="Document"), typed]
        assert cu_fields.key_arguments("enter", view, on_field) == {"key": "enter"}, name
        on_button = [_ok(1, "input.visible.click", label="Buscar:", index=7, kind="Button"), typed]
        assert cu_fields.key_arguments("enter", view, on_button) == _ASKS, name


def test_a_message_box_hiding_its_value_asks_although_another_field_shows_the_text() -> None:
    # Measured Discord: the editor exposes no value. A search that already held «hola» proves nothing.
    view = _behind([
        {"i": 0, "kind": "Document", "name": "Buscar", "value": "hola", "rect": {"x": 900, "y": 10, "w": 200, "h": 30}},
        {"i": 1, "kind": "Document", "name": "Escribe un mensaje a #general", "rect": {"x": 300, "y": 900, "w": 900, "h": 44}},
    ], title="#general | Servidor - Discord")
    view["window"]["rect"] = {"x": 0, "y": 0, "w": 1600, "h": 1000}
    history = [_ok(1, "input.visible.click", label="Escribe un mensaje a #general", index=1),
               _ok(2, "input.text.type", text="hola")]
    assert cu_fields.key_arguments("enter", view, history) == _ASKS
    step = cu_rules.deterministic_step(goal="buscar hola", view=view, history=history)
    assert step is not None and step["arguments"] == _ASKS
    # The same in front with a focus that cannot be read.
    front = copy.deepcopy(view)
    front["window"].update(foreground=True, focused={"kind": "Pane", "name": ""})
    assert cu_fields.key_arguments("enter", front, history) == _ASKS
    # A message box with no name of its own hiding its value, no click before the text.
    unnamed = _behind([{"i": 0, "kind": "Edit", "name": "Buscar", "value": "hola"},
                       {"i": 1, "kind": "Document", "name": ""}])
    assert cu_fields.key_arguments("enter", unnamed, [_ok(1, "input.text.type", text="hola")]) == _ASKS


def test_a_value_that_only_contains_the_text_or_did_not_just_appear_proves_nothing() -> None:
    # «ok» typed somewhere; the address bar's URL contains «ok».
    view = _behind([{"i": 0, "kind": "Edit", "name": "Barra de direcciones y de búsqueda",
                     "value": "facebook.com/messages/t/ok"}], title="Messenger - Opera")
    assert cu_fields.key_arguments("enter", view, [_ok(1, "input.text.type", text="ok")]) == _ASKS
    # A filter field holding exactly the text: free when the view says it just appeared, or says nothing of it ...
    shown = _behind([{"i": 0, "kind": "Edit", "name": "Filtrar", "value": "rojo"}])
    typed = [_ok(1, "input.text.type", text="rojo")]
    assert cu_fields.key_arguments("enter", shown, typed) == {"key": "enter"}
    shown["newText"] = ["rojo"]
    assert cu_fields.key_arguments("enter", shown, typed) == {"key": "enter"}
    # ... and not when the view's new text does not have it: it was there before the text.
    shown["newText"] = ["otra cosa"]
    assert cu_fields.key_arguments("enter", shown, typed) == _ASKS


def test_in_front_with_a_bare_pane_focus_the_click_alone_does_not_free_a_possible_draft() -> None:
    view = {"window": {"title": "Chat", "process": "app", "foreground": True, "focused": {"kind": "Pane", "name": ""}},
            "controls": [{"i": 0, "kind": "Edit", "name": "Buscar"}, {"i": 1, "kind": "Edit", "name": "Escribe un mensaje"}],
            "text": {}}
    history = [_ok(1, "input.visible.click", label="Buscar", index=0), _ok(2, "input.text.type", text="hola")]
    assert cu_fields.key_arguments("enter", view, history) == _ASKS
    step = cu_rules.deterministic_step(goal="buscar hola", view=view, history=history)
    assert step is not None and step["arguments"] == _ASKS
    # Shown empty, the message box holds nothing to send: the search's Enter goes free.
    view["controls"][1]["value"] = ""
    assert cu_fields.key_arguments("enter", view, history) == {"key": "enter"}


def test_a_form_that_submits_shares_or_posts_still_asks() -> None:
    history = [_ok(1, "input.visible.click", label="Tu nombre", index=0), _ok(2, "input.text.type", text="Ana")]
    for kind, button in (("Button", "Submit"), ("Button", "Mandar"), ("Button", "Compartir"), ("Button", "Share"),
                         ("Button", "Postear"), ("Button", "Publish"), ("Button", "Enviar ahora"),
                         ("Hyperlink", "Enviar"), ("Group", "Send"), ("Custom", "Submit form"), ("Text", "Enviar")):
        view = _behind([{"i": 0, "kind": "Edit", "name": "Tu nombre"}, {"i": 1, "kind": kind, "name": button}])
        assert cu_fields.key_arguments("enter", view, history) == _ASKS, (kind, button)
    # A send button drawn without a tree, read by the OCR.
    drawn = _behind([{"i": 0, "kind": "Edit", "name": "Tu nombre"}])
    drawn["text"] = {"BR": ["Enviar"]}
    assert cu_fields.key_arguments("enter", drawn, history) == _ASKS
    # A message box drawn without a tree (its placeholder on screen) beside a listed field.
    placeholder = _behind([{"i": 0, "kind": "Edit", "name": "Tu nombre"}])
    placeholder["text"] = {"C": ["Escribe un mensaje"]}
    assert cu_fields.key_arguments("enter", placeholder, history) == _ASKS
    # Buttons that hand nothing to anyone keep the form free.
    plain = _behind([{"i": 0, "kind": "Edit", "name": "Tu nombre"}, {"i": 1, "kind": "Button", "name": "Aceptar"},
                     {"i": 2, "kind": "Button", "name": "Copiar"}])
    plain["text"] = {"BR": ["Aceptar", "Copiar"]}
    assert cu_fields.key_arguments("enter", plain, history) == {"key": "enter"}


def test_a_click_on_a_button_named_like_the_field_proves_nothing() -> None:
    view = _behind([{"i": 0, "kind": "Button", "name": "Buscar"}, {"i": 1, "kind": "Edit", "name": "Buscar"}])
    history = [_ok(1, "input.visible.click", label="Buscar", index=0), _ok(2, "input.text.type", text="hola")]
    assert cu_fields.key_arguments("enter", view, history) == _ASKS
    # The field's static label of the same name is not a second target.
    labelled = _behind([{"i": 0, "kind": "Text", "name": "Buscar"}, {"i": 1, "kind": "Edit", "name": "Buscar"}])
    assert cu_fields.key_arguments("enter", labelled, history) == {"key": "enter"}


def test_the_search_goals_enter_with_a_readable_focus_elsewhere_still_asks() -> None:
    # The focus says the keyboard is on a list item, not in the search clicked before: the plain-field proof does
    # not apply where the focus can be read.
    view = {"window": {"title": "Formulario", "process": "app", "foreground": True,
                       "focused": {"kind": "ListItem", "name": "Ana"}},
            "controls": [{"i": 0, "kind": "Edit", "name": "Buscar"}, {"i": 1, "kind": "ListItem", "name": "Ana"}],
            "text": {}}
    history = [_ok(1, "input.visible.click", label="Buscar", index=0), _ok(2, "input.text.type", text="hola")]
    step = cu_rules.deterministic_step(goal="buscar hola", view=view, history=history)
    assert step is not None and step["arguments"] == _ASKS
