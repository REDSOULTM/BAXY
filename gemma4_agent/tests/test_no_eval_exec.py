"""R6 audit (2026-05-28): asegurar que no entran `eval` ni `exec` builtin a
producción.

El audit `architecture_audit_2026_05_27.md` contó 5 ocurrencias de
"eval/exec" en prod; el follow-up de R6 confirmó que las 5 son
`QApplication.exec()` / `QDialog.exec()` de PyQt6 (métodos de objetos Qt
para entrar al event loop), NO el `exec` builtin. CERO riesgo de
inyección.

Este test es la guarda anti-regresión: si alguien introduce un
`eval(...)` o `exec(...)` builtin nuevo (no método), el test lo detecta.
Whitelist explícita para los 5 conocidos de PyQt.

Por qué importa: el agente recibe input del LLM (no confiable) y lo mete
en tools que tocan el SO. Una inyección via `eval` mal usado sería el
peor bug posible.
"""
from __future__ import annotations

import ast
import pathlib
import unittest


# Permitidos: cada uno es method call `<expr>.exec(...)`, NO builtin.
# (Las entradas de gemma4_agent/ui/* se quitaron al eliminar la GUI vieja
# PyQt6 el 2026-06-03 — ya no hay .exec() de Qt en el repo.)
ALLOWED: set[str] = set()


def _is_method_call(node: ast.Call) -> bool:
    """True si la call es method (obj.method(...)) — NO builtin."""
    return isinstance(node.func, ast.Attribute)


def _find_builtin_eval_exec(path: pathlib.Path) -> list[tuple[int, str]]:
    """Devuelve [(lineno, 'eval'|'exec')] de uses de builtin eval/exec en el file."""
    try:
        src = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError:
        return []
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _is_method_call(node):
            continue  # obj.eval() / obj.exec() — Qt o similar
        if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
            hits.append((node.lineno, node.func.id))
    return hits


class TestNoBuiltinEvalExec(unittest.TestCase):
    """Producción no debe usar `eval` ni `exec` builtin.

    Si necesitás parsear un literal Python, usá `ast.literal_eval`. Si
    necesitás ejecutar código dinámico, replanteá el diseño — casi nunca
    es necesario en este repo.
    """

    def test_no_builtin_eval_exec_in_package(self):
        root = pathlib.Path(__file__).resolve().parent.parent  # gemma4_agent/
        offenders: list[str] = []
        for py in root.rglob("*.py"):
            if py.name == "test_no_eval_exec.py":  # skip self
                continue
            # Skip vendored deps (node_modules, etc) — no son código del repo.
            if "node_modules" in py.parts:
                continue
            hits = _find_builtin_eval_exec(py)
            for lineno, name in hits:
                offenders.append(f"{py.relative_to(root.parent)}:{lineno} `{name}(...)`")
        self.assertEqual(
            offenders, [],
            "Builtin eval/exec encontrado(s). Reemplazar por "
            "ast.literal_eval, JSON, o parser explícito.\n"
            "Lista:\n  " + "\n  ".join(offenders),
        )

    def test_no_builtin_eval_exec_in_scripts(self):
        root = pathlib.Path(__file__).resolve().parent.parent.parent / "scripts"
        offenders: list[str] = []
        for py in root.rglob("*.py"):
            hits = _find_builtin_eval_exec(py)
            for lineno, name in hits:
                offenders.append(f"scripts/{py.relative_to(root)}:{lineno} `{name}(...)`")
        self.assertEqual(
            offenders, [],
            "Builtin eval/exec encontrado(s) en scripts/. Reemplazar.\n"
            "Lista:\n  " + "\n  ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
