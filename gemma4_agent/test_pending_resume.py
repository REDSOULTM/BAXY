"""Tests for cross-turn pending action resume (e.g. streaming_profile)."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("GEMMA4_LLAMA_AUTO_START", "0")

from .agent import Gemma4Agent
from .config import AgentConfig
from .domain_tools import (
    clear_pending_action,
    get_pending_action,
    media_tool,
)
from .state import AgentState


def _fresh_state() -> AgentState:
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    p = Path(tmp.name)
    p.unlink(missing_ok=True)
    return AgentState(path=p)


class TestProfileNameExtractor(unittest.TestCase):

    def test_bare_name(self):
        self.assertEqual(Gemma4Agent._extract_profile_name("Ema"), "Ema")
        self.assertEqual(Gemma4Agent._extract_profile_name("Bea"), "Bea")

    def test_mi_perfil_es_X(self):
        self.assertEqual(
            Gemma4Agent._extract_profile_name("Mi perfil es Ema"), "Ema",
        )
        self.assertEqual(
            Gemma4Agent._extract_profile_name("mi perfil de disney es Emmanuel"),
            "Emmanuel",
        )

    def test_soy_X(self):
        self.assertEqual(Gemma4Agent._extract_profile_name("soy Bea"), "Bea")

    def test_perfil_colon(self):
        self.assertEqual(
            Gemma4Agent._extract_profile_name("perfil: Elio"), "Elio",
        )

    def test_usa_el_perfil(self):
        self.assertEqual(
            Gemma4Agent._extract_profile_name("usa el perfil de Clara"), "Clara",
        )

    def test_rejects_commands(self):
        self.assertIsNone(Gemma4Agent._extract_profile_name("abre notepad"))
        self.assertIsNone(Gemma4Agent._extract_profile_name("pon música"))
        self.assertIsNone(Gemma4Agent._extract_profile_name("no, mejor cancela"))

    def test_rejects_questions(self):
        self.assertIsNone(Gemma4Agent._extract_profile_name("¿cuál era el perfil?"))

    def test_two_word_short_ok(self):
        # "REDSOULTM" — 2 palabras cortas que parecen nombre.
        self.assertEqual(
            Gemma4Agent._extract_profile_name("REDSOULTM"),
            "REDSOULTM",
        )

    def test_too_long_rejected(self):
        # Frase larga sin patron explicito.
        self.assertIsNone(
            Gemma4Agent._extract_profile_name(
                "quiero ver una pelicula de comedia hoy a la noche con amigos",
            ),
        )


class TestPendingActionStore(unittest.TestCase):

    def test_set_then_get(self):
        state = _fresh_state()
        from .domain_tools import _set_pending_action
        _set_pending_action(state, "streaming_profile", {"provider": "netflix", "query": "X"})
        p = get_pending_action(state)
        self.assertIsNotNone(p)
        self.assertEqual(p["kind"], "streaming_profile")
        self.assertEqual(p["payload"]["provider"], "netflix")
        self.assertEqual(p["payload"]["query"], "X")

    def test_set_overwrites_previous(self):
        state = _fresh_state()
        from .domain_tools import _set_pending_action
        _set_pending_action(state, "streaming_profile", {"provider": "netflix"})
        _set_pending_action(state, "streaming_profile", {"provider": "disney"})
        # El reciente queda activo, el viejo se cierra.
        p = get_pending_action(state)
        self.assertEqual(p["payload"]["provider"], "disney")

    def test_clear_removes_pending(self):
        state = _fresh_state()
        from .domain_tools import _set_pending_action
        _set_pending_action(state, "streaming_profile", {"provider": "netflix"})
        clear_pending_action(state)
        self.assertIsNone(get_pending_action(state))

    def test_none_state_safe(self):
        self.assertIsNone(get_pending_action(None))
        # No crash:
        clear_pending_action(None)


class TestMediaCreatesPending(unittest.TestCase):
    """Cuando media returns needs_user, debe crear el pending."""

    def test_first_call_creates_pending(self):
        state = _fresh_state()
        with patch("gemma4_agent.domain_tools.webbrowser.open", return_value=True):
            r = media_tool(
                {"action": "play", "provider": "netflix", "query": "Loki"},
                MagicMock(return_value={"ok": True}),
                state,
            )
        self.assertFalse(r["ok"])
        self.assertEqual(r["asks_for"], "streaming_profile")
        p = get_pending_action(state)
        self.assertIsNotNone(p)
        self.assertEqual(p["kind"], "streaming_profile")
        self.assertEqual(p["payload"]["provider"], "netflix")
        self.assertEqual(p["payload"]["query"], "Loki")

    def test_explicit_profile_clears_pending(self):
        state = _fresh_state()
        # Crear pending primero
        from .domain_tools import _set_pending_action
        _set_pending_action(state, "streaming_profile", {"provider": "netflix"})
        # Llamar con profile -> pending se cierra
        def _exec(name, args):
            if name == "gui" and args.get("action") == "click_text":
                return {"ok": True, "found": True}
            return {"ok": True}
        with patch("gemma4_agent.domain_tools.webbrowser.open", return_value=True), \
             patch("time.sleep"):
            media_tool(
                {"action": "play", "provider": "netflix",
                 "query": "X", "profile": "Ema"},
                _exec, state,
            )
        self.assertIsNone(get_pending_action(state))


class TestResumePendingEndToEnd(unittest.TestCase):
    """E2E: pending guardado -> user da nombre -> resume sin LLM ejecuta media."""

    def test_resume_runs_media_with_profile(self):
        from .domain_tools import _set_pending_action
        agent = Gemma4Agent(AgentConfig.from_env())
        # Pre-set pending como si el turn anterior hubiera pedido profile.
        _set_pending_action(agent.state, "streaming_profile", {
            "provider": "disney",
            "query": "Daredevil Born Again",
            "auto_play": True,
        })

        # Mock executor para evitar GUI real.
        captured: list[tuple] = []

        def _mock_execute(name, args):
            captured.append((name, args))
            if name == "media":
                # Simular media exitoso (played=True).
                return {
                    "ok": True, "played": True, "provider": "disney_web",
                    "profile_name": args.get("profile"),
                    "completion_status": "media_playing",
                    "status": "dispatched", "verified": True,
                    "tool": "media", "action": "play",
                }
            return {"ok": True}

        with patch.object(agent.tools, "execute", side_effect=_mock_execute):
            reply = agent._try_resume_pending_action("Mi perfil es Ema", "test_turn")

        self.assertIsNotNone(reply, "resume should return AgentReply")
        self.assertIn("Ema", reply.content)
        self.assertIn("Daredevil", reply.content)
        # Verificar que media se llamo con el profile correcto.
        media_calls = [c for c in captured if c[0] == "media"]
        self.assertEqual(len(media_calls), 1)
        self.assertEqual(media_calls[0][1]["profile"], "Ema")
        self.assertEqual(media_calls[0][1]["provider"], "disney")
        self.assertEqual(media_calls[0][1]["query"], "Daredevil Born Again")

    def test_resume_traces_without_crashing_on_kind_kwarg(self):
        """REGRESION: trace.event(turn_id, kind, **payload) no acepta otro
        kwarg 'kind'. Verificar que el code path del resume no haga eso."""
        from .domain_tools import _set_pending_action
        agent = Gemma4Agent(AgentConfig.from_env())
        _set_pending_action(agent.state, "streaming_profile", {
            "provider": "disney", "query": "X",
        })

        # Mock trace.event para capturar todos los kwargs.
        recorded_calls: list[tuple] = []
        original_event = agent.trace.event

        def _capture(turn_id, kind, **payload):
            # Llamar al original (que valida args) — esto re-disparara el
            # bug si esta presente.
            recorded_calls.append((turn_id, kind, payload))
            original_event(turn_id, kind, **payload)

        with patch.object(agent.trace, "event", side_effect=_capture):
            with patch.object(agent.tools, "execute",
                              return_value={"ok": True, "played": True,
                                            "provider": "disney_web",
                                            "completion_status": "media_playing"}):
                # Esto NO debe lanzar TypeError "multiple values for kind".
                reply = agent._try_resume_pending_action("Mi perfil es Ema", "test")

        self.assertIsNotNone(reply)
        # Verificar que las trace calls fueron exitosas.
        self.assertTrue(any(c[1] == "pending_resume" for c in recorded_calls))


class TestUnverifiedGuardWithNeedsUser(unittest.TestCase):
    """El guard NO debe inyectar 'Nota:' cuando status='needs_user'."""

    def test_no_nota_for_needs_user(self):
        from .agent import ToolEvent
        agent = Gemma4Agent(AgentConfig.from_env())
        event = ToolEvent(
            name="media",
            args={"action": "play", "provider": "netflix"},
            result={
                "ok": False, "status": "needs_user",
                "asks_for": "streaming_profile", "error": "need profile",
                "verified": False,
            },
        )
        reply = "Necesito tu perfil de Netflix. ¿Cuál es?"
        out = agent._guard_unverified_final(reply, [event])
        # NO debe haber agregado "Nota: ...".
        self.assertNotIn("Nota:", out)
        self.assertEqual(out, reply)

    def test_no_nota_for_needs_dependency(self):
        from .agent import ToolEvent
        agent = Gemma4Agent(AgentConfig.from_env())
        event = ToolEvent(
            name="media", args={},
            result={"ok": False, "status": "needs_dependency",
                    "error": "VLC missing", "verified": False},
        )
        out = agent._guard_unverified_final("VLC no instalado.", [event])
        self.assertNotIn("Nota:", out)


if __name__ == "__main__":
    unittest.main()
