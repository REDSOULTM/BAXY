"""M172 (2026-10-05, App runs v4x/v4y/v5b): a song whose title carries the recording's suffix left the turn without a reply.

DEV-I I-s047 «oye ponme algo de Mon Laferte en el spotify, lo que sea» played «Mon Laferte - Mi Buen Amor - Desde El
Teatro Fru Fru». The mind refused «He iniciado la reproducción de "Mi Buen Amor" de Mon Laferte en Spotify.» as
missing_name (every part of the title was owed, the venue suffix too); the retry quoted the whole title and the App
refused it as internal_code («Fru Fru» read as a stutter), and the turn ended in ⚠. DEV-I I-s049 «what's this song
called?» over the same song died the same way in the mind: twice missing_name and once invented («Fru Fru»). DEV-G
G-w14-t1 (v4x, v5b) lived I-s047 again.

A later part of the title that only says which recording it is («Desde El Teatro…», «En Vivo», «Live at…», «2011
Remaster», «Radio Edit») is not a name the reply owes; a word the verified result observed repeated is data; and
starting the playback the result verified says its playing state. Rows are quoted with their real text; every other
phrasing is our own.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import llm


def _situation(operation: str, observed: dict) -> dict:
    return {"situation": json.dumps({
        "kind": "operation", "operation": operation, "polarity": "success", "verified": True, "succeeded": True,
        "observed": {"version": 1, **observed},
    }, ensure_ascii=False)}


FRU_FRU_PLAYED = _situation("media.play.query", {
    "provider": "spotify", "title": "Mon Laferte - Mi Buen Amor - Desde El Teatro Fru Fru", "query": "Mon Laferte",
    "playbackStatus": "playing", "authority": "spotify_windows_uia_postread",
})
FRU_FRU_STATUS = _situation("media.status", {
    "sourceAppUserModelId": "SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify",
    "title": "Mi Buen Amor - Desde El Teatro Fru Fru", "artist": "Mon Laferte",
    "album": "Mi Buen Amor (Desde El Teatro Fru Fru)", "playbackStatus": "playing",
    "authority": "windows_smtc_current_session_read",
})
I_S047 = "oye ponme algo de Mon Laferte en el spotify, lo que sea"
I_S049 = "what's this song called?"


def _played(title: str) -> dict:
    return _situation("media.play.query", {
        "provider": "spotify", "title": title, "query": "algo", "playbackStatus": "playing",
        "authority": "spotify_windows_uia_postread",
    })


def _status(title: str, artist: str) -> dict:
    return _situation("media.status", {
        "sourceAppUserModelId": "SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify", "title": title, "artist": artist,
        "playbackStatus": "playing", "authority": "windows_smtc_current_session_read",
    })


@pytest.mark.parametrize(("facts", "request_text", "draft"), [
    # I-s047 (v5b first draft, missing_name; then the retry the App refused).
    (FRU_FRU_PLAYED, I_S047, 'He iniciado la reproducción de "Mi Buen Amor" de Mon Laferte en Spotify.'),
    (FRU_FRU_PLAYED, I_S047,
     "Ahora se está reproduciendo la canción «Mon Laferte - Mi Buen Amor - Desde El Teatro Fru Fru» en Spotify."),
    # G-w14-t1 (v4x, v5b first draft, missing_name).
    (FRU_FRU_PLAYED, I_S047, 'He puesto "Mi Buen Amor" de Mon Laferte en Spotify y ya está sonando.'),
    # I-s049 (v5b: first and retry missing_name, third invented).
    (FRU_FRU_STATUS, I_S049, 'The song is "Mi Buen Amor" by Mon Laferte, and it is currently playing.'),
    (FRU_FRU_STATUS, I_S049, 'The song playing is "Mi Buen Amor" by Mon Laferte.'),
    (FRU_FRU_STATUS, I_S049,
     'The song is called "Mi Buen Amor - Desde El Teatro Fru Fru" and it is performed by Mon Laferte.'),
    # Our own: other suffixes, the other language, the suffix said in other words.
    (_played("Queen - Bohemian Rhapsody - Live At Wembley Stadium"), "pon algo de queen",
     "Está sonando «Bohemian Rhapsody» de Queen en Spotify."),
    (_played("Soda Stereo - Persiana Americana - En Vivo"), "ponme soda stereo",
     "Ya suena «Persiana Americana» de Soda Stereo, la versión en vivo."),
    (_played("The Killers - Mr. Brightside - Radio Edit"), "play the killers on spotify",
     'Now playing "Mr. Brightside" by The Killers on Spotify.'),
    (_status("Hotel California - 2013 Remaster", "Eagles"), "qué canción es esta",
     "Es «Hotel California» de Eagles y está sonando."),
    (_status("Bora Bora - Versión Acústica", "Los Twist"), "cómo se llama esta",
     "Está sonando «Bora Bora - Versión Acústica» de Los Twist."),
    (_played("Mon Laferte - Mi Buen Amor"), I_S047, "Inicié la reproducción de «Mi Buen Amor» de Mon Laferte."),
])
def test_the_song_named_without_its_recording_suffix_is_named(facts: dict, request_text: str, draft: str) -> None:
    assert llm.compose_visible_defect(draft, "status", request_text, facts, said=request_text) == ""


@pytest.mark.parametrize(("facts", "request_text", "draft", "reason"), [
    # Another song, another artist, or only the artist: not the song played.
    (FRU_FRU_PLAYED, I_S047, "Está sonando «Tu Falta de Querer» de Mon Laferte en Spotify.", "missing_name"),
    (FRU_FRU_STATUS, I_S049, 'The song is "Mi Buen Amor" by Natalia Lafourcade.', "missing_name"),
    (FRU_FRU_PLAYED, I_S047, "Está sonando Mon Laferte en Spotify.", "missing_name"),
    # A later part that could be a title of its own is still owed («Live Forever» is the song).
    (_played("Oasis - Live Forever"), "pon oasis", "Está sonando Oasis en Spotify.", "missing_name"),
    (_played("Los Prisioneros - Desde Que Te Fuiste"), "pon los prisioneros",
     "Está sonando Los Prisioneros en Spotify.", "missing_name"),
    # A stutter of the writer's own, with or without an observed repetition elsewhere.
    (FRU_FRU_STATUS, I_S049, 'The the song is "Mi Buen Amor" by Mon Laferte.', "invented"),
    (_status("Mi Buen Amor", "Mon Laferte"), I_S049,
     'The song is "Mi Buen Amor - Desde El Teatro Fru Fru" by Mon Laferte.', "invented"),
    # Starting the playback is the playing state; told as not started over a verified playback it is reversed.
    (FRU_FRU_PLAYED, I_S047, 'No he iniciado la reproducción de "Mi Buen Amor" de Mon Laferte.', "reversed_result"),
])
def test_another_song_or_a_stutter_is_still_refused(facts: dict, request_text: str, draft: str, reason: str) -> None:
    assert llm.compose_visible_defect(draft, "status", request_text, facts, said=request_text) == reason


def test_a_suffix_is_never_owed_from_the_first_part_and_parts_stay_owed() -> None:
    assert llm._media_title_names("Mon Laferte - Mi Buen Amor - Desde El Teatro Fru Fru", owed_only=True) == [
        "Mon Laferte", "Mi Buen Amor",
    ]
    # Without ``owed_only`` (the masks) every part is still a name.
    assert "Desde El Teatro Fru Fru" in llm._media_title_names("Mon Laferte - Mi Buen Amor - Desde El Teatro Fru Fru")
    assert llm._media_title_names("En Vivo - Soda Stereo", owed_only=True) == ["En Vivo", "Soda Stereo"]
