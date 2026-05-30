"""Gate del selector de microagents (R3.3, 2026-05-30).

Antes: substring matching de triggers daba FP graves ("RAG" ⊂ "Dragon", "que es"
⊂ "estoy"/"gordo") — 47/1492 mensajes reales disparaban glossary con jerga
irrelevante (dañino para el modelo chico, arXiv:2502.01609).

Ahora: SEMÁNTICO (embeddings multi-vector + abstención por umbral/margen) para
intención (troubleshoot/windows/cheat-sheet) + word-boundary LÉXICO para términos
técnicos exactos (glossary: HKCR/GGUF/VRAM). Multilingüe, NO substring.

Gate:
  - HARD-NEG = 0: ninguno de los FP medidos dispara microagent alguno.
  - RECALL: los casos legítimos disparan el microagent correcto.
  - REGRESIÓN: el % de disparo sobre 1481 mensajes reales BAJA (era 4.1%).

Uso: python scripts/_microagents_gate.py
"""
from __future__ import annotations

import json
import re as _re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Casos legítimos (deben disparar el microagent indicado).
GOLD = [
    ("una app no abre y no responde, ayudame", "troubleshoot"),
    ("el micrófono no anda, qué hago", "troubleshoot"),
    ("algo se rompió y dejó de funcionar", "troubleshoot"),
    ("cómo ejecuto un comando en powershell", "windows-commands"),
    ("qué comando uso en la terminal para esto", "windows-commands"),
    ("qué cosas podés hacer por mí", "tools-cheat-sheet"),
    ("en qué me podés ayudar", "tools-cheat-sheet"),
    ("qué es mmproj", "glossary"),          # término técnico exacto
    ("explicame qué es la VRAM", "glossary"),
    ("qué significa GGUF", "glossary"),
]

# Hard-negatives medidos sobre traces.jsonl — NO deben disparar NINGÚN microagent.
HARD_NEG = [
    "House of Dragon",                            # "RAG" ⊂ "Dragon"
    "dile a Sebastián que es muy gordo",          # "que es" substring
    "puedes reanudar el video que estoy viendo",  # "que es" ⊂ "estoy"
    "Investiga en internet que es el h2o",        # pregunta general, no jerga
    "que es la fotosintesis",                     # conocimiento general
    "abre spotify",
    "pon una canción",
    "que hora es",
    "sube el volumen",
    "dile a juan que es tarde",
    "mutea el sonido",                            # comando audio, no troubleshoot
    "silencia el audio",
    "desmutea mi micrófono en discord",
    "cambia el micrófono por defecto",
]


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    from gemma4_agent.memory_pkg.microagents import (
        load_microagents, select_microagents, reset_microagent_emb_cache)
    from gemma4_agent.routing.semantic_router import embed, _ensure_loaded
    if not _ensure_loaded():
        print("encoder no disponible")
        return 1
    reset_microagent_emb_cache()
    mas = load_microagents()
    names = {m.name for m in mas}
    print(f"Microagents: {sorted(names)}\n")

    ok = wrong = miss = 0
    print("== RECALL (GOLD) ==")
    for q, exp in GOLD:
        sel = select_microagents(q, mas, embed_fn=embed)
        got = {m.name for m in sel}
        if exp in got:
            ok += 1
            extra = got - {exp}
            tag = f"OK (+{extra})" if extra else "OK"
            print(f"  {tag:14s} {exp:18s} {q[:38]!r}")
        elif not got:
            miss += 1
            print(f"  MISS           {exp:18s} {q[:38]!r}")
        else:
            wrong += 1
            print(f"  WRONG -> {got}  esp {exp}  {q[:24]!r}")
    print(f"  RECALL: ok={ok} wrong={wrong} miss={miss} (gold={len(GOLD)})")

    print("\n== HARD-NEG (NO deben disparar) ==")
    fp = 0
    for q in HARD_NEG:
        sel = select_microagents(q, mas, embed_fn=embed)
        if sel:
            fp += 1
            print(f"  FP -> {[m.name for m in sel]}  {q!r}")
    if fp == 0:
        print("  0 falsos positivos en hard-negatives")

    print("\n== REGRESIÓN (mensajes reales) ==")
    msgs = _extract_user_msgs()
    fired = Counter()
    for m in msgs:
        for ma in select_microagents(m, mas, embed_fn=embed):
            fired[ma.name] += 1
    total = sum(fired.values())
    print(f"  mensajes reales: {len(msgs)}  disparan: {total} "
          f"({100*total/max(1,len(msgs)):.1f}%)  (antes: 61/1492 = 4.1%)")
    for nm, n in fired.most_common():
        print(f"    {n:4d}  {nm}")

    print("\n== GATE ==")
    g_recall = (wrong == 0)
    g_fp = (fp == 0)
    print(f"  recall (0 wrong):  {'PASS' if g_recall else 'FAIL'} (ok={ok}/{len(GOLD)})")
    print(f"  hard-neg == 0:     {'PASS' if g_fp else 'FAIL'}")
    return 0 if (g_recall and g_fp) else 2


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
            if _re.search(r"phrase_hook_test|hook_test_\d|_\d{10}", t):
                continue
            if t and 6 < len(t) < 120 and k not in seen:
                seen.add(k)
                msgs.append(t)
    return msgs


if __name__ == "__main__":
    raise SystemExit(main())
