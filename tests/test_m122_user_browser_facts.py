"""M122 (owner 2026-10-02): what the person's own browser could not confirm is told as a fact, not as a code."""

from __future__ import annotations

import pytest

from baxy_mind import llm


@pytest.mark.parametrize(
    ("code", "words"),
    [
        (
            "user_browser_navigation_unconfirmed",
            "opened in the person's own web browser",
        ),
        (
            "user_browser_playback_unconfirmed",
            "could not be confirmed that it started playing",
        ),
        ("user_browser_streaming_playback_unconfirmed", "signed-in session"),
        ("user_browser_tabs_not_automatable", "nothing was done"),
        ("user_browser_not_running", "web browser is not open"),
        ("user_browser_page_unreadable", "could not be read right now"),
        ("user_browser_tab_step_unconfirmed", "not confirmed"),
        ("user_browser_tab_step_unavailable", "nothing was done"),
        ("user_browser_last_tab_kept", "would close the whole browser window"),
        ("user_browser_close_all_declined", "nothing was closed"),
        ("user_browser_fullscreen_control_missing", "no video full-screen control"),
    ],
)
def test_user_browser_codes_have_their_fact(code: str, words: str) -> None:
    prose = llm._cause_in_prose(code, "es")

    assert words in prose
    assert "_" not in prose


def test_a_page_summary_names_the_page_without_saying_title() -> None:
    """Owner's live check 2026-10-06: «léeme lo que dice la página» in Opera GX composed three right summaries and
    all died as missing_name, because the page's title was taken for a record's title."""

    import json

    observed = {
        "version": 1,
        "url": "gxcorner.games",
        "title": "GX Corner",
        "text": "GX DAILY\nEl presidente de PlatinumGames, Atsushi Inaba, ha expresado muchas ganas de ampliar la "
        "serie Bayonetta y expandir su mundo.",
        "truncated": True,
        "browser": "Opera GX",
        "authority": "user_browser_uia_page_text",
    }
    situation = {
        "kind": "operation",
        "operation": "browser.page.read",
        "polarity": "success",
        "verified": True,
        "succeeded": True,
        "observed": observed,
    }
    draft = (
        "En GX Corner se informa que el presidente de PlatinumGames, Atsushi Inaba, ha expresado muchas ganas de "
        "ampliar la serie Bayonetta y expandir su mundo."
    )

    assert llm.compose_visible_defect(
        draft, "status", "léeme lo que dice la página que tengo abierta", {"situation": json.dumps(situation)}
    ) == ""
    assert llm.compose_visible_defect(
        "La página dice que Bayonetta tendrá una película.",
        "status",
        "léeme lo que dice la página que tengo abierta",
        {"situation": json.dumps(situation)},
    ) != ""


def test_a_quoted_passage_may_join_two_lines_of_the_page() -> None:
    seen = {
        "title": "GX Corner",
        "site": "",
        "lead": "GX DAILY\nEl jefe de PlatinumGames insinúa ampliar la serie Bayonetta\n"
        "El presidente de PlatinumGames ha expresado muchas ganas de ampliar la serie.",
        "moreNotShown": True,
    }
    payload = {"operation": "browser.page.read", "seen": seen}
    joined = (
        'La página dice: "El jefe de PlatinumGames insinúa ampliar la serie Bayonetta. El presidente de '
        'PlatinumGames ha expresado muchas ganas de ampliar la serie."'
    )
    invented = 'La página dice: "El jefe de PlatinumGames anunció una película de Bayonetta."'

    assert llm._payload_fact_defect(joined, payload, "léeme la página") == ""
    assert llm._payload_fact_defect(invented, payload, "léeme la página") == "page_unquoted_passage"


def test_when_every_draft_fails_the_page_is_told_by_its_first_sentence() -> None:
    seen = {
        "title": "GX Corner",
        "lead": "GX CORNER\nRegalos\nAgregador de ofertas New content in section\n"
        "El presidente de PlatinumGames ha expresado muchas ganas de ampliar la serie Bayonetta.",
    }

    final = llm._page_read_final(seen, english=False)

    assert final == (
        "Leí la página «GX Corner». Dice: «El presidente de PlatinumGames ha expresado muchas ganas de ampliar "
        "la serie Bayonetta»."
    )
    assert llm._payload_fact_defect(final, {"operation": "browser.page.read", "seen": seen}, "léeme la página") == ""


_FIVE_TABS = {
    "version": 1,
    "count": 5,
    "truncated": False,
    "tabs": [
        {"title": "Recibidos (9) - persona@example.com - Gmail", "active": False},
        {"title": "Rick Astley - Never Gonna Give You Up (Official Video) - YouTube", "active": True},
        {"title": "Wikipedia, la enciclopedia libre", "active": False},
        {"title": "Despacito - YouTube", "active": False},
        {"title": "GX Corner", "active": False},
    ],
    "browser": "Opera GX",
    "authority": "user_browser_uia_tab_strip",
}


def _tabs_payload() -> dict:
    situation = {
        "kind": "operation",
        "operation": "browser.tabs.list",
        "polarity": "success",
        "verified": True,
        "succeeded": True,
        "observed": _FIVE_TABS,
    }
    return llm._compose_situation_payload(situation, "es", "cuántas pestañas tengo abiertas")


def test_the_tab_listing_gives_the_model_the_figures_counted_by_the_code() -> None:
    """Owner's live check 2026-10-06: five tabs, two of them YouTube videos, told as «tres videos de YouTube»."""

    seen = _tabs_payload()["seen"]

    assert seen["tabCount"] == 5
    assert seen["titles"][3] == "Despacito - YouTube"
    assert seen["activeTab"].startswith("Rick Astley")
    assert seen["tabsPerSite"] == {"YouTube": 2}
    assert "authority" not in seen


@pytest.mark.parametrize(
    ("reply", "defect"),
    [
        ("Tienes cinco pestañas abiertas en Opera GX, entre ellas tres videos de YouTube.", "invented_number"),
        ("Tienes 4 pestañas abiertas.", "invented_number"),
        ("Tienes 5 pestañas abiertas, una de Gmail y 3 de YouTube.", "invented_number"),
        (
            "Tienes 5 pestañas abiertas: Gmail, dos videos de YouTube (Never Gonna Give You Up y Despacito), "
            "Wikipedia y GX Corner.",
            "",
        ),
        ("Tienes cinco pestañas abiertas; dos son de YouTube y tres de otros sitios.", ""),
        ("Tienes 5 pestañas, entre ellas «Recibidos (9) - persona@example.com - Gmail».", ""),
    ],
)
def test_a_count_the_tab_strip_did_not_give_is_rejected(reply: str, defect: str) -> None:
    assert llm._payload_fact_defect(reply, _tabs_payload(), "cuántas pestañas tengo abiertas") == defect


def test_when_every_draft_fails_the_tabs_are_told_as_read() -> None:
    payload = _tabs_payload()
    situation = {"operation": "browser.tabs.list", "verified": True, "succeeded": True}

    final = llm._told_result_final(situation, payload, "cuántas pestañas tengo abiertas", "es")

    assert final.startswith("Tienes 5 pestañas abiertas en Opera GX: «Recibidos (9)")
    assert final.endswith("y «GX Corner».")
    assert llm._payload_fact_defect(final, payload, "cuántas pestañas tengo abiertas") == ""


def test_a_tab_step_tells_the_tab_that_closed_and_the_one_now_in_front() -> None:
    situation = {
        "kind": "operation",
        "operation": "browser.control",
        "polarity": "success",
        "verified": True,
        "succeeded": True,
        "observed": {
            "version": 1,
            "action": "close",
            "observedState": "tab_closed",
            "browser": "Opera GX",
            "tabCount": 4,
            "activeTab": "Despacito - YouTube",
            "closedTab": "Example Domain",
            "authority": "user_browser_uia_frame_postread",
        },
    }

    seen = llm._compose_situation_payload(situation, "es", "cierra esta pestaña")["seen"]

    assert seen == {
        "action": "close",
        "observedState": "tab_closed",
        "closedTab": "Example Domain",
        "activeTab": "Despacito - YouTube",
    }


@pytest.mark.parametrize(
    ("text", "action"),
    [
        ("cierra esta pestaña", "close"),
        ("Cierra la pestaña, por favor", "close"),
        ("close this tab", "close"),
        ("cierra la pestaña de YouTube", None),
        ("no cierres esta pestaña", None),
        ("cierra todas las pestañas", None),
    ],
)
def test_the_tab_in_front_is_closed_and_a_named_tab_stays_a_limit(text: str, action: str | None) -> None:
    """Owner 2026-10-06: «cierra esta pestaña» acts on the person's browser; a tab named by its site still has no
    operation (choosing a tab is not in the catalog) and stays a plain limit."""

    import json
    from pathlib import Path

    from baxy_mind.semantic import patterns
    from baxy_mind.semantic.web import browser_close_tab_arguments

    catalog = Path(__file__).resolve().parents[1] / "src" / "baxy_mind" / "data" / "decider_catalog.es.v1.json"
    operations = list(json.loads(catalog.read_text(encoding="utf-8")))
    arguments = browser_close_tab_arguments(text)

    assert (arguments or {}).get("action") == action
    if action == "close":
        assert not patterns.known_unsupported_effect_request(text, operations)
    if text == "cierra la pestaña de YouTube":
        assert patterns.known_unsupported_effect_request(text, operations)
