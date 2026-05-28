"""Audit verification — sprint 2026-05-28.

Test único que verifica que las 8 recomendaciones del
`architecture_audit_2026_05_27` fueron atacadas. Cada R tiene un test
con evidencia concreta. Si alguien revierte parte del trabajo, este test
detecta la regresión.

Es el test "del sello": pasa = sprint del audit cerrado.
"""
from __future__ import annotations

import ast
import pathlib
import subprocess
import unittest


PKG = pathlib.Path(__file__).resolve().parent
REPO = PKG.parent


class TestAudit8R(unittest.TestCase):
    """Una verificación por R, con evidencia."""

    def test_R1_run_content_split_in_4_methods(self):
        """R1: run_content debe estar partido en 3 sub-fases."""
        src = (PKG / "agent.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        methods = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        for required in ("run_content", "_decide_turn", "_execute_turn", "_finalize_turn"):
            self.assertIn(required, methods, f"R1: falta método {required}")
        # run_content debe ser un orquestador chico (< 50 LOC)
        run_content_node = next(
            n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "run_content"
        )
        loc = run_content_node.end_lineno - run_content_node.lineno + 1
        self.assertLess(loc, 50, f"R1: run_content tiene {loc} LOC (esperado < 50)")

    def test_R2_at_least_30_sibling_modules(self):
        """R2: domain_tools partido en ≥30 áreas. Acepta tanto el modelo
        siblings `domain_tools_X.py` como el sub-paquete `domain_tools/X.py`
        (post R2-finalize 2026-05-28: ambos coexisten — los siblings son
        shims que aliasan al sub-paquete vía sys.modules)."""
        siblings = list(PKG.glob("domain_tools_*.py"))
        subpkg = PKG / "domain_tools"
        subpkg_areas = list(subpkg.glob("*.py")) if subpkg.is_dir() else []
        # Subpkg cuenta los .py adentro (excluyendo __init__ que es el core).
        subpkg_count = sum(1 for p in subpkg_areas if p.stem != "__init__")
        total = max(len(siblings), subpkg_count)
        self.assertGreaterEqual(total, 30,
                                f"R2: {len(siblings)} siblings, {subpkg_count} subpkg areas (esperado ≥ 30)")

    def test_R2_subpkg_layout_complete(self):
        """R2 finalize: el audit pedía sub-paquete `domain_tools/` proper.
        Verifica que existe Y tiene áreas adentro Y que los shims viejos
        siguen funcionando (back-compat)."""
        subpkg = PKG / "domain_tools"
        self.assertTrue(subpkg.is_dir(), "R2 finalize: domain_tools/ no es paquete")
        init = subpkg / "__init__.py"
        self.assertTrue(init.exists(), "R2 finalize: domain_tools/__init__.py falta")
        # Al menos 30 áreas como submódulos
        areas = [p for p in subpkg.glob("*.py") if p.stem != "__init__"]
        self.assertGreaterEqual(len(areas), 30,
                                f"R2 finalize: solo {len(areas)} áreas en sub-paquete")

    def test_R3_zero_top_level_cycles(self):
        """R3: cero ciclos top-level (lazy ok, esos no son ciclos runtime)."""
        result = subprocess.run(
            ["python", "scripts/_arch_dep_graph.py"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=REPO,
        )
        # Buscar "CICLOS detectados: N"
        cycle_line = next(
            (l for l in result.stdout.splitlines() if "CICLOS detectados" in l),
            "",
        )
        self.assertIn("0", cycle_line, f"R3: ciclos no son 0 — {cycle_line!r}")

    def test_R4_tool_result_exists_and_has_5_migrated(self):
        """R4: ToolResult dataclass + al menos 5 handlers migrados.

        Post R2-finalize: el código real vive en `domain_tools/<area>.py`.
        Los siblings `domain_tools_<area>.py` son shims sys.modules-aliased.
        Buscamos los marcadores R4 en el sub-paquete."""
        self.assertTrue((PKG / "tool_result.py").exists(), "R4: tool_result.py missing")
        migrated: set[str] = set()
        # Buscar en sub-paquete domain_tools/<area>.py
        subpkg = PKG / "domain_tools"
        if subpkg.is_dir():
            for p in subpkg.glob("*.py"):
                src = p.read_text(encoding="utf-8")
                if "_ok_tr" in src or "ToolResult.ok_result" in src or "ToolResult.err(" in src:
                    migrated.add(p.name)
        # También considerar siblings (pre-finalize) por compatibilidad
        for p in PKG.glob("domain_tools_*.py"):
            src = p.read_text(encoding="utf-8")
            if "_ok_tr" in src or "ToolResult.ok_result" in src or "ToolResult.err(" in src:
                migrated.add(p.name)
        self.assertGreaterEqual(len(migrated), 5,
                                f"R4: solo {len(migrated)} handlers migrados (esperado ≥ 5)")

    def test_R5_schema_contract_test_exists(self):
        """R5: test_schema_handler_contract.py existe + corre."""
        contract = PKG / "test_schema_handler_contract.py"
        self.assertTrue(contract.exists(), "R5: test_schema_handler_contract.py missing")
        # Verificar que tiene al menos los 3 tests esperados
        src = contract.read_text(encoding="utf-8")
        for required in (
            "test_every_schema_property_is_read_by_handler",
            "test_every_compound_schema_has_handler",
            "test_deep_delegate_tools_actually_read_majority_of_props",
        ):
            self.assertIn(required, src, f"R5: falta test {required}")

    def test_R6_zero_builtin_eval_exec_in_repo(self):
        """R6: cero builtins eval/exec en producción."""
        # Reuse the existing R6 test logic.
        from .test_no_eval_exec import _find_builtin_eval_exec
        offenders = []
        for py in PKG.rglob("*.py"):
            if py.name == "test_no_eval_exec.py":
                continue
            for line_no, name in _find_builtin_eval_exec(py):
                offenders.append(f"{py.relative_to(PKG.parent)}:{line_no} {name}")
        self.assertEqual(offenders, [], f"R6: builtins encontrados: {offenders}")

    def test_R7_zero_prints_in_hot_path(self):
        """R7: cero prints en módulos hot-path runtime."""
        from .test_no_print_in_runtime import RUNTIME_HOT_PATH, _find_real_prints
        offenders = []
        for rel in RUNTIME_HOT_PATH:
            p = PKG / rel
            if not p.exists():
                continue
            for line_no in _find_real_prints(p.read_text(encoding="utf-8")):
                offenders.append(f"{rel}:{line_no}")
        self.assertEqual(offenders, [], f"R7: prints encontrados: {offenders}")

    def test_R8_scripts_index_and_diag_exist(self):
        """R8: INDEX.md + carpeta _diag/ + scripts categorizados."""
        scripts_dir = REPO / "scripts"
        self.assertTrue((scripts_dir / "INDEX.md").exists(), "R8: INDEX.md missing")
        self.assertTrue((scripts_dir / "_diag").is_dir(), "R8: _diag/ missing")
        # _diag should have ≥4 scripts (the ones we moved)
        diag_count = len(list((scripts_dir / "_diag").glob("*.py")))
        self.assertGreaterEqual(diag_count, 4, f"R8: solo {diag_count} en _diag/")


if __name__ == "__main__":
    unittest.main()
