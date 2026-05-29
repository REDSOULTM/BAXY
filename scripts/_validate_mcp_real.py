"""Valida el skeleton MCP contra un servidor MCP REAL (@modelcontextprotocol/
server-filesystem via npx) en un dir temporal aislado. NO toca la config del usuario
ni su filesystem. Verifica: discover_mcp_tools (descubre tools reales) + call_mcp_tool
(lee un archivo). Si esto anda, el skeleton (SDK oficial + wrapper async->sync) es sólido."""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["GEMMA4_MCP"] = "1"

from gemma4_agent.tools_pkg import mcp_client as M

# Dir temporal + archivo de prueba (el server-filesystem solo verá este dir).
tmp = Path(tempfile.mkdtemp())
(tmp / "hola.txt").write_text("Gemma4 MCP funciona: lectura via servidor real.", encoding="utf-8")

# Config temporal (no tocar ~/.gemma4 del usuario).
cfg = tmp / "mcp_servers.json"
cfg.write_text(json.dumps({"servers": [{
    "name": "fs",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", str(tmp)],
}]}), encoding="utf-8")

print(f"[setup] dir temp: {tmp}")
print("[1] discover_mcp_tools (npx baja el server la 1ra vez, puede tardar)...")
with mock.patch.object(M, "_CONFIG_PATH", cfg):
    M.reset_cache()
    tools = M.discover_mcp_tools(force=True)
    print(f"    -> {len(tools)} tools MCP descubiertas")
    for t in tools[:8]:
        print(f"       - {t['server']}:{t['name']} — {t['description'][:60]}")

    # Llamar una tool de lectura (read_text_file o read_file) sobre hola.txt.
    read_tool = next((t["name"] for t in tools if "read" in t["name"].lower()
                      and "text" in t["name"].lower()), None) \
        or next((t["name"] for t in tools if t["name"].lower() == "read_file"), None) \
        or next((t["name"] for t in tools if "read" in t["name"].lower()), None)
    print(f"\n[2] call_mcp_tool fs:{read_tool} sobre hola.txt ...")
    called = False
    content = ""
    if read_tool:
        r = M.call_mcp_tool("fs", read_tool, {"path": str(tmp / "hola.txt")})
        called = bool(r.get("ok"))
        content = r.get("content", "") or r.get("error", "")
        print(f"    -> ok={r.get('ok')} content={content[:90]!r}")

print("\n=== VEREDICTO B9 skeleton ===")
print(f"  discover: {'OK (' + str(len(tools)) + ' tools)' if tools else 'FAIL'}")
print(f"  call:     {'OK (leyó el archivo real)' if called and 'funciona' in content else ('parcial: ' + content[:50] if called else 'FAIL')}")
