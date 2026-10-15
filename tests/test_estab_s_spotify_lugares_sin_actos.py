"""Encargo S de estabilización (banco B, fases e1 y e2, 2026-10-11): en Spotify, «andá a tu biblioteca» buscó «tu
biblioteca» en el buscador de la app, abrió una lista pública ajena con ese nombre y la puso a sonar («Shallow»), y luego
la pausó; en y8 pulsó «Reproducir MIX CUMBIAS». Tres reglas, generales y sin nombrar apps:

1. Un lugar de la ventana con botón propio (que lo nombra tras un verbo que lo abre o lo cierra: «Abre Tu biblioteca»,
   «Comprimir Tu biblioteca») se alcanza por ese botón, una vez por sub-objetivo; nunca se busca en el buscador del
   contenido ni se pulsa otro control con su nombre.
2. Un acto en nombre de la persona (seguir, guardar, me gusta, instalar, la sesión y ahora reproducir o pausar) nunca se
   pulsa si el objetivo no lo pide, ni por el modelo ni por una regla. Las palabras están en data/account_acts.v1.json.
3. (La App, ComputerUseSuccessCheck.PlaceToggle: el lugar está abierto o cerrado por su botón propio.)

Las vistas son las reales congeladas (tests/data/estab_s_spotify_vistas.json)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from baxy_mind import computer_use as cu
from baxy_mind import cu_unasked
from baxy_mind import cu_lookup
from baxy_mind import cu_rules
from baxy_mind import cu_validate
from baxy_mind import operation_floor
from baxy_mind.semantic import missions
from baxy_mind.effect_intent import resolve_explicit_effects
from baxy_mind.semantic.account_acts import account_act, goal_asks_for

VIEWS = json.loads((Path(__file__).parent / "data" / "estab_s_spotify_vistas.json").read_text(encoding="utf-8"))["views"]
ACTS = json.loads(
    (Path(cu.__file__).resolve().parent / "data" / "account_acts.v1.json").read_text(encoding="utf-8")
)
GOAL = "ir a tu biblioteca"
OBJECTIVE = "abrí Spotify y andá a tu biblioteca"
CHECK = "control:tu biblioteca:current|title:tu biblioteca|page:tu biblioteca|mark:tu biblioteca"


def _view(name: str) -> dict:
    return copy.deepcopy(VIEWS[name])


def _index(view: dict, name: str) -> int:
    return next(control["i"] for control in view["controls"] if control["name"] == name)


def _validated(view: dict, label: str, goal: str = GOAL) -> dict:
    raw = {"act": "click", "i": _index(view, label)}
    return cu_validate.validate_decision(raw, view=view, last_failed=None, application_names=["Spotify"], goal=goal, history=[])


class _Model:
    """A model that answers the step it is given (the real one's answer in the frozen run), or none."""

    def __init__(self, answer: dict | None = None) -> None:
        self.answer = answer or {"act": "none"}

    def _post_schema_object(self, payload: dict, what: str) -> dict:
        return {"labels": []} if "ruta" in what else self.answer


def _decide(view: dict, history: list[dict], answer: dict | None = None, goal: str = GOAL) -> dict:
    return cu.decide_step(
        _Model(answer), objective=OBJECTIVE, goal=goal, application="Spotify", success_check=CHECK, view=view,
        history=history, budget_left=10, application_names=["Spotify"],
    )


def _pressed(label: str, *, ok: bool) -> dict:
    step = {"step": 1, "operation": "input.visible.click", "label": label, "kind": "Button", "ok": ok}
    if not ok:
        step.update(error="visible_button_postread_unchanged", effectUncertain=True)
    return step


# ------------------------------------------------------------------ 2. ningún acto que nadie pidió


def test_the_acts_are_one_datum_whose_examples_tie_the_reader() -> None:
    for example in ACTS["examples"]:
        assert account_act(example["control"]) == example["act"], example


def test_playing_or_pausing_is_an_act_the_goal_must_ask_for() -> None:
    assert account_act("Reproducir Tu biblioteca") == "playback"
    assert account_act("Pausar Tu biblioteca") == "playback"
    assert account_act("Play") == "playback" and account_act("Pause (k)") == "playback"
    assert not goal_asks_for(GOAL, "playback")
    assert goal_asks_for("reproducir los bunkers", "playback")
    assert goal_asks_for("play some lo-fi", "playback")
    assert goal_asks_for("pausar la música", "playback")
    # «poner» asks to play unless what follows is a mode, a setting or a reminder (data «unless»).
    assert not goal_asks_for("poner el modo oscuro", "playback")


@pytest.mark.parametrize(("view", "label"), [
    ("e2_u1_resultados_de_busqueda", "Reproducir Tu biblioteca"),   # e2 u1: «Shallow» started
    ("e2_u1_lista_ajena_sonando", "Pausar Tu biblioteca"),          # e2 u1: then paused
    ("e1_y8_mix", "Reproducir MIX CUMBIAS | 2026 🎊🪅🥂🍾🎉"),       # e1 y8
])
def test_going_to_a_place_never_plays_nor_pauses(view: str, label: str) -> None:
    step = _validated(_view(view), label)
    assert step["operation"] == "none" and step["code"] == "changes_the_account"
    assert "reproduce o pausa" in step["reason"]


def test_a_rule_never_plays_nor_pauses_what_nobody_asked() -> None:
    # e2 u1, the frozen look before «Pausar Tu biblioteca» (a rule's step there): no rule presses it, and the model's
    # click on it is refused too.
    view = _view("e2_u1_lista_ajena_sonando")
    history = [_pressed("Abre Tu biblioteca", ok=False)]
    for answer in (None, {"act": "click", "i": _index(view, "Pausar Tu biblioteca")}):
        step = _decide(view, history, answer)
        assert not (step["operation"] == "input.visible.click"
                    and account_act((step.get("arguments") or {}).get("label")) is not None), step
    assert cu_unasked._rule_presses_unasked(
        {"operation": "input.visible.click", "arguments": {"label": "Pausar Tu biblioteca"}}, GOAL)


def test_counter_case_a_goal_that_asks_to_play_still_plays() -> None:
    view = _view("e1_y8_dibujando")
    step = _validated(view, "Reproducir Los Bunkers", goal="reproducir los bunkers")
    assert step["operation"] == "input.visible.click" and step["arguments"]["label"] == "Reproducir Los Bunkers"
    assert not cu_unasked._rule_presses_unasked(
        {"operation": "input.visible.click", "arguments": {"label": "Reproducir Los Bunkers"}}, "reproducir los bunkers")
    # The typed route of «poné Los Bunkers en Spotify» is untouched: it plays.
    intent = resolve_explicit_effects(
        "poné Los Bunkers en Spotify", frozenset({"media.play.query", "mission.computer.use", "app.open"}),
        application_names=("Spotify",),
    )
    assert intent is not None and intent.operations == ("media.play.query",)


def test_counter_case_a_place_named_like_an_act_is_still_the_place() -> None:
    view = {"window": {"title": "Música"}, "controls": [
        {"i": 0, "kind": "Button", "name": "Tus me gusta"}, {"i": 1, "kind": "Button", "name": "Reproducir Tus me gusta"},
    ], "text": {}}
    assert _validated(view, "Tus me gusta", goal="ir a tus me gusta")["operation"] == "input.visible.click"
    assert _validated(view, "Reproducir Tus me gusta", goal="ir a tus me gusta")["operation"] == "none"


# ------------------------------------------------------------------ 1. un lugar con botón propio, por ese botón


def test_the_place_is_reached_by_its_own_button_not_by_a_list_named_like_it() -> None:
    view = _view("e2_u1_inicio")
    # A stranger's list «Tu biblioteca» in the recents of the home page (e2 y8): never the place.
    view["controls"].append({"i": 20, "kind": "Hyperlink", "name": "Tu biblioteca", "state": "readonly",
                             "value": "https://xpui.app.spotify.com/playlist/2vyNXjPhiOIfsBqPMyaE07"})
    step = cu_rules.deterministic_step(goal=GOAL, view=view, history=[], application="Spotify", objective=OBJECTIVE,
                                 success_check=CHECK)
    assert step is not None and step["arguments"]["label"] == "Abre Tu biblioteca"


@pytest.mark.parametrize("ok", [True, False])
def test_after_its_press_no_search_no_lookup_and_no_second_press(ok: bool) -> None:
    # e2 u1 (the press's post-read did not hold, then «tu biblioteca» went into the search) and e1 y8 (the press held,
    # the panel still being drawn, then the same search).
    view = _view("e2_u1_tras_clic_sin_efecto")
    history = [_pressed("Abre Tu biblioteca", ok=ok)]
    assert cu_rules.deterministic_step(goal=GOAL, view=view, history=history, application="Spotify", objective=OBJECTIVE,
                                 success_check=CHECK) is None
    step = _decide(view, history)
    assert step["operation"] == "none", step
    assert not cu_lookup._searches_content(step)


def test_an_open_place_is_never_pressed_again() -> None:
    # e1 y8: «Comprimir Tu biblioteca» shown; pressing it would close the library.
    assert cu_lookup.own_place_button(_view("e1_y8_abierta"), "tu biblioteca")[1] is True
    assert cu_rules.deterministic_step(goal=GOAL, view=_view("e1_y8_abierta"), history=[], application="Spotify",
                                 objective=OBJECTIVE, success_check=CHECK) is None


def test_a_place_with_its_own_button_is_never_looked_up_in_the_search() -> None:
    view = _view("e2_u1_tras_clic_sin_efecto")
    assert cu_lookup._find_step("tu biblioteca", view, [], navigate=True, objective=OBJECTIVE) is None


def test_counter_case_a_place_without_a_button_of_its_own_is_still_looked_up() -> None:
    # Discord's «Cotele» is a list item of the channels; not listed, it is looked up in the window's search.
    chat = {"window": {"title": "Amigos - Discord", "process": "Discord"}, "controls": [
        {"i": 0, "kind": "Button", "name": "Buscar o iniciar una conversación", "state": ""},
        {"i": 1, "kind": "ListItem", "name": "General"},
    ], "text": {}}
    step = cu_lookup._find_step("cotele", chat, [], navigate=True, objective="en Discord andá al canal Cotele")
    assert step is not None and cu_lookup._searches_content(step)
    assert cu_lookup.own_place_button(chat, "cotele") is None


def test_the_own_button_reads_both_languages_and_its_state() -> None:
    view = {"controls": [{"i": 0, "kind": "Button", "name": "Open Your Library"}]}
    assert cu_lookup.own_place_button(view, "your library")[1] is False
    view = {"controls": [{"i": 0, "kind": "Button", "name": "Expandir Tu biblioteca"},
                         {"i": 1, "kind": "Button", "name": "Collapse Your Library"}]}
    assert cu_lookup.own_place_button(view, "your library")[1] is True
    # A button called only as the place is no button of its own (Discord: «Cotele» a server and an activity card), nor
    # a list item or a link named so.
    assert cu_lookup.own_place_button(_view("e2_x7_inicio"), "inicio") is None
    assert cu_lookup.own_place_button({"controls": [{"i": 0, "kind": "Hyperlink", "name": "Tu biblioteca"}]}, GOAL[5:]) is None


def test_the_own_button_examples_of_the_datum_tie_the_mind() -> None:
    # The App's ComputerUseSuccessCheck.PlaceToggle reads the same examples (ComputerUseEstabSTests).
    examples = operation_floor.floor_data()["computerUse"]["placeToggle"]["examples"]
    for example in examples:
        view = {"controls": [{"i": i, "kind": "Button", "name": name} for i, name in enumerate(example["buttons"])]}
        own = cu_lookup.own_place_button(view, example["place"])
        assert (own[1] if own is not None else None) == example["open"], example


# ------------------------------------------------------------------ revisión S


H1_REQUESTS = (
    # (request, control): every one asks to play; the reader rewrites some of them without the verb.
    ("en Spotify poné Los Bunkers", "Reproducir Los Bunkers"),
    ("en Spotify poné la playlist Rock", "Reproducir Rock"),
    ("en YouTube poné el video de Shakira", "Reproducir (k)"),
    ("en Spotify dale play a Los Bunkers", "Reproducir Los Bunkers"),
    ("play Los Bunkers", "Play"),
    ("reproducí Los Bunkers", "Reproducir Los Bunkers"),
)


def _goals(request: str) -> list[str]:
    mission = missions.mission_request(request, ("Spotify", "YouTube"))
    goal = mission.goal if mission is not None else request
    return [part.strip() for part in goal.split("; luego ")]


@pytest.mark.parametrize(("request_text", "control"), H1_REQUESTS)
def test_h1_a_request_that_asks_to_play_still_plays(request_text: str, control: str) -> None:
    for goal in _goals(request_text):
        assert cu_unasked.unasked_act(control, goal, request_text) is None, (request_text, goal)


def test_h1_go_to_a_place_and_play_plays_only_in_its_own_sub_goal() -> None:
    request_text = "en Spotify andá a tu biblioteca y poné Rock"
    going, playing = _goals(request_text)
    assert going == "ir a tu biblioteca" and playing.lower().startswith("pon")
    assert cu_unasked.unasked_act("Reproducir Rock", playing, request_text) is None
    # On the way to the library nothing plays, though the request asks to play afterwards.
    assert cu_unasked.unasked_act("Reproducir Tu biblioteca", going, request_text) == "playback"


def test_h1_counter_case_putting_a_mode_never_asks_to_play() -> None:
    for request_text in ("en Spotify poné el modo oscuro", "poné el volumen al 50", "poné una alarma a las 8"):
        for goal in _goals(request_text):
            assert cu_unasked.unasked_act("Reproducir", goal, request_text) == "playback", (request_text, goal)


def test_h2_the_model_never_opens_or_types_a_list_named_like_the_place() -> None:
    view = _view("e2_u1_tras_clic_sin_efecto")
    view["controls"].append({"i": 20, "kind": "Hyperlink", "name": "Tu biblioteca", "state": "readonly"})
    step = _validated(view, "Tu biblioteca")
    assert step["operation"] == "none" and step["code"] == cu_validate.NOT_THE_OWN_BUTTON
    typed = cu_validate.validate_decision({"act": "type", "text": "tu biblioteca"}, view=view, last_failed=None,
                                 application_names=["Spotify"], goal=GOAL, history=[])
    assert typed["operation"] == "none" and typed["code"] == "types_the_place"
    # Counter-case: its own button is pressed.
    assert _validated(view, "Abre Tu biblioteca")["operation"] == "input.visible.click"


def test_h3_the_own_button_crosses_languages() -> None:
    spanish = _view("e2_u1_tras_clic_sin_efecto")
    assert cu_lookup.own_place_button(spanish, "your library") is not None
    assert cu_lookup._find_step("your library", spanish, [], navigate=True, objective="in Spotify go to your library") is None
    english = {"controls": [{"i": 0, "kind": "Button", "name": "Open Your Library"}]}
    assert cu_lookup.own_place_button(english, "tu biblioteca")[1] is False
    step = cu_rules.deterministic_step(goal="ir a your library", view=_view("e2_u1_inicio"), history=[],
                                 application="Spotify", objective="in Spotify go to your library")
    assert step is not None and step["arguments"]["label"] == "Abre Tu biblioteca"


def test_h4_a_button_that_only_leads_to_a_place_is_no_toggle() -> None:
    assert cu_lookup.own_place_button({"controls": [{"i": 0, "kind": "Button", "name": "Ir a Inicio"}]}, "inicio") is None


@pytest.mark.parametrize("label", ["Descargar", "Download", "Habilitar el Modo aleatorio para Tu biblioteca",
                                   "Shuffle play"])
def test_h6_downloading_and_shuffling_are_acts_too(label: str) -> None:
    assert cu_unasked.unasked_act(label, GOAL) is not None
    assert account_act("Siguiente") is None and account_act("Next") is None


def test_h7_a_double_click_reads_the_same_rule() -> None:
    view = {"window": {"title": "Música"}, "controls": [
        {"i": 0, "kind": "ListItem", "name": "Tus me gusta"}, {"i": 1, "kind": "ListItem", "name": "Reproducir Rock"},
    ], "text": {}}
    refused = cu_validate._checked_manner({"i": 1}, "double", view=view, goal=GOAL, objective=OBJECTIVE, history=[], why="",
                                 last_failed=None)
    assert refused["operation"] == "none" and refused["code"] == "changes_the_account"


# ------------------------------------------------------------------ fase 2 con S (f2_inest), u1, x7 y v8


def test_f2_v8_the_name_of_a_place_pressed_by_its_button_is_never_typed_into_the_search() -> None:
    # v8 ×2: the press on «Inicio» did not hold (Spotify behind Discord) and «inicio» was typed into the search.
    view = _view("f2_v8_tras_clic_sin_efecto")
    history = [_pressed("Inicio", ok=False)]
    goal = "ir a inicio"
    step = cu_rules.deterministic_step(goal=goal, view=view, history=history, application="Spotify",
                                 objective="en Spotify andá a Inicio", success_check="title:inicio")
    assert not cu_lookup._searches_content(step), step
    assert cu_lookup._find_step("inicio", view, history, navigate=True, objective="en Spotify andá a Inicio") is None
    decided = _decide(view, history, {"act": "type", "text": "inicio"}, goal=goal)
    # The model's typing is refused; with the place's address declared in the app's data (lugares por dirección) the
    # place is opened by it instead of giving up. Either way nothing is typed into the search.
    assert not cu_lookup._searches_content(decided), decided
    assert decided["operation"] == "none" or (
        decided["operation"] == "app.open" and decided["arguments"].get("place") == "home"), decided


@pytest.mark.parametrize(("view", "label", "goal"), [
    ("f2_u1_tras_clic_sin_efecto", "Abre Tu biblioteca", GOAL),
    ("f2_x7_tras_clic_sin_efecto", "Buscar", "ir a search"),
])
def test_f2_after_a_press_that_did_not_hold_nothing_is_typed(view: str, label: str, goal: str) -> None:
    step = _decide(_view(view), [_pressed(label, ok=False)], goal=goal)
    assert step["operation"] != "input.text.type" and not cu_lookup._searches_content(step), step


def test_f2_counter_case_a_channel_pressed_without_effect_is_still_looked_up() -> None:
    chat = {"window": {"title": "Amigos - Discord", "process": "Discord"}, "controls": [
        {"i": 0, "kind": "Button", "name": "Buscar o iniciar una conversación", "state": ""},
        {"i": 1, "kind": "ListItem", "name": "Cotele"},
    ], "text": {}}
    pressed = [{"step": 1, "operation": "input.visible.click", "label": "Cotele", "kind": "ListItem", "ok": False,
                "error": "visible_button_postread_unchanged", "effectUncertain": True}]
    assert not cu_lookup._pressed_place_button(pressed, "cotele", chat)
    step = cu_lookup._find_step("cotele", chat, pressed, navigate=True, objective="en Discord andá al canal Cotele")
    assert step is not None and cu_lookup._searches_content(step)


# ------------------------------------------------------------------ S2: fase 2 integrada (f3), v8 y c6


def _v8_home() -> dict:
    # The journal keeps the first 20 controls of a look; the list «Filtros de Inicio» was the look's index 62, as the
    # model's prompt of that same look listed it (cu-v3/estab/f3_sub_evidencia/v2-v8/model_calls.jsonl).
    view = _view("f3_v8_inicio")
    view["controls"].append({"i": 62, "kind": "List", "name": "Filtros de Inicio", "state": "", "zone": "T"})
    return view


def test_s2_v8_the_home_page_is_proved_by_what_only_it_shows() -> None:
    mission = missions.mission_request("en Spotify andá a Inicio", ("Spotify",))
    assert mission.success_check.startswith("control:==filtros de inicio|")
    # Counter-cases: another place of the same application, and an application without that datum.
    assert not missions.mission_request("en Spotify andá a search", ("Spotify",)).success_check.startswith("control:==")
    assert "filtros" not in missions.mission_request("en Steam andá a la biblioteca", ("Steam",)).success_check


def test_s2_c6_a_layer_that_holds_the_keyboard_is_closed_before_writing_again() -> None:
    view = _view("f3_c6_tras_escribir_sin_campo")
    refused = {"step": 2, "operation": "input.text.type", "text": "prueba BAXY C6", "ok": False,
               "error": "input_field_not_reachable"}
    history = [{"step": 1, "operation": "input.visible.click", "label": "Mensaje @Ron92", "ok": True}, refused]
    step = cu_rules.deterministic_step(goal="escribir prueba BAXY C6", view=view, history=history, application="Discord",
                                 objective='en Discord abrí el chat con Ron92, escribí "prueba BAXY C6" y mandalo')
    assert step is not None and step["operation"] == "input.key.press" and step["arguments"]["key"] == "escape"
    # Once: after that Escape, never another one.
    escaped = [*history, {"step": 3, "operation": "input.key.press", "key": "escape", "ok": True}, {**refused, "step": 4}]
    assert not cu_lookup._layer_holds_the_keyboard(view, escaped)
    # Counter-case: the same refusal with the keyboard on the window itself (no layer) presses nothing blind.
    plain = copy.deepcopy(view)
    plain["window"]["focused"] = {"kind": "Edit", "name": "Mensaje @Ron92"}
    assert not cu_lookup._layer_holds_the_keyboard(plain, history)
