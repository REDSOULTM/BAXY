"""Regresiones r2 M3 (live v8): en una misión «ir a X» el modelo no escribe X en un buscador cuando el check no es de
búsqueda (el nombre tecleado en el buscador de un reproductor no lleva a ningún lugar y queda en pantalla)."""

from __future__ import annotations

from baxy_mind import computer_use
from baxy_mind import cu_goals
from baxy_mind import cu_validate

APPS = ("Reproductor",)

VIEW = {
    "window": {"title": "Reproductor", "process": "player", "focused": {"kind": "Edit", "name": "Buscar", "value": ""}},
    "controls": [
        {"i": 0, "kind": "Button", "name": "Inicio", "state": ""},
        {"i": 1, "kind": "Edit", "name": "Buscar", "state": "focused", "value": ""},
        {"i": 2, "kind": "Button", "name": "Tu biblioteca", "state": ""},
    ],
}


def _typed(text: str) -> dict:
    return {"act": "type", "i": -1, "label": "", "text": text, "key": "", "direction": "", "application": "", "evidence": "",
            "why": "lo busco"}


def _decide(text: str, goal: str, check: str | None) -> dict:
    return cu_validate.validate_decision(
        _typed(text), view=VIEW, last_failed=None, application_names=APPS, goal=goal, success_check=check,
    )


def test_the_model_never_types_the_place_it_goes_to_unless_the_check_is_a_search() -> None:
    refused = _decide("inicio", "ir a inicio", "control:inicio:current|title:inicio")
    assert refused["operation"] == "none" and refused["code"] == "types_the_place"
    assert "types_the_place" in computer_use._RETRIED  # the model gets one more try, with the refusal in front
    # With the article or the possessive said, the same place.
    assert _decide("Tu biblioteca", "ir a tu biblioteca", "title:biblioteca")["code"] == "types_the_place"
    assert _decide("«Inicio»", "ir a el inicio", None)["code"] == "types_the_place"


def test_typing_stays_allowed_for_a_search_check_another_text_or_another_goal() -> None:
    # Contracase: a check a search proves (a step done and the title or a text it shows).
    searched = _decide("inicio", "ir a inicio", "stepdone:input.text.type&text:inicio")
    assert searched["operation"] == "input.text.type"
    # Contracase: a text that is not the place (a song the person named) is no side effect of going there.
    other = _decide("bohemian rhapsody", "ir a inicio", "title:inicio")
    assert other["operation"] == "input.text.type"
    # Contracase: a search goal types its name.
    search = _decide("inicio", "buscar inicio", "title:inicio")
    assert search["operation"] == "input.text.type"


def test_a_search_check_reads_like_the_apps() -> None:
    assert cu_goals.check_searches("stepdone:input.text.type&title:hades")
    assert cu_goals.check_searches("control:x:current|stepdone:input.key.press&text:resultados")
    assert not cu_goals.check_searches("stepdone:input.text.type")
    assert not cu_goals.check_searches("title:hades|text:hades")
    assert not cu_goals.check_searches(None)


BROWSER = {
    "window": {
        "title": "Google - Opera",
        "process": "browser",
        "focused": {"kind": "Edit", "name": "Barra de direcciones y de búsqueda", "value": "google.com"},
    },
    "controls": [
        {"i": 0, "kind": "Edit", "name": "Barra de direcciones y de búsqueda", "state": "focused", "value": "google.com"},
        {"i": 1, "kind": "Button", "name": "Atrás", "state": ""},
        {"i": 2, "kind": "Hyperlink", "name": "Gmail", "state": ""},
        {"i": 3, "kind": "Edit", "name": "Buscar", "state": "", "value": ""},
    ],
}


def test_a_site_name_in_the_address_bar_holding_a_page_is_never_refused() -> None:
    # Review r4: «ir a wikipedia» on a browser tab already used (its address bar focused, holding google.com) has no
    # control that leads there: typing the site's name in the address bar is the way, never «types_the_place».
    decided = cu_validate.validate_decision(
        _typed("wikipedia"), view=BROWSER, last_failed=None, application_names=("Opera",), goal="ir a wikipedia",
        success_check="title:wikipedia",
    )
    assert decided["operation"] == "input.text.type"


def test_the_place_is_refused_only_when_a_control_on_screen_leads_there() -> None:
    # Contracase of the refusal: a search field with the keyboard and no control named as the place on screen.
    view = {
        "window": {"title": "Reproductor", "process": "player", "focused": {"kind": "Edit", "name": "Buscar", "value": ""}},
        "controls": [
            {"i": 0, "kind": "Edit", "name": "Buscar", "state": "focused", "value": ""},
            {"i": 1, "kind": "Button", "name": "Tu biblioteca", "state": ""},
        ],
    }
    decided = cu_validate.validate_decision(
        _typed("podcasts"), view=view, last_failed=None, application_names=APPS, goal="ir a podcasts",
        success_check="title:podcasts",
    )
    assert decided["operation"] == "input.text.type"
    # The same place named by a control on screen: the click is the way, the typing is refused.
    view["controls"].append({"i": 2, "kind": "Button", "name": "Podcasts", "state": ""})
    refused = cu_validate.validate_decision(
        _typed("podcasts"), view=view, last_failed=None, application_names=APPS, goal="ir a podcasts",
        success_check="title:podcasts",
    )
    assert refused["code"] == "types_the_place"
