"""Confirm filler (2026-06-10): audio inmediato con personalidad mientras el
LLM piensa. Módulo (pick_filler/intent_target) + cableo (_voice_action_filler
en run_content, entre decide y execute). El gate end-to-end real es EN VIVO
(el 4B es no-determinista); acá se prueban los predicados y gates en aislado.
"""
from __future__ import annotations
import os
import unittest
from gemma4_agent.agent_core.action_filler import (
    pick_filler, intent_target_for_filler,
)


class TestActionFiller(unittest.TestCase):
    def test_intent_aware_only_for_safe_open(self):
        # "abrí Spotify" -> target seguro; "qué hora es"/"sube volumen" -> genérico.
        tgt, tool = intent_target_for_filler("abrí Spotify", ["app", "window"])
        self.assertEqual(tgt, "Spotify")
        self.assertEqual(tool, "app")
        for txt, tools in [("qué hora es", ["system"]), ("sube el volumen", ["audio"]),
                           ("poné música de los Beatles", ["media"])]:
            t, _ = intent_target_for_filler(txt, tools)
            self.assertIsNone(t, f"no debe extraer target inseguro: {txt!r}")

    def test_intent_aware_filler_text(self):
        f = pick_filler(lang="es", intent_target="Spotify", intent_tool="app")
        self.assertIn("Spotify", f)

    def test_generic_has_personality_and_rotates(self):
        a = pick_filler(lang="es", rotate=0)
        b = pick_filler(lang="es", rotate=1)
        self.assertTrue(a and b and a != b)

    def test_slow_filler_is_reassuring(self):
        s = pick_filler(lang="es", rotate=0, slow=True)
        self.assertTrue(s)  # banco slow no vacío

    def test_gate_off_disables(self):
        os.environ["GEMMA4_ACTION_FILLER"] = "0"
        try:
            self.assertIsNone(pick_filler(lang="es", rotate=0))
        finally:
            os.environ.pop("GEMMA4_ACTION_FILLER", None)


class _Trace:
    def __init__(self):
        self.events = []

    def event(self, turn_id, name, **kw):
        self.events.append((name, kw))


class _AgentStub:
    """Duck-typed stand-in de Gemma4Agent (mismo patrón que test_stream_tts):
    evita construir el agente completo solo para ejercitar el cableo."""

    def __init__(self, sink):
        self._active_tts_sink = sink
        self.trace = _Trace()


class _Mode:
    def __init__(self, name="quick_action"):
        self.name = name


def _wire(text, tools, sink=None, lang="es", mode_name="quick_action", env=None):
    from gemma4_agent.agent_core.agent import Gemma4Agent
    from gemma4_agent.agent_core.turn_types import TurnDecision
    fed = []
    stub = _AgentStub(sink if sink is not None else fed.append)
    decision = TurnDecision(turn_id="t", raw_text_early=text,
                            selected_tool_names=tools, mode=_Mode(mode_name))
    overrides = {"GEMMA4_VOICE_LANG": lang, **(env or {})}
    old = {k: os.environ.get(k) for k in overrides}
    os.environ.update(overrides)
    try:
        Gemma4Agent._voice_action_filler(stub, text, decision)
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return stub, fed


class TestVoiceActionFillerWiring(unittest.TestCase):
    def test_action_turn_voices_generic_by_default(self):
        # intent-aware es OPT-IN (medido en vivo que contradice en el subset
        # que llega al LLM): default = genérico aunque el open sea claro.
        stub, fed = _wire("abrí Spotify", ["app", "window"])
        self.assertEqual(len(fed), 1)
        self.assertNotIn("Spotify", fed[0])
        names = [n for n, _ in stub.trace.events]
        self.assertIn("action_filler", names)

    def test_intent_aware_requires_opt_in(self):
        _, fed = _wire("abrí Spotify", ["app"],
                       env={"GEMMA4_FILLER_INTENT": "1"})
        self.assertEqual(len(fed), 1)
        self.assertIn("Spotify", fed[0])

    def test_ambiguous_action_voices_generic(self):
        # acción real pero target inseguro -> genérico (nunca miente).
        _, fed = _wire("sube el volumen", ["audio"],
                       env={"GEMMA4_FILLER_INTENT": "1"})
        self.assertEqual(len(fed), 1)
        self.assertNotIn("volumen", fed[0])

    def test_info_mode_no_filler(self):
        # el router puede OFRECER tools en un turno de charla/info (el 4B
        # decide no usarlas): el modo no-acción es la señal -> sin filler.
        _, fed = _wire("qué linda mañana", ["web"], mode_name="fast_info")
        self.assertEqual(fed, [])

    def test_no_tools_no_filler(self):
        _, fed = _wire("qué lindo día", [])
        self.assertEqual(fed, [])

    def test_session_only_is_meta_not_action(self):
        _, fed = _wire("cancelá eso", ["session"])
        self.assertEqual(fed, [])

    def test_meta_only_chat_no_filler(self):
        # MEDIDO: la charla recibe ['session','safety'] en modo fast_action —
        # un set solo-meta no es acción, no se voca filler.
        _, fed = _wire("qué linda mañana", ["session", "safety"],
                       mode_name="fast_action")
        self.assertEqual(fed, [])

    def test_no_sink_no_filler(self):
        # texto/CLI pasan tts_sink=None -> no se voca nada ni se tracea.
        from gemma4_agent.agent_core.agent import Gemma4Agent
        from gemma4_agent.agent_core.turn_types import TurnDecision
        stub = _AgentStub(None)
        Gemma4Agent._voice_action_filler(
            stub, "abrí Spotify",
            TurnDecision(turn_id="t", raw_text_early="abrí Spotify",
                         selected_tool_names=["app"], mode=_Mode()))
        self.assertEqual(stub.trace.events, [])

    def test_unsupported_lang_stays_silent(self):
        # banco solo es/en: con idioma fijo fr NO se voca español.
        _, fed = _wire("ouvre Spotify", ["app"], lang="fr")
        self.assertEqual(fed, [])

    def test_rotation_varies_generic(self):
        from gemma4_agent.agent_core.agent import Gemma4Agent
        from gemma4_agent.agent_core.turn_types import TurnDecision
        fed = []
        stub = _AgentStub(fed.append)
        old = os.environ.get("GEMMA4_VOICE_LANG")
        os.environ["GEMMA4_VOICE_LANG"] = "es"
        try:
            for _ in range(2):
                Gemma4Agent._voice_action_filler(
                    stub, "sube el volumen",
                    TurnDecision(turn_id="t", raw_text_early="sube el volumen",
                                 selected_tool_names=["audio"], mode=_Mode()))
        finally:
            if old is None:
                os.environ.pop("GEMMA4_VOICE_LANG", None)
            else:
                os.environ["GEMMA4_VOICE_LANG"] = old
        self.assertEqual(len(fed), 2)
        self.assertNotEqual(fed[0], fed[1])


if __name__ == "__main__":
    unittest.main()
