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
        ("user_browser_streaming_profile_choice", "does not choose a profile"),
        ("hbo_max_needs_default_browser", "only in the person's own web browser"),
        ("hbo_max_authentication_required", "HBO Max asks to sign in"),
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
