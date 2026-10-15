"""Ronda 24b, palanca «elegido no es llegado y nunca buscar a ciegas» (banco r23: s04, x7, u9).

s04: el nodo «Downloads» del árbol de navegación del Explorador quedó elegido por Invoke sin navegar (recibo ok,
selected, surfaceChanged false) y la mente cayó en la búsqueda de contenido: clic en «Buscar en Este equipo» y
«descargas» tecleado. x7: «andá a search» con el botón «Buscar» ya pulsado acabó en ctrl_f, Escape y tres scrolls.
u9: el DataGrid «Search results» se tomó por contención como el lugar «search» y su clic de puntero eligió una
sugerencia. Gemelos con las vistas del journal y sus contracasos."""

from __future__ import annotations

from baxy_mind.semantic.missions import fold as missions_fold
from baxy_mind import cu_view
from baxy_mind import cu_rules
from baxy_mind import cu_diagnosis
from baxy_mind.semantic.missions import is_search_place


def _explorer(downloads_state: str = "selected") -> dict:
    # The view of s04 (journal 21:45:25.9): Explorer on «Este equipo», «Downloads» of the navigation tree chosen.
    return {
        "window": {"title": "Este equipo - Explorador de archivos", "process": "explorer", "focused": None,
                   "rect": {"x": 0, "y": 0, "w": 1200, "h": 800}},
        "controls": [
            {"i": 0, "kind": "RadioButton", "name": "Detalles", "state": "readonly", "zone": "BR"},
            {"i": 1, "kind": "RadioButton", "name": "Iconos grandes", "state": "readonly", "zone": "BR"},
            {"i": 2, "kind": "TreeItem", "name": "Inicio", "value": "Inicio", "zone": "L"},
            {"i": 3, "kind": "TreeItem", "name": "Downloads", "state": downloads_state, "zone": "L"},
            {"i": 4, "kind": "TreeItem", "name": "Este equipo", "state": "expanded", "zone": "L"},
            {"i": 5, "kind": "TabItem", "name": "Este equipo", "state": "selected", "zone": "T"},
            {"i": 6, "kind": "Edit", "name": "Buscar en Este equipo", "zone": "TR"},
            {"i": 7, "kind": "ListItem", "name": "Disco local (C:)", "zone": "C"},
        ],
        "text": {},
    }


def _downloads_click(**receipt: object) -> list[dict]:
    # The click as HistoryForMind projects it (ComputerUseMission.ForTheMind.cs): «selected», «surfaceChanged», «placeMoved».
    return [{"step": 2, "operation": "input.visible.click", "label": "Downloads", "index": 3, "ok": True,
             "kind": "TreeItem", "changed": True, "selected": True, **receipt}]


def _s04_step(history: list[dict], state: str = "selected") -> dict | None:
    return cu_rules.deterministic_step(
        goal="ir a descargas", view=_explorer(state), history=history, application="Explorador de archivos",
        objective="andá a descargas en el explorador",
    )


def _looks_up_blind(step: dict | None) -> bool:
    if step is None:
        return False
    if step.get("operation") in ("input.text.type", "input.scroll"):
        return True
    arguments = step.get("arguments") or {}
    if step.get("operation") == "input.key.press":
        return True
    return step.get("operation") == "input.visible.click" and "buscar" in missions_fold(arguments.get("label"))


def test_twin_s04_a_node_chosen_whose_place_did_not_move_is_said_never_looked_up() -> None:
    step = _s04_step(_downloads_click(surfaceChanged=False, placeMoved=False))
    assert step is not None
    assert step["operation"] == "none" and step["code"] == cu_rules.CLICK_WITHOUT_EFFECT, step
    assert not _looks_up_blind(step)


def test_revision1_b3_a_receipt_without_the_place_measure_is_never_said_without_effect() -> None:
    # Revisión 1 (B3): a receipt that did not measure the place (an older worker, a way that gave no measure) is no proof
    # that the place stayed: never «no tuvo efecto», and never the blind lookup either; the model decides with the view.
    step = _s04_step(_downloads_click(surfaceChanged=False))
    assert step is None, step
    assert not cu_rules._chosen_without_arriving(_explorer()["controls"][3], _downloads_click(surfaceChanged=False))


def _tabs_view() -> dict:
    # A property sheet whose tab «Avanzado» was chosen by Select alone (WPF, WinUI): the title does not change.
    return {
        "window": {"title": "Propiedades del sistema", "process": "SystemPropertiesAdvanced", "focused": None,
                   "rect": {"x": 0, "y": 0, "w": 600, "h": 500}},
        "controls": [
            {"i": 0, "kind": "TabItem", "name": "General", "zone": "T"},
            {"i": 1, "kind": "TabItem", "name": "Avanzado", "state": "selected", "zone": "T"},
            {"i": 2, "kind": "Button", "name": "Aceptar", "zone": "BR"},
            {"i": 3, "kind": "Button", "name": "Cancelar", "zone": "BR"},
        ],
        "text": {},
    }


def test_revision1_b3_a_tab_chosen_by_select_alone_without_the_measure_is_not_denied() -> None:
    click = {"step": 2, "operation": "input.visible.click", "label": "Avanzado", "index": 1, "ok": True,
             "kind": "TabItem", "changed": True, "selected": True, "surfaceChanged": False}
    step = cu_rules.deterministic_step(
        goal="ir a la pestaña avanzado", view=_tabs_view(), history=[click], application="Propiedades del sistema",
    )
    assert step is None or step.get("code") != cu_rules.CLICK_WITHOUT_EFFECT, step
    # Contracase: the worker measured the place and it stayed: that is said.
    measured = cu_rules.deterministic_step(
        goal="ir a la pestaña avanzado", view=_tabs_view(), history=[{**click, "placeMoved": False}],
        application="Propiedades del sistema",
    )
    assert measured is not None and measured.get("code") == cu_rules.CLICK_WITHOUT_EFFECT, measured


def _settings_view() -> dict:
    # Settings (WinUI NavigationView): its navigation items are ListItem in the left column.
    return {
        "window": {"title": "Configuración", "process": "SystemSettings", "focused": None,
                   "rect": {"x": 0, "y": 0, "w": 1200, "h": 800}},
        "controls": [
            {"i": 0, "kind": "Edit", "name": "Buscar una configuración", "zone": "TL"},
            {"i": 1, "kind": "ListItem", "name": "Inicio", "zone": "L"},
            {"i": 2, "kind": "ListItem", "name": "Sistema", "zone": "L"},
            {"i": 3, "kind": "ListItem", "name": "Bluetooth y dispositivos", "state": "selected", "zone": "L"},
            {"i": 4, "kind": "ListItem", "name": "Red e Internet", "zone": "L"},
            {"i": 5, "kind": "ListItem", "name": "Personalización", "zone": "L"},
            {"i": 6, "kind": "Text", "name": "Pantalla", "zone": "C"},
            {"i": 7, "kind": "Button", "name": "Notificaciones", "zone": "C"},
        ],
        "text": {},
    }


def _bluetooth_click(**receipt: object) -> list[dict]:
    return [{"step": 2, "operation": "input.visible.click", "label": "Bluetooth y dispositivos", "index": 3, "ok": True,
             "kind": "ListItem", "changed": True, "selected": True, "surfaceChanged": False, **receipt}]


def _settings_step(history: list[dict]) -> dict | None:
    return cu_rules.deterministic_step(
        goal="ir a bluetooth y dispositivos", view=_settings_view(), history=history, application="Configuración",
        objective="andá a bluetooth y dispositivos en configuración",
    )


def test_revision1_b2_a_navigation_list_item_chosen_without_moving_is_said_never_looked_up() -> None:
    step = _settings_step(_bluetooth_click(placeMoved=False))
    assert step is not None and step["operation"] == "none" and step["code"] == cu_rules.CLICK_WITHOUT_EFFECT, step
    assert not _looks_up_blind(step)


def test_revision1_b2_contracases_a_navigation_item_that_moved_or_was_not_measured_or_a_content_row() -> None:
    moved = _settings_step(_bluetooth_click(placeMoved=True))
    assert moved is None or moved.get("code") != cu_rules.CLICK_WITHOUT_EFFECT, moved
    unmeasured = _settings_step(_bluetooth_click())
    assert unmeasured is None, unmeasured
    # A content row (zone C) that only chooses is no place, whatever its receipt says.
    row = {"i": 9, "kind": "ListItem", "name": "Bluetooth y dispositivos", "state": "selected", "zone": "C"}
    view = {**_settings_view(), "controls": [*_settings_view()["controls"][:3], row]}
    assert not cu_rules._chosen_without_arriving(row, _bluetooth_click(placeMoved=False), view)
    assert cu_rules._chosen_without_arriving(
        _settings_view()["controls"][3], _bluetooth_click(placeMoved=False), _settings_view(),
    )


def test_contracase_s04_a_node_whose_place_moved_is_the_arrivals_to_judge() -> None:
    # A node that navigates when chosen (a Settings page, an mmc node) moved the place on the first try.
    assert not cu_rules._chosen_without_arriving(
        _explorer()["controls"][3], _downloads_click(surfaceChanged=False, placeMoved=True),
    )
    assert not cu_rules._chosen_without_arriving(_explorer()["controls"][3], _downloads_click(surfaceChanged=True))


def test_contracase_a_row_that_only_chooses_or_a_control_not_shown_chosen_is_no_place_unreached() -> None:
    # The content row «Descargas» of Explorer's Home keeps _content_item_chosen and Enter; Discord's card word
    # «Cotele», not chosen, keeps the window's lookup.
    row = {"i": 9, "kind": "ListItem", "name": "Descargas", "state": "selected", "zone": "C"}
    history = [{"step": 2, "operation": "input.visible.click", "label": "Descargas", "ok": True, "selected": True,
                "surfaceChanged": False, "placeMoved": False}]
    assert not cu_rules._chosen_without_arriving(row, history)
    unchosen = {"i": 3, "kind": "TreeItem", "name": "Downloads", "zone": "L"}
    assert not cu_rules._chosen_without_arriving(unchosen, _downloads_click(surfaceChanged=False))
    # A context menu or an opening is never a choice that did not arrive.
    opened = [{**_downloads_click(surfaceChanged=False)[0], "manner": "open"}]
    assert not cu_rules._chosen_without_arriving(_explorer()["controls"][3], opened)


def test_contracase_the_home_content_row_still_gets_enter() -> None:
    view = {
        "window": {"title": "Inicio - Explorador de archivos", "process": "explorer", "focused": None,
                   "rect": {"x": 0, "y": 0, "w": 1200, "h": 800}},
        "controls": [
            {"i": 0, "kind": "TreeItem", "name": "Inicio", "state": "selected", "zone": "L"},
            {"i": 1, "kind": "ListItem", "name": "Descargas", "state": "selected", "zone": "C",
             "value": "Carpeta de archivos"},
            {"i": 2, "kind": "ListItem", "name": "Documentos", "zone": "C", "value": "Carpeta de archivos"},
            {"i": 3, "kind": "Edit", "name": "Buscar en Inicio", "zone": "TR"},
        ],
        "text": {},
    }
    history = [{"step": 2, "operation": "input.visible.click", "label": "Descargas", "index": 1, "ok": True,
                "kind": "ListItem", "changed": True, "selected": True, "surfaceChanged": False}]
    step = cu_rules.deterministic_step(
        goal="ir a descargas", view=view, history=history, application="Explorador de archivos",
    )
    assert step is None or step["operation"] != "none"
    assert not _looks_up_blind(step) or step["operation"] == "input.key.press"


def _spotify(*, grid: bool = True) -> dict:
    # The view of x7 and u9: Spotify's home with the search box's suggestions open.
    controls = [
        {"i": 0, "kind": "Button", "name": "Inicio", "zone": "TL"},
        {"i": 1, "kind": "Button", "name": "Buscar", "zone": "T"},
        {"i": 2, "kind": "ComboBox", "name": "¿Qué quieres reproducir?", "value": "cumbia", "state": "expanded focused",
         "zone": "T"},
        {"i": 3, "kind": "CheckBox", "name": "Todo", "state": "on", "zone": "TL"},
        {"i": 4, "kind": "CheckBox", "name": "Música", "state": "off", "zone": "TL"},
        {"i": 5, "kind": "Hyperlink", "name": "Cumbias para carretear", "zone": "C"},
    ]
    if grid:
        controls.append({"i": 6, "kind": "DataGrid", "name": "Search results", "zone": "T"})
    return {"window": {"title": "Spotify Premium", "process": "Spotify", "focused": None,
                       "rect": {"x": 0, "y": 0, "w": 1200, "h": 800}},
            "controls": controls, "text": {}}


def test_twin_u9_the_search_results_grid_is_never_the_search_place_by_containment() -> None:
    view = _spotify()
    assert cu_view.find_control(view, "search", placing=True) is None or (
        cu_view.find_control(view, "search", placing=True)["kind"] != "DataGrid"
    )
    clicked_search = [{"step": 2, "operation": "input.visible.click", "label": "Buscar", "index": 1, "ok": True,
                       "kind": "Button", "changed": True, "surfaceChanged": True}]
    for history in ([], clicked_search):
        step = cu_rules.deterministic_step(
            goal="ir a search", view=view, history=history, application="Spotify", objective="go to Search in Spotify",
        )
        if step is not None and step["operation"] == "input.visible.click":
            assert missions_fold(step["arguments"].get("label")) != "search results"


def test_contracase_u9_a_place_named_exactly_like_a_panel_is_that_panel() -> None:
    view = _spotify()
    found = cu_view.find_control(view, "Search results", placing=True)
    assert found is not None and found["kind"] == "DataGrid"
    # Not going to a place, containment still counts as before.
    assert cu_view.find_control(view, "results") is not None


def test_twin_x7_the_search_pressed_is_never_followed_by_a_find_key_escape_or_scroll() -> None:
    clicked_search = [{"step": 2, "operation": "input.visible.click", "label": "Buscar", "index": 1, "ok": True,
                       "kind": "Button", "changed": True, "surfaceChanged": True}]
    step = cu_rules.deterministic_step(
        goal="ir a search", view=_spotify(grid=False), history=clicked_search, application="Spotify",
        objective="andá a search en Spotify",
    )
    assert step is None or step["operation"] not in ("input.key.press", "input.scroll", "input.text.type"), step


def test_the_search_place_is_data_and_a_search_for_a_name_is_not_it() -> None:
    for said in ("search", "búsqueda", "Buscar", "buscador"):
        assert is_search_place(said), said
    for said in ("hades", "descargas", "search results", ""):
        assert not is_search_place(said), said


def test_contracase_a_search_for_a_name_keeps_the_find_key() -> None:
    # «buscá Hades»: the find stays the window's (ctrl_f, the text and Enter), never cut by the search place.
    assert not is_search_place("hades")


def test_the_receipt_keys_the_mind_reads_are_projected_by_the_app() -> None:
    from pathlib import Path
    import re

    source = (Path(__file__).resolve().parents[1] / "src" / "Baxy.App" / "ComputerUseMission.ForTheMind.cs").read_text(encoding="utf-8")
    body = source[source.index("internal static JsonArray HistoryForMind("):]
    listed = re.search(r"foreach \(string key in new\[\] \{([^}]*)\}\)", body)
    assert listed is not None
    keys = set(re.findall(r'"(\w+)"', listed.group(1)))
    assert {"selected", "surfaceChanged", "placeMoved"} <= keys


def _search_views() -> dict[str, dict]:
    # Revisión 1 (B1): what a view may show once the search's own control was pressed. A: the button and the field both
    # named «Buscar»; B: the button gone, the search's combo box in its place; C: a navigation item «Buscar» in the left
    # column and a button «Buscar».
    window = {"title": "Reproductor", "process": "player", "focused": None, "rect": {"x": 0, "y": 0, "w": 1200, "h": 800}}
    common = [
        {"i": 0, "kind": "Button", "name": "Inicio", "zone": "TL"},
        {"i": 5, "kind": "Hyperlink", "name": "Lo más escuchado", "zone": "C"},
    ]
    return {
        "A": {"window": window, "text": {}, "controls": [
            *common, {"i": 1, "kind": "Button", "name": "Buscar", "zone": "T"},
            {"i": 2, "kind": "Edit", "name": "Buscar", "state": "focused", "zone": "T"}]},
        "B": {"window": window, "text": {}, "controls": [
            *common, {"i": 2, "kind": "ComboBox", "name": "¿Qué quieres reproducir?", "state": "expanded focused",
                      "zone": "T"}]},
        "C": {"window": window, "text": {}, "controls": [
            *common, {"i": 1, "kind": "ListItem", "name": "Buscar", "zone": "L"},
            {"i": 3, "kind": "Button", "name": "Buscar", "zone": "T"},
            {"i": 4, "kind": "ListItem", "name": "Biblioteca", "zone": "L"}]},
    }


_SEARCH_PRESSED = [{"step": 2, "operation": "input.visible.click", "label": "Buscar", "index": 1, "ok": True,
                    "kind": "Button", "changed": True, "surfaceChanged": True}]


def test_revision1_b1_the_search_pressed_is_never_looked_up_blind_whatever_the_view_shows() -> None:
    for case, view in _search_views().items():
        for goal in ("ir a search", "ir a buscar", "ir a la búsqueda"):
            step = cu_rules.deterministic_step(
                goal=goal, view=view, history=_SEARCH_PRESSED, application="Reproductor", objective=f"{goal} en el reproductor",
            )
            assert step is None, (case, goal, step)


def test_revision1_b1_contracases_the_search_not_pressed_yet_or_another_place_after_it() -> None:
    names = ("search", "buscar")
    assert not cu_rules._search_place_pressed("search", names, [])
    # A press that failed is no press.
    assert not cu_rules._search_place_pressed("search", names, [{**_SEARCH_PRESSED[0], "ok": False}])
    # Another place after pressing the search keeps the window's lookup.
    assert not cu_rules._search_place_pressed("hades", ("hades",), _SEARCH_PRESSED)
    assert cu_rules._search_place_pressed("search", names, _SEARCH_PRESSED)
    # Before pressing, the search's own control is pressed (view C: its navigation item, the one in the left column).
    step = cu_rules.deterministic_step(
        goal="ir a buscar", view=_search_views()["C"], history=[], application="Reproductor",
        objective="ir a buscar en el reproductor",
    )
    assert step is not None and step["operation"] == "input.visible.click", step
    assert step["arguments"]["label"] == "Buscar", step


# Revisión 3 (D): the worker refuses a press on a container named exactly as the place (visible_control_is_container).
# The refusal goes back to the model with its reason; no rule's retry looks the place up blind in the window's search.
def _songs_view() -> dict:
    return {
        "window": {"title": "Música", "process": "musica", "focused": None, "rect": {"x": 0, "y": 0, "w": 1000, "h": 700}},
        "controls": [
            {"i": 0, "kind": "Button", "name": "Inicio", "zone": "L"},
            {"i": 1, "kind": "List", "name": "Canciones", "zone": "C"},
            {"i": 2, "kind": "ListItem", "name": "Tema uno", "zone": "C"},
            {"i": 3, "kind": "Edit", "name": "Buscar", "zone": "T"},
        ],
        "text": {},
    }


def _search_grid_view() -> dict:
    # The shape of u9/x7: a grid named like the place and the window's search button.
    return {
        "window": {"title": "Ajustes", "process": "ajustes", "focused": None, "rect": {"x": 0, "y": 0, "w": 1000, "h": 700}},
        "controls": [
            {"i": 0, "kind": "Button", "name": "Inicio", "zone": "L"},
            {"i": 1, "kind": "DataGrid", "name": "Search", "zone": "C"},
            {"i": 2, "kind": "Button", "name": "Buscar", "zone": "T"},
        ],
        "text": {},
    }


def _failed_click(label: str, error: str) -> list[dict]:
    return [{"step": 1, "operation": "input.visible.click", "label": label, "index": 1, "ok": False, "error": error}]


def test_revision3_d_p1_a_container_refused_goes_to_the_model_never_to_the_search() -> None:
    view = _songs_view()
    first = cu_rules.deterministic_step(goal="ir a canciones", view=view, history=[], objective="andá a canciones")
    assert first is not None and first["operation"] == "input.visible.click", first
    assert (first.get("arguments") or {}).get("index") == 1, first
    after = cu_rules.deterministic_step(
        goal="ir a canciones", view=view, history=_failed_click("Canciones", cu_rules.CONTAINER_REFUSAL),
        objective="andá a canciones",
    )
    assert after is None, after
    told = cu_diagnosis.failed_click_diagnosis(_failed_click("Canciones", cu_rules.CONTAINER_REFUSAL)[0], view)
    assert "contenedor" in told and "elementos" in told, told


def test_revision3_d_p2_the_search_grid_refused_never_types_the_place_into_the_search() -> None:
    view = _search_grid_view()
    first = cu_rules.deterministic_step(goal="ir a search", view=view, history=[], objective="andá a search")
    assert first is not None and (first.get("arguments") or {}).get("index") == 1, first
    after = cu_rules.deterministic_step(
        goal="ir a search", view=view, history=_failed_click("Search", cu_rules.CONTAINER_REFUSAL),
        objective="andá a search",
    )
    assert after is None, after
    assert not _looks_up_blind(after)


def test_revision3_d_contracase_a_click_that_found_nothing_keeps_its_retry() -> None:
    # A click by a name the view no longer resolves (visible_button_not_found) keeps the retry it had: the rule goes on.
    view = _songs_view()
    after = cu_rules.deterministic_step(
        goal="ir a canciones", view=view, history=_failed_click("Canciones", "visible_button_not_found"),
        objective="andá a canciones",
    )
    assert after is not None, after
    told = cu_diagnosis.failed_click_diagnosis(_failed_click("Canciones", "visible_button_not_found")[0], view)
    assert "contenedor" not in told, told
