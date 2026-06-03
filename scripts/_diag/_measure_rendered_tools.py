"""Renderiza el chat template REAL de Gemma 4 E2B y mide el bloque de tools
tal como llega al prefill (NO el JSON del body — el template lo re-serializa
a su formato `declaration:...` propio).

Esto responde si el whitespace del JSON importa (NO: el template re-serializa)
y cual es el costo REAL del tools_section en tokens.
"""
import sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import os as _os
from tokenizers import Tokenizer
from jinja2 import Environment, BaseLoader

TOK_DIR = ROOT / "dataset_finetune" / "base_model" / "gemma-4-E2B-it"
TPL = ROOT / "_e2b_embedded_template.jinja"

tok = Tokenizer.from_file(str(TOK_DIR / "tokenizer.json"))
def ntok(s): return len(tok.encode(s).ids)

env = Environment(loader=BaseLoader(), trim_blocks=False, lstrip_blocks=False)
template = env.from_string(TPL.read_text(encoding="utf-8"))

def render(messages, tools):
    return template.render(messages=messages, tools=tools, bos_token="<bos>",
                           enable_thinking=False, add_generation_prompt=True)

def schemas_for(names, lean):
    _os.environ["GEMMA4_LEAN_RULES"] = "1" if lean else "0"
    import gemma4_agent.tools_pkg.tools as T
    from gemma4_agent.tools_pkg.tool_schemas import COMPOUND_TOOL_SCHEMAS
    wanted = set(names)
    out = [s for s in COMPOUND_TOOL_SCHEMAS
           if isinstance(s, dict) and s.get("function", {}).get("name") in wanted]
    if lean:
        out = [T._with_lean_description(s) for s in out]
    return out

SUBSETS = {
    "typical 5": ["system", "gui", "window", "filesystem", "app"],
    "multi-tool PESADO 5": ["whatsapp", "computer_use", "media", "audio", "window"],
    "wide 10": ["system", "gui", "window", "filesystem", "app",
                "audio", "browser", "media", "whatsapp", "web_search"],
}

msgs = [{"role": "user", "content": "hola"}]

print("=" * 78)
print("BLOQUE DE TOOLS RENDERIZADO POR EL TEMPLATE (lo que ve el prefill)")
print("=" * 78)
# baseline: render sin tools, para aislar el delta que aportan los tools.
base = render(msgs, None)
base_tok = ntok(base)
print(f"\nrender sin tools (baseline)        {base_tok:>6,} tok")

for label, names in SUBSETS.items():
    print(f"\n[{label}]  ({len(names)} tools)")
    for lean in (True, False):
        sch = schemas_for(names, lean)
        full = render(msgs, sch)
        delta = ntok(full) - base_tok
        tag = "LEAN on " if lean else "LEAN off"
        print(f"  {tag} tools block (rendered)  {delta:>6,} tok   (full prompt {ntok(full):,})")

print("\n" + "=" * 78)
print("PRUEBA: el whitespace del JSON del body NO afecta el render")
print("=" * 78)
sch = schemas_for(["whatsapp", "media"], True)
# Pasar el MISMO objeto (el template parte del dict, no del string). Para
# demostrar que minificar el JSON del body no cambia nada, re-parseamos desde
# JSON minificado vs pretty: el dict resultante es identico -> mismo render.
mini = json.loads(json.dumps(sch, separators=(",", ":")))
pretty = json.loads(json.dumps(sch, indent=2))
r_mini = render(msgs, mini)
r_pretty = render(msgs, pretty)
print(f"  render desde JSON minificado:  {ntok(r_mini):,} tok")
print(f"  render desde JSON pretty:      {ntok(r_pretty):,} tok")
print(f"  IDENTICOS? {r_mini == r_pretty}")

print("\n" + "=" * 78)
print("MUESTRA del formato renderizado (primeros 900 chars del bloque tools)")
print("=" * 78)
sch = schemas_for(["system", "audio"], True)
r = render(msgs, sch)
# extraer entre <|tool> y el ultimo <tool|>
start = r.find("<|tool>")
end = r.rfind("<tool|>")
print(r[start:end+7][:900] if start >= 0 else "(no tool block)")
