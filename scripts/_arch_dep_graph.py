"""Mapa de dependencias REAL entre módulos de gemma4_agent — qué importa de qué,
contando solo imports relativos (from .X import ... / from gemma4_agent.X import).
Read-only. Output: fan-in/fan-out por módulo + ciclos detectados.

R3-real (2026-05-28): distingue imports TOP-LEVEL (a column 0) de imports
LAZY (a indent > 0, dentro de función). Los ciclos solo se computan sobre
top-level — un import lazy NO causa ciclo real en runtime."""
from __future__ import annotations
import re
from pathlib import Path
from collections import defaultdict, Counter

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "gemma4_agent"
PROD = [p for p in PKG.rglob("*.py") if "test_" not in p.name]

# Mapa: módulo -> set de módulos importados TOP-LEVEL (para detectar ciclos).
deps: dict[str, set[str]] = defaultdict(set)
# Mapa adicional: módulo -> set de imports LAZY (informativo, no causa ciclo).
deps_lazy: dict[str, set[str]] = defaultdict(set)
module_of: dict[Path, str] = {}

def mod_name(p: Path) -> str:
    rel = p.relative_to(PKG).with_suffix("")
    return rel.as_posix().replace("/", ".")

for p in PROD:
    module_of[p] = mod_name(p)

# Top-level: `from` literal en columna 0.
REL_IMPORT_TOP = re.compile(r"^from\s+\.(\w[\w.]*)\s+import", re.M)
ABS_IMPORT_TOP = re.compile(r"^from\s+gemma4_agent\.(\w[\w.]*)\s+import", re.M)
REL_FROM_TOP   = re.compile(r"^from\s+\.\s+import\s+([\w,\s]+)", re.M)

# Lazy: cualquier indent > 0 (dentro de función / método / clase).
REL_IMPORT_LAZY = re.compile(r"^\s+from\s+\.(\w[\w.]*)\s+import", re.M)
ABS_IMPORT_LAZY = re.compile(r"^\s+from\s+gemma4_agent\.(\w[\w.]*)\s+import", re.M)
REL_FROM_LAZY   = re.compile(r"^\s+from\s+\.\s+import\s+([\w,\s]+)", re.M)

for p in PROD:
    me = module_of[p]
    txt = p.read_text(encoding="utf-8", errors="ignore")
    for rx in (REL_IMPORT_TOP, ABS_IMPORT_TOP):
        for m in rx.finditer(txt):
            deps[me].add(m.group(1))
    for m in REL_FROM_TOP.finditer(txt):
        for n in (s.strip() for s in m.group(1).split(",")):
            if n: deps[me].add(n)
    for rx in (REL_IMPORT_LAZY, ABS_IMPORT_LAZY):
        for m in rx.finditer(txt):
            deps_lazy[me].add(m.group(1))
    for m in REL_FROM_LAZY.finditer(txt):
        for n in (s.strip() for s in m.group(1).split(",")):
            if n: deps_lazy[me].add(n)

# Fan-out: cuántos importa cada uno
fan_out = {m: len(d) for m, d in deps.items()}
# Fan-in: cuántos lo importan
fan_in = Counter()
for me, ds in deps.items():
    for d in ds:
        # normalizar prefijos: 'voice.runtime' cuenta como 'voice.runtime'
        fan_in[d] += 1

print("# FAN-IN top-15 (módulos más importados — núcleo del sistema)")
for m, n in fan_in.most_common(15):
    print(f"  {n:>3}  {m}")

print("\n# FAN-OUT top-15 (módulos que importan más — más acoplados)")
for m, n in sorted(fan_out.items(), key=lambda x: -x[1])[:15]:
    print(f"  {n:>3}  {m}")

# Detectar ciclos (DFS simple)
def find_cycles():
    cycles = set()
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {m: WHITE for m in deps}
    path = []
    def dfs(u):
        color[u] = GRAY
        path.append(u)
        for v in deps.get(u, ()):
            if v not in color:
                continue
            if color[v] == GRAY:
                # ciclo: u -> v ya en path
                try:
                    i = path.index(v)
                    cyc = tuple(path[i:] + [v])
                    # normalizar arrancando por el menor
                    k = cyc.index(min(cyc))
                    rot = cyc[k:] + cyc[:k]
                    cycles.add(rot)
                except ValueError:
                    pass
            elif color[v] == WHITE:
                dfs(v)
        path.pop()
        color[u] = BLACK
    for m in list(deps):
        if color[m] == WHITE:
            dfs(m)
    return cycles

cycles = find_cycles()
print(f"\n# CICLOS detectados: {len(cycles)}")
for c in sorted(cycles)[:10]:
    print(f"  {' -> '.join(c)}")

# Lazy imports stats — extension R3 sprint 2026-05-28.
print(f"\n# LAZY IMPORTS (inside functions) — anti-pattern indicator")
lazy_total = 0
lazy_per_file = []
for p in PROD:
    txt = p.read_text(encoding="utf-8", errors="ignore")
    n = len(re.findall(r"^\s+from \.", txt, re.M))
    if n:
        lazy_per_file.append((n, mod_name(p)))
        lazy_total += n
print(f"  Total: {lazy_total}")
print(f"  Top-10 files by lazy count:")
for n, m in sorted(lazy_per_file, reverse=True)[:10]:
    print(f"    {n:>4}  {m}")
