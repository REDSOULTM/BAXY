"""M140 (2026-10-03, DEV-G v4o G-s099 «skip esta cancion, esta horible»): the song a media control observed is not a
failure told. Recorded payload (window/v4o-devG/compose-audit.jsonl, trace t99): «Está sonando MC Hammer - U Can't Touch
This.» died three times as asserted_failure for the «Can't» of the title."""

from __future__ import annotations

import json

from baxy_mind.llm import compose_visible_defect

OBSERVED = {"version": 1, "sourceAppUserModelId": "SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify",
            "title": "U Can't Touch This", "artist": "MC Hammer", "playbackStatus": "playing", "authority": "windows_smtc"}


def _facts(operation: str) -> dict:
    situation = {"kind": "operation", "operation": operation, "polarity": "success", "verified": True,
                 "succeeded": True, "observed": OBSERVED}
    return {"situation": json.dumps(situation)}


def test_g_s099_the_song_a_control_observed_is_no_failure() -> None:
    draft = "Está sonando MC Hammer - U Can't Touch This."
    assert compose_visible_defect(draft, "status", "skip esta cancion, esta horible", _facts("media.control")) != (
        "asserted_failure"
    )
    assert compose_visible_defect("Now playing U Can't Touch This by MC Hammer.", "status", "what's playing",
                                  _facts("media.status")) != "asserted_failure"


def test_a_failure_told_outside_the_title_still_counts() -> None:
    draft = "No pude pasar a la siguiente canción; sigue sonando U Can't Touch This."
    assert compose_visible_defect(draft, "status", "skip esta cancion", _facts("media.control")) == "asserted_failure"
