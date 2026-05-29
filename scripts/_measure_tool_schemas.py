"""Mide el peso REAL del tool_schemas_hint para subset comun."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.tools_pkg.tools import (
    COMPOUND_TOOL_SCHEMAS, compile_tools_to_markdown_exact,
)

CHARS_PER_TOK = 3.6

def stats(label, text):
    chars = len(text)
    toks = int(chars / CHARS_PER_TOK)
    print(f"  {label:40s} {chars:>8,} chars   ~{toks:>6,} toks")

print("=" * 70)
print("TOOL_SCHEMAS_HINT BREAKDOWN")
print("=" * 70)

print(f"\nTotal schemas disponibles: {len(COMPOUND_TOOL_SCHEMAS)}")

# Full vs compact
for mode_compact, mode_label in [(False, "full"), (True, "compact")]:
    md = compile_tools_to_markdown_exact(compact=mode_compact)
    stats(f"FULL CATALOG ({mode_label})", md)

# Subsets tipicos
typical_subsets = [
    [],
    ["web_search"],
    ["system"],
    ["gui", "window"],
    ["system", "gui", "window"],
    ["system", "gui", "window", "filesystem", "app"],
    ["system", "gui", "window", "filesystem", "app", "audio", "browser"],
    ["system", "gui", "window", "filesystem", "app", "audio", "browser", "media"],
]
print()
for subset in typical_subsets:
    wanted = set(subset)
    sub_schemas = [
        s for s in COMPOUND_TOOL_SCHEMAS
        if isinstance(s, dict)
        and isinstance(s.get("function"), dict)
        and s["function"].get("name") in wanted
    ]
    for mode_compact, mode_label in [(False, "full"), (True, "compact")]:
        md = compile_tools_to_markdown_exact(schemas=sub_schemas, compact=mode_compact) if sub_schemas else ""
        stats(f"subset {len(subset)} tools ({mode_label}): {','.join(subset[:3])}{'...' if len(subset)>3 else ''}", md)
