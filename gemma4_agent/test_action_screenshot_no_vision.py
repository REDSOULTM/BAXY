"""Regresión 2026-05-22 (minada de traces): "Pon musica en youtube" → media tool
abre la URL y adjunta un screenshot de VERIFICACIÓN (3840x1944, 1.7MB) con
`image_path`. El agente inyectaba ese screenshot en el historial → la pasada de
respuesta post-tool resolvía al preset de visión; cuando el server no advertía
<perfil>-vision, la imagen caía en -text → HTTP 500 "image input is not supported".

Fix: una confirmación de acción ("Listo, abrí YouTube") NO necesita VER el
screenshot — solo se inyecta la imagen en turnos genuinamente visuales (vision
mode, o tools cuyo deliverable ES la imagen: gui/vision/uia/verify, o un
result.action de captura). El screenshot de auto-verificación de una tool de
ACCIÓN es evidencia para el verifier, no input para el LLM.

EJE: FIABILIDAD (elimina el 500) + LATENCIA (no manda 1.7MB de imagen ni fuerza
un preset de visión por una confirmación de texto). No toca los turnos de visión
reales (siguen inyectando)."""
from __future__ import annotations

import dataclasses
import tempfile
import unittest
from pathlib import Path

from gemma4_agent.agent import Gemma4Agent
from gemma4_agent.config import AgentConfig
from gemma4_agent.modes import choose_mode


def _make_agent(tmp: Path) -> Gemma4Agent:
    cfg = dataclasses.replace(
        AgentConfig.from_env(),
        memory_path=tmp / "m.json", captures_dir=tmp / "cap",
        trace_path=tmp / "t.jsonl", state_path=tmp / "s.json",
        enable_tracing=False, enable_safety=False,
    )
    return Gemma4Agent(cfg)


# A faithful slice of the real youtube_play result that triggered the 500.
_YOUTUBE_RESULT = {
    "ok": True, "action": "youtube_play", "query": "musica popular",
    "url": "https://www.youtube.com/watch?v=YOyc2E2Gp1w&autoplay=1",
    "completion_status": "opened_youtube_video_for_playback",
    "note": "screenshot is provided for visual verification.",
    "image_path": r"C:\fake\captures\screenshot_20260522.png",
    "tool": "browser",
}
_SCREENSHOT_RESULT = {  # a deliberate gui screenshot — IS the deliverable
    "ok": True, "action": "screenshot",
    "image_path": r"C:\fake\captures\shot.png", "width": 1920, "height": 1080,
}


class TestActionScreenshotNotInjected(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gemma4_imgguard_"))
        self.agent = _make_agent(self.tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _mode(self, text):
        return choose_mode(text, configured="auto", base_max_tokens=1280)

    def test_action_self_verification_screenshot_not_for_llm(self):
        # The youtube/media verification screenshot must NOT be fed to the LLM.
        mode = self._mode("pon musica en youtube")
        self.assertFalse(
            self.agent._image_is_for_llm(mode, "media", _YOUTUBE_RESULT),
            "an action tool's verification screenshot must not reach the LLM")

    def test_browser_play_screenshot_not_for_llm(self):
        mode = self._mode("pon stranger things en netflix")
        self.assertFalse(
            self.agent._image_is_for_llm(mode, "browser", _YOUTUBE_RESULT))

    def test_deliberate_gui_screenshot_is_for_llm(self):
        # "saca un screenshot" / a gui capture: the image IS the deliverable.
        mode = self._mode("saca un screenshot")
        self.assertTrue(
            self.agent._image_is_for_llm(mode, "gui", _SCREENSHOT_RESULT),
            "a deliberate screenshot tool's image must reach the LLM")

    def test_vision_mode_always_injects(self):
        # In a vision turn even an action-ish tool image is relevant.
        class _M:
            name = "vision_action"
        self.assertTrue(
            self.agent._image_is_for_llm(_M(), "media", _YOUTUBE_RESULT),
            "vision mode must always feed the image to the LLM")

    def test_screenshot_action_value_is_for_llm(self):
        # Even from a non-visual tool name, an explicit capture action counts.
        mode = self._mode("lee la pantalla")
        self.assertTrue(
            self.agent._image_is_for_llm(mode, "app", {"action": "read_screen",
                                                       "image_path": "x.png"}))


if __name__ == "__main__":
    unittest.main()
