"""Ronda 24 (pasada r23): llegada por el acto propio y final que no niega.

v3-53 t1: the done cited «Silenciar 'Audio del escritorio'», a box a verified click turned on, and was refused «eso ya
se veía antes» because the citation lost its closing quote (cu_view._bare). v3-14: a weak arrival said «la pantalla
todavía no muestra…» while the window showed «Fecha de modificación» on, the option the last click named
(cu_finals._weak_seen, data «weakDone.seen»; the App's twins are tests/data/cu_floor_twins.json
«cu-weak-done-seen-*»). v3-08: «ponele de título Lista del super», typed into «Título de página», was refused as an
echo (cu_evidence._slot_written). v3-62: «I found the active network is Red privada» died as unbacked_act
(semantic.claims.screen_only_object, data «screenObject.observing»). Every situation here is our own shape of those
runs.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind import cu_view
from baxy_mind import cu_first_look
from baxy_mind import cu_evidence
from baxy_mind import cu_validate
from baxy_mind import cu_finals
from baxy_mind import llm  # noqa: E402
from baxy_mind.semantic import claims  # noqa: E402
from baxy_mind.semantic.normalize import fold  # noqa: E402

TWINS = {case["id"]: case for case in json.loads(
    (ROOT / "tests" / "data" / "cu_floor_twins.json").read_text(encoding="utf-8"))["cases"]}

_LINE = re.compile(r"^(?P<i>\d+) · (?P<kind>\w+) · «(?P<name>[^«»]*)»(?P<rest>.*)$")
_ZONES = {"TL", "T", "TR", "L", "C", "R", "BL", "B", "BR"}


def _view(title: str, lines: str, **extra: object) -> dict:
    controls = []
    for line in lines.strip().splitlines():
        match = _LINE.match(line.strip())
        assert match is not None, line
        control: dict[str, object] = {"i": int(match["i"]), "kind": match["kind"], "name": match["name"]}
        for bit in (part.strip() for part in match["rest"].split(" · ") if part.strip()):
            if bit.startswith("valor=«"):
                control["value"] = bit[len("valor=«"):-1]
            elif bit in _ZONES:
                control["zone"] = bit
            else:
                control["state"] = bit
        controls.append(control)
    return {"window": {"title": title, "process": "APP"}, "controls": controls, **extra}


def _validate(raw: dict, view: dict, history: list[dict], goal: str) -> dict:
    return cu_validate.validate_decision(raw, view=view, last_failed=None, application_names=(), history=history, goal=goal)


def _click(step: int, label: str) -> dict:
    return {"step": step, "operation": "input.visible.click", "ok": True, "label": label, "changed": True}


# ------------------------------------------------------------------ (1) one normalizer for both sides


@pytest.mark.parametrize(("text", "bare"), [
    ("«Silenciar 'Audio del escritorio'»", "silenciar 'audio del escritorio'"),
    ("Silenciar 'Audio del escritorio'", "silenciar 'audio del escritorio'"),
    ("'Fecha de modificación'", "fecha de modificacion"),
    ("«Foo", "foo"),
    ("Foo»", "foo"),
    ("\"'Bar'\"", "bar"),
    ("rock 'n' roll", "rock 'n' roll"),
])
def test_bare_drops_only_the_wrapping_quotes(text: str, bare: str) -> None:
    assert cu_view._bare(text) == bare


_OBS_BEFORE = """
22 · Button · «Propiedades para 'Audio del escritorio'» · B
23 · CheckBox · «Silenciar 'Audio del escritorio'» · off · B
25 · Button · «Propiedades para 'Mic/Aux'» · B
26 · CheckBox · «Silenciar 'Mic/Aux'» · on · B
47 · Text · «Audio del escritorio» · B
"""
_OBS_AFTER = """
22 · Button · «Propiedades para 'Audio del escritorio'» · B
23 · CheckBox · «Silenciar 'Audio del escritorio'» · on focused · B
25 · Button · «Propiedades para 'Mic/Aux'» · B
26 · CheckBox · «Silenciar 'Mic/Aux'» · on · B
47 · Text · «Audio del escritorio» · B
"""


def _obs_view(**extra: object) -> dict:
    first = "\n".join(cu_first_look.look_parts(_view("OBS 31.0.0 - Perfil: Sin título", _OBS_BEFORE)))
    return _view("OBS 31.0.0 - Perfil: Sin título", _OBS_AFTER, firstLook=first,
                 chosenBeforeClick={"3": ["silenciar 'mic/aux'"]}, **extra)


def test_v3_53_a_box_the_click_turned_on_is_done_though_its_name_ends_in_a_quote() -> None:
    goal = "silenciar el audio del escritorio"
    history = [_click(3, "Silenciar 'Audio del escritorio'")]
    view = _obs_view()
    assert cu_evidence.chosen_by_act("«Silenciar 'Audio del escritorio'»", view, history)
    assert not cu_evidence._seen_at_start_all("Silenciar 'Audio del escritorio'", view, history, goal)
    decision = _validate({"act": "done", "evidence": "CheckBox «Silenciar 'Audio del escritorio'» · on"}, view, history, goal)
    assert decision["operation"] == "done"
    assert cu_view._bare(decision["arguments"]["evidence"]) == "silenciar 'audio del escritorio'"
    assert decision["arguments"].get("already") is not True


def test_v3_53_counter_a_box_on_from_the_start_with_no_click_is_still_seen_before() -> None:
    goal = "silenciar el mic/aux"
    history = [_click(3, "Silenciar 'Audio del escritorio'")]
    view = _obs_view()
    assert not cu_evidence.chosen_by_act("Silenciar 'Mic/Aux'", view, history)
    assert cu_evidence._seen_at_start_all("Silenciar 'Mic/Aux'", view, history, goal)
    decision = _validate({"act": "done", "evidence": "Silenciar 'Mic/Aux'"}, view, history, goal)
    # Refused, or told as it already was: never as done by the act.
    assert decision["operation"] != "done" or decision["arguments"].get("already") is True


def test_a_control_its_click_changed_by_identity_is_not_seen_at_the_start() -> None:
    lines = "5 · Button · «Silenciar» · on · B\n6 · Button · «Ajustes» · B"
    first = "\n".join(cu_first_look.look_parts(_view("Reproductor", "5 · Button · «Silenciar» · off · B\n6 · Button · «Ajustes» · B")))
    history = [_click(3, "Silenciar")]
    goal = "silenciar el video"
    changed = _view("Reproductor", lines, firstLook=first, changedByClick=[3])
    assert cu_evidence._changed_by_its_click("«Silenciar»", changed, history, goal)
    assert not cu_evidence._seen_at_start_all("Silenciar", changed, history, goal)
    # Counter-cases: no click changed it (on before the click too), or another control the click did not press.
    first_on = "\n".join(cu_first_look.look_parts(_view("Reproductor", lines)))
    unchanged = _view("Reproductor", lines, firstLook=first_on, changedByClick=[], chosenBeforeClick={"3": ["silenciar"]})
    assert not cu_evidence._changed_by_its_click("Silenciar", unchanged, history, goal)
    assert cu_evidence._seen_at_start_all("Silenciar", unchanged, history, goal)
    assert cu_evidence._seen_at_start_all("Ajustes", changed, history, goal)


# ------------------------------------------------------------------ revisión 1 (B1): the change goes the goal's way

_WIFI_ON = "5 · Button · «Wi-Fi» · on · T\n6 · Button · «Bluetooth» · off · T"
_WIFI_OFF = "5 · Button · «Wi-Fi» · off · T\n6 · Button · «Bluetooth» · off · T"


def _wifi(before: str, after: str) -> dict:
    first = "\n".join(cu_first_look.look_parts(_view("Configuración rápida", before)))
    return _view("Configuración rápida", after, firstLook=first, changedByClick=[3])


def test_b1_a_switch_the_click_turned_off_is_no_proof_of_turning_it_on() -> None:
    goal = "activar el wifi"
    history = [_click(3, "Wi-Fi")]
    view = _wifi(_WIFI_ON, _WIFI_OFF)
    assert not cu_evidence._changed_by_its_click("Wi-Fi", view, history, goal)
    assert cu_evidence._seen_at_start_all("Wi-Fi", view, history, goal)
    decision = _validate({"act": "done", "evidence": "Wi-Fi"}, view, history, goal)
    assert decision["operation"] != "done", decision


def test_b1_counter_a_switch_the_click_turned_off_proves_turning_it_off() -> None:
    goal = "desactivar el wifi"
    history = [_click(3, "Wi-Fi")]
    view = _wifi(_WIFI_ON, _WIFI_OFF)
    assert cu_evidence._changed_by_its_click("Wi-Fi", view, history, goal)
    assert not cu_evidence._seen_at_start_all("Wi-Fi", view, history, goal)


def test_b1_a_mute_toggle_left_off_is_no_proof_of_muting() -> None:
    goal = "silenciar el video"
    history = [_click(3, "Silenciar")]
    first = "\n".join(cu_first_look.look_parts(_view("Reproductor", "5 · Button · «Silenciar» · on · B")))
    view = _view("Reproductor", "5 · Button · «Silenciar» · off · B", firstLook=first, changedByClick=[3])
    assert not cu_evidence._changed_by_its_click("Silenciar", view, history, goal)
    assert cu_evidence._seen_at_start_all("Silenciar", view, history, goal)
    # Counter-case: the same toggle left off in a goal of taking the mute off goes the goal's way.
    assert cu_evidence._changed_by_its_click("Silenciar", view, history, "quitar el silencio del video")


def test_b1_a_value_changed_proves_only_when_the_goal_names_it() -> None:
    lines = "5 · Slider · «Volumen» · valor=«80» · B"
    first = "\n".join(cu_first_look.look_parts(_view("Reproductor", "5 · Slider · «Volumen» · valor=«50» · B")))
    history = [_click(3, "Volumen")]
    view = _view("Reproductor", lines, firstLook=first, changedByClick=[3])
    assert cu_evidence._changed_by_its_click("Volumen", view, history, "poner el volumen en 80")
    # Counter-case: a value the goal does not name tells no direction.
    assert not cu_evidence._changed_by_its_click("Volumen", view, history, "poner el volumen en 30")


def test_b1_the_undoing_pattern_is_the_apps_too() -> None:
    from baxy_mind import operation_floor
    from baxy_mind.semantic import cu_buscar

    assert operation_floor.floor_data()["computerUse"]["evidence"]["undoingGoal"] == cu_buscar._UNDOING_GOAL.pattern
    assert cu_buscar.undoes_a_state("desactivar el wifi") and not cu_buscar.undoes_a_state("activar el wifi")


# ------------------------------------------------------------------ (4) the weak final says what it sees


@pytest.mark.parametrize("case_id", ["cu-weak-done-seen-value", "cu-weak-done-seen-value-unrelated", "cu-weak-done-model-evidence"])
@pytest.mark.parametrize("language", ["es", "en"])
def test_v3_14_the_weak_final_says_the_value_the_last_click_named(case_id: str, language: str) -> None:
    situation = TWINS[case_id]["situation"]
    assert cu_finals.floor_sentence(situation["observed"], language == "en", True) == TWINS[case_id][language]


def test_v3_14_two_chosen_values_the_click_named_are_no_guess() -> None:
    steps = [_click(2, "Fecha de modificación y Nombre")]
    values = [{"name": "Fecha de modificación", "state": "on"}, {"name": "Nombre", "state": "selected"}]
    assert cu_finals._weak_seen(steps, {"values": values}) is None
    assert cu_finals._weak_seen(steps, {"values": values[:1]}) == ("Fecha de modificación", "on")
    # A value not chosen says nothing.
    assert cu_finals._weak_seen(steps, {"values": [{"name": "Fecha de modificación", "value": "x"}]}) is None


# ------------------------------------------------------------------ (3) the text a goal puts in the part it names

_ONENOTE = """
40 · Button · «Buscar» · TR
47 · Document · «Título de página» · focused · valor=«Lista del super» · T
48 · Document · «Cuerpo de página» · C
"""
_ONENOTE_SEARCH = """
40 · Edit · «Buscar» · focused · valor=«Lista del super» · TR
47 · Document · «Título de página» · T
48 · Document · «Cuerpo de página» · C
"""


def test_v3_08_the_title_typed_into_the_title_field_is_done() -> None:
    goal = "ponele de título Lista del super"
    history = [{"step": 3, "operation": "input.text.type", "ok": True, "text": "Lista del super",
                "field": "Título de página", "changed": True}]
    view = _view("Sin título - APP", _ONENOTE)
    assert cu_evidence._slot_written("Lista del super", view, history, goal)
    decision = _validate({"act": "done", "evidence": "Lista del super"}, view, history, goal)
    assert decision["operation"] == "done", decision
    # Revisión 1 (B2): the App judges the done again; «written» tells it what the mind saw (SlotWritten checks it).
    assert decision["arguments"].get("written") is True


def test_v3_08_counter_the_title_typed_into_a_search_box_is_no_title() -> None:
    goal = "ponele de título Lista del super"
    history = [{"step": 3, "operation": "input.text.type", "ok": True, "text": "Lista del super",
                "field": "Buscar", "changed": True}]
    view = _view("Sin título - APP", _ONENOTE_SEARCH)
    assert not cu_evidence._slot_written("Lista del super", view, history, goal)
    decision = _validate({"act": "done", "evidence": "Lista del super"}, view, history, goal)
    assert decision["operation"] != "done"
    assert decision.get("arguments", {}).get("written") is not True


def test_counter_a_search_with_only_its_box_holding_the_query_is_still_an_echo() -> None:
    goal = "buscá receta"
    history = [{"step": 2, "operation": "input.text.type", "ok": True, "text": "receta", "field": "Buscar",
                "changed": True}]
    view = _view("Notas - APP", "40 · Edit · «Buscar» · focused · valor=«receta» · TR\n41 · Button · «Inicio» · T")
    assert not cu_evidence._slot_written("receta", view, history, goal)
    decision = _validate({"act": "done", "evidence": "receta"}, view, history, goal)
    assert decision["operation"] != "done"



# ------------------------------------------------------------------ revisión 2 (B1): the click takes no credit for typing

_SEARCH_BEFORE = "40 · Edit · «Buscar» · TR\n41 · Button · «Inicio» · T"
_SEARCH_AFTER = "40 · Edit · «Buscar» · focused · valor=«receta» · TR\n41 · Button · «Inicio» · T"


def _typed(step: int, text: str, into: str) -> dict:
    return {"step": step, "operation": "input.text.type", "ok": True, "text": text, "into": into, "changed": True}


def test_r2_b1_the_search_box_clicked_then_typed_into_is_no_arrival() -> None:
    goal = "buscar receta"
    first = "\n".join(cu_first_look.look_parts(_view("Notas - APP", _SEARCH_BEFORE)))
    view = _view("Notas - APP", _SEARCH_AFTER, firstLook=first, changedByClick=[2])
    history = [_click(2, "Buscar"), _typed(3, "receta", "Buscar")]
    assert not cu_evidence._changed_by_its_click("Buscar", view, history, goal)
    assert cu_evidence._seen_at_start_all("Buscar", view, history, goal)
    decision = _validate({"act": "done", "evidence": "Buscar"}, view, history, goal)
    assert decision["operation"] != "done", decision


def test_r2_b1_a_value_typed_after_the_click_is_no_change_of_the_click() -> None:
    first = "\n".join(cu_first_look.look_parts(_view("Reproductor", "5 · Edit · «Volumen» · valor=«50» · B")))
    view = _view("Reproductor", "5 · Edit · «Volumen» · valor=«80» · B", firstLook=first, changedByClick=[3])
    goal = "poner el volumen en 80"
    # Typed into the control after the click on it, or a typed text that is the value: the typing wrote it.
    assert not cu_evidence._changed_by_its_click("Volumen", view, [_click(3, "Volumen"), _typed(4, "80", "Volumen")], goal)
    assert not cu_evidence._changed_by_its_click("Volumen", view, [_click(3, "Volumen"), _typed(4, "80", "")], goal)
    # Counter-cases: what the click alone changed still proves, though the sub-goal typed elsewhere another text; a
    # typing into the control before the click is not after it.
    assert cu_evidence._changed_by_its_click("Volumen", view, [_click(3, "Volumen"), _typed(4, "Ana", "Nombre")], goal)
    assert cu_evidence._changed_by_its_click("Volumen", view, [_typed(2, "70", "Volumen"), _click(3, "Volumen")], goal)


def test_r2_b1_counter_a_switch_the_click_turned_on_in_a_search_still_proves_its_change() -> None:
    # Only the value branch is closed to a search: a state the click changed goes by its state.
    first = "\n".join(cu_first_look.look_parts(_view("Notas - APP", "40 · CheckBox · «Mayúsculas» · off · TR")))
    view = _view("Notas - APP", "40 · CheckBox · «Mayúsculas» · on · TR", firstLook=first, changedByClick=[2])
    assert cu_evidence._changed_by_its_click("Mayúsculas", view, [_click(2, "Mayúsculas")], "buscar receta")


# ------------------------------------------------------------------ (5) observing acts on nothing


def test_v3_62_an_observation_names_no_object_of_an_act() -> None:
    done = fold("ir a firewall y proteccion de red; clic en firewall y proteccion de red")
    seen = fold("firewall y proteccion de red red privada (activa) red publica red de dominio")
    assert claims.screen_only_object("I found the active network is Red privada.", done, seen) == ""
    assert claims.screen_only_object("Encontré que la red activa es Red privada.", done, seen) == ""


def test_counter_choosing_is_no_observation() -> None:
    done = fold("ir a programador; clic en programador")
    seen = fold("programador decimal hexadecimal octal binario")
    assert claims.screen_only_object("Llegué al Programador y elegí el modo Decimal.", done, seen) == "decimal"


def test_the_seen_template_passes_the_book_of_acts() -> None:
    sentence = TWINS["cu-weak-done-seen-value"]["es"]
    assert claims.claimed_acts(sentence, third_person=False) == []
    assert llm is not None


# ------------------------------------------------------------------ revisión 3 (B1): a field of a form still to save

_PLAYLIST_DIALOG = """
10 · Text · «Mi playlist» · T
20 · Edit · «Nombre» · focused · valor=«Gym» · C
21 · Edit · «Descripción» · C
22 · Button · «Guardar» · C
23 · Button · «Cerrar» · TR
"""
_DIALOG_LINES = ["Editar detalles", "Nombre", "Descripción", "Guardar", "Cerrar"]


def _form_view(lines: str, appeared: list[str], **extra: object) -> dict:
    return _view("Mi playlist - APP", lines, newTextAfterClick=appeared, **extra)


@pytest.mark.parametrize("goal", ["ponele de nombre «Gym» a la playlist", "escribí «Gym» en el nombre"])
def test_r3_b1_the_name_typed_into_a_form_still_to_save_is_not_set(goal: str) -> None:
    view = _form_view(_PLAYLIST_DIALOG, _DIALOG_LINES)
    history = [_click(2, "Editar detalles"), _typed(3, "Gym", "Nombre")]
    assert not cu_evidence._slot_written("Gym", view, history, goal)
    decision = _validate({"act": "done", "evidence": "Gym"}, view, history, goal)
    assert decision["operation"] != "done", decision
    assert decision.get("arguments", {}).get("written") is not True


def test_r3_b1_the_form_brought_is_read_from_the_first_look_too() -> None:
    # Without the lines of the click, the dialog's «Guardar» shows more times than on the sub-goal's first look.
    goal = "ponele de título «Reunión» al evento"
    first = "\n".join(cu_first_look.look_parts(_view("Calendario - APP", "30 · Button · «Nuevo evento» · T")))
    view = _view("Calendario - APP", "30 · Button · «Nuevo evento» · T\n"
                 "31 · Edit · «Agregar un título» · focused · valor=«Reunión» · C\n32 · Button · «Guardar» · C",
                 firstLook=first)
    history = [_click(2, "Nuevo evento"), _typed(3, "Reunión", "Agregar un título")]
    assert not cu_evidence._slot_written("Reunión", view, history, goal)


def test_r3_b1_counter_the_same_form_after_the_verified_click_on_save_is_done() -> None:
    goal = "ponele de nombre «Gym» a la playlist"
    view = _form_view(_PLAYLIST_DIALOG, ["Cambios guardados"])
    history = [_click(2, "Editar detalles"), _typed(3, "Gym", "Nombre"), _click(4, "Guardar")]
    assert cu_evidence._slot_written("Gym", view, history, goal)
    decision = _validate({"act": "done", "evidence": "Gym"}, view, history, goal)
    assert decision["operation"] == "done", decision
    assert decision["arguments"].get("written") is True


def test_r3_b1_counter_a_save_button_on_screen_all_along_is_no_form_brought() -> None:
    # v3-08 with the quick access bar's «Guardar»: on the first look already, so the title field is no form to save.
    goal = "ponele de título Lista del super"
    lines = _ONENOTE.strip() + "\n41 · Button · «Guardar» · TL"
    before = "40 · Button · «Buscar» · TR\n47 · Document · «Título de página» · T\n41 · Button · «Guardar» · TL"
    first = "\n".join(cu_first_look.look_parts(_view("Sin título - APP", before)))
    view = _view("Sin título - APP", lines, firstLook=first)
    history = [{"step": 3, "operation": "input.text.type", "ok": True, "text": "Lista del super",
                "field": "Título de página", "changed": True}]
    assert cu_evidence._slot_written("Lista del super", view, history, goal)
    decision = _validate({"act": "done", "evidence": "Lista del super"}, view, history, goal)
    assert decision["operation"] == "done", decision


# ------------------------------------------------------------------ revisión 4 (B1): a rename box the sub-goal brought

_TERMINAL_BEFORE = """
10 · TabItem · «Windows PowerShell» · T
11 · Button · «Cambiar nombre de pestaña» · T
"""
_TERMINAL_RENAMING = """
10 · TabItem · «Windows PowerShell» · T
12 · Edit · «Título de la pestaña» · focused · valor=«pruebas» · T
"""
_TERMINAL_GOAL = "ponele de título «pruebas» a la pestaña"


def _terminal_view(**extra: object) -> dict:
    first = "\n".join(cu_first_look.look_parts(_view("Windows PowerShell - APP", _TERMINAL_BEFORE)))
    return _view("Windows PowerShell - APP", _TERMINAL_RENAMING, firstLook=first, **extra)


@pytest.mark.parametrize("appeared", [["Título de la pestaña"], None])
def test_r4_b1_the_rename_box_brought_by_the_click_is_no_name_set(appeared: list[str] | None) -> None:
    # Brought by the last click (its new lines) or, without them, by the first look that had no such field.
    view = _terminal_view(**({"newTextAfterClick": appeared} if appeared else {}))
    history = [_click(2, "Cambiar nombre de pestaña"), _typed(3, "pruebas", "Título de la pestaña")]
    assert cu_evidence._field_brought(view["controls"][1], view)
    assert not cu_evidence._slot_written("pruebas", view, history, _TERMINAL_GOAL)
    decision = _validate({"act": "done", "evidence": "pruebas"}, view, history, _TERMINAL_GOAL)
    assert decision["operation"] != "done", decision
    assert decision.get("arguments", {}).get("written") is not True


def test_r4_b1_the_rename_box_beside_a_column_of_the_same_name_is_brought() -> None:
    # Explorer: F2 brings the box «Nombre» while the column «Nombre» was on the first look already.
    goal = "ponele de nombre «pruebas» a la carpeta Nueva carpeta"
    before = "5 · HeaderItem · «Nombre» · T\n6 · ListItem · «Nueva carpeta» · C"
    first = "\n".join(cu_first_look.look_parts(_view("Documentos - APP", before)))
    view = _view("Documentos - APP", before + "\n7 · Edit · «Nombre» · focused · valor=«pruebas» · C", firstLook=first)
    history = [{"step": 2, "operation": "input.key.press", "ok": True, "keys": "F2", "changed": True},
               _typed(3, "pruebas", "Nombre")]
    assert not cu_evidence._slot_written("pruebas", view, history, goal)
    decision = _validate({"act": "done", "evidence": "pruebas"}, view, history, goal)
    assert decision.get("arguments", {}).get("written") is not True


def test_r4_b1_counter_a_brought_field_confirmed_by_a_verified_click_is_set() -> None:
    goal = "ponele de título «Informe» al documento"
    first = "\n".join(cu_first_look.look_parts(_view("Documento - APP", "3 · Button · «Propiedades» · T")))
    view = _view("Documento - APP", "3 · Button · «Propiedades» · T\n4 · Edit · «Título» · valor=«Informe» · C\n"
                 "5 · Button · «Aceptar» · C", firstLook=first)
    typed = [_click(2, "Propiedades"), _typed(3, "Informe", "Título")]
    assert not cu_evidence._slot_written("Informe", view, typed, goal)
    assert cu_evidence._slot_written("Informe", view, typed + [_click(4, "Aceptar")], goal)


def test_r4_b1_counter_a_field_on_the_first_look_is_no_box_brought() -> None:
    # v3-08: «Título de página» was on the sub-goal's first look, empty; its value changed, not its presence.
    first = "\n".join(cu_first_look.look_parts(_view("Sin título - APP", "40 · Button · «Buscar» · TR\n47 · Document · «Título de página» · T")))
    view = _view("Sin título - APP", _ONENOTE, firstLook=first)
    history = [{"step": 3, "operation": "input.text.type", "ok": True, "text": "Lista del super",
                "field": "Título de página", "changed": True}]
    assert not cu_evidence._field_brought(view["controls"][1], view)
    assert cu_evidence._slot_written("Lista del super", view, history, "ponele de título Lista del super")
