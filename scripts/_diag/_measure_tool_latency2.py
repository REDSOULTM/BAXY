"""MEDICIÓN tanda 2 (CLAUDE.md): latencia del MODO STATUS/lectura de las tools que
NO cubrió _measure_tool_latency.py. Solo acciones read-only/status — nada que abra
ventanas, instale, borre ni envíe. Encuentra gastadores locales restantes.
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

# (label, tool, args) — read-only/status. Las que requieren red real (download/
# email/fact_check) o input físico NO van. uia/printer/network status son lecturas.
CASES = [
    ("uia.tree",            "uia", {"action": "tree", "window": "", "limit": 30, "timeout_sec": 5}),
    ("printer_scanner",     "printer_scanner", {"action": "status"}),
    ("printer.list",        "printer_scanner", {"action": "list"}),
    ("desktop_layout",      "desktop_layout", {"action": "status"}),
    ("device_settings",     "device_settings", {"action": "status"}),
    ("network.status",      "network", {"action": "status"}),
    ("maintenance",         "maintenance", {"action": "status"}),
    ("job_manager.list",    "job_manager", {"action": "list"}),
    ("watcher.list",        "watcher", {"action": "list"}),
    ("routine.list",        "routine", {"action": "list"}),
    ("notes_tasks.list",    "notes_tasks", {"action": "list"}),
    ("local_calendar",      "local_calendar", {"action": "list"}),
    ("habit_tracker.list",  "habit_tracker", {"action": "list"}),
    ("contacts.list",       "contacts", {"action": "list"}),
    ("source_manager",      "source_manager", {"action": "list"}),
    ("dependency.status",   "dependency", {"action": "status"}),
    ("session.status",      "session", {"action": "status"}),
    ("verify.status",       "verify", {"action": "status"}),
    ("env.list",            "env", {"action": "list"}),
    ("registry.read",       "registry", {"action": "read", "path": r"HKCU\Environment", "name": "TEMP"}),
    ("photo_library",       "photo_library", {"action": "status"}),
    ("container.status",    "container", {"action": "status"}),
    ("database.status",     "database", {"action": "status"}),
    ("developer.status",    "developer", {"action": "status"}),
    ("media.status",        "media", {"action": "status"}),
    ("game_launcher.list",  "game_launcher", {"action": "list"}),
    ("notification",        "notification", {"action": "status"}),
    ("device_settings.bt",  "device_settings", {"action": "bluetooth_status"}),
    ("study.status",        "study", {"action": "status"}),
    ("form_filler",         "form_filler", {"action": "status"}),
    ("peripheral.status",   "peripheral", {"action": "status"}),
    ("accessibility",       "accessibility", {"action": "status"}),
    ("backup_sync.status",  "backup_sync", {"action": "status"}),
    ("mcp.list",            "mcp", {"action": "list"}),
]

print(f"{'TOOL.ACTION':22} {'ms':>8}   nota")
print("=" * 60)
rows = []
for label, tool, args in CASES:
    try:
        t = time.perf_counter()
        res = reg.execute(tool, args)
        dt = (time.perf_counter() - t) * 1000.0
        st = "" if (isinstance(res, dict) and res.get("ok") is not False) else \
             f"({str((res or {}).get('error') or (res or {}).get('status') or '')[:24]})"
        rows.append((dt, label, st))
        print(f"{label:22} {dt:8.1f}   {st}")
    except Exception as e:
        print(f"{label:22} {'ERR':>8}   {type(e).__name__}: {str(e)[:34]}")

print("\n=== gastadores (>300ms) ===")
hot = [r for r in sorted(rows, reverse=True) if r[0] > 300]
if not hot:
    print("  ninguno >300ms — el resto de las tools son rápidas.")
for dt, label, st in hot:
    print(f"  {label:22} {dt:8.1f}ms {st}")
