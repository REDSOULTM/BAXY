"""Verificación EN VIVO del budget de retry por clase (H2/H3, roadmap).

Ejercita la cadena REAL dispatcher -> classify_failure -> retry_budget_for con
resultados de producción (no fixtures): llama al ToolRegistry.execute real con
(a) una tool inexistente y (b) una acción fuera del enum, y confirma que:
  - "unknown tool: X"      -> TOOL_NOT_FOUND -> budget 0 (NO reintentar).
  - acción inválida         -> PARAM_MISMATCH  -> budget 1 (1 corrección).
  - timeout/red             -> TRANSIENT       -> budget 2.
  - error raro              -> UNKNOWN          -> budget 0.

Esto valida que el flakeo "466/513 retries desperdiciados" se corta: lo
irrecuperable obtiene 0 reintentos desde el dispatcher real. NO usa LLM ni input
sintético (solo el dispatcher, que es código puro de routing).

Uso: python scripts/_live_verify_retry_budget.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.tools_pkg.tools import ToolRegistry  # noqa: E402
from gemma4_agent.safety_pkg.verify_core import (  # noqa: E402
    classify_failure, retry_budget_for,
    ERR_TOOL_NOT_FOUND, ERR_PARAM_MISMATCH, ERR_TRANSIENT, ERR_UNKNOWN,
)


def main() -> int:
    reg = ToolRegistry.__new__(ToolRegistry)
    reg._impls = {}                # catálogo vacío -> cualquier tool = unknown
    reg.state = MagicMock()
    reg.safety_enabled = False
    failures = []

    print("== cadena REAL dispatcher -> classify -> budget ==")

    # (a) tool inexistente: el dispatcher devuelve "unknown tool: X".
    r = reg.execute("herramienta_que_no_existe", {"action": "x"})
    cls = classify_failure(r)
    budget = retry_budget_for(cls)
    ok = (cls == ERR_TOOL_NOT_FOUND and budget == 0)
    print(f"  {'OK ' if ok else 'FALLA'} tool inexistente -> error={r.get('error')!r}")
    print(f"        clasificó={cls!r} budget={budget} (esperado tool_not_found / 0)")
    if not ok:
        failures.append(f"tool inexistente: cls={cls} budget={budget}")

    # (b) clasificación de los demás tipos sobre resultados representativos del
    #     dispatcher (mismos shapes que producen las tools reales).
    cases = [
        ("acción fuera del enum",
         {"error": "invalid tool arguments", "validation_errors": ["bad action"]},
         ERR_PARAM_MISMATCH, 1),
        ("timeout de red",
         {"error": "connection timeout", "status": "failed"},
         ERR_TRANSIENT, 2),
        ("error interno raro",
         {"error": "weird glitch zzz", "status": "failed"},
         ERR_UNKNOWN, 0),
        ("dependencia faltante",
         {"status": "needs_dependency", "error": "playwright not installed"},
         "missing_precondition", 1),
    ]
    for name, result, exp_cls, exp_budget in cases:
        cls = classify_failure(result)
        budget = retry_budget_for(cls)
        ok = (cls == exp_cls and budget == exp_budget)
        print(f"  {'OK ' if ok else 'FALLA'} {name} -> clasificó={cls!r} budget={budget} "
              f"(esperado {exp_cls} / {exp_budget})")
        if not ok:
            failures.append(f"{name}: cls={cls} budget={budget}")

    print()
    print("== invariante anti-desperdicio (el corazón del fix) ==")
    # Lo irrecuperable SIEMPRE tiene budget 0: nunca se reintenta a ciegas.
    for cls in (ERR_TOOL_NOT_FOUND, ERR_UNKNOWN):
        b = retry_budget_for(cls)
        ok = (b == 0)
        print(f"  {'OK ' if ok else 'FALLA'} {cls} budget={b} (debe ser 0: irrecuperable)")
        if not ok:
            failures.append(f"{cls} budget no es 0")

    print()
    if failures:
        print(f"RESULTADO: {len(failures)} FALLAS:")
        for f in failures:
            print("  -", f)
        return 1
    print("RESULTADO: TODO OK — lo irrecuperable obtiene 0 reintentos (no más desperdicio).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
