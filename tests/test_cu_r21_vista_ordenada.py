"""Ronda 21 (vista ordenada por objetivo y estructura): what the mind shows the model of a crowded view.

t-drag-4: the window's content surface (the provider's «body») was raised for a goal that drags a stroke; dragging is a
declared limit since the estabilización L, so no goal raises it and no act drags over it. t-menu-2: the list that holds
the items (its empty space opens the list's own menu) was out of the 30 controls the model saw; it is kept. The words
the listing is ranked by go back to the shell for the next look (``view_wanted``).
"""

from __future__ import annotations

from baxy_mind import computer_use as cu
from baxy_mind import cu_first_look
from baxy_mind import cu_creation
from baxy_mind import cu_evidence
from baxy_mind import cu_step_prompt


def _rect(x: int, y: int, w: int = 30, h: int = 20) -> dict:
    return {"x": x, "y": y, "w": w, "h": h}


def _paint_view() -> dict:
    controls = [{"i": k, "kind": "Button", "name": f"Herramienta {k}", "rect": _rect(10 + k * 32, 40)} for k in range(40)]
    controls.append({"i": 40, "kind": "Pane", "name": "(pane)", "body": True, "rect": _rect(100, 200, 900, 500)})
    return {"controls": controls}


def test_no_goal_raises_the_body_a_drawing_neither():
    # Estabilización L: dragging and drawing are a declared limit (the mission stops before them), so the content
    # surface the ronda 21 raised for a stroke is raised for no goal, and no act drags over it.
    view = _paint_view()
    for goal in ("elegir la herramienta lapiz", "arrastrar una linea a la derecha del lienzo"):
        shown = cu_step_prompt._ranked_controls(view["controls"], goal, 30, view=view)
        assert not any(control.get("body") is True for control in shown), goal
    assert "drag" not in cu.ACTS


def test_the_list_holding_the_items_stays_in_a_cut_listing():
    controls = [{"i": k, "kind": "Button", "name": f"Comando {k}", "rect": _rect(10 + k * 32, 40)} for k in range(30)]
    controls += [
        {"i": 30 + k, "kind": "ListItem", "name": f"archivo {k}.txt", "rect": _rect(120, 220 + k * 20, 600, 20)}
        for k in range(5)
    ]
    controls.append({"i": 35, "kind": "List", "name": "Vista de elementos", "rect": _rect(100, 200, 900, 500)})
    view = {"controls": controls}
    shown = cu_step_prompt._ranked_controls(controls, "abrir el menu contextual de espacio vacio", 30, view=view)
    assert any(control.get("i") == 35 for control in shown)


def test_headers_are_not_raised_by_a_goal_that_does_not_sort():
    controls = [{"i": k, "kind": "ListItem", "name": f"archivo {k}.txt"} for k in range(40)]
    controls.append({"i": 40, "kind": "HeaderItem", "name": "Fecha de modificación"})
    sorted_goal = cu_step_prompt._ranked_controls(controls, "ordenar por fecha de modificacion", 30)
    other_goal = cu_step_prompt._ranked_controls(controls, "abrir archivo 3.txt", 30)
    assert any(control.get("kind") == "HeaderItem" for control in sorted_goal)
    assert not any(control.get("kind") == "HeaderItem" for control in other_goal)


def test_the_next_look_carries_the_words_the_listing_is_ranked_by():
    wanted = cu.view_wanted("ir a Aplicación en Configuración", ("Application",))
    assert "aplicacion" in wanted and "application" in wanted
    assert all(len(word) >= 3 for word in wanted)
    many = cu.view_wanted(" ".join(f"palabra{k}" for k in range(40)))
    assert len(many) == 24
    assert cu.view_wanted("") == []


def _folder_look(entry: dict | None) -> dict:
    controls = [{"i": k, "kind": "ListItem", "name": f"archivo {k}.txt", "zone": "L"} for k in range(40)]
    controls[3]["state"] = "selected"
    if entry is not None:
        controls.append({"i": 40, "zone": "L", **entry})
    return {
        "window": {"title": "Documentos"},
        "controls": controls,
        "text": {"L": ["Presupuesto 2023.xlsx", "archivo 0.txt"]},
    }


def test_a_control_listed_only_for_the_goals_words_is_not_new_on_the_look():
    """Revisión 2: the sub-goal's first look carried no goal's words and already wrote «Presupuesto 2023.xlsx»; the
    next look lists the reserved ListItem of that name. It is no part of the look (``look_parts``, twin of LookText):
    the citation was seen at the start and the control was not brought. Contracase: the same entry listed by the base
    cut is new on the look."""

    first_look = "\n".join(cu_first_look.look_parts(_folder_look(None)))
    reserved_entry = {"kind": "ListItem", "name": "Presupuesto 2023.xlsx", "reserved": True}
    listed_entry = {"kind": "ListItem", "name": "Presupuesto 2023.xlsx"}
    reserved = {**_folder_look(reserved_entry), "firstLook": first_look}
    listed = {**_folder_look(listed_entry), "firstLook": first_look}

    assert cu_first_look.look_parts(reserved) == cu_first_look.look_parts(_folder_look(None))
    assert cu_first_look._seen_at_start("Presupuesto 2023.xlsx", reserved) is True
    assert cu_creation._brought_this_subgoal(reserved_entry, reserved) is False
    assert cu_first_look._seen_at_start("Presupuesto 2023.xlsx", listed) is False
    assert cu_creation._brought_this_subgoal(listed_entry, listed) is True


def test_a_control_listed_only_for_the_goals_words_never_shows_what_baxy_typed():
    """Revisión 3: a full folder, goal «crea una carpeta nueva llamada Informe»; BAXY typed «Informe» into «Nombre».
    «Informe 2023.xlsx», listed only for the goal's words (reserved), is no item that shows the typing, so the veto
    stands as without it; the same entry listed by the base cut is an item named so and lifts it."""

    goal = "crea una carpeta nueva llamada informe"
    history = [{"operation": "input.text.type", "text": "Informe", "into": "Nombre", "ok": True}]

    def folder(entry: dict | None) -> dict:
        controls = [{"i": 0, "kind": "Edit", "name": "Nombre", "value": "Informe"}]
        controls += [{"i": 1 + k, "kind": "ListItem", "name": f"archivo {k}.txt"} for k in range(40)]
        if entry is not None:
            controls.append({"i": len(controls), **entry})
        return {"window": {"title": "Documentos", "process": "explorer"}, "controls": controls}

    reserved = folder({"kind": "ListItem", "name": "Informe 2023.xlsx", "reserved": True})
    listed = folder({"kind": "ListItem", "name": "Informe 2023.xlsx"})
    assert cu_evidence._holds_typing("Informe", history, folder(None), goal) is True
    assert cu_evidence._holds_typing("Informe", history, reserved, goal) is True
    assert cu_evidence._holds_typing("Informe", history, listed, goal) is False
