"""R7 sprint 2026-05-28: prevenir prints en módulos runtime productivos.

El audit `architecture_audit_2026_05_27.md` contó 195 `print()` (78 en
archivos no-CLI). Análisis ulterior: la mayoría vive en CLIs interactivos
(`chat.py`, `launcher.py`, `microagents.py`) donde print es la UX
legítima, y en scripts diagnósticos one-shot.

Este test **no migra los prints existentes** (sería un sprint dedicado;
y para chat/launcher el comportamiento del print es deliberado). Lo que
hace es **guardia anti-regresión** sobre los módulos del HOT PATH del
runtime de voz/agente — esos no deben usar `print()` porque rompen el
flujo de logs estructurados que el operador usa para post-mortem.

Hot-path runtime modules (whitelist explícita):
"""
from __future__ import annotations

import re
import pathlib
import unittest


# Módulos del hot-path runtime de voz/agente. Estos NUNCA deben usar
# `print()` — todo va via logger.* + trace.event(). Lista explícita para
# no expandir el scope accidentalmente.
RUNTIME_HOT_PATH = {
    "agent.py",
    "agent_dispatch.py",
    "agent_guards.py",
    "agent_runner.py",
    "agent_prompt.py",
    "llm_client.py",
    "llama_server.py",
    "planner.py",
    "semantic_router.py",
    "intent_router.py",
    "modes.py",
    "memory.py",
    "state.py",
    "tools.py",
    "domain_tools.py",
    "tracing.py",
    # voice/
    "voice/pipeline.py",
    "voice/stt.py",
    "voice/tts.py",
    "voice/wake.py",
    "voice/vad.py",
    "voice/audio_io.py",
}


def _find_real_prints(src: str) -> list[int]:
    """Devuelve los `lineno` de print() reales — usa AST para descartar
    matches dentro de docstrings, comments y strings."""
    import ast
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    out: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "print":
                out.append(node.lineno)
    return out


class TestNoPrintInRuntime(unittest.TestCase):
    """Los módulos de hot-path NO deben tener `print()`. Logger
    estructurado (logger.info/debug/warning) o trace.event(...).
    """

    def test_no_print_in_runtime_modules(self):
        root = pathlib.Path(__file__).resolve().parent  # gemma4_agent/
        offenders: list[str] = []
        for relpath in RUNTIME_HOT_PATH:
            p = root / relpath
            if not p.exists():
                continue  # módulo opcional / movido
            txt = p.read_text(encoding="utf-8", errors="replace")
            for line_no in _find_real_prints(txt):
                offenders.append(f"{relpath}:{line_no}")
        self.assertEqual(
            offenders, [],
            "print() detectado en hot-path runtime. Reemplazar por "
            "logger.{info,debug,warning} o trace.event(). Lista:\n  "
            + "\n  ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
