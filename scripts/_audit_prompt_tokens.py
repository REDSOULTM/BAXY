"""Auditoria ESTATICA del presupuesto de tokens del prompt + tools (CPU puro,
sin agente/server/GPU). Lee los .md del prompt + importa el literal de schemas
(tool_schemas solo importa typing). Estima tokens = chars / 3.6 (factor medido
del repo; es estimacion, la tokenizacion real difiere ~10%).

Objetivo: saber DONDE estan los tokens para optimizar con datos, no a ciegas.
Separa lo MECANICO/seguro de lo QUALITY-SENSITIVE (necesita validacion en vivo).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CPT = 3.6  # chars per token (estimacion del repo)
def tok(s: str) -> int:
    return round(len(s) / CPT)

PROMPTS = ROOT / "gemma4_agent" / "prompts"
RULES_DIR = PROMPTS / "tool_rules"

# --- Piso del system prompt: core lean + 6 reglas always-on (Plan A2) ---
print("=" * 78)
print("PISO DEL SYSTEM PROMPT (se manda en CADA turno)")
print("=" * 78)
core = (PROMPTS / "core_lean.md").read_text(encoding="utf-8")
print(f"  core_lean.md                {tok(core):>6} tok ({len(core)} chars)")
CORE6 = ["app", "audio", "session", "system", "web", "window"]
rules_tok = {}
for r in sorted((RULES_DIR.glob("*.md"))):
    rules_tok[r.stem] = tok(r.read_text(encoding="utf-8"))
floor_rules = sum(rules_tok.get(n, 0) for n in CORE6)
print(f"  6 reglas always-on (A2)     {floor_rules:>6} tok  -> " +
      ", ".join(f"{n}:{rules_tok.get(n,0)}" for n in CORE6))
print(f"  PISO TOTAL aprox            {tok(core)+floor_rules:>6} tok (core + 6 rules; +overhead jinja/chat)")

# --- Schemas de tools (se manda el del subset, cap 5-8 por turno) ---
print("=" * 78)
print("SCHEMAS DE TOOLS (JSON; se manda el del subset del turno, cap 5-8)")
print("=" * 78)
from gemma4_agent.tools_pkg.tool_schemas import COMPOUND_TOOL_SCHEMAS
rows = []
for sch in COMPOUND_TOOL_SCHEMAS:
    fn = sch.get("function", {})
    name = fn.get("name", "?")
    desc = fn.get("description", "")
    full = json.dumps(sch, ensure_ascii=False)
    rows.append((name, tok(full), tok(desc), tok(json.dumps(fn.get("parameters", {}), ensure_ascii=False)),
                 rules_tok.get(name, 0)))
rows.sort(key=lambda r: -r[1])
print(f"  {'tool':<16}{'schema':>7}{'  desc':>7}{' params':>8}{'  rule':>7}{'  desc+rule':>11}")
print(f"  {'-'*16}{'-'*7}{'-'*7}{'-'*8}{'-'*7}{'-'*11}")
tot_schema = 0
for name, st, dt, pt, rt in rows:
    tot_schema += st
    print(f"  {name:<16}{st:>7}{dt:>7}{pt:>8}{rt:>7}{dt+rt:>11}")
print(f"  {'-'*16}")
print(f"  TOTAL {len(rows)} schemas: {tot_schema} tok (si se mandaran TODOS — no pasa; cap 5-8)")

# --- Whales: top 6 por schema ---
print("=" * 78)
print("TOP OFENSORES (los que mas pesan cuando entran al subset)")
print("=" * 78)
for name, st, dt, pt, rt in rows[:6]:
    print(f"  {name:<16} schema={st} tok  (desc={dt}, params={pt})  + rule={rt}  = {dt+rt} tok de guia")

# --- Turno tipico de accion: piso + 5 schemas representativos ---
print("=" * 78)
print("TURNO DE ACCION TIPICO (estimacion)")
print("=" * 78)
example = ["audio", "media", "app", "window", "session"]
by_name = {r[0]: r for r in rows}
sch_sum = sum(by_name.get(n, (0, 0, 0, 0, 0))[1] for n in example)
print(f"  subset ejemplo {example}: schemas={sch_sum} tok")
print(f"  + piso {tok(core)+floor_rules} tok  = ~{sch_sum + tok(core)+floor_rules} tok (sin historial)")
