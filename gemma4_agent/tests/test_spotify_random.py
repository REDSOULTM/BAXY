"""Spotify random playback: 'pon una cancion' sin titulo NO busca la palabra
literal, sino que reproduce algo aleatorio.

Contrato:
  - con username -> Liked Songs en shuffle (deeplink spotify:user:<u>:collection)
  - sin username -> reproducir DENTRO de Spotify (UIA sobre la vista actual,
    deeplink pelado spotify:). NUNCA la media key global: VK_MEDIA_PLAY_PAUSE
    va a la ultima sesion SMTC del SISTEMA (MEDIDO 2026-06-12: reanudaba un
    video de YouTube pausado en el navegador y reportaba "en Spotify").

Bug original (trace #847): query="cancion" -> spotify:search:cancion ->
post_play_title="Spotify Premium", query_match=False (no sono nada util).
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ..domain_tools import (
    _is_generic_music_query,
    _media_play_streaming,
    _set_streaming_preference,
)
from ..memory_pkg.state import AgentState


def _fresh_state() -> AgentState:
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    p = Path(tmp.name)
    p.unlink(missing_ok=True)
    return AgentState(path=p)


def _spotify_exec(name, args):
    """Executor que finge la ventana de Spotify enfocada con un track sonando."""
    if name == "window":
        if args.get("action") == "active":
            # Title real de Spotify reproduciendo: "Spotify - Track • Artist".
            # El "•" => un track esta sonando (no la marca pelada).
            return {"ok": True, "active": {"title": "Spotify - Liked Song • Some Artist"}}
        return {"ok": True}
    if name == "audio":
        return {"ok": True}
    if name == "gui":
        return {"ok": True}
    return {"ok": True}


class TestGenericQueryDetector(unittest.TestCase):
    def test_generic_phrases_multilang(self):
        for q in ["una cancion", "una canción", "musica", "música",
                   "pon música", "algo", "algo de musica", "cualquier cancion",
                   "a song", "play something", "random", "uma musica",
                   "une chanson", "", "   "]:
            self.assertTrue(_is_generic_music_query(q), f"{q!r} debe ser genérica")

    def test_real_titles_not_generic(self):
        for q in ["Benson Boone", "Stranger Things", "Bohemian Rhapsody",
                   "Bad Bunny", "Loki", "la cancion de moana titi me pregunto"]:
            self.assertFalse(_is_generic_music_query(q), f"{q!r} NO es genérica")


class TestSpotifyRandomNoUsername(unittest.TestCase):
    def test_in_app_play_when_no_username(self):
        # Sin username: reproducir DENTRO de Spotify (UIA en la vista actual),
        # nunca la media key global (reanudaba media de OTRA app).
        state = _fresh_state()
        uia = _mock_uia_run({"ok": True, "chosen": "Reproducir Daily Mix 1",
                              "matched_query": False,
                              "title_before": "Spotify Premium",
                              "title_after": "Some Track - Some Artist"})
        with patch("time.sleep"), \
             patch("gemma4_agent.domain_tools.os.name", "nt"), \
             patch("gemma4_agent.domain_tools.os.unlink"), \
             patch("gemma4_agent.domain_tools.subprocess.run", uia), \
             patch("gemma4_agent.domain_tools.subprocess.Popen") as popen:
            r = _media_play_streaming(
                "spotify", "una cancion", {"action": "play"},
                executor=_spotify_exec, state=state,
            )
        self.assertTrue(r.get("random_playback"))
        self.assertEqual(r.get("random_mode"), "in_app_play")
        self.assertTrue(r.get("played"))
        self.assertTrue(r.get("verified"))
        # Abrió Spotify (deeplink pelado), NO buscó la palabra "cancion".
        launched = " ".join(str(c) for c in popen.call_args_list)
        self.assertIn("spotify:", launched)
        self.assertNotIn("search:cancion", str(r))

    def test_no_username_uia_fails_reports_honest(self):
        # Si la vista no tiene nada reproducible -> played=False honesto + hint.
        state = _fresh_state()
        uia = _mock_uia_run({"ok": False, "error": "no play button"})
        with patch("time.sleep"), \
             patch("gemma4_agent.domain_tools.os.name", "nt"), \
             patch("gemma4_agent.domain_tools.os.unlink"), \
             patch("gemma4_agent.domain_tools.subprocess.run", uia), \
             patch("gemma4_agent.domain_tools.subprocess.Popen"):
            r = _media_play_streaming(
                "spotify", "una cancion", {"action": "play"},
                executor=_spotify_exec, state=state,
            )
        self.assertFalse(r.get("played"))
        self.assertFalse(r.get("verified"))
        self.assertIn("usuario de Spotify", str(r.get("note") or ""))


def _mock_uia_run(payload):
    """Simula subprocess.run del script UIA con un JSON de salida."""
    import json as _json
    completed = MagicMock()
    completed.stdout = _json.dumps(payload)
    completed.stderr = ""
    return MagicMock(return_value=completed)


class TestSpotifyRandomWithUsername(unittest.TestCase):
    def test_liked_songs_when_username_known(self):
        state = _fresh_state()
        _set_streaming_preference(state, "spotify_user", "ema123")
        # El UIA play (liked songs) corre PowerShell -> mockear que reproduce.
        uia = _mock_uia_run({"ok": True, "chosen": "Reproducir Tus Me Gusta",
                              "matched_query": False, "title_before": "Spotify",
                              "title_after": "Liked Track - Some Artist"})
        with patch("time.sleep"), \
             patch("gemma4_agent.domain_tools.os.name", "nt"), \
             patch("gemma4_agent.domain_tools.os.unlink"), \
             patch("gemma4_agent.domain_tools.subprocess.run", uia), \
             patch("gemma4_agent.domain_tools.subprocess.Popen"):
            r = _media_play_streaming(
                "spotify", "pon música", {"action": "play"},
                executor=_spotify_exec, state=state,
            )
        self.assertEqual(r.get("random_mode"), "liked_songs")
        self.assertTrue(r.get("played"))
        # Deeplink correcto a la coleccion del user.
        info = r.get("auto_play_info") or {}
        self.assertEqual(info.get("deeplink"), "spotify:user:ema123:collection")

    def test_username_arg_is_persisted(self):
        state = _fresh_state()
        with patch("time.sleep"), \
             patch("gemma4_agent.domain_tools.subprocess.Popen"):
            r = _media_play_streaming(
                "spotify", "una cancion",
                {"action": "play", "spotify_user": "ema123"},
                executor=_spotify_exec, state=state,
            )
        # Con el username en el mismo turno -> ya usa Liked Songs.
        self.assertEqual(r.get("random_mode"), "liked_songs")


class TestSpotifyRealTitleStillSearches(unittest.TestCase):
    def test_named_title_uses_search_deeplink(self):
        """Un titulo concreto NO debe disparar random — sigue el flujo normal."""
        state = _fresh_state()
        with patch("time.sleep"), \
             patch("gemma4_agent.domain_tools.subprocess.Popen"), \
             patch("gemma4_agent.domain_tools._spotify_auto_play",
                    return_value={"played": True, "query_match": True}):
            r = _media_play_streaming(
                "spotify", "Benson Boone", {"action": "play"},
                executor=_spotify_exec, state=state,
            )
        self.assertNotIn("random_playback", r)
        self.assertEqual(r.get("deeplink"), "spotify:search:Benson%20Boone")


if __name__ == "__main__":
    unittest.main()
