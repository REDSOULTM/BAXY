"""¿Los nombres que el corrector NO rescató están AUSENTES del inventario?
(= fix por expandir el seed) o presentes (= bug del corrector)?"""
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gemma4_agent.voice.inventory import get_inventory

inv = get_inventory()
blob = repr(inv).lower()
print(f"tipo inventario: {type(inv).__name__} | len repr: {len(blob)}")

miss = ["gimp", "hozier", "elden ring", "hollow knight", "edge", "zoom", "reddit",
        "outlook", "dua lipa", "arcane", "grand theft auto", "counter-strike",
        "stardew", "league of legends", "billie eilish", "taylor swift"]
ok = ["steam", "spotify", "discord", "chrome", "photoshop", "minecraft", "netflix"]

print("--- nombres que el corrector NO rescató: ¿en inventario? ---")
for n in miss:
    print(f"  {n:22} {'EN inv' if n in blob else 'AUSENTE'}")
print("--- control (correctos/rescatados) ---")
for n in ok:
    print(f"  {n:22} {'EN inv' if n in blob else 'AUSENTE'}")
