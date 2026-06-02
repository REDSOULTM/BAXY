"""--reasoning-budget-message: cierre limpio del thinking cuando se agota el
budget (mejora 2026-06-02).

Sin el flag, llama.cpp fuerza el end-of-thinking tag EN SECO; con él, inyecta
un mensaje corto justo antes para que el modelo "aterrice" la respuesta/tool-call.

Tag de cierre de Gemma 4 = `<channel|>` (verificado contra el chat_template
embebido en el GGUF y contra common_chat_params_init_gemma4() de llama.cpp,
PR ggml-org/llama.cpp#21697). El binario b9090+ acepta el flag (verificado en
`llama-server --help`: env LLAMA_ARG_THINK_BUDGET_MESSAGE).

Estos tests SOLO verifican la CONSTRUCCIÓN del cmd (forma del flag + gate). El
+calidad NO se puede medir sin arrancar el server (prohibido en este harness);
esa validación es viva (forzar el corte del thinking y ver el cierre).
"""
from __future__ import annotations

import os
import unittest

from gemma4_agent.infra.llama_server import llama_command
from gemma4_agent.infra.profiles import PROFILES
from gemma4_agent.infra.config import AgentConfig


_FLAG = "--reasoning-budget-message"
_ENV = "GEMMA4_REASONING_BUDGET_MSG"


def _cmd(profile_name: str = "vram4") -> list[str]:
    return llama_command(AgentConfig.from_env(), PROFILES[profile_name])


class _EnvGuard:
    """Save/restore one env var around a test (no leakage entre tests)."""

    def __init__(self, name: str):
        self.name = name
        self._prev: str | None = None

    def __enter__(self):
        self._prev = os.environ.get(self.name)
        return self

    def set(self, value: str):
        os.environ[self.name] = value

    def unset(self):
        os.environ.pop(self.name, None)

    def __exit__(self, *exc):
        if self._prev is None:
            os.environ.pop(self.name, None)
        else:
            os.environ[self.name] = self._prev
        return False


class ReasoningBudgetMessageTest(unittest.TestCase):

    def test_default_on_flag_present(self):
        # Default (env unset) = ON: el flag aparece bien formado (flag + valor).
        with _EnvGuard(_ENV) as g:
            g.unset()
            cmd = _cmd()
            self.assertIn(_FLAG, cmd)
            idx = cmd.index(_FLAG)
            # El valor debe existir y ser el ARG SIGUIENTE (par flag/valor).
            self.assertLess(idx + 1, len(cmd), "flag sin valor a continuación")
            msg = cmd[idx + 1]
            self.assertTrue(msg.strip(), "mensaje vacío")
            self.assertFalse(msg.startswith("--"), "el valor no debe ser otra flag")

    def test_message_is_plain_text_no_tags(self):
        # El sampler fuerza el end-of-thinking tag DESPUÉS del mensaje; el mensaje
        # debe ser texto plano puro — NO debe traer el tag de cierre ni markdown
        # (si lo trajera, contaminaría el canal de thinking / el reply).
        with _EnvGuard(_ENV) as g:
            g.unset()
            cmd = _cmd()
            msg = cmd[cmd.index(_FLAG) + 1]
            for forbidden in ("<channel|>", "<|channel>", "</think>", "<think>",
                              "<|think|>", "<end_of_turn>", "```", "**", "#"):
                self.assertNotIn(forbidden, msg,
                                 f"mensaje no debe contener {forbidden!r}")

    def test_flag_does_not_break_base_flag_order(self):
        # El flag se agrega DESPUÉS del array base; las flags anti-crash CUDA y
        # de cache deben seguir intactas y en su lugar (anti-regresión CUDA).
        with _EnvGuard(_ENV) as g:
            g.unset()
            cmd = _cmd("vram4")
            # base array sigue completo y ordenado
            self.assertIn("--flash-attn", cmd)
            self.assertIn("--swa-full", cmd)
            self.assertEqual(cmd[cmd.index("-ngl") + 1], "99")
            # el flag nuevo va después de --swa-full (no insertado en el medio)
            self.assertGreater(cmd.index(_FLAG), cmd.index("--swa-full"))

    def test_gate_off_zero(self):
        with _EnvGuard(_ENV) as g:
            for off_val in ("0", "false", "off", "no", ""):
                g.set(off_val)
                cmd = _cmd()
                self.assertNotIn(_FLAG, cmd,
                                 f"GEMMA4_REASONING_BUDGET_MSG={off_val!r} debe desactivar")

    def test_custom_message_override(self):
        with _EnvGuard(_ENV) as g:
            custom = "Concluí ahora."
            g.set(custom)
            cmd = _cmd()
            self.assertIn(_FLAG, cmd)
            self.assertEqual(cmd[cmd.index(_FLAG) + 1], custom)

    def test_applies_to_cpu_profile_too(self):
        # El cierre limpio no depende de GPU/CPU; el flag debe estar en ambos
        # (no se gatea por ngl como las mitigaciones CUDA).
        with _EnvGuard(_ENV) as g:
            g.unset()
            self.assertIn(_FLAG, _cmd("cpu"))


if __name__ == "__main__":
    unittest.main()
