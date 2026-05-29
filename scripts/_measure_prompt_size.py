"""Mide el tamano del system prompt en chars y tokens estimados,
desglosado por seccion (CORE vs TOOL_RULES vs tools schemas).

Tokens estimados con tiktoken (cl100k aprox). El tokenizer real de Gemma 4
no esta en este venv; uso aproximacion: 1 tok ~= 3.6 chars para texto
estructurado mixto (medido empiricamente en el log: prompt 13.6k tok =
~48-50k chars).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.agent_core.agent_prompt import (
    TOOL_RULES, build_system_prompt, _core_for_profile,
)

CHARS_PER_TOK = 3.6  # aprox para texto mixto en tokenizer SentencePiece

def stats(label, text):
    chars = len(text)
    toks = int(chars / CHARS_PER_TOK)
    print(f"  {label:30s} {chars:>8,} chars   ~{toks:>6,} toks")
    return chars, toks

print("=" * 70)
print("SYSTEM PROMPT BREAKDOWN")
print("=" * 70)

core = _core_for_profile()
print("\n[CORE — siempre presente]")
stats("CORE", core)

print(f"\n[TOOL_RULES — {len(TOOL_RULES)} entradas]")
# rules deduplicadas
seen = set()
unique_rules = []
for name, rule in sorted(TOOL_RULES.items()):
    rid = id(rule)
    if rid in seen:
        continue
    seen.add(rid)
    unique_rules.append((name, rule))

print(f"  ({len(unique_rules)} unicas tras deduplicar)")
total_rule_chars = 0
total_rule_toks = 0
for name, rule in sorted(unique_rules, key=lambda x: -len(x[1])):
    c, t = stats(name, rule)
    total_rule_chars += c
    total_rule_toks += t

print(f"\n  {'TOTAL TOOL_RULES':30s} {total_rule_chars:>8,} chars   ~{total_rule_toks:>6,} toks")

print("\n[ESCENARIOS]")
for label, names in [
    ("None (legacy: TODAS rules)", None),
    ("[] (smalltalk: solo CORE)", []),
    ("['web_search']", ["web_search"]),
    ("['system','gui','window']", ["system", "gui", "window"]),
    ("['system','gui','window','filesystem','app']",
     ["system", "gui", "window", "filesystem", "app"]),
]:
    p = build_system_prompt(names)
    stats(label, p)

# Mostrar las 15 reglas mas pesadas (candidatos a recortar):
print("\n[TOP 15 reglas mas pesadas — candidatas a recortar]")
ranked = sorted(unique_rules, key=lambda x: -len(x[1]))[:15]
for name, rule in ranked:
    c, t = stats(name, rule)

# Mostrar reglas chicas (probablemente OK)
print("\n[BOTTOM 10 reglas — chicas, no urgente]")
ranked_bottom = sorted(unique_rules, key=lambda x: len(x[1]))[:10]
for name, rule in ranked_bottom:
    c, t = stats(name, rule)
