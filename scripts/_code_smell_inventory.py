"""Inventario rápido de smells objetivos (no opinión, números) — un piso de hechos
para decidir el alcance de una auditoría. Read-only sobre gemma4_agent/."""
from __future__ import annotations
import re
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
PROD = [p for p in (ROOT / "gemma4_agent").rglob("*.py")
        if "test_" not in p.name and not p.name.endswith("_test.py")]

PATTERNS = {
    "try_except_pass":     re.compile(r"except[^\n:]*:\s*\n\s*pass"),
    "bare_except":         re.compile(r"^\s*except\s*:", re.M),
    "todo_fixme_xxx_hack": re.compile(r"\b(?:TODO|FIXME|XXX|HACK)\b"),
    "noqa_comments":       re.compile(r"#\s*noqa"),
    "print_calls":         re.compile(r"^\s*print\(", re.M),
    "eval_or_exec":        re.compile(r"\b(?:eval|exec)\s*\("),
    "global_keyword":      re.compile(r"^\s*global\s+", re.M),
    "mutable_default_arg": re.compile(r"def\s+\w+\([^)]*=\s*(?:\[\]|\{\})"),
    "hardcoded_win_paths": re.compile(r'["\']C:[\\/]'),
    "imports_inside_func": re.compile(r"^\s{4,}(?:import|from)\s+", re.M),
    "noinspection_marker": re.compile(r"#\s*noinspection", re.I),
    "type_ignore":         re.compile(r"#\s*type:\s*ignore"),
    "Any_in_signatures":   re.compile(r":\s*Any\b|->\s*Any\b"),
    "broad_Exception_log": re.compile(r"except\s+Exception[^\n]*\n\s*(?:pass|logging\.)"),
    "f_string_in_log":     re.compile(r"\b(?:logger|logging)\.[a-z]+\(\s*f['\"]"),
}

counts = {k: 0 for k in PATTERNS}
per_file: dict[str, dict[str, int]] = {}
todos_by_file: Counter = Counter()
loc_by_file: dict[str, int] = {}

for p in PROD:
    txt = p.read_text(encoding="utf-8", errors="ignore")
    rel = p.relative_to(ROOT).as_posix()
    loc_by_file[rel] = txt.count("\n") + 1
    pf: dict[str, int] = {}
    for name, rx in PATTERNS.items():
        n = len(rx.findall(txt))
        counts[name] += n
        if n:
            pf[name] = n
    todos = re.findall(r"\b(?:TODO|FIXME|XXX|HACK)\b[:\s]([^\n]{0,80})", txt)
    if todos:
        todos_by_file[rel] += len(todos)
    if pf:
        per_file[rel] = pf

# Top 10 archivos por LOC
print("# Top-10 archivos por LOC (donde más impacta cualquier refactor)")
for rel, n in sorted(loc_by_file.items(), key=lambda x: -x[1])[:10]:
    print(f"  {n:>6,}  {rel}")

print("\n# Conteo TOTAL de cada smell")
for k, v in sorted(counts.items(), key=lambda x: -x[1]):
    print(f"  {v:>5,}  {k}")

print("\n# Top-10 archivos con más TODOs/FIXMEs/HACKs")
for rel, n in todos_by_file.most_common(10):
    print(f"  {n:>4}  {rel}")

print("\n# Archivos con la mayor concentración de smells crudos")
ranked = sorted(per_file.items(), key=lambda x: -sum(x[1].values()))[:10]
for rel, d in ranked:
    parts = ", ".join(f"{k}={v}" for k, v in sorted(d.items(), key=lambda x: -x[1])[:4])
    print(f"  total={sum(d.values()):>4}  {rel}\n           {parts}")
