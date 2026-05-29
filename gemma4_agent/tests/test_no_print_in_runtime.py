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


def _find_fstring_in_logger(src: str) -> list[int]:
    """Devuelve `lineno` de calls `logger.<level>(f"...")` — anti-pattern
    de performance porque el f-string se evalúa SIEMPRE aunque el nivel
    no esté activo. R7 sprint del audit recomienda lazy logging
    `logger.warning("X=%s", x)`.
    """
    import ast as _ast
    try:
        tree = _ast.parse(src)
    except SyntaxError:
        return []
    out: list[int] = []
    levels = {"debug", "info", "warning", "error", "critical", "exception"}
    for node in _ast.walk(tree):
        if not isinstance(node, _ast.Call):
            continue
        if not isinstance(node.func, _ast.Attribute):
            continue
        if node.func.attr not in levels:
            continue
        # Solo `logger.<level>` / `log.<level>` / `_log.<level>`
        if not isinstance(node.func.value, _ast.Name):
            continue
        receiver = node.func.value.id
        if receiver not in {"logger", "log", "_log", "LOG"}:
            continue
        # Detecta f-string como PRIMER argumento (el mensaje).
        if not node.args:
            continue
        first = node.args[0]
        if isinstance(first, _ast.JoinedStr):
            out.append(node.lineno)
    return out


class TestNoPrintInRuntime(unittest.TestCase):
    """Los módulos de hot-path NO deben tener `print()`. Logger
    estructurado (logger.info/debug/warning) o trace.event(...).
    """

    def test_no_print_in_runtime_modules(self):
        root = pathlib.Path(__file__).resolve().parent.parent  # gemma4_agent/
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

    def test_no_fstring_in_hot_path_logger_calls(self):
        """R7 sprint 2026-05-28: `logger.warning(f"X={x}")` evalúa el
        f-string siempre, aunque el nivel no esté activo. Usar lazy:
        `logger.warning("X=%s", x)`.

        Solo se chequea en hot-path runtime para no romper código
        legacy de CLIs. Si fuera trivial migrar todo, sería un sprint
        dedicado.
        """
        root = pathlib.Path(__file__).resolve().parent.parent
        offenders: list[str] = []
        for relpath in RUNTIME_HOT_PATH:
            p = root / relpath
            if not p.exists():
                continue
            txt = p.read_text(encoding="utf-8", errors="replace")
            for line_no in _find_fstring_in_logger(txt):
                offenders.append(f"{relpath}:{line_no}")
        # Estado actual: 0 offenders en hot-path. Hard guard: si alguien
        # introduce uno nuevo, este test lo bloquea.
        self.assertEqual(
            offenders, [],
            f"f-string en logger del hot-path: {len(offenders)} casos. "
            f"Anti-pattern: `logger.warning(f\"X={{x}}\")` evalúa el f-string "
            f"aunque el nivel no esté activo. Reemplazá por "
            f"`logger.warning(\"X=%s\", x)`. Lista:\n  "
            + "\n  ".join(offenders[:15]),
        )


if __name__ == "__main__":
    unittest.main()
