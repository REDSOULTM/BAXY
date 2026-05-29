"""B8 validación EN VIVO: crear un reminder con HORA → ¿se registra un Scheduled
Task REAL en el SO (\\Gemma4Agent\\)? Antes el tool `reminder` sólo guardaba state
(no disparaba). Verifica creación vía `schtasks /query` y LIMPIA el task al final
(no deja basura). No espera el disparo (2 min) — valida que se PROGRAMÓ."""
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["GEMMA4_REMINDER_SCHEDULE"] = "1"

from gemma4_agent.tools_pkg.ops_tools import reminder_tool
from gemma4_agent.memory_pkg.state import AgentState

tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
tmp.close()
p = Path(tmp.name)
p.unlink(missing_ok=True)
state = AgentState(path=p)

due = (datetime.now() + timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%S")
print(f"[1] reminder create due={due}")
r = reminder_tool({"action": "create", "title": "Gemma4 B8 test",
                   "text": "validacion B8 - borrame", "due": due}, state)
print(f"    -> ok={r.get('ok')} kind={r.get('kind')} backend={r.get('backend')} task={r.get('task_name')}")
task_name = r.get("task_name")

created = False
if task_name:
    q = subprocess.run(["schtasks", "/query", "/tn", f"\\Gemma4Agent\\{task_name}"],
                       capture_output=True, text=True)
    created = q.returncode == 0
    print(f"[2] schtasks query rc={q.returncode} -> Task {'EXISTE en el SO' if created else 'NO existe'}")
    if created:
        for line in q.stdout.splitlines():
            if task_name in line or "Next Run" in line or "Ready" in line:
                print(f"    {line.strip()[:90]}")

lst = reminder_tool({"action": "list"}, state)
print(f"[3] reminder list count={lst.get('count')} (incluye el local_reminder)")

# CLEANUP — no dejar el Task de prueba en el SO
if task_name:
    rid = next((x.get("id") for x in lst.get("reminders", [])
                if (x.get("metadata") or {}).get("task_name") == task_name), None)
    if rid:
        d = reminder_tool({"action": "delete", "id": rid}, state)
        print(f"[4] cleanup delete ok={d.get('ok')}")
    q2 = subprocess.run(["schtasks", "/query", "/tn", f"\\Gemma4Agent\\{task_name}"],
                        capture_output=True, text=True)
    print(f"    post-cleanup query rc={q2.returncode} (1/non-zero = ya no existe -> limpio)")

print(f"\n=== VEREDICTO B8: Scheduled Task creado en vivo = {'OK' if created else 'FAIL'} ===")
