"""STUB verify de los defaults v22 (CPU puro, NO bootea server, NO toca GPU).

Confirma que con NINGUNA env override:
  - core_tools_pareto: CORE_SIZE=6 y el set default es el de 6 (Plan A2)
  - GEMMA4_CORE_RULES sigue funcionando como override
  - el INI de router (write_router_presets) sale con flash-attn=off + cache-ram=0
  - los toggles A/B (GEMMA4_FLASH_ATTN=on, GEMMA4_CACHE_RAM=N) siguen funcionando
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
for _k in ("GEMMA4_FLASH_ATTN", "GEMMA4_CACHE_RAM", "GEMMA4_CORE_RULES"):
    os.environ.pop(_k, None)

fails = []


def check(name, got, want):
    ok = got == want
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}: got={got!r} want={want!r}", flush=True)
    if not ok:
        fails.append(name)


print("=== Plan A2 (core_tools_pareto) ===", flush=True)
from gemma4_agent.agent_core import core_tools_pareto as ctp
check("CORE_SIZE", ctp.CORE_SIZE, 6)
check("_default_core_tools", ctp._default_core_tools(),
      ("app", "audio", "session", "system", "web", "window"))
os.environ["GEMMA4_CORE_RULES"] = "media,browser,gui"
check("read_user_core_tools(override)", ctp.read_user_core_tools(),
      ("browser", "gui", "media"))  # sorted
os.environ.pop("GEMMA4_CORE_RULES")

print("=== FA-off + cache-ram INI defaults (write_router_presets) ===", flush=True)
try:
    from gemma4_agent.infra.llama_server import get_shared_manager, write_router_presets
    from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
    prof = get_active_profile()
    apply_profile_to_env(prof)
    cfg = get_shared_manager()._config
    ini_path = write_router_presets(cfg, prof)
    txt = Path(ini_path).read_text(encoding="utf-8")
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    has_fa_off = any(l.replace(" ", "") == "flash-attn=off" for l in lines)
    has_cache0 = any(l.replace(" ", "") == "cache-ram=0" for l in lines)
    check("INI default flash-attn", "off" if has_fa_off else "??", "off")
    check("INI default cache-ram", "0" if has_cache0 else "??", "0")
    # A/B toggles
    os.environ["GEMMA4_FLASH_ATTN"] = "on"
    os.environ["GEMMA4_CACHE_RAM"] = "4096"
    txt2 = Path(write_router_presets(cfg, prof)).read_text(encoding="utf-8")
    l2 = [l.replace(" ", "") for l in txt2.splitlines()]
    check("A/B GEMMA4_FLASH_ATTN=on", any(x == "flash-attn=on" for x in l2), True)
    check("A/B GEMMA4_CACHE_RAM=4096", any(x == "cache-ram=4096" for x in l2), True)
    os.environ.pop("GEMMA4_FLASH_ATTN"); os.environ.pop("GEMMA4_CACHE_RAM")
    # restore default INI on disk
    write_router_presets(cfg, prof)
except Exception as exc:
    import traceback
    traceback.print_exc()
    fails.append(f"INI-check-exc:{type(exc).__name__}")

print(f"\n=== RESULT: {'ALL OK' if not fails else 'FAILURES: ' + ','.join(fails)} ===", flush=True)
sys.exit(1 if fails else 0)
