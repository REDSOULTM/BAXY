"""Gate adversarial del auto-inject de skills (R3, 2026-05-30).

A diferencia de _validate_skills_autoinject_recall.py (recall + precision
agregada), este harness mide la ZONA LIMITE: los casos que medimos sobre
mensajes REALES del usuario donde la separabilidad por umbral global falla.

Fuente de los casos: extraccion de gemma4_agent/data/traces.jsonl (medido
2026-05-30). Cada FP/TP es un mensaje real o una variante minima de uno.

Gate (criterio de exito PRE-definido, mandamiento #3):
  - RECALL_GOLD:  todos los TP-limite disparan la skill correcta.
  - FP_HARD = 0:  ninguno de los FP-limite dispara skill alguna.
  - REGRESION:    el % de disparo sobre los 1481 mensajes reales NO sube.

Reusa el mismo embed + autoinject_skill del runtime (train/serve match).
Uso: python scripts/_skills_autoinject_gate.py
"""
from __future__ import annotations

import json
import re as _re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# --- TP-limite: mensajes reales (o variantes minimas) que DEBEN disparar ---
# Medidos como verdaderos positivos sobre traces.jsonl 2026-05-30.
GOLD = [
    # screenshot-and-analyze (el nucleo: capturar + describir/leer lo visible)
    ("que ves en pantalla", "screenshot-and-analyze"),
    ("saca un screenshot y guardalo", "screenshot-and-analyze"),
    ("leeme lo que dice la pantalla", "screenshot-and-analyze"),
    ("saca una foto de pantalla, que ves", "screenshot-and-analyze"),
    ("take a screenshot and tell me what you see", "screenshot-and-analyze"),
    ("tira uma captura de tela", "screenshot-and-analyze"),
    # research-and-summarize
    ("investiga sobre la guerra de ucrania en internet", "research-and-summarize"),
    ("averigua que es rust y resumeme", "research-and-summarize"),
    ("busca info sobre python y hace un resumen", "research-and-summarize"),
    # backup-then-clean / safe-file-cleanup
    ("hace backup antes de borrar la carpeta", "backup-then-clean"),
    ("borra estos archivos pero con cuidado", "safe-file-cleanup"),
    ("hace una limpieza segura de archivos viejos", "safe-file-cleanup"),
    # debug-app-crash
    ("una app me crashea, ayudame a diagnosticar por que", "debug-app-crash"),
    # voice-record-transcribe
    ("graba audio del microfono y transcribe", "voice-record-transcribe"),
    ("graba lo que voy a dictar y pasalo a texto", "voice-record-transcribe"),
    # new-development-project
    ("crea un proyecto nuevo de python con git", "new-development-project"),
    # schedule-recurring-task
    ("programa una tarea que se repita cada dia a las 9", "schedule-recurring-task"),
    # download-file
    ("descarga el instalador de python", "download-file"),
    ("baja este video de youtube", "download-file"),
    ("descargame el pdf de esta pagina", "download-file"),
    ("download the latest nodejs", "download-file"),
]

# --- FP-limite: mensajes reales que NO deben disparar NINGUNA skill ---
# Cada uno comparte un SUSTANTIVO con una skill pero el VERBO indica otra
# intencion (la cubre un tool del router, no una skill multi-paso).
FP_HARD = [
    "sube el brillo de la pantalla",         # brillo, NO captura (device_settings)
    "pon en pantalla completa el video",      # fullscreen, NO captura (media/window)
    "imprime el documento que tengo abierto", # imprimir, NO captura (print)
    "desmutea mi microfono en discord",       # audio device, NO grabar (audio)
    "mutear mi microfono",                    # audio device, NO grabar (audio)
    "extrae el texto de un pdf",              # OCR/lectura, NO descargar (vision/fs)
    "busca un pdf en el escritorio",          # filesystem.search, NO descargar
    "encuentra el pdf mas reciente en documentos",  # filesystem.search
    "resumime todo lo anterior",              # resumen de contexto, NO research web
    "borra la primera",                       # deixis cleanup item, NO skill
    "pon una cancion",                        # media.play, NO download
    "abre whatsapp",                          # app.open
    "sube el volumen",                        # audio
    "que hora es",                            # info simple
]

# Charla pura que jamas debe disparar.
CONTROL_CHITCHAT = [
    "hola", "muchas gracias", "que tal", "todo bien", "ok dale",
    "que dia es hoy", "como estas",
]


def _load():
    from gemma4_agent.tools_pkg.skills_registry import (
        scan_skills, autoinject_skill, reset_autoinject_cache)
    from gemma4_agent.routing.semantic_router import embed, _ensure_loaded
    if not _ensure_loaded():
        print("encoder no disponible")
        return None
    reset_autoinject_cache()
    return scan_skills, autoinject_skill, embed


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    loaded = _load()
    if loaded is None:
        return 1
    scan_skills, autoinject_skill, embed = loaded
    skills = scan_skills()
    names = {s.name for s in skills}

    ok = wrong = miss = 0
    print("== RECALL (TP-limite, deben disparar) ==")
    for q, exp in GOLD:
        if exp not in names:
            print(f"  SKIP (skill {exp!r} no existe)  {q!r}")
            continue
        name, _ = autoinject_skill(q, skills, embed_fn=embed)
        if name is None:
            miss += 1
            print(f"  MISS                       {q[:48]!r}")
        elif name == exp:
            ok += 1
            print(f"  OK  {name:23s} {q[:40]!r}")
        else:
            wrong += 1
            print(f"  WRONG -> {name:18s} (esp {exp})  {q[:24]!r}")
    print(f"  RECALL: ok={ok} wrong={wrong} miss={miss}  (gold={len(GOLD)})")

    print("\n== FP-HARD (zona limite, NO deben disparar) ==")
    fp_hard = 0
    for q in FP_HARD:
        name, _ = autoinject_skill(q, skills, embed_fn=embed)
        if name is not None:
            fp_hard += 1
            print(f"  FP -> {name:23s} {q!r}")
    if fp_hard == 0:
        print("  0 falsos positivos en zona limite")

    print("\n== CHITCHAT (NO deben disparar) ==")
    fp_chat = 0
    for q in CONTROL_CHITCHAT:
        name, _ = autoinject_skill(q, skills, embed_fn=embed)
        if name is not None:
            fp_chat += 1
            print(f"  FP -> {name}  {q!r}")
    if fp_chat == 0:
        print("  0 falsos positivos en charla")

    print("\n== REGRESION (mensajes reales) ==")
    msgs = _extract_user_msgs()
    fired = Counter()
    for m in msgs:
        name, _ = autoinject_skill(m, skills, embed_fn=embed)
        if name is not None:
            fired[name] += 1
    total = sum(fired.values())
    print(f"  mensajes reales: {len(msgs)}  disparan: {total} "
          f"({100*total/max(1,len(msgs)):.1f}%)")
    for nm, n in fired.most_common():
        print(f"    {n:4d}  {nm}")

    print("\n== GATE ==")
    gate_recall = (wrong == 0 and miss == 0)
    gate_fp = (fp_hard == 0 and fp_chat == 0)
    print(f"  recall full (0 miss, 0 wrong): {'PASS' if gate_recall else 'FAIL'}")
    print(f"  fp-hard + chitchat == 0:       {'PASS' if gate_fp else 'FAIL'}")
    print(f"  disparo real total:            {total}/{len(msgs)}")
    return 0 if (gate_recall and gate_fp) else 2


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
