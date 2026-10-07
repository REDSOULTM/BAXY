"""«en Spotify andá a search» (live x7, 2026-10-07): the search as a place, said in either language, is reached when its
field takes the keyboard after this mission's own click or find key; a read-only address field that merely carries the
word is never the place, and a click that failed is not tried again in the same sub-goal."""

from __future__ import annotations

from baxy_mind import computer_use
from baxy_mind.semantic import missions


def _arguments(text: str) -> dict:
    return missions.mission_request(text, ["Spotify"]).arguments()


def test_the_search_as_a_place_is_read_in_either_language_with_the_focus_atom() -> None:
    for said in ("en Spotify andá a search", "en Spotify ve a la búsqueda", "in Spotify go to search", "en Spotify andá a buscar"):
        check = _arguments(said)["successCheck"]
        assert "focus:search" in check.split("|"), said
        assert "control:buscar:current" in check and "control:search:current" in check, said
        assert len(check.encode("utf-8")) <= 512


def test_another_place_carries_no_focus_atom() -> None:
    check = _arguments("en Spotify andá a la biblioteca")["successCheck"]
    assert "focus:" not in check


def test_busqueda_names_the_search_in_the_other_language() -> None:
    assert set(missions.label_alternatives("busqueda")) == {"buscar", "search"}
    assert "busqueda" in missions.label_alternatives("search")


# Spotify's web player as the App read it at x7 (trimmed): the frame's read-only address field holds the word «search».
VIEW = {
    "window": {"title": "Spotify Premium", "process": "Spotify",
               "focused": {"kind": "Document", "name": "Spotify", "value": "https://xpui.app.spotify.com/index.html"}},
    "controls": [
        {"i": 0, "kind": "Edit", "name": "Address and search bar", "state": "readonly",
         "value": "xpui.app.spotify.com/index.html"},
        {"i": 1, "kind": "Document", "name": "Spotify", "state": "readonly focused"},
        {"i": 2, "kind": "Button", "name": "Inicio", "state": ""},
        {"i": 3, "kind": "Button", "name": "Buscar", "state": ""},
        {"i": 4, "kind": "ComboBox", "name": "¿Qué quieres reproducir?", "state": "collapsed"},
        {"i": 5, "kind": "Button", "name": "Explorar", "state": ""},
    ],
}


def test_going_to_search_never_clicks_a_read_only_address_field() -> None:
    step = computer_use.deterministic_step(goal="ir a search", view=VIEW, history=[], application="Spotify")
    assert step is not None and step["operation"] == "input.visible.click"
    assert step["arguments"]["label"] == "Buscar"


def test_a_label_whose_click_failed_is_not_clicked_again_after_other_steps() -> None:
    history = [
        {"step": 1, "operation": "input.visible.click", "ok": False, "label": "Buscar", "index": 3},
        {"step": 2, "operation": "input.key.press", "ok": True, "key": "ctrl_f"},
    ]
    step = computer_use.deterministic_step(goal="ir a search", view=VIEW, history=history, application="Spotify")
    assert step is None or step.get("arguments", {}).get("label") != "Buscar"
