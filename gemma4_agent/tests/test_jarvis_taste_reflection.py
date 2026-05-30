"""Tests de la reflexión por LLM (gustos finos) — R-Jarvis fase 1.

Pinnea el CONTRATO de la capa opt-in: grounding guard (anti-alucinación), parse
tolerante, gate OFF = no-op, thinking OFF, perfil vacío = sin llamada LLM, y el
roundtrip del caché + forget. El LLM se mockea (determinista); la calidad real del
4B se verifica en vivo aparte (regla 3.5)."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gemma4_agent.memory_pkg import taste_reflection as TR
from gemma4_agent.memory_pkg.taste_profile import TasteProfile


def _profile() -> TasteProfile:
    p = TasteProfile(total_observations=50)
    p.top_apps = [("code.exe", 12.0), ("spotify.exe", 8.0)]
    p.apps_by_slot = {"mañana": "code.exe", "noche": "spotify.exe"}
    p.top_artists = [("soda stereo", 15), ("gustavo cerati", 8)]
    p.music_slots = ["noche"]
    return p


class _FakeLog:
    """behavior_log mínimo: sólo necesita .path para el caché en disco."""
    def __init__(self, d: Path):
        self.path = d / "user.db"


class _FakeLLM:
    def __init__(self, content: str):
        self.content = content
        self.calls: list[dict] = []

    def chat(self, messages, **kw):
        self.calls.append({"messages": messages, "kw": kw})
        return {"choices": [{"message": {"content": self.content}}]}


_GROUNDED = ('```json\n[{"insight": "Preferís rock latino de los 90", '
            '"evidencia": "Artistas: Soda Stereo, Gustavo Cerati"}]\n```')
_FABRICATED = ('[{"insight": "Te gusta el jazz", "evidencia": "escuchás jazz nocturno"}]')


class GroundingGuard(unittest.TestCase):
    def test_grounded_insight_survives(self):
        llm = _FakeLLM(_GROUNDED)
        out = TR.reflect(_profile(), llm)
        self.assertEqual(len(out), 1)
        self.assertIn("rock latino", out[0].text.lower())

    def test_fabricated_evidence_rejected(self):
        # La evidencia no referencia NINGUNA observación real -> descartado.
        llm = _FakeLLM(_FABRICATED)
        out = TR.reflect(_profile(), llm)
        self.assertEqual(out, [], f"evidencia fabricada no debe pasar: {out}")

    def test_thinking_is_disabled(self):
        llm = _FakeLLM(_GROUNDED)
        TR.reflect(_profile(), llm)
        self.assertEqual(len(llm.calls), 1)
        self.assertEqual(llm.calls[0]["kw"].get("enable_thinking"), False)

    def test_empty_profile_no_llm_call(self):
        llm = _FakeLLM(_GROUNDED)
        out = TR.reflect(TasteProfile(), llm)
        self.assertEqual(out, [])
        self.assertEqual(llm.calls, [], "perfil vacío no debe llamar al LLM")

    def test_too_long_insight_rejected(self):
        llm = _FakeLLM('[{"insight": "%s", "evidencia": "Soda Stereo"}]' % ("x" * 300))
        self.assertEqual(TR.reflect(_profile(), llm), [])

    def test_max_three_insights(self):
        many = "[" + ",".join(
            '{"insight": "i%d Code", "evidencia": "Apps: Code"}' % i for i in range(6)) + "]"
        out = TR.reflect(_profile(), _FakeLLM(many))
        self.assertLessEqual(len(out), TR._MAX_INSIGHTS)


class ParseTolerance(unittest.TestCase):
    def test_fences_stripped(self):
        ins = TR._parse_json_insights('```json\n[{"insight":"a Code","evidencia":"Code"}]\n```')
        self.assertEqual(len(ins), 1)

    def test_narration_around_array(self):
        ins = TR._parse_json_insights('Claro:\n[{"insight":"a Code","evidencia":"Code"}]\nlisto')
        self.assertEqual(len(ins), 1)

    def test_malformed_returns_empty(self):
        self.assertEqual(TR._parse_json_insights("no json aquí"), [])
        self.assertEqual(TR._parse_json_insights(""), [])

    def test_english_evidence_key_accepted(self):
        ins = TR._parse_json_insights('[{"insight":"a","evidence":"Code"}]')
        self.assertEqual(ins[0].evidence, "Code")


class GateAndCache(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.log = _FakeLog(Path(self._tmp.name))
        self._prev = os.environ.get("GEMMA4_TASTE_LLM_REFLECTION")

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("GEMMA4_TASTE_LLM_REFLECTION", None)
        else:
            os.environ["GEMMA4_TASTE_LLM_REFLECTION"] = self._prev
        self._tmp.cleanup()

    def test_gate_off_block_empty(self):
        os.environ["GEMMA4_TASTE_LLM_REFLECTION"] = "0"
        # aún con caché, el bloque sale vacío si el gate está OFF
        TR._save_cache(self.log, _profile(), [TR.Insight("x", "Code")])
        self.assertEqual(TR.reflection_block(self.log), "")

    def test_gate_on_block_renders(self):
        os.environ["GEMMA4_TASTE_LLM_REFLECTION"] = "1"
        TR._save_cache(self.log, _profile(), [TR.Insight("rock latino de los 90", "Soda Stereo")])
        block = TR.reflection_block(self.log)
        self.assertIn("rock latino", block)
        self.assertIn("inferido", block.lower())

    def test_cache_roundtrip(self):
        TR._save_cache(self.log, _profile(), [TR.Insight("a", "Code"), TR.Insight("b", "Spotify")])
        got = TR.cached_insights(self.log)
        self.assertEqual([i.text for i in got], ["a", "b"])

    def test_forget_clears_cache(self):
        TR._save_cache(self.log, _profile(), [TR.Insight("a", "Code")])
        self.assertTrue(TR.cached_insights(self.log))
        TR.forget_reflection(self.log)
        self.assertEqual(TR.cached_insights(self.log), [])

    def test_maybe_refresh_gate_off_noop(self):
        os.environ["GEMMA4_TASTE_LLM_REFLECTION"] = "0"
        llm = _FakeLLM(_GROUNDED)
        TR.maybe_refresh_async(self.log, llm)  # no debe hacer nada
        self.assertEqual(llm.calls, [])

    def test_refresh_saves_even_when_empty_profile(self):
        # background con perfil vacío igual escribe el caché (resetea TTL, no re-dispara).
        # Patch donde se USA (taste_reflection lo importa top-level), no en el origen.
        with mock.patch("gemma4_agent.memory_pkg.taste_reflection.build_profile",
                        return_value=TasteProfile()):
            TR.refresh(self.log, _FakeLLM(_GROUNDED))
        data = TR._load_cache(self.log)
        self.assertIsNotNone(data)
        self.assertEqual(data.get("insights"), [])


if __name__ == "__main__":
    unittest.main()
