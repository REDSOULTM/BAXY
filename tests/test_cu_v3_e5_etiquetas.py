"""Pasada r9 del goal v3: el encoder E5 que no responde y las etiquetas en el otro idioma.

Medido en las trazas de la pasada (última corrida de cada caso): 25 pasos «e5_cold» y 12 «e5_failed» en 13 casos.
«e5_failed» es casi siempre el primer o segundo pedido justo después de que el worker quedó listo (t-menu-3, t-long-3,
v3-56, v3-59…): la primera inferencia pasa los 0,75 s del paso. «e5_cold» es el worker todavía cargando entre 37 y más
de 80 s después del arranque con el lote cargando el PC (v3-50, v3-62, t-form-1). En los dos estados el motor seguía
con una tecla de regla a ciegas: ctrl_k en el Bloc de notas abrió «Insertar vínculo» (t-menu-3).

t-scroll-3: el motor buscó «fonts» (el nombre dicho en inglés) en una Configuración en español y eligió el eco «Q
fonts» en vez del resultado «Configuración de fuentes».

Las vistas son las reales del journal de la pasada (``tests/data/cu_e5_etiquetas_vistas.json``; el journal guarda 20
controles de cada vista, la cuenta de la persona anonimizada).
"""

from __future__ import annotations

import copy
import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest

import baxy_mind.router_worker as router_worker
from baxy_mind import computer_use
from baxy_mind import cu_view
from baxy_mind import cu_acts
from baxy_mind import cu_languages
from baxy_mind import cu_meaning
from baxy_mind import cu_lookup
from baxy_mind import cu_rules
from baxy_mind.semantic import cu_semejanza
from baxy_mind.semantic.request import evident_language

_FROZEN = json.loads((Path(__file__).parent / "data" / "cu_e5_etiquetas_vistas.json").read_text(encoding="utf-8"))

MENU_OBJECTIVE = "Zoom in twice in Notepad using the View menu, View > Zoom > Zoom in"
FONTS_OBJECTIVE = "Go to Settings, Personalization, Fonts, scroll down to Times New Roman and open its page"


def _frozen(case: str, step: int) -> dict:
    return copy.deepcopy(next(item["view"] for item in _FROZEN if item["case"] == case and item["step"] == step))


def _notepad() -> dict:
    # The mind saw the 39 controls of this look whole (trace «step.1.controls.39»); the journal kept 20 of them.
    view = _frozen("t-menu-3", 1)
    view["controlCount"] = len(view["controls"])
    return view


def _index(view: dict, name: str) -> int:
    return next(control["i"] for control in view["controls"] if control.get("name") == name)


def _failed(texts, *, prefix="query"):
    raise TimeoutError("interactive encoder budget expired")


class _Cold:
    """An E5 worker still loading: never ready, and encoding fails like the router before «ready»."""

    def try_ready(self, timeout: float = 0.0) -> bool:
        return False

    def __call__(self, texts, *, prefix="query"):
        raise TimeoutError("router worker response timed out")


class _Model:
    def __init__(self, reply: dict) -> None:
        self.reply = reply
        self.payloads: list[dict] = []

    def _post_schema_object(self, payload: dict, what: str) -> dict:
        self.payloads.append(payload)
        return self.reply


def _decide(model: _Model, view: dict, goal: str, *, encoder=None, history=None, objective=MENU_OBJECTIVE) -> dict:
    return computer_use.decide_step(
        model, objective=objective, goal=goal, application="Bloc de notas", success_check=None, view=view,
        history=history or [], budget_left=20, application_names=[], encoder=encoder,
    )


# ------------------------------------------------------------------ t-menu-3: E5 caído, decide el modelo


def test_t_menu_3_twin_the_literal_lookup_is_a_blind_shortcut() -> None:
    # The live step: «View» is not written on the Spanish Notepad («Ver» is), the rule looked it up with ctrl_k. Since
    # menus-teclas (ronda 12) the window's menu bar holds the routine's shortcut back until the model has opened
    # ``_MENUS_BEFORE_KEYS`` of its menus; once they are open, the blind shortcut is the rule's step again.
    view = _notepad()
    assert cu_rules.deterministic_step(goal="ir a View", view=view, history=[], objective=MENU_OBJECTIVE) is None
    opened = [
        {"operation": "input.visible.click", "label": name, "ok": True, "changed": True} for name in ("Archivo", "Editar")
    ]
    step = cu_rules.deterministic_step(goal="ir a View", view=view, history=opened, objective=MENU_OBJECTIVE)
    # Ronda 21: over the editor's document that shortcut is the find (ctrl_f), never ctrl_k (it opened «Vínculo»).
    assert step == {"operation": "input.key.press", "arguments": {"key": "ctrl_f"}, "reason": cu_acts._REASON_FIND}


@pytest.mark.parametrize("encoder", [_failed, _Cold()], ids=["e5_failed", "e5_cold"])
def test_t_menu_3_an_encoder_that_cannot_answer_leaves_the_step_to_the_model(encoder, monkeypatch) -> None:
    monkeypatch.setattr(cu_meaning, "_COLD_WAIT", cu_meaning._ColdWait(0.0))
    view = _notepad()
    model = _Model({"act": "click", "i": _index(view, "Ver")})
    decided = _decide(model, view, "ir a View", encoder=encoder)
    assert model.payloads, "the model was not asked"
    assert decided["operation"] == "input.visible.click" and decided["arguments"]["label"] == "Ver"
    assert decided["source"] == cu_meaning.SOURCE_MODEL
    assert decided["encoder"] in (cu_meaning.ENCODER_FAILED, cu_meaning.ENCODER_COLD)


def test_t_menu_3_a_model_none_is_never_turned_into_the_blind_shortcut() -> None:
    decided = _decide(_Model({"act": "none"}), _notepad(), "ir a View", encoder=_failed)
    assert decided["operation"] == "none" and decided["source"] == cu_meaning.SOURCE_MODEL


def test_contracase_without_an_encoder_the_rule_is_unchanged() -> None:
    # Without an encoder the step is what it was before this branch: with the menu bar holding the shortcut (ronda 12,
    # menus-teclas) the model is asked once, and its none falls back to the routine's literal lookup.
    model = _Model({"act": "none"})
    decided = _decide(model, _notepad(), "ir a View")
    assert len(model.payloads) == 1
    assert decided["arguments"] == {"key": "ctrl_f"} and decided["source"] == cu_meaning.SOURCE_RULE


def test_contracase_a_place_written_on_screen_is_clicked_by_the_rule_with_the_encoder_down() -> None:
    view = _notepad()
    model = _Model({"act": "none"})
    decided = _decide(model, view, "ir a Editar", encoder=_failed)
    assert not model.payloads
    assert decided["operation"] == "input.visible.click" and decided["arguments"]["label"] == "Editar"


def test_contracase_a_lookup_already_started_goes_on_by_rule() -> None:
    # Once a search began (a shortcut pressed), its own next step (Escape on the link dialog) stays the rule's.
    view = _notepad()
    history = [{"operation": "input.key.press", "key": "ctrl_k", "ok": True, "changed": True}]
    model = _Model({"act": "none"})
    decided = _decide(model, view, "ir a View", encoder=_failed, history=history)
    assert not model.payloads and decided["source"] == cu_meaning.SOURCE_RULE


# ------------------------------------------------------------------ worker: la primera inferencia antes de «ready»


def test_the_worker_warms_the_model_up_before_saying_ready() -> None:
    calls: list[tuple[str, tuple[str, ...]]] = []
    order: list[str] = []

    class Encoder:
        def encode(self, texts, *, prefix="query"):
            calls.append((prefix, tuple(texts)))
            order.append("encode")
            return __import__("numpy").zeros((len(texts), 2), dtype="float32")

    output = io.StringIO()

    class Spy(io.StringIO):
        def write(self, text):
            if '"ready"' in text:
                order.append("ready")
            return output.write(text)

    with (
        patch.object(router_worker, "SemanticEncoder", Encoder),
        patch.object(router_worker.sys, "stdin", io.StringIO(json.dumps({"type": "shutdown", "id": 1}) + "\n")),
        patch.object(router_worker.sys, "stdout", Spy()),
    ):
        assert router_worker.main() == 0
    assert order[:len(router_worker.ENCODER_PREFIXES)] == ["encode"] * len(router_worker.ENCODER_PREFIXES)
    assert order[len(router_worker.ENCODER_PREFIXES)] == "ready"
    assert {prefix for prefix, _ in calls} == set(router_worker.ENCODER_PREFIXES)


def test_contracase_a_warm_up_that_fails_still_says_ready() -> None:
    class Broken:
        def encode(self, texts, *, prefix="query"):
            raise RuntimeError("no warm-up")

    output = io.StringIO()
    with (
        patch.object(router_worker, "SemanticEncoder", Broken),
        patch.object(router_worker.sys, "stdin", io.StringIO(json.dumps({"type": "shutdown", "id": 1}) + "\n")),
        patch.object(router_worker.sys, "stdout", output),
    ):
        assert router_worker.main() == 0
    assert json.loads(output.getvalue().splitlines()[0]) == {"type": "ready"}


# ------------------------------------------------------------------ t-scroll-3: la etiqueta en el idioma de la ventana


_NOT_FOUND = "visible_button_not_found"


def _settings_with_search_focused() -> dict:
    view = _frozen("t-scroll-3", 5)
    view["window"]["focused"] = {"kind": "Edit", "name": "Cuadro de búsqueda, Buscar una opción", "i": 4}
    for control in view["controls"]:
        if control["i"] == 4:
            control["state"] = "focused"
    return view


def _searched(typed: str) -> list[dict]:
    return [
        {"operation": "input.visible.click", "label": "fuentes", "ok": False, "error": _NOT_FOUND},
        {"operation": "input.visible.click", "label": "fonts", "ok": False, "error": _NOT_FOUND},
        {"operation": "input.visible.click", "label": "Cuadro de búsqueda, Buscar una opción", "index": 4, "ok": True,
         "kind": "Edit", "surfaceChanged": True},
        {"operation": "input.text.type", "text": typed, "ok": True},
    ]


def test_t_scroll_3_the_window_language_name_is_clicked_first() -> None:
    # Live: «fonts» was clicked by label first on the Spanish Settings, then «fuentes».
    step = cu_rules.deterministic_step(goal="ir a fonts", view=_frozen("t-scroll-3", 5), history=[], objective=FONTS_OBJECTIVE)
    assert step is not None and step["arguments"] == {"label": "fuentes"}


def test_t_scroll_3_the_search_types_the_window_language_name() -> None:
    history = _searched("")[:3]
    step = cu_rules.deterministic_step(goal="ir a fonts", view=_settings_with_search_focused(), history=history,
                                           objective=FONTS_OBJECTIVE)
    assert step == {"operation": "input.text.type", "arguments": {"text": "fuentes"}, "reason": cu_acts._REASON_FIND}


def _results(typed: str) -> dict:
    """The live view after the search (typed «fonts»), with the field and its echo saying ``typed``."""

    view = _frozen("t-scroll-3", 7)
    view["window"]["focused"]["value"] = typed
    for control in view["controls"]:
        if control.get("value") == "fonts":
            control["value"] = typed
    view["text"] = {zone: [f"Q {typed}" if line == "Q fonts" else line for line in lines] for zone, lines in view["text"].items()}
    return view


@pytest.mark.parametrize("typed", ["fonts", "fuentes"])
def test_t_scroll_3_the_result_named_in_the_window_language_is_chosen_never_the_echo(typed: str) -> None:
    # Live (typed «fonts»): the echo «Q fonts» of the field was clicked; «Configuración de fuentes» was listed.
    view = _results(typed)
    assert f"Q {typed}" in view["text"]["TL"] and view["window"]["focused"]["value"] == typed
    step = cu_rules.deterministic_step(goal="ir a fonts", view=view, history=_searched(typed), objective=FONTS_OBJECTIVE)
    assert step is not None and step["arguments"]["label"] == "Configuración de fuentes"


@pytest.mark.parametrize("typed", ["fonts", "fuentes"])
def test_t_scroll_3_the_echo_alone_is_never_a_result(typed: str) -> None:
    # The cause of the live click: with no result listed, the line «Q <typed>» (the field's echo) was the «result».
    view = _results(typed)
    view["controls"] = [control for control in view["controls"]
                        if control.get("kind") != "ListItem" or control.get("name") in ("Inicio", "Sistema")]
    view["text"]["T"] = []
    step = cu_rules.deterministic_step(goal="ir a fonts", view=view, history=_searched(typed), objective=FONTS_OBJECTIVE)
    assert step is not None and step["operation"] != "input.visible.click", step
    # Without the request (no translation) the echo is no result either.
    assert cu_lookup._result_naming(view, typed, _searched(typed)) is None


def test_contracase_the_name_is_kept_as_said_when_the_request_speaks_the_window_language() -> None:
    names = cu_languages._in_window_language("fuentes", ("fonts",), _frozen("t-scroll-3", 5), "andá a configuración y abrí las fuentes")
    assert names == ("fuentes", "fonts")
    # A request whose words tell no language keeps the order as said.
    assert cu_languages._in_window_language("fonts", ("fuentes",), _frozen("t-scroll-3", 5), "fonts") == ("fonts", "fuentes")
    assert evident_language("ir a fonts") is None and evident_language(FONTS_OBJECTIVE) == "en"


def test_contracase_an_english_window_keeps_the_english_name() -> None:
    view = {
        "window": {"title": "Settings", "process": "SystemSettings"},
        "controls": [{"i": 0, "kind": "Edit", "name": "Search box, Find a setting"},
                     {"i": 1, "kind": "ListItem", "name": "Personalization"}],
        "text": {"C": ["Select a theme to apply", "Background", "Colors", "Themes", "Lock screen", "Text input"]},
    }
    assert cu_languages._in_window_language("fonts", ("fuentes",), view, FONTS_OBJECTIVE)[0] == "fonts"


def test_contracase_a_search_for_the_person_words_is_never_translated() -> None:
    history = [{"operation": "input.visible.click", "label": "Cuadro de búsqueda, Buscar una opción", "index": 4,
                "ok": True, "kind": "Edit", "surfaceChanged": True}]
    step = cu_rules.deterministic_step(goal="buscar fonts", view=_settings_with_search_focused(), history=history,
                                           objective=FONTS_OBJECTIVE)
    assert step is not None and step["arguments"].get("text") == "fonts"


def test_contracase_an_absent_place_matches_no_other_result() -> None:
    # A result that names neither the place nor any of its names is never chosen («Tamaño de texto» for «fonts»).
    view = _frozen("t-scroll-3", 7)
    view["controls"] = [control for control in view["controls"] if control.get("name") != "Configuración de fuentes"]
    view["text"] = {zone: [line for line in lines if "fuentes" not in line.lower() and "fonts" not in line.lower()]
                    for zone, lines in view["text"].items()}
    step = cu_rules.deterministic_step(goal="ir a fonts", view=view, history=_searched("fuentes"), objective=FONTS_OBJECTIVE)
    # Nothing on the view is the place (the results «Tamaño de texto», «Ajustar texto ClearType», the echo «Q fonts»):
    # no click; the search is submitted or closed to try the next way.
    assert step is not None and step["operation"] == "input.key.press", step


def test_the_frozen_views_carry_no_account_of_the_person() -> None:
    text = json.dumps(_FROZEN, ensure_ascii=False)
    assert "@" not in text
    # The account button keeps only the anonymised name the journal gave it, on every view of Settings.
    for item in _FROZEN:
        for control in item["view"]["controls"]:
            if control.get("zone") == "TL" and control.get("kind") == "Button" and control.get("i") == 12:
                assert control["name"] == "Cuenta de usuario"


# ------------------------------------------------------------------ revisión adversarial r2: un solo idioma, actos de
# cuenta, el nombre dicho tal como lo muestra la ventana, la rueda y el estado del encoder, la ráfaga


_EN_SETTINGS_SEARCH = {"kind": "Edit", "name": "Search box, Find a setting", "i": 0}


def _english_settings(typed: str | None, *results: str) -> dict:
    field = {**_EN_SETTINGS_SEARCH, "state": "focused", **({"value": typed} if typed else {})}
    return {
        "window": {"title": "Settings", "process": "SystemSettings", "focused": dict(field)},
        "controls": [field, *({"i": 1 + n, "kind": "ListItem", "name": name} for n, name in enumerate(results)),
                     {"i": 1 + len(results), "kind": "ListItem", "name": "System"},
                     {"i": 2 + len(results), "kind": "ListItem", "name": "Personalization"}],
        "text": {"C": ["Select a theme to apply", "Background", "Colors", "Themes", "Lock screen", "Text input", "File",
                       "View", "Help"]},
    }


def _typed_into_english_search(typed: str) -> list[dict]:
    return [{"operation": "input.visible.click", "label": _EN_SETTINGS_SEARCH["name"], "index": 0, "ok": True,
             "kind": "Edit", "surfaceChanged": True},
            {"operation": "input.text.type", "text": typed, "ok": True}]


def test_one_language_the_table_alias_is_no_substring_of_a_result() -> None:
    # Review r2 (1): «red» (the table's Spanish «network») is inside «Sha·red»; one language, the base's result.
    view = _english_settings("network", "Shared experiences settings", "Network status")
    step = cu_rules.deterministic_step(goal="ir a network", view=view, history=_typed_into_english_search("network"),
                                           objective="Open Settings and go to network")
    assert step is not None and step["arguments"]["label"] == "Network status"


def test_contracase_another_language_the_other_name_counts_as_whole_words_only() -> None:
    view = _frozen("t-scroll-3", 7)
    assert cu_view._whole_words_name("red", "Red e Internet")
    assert not cu_view._whole_words_name("red", "Shared experiences settings")
    assert not cu_view._whole_words_name("fuentes", "Configuración de fuentesx")
    assert cu_lookup._result_naming(view, "fonts", _searched("fonts"), ("fuentes",))["arguments"]["label"] == (
        "Configuración de fuentes")


def _spanish_player(typed: str, *controls: dict) -> dict:
    field = {"i": 0, "kind": "Edit", "name": "¿Qué quieres reproducir?", "state": "focused", "value": typed}
    return {
        "window": {"title": "Reproductor", "process": "Player", "focused": dict(field)},
        "controls": [field, {"i": 1, "kind": "Button", "name": "Inicio"}, *controls],
        "text": {"C": ["Inicio", "Búsqueda", "Canciones", "Guardar en Tu biblioteca"]},
    }


def _typed_into_player(typed: str) -> list[dict]:
    return [{"operation": "input.visible.click", "label": "¿Qué quieres reproducir?", "index": 0, "ok": True,
             "kind": "Edit", "surfaceChanged": True},
            {"operation": "input.text.type", "text": typed, "ok": True}]


_SAVE = {"i": 2, "kind": "Button", "name": "Guardar en Tu biblioteca"}


@pytest.mark.parametrize("typed", ["library", "biblioteca"])
@pytest.mark.parametrize("objective", ["Go to my library in the player", "andá a mi biblioteca en el reproductor"])
def test_an_account_act_is_never_the_result_of_going_to_a_place(typed: str, objective: str) -> None:
    # Review r2 (2): «Guardar en Tu biblioteca» names «biblioteca» (the table's name for «library»): an account act
    # RiskPolicy does not confirm, reached by another name or by the name as said; never pressed on the way.
    view = _spanish_player(typed, _SAVE)
    step = cu_rules.deterministic_step(goal="ir a library", view=view, history=_typed_into_player(typed), objective=objective)
    assert step is None or step.get("arguments", {}).get("label") != "Guardar en Tu biblioteca", step


@pytest.mark.parametrize(("typed", "goal", "objective"), [
    ("library", "ir a library", "Go to my library in the player"),
    ("biblioteca", "ir a library", "Go to my library in the player"),
    ("biblioteca", "ir a biblioteca", "andá a mi biblioteca en el reproductor"),
])
def test_contracase_beside_the_account_act_the_place_is_the_result(typed: str, goal: str, objective: str) -> None:
    place = _spanish_player(typed, _SAVE, {"i": 3, "kind": "Button", "name": "Tu biblioteca"})
    step = cu_rules.deterministic_step(goal=goal, view=place, history=_typed_into_player(typed), objective=objective)
    assert step is not None and step["arguments"]["label"] == "Tu biblioteca"


def test_contracase_a_request_that_asks_to_save_reaches_the_save() -> None:
    view = _spanish_player("biblioteca", _SAVE)
    step = cu_rules.deterministic_step(goal="ir a biblioteca", view=view, history=_typed_into_player("biblioteca"),
                                           objective="guardá esta canción en tu biblioteca")
    assert step is not None and step["arguments"]["label"] == "Guardar en Tu biblioteca"


def test_a_content_item_is_never_reached_by_another_name() -> None:
    # A name the person did not say never lands on the person's content (a DataItem: files, rows), as a control or as
    # the line that writes it (``_search_result_of_the_interface``).
    view = _results("fonts")
    for control in view["controls"]:
        if control.get("name") == "Configuración de fuentes":
            control["kind"] = "DataItem"
    step = cu_lookup._result_naming(view, "fonts", _searched("fonts"), ("fuentes",), FONTS_OBJECTIVE)
    assert step is None or step["arguments"]["label"] != "Configuración de fuentes"


@pytest.mark.parametrize(("objective", "said"), [
    ("abrí configuración y andá a fonts por favor", "fonts"),
    ("Abrí el lanzador y andá a la Library", "Library"),
])
def test_a_name_said_as_the_window_shows_it_is_kept(objective: str, said: str) -> None:
    # Review r2 (3): a Spanish request names the place the way the English window writes it: never translated.
    view = _english_settings(None)
    assert cu_languages._in_window_language(said, computer_use.label_alternatives(said) or ("x",), view, objective)[0] == said
    step = cu_rules.deterministic_step(goal=f"ir a {said}", view=view, history=_typed_into_english_search("")[:1],
                                           objective=objective)
    assert step == {"operation": "input.text.type", "arguments": {"text": said}, "reason": cu_acts._REASON_FIND}


def test_contracase_a_name_said_in_the_request_language_is_translated() -> None:
    view = _english_settings(None)
    assert cu_languages._in_window_language("fuentes", ("fonts",), view, "abrí configuración y andá a fuentes")[0] == "fonts"


def test_name_language_tells_only_by_spelling() -> None:
    from baxy_mind.semantic.request import name_language

    assert [name_language(name) for name in ("fonts", "Library", "network", "View", "settings")] == ["en"] * 5
    assert [name_language(name) for name in ("Tamaño", "Red e Internet", "Barra de tareas")] == ["es"] * 3
    assert [name_language(name) for name in ("fuentes", "biblioteca", "red", "Ver")] == [None] * 4


def test_the_wheel_is_no_blind_lookup() -> None:
    # Review r2 (5): scrolling changes nothing and brings «Fuentes» below the list's edge into view.
    scroll = {"operation": "input.scroll", "arguments": {"direction": "down"}, "reason": cu_acts._REASON_FIND}
    key = {"operation": "input.key.press", "arguments": {"key": "ctrl_k"}, "reason": cu_acts._REASON_FIND}
    assert not cu_lookup._blind_lookup(scroll, []) and cu_lookup._blind_lookup(key, [])


def test_the_encoder_is_not_failed_when_nothing_could_be_compared() -> None:
    calls: list[tuple[str, ...]] = []

    def encode(texts, *, prefix="query"):
        calls.append(tuple(texts))
        return __import__("numpy").ones((len(texts), 2), dtype="float32")

    long_only = {"controls": [{"i": 0, "kind": "Text", "name": "x" * 200}]}
    matcher = cu_meaning.SemanticMatcher(encode, cache=cu_semejanza.EmbeddingCache(), cold_wait=cu_meaning._ColdWait(0.0))
    assert matcher.scored("fuentes", long_only) == () and matcher.state != cu_meaning.ENCODER_FAILED and not calls
    shown = {"controls": [{"i": 0, "kind": "ListItem", "name": "Configuración de fuentes"}]}
    assert matcher.scored("fuentes", shown) and matcher.state == cu_meaning.ENCODER_READY
    matcher._left = 0.0
    assert matcher.scored("fonts", shown) == () and matcher.state == cu_meaning.ENCODER_READY


def test_contracase_a_spent_budget_without_an_answer_is_failed() -> None:
    matcher = cu_meaning.SemanticMatcher(_failed, cache=cu_semejanza.EmbeddingCache(), budget_seconds=0.0)
    shown = {"controls": [{"i": 0, "kind": "ListItem", "name": "Configuración de fuentes"}]}
    assert matcher.scored("fuentes", shown) == () and matcher.state == cu_meaning.ENCODER_FAILED


def test_a_burst_launched_with_another_name_is_confirmed_at_the_re_entry() -> None:
    # Review r2 (6): the burst went out with «fuentes» (the window's name); the re-entry carries no translation.
    view = _settings_with_search_focused()
    history = [
        {"operation": "input.visible.click", "ok": True, "label": "Cuadro de búsqueda, Buscar una opción", "index": 4,
         "search": "tipos de letra", "searchBurst": True},
        {"operation": "input.text.type", "ok": True, "text": "tipos de letra", "searchBurst": True},
        {"operation": "input.visible.click", "ok": False, "label": "Tipos de letra (Fuentes)",
         "error": cu_lookup.SEARCH_RESULT_NEEDS_CONFIRMATION, "searchBurst": True},
    ]
    step = cu_lookup._find_step("fonts", view, history, objective=FONTS_OBJECTIVE)
    assert step is not None and step["arguments"] == {
        "label": "Cuadro de búsqueda, Buscar una opción", "index": 4, "search": "tipos de letra",
        "choose": "Tipos de letra (Fuentes)",
    }
