"""Inventario de `except` que TRAGAN en silencio (body == pass) — vía AST (robusto).

Distingue:
  TELEMETRY  = el try solo hace trace/log/event/progress -> tragar está BIEN
               (la telemetría nunca debe tumbar el turno).
  LOGIC      = el try hace lógica real (asignaciones, llamadas no-log) y el except
               la traga sin loguear -> PELIGROSO: esconde bugs (el caso `_os`
               NameError que apagó TODA la validación de reply en silencio).

Reproducible, NO toca nada. Imprime el conteo + los LOGIC sospechosos (file:line).
Lo usa el guard test test_silent_except_ceiling para que el número no CREZCA.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[2] / "gemma4_agent"
_LOGISH = ("trace", "log", "event", "progress", "warn", "debug", "info", "error",
           "print", "emit", "record")


def _is_broad(handler: ast.ExceptHandler) -> bool:
    t = handler.type
    if t is None:
        return True  # bare except:
    names = []
    if isinstance(t, ast.Tuple):
        names = [e.id for e in t.elts if isinstance(e, ast.Name)]
    elif isinstance(t, ast.Name):
        names = [t.id]
    return any(n in ("Exception", "BaseException") for n in names)


def _body_is_silent(handler: ast.ExceptHandler) -> bool:
    # body es solo pass / continue / (un return None)
    b = handler.body
    if len(b) != 1:
        return False
    s = b[0]
    if isinstance(s, (ast.Pass, ast.Continue)):
        return True
    if isinstance(s, ast.Return) and (s.value is None
            or (isinstance(s.value, ast.Constant) and s.value.value is None)):
        return True
    return False


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Attribute):
            return f.attr
        if isinstance(f, ast.Name):
            return f.id
    return ""


def _try_is_only_logging(try_body: list[ast.stmt]) -> bool:
    """True si el try SOLO hace llamadas log/trace (tragar es benigno)."""
    for s in try_body:
        if not isinstance(s, ast.Expr) or not isinstance(s.value, ast.Call):
            return False
        name = _call_name(s.value).lower()
        if not any(tok in name for tok in _LOGISH):
            return False
    return bool(try_body)


def audit() -> tuple[int, int, list[str]]:
    telemetry = 0
    logic = 0
    logic_sites: list[str] = []
    for p in ROOT.rglob("*.py"):
        sp = str(p)
        # vision_input/ = subsistema de cámara EN DESARROLLO por otro workstream (Codex);
        # tiene su propio ciclo de vida -> no se ratchea contra el baseline del agente.
        if ("test" in sp or "_diag" in sp or "__pycache__" in sp
                or "vision_input" in sp):
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        rel = p.relative_to(ROOT.parent)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            for h in node.handlers:
                if not (_is_broad(h) and _body_is_silent(h)):
                    continue
                if _try_is_only_logging(node.body):
                    telemetry += 1
                else:
                    logic += 1
                    logic_sites.append(f"{rel}:{h.lineno}")
    return telemetry, logic, logic_sites


if __name__ == "__main__":
    telemetry, logic, sites = audit()
    print(f"[silent-except] benignos(telemetría)={telemetry}  PELIGROSOS(lógica)={logic}")
    print("[lógica tragada en silencio — top 30]:")
    for s in sites[:30]:
        print(f"  {s}")
