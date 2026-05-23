"""Compara tokens de tool_schemas individuales vs consolidados."""
import json
from pathlib import Path

ROOT = Path(__file__).parent

individual = json.loads((ROOT / "tool_schemas.json").read_text(encoding="utf-8"))
consolidated = json.loads((ROOT / "tool_schemas_consolidated.json").read_text(encoding="utf-8"))

# Aproximación de tokens: chars/4 (regla GPT-3 estándar)
ind_chars = len(json.dumps(individual, ensure_ascii=False))
con_chars = len(json.dumps(consolidated, ensure_ascii=False))

ind_tokens = ind_chars // 4
con_tokens = con_chars // 4

print(f"Individual ({len(individual)} tools): {ind_chars} chars ~ {ind_tokens} tokens")
print(f"Consolidated ({len(consolidated)} tools): {con_chars} chars ~ {con_tokens} tokens")
print(f"\nReducción: {ind_chars - con_chars} chars ~ {ind_tokens - con_tokens} tokens ({round((1 - con_chars/ind_chars)*100, 1)}%)")

# Si Carter crece a 100 tools individuales linealmente:
proj_100_ind = ind_chars * (100 / len(individual))
proj_200_ind = ind_chars * (200 / len(individual))
print(f"\nProyección crecimiento (lineal):")
print(f"  100 tools individuales: ~{int(proj_100_ind/4)} tokens")
print(f"  200 tools individuales: ~{int(proj_200_ind/4)} tokens (caso GitHub MCP donde rompió)")
print(f"\n  Consolidado, 100 sub-acciones (en ~22 tools): ~{int(con_tokens * (22/16))} tokens")
print(f"  Consolidado, 200 sub-acciones (en ~30 tools): ~{int(con_tokens * (30/16))} tokens")
