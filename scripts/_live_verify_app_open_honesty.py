"""Verificación EN VIVO de la honestidad de app.open (C3, roadmap).

NO abre apps reales en la máquina del usuario (intrusivo) ni usa input sintético.
Ejercita el handler app_open REAL de producción con apps.open mockeado para
simular los tres desenlaces que el SO puede dar, y verifica el flujo COMPLETO
(handler -> _normalize_tool_result -> guard de reply) end-to-end:

  1. launch despachado pero ventana NO confirmada -> verified=None (no False),
     status=dispatched -> el guard de reply NO inyecta "no dejó evidencia".
  2. app ya estaba abierta (preexisting) -> verified=True honesto.
  3. ventana confirmada por auto-verify -> verified=True.

El punto: un app.open no confirmado ya no MIENTE diciendo ok/done plano ni se
auto-marca como fallo que dispara reintentos (el flakeo events=0 medido).

Uso: python scripts/_live_verify_app_open_honesty.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.tools_pkg.tools import (  # noqa: E402
    ToolRegistry, _normalize_tool_result, _has_unverified_signal,
)


def _reg(verify_seq, preexisting=False, open_ok=True):
    reg = ToolRegistry.__new__(ToolRegistry)
    cand = MagicMock()
    cand.process_name = "discord.exe"
    cand.as_dict.return_value = {"name": "Discord", "launch": "discord.exe"}
    reg.apps = MagicMock()
    reg.apps.find.return_value = [cand]
    reg.apps.open.return_value = {"ok": open_ok, "error": None}
    reg.state = MagicMock()
    reg.state.register_resource.return_value = {"resource": {"id": "r1"}}
    seq = list(verify_seq)
    calls = {"n": 0}

    def _v(args):
        i = calls["n"]; calls["n"] += 1
        if i == 0:
            return {"found": preexisting}
        f = seq.pop(0) if seq else False
        return {"found": f, "match": {"title": "Discord"} if f else None}
    reg.verify_app_opened = _v
    return reg


def main() -> int:
    failures = []
    scenarios = [
        ("launch no confirmado", _reg([False, False, False]),
         {"verified": None, "status": "dispatched", "completion": "launch_requested",
          "unverified_signal": False}),
        ("app ya abierta", _reg([False], preexisting=True),
         {"verified": True, "status": "done", "completion": "launch_requested"}),
        ("ventana confirmada", _reg([True]),
         {"verified": True, "status": "done", "completion": "launch_verified"}),
    ]
    for name, reg, exp in scenarios:
        r = reg.app_open({"name": "Discord"})
        r = _normalize_tool_result("app", {"action": "open", "name": "Discord"}, r)
        checks = {
            "verified": r.get("verified") is exp["verified"],
            "status": r.get("status") == exp["status"],
            "completion": r.get("completion_status") == exp["completion"],
        }
        if "unverified_signal" in exp:
            checks["unverified_signal"] = (_has_unverified_signal(r) is exp["unverified_signal"])
        ok = all(checks.values())
        bad = [k for k, v in checks.items() if not v]
        print(f"  {'OK ' if ok else 'FALLA'} {name}: "
              f"verified={r.get('verified')!r} status={r.get('status')!r} "
              f"completion={r.get('completion_status')!r}")
        if not ok:
            failures.append(f"{name}: fallaron {bad} -> {r}")

    print()
    if failures:
        print(f"RESULTADO: {len(failures)} FALLAS:")
        for f in failures:
            print("  -", f)
        return 1
    print("RESULTADO: TODO OK — app.open es honesto (None preservado, sin falsa evidencia).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
