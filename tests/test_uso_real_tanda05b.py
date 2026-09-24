"""Uso real tanda 5b (official window, 2026-09-24): «busca podcast y reprodúce lo» played a video titled
«… | ¿Seré Weón? 👀 - YouTube» and every final died in ⚠. The title's «?» was read as BAXY asking, the tab's
« - YouTube» was demanded as part of the name, and a draft that left the title's emoji out (the concision
prompt forbids emoji) no longer named it. The title's words are the name; its own punctuation is not BAXY's.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import llm

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
        "Estoy reproduciendo «Entrevista completa al capitán | ¿Seré el mejor? 👀».",
        "Estoy reproduciendo «Entrevista completa al capitán | ¿Seré el mejor?».",
        "Now playing “Entrevista completa al capitán | ¿Seré el mejor?”.",
    ],
)
def test_the_played_title_names_the_video_with_or_without_the_tab_suffix_and_emoji(draft):
    assert llm.compose_visible_defect(draft, "status", "busca podcast y reprodúcelo", _facts()) == ""


def test_another_title_is_still_not_the_one_playing():
    draft = "Estoy reproduciendo «Otra entrevista distinta»."
    assert llm.compose_visible_defect(draft, "status", "busca podcast y reprodúcelo", _facts()) == "missing_name"


def test_a_question_of_baxy_after_the_title_is_still_a_question():
    draft = "Estoy reproduciendo «Entrevista completa al capitán | ¿Seré el mejor?». ¿Quieres otro?"
    assert llm.compose_visible_defect(draft, "status", "busca podcast y reprodúcelo", _facts()) == "extra_claim"
