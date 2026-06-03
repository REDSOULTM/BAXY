"""Mide el peso REAL (tokenizer Gemma) de tools_section / tools[] JSON.

Responde:
 - En un turno multi-tool, cuanto pesa tools[] vs el resto.
 - Los schemas se mandan completos o recortados (LEAN)?
 - Campos del JSON omitibles? whitespace? Cuanto ahorra cada palanca.

Usa el tokenizer Gemma local (ground truth) si esta; si no, heuristica.
"""
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

TOK_DIR = ROOT / "dataset_finetune" / "base_model" / "gemma-4-E2B-it"

_tok = None
try:
    from tokenizers import Tokenizer
    _tok = Tokenizer.from_file(str(TOK_DIR / "tokenizer.json"))
    print(f"[tokenizer] Gemma real (tokenizers lib) desde {TOK_DIR.name}")
except Exception as e:
    print(f"[tokenizer] FALLBACK heuristica chars/3.6 ({type(e).__name__}: {e})")


def ntok(text: str) -> int:
    if _tok is not None:
        return len(_tok.encode(text).ids)
    return int(len(text) / 3.6)


def show(label, text):
    c = len(text)
    t = ntok(text)
    print(f"  {label:46s} {c:>8,} chars   {t:>6,} tok")
    return t


import os as _os
# Force LEAN on (prod default) and off, to measure the delta.
def schemas_for(names, lean):
    _os.environ["GEMMA4_LEAN_RULES"] = "1" if lean else "0"
    from gemma4_agent.tools_pkg import tools as T
    # bust the per-subset cache between lean toggles
    try:
        T._SCHEMAS_FOR_NAMES_CACHE.clear()
    except Exception:
        pass
    from gemma4_agent.tools_pkg.tool_schemas import COMPOUND_TOOL_SCHEMAS
    wanted = set(names)
    out = [s for s in COMPOUND_TOOL_SCHEMAS
           if isinstance(s, dict) and s.get("function", {}).get("name") in wanted]
    if lean:
        out = [T._with_lean_description(s) for s in out]
    return out


print("=" * 78)
print("tools[] JSON — el path REAL en 4GB (markdown hint OFF para ctx<12k)")
print("=" * 78)

# Subsets representativos. multi-tool tipico = 5 tools.
SUBSETS = {
    "smalltalk []": [],
    "1 tool [web_search]": ["web_search"],
    "typical 5 [system,gui,window,filesystem,app]":
        ["system", "gui", "window", "filesystem", "app"],
    "multi-tool 5 PESADO [whatsapp,computer_use,media,audio,window]":
        ["whatsapp", "computer_use", "media", "audio", "window"],
    "wide 10":
        ["system", "gui", "window", "filesystem", "app",
         "audio", "browser", "media", "whatsapp", "web_search"],
}

for label, names in SUBSETS.items():
    print(f"\n[{label}]")
    for lean in (True, False):
        sub = schemas_for(names, lean)
        body_tools = json.dumps(sub, ensure_ascii=False)              # como va al body
        compact_json = json.dumps(sub, ensure_ascii=False, separators=(",", ":"))
        tag = "LEAN on " if lean else "LEAN off"
        t_body = show(f"{tag} tools[] json (default sep)", body_tools)
        t_cmp = show(f"{tag} tools[] json (no-ws sep)", compact_json)
        if lean:
            print(f"      -> no-ws ahorra {t_body - t_cmp} tok ({100*(t_body-t_cmp)/max(t_body,1):.1f}%)")


print("\n" + "=" * 78)
print("DESGLOSE de UN schema pesado: de que se compone el JSON")
print("=" * 78)
from gemma4_agent.tools_pkg.tool_schemas import COMPOUND_TOOL_SCHEMAS
import gemma4_agent.tools_pkg.tools as T
for nm in ("whatsapp", "media", "computer_use", "system", "audio"):
    full = next((s for s in COMPOUND_TOOL_SCHEMAS
                 if s.get("function", {}).get("name") == nm), None)
    if not full:
        continue
    lean = T._with_lean_description(full)
    fn_full = full["function"]
    desc_full = fn_full.get("description", "")
    desc_lean = lean["function"].get("description", "")
    params = fn_full.get("parameters", {})
    print(f"\n## {nm}")
    show("  full description", desc_full)
    show("  LEAN description", desc_lean)
    show("  parameters block (json)", json.dumps(params, ensure_ascii=False))
    show("  whole schema FULL (json)", json.dumps(full, ensure_ascii=False))
    show("  whole schema LEAN (json)", json.dumps(lean, ensure_ascii=False))


print("\n" + "=" * 78)
print("PALANCA: quitar 'type:object'/'type:function' redundantes? (estructural)")
print("=" * 78)
# Cuanto pesan los wrappers fijos repetidos N veces.
wrapper = '{"type": "function", "function": {"name": "", "description": "", "parameters": {"type": "object", "properties": {}, "required": []}}}'
show("wrapper boilerplate por tool (default)", wrapper)
show("wrapper boilerplate por tool (no-ws)", json.dumps(json.loads(wrapper), separators=(",", ":")))
