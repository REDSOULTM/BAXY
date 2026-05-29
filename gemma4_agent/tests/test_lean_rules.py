"""Tests para las reglas LEAN (opt-in GEMMA4_LEAN_RULES, dormant por default).

MOCKS (sin modelo/GPU):
  - wiring: flag on -> _load_tool_rules carga <rule>.lean.md; off -> <rule>.md
  - las lean son MAS CHICAS que las originales (el punto: menos tokens -> menos prefill)
  - las lean PRESERVAN los anti-patrones/bugfixes criticos (no se podaron a ciegas)

La CALIDAD real (que el modelo rutee bien con la lean) NO se cubre aca: el E2B es
no-determinista, eso es validacion EN VIVO. Ver PLAN_optimizacion_prompt_tokens.md.
"""
import os
import unittest
from pathlib import Path

from ..agent_core import agent_prompt

RULES = Path(agent_prompt._TOOL_RULES_DIR)

# rule -> tokens criticos (anti-patrones/bugfixes) que la lean DEBE conservar.
CRITICAL = {
    "media": ["via_cdp", "spotify_user", "streaming_profile", "para el video", "youtube_play"],
    "browser": ["ANTI-URL-FABRICATION", "youtube.com", "browser.search",
                'window(action="minimize"', "payment"],
    "routine": ["on_phrase", "on_app_open", "cron", "once", "CAPABILITY HONESTY", "NOT execute"],
    "app": ["launch_requested", "verified", "INSTALLED", "low_confidence"],
    "system": ["calculator", "ANTI-HALLUCINATION", "shutdown", "gui(action='type'"],
    "audio": ["mute(state", "set_default", "media_stop", "unmute"],
    "gui": ["uia(", "keypress", "filesystem", "OPERATE AN OPEN APP"],
}


class _LeanEnv:
    def __init__(self, on: bool):
        self.on = on
        self.prev = None

    def __enter__(self):
        self.prev = os.environ.get("GEMMA4_LEAN_RULES")
        if self.on:
            os.environ["GEMMA4_LEAN_RULES"] = "1"
        else:
            os.environ["GEMMA4_LEAN_RULES"] = "0"  # v22: default es ON, off explícito
        return self

    def __exit__(self, *exc):
        if self.prev is None:
            os.environ.pop("GEMMA4_LEAN_RULES", None)
        else:
            os.environ["GEMMA4_LEAN_RULES"] = self.prev


class TestLeanRules(unittest.TestCase):
    def test_lean_files_exist(self):
        for name in CRITICAL:
            self.assertTrue((RULES / f"{name}.lean.md").is_file(), f"falta {name}.lean.md")

    def test_flag_on_loads_lean(self):
        with _LeanEnv(True):
            rules = agent_prompt._load_tool_rules()
            for name in CRITICAL:
                lean_text = (RULES / f"{name}.lean.md").read_text(encoding="utf-8")
                self.assertEqual(rules[name], lean_text, f"{name}: flag on debe cargar .lean.md")

    def test_flag_off_loads_original(self):
        with _LeanEnv(False):
            rules = agent_prompt._load_tool_rules()
            for name in CRITICAL:
                orig = (RULES / f"{name}.md").read_text(encoding="utf-8")
                self.assertEqual(rules[name], orig, f"{name}: flag off debe cargar .md (sin cambio)")

    def test_lean_is_smaller(self):
        for name in CRITICAL:
            orig = len((RULES / f"{name}.md").read_text(encoding="utf-8"))
            lean = len((RULES / f"{name}.lean.md").read_text(encoding="utf-8"))
            self.assertLess(lean, orig, f"{name}: lean ({lean}) no es mas chica que orig ({orig})")

    def test_lean_preserves_critical_tokens(self):
        for name, toks in CRITICAL.items():
            lean = (RULES / f"{name}.lean.md").read_text(encoding="utf-8")
            for t in toks:
                self.assertIn(t, lean, f"{name}.lean.md PODO un token critico: {t!r}")


if __name__ == "__main__":
    unittest.main()
