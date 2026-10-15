"""Uso real tanda 5b (official window, 2026-09-24): «busca podcast y reprodúce lo» played a video titled
«… | ¿Seré Weón? 👀 - YouTube» and every final died in ⚠. The title's «?» was read as BAXY asking, the tab's
« - YouTube» was demanded as part of the name, and a draft that left the title's emoji out (the concision
prompt forbids emoji) no longer named it. The title's words are the name; its own punctuation is not BAXY's.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import visible_defect

TITLE = "Entrevista completa al capitán | ¿Seré el mejor? 👀 - YouTube"


def _facts(title: str = TITLE) -> dict:
    situation = {
        "kind": "operation", "operation": "media.play.youtube", "polarity": "success", "verified": True,
        "succeeded": True,
        "observed": {"version": 1, "provider": "youtube", "query": "podcast", "title": title,
                     "playbackStatus": "playing"},
    }
    return {"situation": json.dumps(situation, ensure_ascii=False)}


@pytest.mark.parametrize(
    "draft",
    [
        "Está reproduciéndose «Entrevista completa al capitán | ¿Seré el mejor? 👀 - YouTube».",
        "Estoy reproduciendo «Entrevista completa al capitán | ¿Seré el mejor? 👀» en YouTube.",
        "Estoy reproduciendo «Entrevista completa al capitán | ¿Seré el mejor?» en YouTube.",
        "Está sonando “Entrevista completa al capitán | ¿Seré el mejor?” en YouTube.",
    ],
)
def test_the_played_title_names_the_video_with_or_without_the_tab_suffix_and_emoji(draft):
    # Uso real v3 tanda 1 (t1-c01): what was put on names the service it plays in, so the drafts that left the tab
    # suffix out say «en YouTube» beside the title (a draft without the service is missing_place now); the curly-quoted
    # draft is said in the request's Spanish, since «on YouTube» now tells its English apart.
    assert visible_defect.compose_visible_defect(draft, "status", "busca podcast y reprodúcelo", _facts()) == ""


def test_another_title_is_still_not_the_one_playing():
    draft = "Estoy reproduciendo «Otra entrevista distinta»."
    assert visible_defect.compose_visible_defect(draft, "status", "busca podcast y reprodúcelo", _facts()) == "missing_name"


def test_a_question_of_baxy_after_the_title_is_still_a_question():
    draft = "Estoy reproduciendo «Entrevista completa al capitán | ¿Seré el mejor?». ¿Quieres otro?"
    assert visible_defect.compose_visible_defect(draft, "status", "busca podcast y reprodúcelo", _facts()) == "extra_claim"
