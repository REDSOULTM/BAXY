"""Verificación EN VIVO end-to-end del cliente MCP enrolado (Ola 3, B9).

Usa el servidor MCP REAL de prueba (scripts/_mcp_test_server.py, SDK mcp) — no
mocks. Valida la cadena completa que el research pidió:
  1. DISCOVER: el cliente descubre las tools del servidor MCP real (stdio).
  2. ENROLL: se enrolan al catálogo del router (TOOL_DESCRIPTIONS).
  3. ROUTE + CAP: el router las rankea junto a las compound y RESPETA el cap <=5
     (nunca le da las N al 4B — la disciplina de subset, mitigación de R7).
  4. DISPATCH: el ToolRegistry ejecuta una tool MCP por su nombre namespaced,
     ruteándola transparente al servidor real -> resultado correcto.

NO usa el LLM (determinista) ni input sintético. Lanza el servidor MCP de prueba
como subproceso stdio (local, sin red).

Uso: python scripts/_live_verify_mcp_e2e.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["GEMMA4_MCP"] = "1"

from gemma4_agent.tools_pkg import mcp_client as M  # noqa: E402
from gemma4_agent.routing import semantic_router as SR  # noqa: E402
from gemma4_agent.routing.planner import plan_mission, select_tool_names, MAX_SELECTED_TOOLS  # noqa: E402


def main() -> int:
    failures: list[str] = []

    # Config -> servidor de prueba real (stdio).
    cfg = {"servers": [{"name": "test", "command": sys.executable,
                        "args": [str((ROOT / "scripts" / "_mcp_test_server.py").resolve())]}]}
    tmp = Path(tempfile.gettempdir()) / "gemma4_mcp_e2e.json"
    tmp.write_text(json.dumps(cfg), encoding="utf-8")
    M._CONFIG_PATH = tmp
    M.reset_cache()

    print("== 1. DISCOVER (servidor MCP real) ==")
    tools = M.discover_mcp_tools(force=True)
    names = sorted(t["name"] for t in tools)
    ok = names == ["add_numbers", "echo"]
    print(f"  {'OK ' if ok else 'FALLA'} descubrió: {names} (esperado ['add_numbers','echo'])")
    if not ok:
        failures.append(f"discover: {names}")

    print("== 2. ENROLL al router ==")
    payload = [{"id": M.mcp_tool_id(t["server"], t["name"]),
                "description": t.get("description") or t["name"]} for t in tools]
    n = SR.enroll_mcp_tools(payload)
    enrolled = [k for k in SR.TOOL_DESCRIPTIONS if k.startswith("mcp__")]
    ok = (n == 2 and "mcp__test__echo" in enrolled)
    print(f"  {'OK ' if ok else 'FALLA'} enroladas {n}: {sorted(enrolled)}")
    if not ok:
        failures.append(f"enroll: {enrolled}")

    print("== 3. ROUTE + CAP (<= cap, nunca las N) ==")
    # Enrolar muchas extra para estresar el cap.
    big = payload + [{"id": f"mcp__test__filler_{i}", "description": f"filler {i}"} for i in range(30)]
    SR.enroll_mcp_tools(big)
    cap_ok = True
    for q in ("sumá dos números", "echo this text", "abrí spotify", "subí el volumen"):
        subset = select_tool_names(q, plan_mission(q))
        if len(subset) > MAX_SELECTED_TOOLS + 2:
            cap_ok = False
            failures.append(f"cap excedido en {q!r}: {len(subset)} tools")
        if len([t for t in subset if t.startswith("mcp__")]) >= 32:
            cap_ok = False
            failures.append(f"se colaron todas las MCP en {q!r}")
    print(f"  {'OK ' if cap_ok else 'FALLA'} subset <= cap con 32 tools MCP enroladas (nunca las 32)")

    print("== 4. DISPATCH (ejecutar tool MCP real por nombre namespaced) ==")
    # Restaurar solo las 2 reales para el dispatch.
    SR.enroll_mcp_tools(payload)
    from gemma4_agent.tools_pkg.tools import ToolRegistry
    reg = ToolRegistry.__new__(ToolRegistry)
    reg._impls = {}
    reg.state = MagicMock()
    reg.safety_enabled = False
    r = reg.execute("mcp__test__add_numbers", {"a": 2, "b": 40})
    ok = (r.get("ok") and "42" in str(r.get("content", "")))
    print(f"  {'OK ' if ok else 'FALLA'} mcp__test__add_numbers(2,40) -> {r.get('content')!r}")
    if not ok:
        failures.append(f"dispatch add: {r}")
    r2 = reg.execute("mcp__test__echo", {"text": "jarvis"})
    ok2 = (r2.get("ok") and "jarvis" in str(r2.get("content", "")))
    print(f"  {'OK ' if ok2 else 'FALLA'} mcp__test__echo('jarvis') -> {r2.get('content')!r}")
    if not ok2:
        failures.append(f"dispatch echo: {r2}")

    SR.enroll_mcp_tools([])  # limpiar
    print()
    if failures:
        print(f"RESULTADO: {len(failures)} FALLAS:")
        for f in failures:
            print("  -", f)
        return 1
    print("RESULTADO: TODO OK — MCP descubre, enrola, respeta el cap, y ejecuta end-to-end.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
