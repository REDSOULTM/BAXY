"""Revisión 1 r24u (bloqueante 1): a Spotify play whose receipt says what plays was not shown to be the query
(``matchesQuery`` false) is never told as the request done.

t2-c01 «pone los bunkers en spotify pa estudiar» played «Fother Muckers - Nada en este Mundo»; the receipt now says
matchesQuery=false, and the mind reads it (semantic.claims.unmatched_play): the final says what plays and, beside it,
that it was not checked to be the query; a draft that does not say so is refused. Contracasos: a receipt with
matchesQuery true or without the field is told as before, and a descriptive query («musica para concentrarse») whose
result shares no word with it is still told as playing — never as a failure, never as «no puse».
"""

from __future__ import annotations

import json

from baxy_mind import compose_payload
from baxy_mind import deterministic_finals
from baxy_mind import visible_defect
from baxy_mind.semantic import claims


T2_C01 = "pone los bunkers en spotify pa estudiar"


def _observed(title: str, query: str, matches: object = "absent") -> dict:
    observed = {
        "version": 1, "provider": "spotify", "title": title, "query": query, "playbackStatus": "playing",
        "processId": 42, "authority": "spotify_windows_uia_postread",
    }
    if matches != "absent":
        observed["matchesQuery"] = matches
    return observed


def _situation(observed: dict) -> dict:
    return {
        "kind": "operation", "operation": "media.play.query", "polarity": "success", "verified": True,
        "succeeded": True, "observed": observed,
    }


def _facts(observed: dict) -> dict:
    return {"situation": json.dumps(_situation(observed), ensure_ascii=False)}


def _final(observed: dict, said: str, language: str = "es") -> str:
    situation = _situation(observed)
    payload = compose_payload._compose_situation_payload(situation, language, said)
    return deterministic_finals._told_result_final(situation, payload, said, language)


FOTHER = _observed("Fother Muckers - Nada en este Mundo", "los bunkers", False)


def test_the_reader_lives_in_semantic_and_reads_only_a_false_match() -> None:
    assert claims.unmatched_play("media.play.query", FOTHER) == "los bunkers"
    assert claims.unmatched_play("media.play.query", _observed("Los Bunkers - Llueve", "los bunkers", True)) == ""
    assert claims.unmatched_play("media.play.query", _observed("x", "los bunkers")) == ""
    # The exact mode never carries the field: nothing to read.
    assert claims.unmatched_play("media.play.exact", FOTHER) == ""


def test_t2_c01_final_says_what_plays_and_that_it_was_not_checked_to_be_the_query() -> None:
    final = _final(FOTHER, T2_C01)
    assert final == "Está sonando «Fother Muckers - Nada en este Mundo» en Spotify; no comprobé que sea «los bunkers»."
    assert not visible_defect.compose_visible_defect(final, "status", T2_C01, _facts(FOTHER), said=T2_C01)


def test_t2_c01_english_final() -> None:
    final = _final(FOTHER, "put los bunkers on spotify", "en")
    assert final == "Now playing «Fother Muckers - Nada en este Mundo» on Spotify; I didn't check that it is «los bunkers»."


def test_a_draft_telling_the_query_as_done_over_an_unmatched_play_is_refused() -> None:
    for draft in (
        "Puse Los Bunkers en Spotify; está sonando «Fother Muckers - Nada en este Mundo».",
        "Listo, ya está sonando «Fother Muckers - Nada en este Mundo» en Spotify para estudiar.",
        "Now playing «Fother Muckers - Nada en este Mundo» on Spotify.",
    ):
        assert visible_defect.compose_visible_defect(draft, "status", T2_C01, _facts(FOTHER), said=T2_C01) == "unmatched_play"
    # The result's own sentence says it, so no draft is asked again.
    assert claims.template_suffices("unmatched_play", "media.play.query")


def test_contracase_a_matching_play_is_told_as_before() -> None:
    matched = _observed("Los Bunkers - Llueve sobre la ciudad", "los bunkers", True)
    assert _final(matched, T2_C01) == "Está sonando «Los Bunkers - Llueve sobre la ciudad» en Spotify."
    draft = "Puse «Los Bunkers - Llueve sobre la ciudad» en Spotify."
    assert visible_defect.compose_visible_defect(draft, "status", T2_C01, _facts(matched), said=T2_C01) != "unmatched_play"


def test_contracase_a_receipt_without_the_fact_is_told_as_before() -> None:
    older = _observed("Mon Laferte - Mi Buen Amor", "mon laferte")
    assert _final(older, "pon mon laferte en spotify") == "Está sonando «Mon Laferte - Mi Buen Amor» en Spotify."
    draft = "Está sonando «Mon Laferte - Mi Buen Amor» en Spotify."
    assert visible_defect.compose_visible_defect(draft, "status", "pon mon laferte", _facts(older), said="pon mon laferte") == ""


def test_contracase_a_descriptive_query_that_shares_no_word_is_still_playing_never_a_failure() -> None:
    # «musica para concentrarse» answered by «Deep Focus»: it may fit with no word in common. What plays is said as
    # playing, with the unchecked fact beside it; never «No puse…», never a failure.
    said = "pon musica para concentrarse en spotify"
    focus = _observed("Deep Focus", "musica para concentrarse", False)
    final = _final(focus, said)
    assert final.startswith("Está sonando «Deep Focus» en Spotify")
    assert not final.lower().startswith("no ")
    assert "no pude" not in final.lower()
    assert _situation(focus)["succeeded"] is True
    assert not visible_defect.compose_visible_defect(final, "status", said, _facts(focus), said=said)


def test_the_unmatched_wording_is_data() -> None:
    import inspect

    source = inspect.getsource(deterministic_finals._told_result_final)
    assert "no comprobé" not in source and "didn't check" not in source
    rule = claims.data()["unmatchedPlay"]
    assert "no comprobé" in rule["es"] and "didn't check" in rule["en"]
