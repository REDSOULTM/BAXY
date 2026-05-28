"""Audit metrics 2026-05-28: este test mide en frío las métricas duras
del estado final del sprint. Sirve como dashboard ejecutable.

Si el repo crece o degrada, esos números cambiarán. Cada uno tiene un
piso (lower bound) tras el sprint que debe mantenerse.
"""
from __future__ import annotations

import ast
import pathlib
import re
import unittest


PKG = pathlib.Path(__file__).resolve().parent  # gemma4_agent/
REPO = PKG.parent


def _iter_prod_py():
    """Itera los .py productivos del paquete (sin tests, sin node_modules)."""
    for p in PKG.rglob("*.py"):
        if "node_modules" in p.parts:
            continue
        if p.name.startswith("test_"):
            continue
        yield p


class TestAuditMetrics(unittest.TestCase):
    """Métricas del repo tras el sprint del audit (2026-05-28).

    Pisos (lower bounds) verificados en el cierre del sprint. Si fallan,
    significa que se introdujo deuda nueva — investigar.
    """

    # ----- R1: run_content estructura -----

    def test_metric_run_content_orchestrator_size(self):
        """run_content quedó como orquestador chico (≤ 50 LOC)."""
        src = (PKG / "agent.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        rc = next(
            (n for n in ast.walk(tree)
             if isinstance(n, ast.FunctionDef) and n.name == "run_content"),
            None,
        )
        self.assertIsNotNone(rc, "run_content not found")
        loc = rc.end_lineno - rc.lineno + 1
        self.assertLessEqual(loc, 50, f"run_content grew to {loc} LOC (esperado ≤ 50)")

    def test_metric_three_phase_methods_exist(self):
        """Las 3 fases del R1 siguen existiendo."""
        src = (PKG / "agent.py").read_text(encoding="utf-8")
        for required in ("_decide_turn", "_execute_turn", "_finalize_turn"):
            self.assertIn(f"def {required}(", src, f"R1: falta {required}")

    # ----- R2: sub-paquete domain_tools/ -----

    def test_metric_subpkg_has_at_least_30_areas(self):
        subpkg = PKG / "domain_tools"
        self.assertTrue(subpkg.is_dir(), "R2: subpkg missing")
        areas = [p for p in subpkg.glob("*.py") if p.stem != "__init__"]
        self.assertGreaterEqual(len(areas), 30,
                                f"R2: solo {len(areas)} áreas en sub-paquete")

    def test_metric_back_compat_shims_match_subpkg(self):
        """Por cada área en domain_tools/, debe haber su shim
        domain_tools_<area>.py para back-compat."""
        subpkg = PKG / "domain_tools"
        areas = {p.stem for p in subpkg.glob("*.py") if p.stem != "__init__"}
        shims = {p.stem.replace("domain_tools_", "") for p in PKG.glob("domain_tools_*.py")}
        missing = areas - shims
        # `helpers` puede no necesitar shim — solo el set público
        missing.discard("helpers")
        self.assertEqual(
            missing, set(),
            f"R2: áreas en subpkg sin shim back-compat: {missing}"
        )

    # ----- R3: ciclos -----

    def test_metric_zero_top_level_cycles(self):
        """0 ciclos top-level. Verificado via _arch_dep_graph.py."""
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "scripts/_arch_dep_graph.py"],
            capture_output=True, text=True, errors="replace",
            cwd=REPO,
        )
        cycle_line = next(
            (l for l in result.stdout.splitlines() if "CICLOS detectados" in l),
            "",
        )
        # Format: "# CICLOS detectados: N"
        match = re.search(r"detectados:\s*(\d+)", cycle_line)
        n = int(match.group(1)) if match else -1
        self.assertEqual(n, 0, f"R3: {n} ciclos top-level detectados")

    def test_metric_lazy_imports_under_500(self):
        """Lazy imports totales en producción < 500 (sprint dejó ~460).
        Si crece mucho, alguien introdujo lazy en vez de top-level."""
        total = 0
        for p in _iter_prod_py():
            try:
                src = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            total += len(re.findall(r"^\s+from \.", src, re.M))
        self.assertLess(
            total, 500,
            f"R3: {total} lazy imports en producción (techo 500)"
        )

    # ----- R4: ToolResult disponible -----

    def test_metric_tool_result_dataclass_available(self):
        from gemma4_agent.tool_result import ToolResult
        # Verifica API mínima
        self.assertTrue(hasattr(ToolResult, "ok_result"))
        self.assertTrue(hasattr(ToolResult, "err"))
        self.assertTrue(hasattr(ToolResult, "to_dict"))
        self.assertTrue(hasattr(ToolResult, "from_dict"))

    # ----- R6: zero builtins, zero bare except -----

    def test_metric_zero_builtin_eval_exec_in_prod(self):
        from .test_no_eval_exec import _find_builtin_eval_exec
        for p in _iter_prod_py():
            hits = _find_builtin_eval_exec(p)
            self.assertEqual(
                hits, [],
                f"R6: builtin eval/exec en {p.relative_to(PKG.parent)}: {hits}"
            )

    def test_metric_zero_bare_except_in_prod(self):
        from .test_no_bare_except import _find_bare_except
        for p in _iter_prod_py():
            hits = _find_bare_except(p)
            self.assertEqual(
                hits, [],
                f"R6: bare-except en {p.relative_to(PKG.parent)}:{hits}"
            )

    # ----- R7: zero prints en hot-path, zero f-strings en logger -----

    def test_metric_zero_fstrings_in_logger_calls_total(self):
        """f-strings en logger.X(f"...") evalúan siempre — anti-pattern.
        El sprint dejó 0 en TODO el repo."""
        from .test_no_print_in_runtime import _find_fstring_in_logger
        total = 0
        for p in _iter_prod_py():
            try:
                src = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            total += len(_find_fstring_in_logger(src))
        self.assertEqual(total, 0,
                         f"R7: {total} f-strings en logger calls (techo 0)")

    # ----- R8: scripts/INDEX.md -----

    def test_metric_index_lists_all_top_level_scripts(self):
        scripts_dir = REPO / "scripts"
        idx = (scripts_dir / "INDEX.md").read_text(encoding="utf-8")
        missing = [p.name for p in scripts_dir.glob("*.py") if p.name not in idx]
        self.assertEqual(missing, [], f"R8: scripts sin entrada en INDEX: {missing}")


if __name__ == "__main__":
    unittest.main()
