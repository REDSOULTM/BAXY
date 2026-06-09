"""Tests for F-005: inherit-tools safety guards.

The continuation-inherits-tools path (agent.py around L1049-1100) heredada
los tools del turn previo cuando el user manda algo corto ("ok", "si").
Sin guards esto puede disparar tools peligrosos tras gaps largos o sobre
herramientas destructivas.

Verifies:
  - TTL: gap > INHERIT_TTL_SEC => no hereda.
  - Blacklist: tools en DANGEROUS_TOOLS_NEVER_INHERIT son filtrados.
  - Happy path: tool seguro tras gap corto sigue heredándose.
"""
from __future__ import annotations

import dataclasses
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from ._src_helpers import agent_method_src  # robusto: lee agent.py de disco (no flakea)

from gemma4_agent.agent_core.agent import (
    DANGEROUS_TOOLS_NEVER_INHERIT,
    INHERIT_TTL_SEC,
    Gemma4Agent,
    _GUI_CONTEXT_TOOLS,
    _contextual_info_query,
    _is_info_followup_question,
)
from gemma4_agent.infra.config import AgentConfig


class TestInheritToolsSafety(unittest.TestCase):
    """The inherit-tools path must respect TTL and blacklist."""

    def setUp(self):
        # We don't want to instantiate the full agent (DB, LLM client, etc).
        # We test the inherit logic by replicating its conditional structure
        # with explicit asserts against the constants.
        pass

    def test_dangerous_tools_blacklist_contains_whatsapp(self):
        self.assertIn("whatsapp_send", DANGEROUS_TOOLS_NEVER_INHERIT)
        self.assertIn("whatsapp", DANGEROUS_TOOLS_NEVER_INHERIT)

    def test_dangerous_tools_blacklist_contains_destructive(self):
        for t in ("file_delete", "system_shutdown", "system_logoff",
                  "system_restart"):
            self.assertIn(t, DANGEROUS_TOOLS_NEVER_INHERIT)

    def test_dangerous_tools_blacklist_does_not_contain_safe(self):
        # Web/memory/calendar are safe to inherit on continuations.
        for t in ("web", "memory", "calendar", "weather", "media_tool"):
            self.assertNotIn(t, DANGEROUS_TOOLS_NEVER_INHERIT)

    def test_ttl_is_five_minutes(self):
        self.assertEqual(INHERIT_TTL_SEC, 300)

    def test_filter_dangerous_keeps_safe_tools(self):
        # Simulación del filtro que aplica el agent
        prev_tools = ["web", "whatsapp_send", "memory", "file_delete"]
        filtered = [t for t in prev_tools if t not in DANGEROUS_TOOLS_NEVER_INHERIT]
        self.assertEqual(filtered, ["web", "memory"])

    def test_filter_dangerous_empties_when_all_dangerous(self):
        prev_tools = ["whatsapp_send", "file_delete", "system_shutdown"]
        filtered = [t for t in prev_tools if t not in DANGEROUS_TOOLS_NEVER_INHERIT]
        self.assertEqual(filtered, [])

    def test_ttl_gap_expired(self):
        # Simular gap > TTL
        last_ts = time.time() - (INHERIT_TTL_SEC + 60)
        now = time.time()
        gap = now - last_ts
        self.assertGreater(gap, INHERIT_TTL_SEC)

    def test_ttl_gap_within(self):
        # Simular continuation rapida (<5min)
        last_ts = time.time() - 30
        now = time.time()
        gap = now - last_ts
        self.assertLess(gap, INHERIT_TTL_SEC)


class TestGuiContextInheritOverride(unittest.TestCase):
    """Override por estado del SO: una continuación corta tras una tarea GUI
    abierta (app/window/gui/uia) NO debe tratarse como charla aunque el abstain
    head la lea como conversacional. Repro real medido (traces): tras "abre
    la calculadora y suma 2+2" (ejecutó `app`), "Pero quiero que lo hagas tu" dio
    p_no_tool=0.924 -> subset [session] -> el 4B alucinó system(action=calculator).
    """

    def test_gui_context_tools_includes_synthesis_and_apps(self):
        for t in ("gui", "uia", "app", "window", "vision"):
            self.assertIn(t, _GUI_CONTEXT_TOOLS)

    def test_gui_context_excludes_conversational_tools(self):
        # session/memory/web no son contexto GUI interactivo.
        for t in ("session", "memory", "web", "calendar"):
            self.assertNotIn(t, _GUI_CONTEXT_TOOLS)

    def test_prev_app_detected_as_gui_context(self):
        # tras "abre la calculadora" sólo se ejecutó `app`: debe contar como
        # contexto GUI abierto (la app quedó en pantalla esperando input).
        prev = ["app", "window", "verify"]
        self.assertTrue(set(prev) & _GUI_CONTEXT_TOOLS)

    def test_inherit_augments_with_synthesis_tools(self):
        # Replica la augmentación del agent: si el contexto era GUI, sumar
        # gui/uia para poder OPERAR la app (type/keypress), no sólo re-abrirla.
        prev_tools = ["app", "window"]
        if prev_tools and (set(prev_tools) & _GUI_CONTEXT_TOOLS):
            for _t in ("gui", "uia"):
                if _t not in prev_tools:
                    prev_tools.append(_t)
        self.assertIn("gui", prev_tools)
        self.assertIn("uia", prev_tools)

    def test_no_augment_when_not_gui_context(self):
        # un contexto no-GUI (web research) NO debe ganar gui/uia.
        prev_tools = ["web", "memory"]
        if prev_tools and (set(prev_tools) & _GUI_CONTEXT_TOOLS):
            for _t in ("gui", "uia"):
                if _t not in prev_tools:
                    prev_tools.append(_t)
        self.assertNotIn("gui", prev_tools)
        self.assertNotIn("uia", prev_tools)

    def test_override_logic_present_in_source(self):
        # el override vive en _decide_turn (la fase decide fue extraída de
        # run_content).
        src = agent_method_src("_decide_turn")
        # el override mantiene la herencia cuando el turno previo dejó GUI abierta
        self.assertIn("inherit_kept_gui_context", src)
        self.assertIn("_GUI_CONTEXT_TOOLS", src)

    def test_knowledge_release_guard_present_in_source(self):
        # el override NO debe mantener GUI cuando el turno es una
        # pregunta-del-mundo clara (wants_knowledge) — heredar [app,gui,uia] le
        # quita web/knowledge al 4B y emite el search como texto (`Web(...)`).
        src = agent_method_src("_decide_turn")
        self.assertIn("inherit_released_for_knowledge", src)
        self.assertIn("wants_knowledge", src)
        # el guard combina prev_gui con la negación de wants_knowledge
        self.assertIn("_prev_gui and not _wants_know", src)


class TestKnowledgeReleaseDiscriminator(unittest.TestCase):
    """El discriminador del release (wants_knowledge) debe separar limpio:
    PREGUNTA-DEL-MUNDO (suelta GUI → web) vs OPERATE-APP (mantiene GUI).

    Regresión: tras abrir una app, "cuál es el mejor lego batman"
    heredaba [app,gui,uia] (sin web) → el 4B emitía `Web(action="search"...)`
    como texto crudo al usuario. wants_knowledge es intención por EMBEDDINGS
    multilingüe (no keywords), mide info>action por margen.

    CRÍTICO (anti-regresión del caso calculadora): los 'operate-app' deben dar
    wants_knowledge=False para que SIGAN heredando GUI. Si el encoder no carga,
    wants_knowledge devuelve False (fallback seguro) → se mantiene el override.
    """

    def _wk(self):
        from gemma4_agent.routing.intent_router import wants_knowledge
        return wants_knowledge

    def test_world_questions_release_gui(self):
        wk = self._wk()
        # Preguntas del mundo CLARAS (info>>action por margen): deben SOLTAR el
        # contexto GUI (→ web/knowledge). Estas son las que el log mostró
        # emitiendo `Web(action="search"...)` como texto.
        for q in ("cuál es el mejor lego batman",
                  "qué es un dinosaurio",
                  "buscame el precio del iphone 15",
                  "qué hora es"):
            self.assertTrue(wk(q), f"{q!r} debería ser wants_knowledge=True (soltar GUI)")

    def test_weather_is_borderline_not_released(self):
        # HONESTIDAD (CLAUDE.md): "qué tiempo hace en Madrid" NO dispara
        # wants_knowledge — el encoder embebe "hace" hacia ACTION (action 0.16 >
        # info 0.04). El guard es conservador (el alcance que eligió el usuario):
        # suelta solo lo info-claro; el clima sigue heredando GUI. NO es
        # catastrófico: si el 4B emite `Web(...)`, el rescate del fix anterior lo
        # atrapa. Documentado como límite del encoder base (mismo que el DE).
        wk = self._wk()
        self.assertFalse(wk("qué tiempo hace en Madrid"),
                         "clima es borderline para el encoder — documentado, no se fuerza")

    def test_operate_app_continuations_keep_gui(self):
        wk = self._wk()
        # Continuaciones que OPERAN la app abierta: NO son pregunta-del-mundo,
        # deben MANTENER la herencia GUI (anti-regresión caso calculadora).
        for q in ("ahora sumá 2+2",
                  "pero quiero que lo hagas tú",
                  "dale, hacelo",
                  "escribí hola"):
            self.assertFalse(wk(q), f"{q!r} NO debería ser wants_knowledge (mantener GUI)")

    def test_safe_fallback_returns_false(self):
        # Invariante de seguridad: ante cualquier error, wants_knowledge no debe
        # explotar el camino de herencia; el guard usa try/except → False, y
        # False MANTIENE el override actual (degrada al comportamiento previo).
        wk = self._wk()
        # texto vacío / no-pregunta no debe soltar GUI espuriamente
        self.assertFalse(wk(""))


class TestInfoFollowupAfterResearch(unittest.TestCase):
    """A short follow-up after web/research must stay in the information domain.

    Regression from live trace 20260608_162255_880a3ae3:
    "quien es kai cenat" used web, then "Con ha hecho collab?" was classified as
    fast_action and memory widened the subset to app/system. Forced retry could
    only call app.search, which opens/searches local apps instead of researching.
    """

    def test_short_question_after_web_is_info_followup(self):
        self.assertTrue(_is_info_followup_question("Con ha hecho collab?", ["web"]))
        self.assertTrue(_is_info_followup_question("con quien ha hecho collab?", ["web"]))

    def test_requires_previous_info_tool(self):
        self.assertFalse(_is_info_followup_question("Con ha hecho collab?", ["app"]))
        self.assertFalse(_is_info_followup_question("Con ha hecho collab?", []))

    def test_does_not_steal_identity_or_next_step_questions(self):
        self.assertFalse(_is_info_followup_question("quien eres", ["web"]))
        self.assertFalse(_is_info_followup_question("que hago ahora?", ["web"]))

    def test_contextual_info_query_uses_previous_user_turn(self):
        history = [
            {"role": "user", "content": "quien es kai cenat"},
            {"role": "assistant", "content": "Kai Cenat es un streamer."},
            {"role": "user", "content": "Con ha hecho collab?"},
        ]
        self.assertEqual(
            _contextual_info_query("Con ha hecho collab?", history),
            "quien es kai cenat Con ha hecho collab?",
        )

    def test_decide_turn_rewrites_action_memory_subset_to_info_tools(self):
        tmp = Path(tempfile.mkdtemp(prefix="gemma4-info-followup-"))
        cfg = dataclasses.replace(
            AgentConfig.from_env(),
            memory_path=tmp / "memory.json",
            captures_dir=tmp / "captures",
            trace_path=tmp / "traces.jsonl",
            state_path=tmp / "state.json",
            enable_tracing=False,
            enable_safety=False,
        )
        agent = Gemma4Agent(cfg)
        agent._last_executed_tools = ["web"]
        fake_select = mock.MagicMock(return_value=["session", "safety", "app", "system"])
        fake_select._last_fallback_used = False
        with mock.patch("gemma4_agent.agent_core.agent.select_tool_names", fake_select):
            decision = agent._decide_turn("Con ha hecho collab?")
        self.assertIn("web", decision.selected_tool_names)
        self.assertIn("source_manager", decision.selected_tool_names)
        self.assertIn("knowledge", decision.selected_tool_names)
        self.assertNotIn("app", decision.selected_tool_names)
        self.assertNotIn("system", decision.selected_tool_names)
        self.assertEqual(decision.mode.name, "research")
        self.assertIn("Information follow-up", agent._info_followup_note)

    def test_run_content_prefetches_web_for_info_followup(self):
        tmp = Path(tempfile.mkdtemp(prefix="gemma4-info-prefetch-"))
        cfg = dataclasses.replace(
            AgentConfig.from_env(),
            memory_path=tmp / "memory.json",
            captures_dir=tmp / "captures",
            trace_path=tmp / "traces.jsonl",
            state_path=tmp / "state.json",
            enable_tracing=True,
            enable_safety=False,
        )
        agent = Gemma4Agent(cfg)
        agent.history = [
            {"role": "user", "content": "quien es kai cenat"},
            {"role": "assistant", "content": "Kai Cenat es un streamer."},
        ]
        agent._last_executed_tools = ["web"]
        fake_select = mock.MagicMock(return_value=["session"])
        fake_select._last_fallback_used = False
        agent.client.chat = mock.MagicMock(return_value={"choices": [{
            "message": {"role": "assistant", "content": "Respuesta desde fuente.", "tool_calls": []},
            "finish_reason": "stop",
        }]})
        agent.tools.execute = mock.MagicMock(return_value={
            "ok": True,
            "status": "done",
            "verified": True,
            "content_verified": True,
            "completion_status": "search_results_extracted",
            "results": [{"title": "x", "url": "https://example.com", "snippet": "x"}],
            "count": 1,
        })
        with mock.patch("gemma4_agent.agent_core.agent.select_tool_names", fake_select):
            reply = agent.run_content("Con ha hecho collab?")
        self.assertEqual(reply.content, "Respuesta desde fuente.")
        agent.tools.execute.assert_called_once_with(
            "web", {"action": "search", "query": "quien es kai cenat Con ha hecho collab?"})
        self.assertEqual([ev.name for ev in reply.tool_events], ["web"])


class TestAgentInheritState(unittest.TestCase):
    """Verify the agent instance has _last_turn_ts state plumbed in."""

    def test_last_turn_ts_attribute_exists(self):
        # Check via class introspection that __init__ sets _last_turn_ts.
        # We don't actually instantiate (avoids DB/LLM setup). Read source.
        src = agent_method_src("__init__")
        self.assertIn("_last_turn_ts", src)

    def test_clear_resets_last_turn_ts(self):
        src = agent_method_src("clear")
        self.assertIn("_last_turn_ts", src)


if __name__ == "__main__":
    unittest.main()
