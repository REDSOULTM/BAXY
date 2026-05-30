"""Guarda anti-regresión del bug `_os` (2026-05-30).

INCIDENTE: el refactor R1 (`_execute_turn` -> `_decide_turn` /
`_execute_turn` / `_finalize_turn`, commit 25261147) y antes el commit
a82d439 dejaron en `_finalize_turn` un `_os.environ.get(...)` SIN que
`_os` estuviera bindeado en esa función. En este archivo `os` se importa
SIEMPRE local por-función (`import os as _os`), nunca top-level, así que
`_os` quedó como variable libre no definida.

Resultado: `NameError: name '_os' is not defined` en CADA turno. El
`except Exception` del bloque lo tragaba como `silent_fallback`, así que
la app no crasheaba ruidosamente — simplemente la capa ENTERA de
validación de reply (anti-'Listo', anti-unverified-claim, manos-libres,
narra-todo, delega-al-usuario) NUNCA corría. Bug invisible para los tests
unitarios (que prueban las funciones puras de reply_validator, no el call
site en agent._finalize_turn). Lo agarró solo la prueba EN VIVO.

Esta guarda detecta exactamente esa clase: un nombre USADO (Load) en una
función crítica de turno que NO está bindeado en la función ni es global
de módulo ni builtin. `py_compile`/`pyflakes` no siempre lo marcan dentro
de los venvs del repo, así que lo chequeamos acá explícito y barato (sin
LLM, sin red).

Por qué solo las funciones de turno: son las que el refactor partió y por
las que pasa TODO mensaje del usuario. Un free-var roto ahí = la app
falla catastróficamente en producción.
"""
from __future__ import annotations

import ast
import pathlib
import unittest

# Métodos por los que pasa cada turno del usuario. Si un free-var se
# cuela acá, la app falla en vivo. Ampliar si se extraen más fases.
CRITICAL_METHODS = {
    "_decide_turn",
    "_execute_turn",
    "_finalize_turn",
    "run_content",
}

AGENT_PY = (
    pathlib.Path(__file__).resolve().parent.parent
    / "agent_core" / "agent.py"
)


def _module_level_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for n in tree.body:
        if isinstance(n, ast.Import):
            for a in n.names:
                names.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                names.add(a.asname or a.name)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            names.add(n.target.id)
    return names


def _bound_in_func(fn: ast.AST) -> set[str]:
    """Nombres que la función bindea (args, asignaciones, imports, for,
    with, comprehensions, except-as, nested defs, lambdas)."""
    bound: set[str] = set()
    args = getattr(fn, "args", None)
    if args is not None:
        for a in list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs):
            bound.add(a.arg)
        if args.vararg:
            bound.add(args.vararg.arg)
        if args.kwarg:
            bound.add(args.kwarg.arg)
    for c in ast.walk(fn):
        if isinstance(c, ast.Import):
            for a in c.names:
                bound.add((a.asname or a.name).split(".")[0])
        elif isinstance(c, ast.ImportFrom):
            for a in c.names:
                bound.add(a.asname or a.name)
        elif isinstance(c, ast.Assign):
            for t in c.targets:
                for nn in ast.walk(t):
                    if isinstance(nn, ast.Name):
                        bound.add(nn.id)
        elif isinstance(c, ast.AnnAssign) and isinstance(c.target, ast.Name):
            bound.add(c.target.id)
        elif isinstance(c, ast.AugAssign) and isinstance(c.target, ast.Name):
            bound.add(c.target.id)
        elif isinstance(c, (ast.For, ast.AsyncFor)):
            for nn in ast.walk(c.target):
                if isinstance(nn, ast.Name):
                    bound.add(nn.id)
        elif isinstance(c, (ast.With, ast.AsyncWith)):
            for item in c.items:
                if item.optional_vars:
                    for nn in ast.walk(item.optional_vars):
                        if isinstance(nn, ast.Name):
                            bound.add(nn.id)
        elif isinstance(c, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            for gen in c.generators:
                for nn in ast.walk(gen.target):
                    if isinstance(nn, ast.Name):
                        bound.add(nn.id)
        elif isinstance(c, ast.ExceptHandler) and c.name:
            bound.add(c.name)
        elif isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bound.add(c.name)
        elif isinstance(c, ast.Lambda):
            for a in c.args.args:
                bound.add(a.arg)
        elif isinstance(c, ast.Name) and isinstance(c.ctx, (ast.Store, ast.Del)):
            bound.add(c.id)
        elif isinstance(c, (ast.Global, ast.Nonlocal)):
            bound.update(c.names)
    return bound


def _loaded_in_func(fn: ast.AST) -> set[str]:
    loaded: set[str] = set()
    for c in ast.walk(fn):
        if isinstance(c, ast.Name) and isinstance(c.ctx, ast.Load):
            loaded.add(c.id)
    return loaded


class TestNoStrandedFreeVars(unittest.TestCase):
    def test_turn_methods_have_no_unbound_names(self):
        import builtins

        src = AGENT_PY.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(AGENT_PY))
        module_names = _module_level_names(tree)
        builtin_names = set(dir(builtins))

        # Recolectar los métodos críticos (pueden estar anidados en la clase).
        funcs: dict[str, ast.AST] = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and node.name in CRITICAL_METHODS:
                funcs[node.name] = node

        missing = CRITICAL_METHODS - set(funcs)
        self.assertFalse(
            missing,
            f"No encontré estos métodos en agent.py (¿renombrados?): {sorted(missing)}. "
            "Actualizá CRITICAL_METHODS.",
        )

        offenders: list[str] = []
        for name, fn in funcs.items():
            bound = _bound_in_func(fn)
            loaded = _loaded_in_func(fn)
            for nm in sorted(loaded):
                if nm == "self":
                    continue
                if nm in bound or nm in module_names or nm in builtin_names:
                    continue
                offenders.append(f"{name}: usa `{nm}` sin bindearlo (free var)")

        self.assertEqual(
            offenders,
            [],
            "Variable(s) libre(s) no bindeada(s) en función de turno — clase del "
            "bug `_os` de 2026-05-30 (NameError en cada turno, tragado por "
            "silent_fallback). Bindealas (import local o asignación) en su "
            "scope.\n  " + "\n  ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
