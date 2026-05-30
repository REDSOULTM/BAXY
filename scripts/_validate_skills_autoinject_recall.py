"""Valida recall + precision del auto-inject de skills (R3, 2026-05-30).

Mide DOS cosas sobre las descripciones de skills (las que disparan el auto-inject):
  1. RECALL: casos GOLD (query -> skill esperada) que disparan correctamente.
  2. PRECISION: sobre los mensajes REALES del usuario, cuantos disparan una skill
     por ERROR (falso positivo). El gate del proyecto es ~0 falsos positivos en
     charla/comandos simples.

Reusa el mismo embed + autoinject_skill del runtime (train/serve match).

Uso: python scripts/_validate_skills_autoinject_recall.py
"""
from __future__ import annotations

import json
import re as _re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

GOLD = [
    ("saca una captura y dime que ves", "screenshot-and-analyze"),
    ("toma un screenshot y describilo", "screenshot-and-analyze"),
    ("que aparece en mi pantalla ahora", "screenshot-and-analyze"),
    ("investiga sobre la guerra de ucrania en internet", "research-and-summarize"),
    ("averigua que es rust y resumeme", "research-and-summarize"),
    ("busca info sobre python y hace un resumen", "research-and-summarize"),
    ("hace backup antes de borrar la carpeta", "backup-then-clean"),
    ("borra estos archivos pero con cuidado", "safe-file-cleanup"),
    ("mi app se colgo, diagnostica por que", "debug-app-crash"),
    ("graba audio del microfono y transcribe", "voice-record-transcribe"),
    ("crea un proyecto nuevo de python con git", "new-development-project"),
    ("programa una tarea para cada dia a las 9", "schedule-recurring-task"),
    ("descarga el instalador de python", "download-file"),
    ("baja este video de youtube", "download-file"),
    ("descargame el pdf de esta pagina", "download-file"),
    ("download the latest nodejs", "download-file"),
]

# Mensajes de control que NO deben disparar ninguna skill (charla + comandos simples).
CONTROL_NO_FIRE = [
    "hola", "muchas gracias", "que tal", "todo bien", "ok dale",
    "abre spotify", "sube el volumen", "que hora es", "cierra steam",
    "pon una cancion", "abre whatsapp", "que dia es hoy",
]


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    from gemma4_agent.tools_pkg.skills_registry import (
        scan_skills, autoinject_skill, reset_autoinject_cache)
    from gemma4_agent.routing.semantic_router import embed, _ensure_loaded
    if not _ensure_loaded():
        print("encoder no disponible")
        return 1
    reset_autoinject_cache()
    skills = scan_skills()
    names = {s.name for s in skills}
    print(f"Skills: {sorted(names)}\n")

    correct = wrong = miss = 0
    print("== RECALL (GOLD) ==")
    for q, exp in GOLD:
        if exp not in names:
            print(f"  SKIP (skill {exp!r} no existe)  {q!r}")
            continue
        name, _ = autoinject_skill(q, skills, embed_fn=embed)
        if name is None:
            miss += 1
            print(f"  MISS                     {q[:45]!r}")
        elif name == exp:
            correct += 1
            print(f"  OK  {name:22s} {q[:38]!r}")
        else:
            wrong += 1
            print(f"  WRONG -> {name:17s} (esp {exp})  {q[:26]!r}")
    print(f"\n  RECALL: correct={correct} wrong={wrong} miss={miss}")

    print("\n== CONTROL (no debe disparar) ==")
    fp_control = 0
    for q in CONTROL_NO_FIRE:
        name, _ = autoinject_skill(q, skills, embed_fn=embed)
        if name is not None:
            fp_control += 1
            print(f"  FALSO POSITIVO -> {name}  {q!r}")
    if fp_control == 0:
        print("  0 falsos positivos en control")

    print("\n== PRECISION (mensajes reales) ==")
    msgs = _extract_user_msgs()
    fired = Counter()
    for m in msgs:
        name, _ = autoinject_skill(m, skills, embed_fn=embed)
        if name is not None:
            fired[name] += 1
    print(f"  mensajes reales: {len(msgs)}")
    for nm, n in fired.most_common():
        print(f"    {n:4d}  {nm}")
    print(f"  total disparan skill: {sum(fired.values())}/{len(msgs)} "
          f"({100*sum(fired.values())/max(1,len(msgs)):.1f}%)")
    return 0


def _extract_user_msgs() -> list[str]:
    traces = ROOT / "gemma4_agent" / "data" / "traces.jsonl"
    if not traces.exists():
        return []
    msgs, seen = [], set()
    for line in traces.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("kind") == "request_start":
            c = d.get("content") or {}
            t = (c.get("preview") or c.get("text") or "").strip()
            k = t.lower()
            # Excluir mensajes de test automatizado (phrase_hook_test_*, etc) —
            # no son del usuario real y contaminan la métrica de precisión.
            if _re.search(r"phrase_hook_test|hook_test_\d|_\d{10}", t):
                continue
            if t and 6 < len(t) < 120 and k not in seen:
                seen.add(k)
                msgs.append(t)
    return msgs


if __name__ == "__main__":
    raise SystemExit(main())
