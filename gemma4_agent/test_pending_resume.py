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


class TestPendingActionTTL(unittest.TestCase):
    """TTL semantics: pending older than 300s must NOT resume, and must
    be auto-cleared when encountered."""

    def test_pending_within_ttl_resumes(self):
        from .domain_tools import _set_pending_action
        agent = Gemma4Agent(AgentConfig.from_env())
        _set_pending_action(agent.state, "streaming_profile",
                            {"provider": "netflix", "query": "X"})
        # Within window (default created_at = now): age ~ 0s.
        with patch.object(agent.tools, "execute",
                          return_value={"ok": True, "played": True,
                                        "provider": "netflix_web",
                                        "completion_status": "media_playing"}):
            reply = agent._try_resume_pending_action("Ema", "t1")
        self.assertIsNotNone(reply)

    def test_pending_past_ttl_does_not_resume_and_clears(self):
        from .domain_tools import (
            _set_pending_action,
            get_pending_action,
        )
        agent = Gemma4Agent(AgentConfig.from_env())
        _set_pending_action(agent.state, "streaming_profile",
                            {"provider": "netflix", "query": "X"})
        # Backdate created_at by 10 minutes so age_seconds > 300.
        from datetime import datetime, timedelta
        data = agent.state._load()  # noqa: SLF001
        for res in data.get("resources", {}).values():
            if isinstance(res, dict) and res.get("kind") == "pending_action":
                old = (datetime.now() - timedelta(seconds=601)).isoformat()
                res.setdefault("metadata", {})["created_at"] = old
        agent.state._save(data)  # noqa: SLF001

        # Sanity: pending is still readable, age > 300.
        p = get_pending_action(agent.state)
        self.assertIsNotNone(p)
        self.assertGreater(p["age_seconds"], 300)

        # Resume must NOT fire even with a valid-looking name.
        with patch.object(agent.tools, "execute") as mock_exec:
            reply = agent._try_resume_pending_action("Ema", "t1")
        self.assertIsNone(reply)
        mock_exec.assert_not_called()
        # And pending must be auto-cleared so future turns don't try again.
        self.assertIsNone(get_pending_action(agent.state))


class TestPendingActionExplicitCancel(unittest.TestCase):
    """User saying 'olvidalo' / 'cancela' / 'no importa' must close the
    pending so it doesn't trap subsequent turns."""

    def setUp(self):
        from .domain_tools import _set_pending_action
        self.agent = Gemma4Agent(AgentConfig.from_env())
        _set_pending_action(
            self.agent.state, "streaming_profile",
            {"provider": "disney", "query": "Loki"},
        )

    def _resume_with(self, text: str):
        with patch.object(self.agent.tools, "execute") as mock_exec:
            reply = self.agent._try_resume_pending_action(text, "tcancel")
        return reply, mock_exec

    def test_olvidalo_clears_pending(self):
        from .domain_tools import get_pending_action
        reply, mock_exec = self._resume_with("olvidalo")
        # No reply (kicks back to normal LLM path) and no media exec.
        self.assertIsNone(reply)
        mock_exec.assert_not_called()
        self.assertIsNone(get_pending_action(self.agent.state))

    def test_cancela_clears_pending(self):
        from .domain_tools import get_pending_action
        self._resume_with("cancela eso por favor")
        self.assertIsNone(get_pending_action(self.agent.state))

    def test_no_importa_clears_pending(self):
        from .domain_tools import get_pending_action
        self._resume_with("no importa, dejalo")
        self.assertIsNone(get_pending_action(self.agent.state))

    def test_unrelated_long_text_does_not_clear(self):
        """Long off-topic text shouldn't auto-cancel — user might still
        intend to follow up. Conservative: leave pending alone, let TTL
        decide or the next on-topic answer."""
        from .domain_tools import get_pending_action
        reply, mock_exec = self._resume_with(
            "quiero saber qué tiempo va a hacer mañana en buenos aires"
        )
        self.assertIsNone(reply)  # no profile extracted
        mock_exec.assert_not_called()
        # Pending still there for future on-topic reply.
        self.assertIsNotNone(get_pending_action(self.agent.state))


class TestPendingActionPersistsAcrossAgentInstances(unittest.TestCase):
    """The pending lives in AgentState (a JSON file). A second Agent
    constructed against the same state path must see it."""

    def test_second_agent_sees_pending_from_first(self):
        from .domain_tools import _set_pending_action, get_pending_action
        # Build first agent + write pending.
        agent_a = Gemma4Agent(AgentConfig.from_env())
        _set_pending_action(
            agent_a.state, "streaming_profile",
            {"provider": "hbo_max", "query": "House of Dragon"},
        )
        state_path = agent_a.state.path

        # Build a second agent against the same state file (simulates
        # process restart). NOTE: Gemma4Agent uses captures-dir-relative
        # default state, so we splice the state path back in.
        agent_b = Gemma4Agent(AgentConfig.from_env())
        from .state import AgentState
        agent_b.state = AgentState(path=state_path)

        p = get_pending_action(agent_b.state)
        self.assertIsNotNone(p, "second agent should read the persisted pending")
        self.assertEqual(p["kind"], "streaming_profile")
        self.assertEqual(p["payload"]["provider"], "hbo_max")
        self.assertEqual(p["payload"]["query"], "House of Dragon")


class TestProfileExtractorAdversarial(unittest.TestCase):
    """10+ adversarial phrases to harden the extractor.

    These come from real-world ways a user might respond when prompted for
    a streaming profile — including ambiguity, accents, capitalization,
    and intent-changes.
    """

    def test_accents_and_capitalization(self):
        self.assertEqual(
            Gemma4Agent._extract_profile_name("José"), "José",
        )
        self.assertEqual(
            Gemma4Agent._extract_profile_name("Mi perfil es JOSÉ"), "JOSÉ",
        )

    def test_with_trailing_punctuation(self):
        self.assertEqual(
            Gemma4Agent._extract_profile_name("Ema."), "Ema",
        )
        # Trailing comma also stripped (current heuristic uses .strip(" .,;")).
        self.assertEqual(
            Gemma4Agent._extract_profile_name("perfil: Elio,"), "Elio",
        )

    def test_intent_change_rejected(self):
        # User pivoted away from the question.
        self.assertIsNone(
            Gemma4Agent._extract_profile_name("Mejor abre Spotify"),
        )
        self.assertIsNone(
            Gemma4Agent._extract_profile_name("dale pausa"),
        )

    def test_pure_no_rejected(self):
        # "no" alone is a cancel, not a name.
        self.assertIsNone(Gemma4Agent._extract_profile_name("no"))
        self.assertIsNone(Gemma4Agent._extract_profile_name("No"))

    def test_pure_yes_rejected(self):
        self.assertIsNone(Gemma4Agent._extract_profile_name("si"))
        self.assertIsNone(Gemma4Agent._extract_profile_name("yes"))
        self.assertIsNone(Gemma4Agent._extract_profile_name("ok"))

    def test_question_rejected(self):
        self.assertIsNone(
            Gemma4Agent._extract_profile_name("¿cuál era el mío?"),
        )
        self.assertIsNone(
            Gemma4Agent._extract_profile_name("qué perfiles tengo?"),
        )

    def test_empty_and_whitespace(self):
        self.assertIsNone(Gemma4Agent._extract_profile_name(""))
        self.assertIsNone(Gemma4Agent._extract_profile_name("   "))
        self.assertIsNone(Gemma4Agent._extract_profile_name("\n\t"))

    def test_long_sentence_rejected(self):
        # 4+ words without explicit "mi perfil es" / "soy" -> reject.
        self.assertIsNone(
            Gemma4Agent._extract_profile_name(
                "me gustaría que uses cualquiera de los perfiles disponibles"
            ),
        )

    def test_special_chars_in_name_rejected(self):
        # Profile names with {}, ?, ! are almost certainly not a real name.
        self.assertIsNone(
            Gemma4Agent._extract_profile_name("Mi perfil es {something}"),
        )

    def test_greeting_rejected_regression(self):
        """REGRESION 2026-05-16 (UI screenshot): user said "Hola" after the
        agent had asked for a streaming profile in a previous turn. Extractor
        accepted "Hola" → media tool saved profile_name="Hola" on HBO Max.
        Visible in chat: "Guardé tu perfil de Hbo Max como 'Hola'."
        """
        for greeting in ("Hola", "hola", "HOLA", "Hello", "Hi", "Hey",
                         "Buenos dias", "Buenas", "Que tal", "Gracias",
                         "Adios", "chau"):
            with self.subTest(greeting=greeting):
                self.assertIsNone(
                    Gemma4Agent._extract_profile_name(greeting),
                    f"{greeting!r} should be rejected as profile name",
                )

    def test_greeting_prefix_does_not_overreject(self):
        """Conversational tokens use exact match, not prefix — "Holanda"
        must NOT be rejected just because it starts with "Hola"."""
        self.assertEqual(
            Gemma4Agent._extract_profile_name("Holanda"), "Holanda",
        )
        self.assertEqual(
            Gemma4Agent._extract_profile_name("Helena"), "Helena",
        )


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
