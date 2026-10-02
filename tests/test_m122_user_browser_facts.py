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
    ],
)
def test_user_browser_codes_have_their_fact(code: str, words: str) -> None:
    prose = llm._cause_in_prose(code, "es")

    assert words in prose
    assert "_" not in prose
