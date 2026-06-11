"""Diagnóstico: ¿dónde se van los ~14s de app.open en MISS? (medido en vivo
2026-06-10 con "abrí jitomatador": decide ~14s + a veces 2º scan del 4B).
Mide cada loader del AppResolver por separado + el deep scan + el resolve web,
y la 2ª llamada (warm) para ver qué se repaga. Sin LLM (medición de tool pura).
"""
import sys
import time
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import os
os.environ.setdefault("GEMMA4_DIAG", "1")

from gemma4_agent.tools_pkg.tools import ToolRegistry
from gemma4_agent.memory_pkg.memory import MemoryStore
from gemma4_agent.memory_pkg.state import AgentState

tmp = Path(tempfile.mkdtemp())
state = AgentState(tmp / "state.json")
reg = ToolRegistry(MemoryStore(tmp / "m.json"), tmp / "cap", state, safety_enabled=False)
apps = reg.apps

MISS = "jitomatador"

print("== loaders individuales (frío) ==", flush=True)
for src, loader in (
    ("path", apps._from_path),
    ("shortcuts", apps._from_shortcuts),
    ("start_apps", apps._from_start_apps),
    ("registry", apps._from_uninstall_registry),
    ("steam", apps._from_steam),
    ("epic", apps._from_epic),
):
    t0 = time.monotonic()
    items = loader()
    print(f"  {src:11} {time.monotonic()-t0:6.2f}s  {len(items)} candidatos", flush=True)

print("== deep scan (_from_common_exe_roots) ==", flush=True)
t0 = time.monotonic()
deep = apps._from_common_exe_roots(MISS)
print(f"  deep_scan   {time.monotonic()-t0:6.2f}s  {len(deep)} matches", flush=True)
t0 = time.monotonic()
deep2 = apps._from_common_exe_roots(MISS)
print(f"  deep_scan2  {time.monotonic()-t0:6.2f}s  {len(deep2)} matches (repetido)", flush=True)

print("== find() end-to-end (resolver NUEVO, frío real) ==", flush=True)
from gemma4_agent.tools_pkg.app_resolver import AppResolver
fresh = AppResolver()
t0 = time.monotonic()
m = fresh.find(MISS)
print(f"  find(miss) frío   {time.monotonic()-t0:6.2f}s  {len(m)} matches", flush=True)
t0 = time.monotonic()
m = fresh.find(MISS)
print(f"  find(miss) warm   {time.monotonic()-t0:6.2f}s  {len(m)} matches (2ª llamada, mismo proceso)", flush=True)
t0 = time.monotonic()
m = fresh.find("calculadora")
print(f"  find(hit) warm    {time.monotonic()-t0:6.2f}s  {len(m)} matches", flush=True)

print("== _resolve_site_by_search (web) ==", flush=True)
t0 = time.monotonic()
url = reg._resolve_site_by_search(MISS)
print(f"  resolve_site      {time.monotonic()-t0:6.2f}s  -> {url!r}", flush=True)
t0 = time.monotonic()
url = reg._resolve_site_by_search(MISS)
print(f"  resolve_site 2ª   {time.monotonic()-t0:6.2f}s  -> {url!r} (repetida)", flush=True)

print("== app_open(miss) end-to-end (tool completa, todo warm) ==", flush=True)
t0 = time.monotonic()
res = reg.t_app({"action": "open", "name": MISS})
print(f"  t_app(open,miss)  {time.monotonic()-t0:6.2f}s  ok={res.get('ok')} err={res.get('error')!r}", flush=True)
t0 = time.monotonic()
res = reg.t_app({"action": "open", "name": MISS})
print(f"  t_app 2ª llamada  {time.monotonic()-t0:6.2f}s  ok={res.get('ok')} err={res.get('error')!r}", flush=True)
