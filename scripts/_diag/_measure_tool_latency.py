"""MEDICIÓN (CLAUDE.md): latencia de las tools NO-web, read-only/status, que el
usuario usa seguido. NO ejecuta nada destructivo ni que abra ventanas/procesos
(el conftest-guard no aplica a scripts, así que elegimos a mano solo read-only).

Reporta ms por tool-action para encontrar gastadores locales (system, audio,
window list, clipboard, memory, knowledge, vision/ocr) — el equivalente al
hallazgo de la búsqueda web pero para el resto.
"""
import sys, os, time
sys.path.insert(0, os.path.abspath("."))
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
os.environ.setdefault("GEMMA4_DIAG", "1")
os.environ.setdefault("GEMMA4_AGENT_SAFETY", "0")

import tempfile, pathlib
from gemma4_agent.tools_pkg.tools import ToolRegistry
from gemma4_agent.memory_pkg.memory import MemoryStore
from gemma4_agent.memory_pkg.state import AgentState

tmp = pathlib.Path(tempfile.mkdtemp())
reg = ToolRegistry(MemoryStore(tmp / "m.json"), tmp / "cap",
                   state=AgentState(tmp / "s.json"), safety_enabled=False)

# (etiqueta, tool, args) — TODO read-only / status. Nada que abra apps ni borre.
CASES = [
    ("system.time",         "system", {"action": "time"}),
    ("system.cpu_ram_gpu",  "system", {"action": "cpu_ram_gpu"}),
    ("system.disk",         "system", {"action": "disk"}),
    ("system.battery",      "system", {"action": "battery"}),
    ("system.processes",    "system", {"action": "processes"}),
    ("audio.get_volume",    "audio",  {"action": "get_volume"}),
    ("audio.devices",       "audio",  {"action": "devices"}),
    ("window.list",         "window", {"action": "list"}),
    ("window.active",       "window", {"action": "active"}),
    ("clipboard.get",       "clipboard", {"action": "get"}),
    ("memory.list",         "memory", {"action": "list"}),
    ("knowledge.search",    "knowledge", {"action": "search", "query": "que es la fotosintesis"}),
    ("app.search",          "app",    {"action": "search", "name": "notepad"}),
    ("vision.ocr(screen)",  "vision", {"action": "ocr"}),
    ("gui.screenshot",      "gui",    {"action": "screenshot"}),
    ("local_search",        "local_search", {"action": "search", "query": "test"}),
]

print(f"{'TOOL.ACTION':24} {'ms':>8}   nota")
print("=" * 60)
rows = []
for label, tool, args in CASES:
    try:
        t = time.perf_counter()
        res = reg.execute(tool, args)
        dt = (time.perf_counter() - t) * 1000.0
        ok = isinstance(res, dict) and res.get("ok") is not False
        note = "" if ok else f"(err: {str(res.get('error') or res.get('status') or '')[:30]})"
        rows.append((dt, label, note))
        print(f"{label:24} {dt:8.1f}   {note}")
    except Exception as e:
        print(f"{label:24} {'ERR':>8}   {type(e).__name__}: {str(e)[:40]}")

print("\n=== TOP gastadores (>300ms) ===")
for dt, label, note in sorted(rows, reverse=True):
    if dt > 300:
        print(f"  {label:24} {dt:8.1f}ms {note}")
