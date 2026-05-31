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


PKG = pathlib.Path(__file__).resolve().parent.parent  # gemma4_agent/ (tests/ es subdir)
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
        src = (PKG / "agent_core" / "agent.py").read_text(encoding="utf-8")  # reorg 2026-05-28: agent.py vive en agent_core/
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
        src = (PKG / "agent_core" / "agent.py").read_text(encoding="utf-8")  # reorg 2026-05-28: agent.py vive en agent_core/
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
        """Por cada área en domain_tools/, debe haber su alias back-compat
        importable como `gemma4_agent.domain_tools_<area>`.

        Reorg 2026-05-28: los shims fueron consolidados de archivos .py
        sueltos a `sys.modules` aliasing en `gemma4_agent/__init__.py` para
        limpiar la raíz del paquete. Esto verifica el ALIAS efectivo, no
        el archivo en disco."""
        import importlib
        subpkg = PKG / "domain_tools"
        areas = {p.stem for p in subpkg.glob("*.py") if p.stem != "__init__"}
        # `helpers` puede no necesitar shim — solo el set público
        areas.discard("helpers")
        missing = set()
        for area in areas:
            try:
                importlib.import_module(f"gemma4_agent.domain_tools_{area}")
            except ImportError:
                missing.add(area)
        self.assertEqual(
            missing, set(),
            f"R2: áreas en subpkg sin alias back-compat: {missing}"
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

    def test_metric_lazy_imports_under_525(self):
        """Lazy imports totales en producción < 525 (sprint dejó ~460; HEAD pre-R3.3
        ya estaba en 507 — deuda preexistente). R3.3 (2026-05-30) sumó +1: el lazy
        `from ..routing.semantic_router import embed` en microagents._default_embed_fn
        es INTENCIONAL — top-level cargaría el encoder (sentence-transformers) al
        importar microagents, ralentizando el boot. R-Jarvis CAPA VIVA (2026-05-30)
        suma +5 JUSTIFICADOS: el lazy `from ..memory_pkg.ambient_observer import
        AmbientObserver` evita cargar `winsdk` (dep pesada Windows-only) al importar el
        agente, y 4 `from ..memory_pkg.taste_profile import ...` viven en bloques
        best-effort. R-Jarvis REFLEXIÓN-LLM (2026-05-30) suma +4: 3 en agent.py
        (reflection_block/maybe_refresh_async/forget_reflection/cached_insights, mismo
        patrón best-effort opt-in) + 1 en taste_reflection.py (`resolve_turn_model` de
        infra/llama_server, pesado, lazy a propósito; los imports livianos del módulo
        —taste_profile, behavior_log— SÍ son top-level). Techo 520→525 por eso.
        COMPUTER-USE Etapa 1+2 (2026-05-31) suma +3 lazy `from ..routing.command_splitter
        import ...` en agent.py, TODOS mismo patrón anti-circular (routing<->agent):
        extract_app_action+split_command (app-action routing, _decide_turn), parse_type_action
        (plan determinista focus+type), is_dependent_open (encadenamiento dependiente
        'instalá X y abrilo' en _run_multi_intent). Techo 525→528. Si crece mucho MÁS,
        alguien introdujo lazy en vez de top-level sin justificación."""
        total = 0
        for p in _iter_prod_py():
            try:
                src = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            total += len(re.findall(r"^\s+from \.", src, re.M))
        self.assertLess(
            total, 528,
            f"R3: {total} lazy imports en producción (techo 528)"
        )

    # ----- R4: ToolResult disponible -----

    def test_metric_tool_result_dataclass_available(self):
        from gemma4_agent.tools_pkg.tool_result import ToolResult
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

    # ----- audit §8: reproducibilidad (data/ README) -----

    def test_metric_data_dir_has_reproducibility_readme(self):
        """audit §8: cada `.npz` / `.bin` / `.pkl` debería tener receta
        documentada. README en `gemma4_agent/data/` documenta cómo se
        regenera cada artefacto."""
        readme = PKG / "data" / "README.md"
        self.assertTrue(readme.exists(), f"audit §8: {readme} missing")
        text = readme.read_text(encoding="utf-8")
        # Cada `.npz` actual debe estar mencionado en el README
        data_dir = PKG / "data"
        if data_dir.is_dir():
            npz_files = list(data_dir.glob("*.npz"))
            for npz in npz_files:
                self.assertIn(
                    npz.name, text,
                    f"audit §8: {npz.name} no documentado en data/README.md"
                )

    # ----- runtime health -----

    def test_metric_all_prod_modules_import_cleanly(self):
        """Todo el paquete prod importa sin error."""
        import importlib, pkgutil
        import gemma4_agent
        errors = []
        for mod_info in pkgutil.walk_packages(
            gemma4_agent.__path__, prefix="gemma4_agent."
        ):
            if "test_" in mod_info.name:
                continue
            if "node_modules" in mod_info.name:
                continue
            try:
                importlib.import_module(mod_info.name)
            except Exception as exc:
                errors.append((mod_info.name, f"{type(exc).__name__}: {exc}"))
        self.assertEqual(
            errors, [],
            f"{len(errors)} módulos rotos:\n  "
            + "\n  ".join(f"{n}: {e[:120]}" for n, e in errors[:5])
        )

    def test_metric_zero_mutable_default_args(self):
        """Audit hygiene: cero funciones con default args mutables
        (`def f(x=[])`, `def f(d={})`). Anti-pattern típico: el default
        se comparte entre llamadas y acumula state."""
        offenders = []
        for p in _iter_prod_py():
            try:
                tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for d in node.args.defaults:
                        if isinstance(d, (ast.List, ast.Dict, ast.Set)):
                            offenders.append(
                                f"{p.relative_to(PKG.parent)}:{node.lineno} def {node.name}(...)"
                            )
        self.assertEqual(
            offenders, [],
            f"Mutable default args (pickled state across calls):\n  "
            + "\n  ".join(offenders[:10])
        )

    def test_metric_zero_trivial_tests(self):
        """Audit hygiene: cero tests cuyo cuerpo es solo `pass` o
        solo un docstring (no asserts). Esos tests dan falsa sensación
        de coverage."""
        trivial = []
        for p in PKG.rglob("test_*.py"):
            if "node_modules" in p.parts:
                continue
            try:
                tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                    if len(node.body) == 1:
                        stmt = node.body[0]
                        if isinstance(stmt, ast.Pass):
                            trivial.append(f"{p.relative_to(PKG.parent)}:{node.lineno} {node.name}")
                        elif (isinstance(stmt, ast.Expr)
                              and isinstance(stmt.value, ast.Constant)):
                            trivial.append(f"{p.relative_to(PKG.parent)}:{node.lineno} {node.name}")
        self.assertEqual(
            trivial, [],
            f"Trivial tests (pass-only or docstring-only):\n  "
            + "\n  ".join(trivial[:10])
        )

    def test_metric_real_todos_under_5(self):
        """Audit hygiene: TODO/FIXME reales en producción ≤ 5.
        Filtramos el "todo" castellano (pronombre indefinido) usando
        pattern explícito `# TODO:` / `# FIXME:` / `# XXX:` / `# HACK:`."""
        pattern = re.compile(r"#\s*(TODO|FIXME|XXX|HACK)(\s*[:(]|$)")
        total = 0
        for p in _iter_prod_py():
            src = p.read_text(encoding="utf-8", errors="replace")
            total += sum(1 for line in src.splitlines() if pattern.search(line))
        self.assertLessEqual(
            total, 5,
            f"Audit hygiene: {total} TODO/FIXME reales en prod (techo 5)"
        )

    def test_metric_subpackage_areas_all_import(self):
        """Cada uno de los 36 submódulos de `domain_tools/` importa."""
        import importlib, pkgutil
        import gemma4_agent.domain_tools
        errors = []
        for mod_info in pkgutil.iter_modules(
            gemma4_agent.domain_tools.__path__,
            prefix="gemma4_agent.domain_tools.",
        ):
            try:
                importlib.import_module(mod_info.name)
            except Exception as exc:
                errors.append((mod_info.name, f"{type(exc).__name__}: {exc}"))
        self.assertEqual(errors, [], f"subpkg imports broken: {errors}")


if __name__ == "__main__":
    unittest.main()
